"""Run with pytest deploy/identity/test_realm.py; no Docker or credentials."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_realm import API_SCOPE, MFA_ACR, build_realm


def configuration():
    return json.loads(Path(__file__).with_name("workspace.example.json").read_text())


@pytest.mark.parametrize("key,value", [
    ("browser_origin", "http://dcim.example.invalid"),
    ("redirect_uri", "https://attacker.invalid/"),
    ("redirect_uri", "https://dcim.example.invalid/*"),
    ("redirect_uri", "https://dcim.example.invalid/#callback"),
    ("redirect_uri", "https://user:secret@dcim.example.invalid/"),
    ("redirect_uri", "https://dcim.example.invalid/${UNUM_GOOGLE_CLIENT_SECRET}"),
    ("post_logout_redirect_uri", "https://attacker.invalid/"),
    ("google_hosted_domains", ["*"]),
    ("google_hosted_domains", []),
    ("google_hosted_domains", [{}]),
    ("google_hosted_domains", ["example.invalid,attacker.invalid"]),
    ("google_hosted_domains", ["example.invalid", "example.invalid"]),
    ("google_client_id", "not-an-oauth-client"),
    ("realm", "master/../operations"),
])
def test_unsafe_configuration_is_rejected(key, value):
    with pytest.raises(ValueError):
        build_realm(configuration() | {key: value})


def test_broker_cannot_issue_api_tokens_without_required_local_step_up():
    realm = build_realm(configuration())
    flows = {flow["alias"]: flow for flow in realm["authenticationFlows"]}
    browser = flows[realm["browserFlow"]]["authenticationExecutions"]
    assert [step["authenticator"] for step in browser] == ["identity-provider-redirector"]
    idp = realm["identityProviders"][0]
    post = flows[idp["postBrokerLoginFlowAlias"]]["authenticationExecutions"]
    step_up = flows[post[0]["flowAlias"]]["authenticationExecutions"]
    assert [(step["authenticator"], step["requirement"]) for step in step_up] == [
        ("conditional-level-of-authentication", "REQUIRED"), ("auth-otp-form", "REQUIRED")]
    configs = {item["alias"]: item["config"] for item in realm["authenticatorConfig"]}
    assert configs[step_up[0]["authenticatorConfig"]] == {"loa-condition-level": "2", "loa-max-age": "0"}
    client = next(c for c in realm["clients"] if c["clientId"] == "unum-web")
    assert client["attributes"]["minimum.acr.value"] == MFA_ACR
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"
    assert not client["directAccessGrantsEnabled"] and not client["implicitFlowEnabled"]
    assert not client["serviceAccountsEnabled"]
    assert API_SCOPE in client["defaultClientScopes"]


def test_grants_are_admin_only_and_assurance_comes_from_achieved_loa():
    realm = build_realm(configuration())
    component = realm["components"]["org.keycloak.userprofile.UserProfileProvider"][0]
    profile = json.loads(component["config"]["kc.user.profile.config"][0])
    assert profile.get("unmanagedAttributePolicy") is None
    grants = [a for a in profile["attributes"] if a["name"].startswith("unum_")]
    assert len(grants) == 3
    assert all(a["permissions"] == {"view": ["admin"], "edit": ["admin"]} for a in grants)
    mappers = next(s for s in realm["clientScopes"] if s["name"] == API_SCOPE)["protocolMappers"]
    assert next(m for m in mappers if m["name"] == "achieved assurance")["protocolMapper"] == "oidc-acr-mapper"
    assert next(m for m in mappers if m["name"] == "stable subject")["protocolMapper"] == "oidc-sub-mapper"
    assert not any("hardcoded" in m["protocolMapper"] for m in mappers)
    assert "users" not in realm
    assert realm["identityProviders"][0]["config"]["clientSecret"] == "${UNUM_GOOGLE_CLIENT_SECRET}"
    assert realm["identityProviders"][0]["storeToken"] is False


def test_generator_refuses_secret_fields_and_existing_outputs(tmp_path):
    with pytest.raises(ValueError):
        build_realm(configuration() | {"google_client_secret": "do-not-embed"})
    target = tmp_path / "realm.json"
    script = Path(__file__).with_name("generate_realm.py")
    args = [sys.executable, str(script), "--config", str(script.with_name("workspace.example.json")), "--output", str(target)]
    first = subprocess.run(args, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    original = target.read_bytes()
    assert target.stat().st_mode & 0o777 == 0o600
    second = subprocess.run(args, capture_output=True, text=True)
    assert second.returncode == 2
    assert target.read_bytes() == original
