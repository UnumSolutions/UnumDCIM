#!/usr/bin/env python3
"""Qualify the broker using disposable Keycloak + synthetic upstream, never Google."""
import base64
import hashlib
import hmac
from html.parser import HTMLParser
import json
import secrets
import subprocess
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import jwt

from generate_realm import API_AUDIENCE, API_SCOPE, CLIENT_ID, KEYCLOAK_IMAGE, KEYCLOAK_VERSION, MFA_ACR, build_realm


class QualificationFailure(Exception):
    pass


def check(condition, code):
    if not condition:
        raise QualificationFailure(code)


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=180)
    check(result.returncode == 0, "docker_" + args[0] + "_failed")
    return result.stdout.strip()


class Forms(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.forms, self.current = [], None
        self.feed(text)

    def handle_starttag(self, tag, attributes):
        data = dict(attributes)
        if tag == "form":
            self.current = {"action": data.get("action"), "inputs": {}}
            self.forms.append(self.current)
        if tag == "input" and self.current is not None and "name" in data:
            if data.get("type") == "checkbox" and "checked" not in data:
                return
            self.current["inputs"][data["name"]] = data.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


class BrowserProtocol:
    """Synthetic HTTP harness, not a browser/TLS acceptance test.

    Keycloak uses Secure cookies even in start-dev. This local HTTP harness
    carries them only to its exact disposable origin; production keeps HTTPS.
    """
    callback = "http://127.0.0.1:9999/callback"

    def __init__(self, base):
        self.base = base
        self.client = httpx.Client(timeout=10, follow_redirects=False, trust_env=False)

    def close(self):
        self.client.close()

    def request(self, method, url, **kwargs):
        check(url.startswith(self.base + "/"), "nonlocal_test_request_rejected")
        for _ in range(20):
            for cookie in self.client.cookies.jar:
                cookie.secure = False
            response = self.client.request(method, url, **kwargs)
            if response.status_code not in (302, 303):
                return response
            url = response.headers["Location"]
            if urlsplit(url)._replace(query="").geturl() == self.callback:
                return response
            check(url.startswith(self.base + "/"), "nonlocal_test_redirect_rejected")
            method, kwargs = "GET", {}
        raise QualificationFailure("redirect_limit")

    def begin(self, realm, *, overrides=None):
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        params = {"client_id": CLIENT_ID, "redirect_uri": self.callback, "response_type": "code",
                  "scope": "openid profile email " + API_SCOPE, "state": secrets.token_urlsafe(16),
                  "nonce": secrets.token_urlsafe(16), "code_challenge": challenge,
                  "code_challenge_method": "S256", "acr_values": MFA_ACR}
        params.update(overrides or {})
        return self.request("GET", f"{self.base}/realms/{realm}/protocol/openid-connect/auth", params=params), verifier

    def submit(self, response, values):
        forms = Forms(response.text).forms
        check(bool(forms), "expected_login_form_missing")
        form = forms[0]
        return self.request("POST", form["action"], data=form["inputs"] | values)


def totp(secret, offset=0):
    message = (int(time.time() // 30) + offset).to_bytes(8, "big")
    value = hmac.new(secret.encode(), message, hashlib.sha1).digest()
    position = value[-1] & 15
    return str((int.from_bytes(value[position:position + 4], "big") & 0x7fffffff) % 1_000_000).zfill(6)


def callback(response):
    check(response.status_code in (302, 303), "authorization_did_not_finish")
    return parse_qs(urlsplit(response.headers["Location"]).query)


def qualify(base, admin_password, passed):
    with httpx.Client(base_url=base, timeout=20, trust_env=False) as admin:
        auth = admin.post("/realms/master/protocol/openid-connect/token", data={"grant_type": "password",
            "client_id": "admin-cli", "username": "qualification", "password": admin_password})
        check(auth.status_code == 200, "admin_login_failed")
        admin.headers["Authorization"] = "Bearer " + auth.json()["access_token"]
        config = {"realm": "qualification", "browser_origin": "https://app.example.invalid",
            "redirect_uri": "https://app.example.invalid/", "post_logout_redirect_uri": "https://app.example.invalid/",
            "google_client_id": "123-synthetic.apps.googleusercontent.com", "google_hosted_domains": ["example.invalid"]}
        realm = build_realm(config)
        # Test-only transport overrides; the production generator requires HTTPS.
        realm["sslRequired"] = "none"
        web = next(c for c in realm["clients"] if c["clientId"] == CLIENT_ID)
        web["redirectUris"] = [BrowserProtocol.callback]
        web["webOrigins"] = ["http://127.0.0.1:9999"]
        prefix = "/admin/realms/qualification"
        check(admin.post("/admin/realms", json=realm).status_code == 201, "realm_import_failed")
        provider = admin.get(prefix + "/identity-provider/instances/google").json()
        check(provider["providerId"] == "google" and provider["config"]["hostedDomain"] == "example.invalid",
              "google_provider_configuration_missing")
        profile = admin.get(prefix + "/users/profile").json()
        check(profile.get("unmanagedAttributePolicy") is None, "unmanaged_attributes_enabled")
        protected = {a["name"]: a for a in profile["attributes"] if a["name"].startswith("unum_")}
        check(set(protected) == {"unum_role", "unum_tenant", "unum_sites"}, "protected_grants_missing")
        check(all(a["permissions"]["edit"] == ["admin"] for a in protected.values()), "grants_user_editable")
        passed.append("realm_import_and_effective_protected_attributes")

        # Replace, rather than update, providerId (which Keycloak keeps immutable).
        # Google hostnames resolve to loopback inside the test container, and the
        # HTTP harness refuses every nonlocal request/redirect.
        upstream_password = secrets.token_urlsafe(32)
        upstream_secret = secrets.token_urlsafe(32)
        upstream = {"realm": "upstream", "enabled": True, "sslRequired": "none", "attributes": {"frontendUrl": base},
            "clients": [{"clientId": "broker", "secret": upstream_secret, "enabled": True,
                "standardFlowEnabled": True, "redirectUris": [base + "/realms/qualification/broker/google/endpoint"]}],
            "users": [{"username": "staff", "enabled": True, "email": "staff@example.invalid", "emailVerified": True,
                "firstName": "Synthetic", "lastName": "Staff",
                "credentials": [{"type": "password", "value": upstream_password, "temporary": False}]}]}
        check(admin.post("/admin/realms", json=upstream).status_code == 201, "upstream_import_failed")
        check(admin.delete(prefix + "/identity-provider/instances/google").status_code == 204, "provider_replace_failed")
        provider.pop("internalId", None)
        provider["providerId"] = "oidc"
        inside = "http://127.0.0.1:8080/realms/upstream/protocol/openid-connect/"
        provider["config"] = {"clientId": "broker", "clientSecret": upstream_secret,
            "authorizationUrl": base + "/realms/upstream/protocol/openid-connect/auth",
            "tokenUrl": inside + "token", "jwksUrl": inside + "certs", "issuer": base + "/realms/upstream",
            "useJwksUrl": "true", "validateSignature": "true", "defaultScope": "openid profile email", "syncMode": "IMPORT"}
        check(admin.post(prefix + "/identity-provider/instances", json=provider).status_code == 201, "synthetic_provider_failed")
        browser = BrowserProtocol(base)
        try:
            response, _ = browser.begin("qualification", overrides={"code_challenge": None, "code_challenge_method": None})
            check("code" not in callback(response), "missing_pkce_accepted")
            passed.append("missing_pkce_rejected")
            response, verifier = browser.begin("qualification")
            check("password" in Forms(response.text).forms[0]["inputs"], "upstream_login_not_requested")
            response = browser.submit(response, {"username": "staff", "password": upstream_password})
            forms = Forms(response.text).forms
            check(bool(forms) and "totpSecret" in forms[0]["inputs"], "broker_skipped_mfa_enrollment")
            response = browser.submit(response, {"totp": "invalid", "userLabel": "Synthetic"})
            check(response.status_code == 200 and "totpSecret" in Forms(response.text).forms[0]["inputs"], "invalid_otp_accepted")
            secret = Forms(response.text).forms[0]["inputs"]["totpSecret"]
            response = browser.submit(response, {"totp": totp(secret), "userLabel": "Synthetic"})
            code = callback(response).get("code", [None])[0]
            check(code is not None, "otp_enrollment_did_not_authorize")
            endpoint = base + "/realms/qualification/protocol/openid-connect/token"
            tokens = browser.client.post(endpoint, data={"grant_type": "authorization_code", "client_id": CLIENT_ID,
                "redirect_uri": BrowserProtocol.callback, "code": code, "code_verifier": verifier})
            check(tokens.status_code == 200, "pkce_exchange_failed")
            tokens = tokens.json()
            jwks = jwt.PyJWKClient(base + "/realms/qualification/protocol/openid-connect/certs")

            def claims(token):
                return jwt.decode(token, jwks.get_signing_key_from_jwt(token).key, algorithms=["RS256"],
                    audience=API_AUDIENCE, issuer=base + "/realms/qualification",
                    options={"require": ["iss", "aud", "sub", "exp", "iat"]})

            issued = claims(tokens["access_token"])
            check(issued["acr"] == MFA_ACR and API_SCOPE in issued["scope"].split(), "assurance_or_scope_missing")
            check(not any(name in issued for name in protected), "unapproved_user_has_api_grants")
            passed.append("mandatory_otp_and_signed_access_token_without_implicit_grants")
            users = admin.get(prefix + "/users", params={"username": "staff", "exact": "true"}).json()
            check(len(users) == 1, "broker_subject_not_unique")
            user = users[0]
            user["attributes"] = {"unum_role": ["operator"], "unum_tenant": ["synthetic-tenant"], "unum_sites": ["site-a", "site-b"]}
            check(admin.put(prefix + "/users/" + user["id"], json=user).status_code == 204, "admin_grant_update_failed")
            refreshed = browser.client.post(endpoint, data={"grant_type": "refresh_token", "client_id": CLIENT_ID,
                                                          "refresh_token": tokens["refresh_token"]})
            check(refreshed.status_code == 200, "session_refresh_failed")
            issued = claims(refreshed.json()["access_token"])
            check(issued["unum_role"] == "operator" and issued["unum_tenant"] == "synthetic-tenant"
                and sorted(issued["unum_sites"]) == ["site-a", "site-b"] and issued["acr"] == MFA_ACR,
                "issued_grants_do_not_match_admin_assignment")
            attempt = browser.client.post(base + "/realms/qualification/account/",
                headers={"Authorization": "Bearer " + refreshed.json()["access_token"]},
                json={"attributes": {"unum_role": ["admin"], "unum_tenant": ["foreign"]}})
            stored = admin.get(prefix + "/users/" + user["id"]).json()["attributes"]
            check(attempt.status_code >= 400 and stored == user["attributes"], "application_token_escalated_grants")
            passed.append("admin_grant_shapes_and_self_service_escalation_denied")
            response, verifier = browser.begin("qualification", overrides={"acr_values": "1"})
            if response.status_code == 200 and Forms(response.text).forms and "password" in Forms(response.text).forms[0]["inputs"]:
                response = browser.submit(response, {"username": "staff", "password": upstream_password})
            # Minimum ACR can reject a lower request before login rather than
            # upgrading it; either outcome must never return an authorization code.
            forms = Forms(response.text).forms if response.status_code == 200 else []
            if not forms or "otp" not in forms[0]["inputs"]:
                rejected = response.status_code >= 400
                if response.status_code in (302, 303):
                    parameters = callback(response)
                    rejected = "error" in parameters and "code" not in parameters
                check(rejected, "acr_downgrade_not_rejected_or_challenged")
                passed.append("acr_downgrade_rejected")
                response, verifier = browser.begin("qualification")
                if response.status_code == 200 and Forms(response.text).forms and "password" in Forms(response.text).forms[0]["inputs"]:
                    response = browser.submit(response, {"username": "staff", "password": upstream_password})
            check(response.status_code == 200 and "otp" in Forms(response.text).forms[0]["inputs"],
                  "sso_or_acr_downgrade_bypassed_step_up")
            response = browser.submit(response, {"otp": totp(secret, 1)})
            code = callback(response).get("code", [None])[0]
            check(code is not None, "repeat_step_up_failed")
            wrong = browser.client.post(endpoint, data={"grant_type": "authorization_code", "client_id": CLIENT_ID,
                "redirect_uri": BrowserProtocol.callback, "code": code, "code_verifier": "incorrect" * 8})
            check(wrong.status_code == 400, "wrong_pkce_verifier_accepted")
            passed.append("sso_reentry_and_acr_downgrade_require_fresh_otp")
            passed.append("wrong_pkce_verifier_rejected")
            password_grant = browser.client.post(endpoint, data={"grant_type": "password", "client_id": CLIENT_ID,
                "username": "staff", "password": upstream_password})
            check(password_grant.status_code == 400, "password_grant_enabled")
            passed.append("direct_password_grant_disabled")
        finally:
            browser.close()
    return passed


def main():
    suffix = uuid4().hex[:10]
    container, network = "unum-identity-" + suffix, "unum-identity-net-" + suffix
    report = {"keycloak_version": KEYCLOAK_VERSION, "image": KEYCLOAK_IMAGE,
              "google_login_verified": False, "real_browser_tls_verified": False, "passed": [], "complete": False}
    try:
        docker("network", "create", network)
        password = secrets.token_urlsafe(32)
        docker("run", "-d", "--name", container, "--network", network, "-p", "127.0.0.1::8080",
            "--add-host", "accounts.google.com:127.0.0.1", "--add-host", "oauth2.googleapis.com:127.0.0.1",
            "--add-host", "www.googleapis.com:127.0.0.1", "--add-host", "openidconnect.googleapis.com:127.0.0.1",
            "-e", "KC_BOOTSTRAP_ADMIN_USERNAME=qualification", "-e", "KC_BOOTSTRAP_ADMIN_PASSWORD=" + password,
            KEYCLOAK_IMAGE, "start-dev")
        binding = docker("port", container, "8080").splitlines()[0]
        check(binding.startswith("127.0.0.1:"), "nonlocal_container_port")
        base = "http://" + binding
        deadline = time.monotonic() + 90
        while True:
            try:
                if httpx.get(base + "/realms/master/.well-known/openid-configuration", timeout=2, trust_env=False).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            check(time.monotonic() < deadline, "keycloak_startup_timeout")
            time.sleep(.5)
        qualify(base, password, report["passed"])
        report["complete"] = True
    except (QualificationFailure, httpx.HTTPError, jwt.PyJWTError, KeyError, IndexError, ValueError, subprocess.SubprocessError) as exc:
        report["error"] = str(exc) if isinstance(exc, QualificationFailure) else type(exc).__name__
    finally:
        for command in (("rm", "-f", "-v", container), ("network", "rm", network)):
            result = subprocess.run(["docker", *command], capture_output=True, text=True, timeout=30)
            if result.returncode != 0 and "No such" not in result.stderr:
                report["complete"] = False
                report["cleanup_failed"] = True
    print(json.dumps(report, indent=2))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
