from datetime import timedelta
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from platform_core.api import Problem, emit, endpoint, site_allowed, tenant
from .models import Authority, Placement, Rack, Reservation, Room


def position(p):
    return {"asset_id": p.asset_id, "rack_id": p.rack_id, "u": p.u,
            "height_u": p.height_u, "face": p.face, "owner": p.owner, "revision": p.revision}


@endpoint()
def scene(request):
    rooms = Room.objects.filter(tenant=tenant(request), site__in=request.identity["sites"])
    return JsonResponse({"contract": "unum.scene/1", "generated_at": timezone.now().isoformat(),
        "rooms": list(rooms.values("id", "site", "site_name", "name", "region", "country", "state", "city", "room_type")),
        "racks": [{"id": r.id, "room_id": r.room_id, "label": r.label, "x": r.x, "y": r.y,
                   "height_u": r.height_u, "budget_watts": r.budget_watts}
                  for r in Rack.objects.filter(tenant=tenant(request), room__in=rooms)],
        "placements": [position(p) for p in Placement.objects.filter(tenant=tenant(request), rack__room__in=rooms)],
        "authority": list(Authority.objects.filter(tenant=tenant(request), site__in=request.identity["sites"])
                           .values("site", "epoch", "local", "connected"))})


def validate(request, data, lock=False):
    # Lock the source asset first, then both rack rows in deterministic order.
    qs = Placement.objects.select_for_update() if lock else Placement.objects
    p = qs.filter(asset_id=data["asset_id"], tenant=tenant(request)).first()
    if not p:
        raise Problem("Placement not found", 404)
    rack = Rack.objects.select_related("room").filter(pk=data["rack_id"], tenant=tenant(request)).first()
    if not rack:
        raise Problem("Rack not found", 404)
    site_allowed(request, rack.room.site)
    site_allowed(request, p.rack.room.site)
    if rack.room.site != p.rack.room.site:
        raise Problem("Cross-site moves require a coordinated transfer", 409)
    if data.get("site", rack.room.site) != rack.room.site:
        raise Problem("Requested site does not match placement", 403)
    if lock:
        list(Rack.objects.select_for_update().filter(pk__in=sorted({rack.id, p.rack_id})).order_by("pk"))
    authority_qs = Authority.objects.select_for_update() if lock else Authority.objects
    authority = authority_qs.filter(site=rack.room.site, tenant=tenant(request)).first()
    if not authority:
        raise Problem("Site authority unavailable", 503)
    if not authority.local or data["authority_epoch"] != authority.epoch:
        raise Problem("Site authority changed; refresh before proposing", 409)
    if p.revision != data["expected_revision"]:
        raise Problem("Placement changed; refresh before proposing", 409)
    u = data["u"]
    if type(u) is not int or u < 1 or u + p.height_u - 1 > rack.height_u:
        raise Problem("Destination is outside the rack U range", 409)
    if data["face"] not in ("front", "rear"):
        raise Problem("Face must be front or rear")
    # Full-depth foundation assets occupy both faces.
    occupied = Placement.objects.filter(rack=rack).exclude(asset_id=p.asset_id)
    held = Reservation.objects.filter(rack=rack, state="held", expires_at__gt=timezone.now())
    held = held.exclude(request_id=data.get("request_id")) if data.get("request_id") else held
    for other in [*occupied, *held]:
        if u < other.u + other.height_u and other.u < u + p.height_u:
            raise Problem("U range is occupied or reserved", 409)
    return p, rack, authority


@endpoint(("POST",), roles=("operator", "admin", "service"))
def preview(request):
    p, rack, _ = validate(request, request.data)
    return JsonResponse({"valid": True, "height_u": p.height_u, "owner": p.owner,
                          "state": "awaiting_nlyte" if p.owner != "unum" else "awaiting_approval"})


def reservation_result(request, existing, data):
    site_allowed(request, existing.rack.room.site)
    if any(getattr(existing, key) != data[key] for key in
           ("asset_id", "rack_id", "u", "face", "expected_revision", "authority_epoch")):
        raise Problem("Idempotency key reused for different reservation", 409)
    return JsonResponse({"state": existing.state})


