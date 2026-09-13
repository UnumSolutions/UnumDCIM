from django.conf import settings
from django.urls import include, path
from platform_core.api import health, metrics, ready, openapi

urlpatterns = [path("health", health), path("ready", ready), path("metrics", metrics),
               path("api/v1/openapi", openapi),
               path("api/v1/", include("services." + settings.SERVICE + ".urls"))]
