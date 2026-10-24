"""Django behind a TLS-terminating proxy (17tnw2b1wtr, follow-up to 86ak5t1gw).

In production TLS ends at the edge and Django sees plain HTTP. Without
`SECURE_PROXY_SSL_HEADER`, `request.is_secure()` is always False, which has two effects that
look healthy at boot and only show up in a browser:

- `CsrfViewMiddleware` compares the request's `Origin` (`https://<host>`, which is what every
  browser sends from the TLS-served SPA) to `http://<host>`, and refuses a valid, token-bearing
  mutation with 403;
- `SecurityMiddleware` never emits `Strict-Transport-Security`, because it only does so over a
  secure request.

The fix is a trust decision, so it is OPT-IN (`SELAHCUE_TRUST_FORWARDED_PROTO`, default off):
`X-Forwarded-Proto` is caller-controlled for any client that reaches Django without passing
through a proxy that overwrites it, and a forged `https` there would make Django believe the
request was secure. Both directions are pinned below.

WHAT EACH GROUP OF TESTS PROVES. The in-process browser tests inject `SECURE_PROXY_SSL_HEADER`
through the pytest `settings` fixture, so they pin DJANGO's behaviour for the header values and
origins we depend on, NOT `settings.py`. The tests that prove `settings.py` are the environment
wiring ones further down (each case boots the real settings module in a subprocess), and the
labelled acceptance test, `test_acceptance_the_environment_variable_alone_turns_the_https_flow_on`,
is the one that goes from environment variable to HTTP response. The nginx half of the chain is
pinned in `tests/test_nginx_forwarded_proto.py`; the deploy-time warning (`selahcue_accounts.W002`)
in `tests/test_deployment_guards.py` and, through `manage.py`, here; the native `/v1` routes'
independence from all of it here and in `tests/test_native_account_surface.py`.

Django's test client bypasses CSRF unless `enforce_csrf_checks=True`, so every browser-shaped
client here sets it. A FRESH client per attempt: `CsrfViewMiddleware` and `SecurityMiddleware`
read their settings once per middleware instance, i.e. once per client.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import (
    CustomerOrg,
    CustomerRole,
    CustomerUser,
    CustomerUserStatus,
)

API_ROOT = Path(__file__).resolve().parent.parent

PROXY_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
HSTS = "Strict-Transport-Security"
EXPECTED_HSTS = "max-age=31536000; includeSubDomains; preload"
W002 = "selahcue_accounts.W002"

# What a browser behind the proxy produces. The explicit Host matters: the test client otherwise
# derives one from SERVER_NAME and SERVER_PORT (80), which becomes `testserver:80` once the
# request counts as https and has nothing to do with what nginx forwards (`Host $host`).
HTTPS_VIA_PROXY = {"HTTP_X_FORWARDED_PROTO": "https", "HTTP_HOST": "testserver"}

# A query that needs no database, so the browser tests exercise only the middleware stack.
QUERY = {"query": "{ __typename }"}


@pytest.fixture(autouse=True)
def _baseline(settings):
    """Every test starts from the shipped defaults, whatever the host environment says: proxy
    header untrusted, no extra trusted origins, and the production HSTS values (`DEBUG=1` or an
    exported SELAHCUE_TRUST_FORWARDED_PROTO in a developer's shell would otherwise change them)."""
    settings.SECURE_PROXY_SSL_HEADER = None
    settings.CSRF_TRUSTED_ORIGINS = []
    settings.SECURE_HSTS_SECONDS = 31536000
    settings.SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    settings.SECURE_HSTS_PRELOAD = True


def _trust_the_proxy(settings):
    settings.SECURE_PROXY_SSL_HEADER = PROXY_HEADER


def _browser_post(client, token, **extra):
    return client.post(
        "/graphql/account",
        data=json.dumps(QUERY),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
        **extra,
    )


def _seed_token(client, **extra):
    bootstrap = client.get("/graphql/csrf", **extra)
    assert bootstrap.status_code == 200
    return bootstrap.cookies[django_settings.CSRF_COOKIE_NAME].value


def _attempt(*, origin=None, referer=None, proto="https", host="testserver"):
    """One browser-shaped POST from a fresh client with a valid CSRF token. `proto=None` sends no
    X-Forwarded-Proto at all; `origin`/`referer` None send no such header."""
    client = Client(enforce_csrf_checks=True)
    headers = {"HTTP_HOST": host}
    if proto is not None:
        headers["HTTP_X_FORWARDED_PROTO"] = proto
    token = _seed_token(client, **headers)
    if origin is not None:
        headers["HTTP_ORIGIN"] = origin
    if referer is not None:
        headers["HTTP_REFERER"] = referer
    return _browser_post(client, token, **headers)


# --- Django's behaviour once the proxy header is trusted --------------------------------------
def test_https_origin_through_a_trusted_proxy_passes_csrf_and_gets_hsts(settings):
    """A browser-shaped POST with `Origin: https://<host>`, a valid token and the proxy's
    `X-Forwarded-Proto: https` returns 200 and carries HSTS. (Django's behaviour, with the setting
    injected; the settings.py half is the acceptance test further down.)"""
    _trust_the_proxy(settings)

    response = _attempt(origin="https://testserver")

    assert response.status_code == 200
    assert response.json()["data"] == {"__typename": "AccountQuery"}
    assert response[HSTS] == EXPECTED_HSTS


def test_hsts_header_carries_the_configured_value_on_a_proxied_secure_get(settings):
    _trust_the_proxy(settings)

    response = Client().get("/graphql/csrf", **HTTPS_VIA_PROXY)

    assert response[HSTS] == EXPECTED_HSTS


def test_hsts_follows_the_configured_hsts_values_not_just_the_scheme(settings):
    """Trusting the proxy makes the request secure; HSTS then obeys the existing SECURE_HSTS_*
    values, so `SECURE_HSTS_SECONDS=0` (the DEBUG default) still switches it off."""
    _trust_the_proxy(settings)

    settings.SECURE_HSTS_SECONDS = 0
    assert HSTS not in Client().get("/graphql/csrf", **HTTPS_VIA_PROXY)

    settings.SECURE_HSTS_SECONDS = 60
    settings.SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    settings.SECURE_HSTS_PRELOAD = False
    assert Client().get("/graphql/csrf", **HTTPS_VIA_PROXY)[HSTS] == "max-age=60"


# What the forwarded-proto header may contain once the proxy is trusted, and whether Django then
# treats the request as secure. Django takes the FIRST comma-separated entry, strips surrounding
# whitespace and compares it to "https" CASE-SENSITIVELY (docs/ops/DEPLOYMENT.md section 6c states
# the same rule). nginx forwards a literal lowercase `https` or `http` (see the nginx guard); the
# cases below are for any proxy that forwards the value as received.
FORWARDED_PROTO_VALUES = [
    ("https", True),
    (" https", True),
    ("https ", True),
    (" https ", True),
    ("https, http", True),
    ("https,http", True),
    ("HTTPS", False),
    ("Https", False),
    ("http", False),
    ("http, https", False),
    ("", False),
    (" ", False),
    ("yes", False),
    ("on", False),
    ("1", False),
    ("true", False),
    ("junk", False),
    ("https://", False),
    ("wss", False),
]


@pytest.mark.parametrize(("value", "secure"), FORWARDED_PROTO_VALUES)
def test_only_an_https_first_entry_makes_a_proxied_request_secure(settings, value, secure):
    _trust_the_proxy(settings)

    plain = Client().get("/graphql/csrf", HTTP_X_FORWARDED_PROTO=value, HTTP_HOST="testserver")
    assert (HSTS in plain) is secure

    https_origin = _attempt(origin="https://testserver", proto=value)
    assert https_origin.status_code == (200 if secure else 403)

    # The control that makes the 403 above mean "treated as insecure" and nothing else: the same
    # request with the plain-http Origin is accepted exactly when the request is NOT secure.
    http_origin = _attempt(origin="http://testserver", proto=value)
    assert http_origin.status_code == (403 if secure else 200)


def test_configured_but_no_header_means_a_direct_client_cannot_claim_https(settings):
    """Even with the setting on, a request that carries no `X-Forwarded-Proto` is plain HTTP:
    the setting reads the header, it does not assume https."""
    _trust_the_proxy(settings)

    refused = _attempt(origin="https://testserver", proto=None)

    assert refused.status_code == 403
    assert HSTS not in refused
    # ...and the plain flow it falls back to still works.
    assert _attempt(origin="http://testserver", proto=None).status_code == 200


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://evil.example",
        "https://testserver.evil.example",
        "https://sub.testserver",
        "https://testserver:8443",
        "http://testserver",
        "null",
    ],
)
def test_a_foreign_or_mismatched_origin_is_still_refused_when_the_proxy_is_trusted(
    settings, origin
):
    """Trusting the scheme must not loosen the origin check itself. Only `https://testserver`
    (the forwarded scheme plus the forwarded Host) is the same origin here."""
    _trust_the_proxy(settings)

    assert _attempt(origin=origin).status_code == 403
    assert _attempt(origin="https://testserver").status_code == 200  # control: same client shape


