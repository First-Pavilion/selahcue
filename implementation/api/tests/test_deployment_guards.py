"""Configuration that must not be able to go silently wrong in production.

Both guards here exist because the failure they prevent is invisible at runtime: the service
starts, serves traffic, and behaves incorrectly for everyone.
"""

import importlib.util
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from envscan import settings_env_names

from selahcue_api.apps.accounts.checks import (
    INERT_CORS_WARNING,
    UNTRUSTED_PROXY_PROTO_WARNING,
    cors_allowed_origins_has_no_middleware,
    forwarded_proto_is_trusted_behind_a_tls_proxy,
)
from selahcue_api.apps.throttling.checks import (
    SHARED_BUCKET_WARNING,
    trusted_proxy_count_is_set_behind_a_proxy,
)

# tests/conftest.py snapshots the migration-installed catalogue in a session fixture that needs the
# test database, and pytest-django only builds it when a selected test is marked. Without this the
# file errors in setup when run on its own (`pytest tests/test_deployment_guards.py`). Same
# arrangement as tests/test_nginx_forwarded_proto.py.
pytestmark = pytest.mark.django_db

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


def _environment(env_overrides):
    """The child process environment: ours MINUS every variable settings.py reads, then each
    override applied (None leaves it unset, which is not the same as empty).

    Clearing them all is what makes a case mean what it says. CI's api job exports SQL_ENGINE,
    CACHE_URL and CELERY_BROKER_URL, a developer's shell may export DEBUG=1 or
    CELERY_TASK_ALWAYS_EAGER=1, and any of them would otherwise leak into a case that never
    mentioned it. The list is derived from settings.py by the same extractor the docs drift test
    uses, so it cannot go stale when a variable is added."""
    cleared = settings_env_names()
    env = {name: value for name, value in os.environ.items() if name not in cleared}
    for name, value in env_overrides.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    # The suite itself may run under an eager/settings env; start from a clean slate.
    env.pop("DJANGO_SETTINGS_MODULE", None)
    return env


def _run_check(**env_overrides):
    env = _environment(env_overrides)
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


# --- accounts W002: deployed, but Django was not told it is behind a TLS proxy ---------------
PROXY_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


@pytest.mark.parametrize("environment", ["staging", "prod"])
def test_untrusted_proxy_proto_warning_fires_in_a_deployed_environment(settings, environment):
    """17tnw2b1wtr: a deployed process that never opted in sees every request as plain http, so
    a browser's https Origin fails CSRF and HSTS is never sent, with nothing said at boot."""
    settings.DEBUG = False
    settings.ENVIRONMENT = environment
    settings.SECURE_PROXY_SSL_HEADER = None

    issues = forwarded_proto_is_trusted_behind_a_tls_proxy(None)

    assert [issue.id for issue in issues] == [UNTRUSTED_PROXY_PROTO_WARNING]
    # The id is part of the operator-facing contract (docs/ops/DEPLOYMENT.md names it, and
    # SILENCED_SYSTEM_CHECKS takes it), so pin the literal rather than the constant, and keep the
    # id the hint tells people to silence in step with the id the warning carries.
    assert issues[0].id == "selahcue_accounts.W002"
    assert issues[0].id in issues[0].hint
    # A Warning, not an Error: Django may terminate TLS itself, and the failure is closed.
    assert issues[0].level < 40, "an Error here would fail every non-dev `manage.py check`"
    assert "docs/ops/DEPLOYMENT.md section 6c" in issues[0].hint
    assert "SELAHCUE_TRUST_FORWARDED_PROTO" in issues[0].msg


def test_untrusted_proxy_proto_warning_is_silent_once_opted_in(settings):
    settings.DEBUG = False
    settings.ENVIRONMENT = "prod"
    settings.SECURE_PROXY_SSL_HEADER = PROXY_HEADER
    assert forwarded_proto_is_trusted_behind_a_tls_proxy(None) == []


def test_untrusted_proxy_proto_warning_is_silent_in_dev_and_under_debug(settings):
    """CI, a bare `pytest` and the compose stack run with ENVIRONMENT=dev and must stay clean;
    DEBUG is a developer's own machine whatever ENVIRONMENT says."""
    settings.SECURE_PROXY_SSL_HEADER = None

    settings.DEBUG = False
    settings.ENVIRONMENT = "dev"
    assert forwarded_proto_is_trusted_behind_a_tls_proxy(None) == []

    settings.DEBUG = True
    settings.ENVIRONMENT = "prod"
    assert forwarded_proto_is_trusted_behind_a_tls_proxy(None) == []


