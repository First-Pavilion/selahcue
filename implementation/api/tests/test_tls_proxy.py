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

Django's test client bypasses CSRF unless `enforce_csrf_checks=True`, so every browser-shaped
client here sets it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.cache import cache
from django.test import Client

API_ROOT = Path(__file__).resolve().parent.parent

PROXY_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
HSTS = "Strict-Transport-Security"
EXPECTED_HSTS = "max-age=31536000; includeSubDomains; preload"

# What a browser behind the proxy produces. The explicit Host matters: the test client otherwise
# derives one from SERVER_NAME and SERVER_PORT (80), which becomes `testserver:80` once the
# request counts as https and has nothing to do with what nginx forwards (`Host $host`).
HTTPS_VIA_PROXY = {"HTTP_X_FORWARDED_PROTO": "https", "HTTP_HOST": "testserver"}

MUTATION = {
    "query": 'mutation { resendVerificationEmail(email: "nobody@browser.example") { accepted } }'
}


@pytest.fixture(autouse=True)
def _hsts_on_and_budget_clean(settings):
    """Pin HSTS to the production values whatever the host environment says (`DEBUG=1` in a
    developer's shell zeroes it), and start every test with an unspent resend budget and no
    constant-time padding: neither is this file's subject."""
    settings.SECURE_HSTS_SECONDS = 31536000
    settings.SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    settings.SECURE_HSTS_PRELOAD = True
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0.0
    cache.clear()
    yield
    cache.clear()


def _browser_post(client, token, **extra):
    return client.post(
        "/graphql/account",
        data=json.dumps(MUTATION),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
        **extra,
    )


def _seed_token(client, **extra):
    bootstrap = client.get("/graphql/csrf", **extra)
    assert bootstrap.status_code == 200
    return bootstrap.cookies["csrftoken"].value


# --- the configured deployment: header honoured ----------------------------------------------
@pytest.mark.django_db
def test_https_origin_through_a_tls_proxy_passes_csrf_and_gets_hsts(settings):
    """THE acceptance test: a browser-shaped mutation with `Origin: https://<host>`, a valid
    token and the proxy's `X-Forwarded-Proto: https` returns 200 and carries HSTS."""
    settings.SECURE_PROXY_SSL_HEADER = PROXY_HEADER
    client = Client(enforce_csrf_checks=True)
    token = _seed_token(client, **HTTPS_VIA_PROXY)

    response = _browser_post(client, token, HTTP_ORIGIN="https://testserver", **HTTPS_VIA_PROXY)

    assert response.status_code == 200
    assert response.json()["data"]["resendVerificationEmail"]["accepted"] is True
    assert response[HSTS] == EXPECTED_HSTS


@pytest.mark.django_db
def test_hsts_is_emitted_on_every_proxied_secure_response(settings):
    settings.SECURE_PROXY_SSL_HEADER = PROXY_HEADER
    client = Client(enforce_csrf_checks=True)

    response = client.get("/graphql/csrf", **HTTPS_VIA_PROXY)

    assert response[HSTS] == EXPECTED_HSTS


@pytest.mark.django_db
def test_a_request_the_proxy_says_was_plain_http_is_not_treated_as_secure(settings):
    """Only the exact value `https` upgrades a request. `http` (what a proxy sends for a
    plain-HTTP hop) leaves it insecure: no HSTS, and an `https` Origin is still refused."""
    settings.SECURE_PROXY_SSL_HEADER = PROXY_HEADER
    client = Client(enforce_csrf_checks=True)
    plain_http = {**HTTPS_VIA_PROXY, "HTTP_X_FORWARDED_PROTO": "http"}
    token = _seed_token(client, **plain_http)

    plain = client.get("/graphql/csrf", **plain_http)
    assert HSTS not in plain

    refused = _browser_post(client, token, HTTP_ORIGIN="https://testserver", **plain_http)
    assert refused.status_code == 403


