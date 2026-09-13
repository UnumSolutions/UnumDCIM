from dataclasses import asdict
from django.db import transaction
from django.http import JsonResponse
from platform_core.api import Problem, emit, endpoint, site_allowed, tenant
from unum_sync.contracts import MappingContract, Observation, reconcile
from unum_sync.reconcile import Scope
from .models import Conflict, Connection


def serialize(c):
    return {"id": str(c.id), "site": c.site, "entity": c.entity, "field": c.field, "owner": c.owner,
            "baseline": c.baseline, "candidates": c.candidates, "state": c.state,
            "resolution": c.resolution, "revision": c.revision, "observed_at": c.observed_at.isoformat()}


@endpoint()
def status(request):
    return JsonResponse({"contract": "unum.sync-status/1", "live_write_enabled": False,
        "connections": list(Connection.objects.filter(tenant=tenant(request), site__in=request.identity["sites"])
                            .values("id", "label", "state", "capabilities", "last_success")),
        "conflicts": [serialize(c) for c in Conflict.objects.filter(tenant=tenant(request), site__in=request.identity["sites"])]})


@endpoint(("POST",), roles=("operator", "admin"))
def resolve(request, conflict_id):
    with transaction.atomic():
        c = Conflict.objects.select_for_update().filter(pk=conflict_id, tenant=tenant(request)).first()
        if not c:
            raise Problem("Conflict not found", 404)
        site_allowed(request, c.site)
        if c.revision != request.data.get("expected_revision") or c.state != "conflict":
            raise Problem("Conflict changed; refresh before resolving", 409)
        candidate = request.data["candidate"]
        if candidate not in c.candidates:
            raise Problem("Unknown candidate")
        c.resolution = {"connection": candidate, "value": c.candidates[candidate], "actor": request.identity["actor"]}
        c.state = "resolution_staged"
        c.revision += 1
        c.save()
        emit(c.tenant, c.site, "conflict.resolution_staged", c.id, c.revision,
             request.identity["actor"], c.resolution)
    return JsonResponse(serialize(c))


@endpoint(("POST",), roles=("operator", "admin", "service"))
def rehearsal(request):
    d = request.data
    scope = Scope(tenant(request), d["connection"], d["entity"])
    site_allowed(request, d["site"])
    peers = [Observation(scope=scope, **p) for p in d["peers"]]
    previous = {p["connection"]: Observation(scope=scope, **p) for p in d.get("previous", [])} or None
    decisions = reconcile(scope, d["baseline"], peers, MappingContract(**d["mapping"]),
                          {k: set(v) for k, v in d.get("writable", {}).items()}, previous)
    return JsonResponse({"dry_run": True, "decisions": [asdict(x) for x in decisions]})