# --- SECRET_KEY: a public value must never sign anything outside `dev` (17tnw2b9ab0) -------------
# The dev key is in this repository, and it is the HMAC pepper for licence-key, device-token and
# account-session fingerprints. The `replace-me-with-a-fresh-key` placeholder is what
# implementation/api/.env.sample used to carry, and that file is what `make up` copies to `.env`
# (and what its own header tells people to copy), so copies of the old one are out there. Both are
# public, so neither may be a deployed key, however it is spelled: quoted, re-cased, or carrying a
# byte-order mark or a zero-width character from a copy-paste. The refusal is an import-time check
# in settings.py, so the matrix below executes a FRESH copy of that file under a controlled
# environment (fast, and it never touches the `django.conf.settings` the rest of the suite is
# using), and a few cases go through `manage.py check` in a child process to prove the real entry
# point refuses too.
#
# HERMETIC. `_fresh_settings` clears every variable settings.py reads before it applies a case, so
# a value the machine running the suite exports (CI exports SQL_ENGINE, a developer may export
# DEBUG=1) cannot change an outcome. Run the file with those exported to see it.
DEV_SECRET_KEY = "selahcue-dev-only-insecure-key"
SAMPLE_PLACEHOLDER = "replace-me-with-a-fresh-key"
SETTINGS_FILE = API_ROOT / "selahcue_api" / "settings.py"
# Built with chr() rather than typed: an invisible character in a source file is exactly what
# this test is about, and it must not depend on how an editor or a tool treats the file.
BOM = chr(0xFEFF)
ZERO_WIDTH_SPACE = chr(0x200B)
ZERO_WIDTH_JOINER = chr(0x200D)
NO_BREAK_SPACE = chr(0xA0)