@pytest.mark.django_db
def test_configured_but_no_header_means_a_direct_client_cannot_claim_https(settings):
    """Even with the setting on, a request that carries no `X-Forwarded-Proto` is plain HTTP:
    the setting reads the header, it does not assume https."""
    settings.SECURE_PROXY_SSL_HEADER = PROXY_HEADER
    client = Client(enforce_csrf_checks=True)
    token = _seed_token(client)

    refused = _browser_post(
        client, token, HTTP_ORIGIN="https://testserver", HTTP_HOST="testserver"
    )

    assert refused.status_code == 403
    assert HSTS not in refused


@pytest.mark.django_db
def test_a_cross_origin_post_is_still_refused_when_the_proxy_is_trusted(settings):
    """Trusting the scheme must not loosen the origin check itself."""
    settings.SECURE_PROXY_SSL_HEADER = PROXY_HEADER
    client = Client(enforce_csrf_checks=True)
    token = _seed_token(client, **HTTPS_VIA_PROXY)

    forged = _browser_post(client, token, HTTP_ORIGIN="https://evil.example", **HTTPS_VIA_PROXY)
    assert forged.status_code == 403

    tokenless = Client(enforce_csrf_checks=True).post(
        "/graphql/account",
        data=json.dumps(MUTATION),
        content_type="application/json",
        HTTP_ORIGIN="https://testserver",
        **HTTPS_VIA_PROXY,
    )
    assert tokenless.status_code == 403


# --- the default deployment: header NOT trusted -----------------------------------------------
@pytest.mark.django_db
def test_a_forged_forwarded_proto_is_ignored_when_the_setting_is_off(settings):
    """The shipped default. A client that reaches Django directly and sends
    `X-Forwarded-Proto: https` must not be believed: the https Origin stays refused and no
    HSTS is emitted, exactly as before the setting existed."""
    assert getattr(settings, "SECURE_PROXY_SSL_HEADER", None) is None
    client = Client(enforce_csrf_checks=True)
    token = _seed_token(client, **HTTPS_VIA_PROXY)

    refused = _browser_post(client, token, HTTP_ORIGIN="https://testserver", **HTTPS_VIA_PROXY)

    assert refused.status_code == 403
    assert HSTS not in refused
    forged_get = client.get("/graphql/csrf", **HTTPS_VIA_PROXY)
    assert HSTS not in forged_get


@pytest.mark.django_db
def test_local_development_without_a_proxy_is_unchanged(settings):
    """No proxy, no header, http Origin: the pre-existing flow still works end to end."""
    client = Client(enforce_csrf_checks=True)
    token = _seed_token(client)

    accepted = _browser_post(client, token, HTTP_ORIGIN="http://testserver")

    assert accepted.status_code == 200
    assert HSTS not in accepted


# --- CSRF_TRUSTED_ORIGINS ---------------------------------------------------------------------
@pytest.mark.django_db
def test_a_public_origin_that_differs_from_the_host_needs_csrf_trusted_origins(settings):
    """Origin `https://app.example.com` against a Host of `testserver` is refused until the
    public origin is listed, and listing it admits ONLY that origin. A fresh client per attempt:
    `CsrfViewMiddleware` reads the setting once per middleware instance."""
    settings.SECURE_PROXY_SSL_HEADER = PROXY_HEADER

    def attempt(origin):
        client = Client(enforce_csrf_checks=True)
        token = _seed_token(client, **HTTPS_VIA_PROXY)
        return _browser_post(client, token, HTTP_ORIGIN=origin, **HTTPS_VIA_PROXY).status_code

    assert attempt("https://app.example.com") == 403

    settings.CSRF_TRUSTED_ORIGINS = ["https://app.example.com"]
    assert attempt("https://app.example.com") == 200
    assert attempt("https://other.example.com") == 403


