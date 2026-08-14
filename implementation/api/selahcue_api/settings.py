import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _database_config() -> dict:
    """Postgres from ``DATABASE_URL`` in production — so a row-locking backend makes
    ``select_for_update`` (the device instance-limit guard, DEC-004) actually hold; bundled
    SQLite otherwise for dev/test. No third-party dep: a minimal DSN parse."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    from urllib.parse import unquote, urlparse

    parsed = urlparse(url)
    engines = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
    }
    engine = engines.get(parsed.scheme)
    if engine is None:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme!r}")
    return {
        "ENGINE": engine,
        "NAME": unquote((parsed.path or "").lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    }


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "selahcue-dev-only-insecure-key")
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "strawberry_django",
    "selahcue_api.apps.accounts.apps.SelahCueAccountsConfig",
    "selahcue_api.apps.billing.apps.SelahCueBillingConfig",
    "selahcue_api.apps.license_keys.apps.SelahCueLicenseKeysConfig",
    "selahcue_api.apps.catalogue.apps.SelahCueCatalogueConfig",
    "selahcue_api.apps.entitlements.apps.SelahCueEntitlementsConfig",
    "selahcue_api.apps.downloads.apps.SelahCueDownloadsConfig",
    "selahcue_api.apps.devices.apps.SelahCueDevicesConfig",
    "selahcue_api.apps.audit.apps.SelahCueAuditConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "selahcue_api.urls"
WSGI_APPLICATION = "selahcue_api.wsgi.application"
ASGI_APPLICATION = "selahcue_api.asgi.application"

DATABASES = {"default": _database_config()}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SAMESITE = "Strict"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

CORS_ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv("SELAHCUE_CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
)

GRAPHQL_ALLOW_QUERIES_VIA_GET = False
GRAPHQL_MULTIPART_UPLOADS_ENABLED = False
GRAPHQL_IDE = "graphiql" if DEBUG else None
GRAPHQL_INTROSPECTION_ENABLED = DEBUG
SELAHCUE_TRUST_ACTOR_HEADERS = env_bool("SELAHCUE_TRUST_ACTOR_HEADERS", DEBUG)

# Ed25519 seed (32 bytes, standard base64) signing offline entitlement manifests (DEC-004).
# DELIBERATELY has no default, unlike DJANGO_SECRET_KEY above: an absent key must fail loudly
# at issuance rather than degrade to unsigned output or to a well-known dev key. Either would
# let anyone forge an entitlement, voiding the offline licensing model entirely.
# Generate: python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"
ENTITLEMENT_SIGNING_KEY = os.getenv("SELAHCUE_ENTITLEMENT_SIGNING_KEY", "")

# Traditional email/password customer auth (DEC-007 / ADR-0023). Env-overridable; the accounts
# services fall back to these same defaults via getattr, so unset is safe in dev.
ACCOUNT_SESSION_TTL_SECONDS = int(os.getenv("ACCOUNT_SESSION_TTL_SECONDS", str(30 * 24 * 3600)))
ACCOUNT_EMAIL_VERIFY_TTL_SECONDS = int(os.getenv("ACCOUNT_EMAIL_VERIFY_TTL_SECONDS", str(24 * 3600)))
ACCOUNT_PASSWORD_RESET_TTL_SECONDS = int(os.getenv("ACCOUNT_PASSWORD_RESET_TTL_SECONDS", str(3600)))
ACCOUNT_LOGIN_LOCKOUT_THRESHOLD = int(os.getenv("ACCOUNT_LOGIN_LOCKOUT_THRESHOLD", "5"))
ACCOUNT_LOGIN_LOCKOUT_SECONDS = int(os.getenv("ACCOUNT_LOGIN_LOCKOUT_SECONDS", "900"))
ACCOUNT_MIN_PASSWORD_LENGTH = int(os.getenv("ACCOUNT_MIN_PASSWORD_LENGTH", "10"))
