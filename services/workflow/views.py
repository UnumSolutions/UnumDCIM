import hashlib
import json
import uuid
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from platform_core.api import Problem, emit, endpoint, remote, site_allowed, tenant
from .models import Change


def serialize(c):
    return {"id": str(c.id), "site": c.site, "proposer": c.proposer, "approver": c.approver,
            "payload": c.payload, "state": c.state, "error": c.error, "revision": c.revision,
            "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat()}


def change_list(request):
    """Keep unfinished work visible independently of the completed history page."""
    try:
        limit = int(request.GET.get("history_limit", "50"))
    except ValueError:
        raise Problem("History limit must be an integer between 1 and 100")
    if not 1 <= limit <= 100:
        raise Problem("History limit must be an integer between 1 and 100")
    rows = Change.objects.filter(tenant=tenant(request), site__in=request.identity["sites"])
    history = rows.filter(state="completed")
    scope = hashlib.sha256(json.dumps({"tenant": tenant(request), "sites": request.identity["sites"]},
                                      sort_keys=True).encode()).hexdigest()
    cursor = request.GET.get("history_cursor")
    if cursor is not None:
        try:
            if not cursor or len(cursor) > 2048:
                raise ValueError()
            position = signing.loads(cursor, salt="workflow.completed-history")
            if position["scope"] != scope:
                raise ValueError()
            created_at = parse_datetime(position["created_at"])
            row_id = uuid.UUID(position["id"])
            if created_at is None or created_at.tzinfo is None:
                raise ValueError()
        except (signing.BadSignature, ValueError, TypeError, KeyError):
            raise Problem("Invalid history cursor; restart completed history")
        history = history.filter(Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=row_id))
    completed = list(history.order_by("-created_at", "-id")[:limit + 1])
    has_more = len(completed) > limit
    completed = completed[:limit]
    next_cursor = None
    if has_more:
        last = completed[-1]
        next_cursor = signing.dumps({"scope": scope, "created_at": last.created_at.isoformat(),
                                     "id": str(last.id)}, salt="workflow.completed-history")
    active = list(rows.exclude(state="completed").order_by("-created_at", "-id"))
    return JsonResponse({"contract": "unum.changes/1", "items": [serialize(c) for c in active + completed],
                         "active_count": len(active),
                         "history": {"limit": limit, "next_cursor": next_cursor, "has_more": has_more}})


@endpoint(("GET", "POST"))
def changes(request):
    if request.method == "GET":
        return change_list(request)
    if request.identity["role"] not in ("operator", "admin"):
        raise Problem("Permission denied", 403)
    d = request.data
    required = {"asset_id", "rack_id", "u", "face", "expected_revision", "authority_epoch", "site", "idempotency_key"}
    if set(d) != required:
        raise Problem("Unexpected or missing change fields")
    if not isinstance(d["idempotency_key"], str) or not 1 <= len(d["idempotency_key"]) <= 100:
        raise Problem("Idempotency key required")
    site_allowed(request, d["site"])
    payload = {k: v for k, v in d.items() if k != "idempotency_key"}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    existing = Change.objects.filter(tenant=tenant(request), proposer=request.identity["actor"], idempotency_key=d["idempotency_key"]).first()
    if existing:
        if existing.payload_hash != digest:
            raise Problem("Idempotency key reused with a different command", 409)
        return JsonResponse(serialize(existing))
    asset = remote(request, "inventory", "GET", "assets/" + d["asset_id"])
    if asset["site"] != d["site"]:
        raise Problem("Asset and requested site differ", 403)
    preview = remote(request, "placement", "POST", "preview", payload)
    with transaction.atomic():
        c, created = Change.objects.get_or_create(tenant=tenant(request), proposer=request.identity["actor"],
            idempotency_key=d["idempotency_key"], defaults={"site": d["site"], "payload_hash": digest,
                                                         "payload": payload, "state": preview["state"]})
        if c.payload_hash != digest:
            raise Problem("Idempotency key reused with a different command", 409)
        if created:
            emit(c.tenant, c.site, "change.proposed", c.id, c.revision, c.proposer, {"request_id": str(c.id), "state": c.state})
    return JsonResponse(serialize(c), status=201 if created else 200)


