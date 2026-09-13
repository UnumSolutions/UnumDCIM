"""Tenant delegation and recovery exercised across real isolated HTTP services."""
import json
import subprocess
import sys
from textwrap import dedent, indent

import httpx
import pytest
from scripts.dev_config import ROOT
from test_services import call, proposal


def manage(cluster, service, code):
    scoped = "from platform_core.tenancy import tenant_scope\nwith tenant_scope('demo'):\n" + indent(dedent(code), "    ")
    result = subprocess.run([sys.executable, "manage.py", "shell", "-c", scoped],
                            cwd=ROOT, env=cluster[3][service], check=True,
                            capture_output=True, text=True)
    return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""


def approved_change(cluster, data):
    response = call(cluster, "workflow", "changes", data)
    assert response.status_code == 201, response.text
    change = response.json()
    approved = call(cluster, "workflow", f"changes/{change['id']}/approve",
                    {"expected_revision": change["revision"]}, role="approver")
    assert approved.status_code == 200, approved.text
    return approved.json()


def placement(cluster, asset_id):
    return next(p for p in call(cluster, "placement", "scene").json()["placements"]
                if p["asset_id"] == asset_id)


def test_workflow_cannot_amplify_other_tenant_credentials(cluster):
    data = proposal("asset-048", "rack-12")
    direct = call(cluster, "inventory", "assets/asset-048", role="other")
    assert direct.status_code == 404
    response = call(cluster, "workflow", "changes", data, role="other")
    assert response.status_code == 403, response.text
    assert call(cluster, "workflow", "changes", role="other").json()["items"] == []
    assert placement(cluster, data["asset_id"])["revision"] == 1


def test_workflow_preserves_caller_site_restrictions(cluster):
    # Lying about the proposal's site must not acquire the service's Dallas grant.
    data = proposal("asset-096", "rack-24")
    response = call(cluster, "workflow", "changes", data, role="ashburn")
    assert response.status_code == 403, response.text
    response = call(cluster, "workflow", "changes", data | {"site": "dallas"}, role="ashburn")
    assert response.status_code == 403
    assert placement(cluster, data["asset_id"])["revision"] == 1


def test_delegated_service_scope_is_intersection_not_header_claims(cluster):
    url = cluster[0]["placement"] + "/api/v1/preview"
    data = proposal("asset-096", "rack-24") | {"site": "dallas"}
    headers = {"Authorization": "Bearer demo-service-token",
               "X-Unum-Caller-Authorization": "Bearer demo-ashburn-token",
               "X-Unum-Tenant": "demo", "X-Unum-Sites": "ashburn,dallas"}
    response = httpx.post(url, json=data, headers=headers)
    assert response.status_code == 403, response.text
    headers["X-Unum-Caller-Authorization"] = "Bearer demo-other-tenant"
    assert httpx.post(url, json=data, headers=headers).status_code == 403
    headers["Authorization"] = "Bearer demo-ashburn-token"
    headers["X-Unum-Caller-Authorization"] = "Bearer demo-admin-token"
    assert httpx.post(url, json=data, headers=headers).status_code == 403


def test_other_tenant_cannot_approve_or_execute_an_existing_change(cluster):
    change = approved_change(cluster, proposal("asset-051", "rack-12", u=39))
    path = f"changes/{change['id']}"
    assert call(cluster, "workflow", path + "/approve", {"expected_revision": change["revision"]},
                role="other").status_code == 404
    assert call(cluster, "workflow", path + "/execute", {}, role="other").status_code == 404
    assert placement(cluster, "asset-051")["revision"] == 1


def test_expired_reservation_becomes_terminal_and_requires_new_approval(cluster):
    data = proposal("asset-060", "rack-15")
    change = approved_change(cluster, data)
    response = call(cluster, "placement", "reservations",
                    change["payload"] | {"request_id": change["id"]}, role="service")
    assert response.status_code == 201, response.text
    manage(cluster, "placement", f'''
        from datetime import timedelta
        from django.utils import timezone
        from services.placement.models import Reservation
        Reservation.objects.filter(pk={change['id']!r}).update(expires_at=timezone.now()-timedelta(seconds=1))
    ''')
    response = call(cluster, "workflow", f"changes/{change['id']}/execute", {})
    assert response.status_code == 409, response.text
    assert response.json()["state"] == "replan_required"
    assert manage(cluster, "placement", f'''
        from services.placement.models import Reservation
        print(Reservation.objects.get(pk={change['id']!r}).state)
    ''') == "expired"
    repeated = call(cluster, "workflow", f"changes/{change['id']}/execute", {})
    assert repeated.status_code == 409
    assert repeated.json()["code"] == "replan_required"
    assert placement(cluster, data["asset_id"])["revision"] == 1
    fresh = proposal("asset-060", "rack-15")
    new_response = call(cluster, "workflow", "changes", fresh)
    assert new_response.status_code == 201, new_response.text
    new_change = new_response.json()
    assert new_change["id"] != change["id"]
    assert new_change["state"] == "awaiting_approval"
    assert new_change["approver"] == ""
    assert call(cluster, "workflow", f"changes/{new_change['id']}/execute", {}).status_code == 409
    assert call(cluster, "workflow", f"changes/{new_change['id']}/approve", {"expected_revision": 1},
                role="approver").status_code == 200
    assert call(cluster, "workflow", f"changes/{new_change['id']}/execute", {}).json()["state"] == "completed"
    assert placement(cluster, data["asset_id"])["revision"] == 2


