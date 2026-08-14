"""Rate limiting for the /v1 device-auth surface.

Two load-bearing tests here:

- `spoofed_forwarded_for_is_ignored_by_default`: behind a proxy, trusting a caller-supplied
  X-Forwarded-For lets anyone mint a fresh identity per request and bypass the limiter.
- `rollover_race_never_leaves_the_counter_without_a_ttl`: Django's Redis `incr()` is
  `EXISTS` then `INCR`. A TTL lapse between them makes Redis recreate the key with NO
  expiry, and that caller is then rate-limited forever. `FakeCache` below exists to make
  that observable — the original `FakeStore` had no clock, so no test could see a window
  expire and the ValueError branch never executed once.
"""

import json
import logging

import pytest
from django.core.cache import cache
from django.test import RequestFactory

from selahcue_api.apps.throttling import services
from selahcue_api.apps.throttling.services import CacheStore, client_ip, should_allow


class FakeStore:
    """Minimal store double for the limit arithmetic — no cache semantics, no clock."""

    def __init__(self, raise_on_use=False):
        self.data = {}
        self.raise_on_use = raise_on_use

    def incr_with_expiry(self, key, window_seconds):
        if self.raise_on_use:
            raise RuntimeError("redis down")
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]


class FakeClock:
    def __init__(self, now=1_000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeCache:
    """A Django cache API double with REDIS semantics and an injected clock.

    Faithful where it matters:

    - `add()` is `SET NX EX` — one atomic step, so it always carries an expiry.
    - `incr()` is `EXISTS` **then** `INCR` — two round trips, exactly as
      `django/core/cache/backends/redis.py` implements it.
    - `INCR` on a key that has vanished between those two steps recreates it at 1 with
      **no expiry**, which is the defect this suite has to be able to see.
    - `touch()` is `EXPIRE`.

    `before_exists` / `after_exists` fire once each, at the two points a real TTL can lapse.
    """

    def __init__(self, clock):
        self._clock = clock
        self.values = {}
        self.expires = {}  # key -> deadline, or None meaning PERSISTENT (no TTL)
        self.before_exists = None
        self.after_exists = None

    # -- internals ---------------------------------------------------------
    def _drop_expired(self):
        now = self._clock()
        for key in [k for k, at in self.expires.items() if at is not None and at <= now]:
            del self.values[key]
            del self.expires[key]

    def _fire(self, name):
        hook = getattr(self, name)
        if hook is not None:
            setattr(self, name, None)  # one-shot
            hook()

    # -- cache API ---------------------------------------------------------
    def add(self, key, value, timeout):
        self._drop_expired()
        if key in self.values:
            return False
        self.values[key] = value
        self.expires[key] = self._clock() + timeout
        return True

    def incr(self, key, delta=1):
        self._fire("before_exists")
        self._drop_expired()
        exists = key in self.values  # round trip 1: EXISTS
        self._fire("after_exists")
        if not exists:
            raise ValueError(f"Key '{key}' not found.")
        self._drop_expired()
        if key not in self.values:  # round trip 2: INCR, and the key is gone
            self.values[key] = delta
            self.expires[key] = None  # Redis INCR creates a PERSISTENT key
            return delta
        self.values[key] += delta
        return self.values[key]

    def touch(self, key, timeout):
        self._drop_expired()
        if key not in self.values:
            return False
        self.expires[key] = self._clock() + timeout
        return True


@pytest.fixture(autouse=True)
def _reset_store_error_log_throttle(monkeypatch):
    """`should_allow` reports a store outage at most once a minute via module state."""
    monkeypatch.setattr(services, "_last_store_error_log", float("-inf"))


# --- limit arithmetic ------------------------------------------------------
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


def test_store_outage_logs_once_per_window_without_a_traceback(caplog):
    """CLAUDE.md forbids unbounded logs. `logger.exception` per failing request meant
    ~30,000 tracebacks in a five-minute outage at 100 rps."""
    store = FakeStore(raise_on_use=True)
    with caplog.at_level(logging.WARNING, logger=services.logger.name):
        for _ in range(200):
            assert should_allow(store, "k", 1, 60) is True

    records = [r for r in caplog.records if "rate-limit store unavailable" in r.getMessage()]
    assert len(records) == 1, f"expected one report per outage, got {len(records)}"
    assert records[0].levelno == logging.WARNING
    assert records[0].exc_info is None, "a traceback per request is the unbounded-log problem"


# --- window behaviour (needs the clock-injected cache) ---------------------
def test_window_expiry_resets_the_budget():
    """The gap that let the blocker ship: with no clock in the double, nothing could
    observe a window ending, so a limiter that never reset would have passed."""
    clock = FakeClock()
    store = CacheStore(FakeCache(clock))

    assert [should_allow(store, "k", 2, 60) for _ in range(3)] == [True, True, False]
    clock.advance(59)
    assert should_allow(store, "k", 2, 60) is False, "the window must not end early"
    clock.advance(2)
    assert should_allow(store, "k", 2, 60) is True, "a fresh window must restore the budget"
    assert should_allow(store, "k", 2, 60) is True
    assert should_allow(store, "k", 2, 60) is False


def test_expiry_before_the_existence_check_starts_a_fresh_window():
    """The harmless half of the race: the key lapses before incr()'s EXISTS, so incr()
    raises ValueError. The recovery must still leave the new window with a TTL."""
    clock = FakeClock()
    fake = FakeCache(clock)
    store = CacheStore(fake)

    assert should_allow(store, "k", 2, 60) is True
    fake.before_exists = lambda: clock.advance(61)
    assert should_allow(store, "k", 2, 60) is True
    assert fake.values["k"] == 1, "the lapsed window must restart at 1, not fail open"
    assert fake.expires["k"] is not None
    clock.advance(61)
    assert should_allow(store, "k", 2, 60) is True


def test_rollover_race_never_leaves_the_counter_without_a_ttl():
    """THE blocker. The TTL lapses between incr()'s EXISTS and its INCR, so Redis recreates
    the key at 1 with NO expiry. Under the old `add()` + `incr()` shape nothing could ever
    set that expiry again: `add()` fails (the key exists) and `incr()` never expires it, so
    the counter climbed monotonically and the key returned 429 forever, recoverable only by
    a manual DEL in Redis db 1."""
    clock = FakeClock()
    fake = FakeCache(clock)
    store = CacheStore(fake)

    assert should_allow(store, "k", 2, 60) is True  # add() starts the window

    # Alive at add(), gone by the time INCR lands.
    fake.after_exists = lambda: clock.advance(61)
    assert should_allow(store, "k", 2, 60) is True

    assert fake.expires["k"] is not None, (
        "INCR recreated the counter with no expiry — this key can now never expire, so it "
        "will return 429 permanently"
    )

    # And the limiter genuinely self-heals: the recreated window carries a real budget...
    assert should_allow(store, "k", 2, 60) is True
    assert should_allow(store, "k", 2, 60) is False
    # ...and then rolls over like any other window.
    clock.advance(61)
    assert should_allow(store, "k", 2, 60) is True


# --- client IP -------------------------------------------------------------
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


def test_forged_non_ip_entry_falls_back_to_remote_addr(settings):
    """With the hop count set higher than the real proxy depth, the selected entry is
    attacker-chosen text that would go straight into a cache key. Django only warns about an
    over-long key, so this bought a fresh limiter budget per request AND unbounded distinct
    Redis keys. Refusing to parse caps cardinality at real addresses."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 2
    forged = "A" * 300
    request = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR=f"{forged}, 1.2.3.4"
    )
    assert client_ip(request) == "10.0.0.9"

    # Same for the smaller forgeries: hostnames, empty-ish junk, and address:port.
    for entry in ("not-an-ip", "localhost", "1.2.3.4:5678", "999.999.999.999"):
        req = RequestFactory().get(
            "/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR=f"{entry}, 1.2.3.4"
        )
        assert client_ip(req) == "10.0.0.9", entry


def test_valid_ipv6_forwarded_entry_is_accepted(settings):
    """Validation must not become an accidental IPv4-only filter — that would collapse
    every IPv6 client onto the proxy's single bucket."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 1
    request = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="2001:db8::1"
    )
    assert client_ip(request) == "2001:db8::1"

    # Spelling is normalised, so one client cannot hold two budgets.
    expanded = RequestFactory().get(
        "/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="2001:0DB8:0:0:0:0:0:1"
    )
    assert client_ip(expanded) == "2001:db8::1"


