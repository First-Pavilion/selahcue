"""Remaining-window headers on the existing shared /v1 throttle (17tnw2b1wqc).

The decisions and error envelope must stay unchanged. A constant full-window retry hint
passes a presence-only assertion but makes a request near expiry wait a whole extra window;
clock-driven real-cache checks distinguish that regression without sleeps.
"""

import math
import os
import time
import uuid

import pytest
from django.core.cache import cache, caches
from django.core.cache.backends.dummy import DummyCache
from django.core.cache.backends.redis import RedisCache
from django.http import JsonResponse
from django.test import RequestFactory

from selahcue_api.apps.throttling import services
from selahcue_api.apps.throttling.decorators import throttle
from selahcue_api.apps.throttling.services import CacheStore
from selahcue_api.graphql.errors import ErrorCode, SAFE_MESSAGES


@pytest.fixture
def local_clock(settings, monkeypatch):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": f"throttle-headers-{uuid.uuid4()}",
            "KEY_PREFIX": "headers",
            "VERSION": 7,
        }
    }
    now = [1000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    return now


ROUTES = [
    ("/v1/activations", "post", "SELAHCUE_THROTTLE_ACTIVATION", "activation", 400),
    ("/v1/sessions", "post", "SELAHCUE_THROTTLE_SESSION_LOGIN", "session_login", 400),
    (
        "/v1/activations:with-session", "post", "SELAHCUE_THROTTLE_ACTIVATION",
        "activation_with_session", 401,
    ),
    ("/v1/license:refresh", "post", "SELAHCUE_THROTTLE_DEVICE_READ", "license_refresh", 401),
    (
        "/v1/entitlements/manifest", "get", "SELAHCUE_THROTTLE_DEVICE_READ",
        "entitlement_manifest", 401,
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize("path,method,setting,scope,allowed_status", ROUTES)
def test_every_shared_route_has_remaining_headers_without_changing_budget_or_body(
    client, settings, local_clock, path, method, setting, scope, allowed_status,
):
    setattr(settings, setting, (1, 60))

    def call():
        if method == "get":
            return client.get(path, REMOTE_ADDR="203.0.113.19")
        return client.post(
            path, data="{}", content_type="application/json", REMOTE_ADDR="203.0.113.19"
        )

    assert call().status_code == allowed_status
    local_clock[0] += 23.2
    refused = call()
    assert refused.status_code == 429
    assert refused["Cache-Control"] == "no-store"
    assert refused["Retry-After"] == "37", "must be the remaining window, rounded up"
    assert refused.json() == {
        "error": {"code": "RATE_LIMITED", "message": SAFE_MESSAGES[ErrorCode.RATE_LIMITED]},
        "surface": "desktop", "operation": scope,
    }
    local_clock[0] = 1059.99
    final_second = call()
    assert final_second.status_code == 429
    assert final_second["Retry-After"] == "1"
    local_clock[0] = 1060.0
    assert call().status_code == allowed_status, "reading expiry must not extend the budget"
    renewed = call()
    assert renewed.status_code == 429
    assert renewed["Retry-After"] == "60"


def test_local_expiry_uses_the_real_versioned_key_and_does_not_touch_its_deadline(local_clock):
    store = CacheStore(cache)
    assert store.incr_with_expiry("throttle:test:203.0.113.3", 60) == 1
    local_clock[0] += 58.01
    assert store.retry_after("throttle:test:203.0.113.3", 60) == 2
    local_clock[0] += 1.99
    assert store.incr_with_expiry("throttle:test:203.0.113.3", 60) == 1
    assert store.retry_after("throttle:test:203.0.113.3", 60) == 60


def test_expired_metadata_between_denial_and_read_reports_one_second(local_clock):
    store = CacheStore(cache)
    store.incr_with_expiry("throttle:expired", 60)
    local_clock[0] += 60
    assert store.retry_after("throttle:expired", 60) == 1


def test_unknown_or_persistent_backend_metadata_has_a_bounded_hint(local_clock):
    unknown = CacheStore(DummyCache("unused", {}))
    assert unknown.retry_after("throttle:unknown", 60) == 60
    cache.set("throttle:persistent", 99, timeout=None)
    assert CacheStore(cache).retry_after("throttle:persistent", 60) == 60


def test_a_clock_adjustment_cannot_emit_more_than_the_configured_window(local_clock):
    store = CacheStore(cache)
    store.incr_with_expiry("throttle:clock", 60)
    local_clock[0] -= 120
    assert store.retry_after("throttle:clock", 60) == 60


def test_retry_metadata_error_does_not_turn_an_established_denial_into_an_error(local_clock):
    store = CacheStore(cache)
    store.incr_with_expiry("throttle:error", 60)
    # Corrupt metadata stands in for a backend TTL-read failure after counter success.
    backend = caches["default"]
    key = backend.make_and_validate_key("throttle:error")
    with backend._lock:
        backend._expire_info[key] = "secret-backend-error"
    assert store.retry_after("throttle:error", 60) == 60
    with backend._lock:
        del backend._expire_info[key]
        del backend._cache[key]


def test_only_a_denial_queries_retry_metadata(monkeypatch, local_clock, settings):
    settings.SELAHCUE_HEADER_PROBE = (1, 60)
    calls = []
    original = CacheStore.retry_after

    def observe(store, key, window):
        calls.append(key)
        return original(store, key, window)

    monkeypatch.setattr(CacheStore, "retry_after", observe)
    view = throttle("header_probe", "SELAHCUE_HEADER_PROBE", (1, 60))(
        lambda request: JsonResponse({"ok": True})
    )
    request = RequestFactory().get("/probe", REMOTE_ADDR="203.0.113.2")
    assert view(request).status_code == 200
    assert calls == []
    assert view(request).status_code == 429
    assert calls == ["throttle:header_probe:203.0.113.2"]


@pytest.mark.skipif(not os.getenv("CACHE_URL"), reason="real Redis requires CACHE_URL")
def test_real_redis_remaining_expiry_is_read_from_the_existing_counter():
    backend = RedisCache(
        os.environ["CACHE_URL"],
        {"KEY_PREFIX": "header-probe", "VERSION": 9, "OPTIONS": {"socket_connect_timeout": 0.5, "socket_timeout": 0.5}},
    )
    key = f"throttle:headers:{uuid.uuid4()}"
    store = CacheStore(backend)
    redis_key = backend.make_and_validate_key(key)
    redis_client = backend._cache.get_client(redis_key, write=True)
    try:
        assert store.incr_with_expiry(key, 60) == 1
        redis_client.pexpire(redis_key, 2500)
        before = redis_client.pttl(redis_key)
        retry = store.retry_after(key, 60)
        after = redis_client.pttl(redis_key)
        assert before > 0 and after > 0, "fixture window expired before observation"
        assert math.ceil(after / 1000) <= retry <= math.ceil(before / 1000)
        assert 1 <= retry <= 3, "must read actual expiry rather than return the full 60s"
        assert backend.get(key) == 1, "TTL read must not spend or reset the budget"
    finally:
        backend.delete(key)
        redis_client.close()
        redis_client.connection_pool.disconnect()
        backend.close()


@pytest.mark.parametrize("ttl,expected", [(37001, 38), (1, 1), (0, 1), (-2, 1), (-1, 60)])
def test_redis_expiry_adapter_uses_primary_versioned_key(monkeypatch, ttl, expected):
    backend = RedisCache("redis://unused.invalid/1", {"KEY_PREFIX": "probe", "VERSION": 8})
    observed = []

    class ExpiryClient:
        def pttl(self, key):
            observed.append(key)
            return ttl

    def primary_client(key, *, write=False):
        assert write is True, "read replicas may lag behind the counter decision"
        return ExpiryClient()

    monkeypatch.setattr(backend._cache, "get_client", primary_client)
    assert CacheStore(backend).retry_after("throttle:probe", 60) == expected
    assert observed == [backend.make_and_validate_key("throttle:probe")]


def test_metadata_exception_preserves_the_complete_429_response(
    local_clock, settings, monkeypatch,
):
    settings.SELAHCUE_HEADER_PROBE = (1, 60)
    view = throttle("header_probe", "SELAHCUE_HEADER_PROBE", (1, 60))(
        lambda request: JsonResponse({"ok": True})
    )
    request = RequestFactory().get("/probe", REMOTE_ADDR="203.0.113.2")
    assert view(request).status_code == 200

    def broken_metadata(value):
        raise RuntimeError("secret backend detail must not escape")

    monkeypatch.setattr(services.math, "ceil", broken_metadata)
    response = view(request)
    assert response.status_code == 429
    assert response["Cache-Control"] == "no-store"
    assert response["Retry-After"] == "60"
    assert b"secret" not in response.content
    assert response.content == (
        b'{"error": {"code": "RATE_LIMITED", "message": "Too many requests."}, '
        b'"surface": "desktop", "operation": "header_probe"}'
    )
