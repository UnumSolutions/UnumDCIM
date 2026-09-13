"""Explicitly insecure synthetic identities for loopback-only development."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ["inventory", "placement", "workflow", "synchronization", "registry"]
TOKENS = {
    "demo-ashburn-token": {"actor": "site-operator", "role": "operator", "tenant": "demo", "sites": ["ashburn"]},
    "demo-operator-token": {"actor": "alex", "role": "operator", "tenant": "demo", "sites": ["ashburn", "dallas"]},
    "demo-approver-token": {"actor": "jordan", "role": "approver", "tenant": "demo", "sites": ["ashburn", "dallas"]},
    "demo-admin-token": {"actor": "admin", "role": "admin", "tenant": "demo", "sites": ["ashburn", "dallas"]},
    "demo-service-token": {"actor": "workflow-service", "role": "service", "tenant": "demo", "sites": ["ashburn", "dallas"]},
    "demo-other-tenant": {"actor": "outsider", "role": "admin", "tenant": "other", "sites": ["ashburn", "dallas"]},
}


def environment(service, data_dir=None, base_port=8101):
    # The local demo must never inherit credentials for a real PostgreSQL DB.
    local = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    return local | {"UNUM_SERVICE": service, "UNUM_DEMO": "1", "UNUM_SECRET_KEY": "development-only",
        "UNUM_AUTH_TOKENS": json.dumps(TOKENS), "UNUM_SERVICE_TOKEN": "demo-service-token",
        "UNUM_DATA_DIR": str(data_dir or ROOT / ".data"),
        "UNUM_SERVICE_URLS": json.dumps({s: f"http://127.0.0.1:{base_port+i}" for i, s in enumerate(SERVICES)})}
