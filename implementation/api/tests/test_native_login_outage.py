"""Native login refuses unavailable limiter budgets; device traffic remains fail-open.

Real HTTP requests and the original PBKDF2 encoder distinguish zero password work from a
service-only stub. Fault injection raises from the actual private LocMem backend's add.
"""

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.core.cache import cache
from django.core.cache.backends.locmem import LocMemCache
from django.test import Client

from selahcue_api import settings as production_settings
from selahcue_api.apps.throttling import guards, services
from selahcue_api.apps.throttling.services import BudgetOutcome, CacheStore
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
from selahcue_api.platform import views
from test_native_account_surface import (
    activation_payload, bearer, native_client, post_json, seed_admin_with_license, session_token,
)

pytestmark = pytest.mark.django_db
EMAIL = "native-outage-private@example.invalid"
PASSWORD = "PRIVATE-OUTAGE-PASSWORD-3ac1"
TOKEN = "PRIVATE-OUTAGE-BEARER-7dfa"
ERROR_TEXT = "PRIVATE-CACHE-EXCEPTION-8bcb"
IP = "203.0.113.71"


@pytest.fixture(autouse=True)
def private_state(settings, monkeypatch, caplog):
    settings.CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": f"native-login-outage-{uuid.uuid4()}",
    }}
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = production_settings.SELAHCUE_THROTTLE_SESSION_LOGIN
    cache.clear()
    guards._reset_denial_log_suppression()
    monkeypatch.setattr(services, "_last_store_error_log", float("-inf"))
    clock = [1000.0]
    monkeypatch.setattr(services.time, "monotonic", lambda: clock[0])
    caplog.set_level(logging.WARNING, logger=services.logger.name)
    yield clock
    guards._reset_denial_log_suppression()


@pytest.fixture
def broken_cache(monkeypatch):
    @contextmanager
    def broken():
        calls = []
        with monkeypatch.context() as patch:
            def unavailable(*args, **kwargs):
                calls.append(1)
                raise RuntimeError(ERROR_TEXT)
            patch.setattr(LocMemCache, "add", unavailable)
            yield calls
    return broken


@pytest.fixture
def password_hashes(monkeypatch):
    original = PBKDF2PasswordHasher.encode
    calls = []

    def count_real_hash(self, password, salt, iterations=None):
        calls.append(1)
        return original(self, password, salt, iterations)

    monkeypatch.setattr(PBKDF2PasswordHasher, "encode", count_real_hash)
    return calls


