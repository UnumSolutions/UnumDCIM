from django.db import transaction
from django.http import JsonResponse
from platform_core.api import Problem, emit, endpoint, site_allowed, tenant
from .models import Asset


def serialize(asset):
    return {k: getattr(asset, k) for k in ("id", "site", "name", "manufacturer", "model", "serial",
            "asset_tag", "height_u", "watts", "lifecycle", "revision")} | {"updated_at": asset.updated_at.isoformat()}


@endpoint()
def assets(request):
    rows = Asset.objects.filter(tenant=tenant(request), site__in=request.identity["sites"])
    if request.GET.get("q"):
        rows = rows.filter(name__icontains=request.GET["q"])
    return JsonResponse({"contract": "unum.inventory/1", "items": [serialize(a) for a in rows.order_by("id")[:1000]]})


@endpoint(("GET", "PATCH"))
def asset(request, asset_id):
    with transaction.atomic():
        obj = Asset.objects.select_for_update().filter(pk=asset_id, tenant=tenant(request)).first()
        if not obj:
            raise Problem("Asset not found", 404)
        site_allowed(request, obj.site)
        if request.method == "PATCH":
            if request.identity["role"] not in ("operator", "admin"):
                raise Problem("Permission denied", 403)
            if set(request.data) != {"name", "expected_revision"}:
                raise Problem("Only name and expected_revision accepted in this foundation")
            if request.data["expected_revision"] != obj.revision:
                raise Problem("Asset revision changed", 409)
            name = request.data["name"]
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
                raise Problem("Name must contain 1–160 characters")
            obj.name = name.strip()
            obj.revision += 1
            obj.save()
            emit(obj.tenant, obj.site, "asset.updated", obj.id, obj.revision,
                 request.identity["actor"], {"name": obj.name})
        return JsonResponse(serialize(obj))