def test_a_token_less_or_wrong_token_post_is_still_refused_when_the_proxy_is_trusted(settings):
    _trust_the_proxy(settings)

    tokenless = Client(enforce_csrf_checks=True).post(
        "/graphql/account",
        data=json.dumps(QUERY),
        content_type="application/json",
        HTTP_ORIGIN="https://testserver",
        **HTTPS_VIA_PROXY,
    )
    assert tokenless.status_code == 403

    client = Client(enforce_csrf_checks=True)
    _seed_token(client, **HTTPS_VIA_PROXY)
    wrong = _browser_post(client, "x" * 64, HTTP_ORIGIN="https://testserver", **HTTPS_VIA_PROXY)
    assert wrong.status_code == 403


def test_without_origin_or_referer_a_proxied_https_post_is_refused(settings):
    """Enabling the flag makes the request secure, and Django's CSRF check for a secure request
    with NO Origin demands a same-origin Referer. Browsers always send Origin on a POST, so the
    SPA is unaffected; a non-browser caller that sends neither header (and used to get through on
    the token alone, believed to be plain http) is refused. Pinned so the behaviour change is
    deliberate and documented (docs/ops/DEPLOYMENT.md section 6c)."""
    _trust_the_proxy(settings)

    refused = _attempt()

    assert refused.status_code == 403
    assert b"Referer" in refused.content


