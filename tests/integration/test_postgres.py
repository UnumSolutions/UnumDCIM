"""Concurrency and database enforcement checks that SQLite cannot establish."""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import uuid

import psycopg
import pytest

from test_services import call, proposal

pytestmark = pytest.mark.skipif(not os.environ.get("UNUM_TEST_PG_DSN"), reason="Run scripts/qualify.py for PostgreSQL")


def connect(env):
    return psycopg.connect(host=env["PGHOST"], port=env["PGPORT"], dbname=env["PGDATABASE"],
        user=env["PGUSER"], password=env["PGPASSWORD"], sslmode=env["PGSSLMODE"], autocommit=True)


def simultaneous(commands):
    barrier = threading.Barrier(len(commands))
    def invoke(command):
        barrier.wait(timeout=10)
        return command()
    with ThreadPoolExecutor(max_workers=len(commands)) as executor:
        return list(executor.map(invoke, commands))


def test_runtime_role_and_database_tenant_enforcement(cluster):
    with connect(cluster[3]["inventory"]) as db:
        superuser, bypass = db.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
        assert not superuser and not bypass
        assert db.execute("SELECT count(*) FROM inventory_asset").fetchone()[0] == 0
        db.execute("SELECT set_config('unum.tenant', 'demo', false)")
        assert db.execute("SELECT count(*) FROM inventory_asset").fetchone()[0] == 128
        flags = db.execute("SELECT relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner)=current_user FROM pg_class WHERE relname='inventory_asset'").fetchone()
        assert flags == (True, True, False)
        db.execute("SELECT set_config('unum.tenant', 'other', false)")
        assert db.execute("SELECT count(*) FROM inventory_asset").fetchone()[0] == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("INSERT INTO inventory_asset (id,tenant,site,name,manufacturer,model,serial,asset_tag,height_u,watts,lifecycle,revision,updated_at) VALUES ('forged','demo','ashburn','forged','','','','',1,1,'active',1,now())")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("ALTER TABLE inventory_asset DISABLE ROW LEVEL SECURITY")


def test_overlapping_reservations_have_exactly_one_winner(cluster):
    commands = [proposal(asset, "rack-24") | {"site": "dallas", "request_id": str(uuid.uuid4())}
        for asset in ("asset-096", "asset-097")]
    responses = simultaneous([lambda d=d: call(cluster, "placement", "reservations", d, role="service") for d in commands])
    assert sorted(r.status_code for r in responses) == [201, 409], [r.text for r in responses]
    winner = next(d for d, r in zip(commands, responses) if r.status_code == 201)
    commits = simultaneous([lambda: call(cluster, "placement", f"reservations/{winner['request_id']}/commit", {}, role="service") for _ in range(2)])
    assert [r.status_code for r in commits] == [200, 200], [r.text for r in commits]
    assert {r.json()["revision"] for r in commits} == {2}


def test_duplicate_reservation_and_execution_are_idempotent(cluster):
    data = proposal("asset-100", "rack-25") | {"site": "dallas", "request_id": str(uuid.uuid4())}
    responses = simultaneous([lambda: call(cluster, "placement", "reservations", data, role="service") for _ in range(2)])
    assert all(r.status_code in (200, 201) for r in responses), [r.text for r in responses]
    data = proposal("asset-104", "rack-26") | {"site": "dallas"}
    proposed = call(cluster, "workflow", "changes", data)
    assert proposed.status_code == 201, proposed.text
    change = proposed.json()
    approved = call(cluster, "workflow", f"changes/{change['id']}/approve", {"expected_revision": 1}, role="approver")
    assert approved.status_code == 200, approved.text
    results = simultaneous([lambda: call(cluster, "workflow", f"changes/{change['id']}/execute", {}) for _ in range(2)])
    assert all(r.status_code == 200 and r.json()["state"] == "completed" for r in results), [r.text for r in results]
    scene = call(cluster, "placement", "scene").json()
    assert next(p for p in scene["placements"] if p["asset_id"] == "asset-104")["revision"] == 2


def test_audit_entries_cannot_be_rewritten_by_runtime_role(cluster):
    response = call(cluster, "inventory", "assets/asset-000", {"name": "Audited asset", "expected_revision": 1}, method="PATCH")
    assert response.status_code == 200, response.text
    with connect(cluster[3]["inventory"]) as db:
        db.execute("SELECT set_config('unum.tenant', 'demo', false)")
        assert db.execute("SELECT count(*) FROM platform_core_auditentry").fetchone()[0] > 0
        for operation in ("UPDATE platform_core_auditentry SET digest='rewritten'", "DELETE FROM platform_core_auditentry"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute(operation)