# --- the native routes are untouched ----------------------------------------------------------
def test_the_native_routes_stay_csrf_exempt_and_graphql_routes_stay_enforced():
    """The two `/v1` native routes are `csrf_exempt` by design (ADR-0029); the browser GraphQL
    routes are not. Trusting the proxy header changes `is_secure()`, nothing about exemption."""
    from selahcue_api import urls

    def callbacks(patterns, prefix=""):
        for entry in patterns:
            route = prefix + str(entry.pattern)
            if hasattr(entry, "url_patterns"):
                yield from callbacks(entry.url_patterns, route)
            else:
                yield route, entry.callback

    by_route = dict(callbacks(urls.urlpatterns))
    assert getattr(by_route["graphql/account"], "csrf_exempt", False) is False
    assert getattr(by_route["graphql/admin"], "csrf_exempt", False) is False
    assert getattr(by_route["v1/sessions"], "csrf_exempt", False) is True


# --- the environment -> settings wiring (import-time, so a subprocess) ------------------------
def _read_settings(**env_overrides):
    env = {**os.environ, **env_overrides}
    env.pop("DJANGO_SETTINGS_MODULE", None)
    for name in ("SELAHCUE_TRUST_FORWARDED_PROTO", "DJANGO_CSRF_TRUSTED_ORIGINS"):
        if name not in env_overrides:
            env.pop(name, None)
    program = (
        "import json; from selahcue_api import settings as s; "
        "print(json.dumps({'header': s.SECURE_PROXY_SSL_HEADER, "
        "'origins': s.CSRF_TRUSTED_ORIGINS}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_proxy_header_is_not_trusted_unless_the_environment_opts_in():
    assert _read_settings()["header"] is None
    assert _read_settings(SELAHCUE_TRUST_FORWARDED_PROTO="0")["header"] is None
    # A prod-looking environment still does not opt in by itself: this is an explicit decision.
    assert _read_settings(ENVIRONMENT="prod", SECRET_KEY="x")["header"] is None


def test_the_environment_opt_in_sets_the_exact_django_header_pair():
    assert _read_settings(SELAHCUE_TRUST_FORWARDED_PROTO="1")["header"] == list(PROXY_HEADER)


def test_csrf_trusted_origins_parse_space_or_comma_separated():
    assert _read_settings()["origins"] == []
    parsed = _read_settings(
        DJANGO_CSRF_TRUSTED_ORIGINS="https://a.example.com, https://b.example.com  https://c.example.com"
    )
    assert parsed["origins"] == [
        "https://a.example.com",
        "https://b.example.com",
        "https://c.example.com",
    ]


def test_a_scheme_less_trusted_origin_fails_the_django_system_check():
    """Django's own check (4_0.E001) is what stops `app.example.com` from being silently
    ignored; pin that it fires through the real `manage.py check`, with the real env name."""
    env = {**os.environ, "ENVIRONMENT": "dev", "DJANGO_CSRF_TRUSTED_ORIGINS": "app.example.com"}
    env.pop("DJANGO_SETTINGS_MODULE", None)
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "CSRF_TRUSTED_ORIGINS" in result.stderr + result.stdout


# --- end to end through the real environment variable -----------------------------------------
_BROWSER_THROUGH_PROXY = """
import json
import django

django.setup()
from django.test import Client

client = Client(enforce_csrf_checks=True)
hdr = {"HTTP_X_FORWARDED_PROTO": "https", "HTTP_HOST": "testserver"}
bootstrap = client.get("/graphql/csrf", **hdr)
token = bootstrap.cookies["csrftoken"].value
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
    env = {**os.environ, "ENVIRONMENT": "dev", "DEBUG": "0", "SQL_DATABASE": ":memory:"}
    env["DJANGO_SETTINGS_MODULE"] = "selahcue_api.settings"
    env.pop("SELAHCUE_TRUST_FORWARDED_PROTO", None)
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


def test_the_environment_variable_alone_turns_the_https_flow_on():
    """Wiring, not behaviour: the same browser sequence against a freshly booted settings
    module, with only the environment differing. Off, an `https` Origin is refused and no HSTS
    comes back; on, it is accepted and HSTS is present."""
    off = _browser_through_proxy()
    assert off == {"status": 403, "hsts": None}

    on = _browser_through_proxy(SELAHCUE_TRUST_FORWARDED_PROTO="1")
    assert on["status"] == 200
    assert on["hsts"] == EXPECTED_HSTS
