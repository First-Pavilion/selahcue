"""Configuration that must not be able to go silently wrong in production.

Both guards here exist because the failure they prevent is invisible at runtime: the service
starts, serves traffic, and behaves incorrectly for everyone.
"""

import os
import subprocess
import sys
from pathlib import Path

from selahcue_api.apps.accounts.checks import (
    INERT_CORS_WARNING,
    cors_allowed_origins_has_no_middleware,
)
from selahcue_api.apps.throttling.checks import (
    SHARED_BUCKET_WARNING,
    trusted_proxy_count_is_set_behind_a_proxy,
)

REDIS_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://localhost:6379/1",
    }
}
LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "selahcue",
    }
}


# --- W001: everyone shares one rate-limit bucket ---------------------------
def test_shared_bucket_warning_fires_behind_a_proxy(settings):
    """Default proxy count 0 means the limiter keys on REMOTE_ADDR, which behind the
    documented Coolify/Cloudflare edge is the PROXY for every request — one 10/min activation
    bucket for the entire customer base worldwide."""
    settings.DEBUG = False
    settings.CACHES = REDIS_CACHE
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0

    issues = trusted_proxy_count_is_set_behind_a_proxy(None)
    assert [issue.id for issue in issues] == [SHARED_BUCKET_WARNING]
    # Must be a WARNING: CI runs with CACHE_URL set and DEBUG unset, and an Error would fail
    # `manage.py check` there. The hop count is a deployment decision, not a code defect.
    assert issues[0].level < 40, "an Error here would break the CI `api` job"


def test_shared_bucket_warning_is_silent_once_the_hop_count_is_set(settings):
    settings.DEBUG = False
    settings.CACHES = REDIS_CACHE
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 1
    assert trusted_proxy_count_is_set_behind_a_proxy(None) == []


def test_shared_bucket_warning_is_silent_without_a_shared_cache(settings):
    """No CACHE_URL means LocMemCache, i.e. a local dev run — not a fronted deployment."""
    settings.DEBUG = False
    settings.CACHES = LOCMEM_CACHE
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    assert trusted_proxy_count_is_set_behind_a_proxy(None) == []

    settings.DEBUG = True
    settings.CACHES = REDIS_CACHE
    assert trusted_proxy_count_is_set_behind_a_proxy(None) == []


# --- eager Celery in production -------------------------------------------
API_ROOT = Path(__file__).resolve().parent.parent


def _run_check(**env_overrides):
    env = {**os.environ, **env_overrides}
    # The suite itself may run under an eager/settings env; start from a clean slate.
    env.pop("DJANGO_SETTINGS_MODULE", None)
    return subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_eager_celery_cannot_be_switched_on_in_production():
    """Eager mode runs every task inline in the web process — SMTP back on the request path,
    which is exactly what the worker was introduced to remove. A subprocess because the guard
    is an import-time settings check, like the SECRET_KEY one it mirrors."""
    result = _run_check(ENVIRONMENT="prod", SECRET_KEY="x", CELERY_TASK_ALWAYS_EAGER="1")
    assert result.returncode != 0, result.stdout
    assert "ImproperlyConfigured" in result.stderr
    assert "CELERY_TASK_ALWAYS_EAGER" in result.stderr


def test_production_still_boots_without_eager_celery():
    """The guard must refuse only the dangerous combination, not production itself."""
    result = _run_check(ENVIRONMENT="prod", SECRET_KEY="x", CELERY_TASK_ALWAYS_EAGER="0")
    assert result.returncode == 0, result.stderr


def test_eager_celery_is_still_allowed_outside_production():
    """It stays available as the test/debug lever it is."""
    result = _run_check(ENVIRONMENT="dev", CELERY_TASK_ALWAYS_EAGER="1")
    assert result.returncode == 0, result.stderr


# --- accounts W001: a CORS allow-list that nothing enforces -----------------
def test_inert_cors_warning_fires_when_the_allow_list_is_set(settings):
    """`CORS_ALLOWED_ORIGINS` has been read from the environment since the foundation
    slice while no middleware ever consumed it. Setting it looks like configuring CORS and
    achieves nothing — the browser blocks the call and the server log says nothing."""
    settings.CORS_ALLOWED_ORIGINS = ("http://localhost:5173",)
    settings.MIDDLEWARE = [m for m in settings.MIDDLEWARE if "cors" not in m.lower()]

    issues = cors_allowed_origins_has_no_middleware(None)
    assert [issue.id for issue in issues] == [INERT_CORS_WARNING]
    # A Warning, not an Error: with no CORS headers the browser REFUSES the request, so the
    # misconfiguration fails closed. Nothing is exposed; something merely does not work.
    assert issues[0].level < 40
    # The hint has to name the same-origin arrangement, or the obvious "fix" is to install
    # corsheaders and then relax SameSite to make the cookie flow — the exact regression
    # this guard exists to prevent.
    assert "same-origin" in issues[0].hint.lower()
    assert "SameSite=Strict" in issues[0].hint


def test_inert_cors_warning_is_silent_by_default(settings):
    """The variable is unset in CI, in tests and in the compose stack, so `manage.py check`
    stays clean for everyone who has not opted in."""
    settings.CORS_ALLOWED_ORIGINS = ()
    assert cors_allowed_origins_has_no_middleware(None) == []


def test_inert_cors_warning_is_silent_once_middleware_exists(settings):
    """If CORS middleware is ever installed deliberately, the allow-list is real and the
    warning must get out of the way rather than nag forever."""
    settings.CORS_ALLOWED_ORIGINS = ("http://localhost:5173",)
    settings.MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware", *settings.MIDDLEWARE]
    assert cors_allowed_origins_has_no_middleware(None) == []


def test_the_shipped_configuration_emits_no_cors_headers(client, settings):
    """Pins the actual behaviour the warning describes, so the guard cannot drift away from
    reality: even with an allow-list set, no Access-Control-Allow-Origin comes back."""
    settings.CORS_ALLOWED_ORIGINS = ("http://localhost:5173",)
    response = client.get("/graphql/account", HTTP_ORIGIN="http://localhost:5173")
    assert "Access-Control-Allow-Origin" not in response.headers