@pytest.mark.parametrize(
    ("referer", "status"),
    [
        ("https://testserver/", 200),
        ("https://testserver/account/signin?next=%2F", 200),
        ("https://evil.example/", 403),
        ("https://testserver.evil.example/", 403),
        ("http://testserver/", 403),  # an insecure Referer on a secure request
        ("not a url", 403),
    ],
)
def test_the_referer_fallback_when_there_is_no_origin(settings, referer, status):
    _trust_the_proxy(settings)

    assert _attempt(referer=referer).status_code == status


# --- the default deployment: header NOT trusted -----------------------------------------------
@pytest.mark.parametrize("forged", ["https", "HTTPS", "https, http", " https", "http"])
def test_a_forged_forwarded_proto_is_ignored_when_the_setting_is_off(settings, forged):
    """The shipped default. A client that reaches Django directly and sends
    `X-Forwarded-Proto: https` must not be believed: the https Origin stays refused and no
    HSTS is emitted, exactly as before the setting existed."""
    assert settings.SECURE_PROXY_SSL_HEADER is None

    refused = _attempt(origin="https://testserver", proto=forged)

    assert refused.status_code == 403
    assert HSTS not in refused
    assert HSTS not in Client().get(
        "/graphql/csrf", HTTP_X_FORWARDED_PROTO=forged, HTTP_HOST="testserver"
    )


def test_an_https_origin_without_the_header_behaves_as_before_when_the_setting_is_off():
    """The ticket's second acceptance criterion: no forwarded-proto header, setting off."""
    refused = _attempt(origin="https://testserver", proto=None)

    assert refused.status_code == 403
    assert HSTS not in refused


def test_local_development_without_a_proxy_is_unchanged():
    """No proxy, no header: the pre-existing flow still works end to end, with the http Origin
    a local browser sends and also with neither Origin nor Referer (the token alone suffices over
    plain http, which is what a script or the existing suite relies on)."""
    with_origin = _attempt(origin="http://testserver", proto=None)
    assert with_origin.status_code == 200
    assert HSTS not in with_origin

    bare = _attempt(proto=None)
    assert bare.status_code == 200
    assert HSTS not in bare


# --- HSTS only when the proxy header is honoured ----------------------------------------------
@pytest.mark.parametrize(
    ("trusted", "header", "emitted"),
    [
        (True, "https", True),
        (True, "http", False),
        (True, "", False),
        (True, None, False),
        (False, "https", False),
        (False, "http", False),
        (False, None, False),
    ],
)
def test_hsts_is_emitted_only_when_the_proxy_header_is_trusted_and_says_https(
    settings, trusted, header, emitted
):
    if trusted:
        _trust_the_proxy(settings)
    extra = {"HTTP_HOST": "testserver"}
    if header is not None:
        extra["HTTP_X_FORWARDED_PROTO"] = header

    response = Client().get("/graphql/csrf", **extra)

    assert (HSTS in response) is emitted


# --- CSRF_TRUSTED_ORIGINS in the request path -------------------------------------------------
def test_a_public_origin_that_differs_from_the_host_needs_csrf_trusted_origins(settings):
    """Origin `https://app.example.com` against a Host of `testserver` (a proxy that rewrites
    Host to an internal name). It is refused until the public origin is listed, listing it admits
    ONLY that origin, and the proxy header decides whether HSTS comes back:

    - trusted proxy, not listed: 403;
    - trusted proxy, listed: 200 and HSTS;
    - NO trusted proxy, listed: 200 but no HSTS (the list alone fixes CSRF; only the proxy header
      fixes HSTS), so this test fails if the proxy header stops being honoured;
    - trusted proxy, a different origin requested: 403."""
    origin = "https://app.example.com"

    _trust_the_proxy(settings)
    assert _attempt(origin=origin).status_code == 403

    settings.CSRF_TRUSTED_ORIGINS = [origin]
    listed = _attempt(origin=origin)
    assert listed.status_code == 200
    assert listed[HSTS] == EXPECTED_HSTS
    assert _attempt(origin="https://other.example.com").status_code == 403

    settings.SECURE_PROXY_SSL_HEADER = None
    listed_without_proxy = _attempt(origin=origin)
    assert listed_without_proxy.status_code == 200
    assert HSTS not in listed_without_proxy


