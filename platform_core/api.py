"""Authenticated API boundary and scoped service-to-service transport."""
import functools
import hashlib
import json
import uuid

import httpx
from django.conf import settings
from django.db import transaction, connection, DatabaseError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from platform_core.auth import AuthenticationError, authenticate_request
from platform_core.models import AuditEntry, AuditHead, Outbox
from platform_core.tenancy import tenant_scope


class Problem(Exception):
    def __init__(self, message, status=400, code=None):
        self.message, self.status, self.code = message, status, code


def endpoint(methods=("GET",), roles=()):
    def decorate(fn):
        @csrf_exempt
        @functools.wraps(fn)
        def wrapped(request, *args, **kwargs):
            try:
                if request.method not in methods:
                    return JsonResponse({"error": "Method not allowed"}, status=405)
                identity = request.identity = authenticate_request(request)
                if roles and identity["role"] not in roles:
                    raise Problem("Permission denied", 403)
                request.data = json.loads(request.body) if request.body else {}
                if not isinstance(request.data, dict):
                    raise Problem("JSON object required")
                with tenant_scope(identity["tenant"]):
                    return fn(request, *args, **kwargs)
            except (Problem, AuthenticationError) as exc:
                code = getattr(exc, "code", None)
                return JsonResponse({"error": exc.message, **({"code": code} if code else {})}, status=exc.status)
            except (ValueError, KeyError, TypeError) as exc:
                return JsonResponse({"error": "Invalid or missing input: " + str(exc)}, status=400)
        return wrapped
    return decorate


def site_allowed(request, site):
    if site not in request.identity["sites"]:
        raise Problem("Site access denied", 403)


def tenant(request):
    return request.identity["tenant"]


def remote(request, service, method, path, data=None):
    base = settings.SERVICE_URLS.get(service)
    if not base or not settings.SERVICE_TOKEN:
        raise Problem("Dependency unavailable: " + service, 503)
    try:
        response = httpx.request(method, base + "/api/v1/" + path,
                                 json=data, headers={
                                     "Authorization": "Bearer " + settings.SERVICE_TOKEN,
                                     # Forward the credential, never caller-supplied identity claims.
                                     "X-Unum-Caller-Authorization": request.headers.get(
                                         "X-Unum-Caller-Authorization", request.headers.get("Authorization", "")),
                                 },
                                 timeout=5)
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Dependency returned an invalid response")
    except (httpx.HTTPError, ValueError):
        raise Problem("Dependency unavailable: " + service, 503)
    if response.status_code >= 400:
        raise Problem(result.get("error", "Dependency rejected operation"), response.status_code, result.get("code"))
    return result


def emit(tenant_id, site, kind, entity, revision, actor, data, authority_epoch=1):
    """Caller must hold a transaction: domain, audit and outbox commit together."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("emit requires atomic transaction")
    event_id = uuid.uuid4()
    payload = {"contract": "unum.event/1", "event_id": str(event_id), "producer": settings.SERVICE,
               "tenant": tenant_id, "site": site, "entity": str(entity), "revision": revision,
               "authority_epoch": authority_epoch, "actor": actor,
               "correlation_id": str(data.get("request_id", event_id)),
               "type": kind, "occurred_at": timezone.now().isoformat(), "data": data}
    Outbox.objects.create(id=event_id, tenant=tenant_id, site=site,
                          subject="unum." + settings.SERVICE + "." + kind, payload=payload)
    chain = tenant_id + "/" + site + "/" + settings.SERVICE
    head, _ = AuditHead.objects.get_or_create(chain=chain, tenant=tenant_id)
    head = AuditHead.objects.select_for_update().get(pk=chain)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256((head.digest + encoded).encode()).hexdigest()
    AuditEntry.objects.create(chain=chain, tenant=tenant_id, sequence=head.sequence + 1,
                              previous=head.digest, digest=digest, payload=payload)
    head.sequence += 1
    head.digest = digest
    head.save()


def health(request):
    return JsonResponse({"service": settings.SERVICE, "version": "0.1.0", "status": "ok",
                         "demo": settings.DEMO, "contract": "unum.health/1"})


def ready(request):
    from platform_core.auth import oidc_configuration_valid
    from platform_core.tenancy import validate_runtime_database
    if not settings.DEMO and not oidc_configuration_valid(settings.OIDC):
        return JsonResponse({"service": settings.SERVICE, "status": "identity_configuration_invalid"}, status=503)
    try:
        validate_runtime_database(refresh=True)
        return JsonResponse({"service": settings.SERVICE, "status": "ready"})
    except DatabaseError:
        return JsonResponse({"service": settings.SERVICE, "status": "database_unavailable"}, status=503)
    except RuntimeError:
        return JsonResponse({"service": settings.SERVICE, "status": "database_policy_invalid"}, status=503)


@endpoint()
def identity(request):
    response = JsonResponse({key: request.identity[key] for key in ("actor", "tenant", "sites", "role")})
    response["Cache-Control"] = "no-store"
    return response


@endpoint()
def openapi(request):
    path = settings.BASE_DIR / "contracts" / "openapi" / (settings.SERVICE + ".json")
    return JsonResponse(json.loads(path.read_text()))


@endpoint(roles=("service", "admin"))
def metrics(request):
    return JsonResponse({"service": settings.SERVICE,
                         "outbox_pending": Outbox.objects.filter(tenant=tenant(request), site__in=request.identity["sites"], published_at=None).count()})
