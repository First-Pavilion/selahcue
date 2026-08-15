import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _database_config() -> dict:
    """Discrete ``SQL_*`` variables, matching the First Pavilion house convention (see
    yharah-logistics `core/settings.py`) rather than a `DATABASE_URL` DSN.

    Defaults to bundled SQLite so a bare `pytest` needs no environment. Point `SQL_ENGINE` at
    postgresql in any real deployment: the device instance-limit guard (DEC-004) uses
    ``select_for_update``, which SQLite silently no-ops (`has_select_for_update=False`), so the
    limit is only actually enforced on a row-locking backend.
    """
    engine = os.getenv("SQL_ENGINE", "django.db.backends.sqlite3")
    if engine.endswith("sqlite3"):
        return {"ENGINE": engine, "NAME": os.getenv("SQL_DATABASE", str(BASE_DIR / "db.sqlite3"))}
    return {
        "ENGINE": engine,
        "NAME": os.getenv("SQL_DATABASE", "selahcue"),
        "USER": os.getenv("SQL_USER", "postgres"),
        "PASSWORD": os.getenv("SQL_PASSWORD", "postgres"),
        "HOST": os.getenv("SQL_HOST", "localhost"),
        "PORT": os.getenv("SQL_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    }


# dev | staging | prod. Gates debug tooling, mail backend and Sentry, as in yharah-logistics.
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

# `DEBUG=1` / `DEBUG=0`, the house convention. env_bool also accepts true/yes/on.
DEBUG = env_bool("DEBUG", False)

# Required outside dev. yharah raises unconditionally, but SelahCue's tests run bare (no
# container env), so the hard requirement is scoped to non-dev — still stricter than the
# previous silent insecure default, which would have shipped to production unnoticed.
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if ENVIRONMENT != "dev":
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            f"SECRET_KEY must be set when ENVIRONMENT={ENVIRONMENT!r}."
        )
    SECRET_KEY = "selahcue-dev-only-insecure-key"

# Space-separated, matching the house convention (`DJANGO_ALLOWED_HOSTS=localhost 127.0.0.1`).
# Commas are also tolerated so an older comma-separated value cannot silently collapse into a
# single bogus host.
ALLOWED_HOSTS = [
    host
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost 127.0.0.1 testserver")
    .replace(",", " ")
    .split()
    if host
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
    "selahcue_api.apps.throttling.apps.SelahCueThrottlingConfig",
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

# There was no TEMPLATES block until now: the API is GraphQL + JSON and rendered nothing.
# The transactional emails (docs/design/TRANSACTIONAL-EMAIL-spec.md) are the first
# templates, so this is a whole definition rather than an added DIRS entry.
# `django.contrib.messages` and MessageMiddleware are already installed, and the admin-less
# `check` framework still expects the auth/messages context processors beside them, so the
# four standard processors are kept rather than trimmed to the one email rendering needs.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "selahcue_api" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

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

# --- Celery / Redis (house convention: yharah-logistics core/settings.py) -------------------
# `redis` is the compose service name; db 2 is the broker, matching the sibling project so the
# two stacks can share a Redis instance without colliding.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/2")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Run tasks inline instead of enqueuing them. OFF by default — this is a test/debug lever,
# and turning it on in a real deployment would move email sending back into the request.
# Tests that need `.delay()` to execute synchronously flip it through the `settings` fixture.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
if CELERY_TASK_ALWAYS_EAGER and ENVIRONMENT == "prod":
    # Guarded like SECRET_KEY above. Eager mode runs every task inline in the web process,
    # which puts SMTP back on the request path and undoes the decoupling this whole worker
    # exists for — a signup would then 500 whenever the mail provider is slow. It is a
    # test/debug lever, so an env var must not be able to switch it on in production.
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "CELERY_TASK_ALWAYS_EAGER must not be enabled when ENVIRONMENT='prod': it moves "
        "task execution (including SMTP) back into the request path."
    )
# Only meaningful while eager: re-raise task exceptions in the caller instead of burying them
# in an EagerResult, so an inline failure surfaces as a test failure rather than silence.
CELERY_TASK_EAGER_PROPAGATES = env_bool("CELERY_TASK_EAGER_PROPAGATES", CELERY_TASK_ALWAYS_EAGER)

from celery.schedules import crontab  # noqa: E402  (kept beside the schedule it configures)

# Beat dispatches by NAME, so every name here must be one the worker registers — i.e. it must
# be declared with @shared_task inside some installed app's `tasks.py`, the only module
# `autodiscover_tasks()` imports. tests/test_revocation_cascade.py asserts that in a clean
# interpreter; without it a misplaced task fails as NotRegistered nightly, in production only.
CELERY_BEAT_SCHEDULE = {
    # Hourly: a revoked licence should stop working within the hour, not at expiry.
    "cascade-license-revocations": {
        "task": "devices.cascade_license_revocations",
        "schedule": crontab(minute=0),
    },
    # Nightly: pure row hygiene, no behavioural effect.
    "sweep-expired-credentials": {
        "task": "accounts.sweep_expired_credentials",
        "schedule": crontab(hour=3, minute=30),
    },
}

# --- Cache / throttling ---------------------------------------------------------------
# Redis db 1 — deliberately NOT db 2, which is the Celery broker: a FLUSHDB on either
# must not destroy the other. Falls back to per-process LocMemCache when CACHE_URL is
# unset so a bare `pytest` needs no Redis. That fallback is only safe because the
# throttle's logic tests inject their own store.
_cache_url = os.getenv("CACHE_URL", "")
CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": _cache_url}
        if _cache_url
        else {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "selahcue"}
    )
}