@endpoint()
def change(request, change_id):
    c = Change.objects.filter(pk=change_id, tenant=tenant(request), site__in=request.identity["sites"]).first()
    if not c:
        raise Problem("Change not found", 404)
    return JsonResponse(serialize(c))


@endpoint(("POST",), roles=("approver", "admin"))
def approve(request, change_id):
    with transaction.atomic():
        c = Change.objects.select_for_update().filter(pk=change_id, tenant=tenant(request)).first()
        if not c:
            raise Problem("Change not found", 404)
        site_allowed(request, c.site)
        if c.proposer == request.identity["actor"]:
            raise Problem("A different principal must approve", 403)
        if request.data.get("expected_revision") != c.revision:
            raise Problem("Change revision changed", 409)
        if c.state != "awaiting_approval":
            raise Problem("Change is not awaiting approval", 409)
        c.state, c.approver = "approved", request.identity["actor"]
        c.revision += 1
        c.save()
        emit(c.tenant, c.site, "change.approved", c.id, c.revision, c.approver, {"request_id": str(c.id)})
    return JsonResponse(serialize(c))


@endpoint(("POST",), roles=("operator", "approver", "admin"))
def execute(request, change_id):
    with transaction.atomic():
        c = Change.objects.select_for_update().filter(pk=change_id, tenant=tenant(request)).first()
        if not c:
            raise Problem("Change not found", 404)
        site_allowed(request, c.site)
        if c.state == "completed":
            return JsonResponse(serialize(c))
        if c.state == "replan_required":
            raise Problem("Refresh placement and submit a new proposal for approval", 409, "replan_required")
        if c.state not in ("approved", "executing") or not c.approver or c.approver == c.proposer:
            raise Problem("Change needs a separate principal's approval", 409)
        if c.state != "executing":
            c.state, c.error = "executing", ""
            c.revision += 1
            c.save()
            emit(c.tenant, c.site, "change.executing", c.id, c.revision,
                 request.identity["actor"], {"request_id": str(c.id)})
    # Never hold a local DB transaction across remote network operations.
    try:
        reservation = remote(request, "placement", "POST", "reservations", c.payload | {"request_id": str(c.id)})
        if reservation.get("state") not in {"held", "committed", "expired", "invalid"}:
            raise Problem("Placement reservation was not confirmed; retry execution", 503)
        committed = remote(request, "placement", "POST", "reservations/" + str(c.id) + "/commit", {})
        if committed.get("state") != "committed":
            raise Problem("Placement commit was not confirmed; retry execution", 503)
    except Problem as exc:
        with transaction.atomic():
            c = Change.objects.select_for_update().get(pk=c.id)
            if c.state == "executing":
                c.error = exc.message
                # Only an explicit, definitive placement rejection permits a new
                # request ID. A timeout can hide a successful commit: keep the
                # same reservation ID and recover via idempotent execution.
                if exc.code in {"plan_invalid", "reservation_expired", "reservation_invalid"}:
                    c.state = "replan_required"
                    c.revision += 1
                    emit(c.tenant, c.site, "change.replan_required", c.id, c.revision,
                         request.identity["actor"], {"request_id": str(c.id), "reason": exc.code})
                c.save()
        return JsonResponse(serialize(c), status=200 if c.state == "completed" else exc.status)
    with transaction.atomic():
        c = Change.objects.select_for_update().get(pk=c.id)
        if c.state != "completed":
            c.state, c.error = "completed", ""
            c.revision += 1
            c.save()
            emit(c.tenant, c.site, "change.completed", c.id, c.revision, request.identity["actor"], {"request_id": str(c.id)})
    return JsonResponse(serialize(c))