# --- through the real view -------------------------------------------------
ACTIVATION_BODY = json.dumps(
    {
        "idempotency_key": "throttle-probe-1",
        "license_key": "nope",
        "device_fingerprint": "fp",
        "platform": "macos",
    }
)


@pytest.mark.django_db
def test_activation_returns_429_over_the_limit(client, settings):
    """Asserts the WHOLE sequence, not just the last response: inspecting only request 4
    would equally pass for a limiter that 429s everything, or one that denies from request 3."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    settings.SELAHCUE_THROTTLE_ACTIVATION = (2, 60)
    cache.clear()

    responses = [
        client.post("/v1/activations", data=ACTIVATION_BODY, content_type="application/json")
        for _ in range(4)
    ]
    codes = [r.status_code for r in responses]

    # Requests 1-2 are inside the budget: they reach the view and fail on the bogus key
    # (NOT_FOUND -> 404), which is what proves they were not refused by the limiter.
    assert codes[:2] == [404, 404], codes
    assert responses[0].json()["error"]["code"] == "NOT_FOUND"
    # Request 3 is the FIRST one refused — not earlier, not later.
    assert codes[2:] == [429, 429], codes
    assert responses[2].json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.django_db
def test_the_throttle_budget_is_per_client_ip(client, settings):
    """A decorator building `key = f"throttle:{scope}"` would satisfy every other test in
    this file while letting one noisy IP 429 the entire customer base."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1, 60)
    cache.clear()

    def post(remote_addr):
        return client.post(
            "/v1/activations",
            data=ACTIVATION_BODY,
            content_type="application/json",
            REMOTE_ADDR=remote_addr,
        ).status_code

    assert post("203.0.113.1") == 404  # reaches the view (bogus key) — spends the budget
    assert post("203.0.113.1") == 429  # ...and is refused
    assert post("203.0.113.2") == 404, "a second IP must have its own budget"
    assert post("203.0.113.2") == 429