def test_a_listed_origin_does_not_admit_a_different_scheme_or_port(settings):
    _trust_the_proxy(settings)
    settings.CSRF_TRUSTED_ORIGINS = ["https://app.example.com"]

    assert _attempt(origin="https://app.example.com").status_code == 200
    assert _attempt(origin="http://app.example.com").status_code == 403
    assert _attempt(origin="https://app.example.com:8443").status_code == 403
    assert _attempt(origin="https://app.example.com.evil.example").status_code == 403


def test_django_reads_a_leading_dot_trusted_origin_as_every_subdomain(settings):
    """WHY settings.py refuses `https://.example.com`: injected directly (the validator would
    stop it at boot), Django's Referer fallback treats the leading-dot host as 'this domain and
    every subdomain', so a POST from an attacker's subdomain with no Origin passes CSRF. If a
    Django upgrade ever changes this, the validator rule can be revisited."""
    _trust_the_proxy(settings)
    settings.CSRF_TRUSTED_ORIGINS = ["https://.example.com"]

    assert _attempt(referer="https://attacker.example.com/x").status_code == 200
    assert _attempt(referer="https://example.com/x").status_code == 200
    assert _attempt(referer="https://evil.test/x").status_code == 403  # the control


# --- the native routes are untouched ----------------------------------------------------------
NATIVE_EMAIL = "pastor@grace.example"
NATIVE_PASSWORD = "correct-horse-battery"


@pytest.fixture
def _fresh_throttle(settings):
    """The throttle buckets live in the process-wide LocMemCache and every test client is
    127.0.0.1, so reset them around the native tests and raise the budgets: the throttle is not
    this file's subject, and a spent bucket must not leak into another file."""
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1000, 60)
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1000, 60)
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def native_user(settings, _fresh_throttle):
    """One verified admin. The cheap hasher is for this file's speed only: what is under test is
    CSRF and the forwarded scheme, not password hashing."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    org = CustomerOrg.objects.create(
        name="Grace Chapel",
        slug="grace-chapel",
        primary_contact_email="office@grace.example",
        country="NG",
        created_by_actor_id="test",
        idempotency_key="org-grace-0001",
    )
    return CustomerUser.objects.create(
        customer=org,
        email=NATIVE_EMAIL,
        email_fingerprint=services._fingerprint(NATIVE_EMAIL),
        password_hash=make_password(NATIVE_PASSWORD),
        status=CustomerUserStatus.ACTIVE,
        role=CustomerRole.ADMIN,
        email_verified_at=timezone.now(),
        created_by_actor_id="test",
        idempotency_key=f"user-{NATIVE_EMAIL}",
    )


def _native_post(path, payload, **extra):
    client = Client(enforce_csrf_checks=True)
    return client.post(path, data=json.dumps(payload), content_type="application/json", **extra)


@pytest.mark.django_db
@pytest.mark.parametrize("trusted", [False, True], ids=["flag-off", "flag-on"])
@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"HTTP_ORIGIN": "https://evil.example", **HTTPS_VIA_PROXY},
        {"HTTP_ORIGIN": "https://testserver", **HTTPS_VIA_PROXY},
        {"HTTP_X_FORWARDED_PROTO": "http", "HTTP_HOST": "testserver"},
    ],
    ids=["no-headers", "foreign-origin", "same-origin", "proxy-says-http"],
)
def test_native_sign_in_needs_no_token_origin_or_referer_whether_or_not_the_proxy_is_trusted(
    settings, native_user, trusted, extra
):
    """The desktop sends none of Origin, Referer, cookie or CSRF token. It must keep working
    with the flag on or off, and whatever a hostile Origin claims: the route is `csrf_exempt` and
    sets no cookie, so nothing about it can be driven from a browser. A wrong password is the
    view's own 401 (JSON), never CSRF's 403 (HTML)."""
    if trusted:
        _trust_the_proxy(settings)

    ok = _native_post(
        "/v1/sessions", {"email": NATIVE_EMAIL, "password": NATIVE_PASSWORD}, **extra
    )
    assert ok.status_code == 200, ok.content
    assert ok.json()["session_token"]
    assert not ok.cookies

    bad = _native_post(
        "/v1/sessions", {"email": NATIVE_EMAIL, "password": "wrong-password"}, **extra
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
@pytest.mark.parametrize("trusted", [False, True], ids=["flag-off", "flag-on"])
def test_native_activation_with_session_is_not_csrf_checked_either(
    settings, _fresh_throttle, trusted
):
    """No bearer token is a 401 from the VIEW (JSON), not a 403 from CSRF (HTML)."""
    if trusted:
        _trust_the_proxy(settings)

    response = _native_post(
        "/v1/activations:with-session",
        {"idempotency_key": "native-act-0001", "device_fingerprint": "fp"},
        HTTP_ORIGIN="https://evil.example",
        **HTTPS_VIA_PROXY,
    )

    assert response.status_code == 401, response.content
    assert response["Content-Type"].startswith("application/json")


# --- the environment -> settings wiring (import-time, so a subprocess) ------------------------
# Booting the real settings module once per case would cost a process each. The pure-settings
# cases below are therefore registered when this module is imported and evaluated together in ONE
# subprocess (each under its own environment, via runpy), then looked up by the tests. Cases that
# must go through `manage.py` or a real request run in a subprocess of their own.
ENV_NAMES = (
    "SELAHCUE_TRUST_FORWARDED_PROTO",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_ALLOWED_HOSTS",
    "SILENCED_SYSTEM_CHECKS",
)
_REGISTERED: list[dict] = []
_EVALUATED: dict[str, dict] = {}

_EVALUATE = """
import json, os, runpy, sys

