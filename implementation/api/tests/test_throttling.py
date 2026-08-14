"""Rate limiting for the /v1 device-auth surface.

The load-bearing test here is `spoofed_forwarded_for_is_ignored_by_default`: behind a
proxy, trusting a caller-supplied X-Forwarded-For lets anyone mint a fresh identity per
request and bypass the limiter entirely.
"""

import json

import pytest
from django.test import RequestFactory

from selahcue_api.apps.throttling.services import client_ip, should_allow


class FakeStore:
    """Minimal cache double — incr/expire semantics only, no Redis, no clock."""

    def __init__(self, raise_on_use=False):
        self.data = {}
        self.raise_on_use = raise_on_use

    def incr_with_expiry(self, key, window_seconds):
        if self.raise_on_use:
            raise RuntimeError("redis down")
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]


def test_allows_up_to_the_limit_then_denies():
    store = FakeStore()
    assert [should_allow(store, "k", 3, 60) for _ in range(3)] == [True, True, True]
    assert should_allow(store, "k", 3, 60) is False


def test_separate_keys_have_separate_budgets():
    store = FakeStore()
    for _ in range(3):
        should_allow(store, "a", 3, 60)
    assert should_allow(store, "a", 3, 60) is False
    assert should_allow(store, "b", 3, 60) is True


def test_fails_open_when_the_store_errors():
    """A Redis outage must not refuse device traffic — brute force is already
    infeasible, so denying everyone would cause the outage it aims to prevent."""
    store = FakeStore(raise_on_use=True)
    assert should_allow(store, "k", 1, 60) is True


def test_client_ip_uses_remote_addr_by_default(settings):
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.9")
    assert client_ip(request) == "10.0.0.9"


def test_spoofed_forwarded_for_is_ignored_by_default(settings):
    """THE test. Without this, the limiter is bypassable with one header."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    request = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="1.2.3.4"
    )
    assert client_ip(request) == "10.0.0.9"


def test_forwarded_for_is_read_only_from_the_trusted_hops(settings):
    """`SELAHCUE_TRUSTED_PROXY_COUNT = N` means the last N entries were written by our own
    proxies; the resolver takes the Nth-from-last. Everything to the LEFT of those entries
    was supplied by the caller and is forgeable."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 1
    request = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="1.2.3.4"
    )
    # One trusted hop, appending the socket peer it saw: that entry IS the real client.
    assert client_ip(request) == "1.2.3.4"

    # Same one hop, but the caller pre-seeded the header. The proxy appended the address it
    # actually saw, so the real client is still the rightmost entry — the planted 1.2.3.4
    # must NOT win, or one header buys a fresh budget per request.
    spoofed = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="1.2.3.4, 10.0.0.8"
    )
    assert client_ip(spoofed) == "10.0.0.8"

    # Two trusted hops (CDN → load balancer): the CDN appended the client, the LB appended
    # the CDN, so the client is second-from-last.
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 2
    two_hops = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="9.9.9.9, 1.2.3.4, 10.0.0.8"
    )
    assert client_ip(two_hops) == "1.2.3.4"


@pytest.mark.django_db
def test_activation_returns_429_over_the_limit(client, settings):
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    settings.SELAHCUE_THROTTLE_ACTIVATION = (2, 60)
    from django.core.cache import cache

    cache.clear()
    body = json.dumps({"idempotency_key": "x", "license_key": "nope",
                       "device_fingerprint": "fp", "platform": "macos"})
    last = None
    for _ in range(4):
        last = client.post("/v1/activations", data=body, content_type="application/json")
    assert last.status_code == 429
    assert last.json()["error"]["code"] == "RATE_LIMITED"
