"""Native-only bounded application warning stream (17tnw2b1wqa).

Framework request-status logging is separate. These assertions inspect only the new/shared
application reporter; actual HTTP checks retain the complete native guards and response path.
"""

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from selahcue_api.apps.throttling import guards
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
from selahcue_api.platform import views
from test_native_account_surface import seed_org, seed_user

pytestmark = pytest.mark.django_db

SCOPES = [
    ("activation", "/v1/activations", "post", "SELAHCUE_THROTTLE_ACTIVATION"),
    ("session_login", "/v1/sessions", "post", "SELAHCUE_THROTTLE_SESSION_LOGIN"),
    ("activation_with_session", "/v1/activations:with-session", "post", "SELAHCUE_THROTTLE_ACTIVATION"),
    ("license_refresh", "/v1/license:refresh", "post", "SELAHCUE_THROTTLE_DEVICE_READ"),
    ("entitlement_manifest", "/v1/entitlements/manifest", "get", "SELAHCUE_THROTTLE_DEVICE_READ"),
]
EMAIL = "private-observability@example.invalid"
PASSWORD = "PRIVATE-PASSWORD-OBS-7b21"
TOKEN = "PRIVATE-BEARER-OBS-9b52"
IP = "203.0.113.91"


@pytest.fixture(autouse=True)
def clean_reporting(settings, monkeypatch, caplog):
    settings.CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": f"native-observability-{uuid.uuid4()}",
    }}
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1000, 60)
    cache.clear()
    guards._reset_denial_log_suppression()
    clock = [1000.0]
    monkeypatch.setattr(guards.time, "monotonic", lambda: clock[0])
    caplog.set_level(logging.WARNING, logger=guards.logger.name)
    yield clock
    guards._reset_denial_log_suppression()


def application_warnings(caplog):
    return [r for r in caplog.records if r.name == guards.logger.name and r.levelno >= logging.WARNING]


def assert_no_identifiers(records):
    for record in records:
        for secret in (EMAIL, PASSWORD, TOKEN, IP):
            assert secret not in record.getMessage()
            assert secret not in repr(record.args)
        assert record.exc_info is None


