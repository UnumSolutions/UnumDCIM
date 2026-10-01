"""Real HTTP services, independent databases and durable workflow recovery."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

import httpx
import pytest
from scripts.dev_config import ROOT, SERVICES, environment



def call(cluster, service, path, body=None, role="operator", method=None):
    token="demo-"+role+"-token" if role!="other" else "demo-other-tenant"
    return httpx.request(method or ("GET" if body is None else "POST"),cluster[0][service]+"/api/v1/"+path,
                         json=body,headers={"Authorization":"Bearer "+token},timeout=10)


def proposal(asset="asset-000", rack="rack-00", u=35, revision=1):
    return {"asset_id":asset,"rack_id":rack,"u":u,"face":"front","expected_revision":revision,
            "authority_epoch":1,"site":"ashburn","idempotency_key":str(uuid.uuid4())}


def test_auth_and_tenant_isolation(cluster):
    assert httpx.get(cluster[0]["inventory"]+"/api/v1/assets").status_code==401
    assert call(cluster,"inventory","assets",role="other").json()["items"]==[]
    assert call(cluster,"inventory","assets/asset-000",role="other").status_code==404
    assert len(call(cluster,"inventory","assets").json()["items"])==128


@pytest.mark.parametrize("service", SERVICES)
def test_identity_is_verified_scoped_and_not_cached(cluster, service):
    url = cluster[0][service] + "/api/v1/identity"
    assert httpx.get(url).status_code == 401
    response = call(cluster, service, "identity", role="ashburn")
    assert response.status_code == 200
    assert response.json() == {"actor": "site-operator", "tenant": "demo", "sites": ["ashburn"], "role": "operator"}
    assert response.headers["cache-control"] == "no-store"
    response = httpx.get(url, headers={"Authorization": "Bearer demo-other-tenant", "X-Unum-Tenant": "demo", "X-Unum-Role": "operator"})
    assert response.json() == {"actor": "outsider", "tenant": "other", "sites": ["ashburn", "dallas"], "role": "admin"}


def test_location_scope_and_cross_site_moves(cluster):
    scene=call(cluster,"placement","scene").json()
    assert {r["site"] for r in scene["rooms"]}=={"ashburn","dallas"}
    limited=call(cluster,"placement","scene",role="ashburn").json()
    assert {r["site"] for r in limited["rooms"]}=={"ashburn"}
    assert call(cluster,"inventory","assets/asset-096",role="ashburn").status_code==403
    assert call(cluster,"placement","preview",proposal("asset-000","rack-24")).status_code==409


def test_occupied_preview_and_stale_revision(cluster):
    d=proposal(u=9)
    assert call(cluster,"placement","preview",d).status_code==409
    d["u"]=35;d["expected_revision"]=99
    assert call(cluster,"placement","preview",d).status_code==409


def test_move_lifecycle_idempotency_and_restart(cluster):
    d=proposal()
    response=call(cluster,"workflow","changes",d)
    assert response.status_code==201,response.text
    c=response.json()
    assert c["state"]=="awaiting_approval"
    assert call(cluster,"workflow","changes",d).json()["id"]==c["id"]
    assert call(cluster,"workflow","changes",d|{"u":36}).status_code==409
    placements=call(cluster,"placement","scene").json()["placements"]
    assert next(p for p in placements if p["asset_id"]==d["asset_id"])["u"]==3
    assert call(cluster,"workflow",f"changes/{c['id']}/approve",{"expected_revision":1}).status_code==403
    assert call(cluster,"workflow",f"changes/{c['id']}/execute",{}).status_code==409
    approved=call(cluster,"workflow",f"changes/{c['id']}/approve",{"expected_revision":1},role="approver")
    assert approved.status_code==200,approved.text
    result=call(cluster,"workflow",f"changes/{c['id']}/execute",{})
    assert result.status_code==200,result.text
    assert result.json()["state"]=="completed"
    assert call(cluster,"workflow",f"changes/{c['id']}/execute",{}).json()["state"]=="completed"
    ps=call(cluster,"placement","scene").json()["placements"]
    assert next(p for p in ps if p["asset_id"]==d["asset_id"])["revision"]==2
    # Re-run migrations/seed as an upgrade rehearsal: existing placement survives.
    subprocess.run([sys.executable,"manage.py","seed_demo"],cwd=ROOT,env=cluster[3]["placement"],check=True,capture_output=True)
    assert next(p for p in call(cluster,"placement","scene").json()["placements"] if p["asset_id"]==d["asset_id"])["u"]==35


def test_nlyte_owned_moves_remain_staged(cluster):
    response=call(cluster,"workflow","changes",proposal("asset-004","rack-01"))
    assert response.status_code==201,response.text
    c=response.json()
    assert c["state"]=="awaiting_nlyte"
    assert call(cluster,"workflow",f"changes/{c['id']}/approve",{"expected_revision":1},role="approver").status_code==409


def test_same_principal_admin_cannot_approve(cluster):
    r=call(cluster,"workflow","changes",proposal("asset-012","rack-03"),role="admin")
    c=r.json()
    assert r.status_code==201,r.text
    assert call(cluster,"workflow",f"changes/{c['id']}/approve",{"expected_revision":1},role="admin").status_code==403


def test_conflict_resolution_does_not_claim_convergence(cluster):
    status=call(cluster,"synchronization","status").json()
    c=status["conflicts"][0]
    assert not status["live_write_enabled"]
    r=call(cluster,"synchronization",f"conflicts/{c['id']}/resolve",{"expected_revision":c["revision"],"candidate":"unum"})
    assert r.status_code==200,r.text
    assert r.json()["state"]=="resolution_staged"
    assert call(cluster,"inventory","assets/asset-004").json()["asset_tag"]=="UD-10004"


def test_audit_and_outbox_are_durable(cluster):
    for service in ("workflow","placement","synchronization"):
        result=subprocess.run([sys.executable,"manage.py","verify_audit","--tenant","demo"],cwd=ROOT,env=cluster[3][service],capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        metrics=httpx.get(cluster[0][service]+"/metrics",headers={"Authorization":"Bearer demo-service-token"}).json()
        assert metrics["outbox_pending"]>0


def test_services_have_separate_databases(cluster):
    if "PGHOST" in cluster[3]["inventory"]:
        assert len({env["PGDATABASE"] for env in cluster[3].values()}) == 5
        assert len({env["PGUSER"] for env in cluster[3].values()}) == 5
    else:
        assert len(list(cluster[1].glob('*.sqlite3')))==5


def test_public_preflight_cannot_self_attest_signature(cluster):
    r=call(cluster,"registry","preflight",{"manifest_version":1,"status":"implemented","artifact":"x@sha256:"+"a"*64,
           "signature_verified":True,"supported_until":"2029-01-01"},role="admin")
    assert r.status_code==200
    assert not r.json()["allowed"]


def test_recovery_after_remote_commit_before_workflow_ack(cluster):
    d=proposal("asset-024","rack-06")
    response=call(cluster,"workflow","changes",d)
    assert response.status_code==201,response.text
    c=response.json()
    assert call(cluster,"workflow",f"changes/{c['id']}/approve",{"expected_revision":1},role="approver").status_code==200
    # Remote transaction completed, but workflow has not yet recorded completion.
    reserve=call(cluster,"placement","reservations",c["payload"]|{"request_id":c["id"]},role="service")
    assert reserve.status_code==201,reserve.text
    committed=call(cluster,"placement",f"reservations/{c['id']}/commit",{},role="service")
    assert committed.status_code==200,committed.text
    recovered=call(cluster,"workflow",f"changes/{c['id']}/execute",{})
    assert recovered.status_code==200,recovered.text
    assert recovered.json()["state"]=="completed"
    p=next(p for p in call(cluster,"placement","scene").json()["placements"] if p["asset_id"]==d["asset_id"])
    assert p["revision"]==2


def test_active_reservations_prevent_other_workflows(cluster):
    d=proposal("asset-036","rack-09",35)
    first=call(cluster,"placement","reservations",d|{"request_id":str(uuid.uuid4())},role="service")
    assert first.status_code==201,first.text
    other=proposal("asset-037","rack-09",35)
    second=call(cluster,"placement","reservations",other|{"request_id":str(uuid.uuid4())},role="service")
    assert second.status_code==409


def test_restart_one_module_preserves_others_and_state(cluster):
    urls,data,children,envs=cluster
    children["workflow"].terminate()
    children["workflow"].wait(timeout=5)
    assert call(cluster,"inventory","assets").status_code==200
    assert call(cluster,"placement","scene").status_code==200
    port=urls["workflow"].rsplit(":",1)[1]
    children["workflow"]=subprocess.Popen([sys.executable,"manage.py","runserver",f"127.0.0.1:{port}","--noreload"],cwd=ROOT,env=envs["workflow"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            response=call(cluster,"workflow","changes")
            if response.status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(.05)
    else:raise AssertionError("Workflow did not restart")
    assert any(c["state"]=="completed" for c in response.json()["items"])


def test_contracts_served_by_each_module(cluster):
    for service in SERVICES:
        r=call(cluster,service,"openapi")
        assert r.status_code==200,r.text
        assert r.json()["openapi"]=="3.1.0"
