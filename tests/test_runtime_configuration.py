import subprocess
import sys

import pytest
from platform_core.auth import oidc_configuration_valid
from scripts.dev_config import ROOT, environment


def configuration():
    return {"issuer": "https://identity.example.test", "audience": "unum-api",
            "jwks_uri": "https://identity.example.test/keys", "scope": "unum.api",
            "role_claim": "unum_role", "tenant_claim": "unum_tenant", "sites_claim": "unum_sites",
            "mfa_acr_values": []}


def test_valid_oidc_configuration_needs_no_live_identity_provider():
    assert oidc_configuration_valid(configuration())


@pytest.mark.parametrize("change", [
    {"issuer": ""}, {"audience": " "}, {"jwks_uri": "http://identity.example.test/keys"},
    {"jwks_uri": "https://user:password@identity.example.test/keys"},
    {"issuer": "https://[invalid"}, {"tenant_claim": None}, {"sites_claim": ""},
    {"scope": ""}, {"mfa_acr_values": "mfa"}, {"mfa_acr_values": [None]},
])
def test_invalid_oidc_configuration_fails_readiness_validation(change):
    assert not oidc_configuration_valid(configuration() | change)


def test_readiness_rejects_unsafe_runtime_and_missing_identity_configuration(tmp_path):
    script = '''
import json
from unittest.mock import patch
from django.db import DatabaseError
from django.test import override_settings
from platform_core.api import ready

with override_settings(DEMO=False, OIDC={}):
    with patch("platform_core.tenancy.validate_runtime_database") as check:
        response = ready(None)
        assert response.status_code == 503
        assert json.loads(response.content)["status"] == "identity_configuration_invalid"
        check.assert_not_called()
with override_settings(DEMO=True):
    for failure, status in ((RuntimeError("unsafe role"), "database_policy_invalid"),
                            (DatabaseError("connection failed"), "database_unavailable")):
        with patch("platform_core.tenancy.validate_runtime_database", side_effect=failure):
            response = ready(None)
            assert response.status_code == 503
            assert json.loads(response.content)["status"] == status
    with patch("platform_core.tenancy.validate_runtime_database") as check:
        assert ready(None).status_code == 200
        check.assert_called_once_with(refresh=True)
'''
    env = {key: value for key, value in environment("inventory", tmp_path).items() if not key.startswith("PG")}
    result = subprocess.run([sys.executable, "manage.py", "shell", "-c", script],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