def sign_in(client, *, email=EMAIL, password=PASSWORD):
    return client.post(
        "/v1/sessions", data=json.dumps({"email": email, "password": password}),
        content_type="application/json", REMOTE_ADDR=IP,
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


@pytest.mark.parametrize("scope,path,method,setting_name", SCOPES)
def test_fifty_actual_native_denials_emit_one_scope_warning_and_keep_headers(
    settings, caplog, scope, path, method, setting_name,
):
    setattr(settings, setting_name, (0, 60))
    client = Client(enforce_csrf_checks=True)
    for _ in range(50):
        if method == "get":
            response = client.get(path, REMOTE_ADDR=IP, HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
        else:
            response = client.post(
                path, data=json.dumps({"email": EMAIL, "password": PASSWORD, "token": TOKEN}),
                content_type="application/json", REMOTE_ADDR=IP,
                HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
            )
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        assert response["Cache-Control"] == "no-store"
        assert 1 <= int(response["Retry-After"]) <= 60
        assert not response.cookies
    records = application_warnings(caplog)
    assert len(records) == 1, "50 native denials must report once, rather than zero or50 times"
    assert f"scope={scope}" in records[0].getMessage()
    assert_no_identifiers(records)


@pytest.mark.parametrize("code", [ErrorCode.UNAUTHENTICATED, ErrorCode.POLICY_DENIED,
                                  ErrorCode.VALIDATION_FAILED])
def test_fifty_native_service_refusals_have_one_aggregate_warning(monkeypatch, caplog, code):
    calls = []

    def refuse(data, **kwargs):
        calls.append(kwargs)
        raise SafeAPIError(code)

    monkeypatch.setattr(views, "_login_service", refuse)
    client = Client(enforce_csrf_checks=True)
    for _ in range(50):
        response = sign_in(client)
        assert response.json()["error"]["code"] == code.value
        assert response["Cache-Control"] == "no-store"
        assert not response.cookies
    assert calls == [{"source_surface": "desktop_v1"}] * 50
    records = application_warnings(caplog)
    assert len(records) == 1, "native failed authentication must have a bounded positive signal"
    assert "scope=session_login" in records[0].getMessage()
    assert "refused sign-ins" in records[0].getMessage()
    assert_no_identifiers(records)


def test_real_unknown_wrong_locked_and_policy_refusals_report_without_state_details(
    clean_reporting, caplog,
):
    org = seed_org(tag="observability")
    wrong = seed_user(org, email="wrong-observability@example.invalid")
    locked = seed_user(org, email="locked-observability@example.invalid")
    locked.locked_until = timezone.now() + timezone.timedelta(minutes=1)
    locked.save(update_fields=["locked_until"])
    policy = seed_user(org, email="policy-observability@example.invalid", verified=False)
    client = Client(enforce_csrf_checks=True)
    for email, password, code in [
        (EMAIL, PASSWORD, "UNAUTHENTICATED"),
        (wrong.email, PASSWORD, "UNAUTHENTICATED"),
        (locked.email, "correct-horse-battery", "UNAUTHENTICATED"),
        (policy.email, "correct-horse-battery", "POLICY_DENIED"),
    ]:
        response = sign_in(client, email=email, password=password)
        assert response.json()["error"]["code"] == code
        clean_reporting[0] += 60
    records = application_warnings(caplog)
    assert len(records) == 4
    assert len({r.getMessage() for r in records}) == 1, "do not distinguish existence or locked state"
    assert_no_identifiers(records)
    for record in records:
        for value in (wrong.email, locked.email, policy.email, str(wrong.pk), str(org.pk)):
            assert value not in record.getMessage()


@pytest.mark.parametrize("event", ["denial", "login_failure"])
def test_native_warning_clock_boundary_and_reset_are_positive(clean_reporting, caplog, event):
    report = (lambda: guards.report_native_denial("session_login")) if event == "denial" else guards.report_native_login_failure
    report()
    clean_reporting[0] += 59.99
    report()
    assert len(application_warnings(caplog)) == 1
    clean_reporting[0] += 0.01
    report()
    assert len(application_warnings(caplog)) == 2
    guards._reset_denial_log_suppression()
    report()
    assert len(application_warnings(caplog)) == 3


@pytest.mark.parametrize("event", ["denial", "login_failure"])
def test_concurrent_native_warning_reports_emit_once(caplog, event):
    barrier = threading.Barrier(8)

    def report_many():
        barrier.wait(timeout=10)
        for _ in range(50):
            if event == "denial":
                guards.report_native_denial("session_login")
            else:
                guards.report_native_login_failure()

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(report_many) for _ in range(8)]
        for future in futures:
            future.result(timeout=15)
    assert len(application_warnings(caplog)) == 1


def test_native_scope_state_rejects_unknown_names_and_never_tracks_identifiers(caplog):
    for scope, *_ in SCOPES:
        guards.report_native_denial(scope)
    expected = {scope for scope, *_ in SCOPES}
    assert set(guards._last_denial_log) == expected
    assert len(application_warnings(caplog)) == 5
    for i in range(1000):
        guards.report_native_denial(f"{EMAIL}:{IP}:{i}")
        guards.report_native_login_failure()
    assert set(guards._last_denial_log) == expected
    assert len(application_warnings(caplog)) == 6
    assert_no_identifiers(application_warnings(caplog))


def test_native_denial_and_login_failure_are_independent_signals(caplog):
    guards.report_native_denial("session_login")
    guards.report_native_login_failure()
    assert len(application_warnings(caplog)) == 2
    assert any("RATE_LIMITED" in r.getMessage() for r in application_warnings(caplog))
    assert any("refused sign-ins" in r.getMessage() for r in application_warnings(caplog))


def test_browser_graphql_login_refusal_does_not_emit_native_warning(caplog):
    response = Client().post(
        "/graphql/account",
        data=json.dumps({
            "query": "mutation($i: LoginInput!) { login(input: $i) { sessionToken } }",
            "variables": {"i": {"email": EMAIL, "password": PASSWORD}},
        }), content_type="application/json",
    )
    assert response.json()["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"
    assert application_warnings(caplog) == []


def test_success_and_precredential_rejections_never_emit_failed_signin_warning(monkeypatch, caplog):
    monkeypatch.setattr(views, "_login_service", lambda *a, **kw: SimpleNamespace(
        session_token=TOKEN, expires_at="2026-10-29T20:00:00Z", role="ADMIN", org_id="org",
    ))
    client = Client(enforce_csrf_checks=True)
    assert sign_in(client).status_code == 200
    assert client.post("/v1/sessions", data="{}", content_type="application/json").status_code == 400
    assert client.post("/v1/sessions", data="secret", content_type="text/plain").status_code == 400
    assert client.get("/v1/sessions").status_code == 405
    assert application_warnings(caplog) == []
