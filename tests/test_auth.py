import json
from types import SimpleNamespace
import time

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest

from platform_core import auth


@pytest.fixture
def identity_config(monkeypatch):
    service = {"actor": "workflow", "role": "service", "tenant": "a", "sites": ["east", "west"]}
    user = {"actor": "alice", "role": "operator", "tenant": "a", "sites": ["east"]}
    config = SimpleNamespace(DEMO=True, AUTH_TOKENS={"service": service, "user": user,
        "outsider": user | {"tenant": "b"}, "western": user | {"sites": ["elsewhere"]}},
        OIDC={"issuer": "https://identity.example.test", "audience": "unum-api",
            "jwks_uri": "https://identity.example.test/keys", "scope": "unum.api",
            "role_claim": "unum_role", "tenant_claim": "unum_tenant", "sites_claim": "unum_sites",
            "mfa_acr_values": []})
    monkeypatch.setattr(auth, "settings", config)
    return config


@pytest.fixture
def signed_token(identity_config, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwt.PyJWK.from_json(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    monkeypatch.setattr(auth, "_jwks_client", lambda uri: SimpleNamespace(get_signing_key_from_jwt=lambda token: public))
    def sign(**changes):
        claims = {"iss": identity_config.OIDC["issuer"], "aud": "unum-api", "sub": "subject-17",
            "iat": int(time.time()), "exp": int(time.time()) + 300, "scope": "unum.api",
            "amr": ["pwd", "mfa"], "unum_role": "operator", "unum_tenant": "a", "unum_sites": ["east"]}
        claims.update(changes)
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "key-1"})
    return sign


def request(token="service", caller="user"):
    headers = {"Authorization": "Bearer " + token}
    if caller is not None:
        headers["X-Unum-Caller-Authorization"] = "Bearer " + caller
    return SimpleNamespace(headers=headers)


def test_delegation_intersects_verified_scope(identity_config):
    result = auth.authenticate_request(request())
    assert result == {"actor": "alice", "tenant": "a", "sites": ["east"],
        "role": "service", "caller_role": "operator"}


@pytest.mark.parametrize("token,caller", [("service", "outsider"), ("service", "western"),
    ("user", "service"), ("service", "service"), ("service", "made-up")])
def test_delegation_rejects_forged_or_expanded_scope(identity_config, token, caller):
    with pytest.raises(auth.AuthenticationError):
        auth.authenticate_request(request(token, caller))


def test_unsigned_identity_headers_do_not_affect_access(identity_config):
    r = request("user", None)
    r.headers.update({"X-Unum-Tenant": "b", "X-Unum-Role": "admin", "X-Unum-Sites": "west"})
    assert auth.authenticate_request(r)["tenant"] == "a"
    assert auth.authenticate_request(r)["role"] == "operator"


def test_production_disables_static_human_tokens(identity_config):
    identity_config.DEMO = False
    with pytest.raises(auth.AuthenticationError):
        auth.authenticate_token("Bearer user")
    assert auth.authenticate_token("Bearer service")["role"] == "service"


def test_signed_oidc_access_has_stable_principal(identity_config, signed_token):
    identity_config.DEMO = False
    first = auth.authenticate_token("Bearer " + signed_token(preferred_username="alice"))
    renamed = auth.authenticate_token("Bearer " + signed_token(preferred_username="renamed"))
    assert first == renamed
    assert first["actor"].startswith("oidc:")
    assert first["tenant"] == "a" and first["sites"] == ["east"]


@pytest.mark.parametrize("changes", [
    {"iss": "https://wrong.example.test"}, {"aud": "other-api"},
    {"exp": 1}, {"iat": int(time.time()) + 600}, {"exp": None},
    {"scope": "different"}, {"amr": ["pwd"]}, {"unum_role": "service"},
    {"unum_role": ["admin"]}, {"unum_role": {"role": "admin"}},
    {"unum_tenant": ""}, {"unum_sites": "east"}, {"unum_sites": ["east,west"]},
    {"sub": ""},
])
def test_invalid_oidc_claims_fail_closed(identity_config, signed_token, changes):
    with pytest.raises(auth.AuthenticationError):
        auth.authenticate_token("Bearer " + signed_token(**changes))


def test_bad_signature_and_algorithm_are_rejected(identity_config, signed_token):
    token = signed_token()
    parts = token.split(".")
    parts[1] = jwt.utils.base64url_encode(json.dumps({"sub": "forged"}).encode()).decode()
    with pytest.raises(auth.AuthenticationError):
        auth.authenticate_token("Bearer " + ".".join(parts))
    with pytest.raises(auth.AuthenticationError):
        auth.authenticate_token("Bearer " + jwt.encode({"sub": "forged"}, "a" * 32, algorithm="HS256"))


def test_jwks_outage_does_not_accept_unverified_tokens(identity_config, signed_token, monkeypatch):
    def fail(token):
        raise jwt.PyJWKClientConnectionError("offline")
    monkeypatch.setattr(auth, "_jwks_client", lambda uri: SimpleNamespace(get_signing_key_from_jwt=fail))
    with pytest.raises(auth.AuthenticationError) as exc:
        auth.authenticate_token("Bearer " + signed_token())
    assert exc.value.status == 503


def test_oidc_caller_delegation_preserves_human_principal(identity_config, signed_token):
    identity_config.DEMO = False
    token = signed_token()
    result = auth.authenticate_request(request("service", token))
    assert result["actor"] == auth.authenticate_token("Bearer " + token)["actor"]
    assert result["sites"] == ["east"]


def test_configured_mfa_acr_is_accepted(identity_config, signed_token):
    identity_config.OIDC["mfa_acr_values"] = ["urn:example:mfa"]
    assert auth.authenticate_token("Bearer " + signed_token(amr=[], acr="urn:example:mfa"))["role"] == "operator"
