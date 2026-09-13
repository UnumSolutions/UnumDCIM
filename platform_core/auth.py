"""Validate API credentials and authenticated service delegation.

Only configured service credentials may carry another caller's bearer token.
Claims always come from a verified credential, never tenant/role headers.
"""
from functools import lru_cache
import hashlib
import re
import secrets
from urllib.parse import urlsplit

from django.conf import settings
import jwt


SCOPE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z")
HUMAN_ROLES = {"viewer", "operator", "approver", "admin"}


def oidc_configuration_valid(config):
    """Validate required server settings without fetching keys or contacting the IdP."""
    fields = ("issuer", "audience", "jwks_uri", "scope", "role_claim", "tenant_claim", "sites_claim")
    if not isinstance(config, dict) or not all(
            isinstance(config.get(key), str) and config[key].strip() for key in fields):
        return False
    for field in ("issuer", "jwks_uri"):
        try:
            parsed = urlsplit(config[field])
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.fragment or any(char.isspace() for char in config[field])):
                return False
        except ValueError:
            return False
    acr_values = config.get("mfa_acr_values")
    return isinstance(acr_values, list) and all(isinstance(value, str) and value.strip() for value in acr_values)


class AuthenticationError(Exception):
    def __init__(self, message, status=401):
        self.message, self.status = message, status


def _deny(message="Authentication required", status=401):
    raise AuthenticationError(message, status)


def _identity(value, *, service_allowed=False):
    if not isinstance(value, dict):
        _deny()
    actor, tenant, role, sites = (value.get(k) for k in ("actor", "tenant", "role", "sites"))
    allowed = HUMAN_ROLES | ({"service"} if service_allowed else set())
    if (not isinstance(actor, str) or not 1 <= len(actor) <= 100
            or not isinstance(tenant, str) or not SCOPE_ID.fullmatch(tenant)
            or not isinstance(role, str) or role not in allowed or not isinstance(sites, list) or not sites
            or any(not isinstance(site, str) or not SCOPE_ID.fullmatch(site) for site in sites)):
        _deny("Invalid identity scope")
    return {"actor": actor, "tenant": tenant, "role": role, "sites": sorted(set(sites))}


@lru_cache(maxsize=8)
def _jwks_client(uri):
    # URI comes only from server configuration, never from a token's jku header.
    parsed = urlsplit(uri)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        _deny("OIDC JWKS must use a configured HTTPS URL", 503)
    return jwt.PyJWKClient(uri, cache_jwk_set=True, lifespan=300, timeout=5)


def _oidc_identity(token):
    config = settings.OIDC
    if not all(config.get(k) for k in ("issuer", "audience", "jwks_uri")):
        _deny()
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            _deny("Unsupported token algorithm")
        key = _jwks_client(config["jwks_uri"]).get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=["RS256"],
            issuer=config["issuer"], audience=config["audience"],
            options={"require": ["exp", "iat", "iss", "aud", "sub"]}, leeway=15)
    except jwt.PyJWKClientConnectionError:
        _deny("Identity provider temporarily unavailable", 503)
    except (jwt.PyJWTError, ValueError, TypeError):
        _deny("Invalid or expired access token")
    scope = claims.get("scope")
    if not isinstance(scope, str) or config["scope"] not in scope.split():
        _deny("API scope required", 403)
    amr = claims.get("amr", [])
    acr = claims.get("acr")
    if not ((isinstance(amr, list) and "mfa" in amr)
            or (isinstance(acr, str) and acr in config["mfa_acr_values"])):
        _deny("MFA authentication required", 403)
    if not isinstance(claims["sub"], str) or not claims["sub"]:
        _deny("Stable subject required")
    actor = "oidc:" + hashlib.sha256((claims["iss"] + "\0" + claims["sub"]).encode()).hexdigest()
    return _identity({"actor": actor, "role": claims.get(config["role_claim"]),
        "tenant": claims.get(config["tenant_claim"]), "sites": claims.get(config["sites_claim"])})


def authenticate_token(authorization):
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        _deny()
    token = authorization[7:]
    if not token or len(token) > 16384 or not token.isascii():
        _deny()
    for configured, value in settings.AUTH_TOKENS.items():
        if secrets.compare_digest(configured.encode(), token.encode()):
            # Human static tokens are strictly a synthetic demo facility.
            if not settings.DEMO and value.get("role") != "service":
                _deny("Human access requires OIDC")
            return _identity(value, service_allowed=True)
    return _oidc_identity(token)


def authenticate_request(request):
    service = authenticate_token(request.headers.get("Authorization", ""))
    delegated = request.headers.get("X-Unum-Caller-Authorization")
    if delegated is None:
        return service
    if service["role"] != "service":
        _deny("Only a service may delegate a caller", 403)
    caller = authenticate_token(delegated)
    if caller["role"] == "service" or caller["tenant"] != service["tenant"]:
        _deny("Delegated tenant is outside service scope", 403)
    sites = sorted(set(caller["sites"]) & set(service["sites"]))
    if not sites:
        _deny("Delegated sites are outside service scope", 403)
    return {"actor": caller["actor"], "tenant": caller["tenant"], "sites": sites,
        "role": "service", "caller_role": caller["role"]}