# 0 = trust REMOTE_ADDR only. Raise to the number of proxies in front of Django BEFORE
# relying on X-Forwarded-For — a caller-supplied header is otherwise a limiter bypass.
SELAHCUE_TRUSTED_PROXY_COUNT = int(os.getenv("SELAHCUE_TRUSTED_PROXY_COUNT", "0"))

# (limit, window_seconds) per client IP. Activation is the expensive one — it runs
# `make_password` against the enrollment key — so it gets the tighter budget.
SELAHCUE_THROTTLE_ACTIVATION = (10, 60)
SELAHCUE_THROTTLE_DEVICE_READ = (60, 60)

# Resend-verification is unauthenticated AND sends email on demand, so it is both a spam
# vector (flooding an arbitrary victim's mailbox) and a cost vector. Three budgets, because
# each stops a different attack and none subsumes the others:
#   ADDRESS — per target address, so one victim cannot be flooded. Spent whether or not the
#             account exists; a limit that only bit for real accounts would be an oracle.
#   IP      — per source, so one client cannot spray thousands of DISTINCT addresses (which
#             the per-address budget alone would never notice).
#   GLOBAL  — a ceiling on total sends, which is what actually bounds the provider bill when
#             an attack is distributed across many IPs.
SELAHCUE_THROTTLE_RESEND_ADDRESS = (3, 900)
SELAHCUE_THROTTLE_RESEND_IP = (10, 3600)
SELAHCUE_THROTTLE_RESEND_GLOBAL = (500, 3600)

# --- Mail --------------------------------------------------------------------------------
# Dev points at mailhog (compose service, port 1025) so the transactional templates
# (docs/design/TRANSACTIONAL-EMAIL-spec.md) can be verified end to end before any provider
# exists. Non-dev reads real SMTP credentials.
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@selahcue.com")
DEFAULT_EMAIL = os.getenv("DEFAULT_EMAIL", "info@firstpavitech.com")

# MAILERS, not the EMAIL_* settings. Django 6.1 deprecates EMAIL_BACKEND/EMAIL_HOST/... in
# favour of this dict and removes them in 7.0 — since we are already on 6.1, using the old
# names would ship a deprecation warning on day one. yharah-logistics still uses EMAIL_* only
# because it predates the change; the env var NAMES (MAIL_*) stay identical to the house
# convention, which is what actually has to match.
_mail_is_dev = ENVIRONMENT == "dev"
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            # dev → mailhog (compose service, no auth, no TLS)
            "host": os.getenv("MAIL_HOST", "selahcue_mailhog" if _mail_is_dev else ""),
            "port": int(os.getenv("MAIL_PORT", "1025" if _mail_is_dev else "587")),
            "username": os.getenv("MAIL_USERNAME", ""),
            "password": os.getenv("MAIL_PASSWORD", ""),
            "use_tls": not _mail_is_dev,
            "use_ssl": False,
        },
    }
}

# --- Error monitoring ----------------------------------------------------------------------
# Wired only when a DSN is present AND we are not in dev, so local runs never emit events.
SENTRY_DSN = os.getenv("SENTRY_DSN", "")

# Ed25519 seed (32 bytes, standard base64) signing offline entitlement manifests (DEC-004).
# DELIBERATELY has no default, unlike SECRET_KEY above: an absent key must fail loudly
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

# Constant-time floor for the resend-verification mutation, in seconds. Every call is padded
# to this duration so the response time cannot distinguish an unknown address from one that
# actually dispatched an email (minting a token costs a ~120ms PBKDF2 plus a broker publish).
# ~2x the measured worst case. Lowering it below the real branch's cost re-opens the oracle;
# 0 disables padding entirely and should only ever be done in tests.
ACCOUNT_RESEND_MIN_SECONDS = float(os.getenv("ACCOUNT_RESEND_MIN_SECONDS", "0.25"))

# Base URL of the web surface that hosts /verify and /reset. NOTE: those routes do not
# exist yet — they land with slice 4 (86ajy7anx). Emails link to a 404 until then.
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:2000")