cases = json.load(sys.stdin)
base = dict(os.environ)
results = []
for case in cases:
    os.environ.clear()
    os.environ.update(base)
    for name, value in case.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    try:
        ns = runpy.run_path("selahcue_api/settings.py")
        results.append({
            "header": ns["SECURE_PROXY_SSL_HEADER"],
            "origins": ns["CSRF_TRUSTED_ORIGINS"],
            "hosts": ns["ALLOWED_HOSTS"],
        })
    except Exception as exc:
        results.append({"error": type(exc).__name__ + ": " + str(exc)})
print(json.dumps(results))
"""


def _clean_env(**env_overrides):
    """The host environment with this file's variables removed, then the overrides applied. A
    value of None means 'leave unset'; an empty or blank string is passed through as given."""
    env = {**os.environ}
    env.pop("DJANGO_SETTINGS_MODULE", None)
    for name in ENV_NAMES:
        env.pop(name, None)
    for name, value in env_overrides.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return env


def _case(**env):
    """Register a settings case at import time and return its environment (a plain dict, which
    is also the lookup key). Every case pins ENVIRONMENT and DEBUG, and leaves SECRET_KEY unset
    unless given, so the host's values cannot change the outcome."""
    full = {"ENVIRONMENT": "dev", "DEBUG": "0", "SECRET_KEY": None, **env}
    _REGISTERED.append(full)
    return full


def _key(env):
    return json.dumps(env, sort_keys=True)


def _settings_for(env):
    """What booting `selahcue_api/settings.py` under `env` produced: the three settings this file
    cares about, or {"error": "<ExceptionType>: <message>"}."""
    if _key(env) not in _EVALUATED:
        cases = _REGISTERED if env in _REGISTERED else [env]
        result = subprocess.run(
            [sys.executable, "-c", _EVALUATE],
            cwd=API_ROOT,
            env=_clean_env(),
            input=json.dumps(cases),
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, result.stderr
        _EVALUATED.update(zip(map(_key, cases), json.loads(result.stdout), strict=True))
    return _EVALUATED[_key(env)]


def _run_manage_check(**env_overrides):
    return subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=API_ROOT,
        env=_clean_env(**{"ENVIRONMENT": "dev", "DEBUG": "0", **env_overrides}),
        capture_output=True,
        text=True,
        timeout=120,
    )


def _flag_id(raw):
    return "unset" if raw is None else repr(raw)


FLAG_ON = ["1", " 1 ", "true", "TRUE", "True", " yes ", "YES", "on"]
FLAG_OFF = [None, "", " ", "0", "false", "off", "no", "y", "t", "enabled", "2", "https"]
FLAG_ON_CASES = [
    pytest.param(_case(SELAHCUE_TRUST_FORWARDED_PROTO=raw), id=_flag_id(raw)) for raw in FLAG_ON
]
FLAG_OFF_CASES = [
    pytest.param(_case(SELAHCUE_TRUST_FORWARDED_PROTO=raw), id=_flag_id(raw)) for raw in FLAG_OFF
]
DEFAULT_CASE = _case()
PROD_DEFAULT_CASE = _case(ENVIRONMENT="prod", SECRET_KEY="x")
PROD_OPT_IN_CASE = _case(ENVIRONMENT="prod", SECRET_KEY="x", SELAHCUE_TRUST_FORWARDED_PROTO="1")


@pytest.mark.parametrize("env", FLAG_ON_CASES)
def test_these_values_turn_the_proxy_trust_on(env):
    assert _settings_for(env)["header"] == list(PROXY_HEADER)


