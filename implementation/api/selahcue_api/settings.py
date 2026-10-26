import os
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    """Space-separated, matching the house convention (`DJANGO_ALLOWED_HOSTS=localhost 127.0.0.1`).
    Commas are also tolerated so an older comma-separated value cannot silently collapse into a
    single bogus entry."""
    return [item for item in os.getenv(name, default).replace(",", " ").split() if item]


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


# dev | staging | prod. Anything but exactly `dev` counts as deployed: it switches on the SECRET_KEY
# requirement below, the real-SMTP mail defaults, the TLS-proxy warning (selahcue_accounts.W002) and
# the refusal of eager Celery in prod. It does not touch DEBUG, and it gates no error monitoring:
# nothing in this repo consumes SENTRY_DSN (see the end of this file).
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

# `DEBUG=1` / `DEBUG=0`, the house convention. env_bool also accepts true/yes/on.
DEBUG = env_bool("DEBUG", False)

# Required outside dev. yharah raises unconditionally, but SelahCue's tests run bare (no
# container env), so the hard requirement is scoped to non-dev — still stricter than the
# previous silent insecure default, which would have shipped to production unnoticed.
#
# Two public values must never be a deployed key (17tnw2b9ab0). The dev key is in this repository,
# and it is the signing key and the HMAC pepper for licence-key, device-token and account-session
# fingerprints. The placeholder is the example value implementation/api/.env.sample used to carry;
# `make up` copies that file to `.env` and its own header says to copy it, so copies of the old one
# are out there. So outside `dev` the key must be neither missing nor one of those, whether it got
# there by being unset or by being set to one, and however the value was spelled: in matching
# quotes, re-cased, or carrying a byte-order mark, a zero-width character or stray whitespace from
# a copy-paste (`_normalised_secret`). "Outside dev" means ENVIRONMENT is anything but exactly
# `dev`, so a typo or a different spelling ('Dev', 'production') fails closed instead of quietly
# running as dev.
#
# Deliberately NOT here: a minimum length or an entropy test. Several suites boot prod with a
# one-character key on purpose, and a length rule is not what this guards (a short key is weak, a
# PUBLIC key is forgeable by anyone who has read the repository). Django's own `check --deploy`
# warns about a weak key (security.W009), but nothing in this repo, in CI or in the Dockerfile runs
# `check --deploy`, so a weak key is not caught automatically anywhere today. Adopting that check
# or its thresholds is a possible follow-up.
#
# What this does NOT cover: an environment that never sets ENVIRONMENT IS `dev`, so it starts
# without complaint, on the dev key. That is why docs/ops/DEPLOYMENT.md and deployments.md list
# ENVIRONMENT first in "Prod must-set" and say so.
_DEV_SECRET_KEY = "selahcue-dev-only-insecure-key"
_PUBLIC_SECRET_KEYS = frozenset({_DEV_SECRET_KEY, "replace-me-with-a-fresh-key"})


def _normalised_secret(value: str) -> str:
    """`value` as a comparison would see it through the noise a pasted key picks up: invisible
    format characters removed (a byte-order mark, zero-width spaces and joiners, soft hyphens:
    Unicode category Cf), whitespace stripped, matched ASCII quotes (' or ") stripped from the
    ends, case folded. Nothing else is normalised: other punctuation, other kinds of invisible
    character and look-alike letters are not. Only ever used to COMPARE; the key Django uses is
    the configured value, untouched."""
    value = "".join(char for char in value if unicodedata.category(char) != "Cf").strip()
    while len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value.casefold()


SECRET_KEY = os.getenv("SECRET_KEY", "")
if ENVIRONMENT != "dev":
    _normalised_secret_key = _normalised_secret(SECRET_KEY)
    if not _normalised_secret_key:
        raise ImproperlyConfigured(
            f"SECRET_KEY must be set when ENVIRONMENT={ENVIRONMENT!r}."
        )
    if _normalised_secret_key in _PUBLIC_SECRET_KEYS:
        raise ImproperlyConfigured(
            "SECRET_KEY must not be a public example value (the development key, or the "
            f"old placeholder from .env.sample) when ENVIRONMENT={ENVIRONMENT!r}: those are in the "
            "repository, so anyone can forge what they sign. Set SECRET_KEY to a fresh random value."
        )
    # A lower-cased copy of the live key must not stay behind as a module global.
    del _normalised_secret_key
