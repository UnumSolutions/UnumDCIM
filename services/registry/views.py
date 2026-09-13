import json
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from platform_core.api import endpoint
from platform_core.compatibility import check_install


def manifests():
    return [json.loads(p.read_text()) for p in sorted((settings.BASE_DIR / "contracts/modules").glob("*.json"))]


@endpoint()
def modules(request):
    return JsonResponse({"contract": "unum.modules/1", "items": manifests(),
                          "plugin_install_enabled": False})


@endpoint(("POST",), roles=("admin",))
def preflight(request):
    candidate = request.data | {"signature_verified": False}
    errors = check_install(candidate, {m["id"]: m for m in manifests()})
    return JsonResponse({"allowed": not errors, "errors": errors,
                         "note": "Read-only preflight. No signature verifier or installer is enabled."})