def test_invalid_reserved_plan_is_released_and_terminal(cluster):
    data = proposal("asset-072", "rack-18")
    change = approved_change(cluster, data)
    assert call(cluster, "placement", "reservations", change["payload"] | {"request_id": change["id"]},
                role="service").status_code == 201
    manage(cluster, "placement", '''
        from services.placement.models import Placement
        Placement.objects.filter(asset_id="asset-072").update(revision=2)
    ''')
    response = call(cluster, "workflow", f"changes/{change['id']}/execute", {})
    assert response.status_code == 409, response.text
    assert response.json()["state"] == "replan_required"
    assert manage(cluster, "placement", f'''
        from services.placement.models import Reservation
        print(Reservation.objects.get(pk={change['id']!r}).state)
    ''') == "invalid"
    replacement = approved_change(cluster, proposal("asset-072", "rack-18", revision=2))
    response = call(cluster, "workflow", f"changes/{replacement['id']}/execute", {})
    assert response.status_code == 200, response.text
    assert placement(cluster, "asset-072")["revision"] == 3


def test_stale_plan_without_reservation_requires_replan(cluster):
    change = approved_change(cluster, proposal("asset-084", "rack-21"))
    manage(cluster, "placement", '''
        from services.placement.models import Placement
        Placement.objects.filter(asset_id="asset-084").update(revision=2)
    ''')
    response = call(cluster, "workflow", f"changes/{change['id']}/execute", {})
    assert response.status_code == 409, response.text
    assert response.json()["state"] == "replan_required"
    assert placement(cluster, "asset-084")["u"] == 3


@pytest.mark.parametrize("lost_path,asset,u", [("reservations", "asset-048", 35),
                                                ("commit", "asset-049", 39),
                                                ("unconfirmed_commit", "asset-050", 37)])
def test_lost_remote_ack_recovers_same_request_without_duplicate_move(cluster, lost_path, asset, u):
    change = approved_change(cluster, proposal(asset, "rack-12", u=u))
    # Invoke the real workflow endpoint with fault injection exactly after a real
    # placement HTTP transaction returns. Both service databases remain durable.
    result = manage(cluster, "workflow", f'''
        import json
        from unittest.mock import patch
        from django.test import Client
        from platform_core.api import Problem
        from services.workflow import views
        original_remote = views.remote
        def lose_ack(request, service, method, path, data=None):
            result = original_remote(request, service, method, path, data)
            if {lost_path!r} == "unconfirmed_commit" and path.endswith("/commit"):
                return {{"state": "held"}}
            if path == {lost_path!r} or path.endswith("/" + {lost_path!r}):
                raise Problem("Dependency unavailable: placement", 503)
            return result
        with patch.object(views, "remote", side_effect=lose_ack):
            response = Client().post("/api/v1/changes/{change['id']}/execute", data={{}},
                                     content_type="application/json",
                                     HTTP_AUTHORIZATION="Bearer demo-operator-token")
        print(json.dumps({{"status": response.status_code, "body": response.json()}}))
    ''')
    failed = json.loads(result)
    assert failed["status"] == 503, failed
    assert failed["body"]["state"] == "executing"
    revision_after_loss = placement(cluster, asset)["revision"]
    assert revision_after_loss == (1 if lost_path == "reservations" else 2)
    response = call(cluster, "workflow", f"changes/{change['id']}/execute", {})
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "completed"
    assert placement(cluster, asset)["revision"] == 2
    assert call(cluster, "workflow", f"changes/{change['id']}/execute", {}).json()["state"] == "completed"
    assert placement(cluster, asset)["revision"] == 2
    counts = json.loads(manage(cluster, "placement", f'''
        import json
        from services.placement.models import Reservation
        from platform_core.models import Outbox
        print(json.dumps({{"reservations": Reservation.objects.filter(asset_id={asset!r}).count(),
                           "confirmations": list(Outbox.objects.filter(payload__type="placement.confirmed", payload__entity={asset!r}).values_list("payload__actor", flat=True))}}))
    '''))
    assert counts == {"reservations": 1, "confirmations": ["alex"]}
