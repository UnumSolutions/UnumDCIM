import json
from pathlib import Path

import pytest

from deploy.web.render import render


def configuration():
    return json.loads((Path(__file__).resolve().parents[1] / "deploy/web/runtime.example.json").read_text())


def test_public_configuration_excludes_private_upstreams_and_credentials():
    config, public = render(configuration())
    assert public == configuration()["auth"]
    assert "internal.example.invalid" not in json.dumps(public)
    assert "proxy_set_header Authorization $http_authorization" in config
    assert 'proxy_set_header X-Unum-Caller-Authorization "";' in config
    assert 'proxy_set_header X-Demo-Role "";' in config
    assert "proxy_ssl_verify on" in config
    assert "proxy_next_upstream off" in config
    assert "$request_uri" not in config  # OAuth callback query strings must not reach access logs.


@pytest.mark.parametrize("field,value", [
    ("mode", "demo"), ("issuer", "http://identity.example.invalid/realms/unum"),
    ("issuer", "https://user:password@identity.example.invalid"),
    ("issuer", "https://identity.example.invalid/;injection"),
    ("issuer", "https://identity.example.invalid/$variable"),
    ("redirect_uri", "https://other.example.invalid/auth/callback"),
    ("redirect_uri", "https://dcim.example.invalid/callback?code=secret"),
    ("client_id", "other-client"), ("scope", "openid profile email"), ("acr_values", "0"), ("google_provider", "password"),
])
def test_unsafe_or_incompatible_auth_configuration_is_rejected(field, value):
    data = configuration()
    data["auth"][field] = value
    with pytest.raises(ValueError):
        render(data)


@pytest.mark.parametrize("url", ["http://inventory.internal.invalid", "https://inventory.invalid/path",
                                "https://user:secret@inventory.invalid", "https://inventory.invalid;rewrite"])
def test_upstream_routes_require_explicit_https_origins(url):
    data = configuration()
    data["services"]["inventory"] = url
    with pytest.raises(ValueError):
        render(data)


def test_missing_configuration_never_falls_back_to_demo():
    data = configuration()
    for incomplete in ({}, {"auth": data["auth"]}, {"services": data["services"]}):
        with pytest.raises(ValueError):
            render(incomplete)
    data["services"].pop("inventory")
    with pytest.raises(ValueError):
        render(data)