@endpoint(("POST",), roles=("service",))
def reserve(request):
    d = request.data
    with transaction.atomic():
        existing = Reservation.objects.filter(request_id=d["request_id"], tenant=tenant(request)).first()
        if existing:
            return reservation_result(request, existing, d)
        # Serialize repeated commands for the same asset, then recheck the key.
        # Another request may have created or committed it while this one waited.
        source = Placement.objects.select_for_update().filter(asset_id=d["asset_id"], tenant=tenant(request)).first()
        if not source:
            raise Problem("Placement not found", 404, "plan_invalid")
        existing = Reservation.objects.filter(request_id=d["request_id"], tenant=tenant(request)).first()
        if existing:
            return reservation_result(request, existing, d)
        try:
            p, rack, authority = validate(request, d, lock=True)
            if p.owner != "unum":
                raise Problem("Nlyte owns placement; staged until verified owner confirmation", 409)
            if Reservation.objects.filter(asset_id=p.asset_id, state="held", expires_at__gt=timezone.now()).exists():
                raise Problem("Asset already has an active reservation", 409)
        except Problem as exc:
            if exc.status in (404, 409):
                exc.code = "plan_invalid"
            raise
        try:
            with transaction.atomic():
                Reservation.objects.create(request_id=d["request_id"], tenant=tenant(request), asset_id=p.asset_id,
                    rack=rack, u=d["u"], face=d["face"], height_u=p.height_u, expected_revision=p.revision,
                    authority_epoch=authority.epoch, expires_at=timezone.now() + timedelta(minutes=15))
        except IntegrityError:
            # Different assets may race using the same request key. The inner
            # savepoint keeps the surrounding transaction usable after a clash.
            existing = Reservation.objects.filter(request_id=d["request_id"], tenant=tenant(request)).first()
            if not existing:
                raise Problem("Reservation key unavailable", 409)
            return reservation_result(request, existing, d)
        emit(tenant(request), rack.room.site, "reservation.held", p.asset_id, p.revision,
             request.identity["actor"], d, authority.epoch)
    return JsonResponse({"state": "held"}, status=201)


def reject_reservation(request, reservation, state, message, code):
    """Persist a definitive rejection without raising out of its transaction."""
    reservation.state = state
    reservation.save(update_fields=["state"])
    emit(reservation.tenant, reservation.rack.room.site, "reservation." + state,
         reservation.asset_id, reservation.expected_revision, request.identity["actor"],
         {"request_id": str(reservation.request_id), "reason": code}, reservation.authority_epoch)
    return JsonResponse({"error": message, "code": code}, status=409)


@endpoint(("POST",), roles=("service",))
def commit(request, request_id):
    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().filter(pk=request_id, tenant=tenant(request)).first()
        if not reservation:
            raise Problem("Reservation not found", 404)
        site_allowed(request, reservation.rack.room.site)
        if reservation.state == "committed":
            return JsonResponse({"state": "committed", "revision": reservation.committed_revision})
        if reservation.state == "expired":
            raise Problem("Reservation expired; re-plan required", 409, "reservation_expired")
        if reservation.state != "held":
            raise Problem("Reservation invalid; re-plan required", 409, "reservation_invalid")
        if reservation.expires_at <= timezone.now():
            return reject_reservation(request, reservation, "expired",
                                      "Reservation expired; re-plan required", "reservation_expired")
        d = {k: getattr(reservation, k) for k in ("asset_id", "rack_id", "u", "face", "expected_revision", "authority_epoch")}
        d["request_id"] = str(reservation.request_id)
        try:
            p, rack, authority = validate(request, d, lock=True)
            if p.owner != "unum":
                raise Problem("Owner changed; re-plan required", 409)
        except Problem as exc:
            if exc.status in (404, 409):
                return reject_reservation(request, reservation, "invalid", exc.message, "reservation_invalid")
            raise
        p.rack, p.u, p.face = rack, reservation.u, reservation.face
        p.revision += 1
        p.save()
        reservation.state, reservation.committed_revision = "committed", p.revision
        reservation.save()
        emit(tenant(request), rack.room.site, "placement.confirmed", p.asset_id, p.revision,
             request.identity["actor"], d, authority.epoch)
    return JsonResponse({"state": "committed", "revision": p.revision})