elif not SECRET_KEY:
    SECRET_KEY = _DEV_SECRET_KEY

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost 127.0.0.1 testserver")

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

# --- Behind a TLS-terminating proxy (17tnw2b1wtr) ---------------------------------------------
# In production TLS ends at the edge (Cloudflare / Coolify's proxy, then the marketing nginx)
# and Django receives plain HTTP, so `request.is_secure()` is False for every request. Two
# things then break without any error at boot: CsrfViewMiddleware compares a browser's
# `Origin: https://<host>` with `http://<host>` and 403s every account/admin mutation, and
# SecurityMiddleware never emits Strict-Transport-Security (it only does so over a secure
# request, so the SECURE_HSTS_* values above are dead).
#
# OPT-IN, DEFAULT OFF, because the fix is a trust decision. `X-Forwarded-Proto` is a request
# header: a client that reaches Django without passing through a proxy that OVERWRITES it can
# send `https` and be believed. Set `SELAHCUE_TRUST_FORWARDED_PROTO=1` only in an environment
# where every path to Django goes through such a proxy (docs/ops/DEPLOYMENT.md section 6c). It
# is deliberately separate from SELAHCUE_TRUSTED_PROXY_COUNT below: that setting is about how
# many X-Forwarded-For entries to believe, this one is about a different header, and setting
# the first must not silently decide the second.
SELAHCUE_TRUST_FORWARDED_PROTO = env_bool("SELAHCUE_TRUST_FORWARDED_PROTO", False)
if SELAHCUE_TRUST_FORWARDED_PROTO:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    SECURE_PROXY_SSL_HEADER = None


def _without_credentials(entry: str) -> str:
    """`entry` safe to print: anything before the last `@` (the userinfo of a pasted
    `https://user:secret@host`) is replaced with `***`, keeping a leading `scheme://`. A refusal
    message ends up in logs and terminals, so it must never echo a password."""
    head, at, tail = entry.rpartition("@")
    if not at:
        return entry
    scheme, sep, _ = head.partition("://")
    return f"{scheme}://***@{tail}" if sep else f"***@{tail}"