def _fresh_settings(monkeypatch, **env):
    """Execute a new copy of settings.py with exactly `env` for the variables it names (None
    unsets one) and every other variable it reads cleared. Raises whatever settings.py raises."""
    for name in settings_env_names():
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location("_settings_under_test", SETTINGS_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REFUSED_KEYS = [
    pytest.param(None, id="unset"),
    pytest.param("", id="empty"),
    pytest.param("   ", id="blank"),
    pytest.param(BOM + ZERO_WIDTH_SPACE, id="only-invisible-characters"),
    pytest.param('""', id="only-quotes"),
    pytest.param(DEV_SECRET_KEY, id="the-dev-key"),
    pytest.param(f"  {DEV_SECRET_KEY}\n", id="the-dev-key-with-whitespace"),
    pytest.param(f'"{DEV_SECRET_KEY}"', id="the-dev-key-in-double-quotes"),
    pytest.param(f"'{DEV_SECRET_KEY}'", id="the-dev-key-in-single-quotes"),
    pytest.param(f' "{DEV_SECRET_KEY}" ', id="the-dev-key-in-quotes-with-whitespace"),
    pytest.param(DEV_SECRET_KEY.upper(), id="the-dev-key-upper-case"),
    pytest.param(DEV_SECRET_KEY.title(), id="the-dev-key-title-case"),
    pytest.param(BOM + DEV_SECRET_KEY, id="the-dev-key-after-a-bom"),
    pytest.param(DEV_SECRET_KEY + ZERO_WIDTH_SPACE, id="the-dev-key-before-a-zero-width-space"),
    pytest.param(
        DEV_SECRET_KEY[:10] + ZERO_WIDTH_JOINER + DEV_SECRET_KEY[10:], id="the-dev-key-split-by-a-zero-width-joiner"
    ),
    pytest.param(NO_BREAK_SPACE + DEV_SECRET_KEY, id="the-dev-key-after-a-no-break-space"),
    pytest.param(SAMPLE_PLACEHOLDER, id="the-env-sample-placeholder"),
    pytest.param(f'"{SAMPLE_PLACEHOLDER}"', id="the-placeholder-in-quotes"),
    pytest.param(SAMPLE_PLACEHOLDER.upper(), id="the-placeholder-upper-case"),
    pytest.param(BOM + SAMPLE_PLACEHOLDER, id="the-placeholder-after-a-bom"),
]

# The key matrix runs under `prod` only. Inside the `!= "dev"` branch of settings.py the environment
# value feeds nothing but the message, so repeating all twenty keys per spelling would multiply the
# cases (each one executes settings.py afresh) without being able to catch anything new. What the
# environment CAN change is whether the branch is entered at all, so each spelling below gets the
# two cases that exercise both refusals (no key, and a public key).
DEPLOYED_ENVIRONMENTS = [
    pytest.param("prod", id="prod"),
    pytest.param("staging", id="staging"),
    pytest.param("production", id="an-unlisted-spelling"),
    pytest.param("Dev", id="a-near-miss-of-dev"),
    pytest.param("", id="empty"),
]
OTHER_THAN_PROD = DEPLOYED_ENVIRONMENTS[1:]


# The later owner instruction on 17tnw2b9d9z covers EVERY non-dev environment,
# superseding the original description's explicit ingress opt-in.
@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("flag", ["DEBUG", "SELAHCUE_TRUST_ACTOR_HEADERS"])
@pytest.mark.parametrize("value", ["1", "true", "yes", " ON "])
def test_non_dev_refuses_debug_and_actor_header_trust(monkeypatch, environment, flag, value):
    with pytest.raises(ImproperlyConfigured) as refusal:
        _fresh_settings(monkeypatch, ENVIRONMENT=environment, SECRET_KEY="non-public-test-key", **{flag: value})
    assert flag in str(refusal.value)
    assert f"ENVIRONMENT={environment!r}" in str(refusal.value)


@pytest.mark.parametrize("environment", DEPLOYED_ENVIRONMENTS)
@pytest.mark.parametrize("value", [None, "", "0", "false", "no", "off"])
def test_non_dev_boots_with_debug_and_actor_header_trust_disabled(monkeypatch, environment, value):
    module = _fresh_settings(
        monkeypatch,
        ENVIRONMENT=environment,
        SECRET_KEY="non-public-test-key",
        DEBUG=value,
        SELAHCUE_TRUST_ACTOR_HEADERS=value,
    )
    assert module.DEBUG is False
    assert module.SELAHCUE_TRUST_ACTOR_HEADERS is False


@pytest.mark.parametrize(
    "debug,trust,expected",
    [
        (None, None, False),
        ("0", None, False),
        ("1", None, True),
        ("1", "0", False),
        ("0", "1", True),
        ("yes", "on", True),
    ],
)
def test_dev_keeps_debug_default_and_explicit_actor_header_controls(monkeypatch, debug, trust, expected):
    module = _fresh_settings(monkeypatch, ENVIRONMENT="dev", DEBUG=debug, SELAHCUE_TRUST_ACTOR_HEADERS=trust)
    assert module.DEBUG is (debug in {"1", "yes"})
    assert module.SELAHCUE_TRUST_ACTOR_HEADERS is expected


def _assert_refused(monkeypatch, environment, secret_key):
    with pytest.raises(ImproperlyConfigured) as refusal:
        _fresh_settings(monkeypatch, ENVIRONMENT=environment, SECRET_KEY=secret_key)
    message = str(refusal.value)
    assert "SECRET_KEY" in message
    assert f"ENVIRONMENT={environment!r}" in message
    if secret_key and secret_key.strip():
        # The message is built from fixed text; echoing the configured value would put a key in
        # logs. (The public values are public, but the rule is the same for every value.)
        assert secret_key not in message
        assert secret_key.upper() not in message and secret_key.lower() not in message


@pytest.mark.parametrize("secret_key", REFUSED_KEYS)
def test_settings_refuse_in_prod_without_a_real_secret_key(monkeypatch, secret_key):
    """In a deployed environment the key must be neither missing nor a public value, however the
    value is spelled. The message has to name SECRET_KEY and ENVIRONMENT, because the operator
    reading it needs the variables to fix, and it must never contain what was configured."""
    _assert_refused(monkeypatch, "prod", secret_key)


@pytest.mark.parametrize("environment", OTHER_THAN_PROD)
@pytest.mark.parametrize(
    "secret_key", [pytest.param(None, id="no-key"), pytest.param(DEV_SECRET_KEY, id="the-dev-key")]
)
def test_settings_treat_every_environment_but_exactly_dev_as_deployed(monkeypatch, environment, secret_key):
    """Any ENVIRONMENT other than exactly `dev` is deployed, so a typo or a different spelling
    fails closed instead of quietly running as dev. A guard written as `ENVIRONMENT == "prod"`
    passes the `prod` cases above and fails these."""
    _assert_refused(monkeypatch, environment, secret_key)


# Obviously fake, on purpose: a realistic-looking random key in a source file is what a secret
# scanner flags. The runtime-generated case is `test_a_generated_key_boots_outside_dev` below.
REAL_KEYS = [
    pytest.param("x", id="a-one-character-key"),
    pytest.param("a-real-key-" + "x" * 40, id="a-long-plain-key"),
    pytest.param("fake-test-key-" + "0123456789abcdef" * 4, id="a-64-character-fake-key"),
    pytest.param(DEV_SECRET_KEY + "-but-longer", id="the-dev-key-with-a-suffix"),
    pytest.param("not-" + SAMPLE_PLACEHOLDER, id="the-placeholder-with-a-prefix"),
]


@pytest.mark.parametrize("secret_key", REAL_KEYS)
def test_settings_accept_a_real_secret_key_in_prod(monkeypatch, secret_key):
    """The positive control for the matrix above: it stops the public values, not deployment, and
    not short keys (other suites deliberately boot prod with SECRET_KEY='x'). Without this, a
    guard that refused everything outside dev would pass every case there."""
    module = _fresh_settings(monkeypatch, ENVIRONMENT="prod", SECRET_KEY=secret_key)
    assert module.SECRET_KEY == secret_key
    # The comparison copy of the key (lower-cased) must not outlive the check as a module global.
    assert not [name for name in vars(module) if "normalised" in name and name != "_normalised_secret"]
    assert not [value for name, value in vars(module).items() if value == secret_key.casefold() and name != "SECRET_KEY"]


@pytest.mark.parametrize("environment", OTHER_THAN_PROD)
def test_settings_accept_a_real_secret_key_in_every_deployed_spelling(monkeypatch, environment):
    module = _fresh_settings(monkeypatch, ENVIRONMENT=environment, SECRET_KEY="a-real-key-" + "x" * 40)
    assert module.SECRET_KEY == "a-real-key-" + "x" * 40


def test_a_generated_key_boots_outside_dev(monkeypatch):
    """The key the docs tell operators to generate (`secrets.token_urlsafe(64)`)."""
    key = secrets.token_urlsafe(64)
    assert len(key) >= 80
    assert _fresh_settings(monkeypatch, ENVIRONMENT="prod", SECRET_KEY=key).SECRET_KEY == key


@pytest.mark.parametrize(
    "secret_key",
    [None, "", DEV_SECRET_KEY, SAMPLE_PLACEHOLDER],
    ids=["unset", "empty", "dev-key", "placeholder"],
)
def test_settings_allow_public_keys_inside_dev(monkeypatch, secret_key):
    """`dev` is where the public values are meant to work: a bare `pytest`, the compose stack, and
    a developer who copied .env.sample. Unset and empty fall back to the dev key."""
    module = _fresh_settings(monkeypatch, ENVIRONMENT="dev", SECRET_KEY=secret_key)
    assert module.SECRET_KEY == (secret_key or DEV_SECRET_KEY)


def test_an_unset_environment_is_dev_and_runs_on_the_public_dev_key(monkeypatch):
    """THE HAZARD the deployment docs now warn about, pinned as fact. If an operator sets only
    the names the old docs listed (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DATABASE_URL`), none of
    which is read, ENVIRONMENT stays `dev` and nothing refuses to start. When this stops being
    true (for example a deployed-host check is added) update the docs, not just this test.

    Hermetic on purpose: it asserts DEBUG is off and the engine is SQLite, which are only true
    because `_fresh_settings` cleared whatever the machine running the suite exports."""
    module = _fresh_settings(
        monkeypatch,
        ENVIRONMENT=None,
        SECRET_KEY=None,
        DJANGO_SECRET_KEY="a-key-the-old-docs-told-you-to-set",
        DJANGO_DEBUG="false",
        DATABASE_URL="postgres://user:pass@db/selahcue",
    )
    assert module.ENVIRONMENT == "dev"
    assert module.SECRET_KEY == DEV_SECRET_KEY
    assert module.DEBUG is False
    assert module.DATABASES["default"]["ENGINE"].endswith("sqlite3")


def test_the_inherited_environment_cannot_change_a_case(monkeypatch):
    """The hermeticity itself: with variables a CI runner or a developer shell would export set
    in THIS process, a case still resolves from its own inputs only."""
    monkeypatch.setenv("SQL_ENGINE", "django.db.backends.postgresql")
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "1")
    monkeypatch.setenv("SECRET_KEY", "an-inherited-key")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    module = _fresh_settings(monkeypatch, ENVIRONMENT=None, SECRET_KEY=None)
    assert module.ENVIRONMENT == "dev"
    assert module.SECRET_KEY == DEV_SECRET_KEY
    assert module.DEBUG is False
    assert module.CELERY_TASK_ALWAYS_EAGER is False
    assert module.DATABASES["default"]["ENGINE"].endswith("sqlite3")


@pytest.mark.parametrize(
    "secret_key",
    [
        pytest.param(None, id="unset"),
        pytest.param(DEV_SECRET_KEY, id="the-dev-key"),
        pytest.param(SAMPLE_PLACEHOLDER, id="the-env-sample-placeholder"),
        pytest.param(f'"{DEV_SECRET_KEY.upper()}"', id="a-quoted-upper-case-dev-key"),
    ],
)
def test_manage_py_refuses_to_start_outside_dev_without_a_real_secret_key(secret_key):
    """End to end through the real entry point, for the cases that matter most."""
    result = _run_check(ENVIRONMENT="prod", SECRET_KEY=secret_key)
    assert result.returncode != 0, f"started on SECRET_KEY={secret_key!r}: {result.stdout}"
    assert "ImproperlyConfigured" in result.stderr
    assert "SECRET_KEY" in result.stderr


def test_manage_py_still_starts_in_prod_with_a_real_secret_key():
    result = _run_check(ENVIRONMENT="prod", SECRET_KEY=secrets.token_urlsafe(64))
    assert result.returncode == 0, result.stderr
