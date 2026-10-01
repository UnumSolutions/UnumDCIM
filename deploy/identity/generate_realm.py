#!/usr/bin/env python3
"""Generate a fail-closed Keycloak realm; never reads or embeds Google secrets."""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


KEYCLOAK_VERSION = "26.7.5"
KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.7.5@sha256:37dbaf6f0722c9ec246335f36e1ef8b2e6cb960f7c27e0d8c615121a3d475a85"
CLIENT_ID = "unum-web"
API_AUDIENCE = "unum-api"
API_SCOPE = "unum.api"
MFA_ACR = "urn:unum:acr:staff-mfa"
GOOGLE_SECRET_ENV = "UNUM_GOOGLE_CLIENT_SECRET"


def _https_url(value, *, origin=False):
    if not isinstance(value, str) or any(ord(c) < 33 or c in "*\\${}" for c in value):
        raise ValueError("URLs must be exact HTTPS URLs")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or origin and parsed.path not in ("", "/")):
        raise ValueError("URLs must be exact HTTPS URLs without query, fragment or credentials")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid HTTPS port")
    return f"https://{parsed.netloc}"


def validate_config(config):
    required = {"realm", "browser_origin", "redirect_uri", "post_logout_redirect_uri",
                "google_client_id", "google_hosted_domains"}
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError("Configuration must contain exactly the documented fields")
    if not isinstance(config["realm"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", config["realm"]):
        raise ValueError("Invalid realm name")
    origin = _https_url(config["browser_origin"], origin=True)
    if any(_https_url(config[key]) != origin for key in ("redirect_uri", "post_logout_redirect_uri")):
        raise ValueError("Callback and logout redirect must belong to browser_origin")
    if (not isinstance(config["google_client_id"], str) or not re.fullmatch(
            r"[A-Za-z0-9_-]+\.apps\.googleusercontent\.com", config["google_client_id"])):
        raise ValueError("A Google web OAuth client ID is required")
    domains = config["google_hosted_domains"]
    if (not isinstance(domains, list) or not 1 <= len(domains) <= 20
            or not all(isinstance(domain, str) for domain in domains) or len(set(domains)) != len(domains)
            or any(not isinstance(domain, str) or len(domain) > 253 or not re.fullmatch(
                r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain) for domain in domains)):
        raise ValueError("Explicit lowercase Google hosted domains are required; wildcards are forbidden")


def _execution(authenticator=None, *, flow=None, config=None, requirement="REQUIRED", priority=10):
    result = {"requirement": requirement, "priority": priority, "userSetupAllowed": False,
              "authenticatorFlow": flow is not None}
    result["flowAlias" if flow else "authenticator"] = flow or authenticator
    if config:
        result["authenticatorConfig"] = config
    return result


def _flow(alias, executions, *, top=True):
    return {"alias": alias, "providerId": "basic-flow", "topLevel": top, "builtIn": False,
            "authenticationExecutions": executions}


def _mapper(name, provider, config):
    return {"name": name, "protocol": "openid-connect", "protocolMapper": provider,
            "consentRequired": False, "config": config}


def build_realm(config):
    validate_config(config)
    profile_attributes = [
        {"name": name, "permissions": {"view": ["admin", "user"], "edit": ["admin", "user"]}}
        for name in ("username", "email", "firstName", "lastName")
    ]
    for name in ("unum_role", "unum_tenant", "unum_sites"):
        profile_attributes.append({"name": name, "multivalued": name == "unum_sites",
            "permissions": {"view": ["admin"], "edit": ["admin"]}})
    # An omitted unmanagedAttributePolicy means disabled in Keycloak; DISABLED
    # is a UI label, not a supported serialized enum value.
    profile = {"attributes": profile_attributes}
    basic_scopes = []
    for scope, fields in (("profile", (("username", "preferred_username", "String"),
                                        ("firstName", "given_name", "String"), ("lastName", "family_name", "String"))),
                          ("email", (("email", "email", "String"), ("emailVerified", "email_verified", "boolean")))):
        basic_scopes.append({"name": scope, "protocol": "openid-connect",
            "attributes": {"include.in.token.scope": "true"},
            "protocolMappers": [_mapper(claim, "oidc-usermodel-property-mapper", {
                "user.attribute": attribute, "claim.name": claim, "jsonType.label": kind,
                "access.token.claim": "false", "id.token.claim": "true", "userinfo.token.claim": "true",
            }) for attribute, claim, kind in fields]})
    grants = [_mapper(name, "oidc-usermodel-attribute-mapper", {
        "user.attribute": name, "claim.name": name, "jsonType.label": "String",
        "multivalued": str(name == "unum_sites").lower(),
        "access.token.claim": "true", "id.token.claim": "false", "userinfo.token.claim": "false",
    }) for name in ("unum_role", "unum_tenant", "unum_sites")]
    return {
        "realm": config["realm"], "enabled": True, "sslRequired": "all",
        "registrationAllowed": False, "resetPasswordAllowed": False,
        "editUsernameAllowed": False, "duplicateEmailsAllowed": False,
        "loginWithEmailAllowed": False, "bruteForceProtected": True,
        "defaultSignatureAlgorithm": "RS256", "accessTokenLifespan": 300,
        "ssoSessionIdleTimeout": 1800, "ssoSessionMaxLifespan": 28800,
        "revokeRefreshToken": True, "refreshTokenMaxReuse": 0,
        "otpPolicyType": "totp", "otpPolicyAlgorithm": "HmacSHA1", "otpPolicyDigits": 6,
        "otpPolicyPeriod": 30, "otpPolicyLookAheadWindow": 1,
        "browserFlow": "unum-google-browser",
        "attributes": {"acr.loa.map": json.dumps({MFA_ACR: 2})},
        "components": {"org.keycloak.userprofile.UserProfileProvider": [{
            "providerId": "declarative-user-profile", "config": {"kc.user.profile.config": [json.dumps(profile)]},
        }]},
        "identityProviders": [{"alias": "google", "providerId": "google", "enabled": True,
            "trustEmail": False, "storeToken": False, "linkOnly": False,
            "firstBrokerLoginFlowAlias": "unum-first-google",
            "postBrokerLoginFlowAlias": "unum-post-google",
            "config": {"clientId": config["google_client_id"],
                "clientSecret": "${" + GOOGLE_SECRET_ENV + "}",
                "hostedDomain": ",".join(config["google_hosted_domains"]),
                "defaultScope": "openid profile email", "useJwksUrl": "true",
                "syncMode": "IMPORT", "offlineAccess": "false"}}],
        "authenticatorConfig": [
            {"alias": "unum-google-redirect", "config": {"defaultProvider": "google"}},
            {"alias": "unum-staff-loa", "config": {"loa-condition-level": "2", "loa-max-age": "0"}},
        ],
        "authenticationFlows": [
            _flow("unum-google-browser", [_execution("identity-provider-redirector", config="unum-google-redirect")]),
            _flow("unum-first-google", [_execution("idp-create-user-if-unique")]),
            _flow("unum-post-google", [_execution(flow="unum-staff-step-up", requirement="CONDITIONAL")]),
            _flow("unum-staff-step-up", [
                _execution("conditional-level-of-authentication", config="unum-staff-loa"),
                _execution("auth-otp-form", priority=20),
            ], top=False),
        ],
        "clientScopes": basic_scopes + [{"name": API_SCOPE, "protocol": "openid-connect",
            "attributes": {"include.in.token.scope": "true", "display.on.consent.screen": "false"},
            "protocolMappers": grants + [
                _mapper("stable subject", "oidc-sub-mapper", {"access.token.claim": "true"}),
                _mapper("authentication time", "oidc-usersessionmodel-note-mapper", {
                    "user.session.note": "AUTH_TIME", "claim.name": "auth_time", "jsonType.label": "long",
                    "access.token.claim": "true", "id.token.claim": "true"}),
                _mapper("unum-api audience", "oidc-audience-mapper", {
                    "included.client.audience": API_AUDIENCE,
                    "access.token.claim": "true", "id.token.claim": "false"}),
                _mapper("achieved assurance", "oidc-acr-mapper", {
                    "access.token.claim": "true", "id.token.claim": "true"}),
            ]}],
        "clients": [
            {"clientId": API_AUDIENCE, "enabled": True, "protocol": "openid-connect",
             "bearerOnly": True, "standardFlowEnabled": False, "implicitFlowEnabled": False,
             "directAccessGrantsEnabled": False, "serviceAccountsEnabled": False},
            {"clientId": CLIENT_ID, "enabled": True, "protocol": "openid-connect", "publicClient": True,
             "standardFlowEnabled": True, "implicitFlowEnabled": False,
             "directAccessGrantsEnabled": False, "serviceAccountsEnabled": False,
             "fullScopeAllowed": False, "redirectUris": [config["redirect_uri"]],
             "webOrigins": [_https_url(config["browser_origin"], origin=True)],
             "defaultClientScopes": ["profile", "email", API_SCOPE], "optionalClientScopes": [],
             "attributes": {"pkce.code.challenge.method": "S256", "minimum.acr.value": MFA_ACR,
                 "default.acr.values": MFA_ACR, "access.token.signed.response.alg": "RS256",
                 "post.logout.redirect.uris": config["post_logout_redirect_uri"],
                 "oauth2.device.authorization.grant.enabled": "false", "oidc.ciba.grant.enabled": "false",
                 "standard.token.exchange.enabled": "false", "oauth2.jwt.authorization.grant.enabled": "false"}},
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New private realm JSON; existing files are never overwritten")
    args = parser.parse_args()
    try:
        result = build_realm(json.loads(args.config.read_text()))
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(result, handle, indent=2)
            handle.write("\n")
    except (ValueError, TypeError, OSError) as exc:
        parser.exit(2, f"Cannot generate realm: {type(exc).__name__}\n")


if __name__ == "__main__":
    main()
