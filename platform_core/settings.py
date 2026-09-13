import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SERVICE = os.environ.get("UNUM_SERVICE", "inventory")
if SERVICE not in {"inventory", "placement", "workflow", "synchronization", "registry"}:
    raise RuntimeError("Unknown implemented service")
DEMO = os.environ.get("UNUM_DEMO") == "1"
SECRET_KEY = os.environ.get("UNUM_SECRET_KEY", "local-demo-only" if DEMO else "")
if not SECRET_KEY:
    raise RuntimeError("UNUM_SECRET_KEY is required outside demo mode")
DEBUG = False
ALLOWED_HOSTS = os.environ.get("UNUM_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
ROOT_URLCONF = "platform_core.urls"
INSTALLED_APPS = ["platform_core", "services." + SERVICE]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware"]
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_DIR = Path(os.environ.get("UNUM_DATA_DIR", BASE_DIR / ".data"))
if os.environ.get("PGHOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["PGDATABASE"], "USER": os.environ["PGUSER"],
        "PASSWORD": os.environ["PGPASSWORD"], "HOST": os.environ["PGHOST"],
        "PORT": os.environ.get("PGPORT", "5432"),
        "OPTIONS": {"sslmode": os.environ.get("PGSSLMODE", "verify-full")},
    }}
elif DEMO:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                              "NAME": DATA_DIR / (SERVICE + ".sqlite3"),
                              "OPTIONS": {"timeout": 20}}}
else:
    raise RuntimeError("PostgreSQL required outside local demo")
AUTH_TOKENS = json.loads(os.environ.get("UNUM_AUTH_TOKENS", "{}"))
SERVICE_TOKEN = os.environ.get("UNUM_SERVICE_TOKEN", "")
SERVICE_URLS = json.loads(os.environ.get("UNUM_SERVICE_URLS", "{}"))
NATS_URL = os.environ.get("UNUM_NATS_URL", "")
OIDC = {
    "issuer": os.environ.get("UNUM_OIDC_ISSUER", ""),
    "audience": os.environ.get("UNUM_OIDC_AUDIENCE", ""),
    "jwks_uri": os.environ.get("UNUM_OIDC_JWKS_URI", ""),
    "scope": os.environ.get("UNUM_OIDC_SCOPE", "unum.api"),
    "role_claim": os.environ.get("UNUM_OIDC_ROLE_CLAIM", "unum_role"),
    "tenant_claim": os.environ.get("UNUM_OIDC_TENANT_CLAIM", "unum_tenant"),
    "sites_claim": os.environ.get("UNUM_OIDC_SITES_CLAIM", "unum_sites"),
    "mfa_acr_values": json.loads(os.environ.get("UNUM_OIDC_MFA_ACR_VALUES", "[]")),
}
