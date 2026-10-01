"""Unfinished work stays visible while completed history is paged and scoped."""
import json
import subprocess
import sys
from urllib.parse import urlencode

import pytest

from scripts.dev_config import ROOT
from test_services import call


@pytest.fixture(scope="module")
def workflow_rows(cluster):
    # This module's disposable database is isolated from all other HTTP tests.
    # Equal completion timestamps exercise the cursor's unique-ID tie breaker.
    code = '''
import json
from datetime import datetime, timezone
from platform_core.tenancy import tenant_scope
from services.workflow.models import Change
result = {}
for tenant, site, prefix, completed_count in [
    ("demo", "ashburn", "ashburn", 115),
    ("demo", "dallas", "dallas", 3),
    ("other", "ashburn", "other", 2),
]:
    with tenant_scope(tenant):
        states = ["awaiting_approval", "awaiting_nlyte", "approved", "executing", "replan_required"] if prefix == "ashburn" else ["executing"]
        active = [Change(tenant=tenant, site=site, proposer="alex", approver="jordan",
                         idempotency_key=f"{prefix}-active-{i}", payload_hash="0" * 64,
                         payload={"asset_id": "asset-000", "rack_id": "rack-00"}, state=state)
                  for i, state in enumerate(states)]
        completed = [Change(tenant=tenant, site=site, proposer="alex", approver="jordan",
                            idempotency_key=f"{prefix}-completed-{i}", payload_hash="0" * 64,
                            payload={"asset_id": "asset-000", "rack_id": "rack-00"}, state="completed")
                     for i in range(completed_count)]
        Change.objects.bulk_create(active + completed)
        Change.objects.filter(id__in=[c.id for c in active]).update(created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
        Change.objects.filter(id__in=[c.id for c in completed]).update(created_at=datetime(2025, 2, 1, tzinfo=timezone.utc))
        result[prefix] = {"active": [str(c.id) for c in active], "completed": [str(c.id) for c in completed]}
print(json.dumps(result))
'''
    result = subprocess.run([sys.executable, "manage.py", "shell", "-c", code],
                            cwd=ROOT, env=cluster[3]["workflow"], check=True, capture_output=True, text=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_older_unfinished_changes_survive_more_than_one_hundred_completed_changes(cluster, workflow_rows):
    response = call(cluster, "workflow", "changes")
    assert response.status_code == 200, response.text
    result = response.json()
    expected_active = set(workflow_rows["ashburn"]["active"] + workflow_rows["dallas"]["active"])
    assert result["active_count"] == len(expected_active)
    assert {c["id"] for c in result["items"] if c["state"] != "completed"} == expected_active
    assert len(result["items"]) == len(expected_active) + 50
    assert result["history"]["limit"] == 50
    assert result["history"]["has_more"] is True
    assert result["history"]["next_cursor"]


@pytest.mark.parametrize("role,prefixes", [("operator", ["ashburn", "dallas"]), ("ashburn", ["ashburn"]), ("other", ["other"])])
def test_completed_history_pagination_preserves_active_work_and_scope(cluster, workflow_rows, role, prefixes):
    expected_active = {row for prefix in prefixes for row in workflow_rows[prefix]["active"]}
    expected_completed = {row for prefix in prefixes for row in workflow_rows[prefix]["completed"]}
    completed_ids = []
    query = {"history_limit": 37}
    for _ in range(10):
        response = call(cluster, "workflow", "changes?" + urlencode(query), role=role)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["active_count"] == len(expected_active)
        assert {c["id"] for c in result["items"] if c["state"] != "completed"} == expected_active
        page = [c["id"] for c in result["items"] if c["state"] == "completed"]
        assert len(page) <= 37
        completed_ids.extend(page)
        history = result["history"]
        assert history["has_more"] == (history["next_cursor"] is not None)
        if not history["has_more"]:
            break
        query["history_cursor"] = history["next_cursor"]
    else:
        pytest.fail("Completed history did not terminate")
    assert len(completed_ids) == len(expected_completed)
    assert set(completed_ids) == expected_completed
    assert completed_ids == sorted(expected_completed, reverse=True)


def test_history_cursor_cannot_be_reused_outside_its_tenant_and_site_scope(cluster, workflow_rows):
    first = call(cluster, "workflow", "changes?history_limit=1").json()
    path = "changes?" + urlencode({"history_cursor": first["history"]["next_cursor"]})
    assert call(cluster, "workflow", path, role="ashburn").status_code == 400
    assert call(cluster, "workflow", path, role="other").status_code == 400


def test_new_completions_do_not_shift_an_existing_history_cursor(cluster, workflow_rows):
    first = call(cluster, "workflow", "changes?history_limit=37").json()
    completed_ids = [c["id"] for c in first["items"] if c["state"] == "completed"]
    code = '''
from platform_core.tenancy import tenant_scope
from services.workflow.models import Change
with tenant_scope("demo"):
    c = Change.objects.create(tenant="demo", site="ashburn", proposer="alex", approver="jordan",
                              idempotency_key="completed-during-pagination", payload_hash="0" * 64,
                              payload={}, state="completed")
    print(c.id)
'''
    result = subprocess.run([sys.executable, "manage.py", "shell", "-c", code],
                            cwd=ROOT, env=cluster[3]["workflow"], check=True, capture_output=True, text=True)
    inserted_id = result.stdout.strip().splitlines()[-1]
    try:
        cursor = first["history"]["next_cursor"]
        for _ in range(10):
            if cursor is None:
                break
            result = call(cluster, "workflow", "changes?" + urlencode({"history_limit": 37, "history_cursor": cursor})).json()
            completed_ids.extend(c["id"] for c in result["items"] if c["state"] == "completed")
            cursor = result["history"]["next_cursor"]
        else:
            pytest.fail("Completed history did not terminate")
        expected = workflow_rows["ashburn"]["completed"] + workflow_rows["dallas"]["completed"]
        assert completed_ids == sorted(expected, reverse=True)
        restarted = call(cluster, "workflow", "changes?history_limit=1").json()
        assert [c["id"] for c in restarted["items"] if c["state"] == "completed"] == [inserted_id]
    finally:
        cleanup = f'''
from platform_core.tenancy import tenant_scope
from services.workflow.models import Change
with tenant_scope("demo"):
    Change.objects.filter(pk={inserted_id!r}).delete()
'''
        subprocess.run([sys.executable, "manage.py", "shell", "-c", cleanup],
                       cwd=ROOT, env=cluster[3]["workflow"], check=True, capture_output=True, text=True)


def test_change_detail_retrieves_old_records_without_widening_scope(cluster, workflow_rows):
    for row_id in workflow_rows["ashburn"]["active"] + workflow_rows["ashburn"]["completed"][:1]:
        response = call(cluster, "workflow", "changes/" + row_id, role="ashburn")
        assert response.status_code == 200, response.text
        assert response.json()["id"] == row_id
        assert call(cluster, "workflow", "changes/" + row_id, role="other").status_code == 404
    dallas_id = workflow_rows["dallas"]["active"][0]
    assert call(cluster, "workflow", "changes/" + dallas_id, role="ashburn").status_code == 404
    assert call(cluster, "workflow", "changes/" + dallas_id, role="operator").status_code == 200


@pytest.mark.parametrize("query", ["history_limit=0", "history_limit=-1", "history_limit=101", "history_limit=abc", "history_cursor=", "history_cursor=invalid"])
def test_malformed_history_parameters_return_client_errors(cluster, query):
    response = call(cluster, "workflow", "changes?" + query)
    assert response.status_code == 400, response.text