@pytest.mark.parametrize("env", FLAG_OFF_CASES)
def test_every_other_value_leaves_the_proxy_untrusted(env):
    """Anything that is not an unambiguous yes is a no, including the near-misses (`y`, `t`,
    `enabled`, `2`) an operator might type believing they enabled it: failing closed means the
    symptom is the original, documented 403 and not a silently-trusted forgeable header."""
    assert _settings_for(env)["header"] is None


def test_the_shipped_default_is_untrusted_even_in_a_production_environment():
    assert _settings_for(DEFAULT_CASE)["header"] is None
    # A prod-looking environment still does not opt in by itself: this is an explicit decision.
    assert _settings_for(PROD_DEFAULT_CASE)["header"] is None


def test_the_opt_in_works_in_a_production_environment_and_sets_the_exact_django_header_pair():
    assert _settings_for(PROD_OPT_IN_CASE)["header"] == ["HTTP_X_FORWARDED_PROTO", "https"]


# DJANGO_CSRF_TRUSTED_ORIGINS: (raw value, DEBUG, expected list OR the fragment of the refusal).
# Accepted: exact https origins (http only under DEBUG), comma or any whitespace separated,
# duplicates merged, one trailing slash and mixed case normalised. Refused: anything that is not an
# exact origin, with an ImproperlyConfigured naming the variable and the entry.
A = "https://a.example.com"
B = "https://b.example.com"
C = "https://c.example.com"
PATH_MESSAGE = "path, query or fragment"
DOT_MESSAGE = "must not start or end with a dot or contain an empty label"
ORIGIN_CASES = [
    # accepted, and the positive controls
    (None, "0", [], "unset"),
    ("", "0", [], "empty"),
    (" ", "0", [], "whitespace-only"),
    (",", "0", [], "comma-only"),
    (" , ,, ", "0", [], "commas-and-spaces"),
    (A, "0", [A], "single"),
    (f"{A},{B}", "0", [A, B], "comma"),
    (f"{A} {B}", "0", [A, B], "space"),
    (f"{A}, {B}  {C}", "0", [A, B, C], "comma-space-mixed"),
    (f"{A}\t{B}\n", "0", [A, B], "tab-and-newline"),
    (f"{A},", "0", [A], "trailing-comma"),
    (f"{A},{B},{A}", "0", [A, B], "duplicates-merged"),
    (f"{A}/", "0", [A], "one-trailing-slash-normalised"),
    ("https://A.Example.COM", "0", [A], "mixed-case-host-lowercased"),
    ("https://a.example.com:8443", "0", ["https://a.example.com:8443"], "port"),
    ("https://[::1]:8443", "0", ["https://[::1]:8443"], "ipv6"),
    ("http://localhost:5173", "1", ["http://localhost:5173"], "http-in-debug"),
    ("https://localhost:5173", "1", ["https://localhost:5173"], "https-in-debug"),
    ("https://a.example.com:80", "0", ["https://a.example.com:80"], "other-scheme-default-port"),
    ("http://localhost:8080", "1", ["http://localhost:8080"], "http-non-default-port-in-debug"),
    ("https://1.2.3.4:8443", "0", ["https://1.2.3.4:8443"], "ipv4"),
    # refused
    ("http://localhost:5173", "0", "scheme must be https", "http-not-in-debug"),
    ("a.example.com", "0", "scheme must be https", "scheme-less"),
    ("//a.example.com", "0", "scheme must be https", "protocol-relative"),
    ("ftp://a.example.com", "1", "scheme must be https or http", "other-scheme"),
    ("*", "0", "wildcards", "star"),
    ("https://*", "0", "wildcards", "https-star"),
    ("https://*.example.com", "0", "wildcards", "wildcard-subdomain"),
    ("https://a.*.com", "0", "wildcards", "inner-wildcard"),
    ("https://", "0", "no host", "no-host"),
    ("https://a.example.com/path", "0", PATH_MESSAGE, "path"),
    ("https://a.example.com//", "0", PATH_MESSAGE, "two-trailing-slashes"),
    ("https://a.example.com?x=1", "0", PATH_MESSAGE, "query"),
    ("https://a.example.com#frag", "0", PATH_MESSAGE, "fragment"),
    ("https://user@a.example.com", "0", "credentials", "userinfo"),
    ("https://a.example.com:99999", "0", "not a valid URL", "bad-port"),
    # a host Django would read as a wildcard, or that no browser Origin can contain
    ("https://.example.com", "0", DOT_MESSAGE, "leading-dot-host"),
    ("https://.com", "0", DOT_MESSAGE, "leading-dot-tld"),
    ("https://a..example.com", "0", DOT_MESSAGE, "empty-label"),
    ("https://example.com.", "0", DOT_MESSAGE, "trailing-dot-host"),
    ("https://example.com./", "0", DOT_MESSAGE, "trailing-dot-host-and-slash"),
    ("https://.", "0", DOT_MESSAGE, "dot-only-host"),
    # an entry that could never equal a browser's Origin, so it would silently never match
    ("https://a.example.com:443", "0", "default port :443", "default-https-port"),
    ("https://a.example.com:443/", "0", "default port :443", "default-https-port-and-slash"),
    ("http://a.example.com:80", "1", "default port :80", "default-http-port-in-debug"),
    ("https://a.example.com:0", "0", "port 0", "port-zero"),
    ("https://a.example.com\\x", "0", "backslash", "backslash-in-path"),
    ("https://a\\.example.com", "0", "backslash", "backslash-in-host"),
    ("https:\\\\a.example.com", "0", "backslash", "backslash-scheme-separator"),
    ("https://caf" + chr(0xE9) + ".example.com", "0", "punycode (xn--)", "non-ascii-host"),
    ("https://" + chr(0x0430) + ".example.com", "0", "punycode (xn--)", "cyrillic-lookalike-host"),
    ("https://xn--caf-dma.example.com", "0", ["https://xn--caf-dma.example.com"], "punycode-host"),
    (f"{A} https://bad.example.com/x {B}", "0", "https://bad.example.com/x", "bad-among-good"),
]
ORIGIN_PARAMS = [
    pytest.param(_case(DJANGO_CSRF_TRUSTED_ORIGINS=raw, DEBUG=debug), expected, id=case_id)
    for raw, debug, expected, case_id in ORIGIN_CASES
]


