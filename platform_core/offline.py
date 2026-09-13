"""Offline grant and authority policy primitives, not an identity provider.

Only a trusted MFA enrollment service may issue grants. This module deliberately
has no public issuance endpoint. Local revocations must be durably supplied by
the site access service. Host clocks must be secured by the deployment.
"""
import base64
import hashlib
import hmac
import json
import uuid

MAX_OFFLINE_SECONDS = 72 * 60 * 60
FORBIDDEN_OFFLINE = {"plugin.install", "access.grant", "authority.transfer", "cross_site.move"}


def _sign(body, key):
    if len(key) < 32:
        raise ValueError("A dedicated signing key of at least 32 bytes is required")
    return hmac.new(key, body.encode(), hashlib.sha256).hexdigest()


def issue_grant(*, actor, tenant, site, permissions, authority_epoch, now, key, mfa_verified):
    if not mfa_verified:
        raise ValueError("Trusted MFA verification is required before issuance")
    if not actor or not tenant or not site or authority_epoch < 1:
        raise ValueError("Grant identity and authority scope required")
    if FORBIDDEN_OFFLINE.intersection(permissions):
        raise ValueError("Grant requests an operation prohibited offline")
    payload = {"contract": "unum.offline-grant/1", "id": str(uuid.uuid4()), "actor": actor,
               "tenant": tenant, "site": site, "permissions": sorted(set(permissions)),
               "authority_epoch": authority_epoch, "issued_at": now,
               "expires_at": now + MAX_OFFLINE_SECONDS}
    body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).decode()
    return body + "." + _sign(body, key)


def verify_grant(token, *, tenant, site, permission, authority_epoch, now, key, revoked_ids):
    try:
        body, signature = token.split(".")
        if not hmac.compare_digest(_sign(body, key), signature):
            raise ValueError("Invalid grant signature")
        p = json.loads(base64.urlsafe_b64decode(body))
        if p["contract"] != "unum.offline-grant/1" or p["tenant"] != tenant or p["site"] != site:
            raise ValueError("Grant scope mismatch")
        if p["authority_epoch"] != authority_epoch or p["id"] in revoked_ids:
            raise ValueError("Grant revoked or authority superseded")
        if not p["issued_at"] <= now < p["expires_at"] or p["expires_at"] - p["issued_at"] > MAX_OFFLINE_SECONDS:
            raise ValueError("Grant expired, issued in the future or exceeds 72 hours")
        if permission in FORBIDDEN_OFFLINE or permission not in p["permissions"]:
            raise ValueError("Operation not permitted offline")
        return p
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed offline grant") from exc


def operation_state(*, local_authority, epoch, expected_epoch, connected, owner, cross_site=False):
    if not local_authority or epoch != expected_epoch:
        return "pending_site_authority"
    if cross_site:
        return "requires_coordinated_transfer" if connected else "pending_connectivity"
    if owner != "unum":
        return "pending_owner_confirmation"
    return "eligible_for_local_workflow"