def native_login(client):
    return client.post(
        "/v1/sessions", data=json.dumps({"email": EMAIL, "password": PASSWORD}),
        content_type="application/json", REMOTE_ADDR=IP,
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def outage_records(caplog):
    return [r for r in caplog.records if r.name == services.logger.name
            and "rate-limit store unavailable" in r.getMessage()]


def test_twentyfive_native_outage_requests_hash_zero_passwords_and_return_429(
    broken_cache, password_hashes, caplog,
):
    client = native_client()
    with broken_cache() as calls:
        responses = [native_login(client) for _ in range(25)]
    assert len(calls) == 25, "each actual request reached the unavailable cache"
    assert len(password_hashes) == 0, f"outage performed {len(password_hashes)} real PBKDF2 calls"
    assert [r.status_code for r in responses] == [429] * 25
    for response in responses:
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        assert response.json()["operation"] == "session_login"
        assert response["Cache-Control"] == "no-store"
        assert response["Retry-After"] == "60"
        assert not response.cookies
    assert len(outage_records(caplog)) == 1


def test_healthy_native_login_still_spends_ten_real_hashes_then_denies(password_hashes):
    assert production_settings.SELAHCUE_THROTTLE_SESSION_LOGIN == (10, 60)
    responses = [native_login(native_client()) for _ in range(11)]
    assert [r.status_code for r in responses] == [401] * 10 + [429]
    assert len(password_hashes) == 10


def test_cache_recovery_allows_next_native_password_check(broken_cache, password_hashes):
    client = native_client()
    with broken_cache():
        refused = native_login(client)
    assert refused.status_code == 429
    assert len(password_hashes) == 0
    assert native_login(client).status_code == 401
    assert len(password_hashes) == 1


@pytest.mark.parametrize("code,status", [
    (ErrorCode.UNAUTHENTICATED, 401), (ErrorCode.POLICY_DENIED, 403),
    (ErrorCode.VALIDATION_FAILED, 400),
])
def test_service_refusal_is_not_misclassified_as_store_outage(monkeypatch, caplog, code, status):
    def refuse(*args, **kwargs):
        raise SafeAPIError(code)
    monkeypatch.setattr(views, "_login_service", refuse)
    response = native_login(native_client())
    assert response.status_code == status
    assert response.json()["error"]["code"] == code.value
    assert outage_records(caplog) == []


@pytest.mark.parametrize("path,method,status", [
    ("/v1/activations", "post", 400), ("/v1/activations:with-session", "post", 401),
    ("/v1/license:refresh", "post", 401), ("/v1/entitlements/manifest", "get", 401),
])
def test_other_native_routes_still_fail_open_on_the_same_cache_fault(broken_cache, path, method, status):
    client = native_client()
    with broken_cache() as calls:
        if method == "get":
            response = client.get(path, REMOTE_ADDR=IP)
        else:
            response = client.post(path, data="{}", content_type="application/json", REMOTE_ADDR=IP)
    assert calls == [1]
    assert response.status_code == status, "other routes must reach their normal application path"


def test_an_activated_device_still_refreshes_while_bootstrap_login_is_refused(broken_cache):
    seed_admin_with_license()
    client = native_client()
    account_token = session_token(client)
    activation = post_json(
        client, "/v1/activations:with-session", activation_payload(), **bearer(account_token),
    )
    assert activation.status_code == 200
    device_token = activation.json()["activation_token"]
    with broken_cache():
        assert native_login(client).status_code == 429
        refresh = client.post("/v1/license:refresh", **bearer(device_token))
    assert refresh.status_code == 200, refresh.content
    assert refresh.json()["device"]["status"] == "ACTIVE"
    assert refresh.json()["license"]["valid_now"] is True


def test_browser_graphql_login_is_unchanged_even_when_cache_is_unavailable(broken_cache, password_hashes):
    with broken_cache() as calls:
        response = Client().post(
            "/graphql/account", data=json.dumps({
                "query": "mutation($i: LoginInput!) { login(input: $i) { sessionToken } }",
                "variables": {"i": {"email": EMAIL, "password": PASSWORD}},
            }), content_type="application/json",
        )
    assert response.json()["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"
    assert calls == [], "browser login did not gain a native limiter policy"
    assert len(password_hashes) == 1


def test_method_and_content_type_guards_still_run_before_unavailable_budget(broken_cache, password_hashes):
    client = native_client()
    with broken_cache() as calls:
        assert client.get("/v1/sessions").status_code == 405
        assert client.post("/v1/sessions", data="secret", content_type="text/plain").status_code == 400
    assert calls == []
    assert password_hashes == []


def test_unavailable_native_login_never_reads_retry_expiry_from_failed_store(monkeypatch, broken_cache):
    def unexpected_metadata(*args, **kwargs):
        raise AssertionError("outage refusal must not query the failed store again")
    monkeypatch.setattr(CacheStore, "retry_after", unexpected_metadata)
    with broken_cache():
        response = native_login(native_client())
    assert response.status_code == 429
    assert response["Retry-After"] == "60"


def test_outage_warning_is_redacted_honest_and_repeats_after_sixty_seconds(
    broken_cache, private_state, caplog,
):
    with broken_cache():
        store = CacheStore(cache)
        key = f"throttle:session_login:{IP}"
        for _ in range(25):
            assert services.evaluate_budget(store, key, 10, 60) is BudgetOutcome.STORE_UNAVAILABLE
        private_state[0] += 59.99
        services.evaluate_budget(store, key, 10, 60)
        assert len(outage_records(caplog)) == 1
        private_state[0] += 0.01
        services.evaluate_budget(store, key, 10, 60)
    assert len(outage_records(caplog)) == 2
    for record in outage_records(caplog):
        assert "failing open" not in record.getMessage(), "native login no longer fails open"
        assert record.exc_info is None
        for private in (EMAIL, PASSWORD, TOKEN, ERROR_TEXT, IP, key):
            assert private not in record.getMessage()
            assert private not in repr(record.args)


def test_concurrent_unavailable_budget_checks_emit_one_outage_warning(broken_cache, caplog):
    barrier = threading.Barrier(8)

    def many_faults():
        barrier.wait(timeout=10)
        for _ in range(25):
            assert services.evaluate_budget(CacheStore(cache), "synthetic-key", 10, 60) is BudgetOutcome.STORE_UNAVAILABLE

    with broken_cache():
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(many_faults) for _ in range(8)]
            for future in futures:
                future.result(timeout=15)
    assert len(outage_records(caplog)) == 1


def test_unexpected_login_service_exception_is_not_hidden_as_limiter_unavailability(monkeypatch, caplog):
    def failed_service(*args, **kwargs):
        raise RuntimeError("synthetic-login-service-failure")
    monkeypatch.setattr(views, "_login_service", failed_service)
    with pytest.raises(RuntimeError, match="synthetic-login-service-failure"):
        native_login(native_client())
    assert outage_records(caplog) == []