def _exact_origin(name: str, entry: str, debug: bool) -> str:
    """One `scheme://host[:port]` origin from the environment, or a refusal to boot.

    A trusted origin is a cross-origin trust grant on the CSRF-enforced surfaces, and the only
    value anyone should ever need here is the SPA's own public origin. So the entry must be that
    shape exactly: `https` (`http` only under DEBUG, for a local proxy), a host, an optional
    port, and nothing else. One trailing `/` is forgiven (a browser's Origin never has a path, so
    `https://x/` could never match and would fail closed with no hint). The host is lowercased,
    because browsers send it lowercase and Django compares the strings exactly.

    Refused outright, each for a reason:
    - wildcards: `https://*.example.com` would admit every subdomain AND the apex;
    - a host with a leading dot (`https://.example.com`, `https://.com`): Django's Referer
      fallback reads it as 'this domain and every subdomain', i.e. a wildcard in disguise, so
      an attacker's page on any subdomain would pass the check; and an empty label (`a..b`) or a
      trailing dot, which no browser Origin contains;
    - the default port (`:443` on https, `:80` on http) and port 0: a browser omits the default
      port from its Origin and never uses port 0, so the entry could never match and would fail
      closed with no hint (the entry is refused rather than silently rewritten);
    - a backslash anywhere, and a non-ASCII host (use the punycode `xn--` form, which is what
      a browser sends): URL parsers disagree about both;
    - credentials, path, query and fragment.
    The refusal message never echoes credentials (`_without_credentials`)."""
    shown = _without_credentials(entry)

    def refuse(reason: str):
        raise ImproperlyConfigured(
            f"{name} entry {shown!r} is not accepted: {reason}. Each entry must be an exact "
            "origin, scheme://host[:port] with no path, query or wildcard "
            "(for example 'https://selahcue.example'); see docs/ops/DEPLOYMENT.md section 6c."
        ) from None

    candidate = entry[:-1] if entry.endswith("/") else entry
    if "\\" in entry:
        refuse("it contains a backslash")
    if not entry.isascii():
        refuse("it contains non-ASCII characters; use the punycode (xn--) form of the host")
    if "*" in candidate:
        refuse("wildcards are not allowed, list each origin")
    try:
        parts = urlsplit(candidate)
        port = parts.port
    except ValueError:
        refuse("it is not a valid URL")
    allowed = ("https", "http") if debug else ("https",)
    if parts.scheme not in allowed:
        refuse(f"the scheme must be {' or '.join(allowed)}")
    host = parts.hostname
    if not host:
        refuse("it has no host")
    if "@" in parts.netloc:
        refuse("it must not carry credentials")
    if host.startswith(".") or host.endswith(".") or ".." in host:
        refuse(
            "the host must not start or end with a dot or contain an empty label "
            "(a leading dot is read by Django as 'every subdomain')"
        )
    if parts.path or parts.query or parts.fragment:
        refuse("it must not have a path, query or fragment")
    if port == 0:
        refuse("port 0 is not valid")
    if port == {"https": 443, "http": 80}[parts.scheme]:
        refuse(
            f"the default port :{port} is never part of a browser Origin, so this could never "
            f"match; write the origin without ':{port}'"
        )
    return f"{parts.scheme}://{parts.netloc.lower()}"


def _csrf_trusted_origins(name: str, debug: bool) -> list[str]:
    """Validated, de-duplicated origins from the space- or comma-separated variable `name`,
    in the order given. Empty entries (a stray comma, a trailing space) are dropped."""
    origins: list[str] = []
    for entry in env_list(name):
        origin = _exact_origin(name, entry, debug)
        if origin not in origins:
            origins.append(origin)
    return origins


# Public origins (scheme included, e.g. `https://selahcue.example`) whose browsers may POST to
# the CSRF-enforced surfaces. Needed only when the Origin a browser sends differs from
# `<scheme>://<Host header>`, i.e. when the proxy does not forward the public Host (nginx's
# `$host` also drops a non-default port). Empty by default: an entry here is a cross-origin trust
# grant, so list only the SPA's own origin. Validated at boot by `_exact_origin` above.
CSRF_TRUSTED_ORIGINS = _csrf_trusted_origins("DJANGO_CSRF_TRUSTED_ORIGINS", DEBUG)

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


# The accepted range for the two cache socket timeouts, in seconds, both ends inclusive. A
# value outside it refuses to boot. Each end is chosen to catch a distinct, plausible typo that
# would otherwise switch the throttle's protection off while the app boots and looks healthy:
#
# FLOOR 0.05. A healthy Redis answered single commands in 2.6-5.5 ms at p99.9 and 26 ms at worst
# in the PR #186 performance review (shared machine, load 7-14, through Docker Desktop), so 50 ms
# is about twice the worst healthy sample. Below it, working calls start timing out and the
# limiter fails open for no fault of Redis's (`0.001` and `1e-9` do exactly that); `0` is not even
# a timeout to redis-py, it is non-blocking mode.
#
# CEILING 10. A request spends up to nine commands on password-reset and resend (and three more
# on a fresh connection), and each can wait the full timeout on a slow-but-answering Redis, so the
# ceiling is 90-120 s per request. Anything bigger is the unbounded wait this setting exists to
# remove: `86400` is 24 hours, `500` (milliseconds typed as seconds) holds a request for minutes
# on a stall, and values from about 9.2e9 up (`1e10`, `1e308`) are rejected by Python's socket
# layer with an OverflowError that is not an OSError, so every cache call fails and the throttle
# fails open forever, with only the once-a-minute warning to show for it.
_SOCKET_TIMEOUT_MIN_SECONDS = 0.05
_SOCKET_TIMEOUT_MAX_SECONDS = 10.0


