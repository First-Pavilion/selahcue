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

# NOT ENFORCED, ON PURPOSE. No CORS middleware is installed (corsheaders is in neither
# INSTALLED_APPS nor MIDDLEWARE), so this allow-list is read and then consumed by nothing:
# the API emits no Access-Control-* headers and an OPTIONS preflight returns 405.
#
# SelahCue serves its browser client SAME-ORIGIN rather than cross-origin —
# implementation/marketing/vite.config.ts proxies /graphql in dev, nginx.conf does the
# production half. That is what makes the SameSite=Strict session cookie below usable at
# all, and it also keeps Django's CSRF origin check satisfied. Enabling CORS would add a
# second, weaker path to the same surface which by construction CANNOT carry that cookie,
# and the usual next step is to relax SameSite to None — which is precisely what Strict is
# here to prevent. Treat switching this on as a security decision, not a config tweak.
#
# `selahcue_accounts.W001` (apps/accounts/checks.py) warns if the variable is set anyway,
# so the mismatch surfaces at `manage.py check` instead of as an opaque browser error.
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

# Per-client-IP budgets for the two password-reset mutations (86akcmfd4 — DEC-013's required
# follow-up). Both were reachable at an UNLIMITED rate: `request_password_reset` mints (or does
# not mint) a token depending on whether the email exists, and DEC-013 measured that branch gap
# at +0.437ms (sd 0.27ms) after removing the mint's PBKDF2 — smaller than before, but far
# cheaper to sample now that the PBKDF2 noise that used to hide it is gone. `confirm_password_
# reset` shares the same "zero budget on an unauthenticated mutation" gap. This setting does NOT
# re-close that timing gap (see the functions' own comments for why not) — it bounds how many
# samples one source can take, the same defence-in-depth role SELAHCUE_THROTTLE_RESEND_IP plays
# for resend-verification, and the same magnitude for the same reason.
SELAHCUE_THROTTLE_RESET_REQUEST = (20, 3600)
SELAHCUE_THROTTLE_RESET_CONFIRM = (20, 3600)

# Per-target-email and global budgets for `request_password_reset` (86akcn8p4 — Sana's
# more-urgent follow-up to 86akcmfd4). The per-IP budget above was scoped to DEC-013's timing-
# oracle threat and does NOT bound mail-bombing: a distributed attacker's volume against one
# victim was bounded by nothing but IP count, and IPv6 makes IP count nearly free (86akcn8ww).
# `request_password_reset` was therefore the only unauthenticated mail-sender in the API with
# neither a per-address cap nor a global one — `resend_email_verification` has had both since
# it shipped. These two mirror `SELAHCUE_THROTTLE_RESEND_ADDRESS` / `_GLOBAL` exactly: same
# shape, same magnitude, same "spent unconditionally, before the existence check" discipline
# (a budget that only bit for real accounts would itself be the existence oracle this endpoint
# is built to deny). Keyed on the same `_email_fingerprint` HMAC the mint branch already uses —
# never the raw submitted email — for the same cache-key-cardinality reason resend already
# solved.
SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (3, 900)
SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL = (500, 3600)

# COVERS THE THREE `SELAHCUE_THROTTLE_RESEND_*` BUDGETS ONLY — not the FOUR
# `SELAHCUE_THROTTLE_RESET_*` budgets above (86akcn8p4 added the address and global pair
# alongside the original request/confirm per-IP pair — read the count from the settings
# actually declared above, not from this comment, if they ever drift again), despite their
# sitting between this comment and the resend settings it describes. Read the name: this is
# the *resend* degraded ceiling, and `_claim_degraded_send` is called only from
# `resend_email_verification`.
#
# Every one of the SEVEN budgets above (three resend, four reset) fails OPEN when the limiter
# store is unreachable, so while Redis is down none of them bounds anything. This ceiling
# stands in for the resend three during an outage: a PER-WORKER, in-process fixed window,
# because the shared store is exactly what is broken. With N workers the effective limit is
# N x this. It is deliberately far below the global budget it replaces: an outage is the
# wrong time to be generous, and a caller whose send is skipped keeps the link they already
# had.
#
# THE RESET REQUEST PATH NOW HAS ITS OWN, SEPARATE STAND-IN (86akcn92k, F1) —
# `SELAHCUE_RESET_SEND_DEGRADED_CEILING` below, backed by its own `_DegradedSendCeiling`
# instance (`apps/accounts/services._reset_send_degraded_ceiling`), never a shared counter
# with this one: a shared counter would let one endpoint's outage-time flood spend the
# other's degraded budget. It bounds the SEND only — whether the reset REQUEST path also
# wants a process-local SAMPLING ceiling (bounding how many times the mint-vs-no-mint timing
# gap can be probed during an outage, on top of bounding the mail volume) is a separate,
# deliberately deferred decision the ticket explicitly left open; this setting does not make
# that call.
# See RESEND_DEGRADED_SEND_CEILING in apps/accounts/services.py.
SELAHCUE_RESEND_DEGRADED_SEND_CEILING = (20, 3600)

# `request_password_reset`'s own degraded-send ceiling (86akcn92k, F1) — see the comment
# above and `apps/accounts/services._DegradedSendCeiling` for the shared mechanism. Same
# magnitude as the resend ceiling, for the same reason: an outage is the wrong time to be
# generous, and a caller whose send is skipped keeps the link they already had.
SELAHCUE_RESET_SEND_DEGRADED_CEILING = (20, 3600)

# Per-client-IP budget for `verify_email` (86akcn92k — scoped out of 86akcmfd4's required
# follow-up, since DEC-013 named the reset paths specifically). LOWER severity than the reset
# paths, for a real reason: the EMAIL_VERIFY token carries 256 bits of entropy
# (`secrets.token_urlsafe(32)`), so a throttle here bounds FLOOD cost only — it is not closing
# a practical guessing attack the way the reset paths' budgets bound DEC-013's timing oracle.
# Same magnitude as SELAHCUE_THROTTLE_RESET_CONFIRM for that reason: defence in depth against
# an unauthenticated endpoint being hammered, not a response to a specific measured gap.
SELAHCUE_THROTTLE_VERIFY_EMAIL_IP = (20, 3600)

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
# actually dispatched an email (minting a token costs a PBKDF2 hash plus a broker publish).
#
# It is a FLOOR: it equalises only while every branch finishes inside it, and a branch that
# overruns is not padded at all, which re-opens the oracle by exactly the overrun. Keep this
# ABOVE the slowest branch. The eligible branch's own work measures ~197ms on the reference
# machine, so 0.25 (the previous value, wrongly described as ~2x the worst case) left only
# ~53ms for dispatch; 0.4 keeps a third of the floor spare and is pinned by
# `test_the_eligible_branch_costs_well_under_the_constant_time_floor`. Keep in sync with
# `RESEND_MIN_SECONDS_DEFAULT` in apps/accounts/services.py.
#
# If it is ever outgrown anyway, `_pad_to_floor` emits a rate-limited warning naming the
# overrun — an outgrown floor must surface, not degrade quietly. 0 disables padding entirely
# and should only ever be done in tests.
ACCOUNT_RESEND_MIN_SECONDS = float(os.getenv("ACCOUNT_RESEND_MIN_SECONDS", "0.4"))

# Base URL of the web surface that hosts /verify and /reset. Both routes exist as of 6d343b8;
# the emails minted here link to live token-landing pages.
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:2000")
