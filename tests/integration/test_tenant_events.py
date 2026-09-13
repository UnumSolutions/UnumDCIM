import subprocess
import sys

from scripts.dev_config import ROOT


def test_consumer_checks_trusted_tenant_and_rolls_back_failed_projection(cluster):
    script = '''
import uuid
from platform_core.events import consume
from platform_core.models import Inbox
from platform_core.tenancy import current_tenant, tenant_scope
from services.inventory.models import Asset

event = {"contract": "unum.event/1", "event_id": str(uuid.uuid4()), "tenant": "demo",
         "site": "ashburn", "producer": "test", "entity": "event-projection-test",
         "revision": 1, "authority_epoch": 1, "correlation_id": "test-correlation", "data": {}}
with tenant_scope("demo"):
    Asset.objects.create(id=event["entity"], tenant="demo", site="ashburn", name="before",
                         manufacturer="test", model="test", serial="test", asset_tag="test")

def project(event):
    assert current_tenant() == "demo"
    Asset.objects.filter(id=event["entity"], tenant="demo").update(name="after", revision=2)

def fail(event):
    project(event)
    raise RuntimeError("projection failed")

try:
    consume(event | {"tenant": "another-tenant"}, project, trusted_tenant="demo")
    raise AssertionError("Foreign tenant event was accepted")
except ValueError:
    pass
try:
    consume(event, fail, trusted_tenant="demo")
    raise AssertionError("Failed projection was accepted")
except RuntimeError as exc:
    assert str(exc) == "projection failed"
with tenant_scope("demo"):
    assert not Inbox.objects.filter(event_id=event["event_id"]).exists()
    assert Asset.objects.get(pk=event["entity"]).revision == 1
assert consume(event, project, trusted_tenant="demo") is True
assert consume(event, project, trusted_tenant="demo") is False
with tenant_scope("demo"):
    assert Asset.objects.get(pk=event["entity"]).revision == 2
    assert Inbox.objects.get(event_id=event["event_id"]).tenant == "demo"
assert current_tenant() is None
print("tenant validation, atomic rollback and duplicate suppression verified")
'''
    result = subprocess.run([sys.executable, "manage.py", "shell", "-c", script],
                            cwd=ROOT, env=cluster[3]["inventory"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