def _socket_timeout_seconds(name: str, default: str) -> float:
    """Seconds from the environment, within `[_SOCKET_TIMEOUT_MIN_SECONDS,
    _SOCKET_TIMEOUT_MAX_SECONDS]`, or the default when the variable is unset or blank. Anything
    else — out of range, not a number, `nan`, `inf` — refuses to boot.

    Strict on purpose, because this knob guards the throttle's fail-open path and its wrong
    values are not harmless (see the range comment above for each one). A deploy should find out
    now, from a startup error that names the variable, not under load from a once-a-minute log
    line. Written as `not (MIN <= value <= MAX)` so `nan` (every comparison false) and `inf` are
    refused by the same test, with no separate finiteness check.
    """
    raw = (os.getenv(name) or "").strip() or default
    try:
        value = float(raw)
    except ValueError:
        value = None
    if value is None or not (_SOCKET_TIMEOUT_MIN_SECONDS <= value <= _SOCKET_TIMEOUT_MAX_SECONDS):
        raise ImproperlyConfigured(
            f"{name} must be a number of seconds from {_SOCKET_TIMEOUT_MIN_SECONDS:g} to "
            f"{_SOCKET_TIMEOUT_MAX_SECONDS:g} (got {raw!r}). It bounds how long a stalled cache "
            "store can hold a request; see docs/ops/DEPLOYMENT.md §6b."
        )
    return value


# A Redis that is UP but WEDGED accepts the connection and never answers (17tnw2b1wrx). redis-py
# has no socket timeout by default, so every cache call blocked until Redis recovered (this repo
# configures no request timeout of its own) and the throttle's fail-open path — which only runs
# when the store RAISES — never ran: a cache fault became a full API outage. These two bound it.
# A call that runs past either one raises, `evaluate_budget` reads that as "store unavailable",
# and the request proceeds exactly as it does for a store that is down (degraded send ceilings
# and the outage warning included).
#
# 0.5s: a healthy Redis answers a single command in a few milliseconds (26 ms at worst in the
# PR #186 performance review), so this is at least 19x the worst healthy sample.
#
# WHAT A BAD REDIS COSTS A REQUEST. The timeout applies to each COMMAND, not to each budget. A
# budget is up to three commands (SET NX, then EXISTS and INCR once the key exists; rarely an
# EXPIRE more, when a window lapses mid-call) and a new connection adds three more (two CLIENT
# SETINFO and a SELECT), all under the READ timeout. A route spends one budget (/v1
# routes, verifyEmail, confirmPasswordReset) or three (requestPasswordReset, resendVerification).
# - A HARD stall (nothing answers): the first command of each budget times out and the rest of
#   that budget is skipped, so the cost is about one timeout per budget: 0.5 s, or 1.5 s on the
#   three-budget routes. Measured on a frozen Redis.
# - A SLOW Redis (every reply a little under the timeout): nothing times out, nothing fails open,
#   and the cost is nearly the timeout PER COMMAND: about 1.5 s per budget, 4.5 s on the
#   three-budget routes, and 1.5 s more when the connection has to be reopened. Measured with a
#   proxy that answers every command 0.4 s late (about 0.8 of those maxima): 1.21 s for one
#   steady budget, 3.64 s for three, and 1.69 s for the FIRST call on a fresh connection.
# It is a ceiling, not a retry: redis-py 6.4's default connection policy retries nothing for a
# stalled call, and tests/test_cache_socket_timeouts.py asserts a stalled call opens exactly one
# connection, so a client change that makes a stalled call reconnect fails it rather than
# silently multiplying the stall.
# Raising these buys tolerance of a slow-but-working Redis at the cost of every figure above:
# keep timeout x commands-per-request below any request timeout in front of this service.
CACHE_SOCKET_CONNECT_TIMEOUT = _socket_timeout_seconds("CACHE_SOCKET_CONNECT_TIMEOUT", "0.5")
CACHE_SOCKET_TIMEOUT = _socket_timeout_seconds("CACHE_SOCKET_TIMEOUT", "0.5")