@pytest.mark.parametrize(("env", "expected"), ORIGIN_PARAMS)
def test_csrf_trusted_origins_are_parsed_normalised_and_validated(env, expected):
    result = _settings_for(env)

    if isinstance(expected, list):
        assert result.get("origins") == expected, result
        return
    error = result.get("error", "")
    assert error.startswith("ImproperlyConfigured"), result
    assert "DJANGO_CSRF_TRUSTED_ORIGINS" in error
    assert expected in error
    assert "section 6c" in error


# A pasted `https://user:secret@host` is refused, and the message (which lands in logs and
# terminals) must not echo the secret: everything before the last `@` becomes `***`.
SECRET = "hunter2"
CREDENTIAL_ENTRIES = [
    f"https://user:{SECRET}@a.example.com",
    f"https://:{SECRET}@a.example.com",
    f"user:{SECRET}@a.example.com",
    f"https://user:p@{SECRET}@a.example.com",
    f"https://user:{SECRET}@a.example.com:443",
    f"https://user:{SECRET}@a.example.com/path",
    f"https://user:pa/{SECRET}@a.example.com",
    f"https://user:{SECRET}@.example.com",
]
CREDENTIAL_PARAMS = [
    pytest.param(_case(DJANGO_CSRF_TRUSTED_ORIGINS=entry), id=entry.replace(SECRET, "SECRET"))
    for entry in CREDENTIAL_ENTRIES
]


@pytest.mark.parametrize("env", CREDENTIAL_PARAMS)
def test_a_refused_entry_never_echoes_a_password(env):
    error = _settings_for(env).get("error", "")

    assert error.startswith("ImproperlyConfigured"), error
    assert "DJANGO_CSRF_TRUSTED_ORIGINS" in error
    assert SECRET not in error
    assert "***@" in error
    assert "a.example.com" in error or ".example.com" in error  # still identifies the entry


def test_a_refused_credential_entry_leaks_nothing_through_manage_py_either():
    refused = _run_manage_check(DJANGO_CSRF_TRUSTED_ORIGINS=f"https://user:{SECRET}@a.example.com")

    assert refused.returncode != 0
    assert "ImproperlyConfigured" in refused.stderr
    assert SECRET not in refused.stdout + refused.stderr


@pytest.mark.parametrize("entry", ["app.example.com", "*", "https://*.example.com"])
def test_a_bad_trusted_origin_stops_manage_py_with_a_message_naming_it(entry):
    """Through the real `manage.py` entry point, with a positive control: the identical command
    with a valid origin exits 0."""
    refused = _run_manage_check(DJANGO_CSRF_TRUSTED_ORIGINS=entry)
    assert refused.returncode != 0
    assert "ImproperlyConfigured" in refused.stderr
    assert "DJANGO_CSRF_TRUSTED_ORIGINS" in refused.stderr
    assert repr(entry) in refused.stderr

    control = _run_manage_check(DJANGO_CSRF_TRUSTED_ORIGINS="https://a.example.com")
    assert control.returncode == 0, control.stderr


