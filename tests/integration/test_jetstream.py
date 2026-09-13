"""A real broker outage, restart, lost acknowledgement and durable projection."""
import asyncio
import json
import os
import subprocess
import sys
import time
from textwrap import indent

import nats
import pytest

from scripts.dev_config import ROOT
from test_services import call

pytestmark = pytest.mark.skipif(not os.environ.get("UNUM_TEST_NATS_URL"), reason="Run scripts/qualify.py for JetStream")


def shell(env, code):
    scoped = "from platform_core.tenancy import tenant_scope\nwith tenant_scope('demo'):\n" + indent(code, "    ")
    result = subprocess.run([sys.executable, "manage.py", "shell", "-c", scoped], cwd=ROOT, env=env,
        check=True, capture_output=True, text=True)
    return result.stdout.strip().splitlines()[-1]


def test_outage_restart_lost_ack_and_duplicate_projection(cluster):
    env = cluster[3]["inventory"] | {"UNUM_NATS_URL": os.environ["UNUM_TEST_NATS_URL"]}
    response = call(cluster, "inventory", "assets/asset-000", {"name": "Outbox test", "expected_revision": 1}, method="PATCH")
    assert response.status_code == 200, response.text
    event = json.loads(shell(env, "import json\nfrom platform_core.models import Outbox\nprint(json.dumps(Outbox.objects.get().payload))"))

    async def publish_before_lost_ack():
        nc = await nats.connect(env["UNUM_NATS_URL"], max_reconnect_attempts=1,
            reconnect_time_wait=0, allow_reconnect=False, connect_timeout=2)
        try:
            js = nc.jetstream()
            await js.add_stream(name="UNUM_QUALIFICATION", subjects=["unum.>"], storage="file")
            await js.publish("unum.inventory." + event["type"], json.dumps(event).encode(), headers={"Nats-Msg-Id": event["event_id"]})
        finally:
            await nc.drain()
    asyncio.run(publish_before_lost_ack())
    container = os.environ["UNUM_TEST_NATS_CONTAINER"]
    subprocess.run(["docker", "stop", "--time", "2", container], check=True, capture_output=True)
    try:
        failed = subprocess.run([sys.executable, "manage.py", "publish_outbox", "--tenant", "demo"],
            cwd=ROOT, env=env, capture_output=True, timeout=20)
        assert failed.returncode != 0
        assert shell(env, "from platform_core.models import Outbox\nprint(Outbox.objects.filter(published_at=None).count())") == "1"
    finally:
        subprocess.run(["docker", "start", container], check=True, capture_output=True)
    async def read_after_restart():
        nc = await nats.connect(env["UNUM_NATS_URL"], max_reconnect_attempts=1,
            reconnect_time_wait=0, allow_reconnect=False, connect_timeout=2)
        try:
            js = nc.jetstream()
            assert (await js.stream_info("UNUM_QUALIFICATION")).state.messages == 1
            return json.loads((await js.get_msg("UNUM_QUALIFICATION", seq=1)).data)
        finally:
            await nc.drain()
    for attempt in range(20):
        try:
            recovered = asyncio.run(read_after_restart())
            break
        except (OSError, nats.errors.Error):
            time.sleep(.2)
    else:
        raise AssertionError("JetStream did not recover")
    assert recovered == event
    published = subprocess.run([sys.executable, "manage.py", "publish_outbox", "--tenant", "demo"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
    assert published.returncode == 0, published.stderr
    assert shell(env, "from platform_core.models import Outbox\nprint(Outbox.objects.filter(published_at=None).count())") == "0"
    assert asyncio.run(read_after_restart()) == event  # repeat publish was deduplicated
    consume = f'''import json
from django.db.models import F
from platform_core.events import consume
from services.inventory.models import Asset
event = json.loads({json.dumps(event)!r})
def projection(event):
    Asset.objects.filter(pk='asset-001').update(revision=F('revision')+1)
print(consume(event, projection, trusted_tenant='demo'))'''
    assert shell(env, consume) == "True"
    assert shell(env, consume) == "False"  # a new process sees the durable inbox
    assert call(cluster, "inventory", "assets/asset-001").json()["revision"] == 2