def _cache_config(url: str, connect_timeout: float, socket_timeout: float) -> dict:
    """The default cache: Redis (with bounded socket timeouts) when `url` is set, else the
    per-process LocMemCache. LocMem never blocks on I/O, so it needs no timeouts. A function so
    tests can aim the identical configuration at a stalled stub."""
    if not url:
        return {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "selahcue"}
    return {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": url,
        # Django forwards OPTIONS to `redis.ConnectionPool.from_url(url, **OPTIONS)`.
        "OPTIONS": {
            "socket_connect_timeout": connect_timeout,
            "socket_timeout": socket_timeout,
        },
    }


CACHES = {
    "default": _cache_config(_cache_url, CACHE_SOCKET_CONNECT_TIMEOUT, CACHE_SOCKET_TIMEOUT)
}

# 0 = trust REMOTE_ADDR only. Raise to the number of proxies in front of Django BEFORE
# relying on X-Forwarded-For — a caller-supplied header is otherwise a limiter bypass.
SELAHCUE_TRUSTED_PROXY_COUNT = int(os.getenv("SELAHCUE_TRUSTED_PROXY_COUNT", "0"))

# (limit, window_seconds) per client IP. Activation is the expensive one — it runs
# `make_password` against the enrollment key — so it gets the tighter budget.
SELAHCUE_THROTTLE_ACTIVATION = (10, 60)
SELAHCUE_THROTTLE_DEVICE_READ = (60, 60)
# Native sign-in (`POST /v1/sessions`, 86ak5t1gw), per client IP. It runs `check_password`
# against the account hash, so it gets the activation budget. This is the app-level per-IP
# limit the browser login mutation does not have (that one relies on the edge); the durable
# per-account lockout in `login` applies to both.
SELAHCUE_THROTTLE_SESSION_LOGIN = (10, 60)

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

# Per-staff-actor budget for the admin licence-lifecycle mutations (86ak5mn0c, FR-539):
# `adminSuspendLicenseKey` and `adminReinstateLicenseKey` share ONE bucket, and the sibling
# lifecycle mutations (revoke / extend / convert / archive) are meant to draw on it too.
# The identity is the AUTHENTICATED staff actor, never the client IP: these sit behind the
# staff gate, so the thing worth bounding is one account (or one stolen staff credential)
# hammering licence state, and an IP key would let a whole support floor behind one NAT
# throttle each other. 30 a minute is far above a human working a queue of billing holds and
# far below a script. Fails OPEN when the cache is down, like every budget in this file.
SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE = (30, 60)

# How many "you were refused" audit rows the revoke / extend permission gate may write
# (86ak1090r). A caller who is identified but not permitted gets PERMISSION_DENIED and an audit
# row, so an investigator can see the attempt; without a cap that path would be a free way to
# grow the audit table. Per identity, and one global cap across all identities, because actor
# ids are free to vary on the dev header bridge. Past a cap the call is STILL refused; it just
# stops writing rows. Fails open when the cache is down (the row is written: auditing is the
# safe side to err on).
SELAHCUE_THROTTLE_ADMIN_LICENSE_REFUSAL_AUDIT = (5, 60)
SELAHCUE_THROTTLE_ADMIN_LICENSE_REFUSAL_AUDIT_GLOBAL = (100, 60)

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
# Read and kept here, but NOT consumed: no Sentry SDK is installed or initialised anywhere in this
# repo, so setting SENTRY_DSN changes nothing today (docs/ops/DEPLOYMENT.md section 6b says the same).
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