# ALLOWED_HOSTS moved onto the same `env_list` helper as CSRF_TRUSTED_ORIGINS; its parsing
# (space-separated, commas tolerated, a default for local dev, empty entries dropped) must not
# have shifted.
HOSTS_CASES = [
    (None, ["localhost", "127.0.0.1", "testserver"], "default"),
    ("api.example.com", ["api.example.com"], "single"),
    ("api.example.com,admin.example.com", ["api.example.com", "admin.example.com"], "comma"),
    ("api.example.com admin.example.com", ["api.example.com", "admin.example.com"], "space"),
    (
        "api.example.com, admin.example.com  [::1]",
        ["api.example.com", "admin.example.com", "[::1]"],
        "mixed",
    ),
    ("api.example.com,,  ,", ["api.example.com"], "empty-entries-dropped"),
    ("", [], "empty"),
]
HOSTS_PARAMS = [
    pytest.param(_case(DJANGO_ALLOWED_HOSTS=raw), expected, id=case_id)
    for raw, expected, case_id in HOSTS_CASES
]


@pytest.mark.parametrize(("env", "expected"), HOSTS_PARAMS)
def test_allowed_hosts_parsing_is_unchanged_by_the_shared_list_helper(env, expected):
    assert _settings_for(env)["hosts"] == expected


# --- the deploy-time warning (selahcue_accounts.W002) through the real manage.py -------------
def test_manage_py_check_warns_in_a_deployed_environment_that_has_not_opted_in():
    result = _run_manage_check(ENVIRONMENT="prod", SECRET_KEY="x")
    output = result.stdout + result.stderr

    assert result.returncode == 0, result.stderr  # a Warning, never an Error
    # The id as it prefixes the warning itself, not as it appears inside the hint (which names it
    # again in its SILENCED_SYSTEM_CHECKS advice, so a bare substring survives a rename).
    assert f"?: ({W002}) SELAHCUE_TRUST_FORWARDED_PROTO is off" in output
    assert "section 6c" in output


def test_manage_py_check_is_quiet_once_opted_in_and_in_dev():
    opted_in = _run_manage_check(
        ENVIRONMENT="prod", SECRET_KEY="x", SELAHCUE_TRUST_FORWARDED_PROTO="1"
    )
    assert opted_in.returncode == 0, opted_in.stderr
    assert W002 not in opted_in.stdout + opted_in.stderr

    dev = _run_manage_check()
    assert dev.returncode == 0, dev.stderr
    assert W002 not in dev.stdout + dev.stderr


# --- end to end through the real environment variable: THE acceptance test --------------------
_BROWSER_THROUGH_PROXY = """
import json
import django

django.setup()
from django.conf import settings
from django.test import Client

client = Client(enforce_csrf_checks=True)
hdr = {"HTTP_X_FORWARDED_PROTO": "https", "HTTP_HOST": "testserver"}
bootstrap = client.get("/graphql/csrf", **hdr)
token = bootstrap.cookies[settings.CSRF_COOKIE_NAME].value
post = client.post(
    "/graphql/account",
    data=json.dumps({"query": "{ __typename }"}),
    content_type="application/json",
    HTTP_X_CSRFTOKEN=token,
    HTTP_ORIGIN="https://testserver",
    **hdr,
)
print(json.dumps({"status": post.status_code, "hsts": post.headers.get("Strict-Transport-Security")}))
"""


def _browser_through_proxy(**env_overrides):
    env = _clean_env()
    env.update(
        ENVIRONMENT="dev",
        DEBUG="0",
        # Nothing here queries a database or a cache; pin both to the in-process defaults so the
        # job's Postgres/Redis environment (CI) is not even consulted.
        SQL_ENGINE="django.db.backends.sqlite3",
        SQL_DATABASE=":memory:",
        CACHE_URL="",
        DJANGO_SETTINGS_MODULE="selahcue_api.settings",
    )
    env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, "-c", _BROWSER_THROUGH_PROXY],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_acceptance_the_environment_variable_alone_turns_the_https_flow_on():
    """THE acceptance test: environment variable -> real settings module -> middleware stack ->
    HTTP response, with only the environment differing. A browser-shaped POST with
    `Origin: https://<host>`, a valid token and `X-Forwarded-Proto: https` is refused (403, no
    HSTS) by default and accepted (200 plus HSTS) once SELAHCUE_TRUST_FORWARDED_PROTO is on."""
    assert _browser_through_proxy() == {"status": 403, "hsts": None}

    on = _browser_through_proxy(SELAHCUE_TRUST_FORWARDED_PROTO="1")
    assert on["status"] == 200
    assert on["hsts"] == EXPECTED_HSTS


@pytest.mark.parametrize(
    ("raw", "trusted"), [("y", False), ("0", False), (" True ", True), ("on", True)]
)
def test_the_spelling_of_the_flag_decides_the_end_to_end_outcome(raw, trusted):
    outcome = _browser_through_proxy(SELAHCUE_TRUST_FORWARDED_PROTO=raw)

    assert outcome["status"] == (200 if trusted else 403)
    assert (outcome["hsts"] is not None) is trusted
