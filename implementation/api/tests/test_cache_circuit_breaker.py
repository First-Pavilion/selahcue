"""Bound repeated outage cost without changing budget decisions (17tnw2b2kab)."""

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.redis import RedisCache

from selahcue_api import settings as project_settings
from selahcue_api.apps.accounts import services as account_services
from test_cache_socket_timeouts import (
    ACTIVATION_BODY, REQUEST_RESET, RESEND_VERIFICATION,
    StalledRedis, _CapturingSender, _account, _assert_every_request_accepted,
    _post_each, _watchdog, needs_sigalrm,
)

from selahcue_api.apps.throttling import services
from selahcue_api.apps.throttling.services import BudgetOutcome


pytestmark = pytest.mark.django_db


class FailingStore:
    def __init__(self):
        self.calls = 0

    def incr_with_expiry(self, key, window_seconds):
        self.calls += 1
        raise RuntimeError("private store failure")


def test_consecutive_errors_skip_store_across_identities():
    store = FailingStore()
    results = [services.evaluate_budget(store, f"identity-{n}", 3, 60) for n in range(10)]
    assert results == [BudgetOutcome.STORE_UNAVAILABLE] * 10
    assert store.calls == 3


@pytest.fixture
def clock(monkeypatch):
    # Replace only the circuit module's clock; other throttling/runtime timers remain real.
    state = SimpleNamespace(now=1000.0)
    monkeypatch.setattr("selahcue_api.apps.throttling.circuit.time", SimpleNamespace(monotonic=lambda: state.now))
    return state


def evaluate(store):
    return services.evaluate_budget(store, "private-test-key", 2, 60)


def trip(store=None):
    store = store or FailingStore()
    for _ in range(3):
        assert evaluate(store) is BudgetOutcome.STORE_UNAVAILABLE
    return store


def test_healthy_store_keeps_real_limits_and_success_resets_consecutive_errors(clock):
    broken = FailingStore()
    local = LocMemCache("circuit-healthy", {})
    local.clear()
    healthy = services.CacheStore(local)
    for _ in range(5):
        evaluate(broken)
        evaluate(broken)
        assert evaluate(healthy) in (BudgetOutcome.ALLOWED, BudgetOutcome.DENIED)
    assert broken.calls == 10
    local.clear()
    assert [evaluate(healthy) for _ in range(3)] == [BudgetOutcome.ALLOWED, BudgetOutcome.ALLOWED, BudgetOutcome.DENIED]


def test_cooldown_probe_failure_restarts_then_real_denial_closes(clock):
    broken = trip()
    clock.now += 4.99
    evaluate(broken)
    assert broken.calls == 3
    clock.now += 0.01
    assert evaluate(broken) is BudgetOutcome.STORE_UNAVAILABLE
    assert broken.calls == 4
    clock.now += 4.99
    evaluate(broken)
    assert broken.calls == 4
    clock.now += 0.01
    local = LocMemCache("circuit-denial-recovery", {})
    local.clear()
    healthy = services.CacheStore(local)
    # A successful cache operation that denies is still evidence the store recovered.
    assert services.evaluate_budget(healthy, "private-test-key", 0, 60) is BudgetOutcome.DENIED
    assert evaluate(healthy) is BudgetOutcome.ALLOWED
    evaluate(broken)
    assert broken.calls == 5


@pytest.mark.parametrize("probe_fails", [False, True])
def test_exactly_one_half_open_probe_without_lock_across_store(clock, probe_fails):
    trip()
    clock.now += 5
    entered = threading.Event()
    release = threading.Event()
    calls = []

    class BlockingStore:
        def incr_with_expiry(self, key, window):
            calls.append(key)
            entered.set()
            assert release.wait(5), "test did not release probe"
            if probe_fails:
                raise RuntimeError("private probe failure")
            return 1

    store = BlockingStore()
    barrier = threading.Barrier(17)

    def follower(n):
        barrier.wait(timeout=5)
        return evaluate(store)

    with ThreadPoolExecutor(max_workers=17) as pool:
        first = pool.submit(evaluate, store)
        assert entered.wait(5)
        followers = [pool.submit(follower, n) for n in range(16)]
        barrier.wait(timeout=5)
        try:
            # Followers must finish WHILE probe I/O remains blocked.
            assert [f.result(timeout=3) for f in followers] == [BudgetOutcome.STORE_UNAVAILABLE] * 16
            assert len(calls) == 1
        finally:
            release.set()
        assert first.result(timeout=5) is (BudgetOutcome.STORE_UNAVAILABLE if probe_fails else BudgetOutcome.ALLOWED)
    other = FailingStore()
    evaluate(other)
    assert other.calls == (0 if probe_fails else 1)


def test_late_success_cannot_close_newer_outage(clock):
    entered = threading.Event()
    release = threading.Event()

    class LateSuccess:
        def incr_with_expiry(self, key, window):
            entered.set()
            assert release.wait(5)
            return 1

    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(evaluate, LateSuccess())
        assert entered.wait(5)
        broken = trip()
        release.set()
        assert old.result(timeout=5) is BudgetOutcome.ALLOWED
    evaluate(broken)
    assert broken.calls == 3
    clock.now += 5
    assert evaluate(broken) is BudgetOutcome.STORE_UNAVAILABLE
    assert broken.calls == 4


def test_late_failure_cannot_extend_newer_outage_deadline(clock):
    entered = threading.Event()
    release = threading.Event()

    class LateFailure:
        def incr_with_expiry(self, key, window):
            entered.set()
            assert release.wait(5)
            raise RuntimeError("private stale error")

    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(evaluate, LateFailure())
        assert entered.wait(5)
        broken = trip()
        clock.now += 4
        release.set()
        assert old.result(timeout=5) is BudgetOutcome.STORE_UNAVAILABLE
    clock.now += 1
    evaluate(broken)
    assert broken.calls == 4, "old failure must not extend cooldown"


def test_stale_success_does_not_reset_newer_consecutive_error(clock):
    circuit = services.CACHE_CIRCUIT
    old_success = circuit.admit()
    broken = FailingStore()
    evaluate(broken)
    circuit.finish(old_success, success=True, threshold=3, cooldown=5)
    evaluate(broken)
    evaluate(broken)
    evaluate(broken)
    assert broken.calls == 3


def test_cancelled_probe_releases_slot_into_a_fresh_cooldown(clock):
    class Cancelled(BaseException):
        pass

    class CancelStore:
        def incr_with_expiry(self, key, window):
            raise Cancelled()

    trip()
    clock.now += 5
    with pytest.raises(Cancelled):
        evaluate(CancelStore())
    clock.now += 5
    local = LocMemCache("circuit-cancel-recovery", {})
    local.clear()
    assert evaluate(services.CacheStore(local)) is BudgetOutcome.ALLOWED


def test_ten_thousand_distinct_outage_identities_have_fixed_state(clock):
    broken = FailingStore()
    circuit = services.CACHE_CIRCUIT
    assert not hasattr(circuit, "__dict__")
    size = sys.getsizeof(circuit)
    for n in range(10_000):
        assert services.evaluate_budget(broken, f"unique-{n}", 1, 60) is BudgetOutcome.STORE_UNAVAILABLE
    assert broken.calls == 3
    assert sys.getsizeof(circuit) == size
    assert circuit._failures == 3
    assert circuit._generation == 3


def settings_child(**values):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CACHE_CIRCUIT_")}
    env.update(values)
    env.update(ENVIRONMENT="dev", DJANGO_SETTINGS_MODULE="selahcue_api.settings")
    return subprocess.run(
        [sys.executable, "-c", "import json; from django.conf import settings; print(json.dumps([settings.CACHE_CIRCUIT_FAILURE_THRESHOLD, settings.CACHE_CIRCUIT_COOLDOWN]))"],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=30,
    )


@pytest.mark.parametrize("threshold,cooldown", [("1", "0.1"), ("100", "60"), ("3", "5")])
def test_startup_accepts_documented_circuit_ranges(threshold, cooldown):
    result = settings_child(CACHE_CIRCUIT_FAILURE_THRESHOLD=threshold, CACHE_CIRCUIT_COOLDOWN=cooldown)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [int(threshold), float(cooldown)]


def test_startup_defaults_are_three_failures_five_seconds():
    result = settings_child()
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [3, 5.0]


@pytest.mark.parametrize("name,bad", [
    ("CACHE_CIRCUIT_FAILURE_THRESHOLD", value) for value in ("0", "101", "1.5", "nan", "inf", "private-secret-value")
] + [
    ("CACHE_CIRCUIT_COOLDOWN", value) for value in ("0", "0.09", "60.1", "nan", "inf", "-inf", "private-secret-value")
])
def test_startup_rejects_invalid_circuit_settings_without_echoing_value(name, bad):
    result = settings_child(**{name: bad})
    assert result.returncode != 0
    assert name in result.stderr
    assert f"got {bad}" not in result.stderr
    assert "private-secret-value" not in result.stderr


def test_runtime_tunables_control_trip_and_recovery(settings, clock):
    settings.CACHE_CIRCUIT_FAILURE_THRESHOLD = 1
    settings.CACHE_CIRCUIT_COOLDOWN = 0.1
    broken = FailingStore()
    evaluate(broken)
    evaluate(broken)
    assert broken.calls == 1
    clock.now += 0.1
    evaluate(broken)
    assert broken.calls == 2


@needs_sigalrm
def test_actual_silent_redis_opens_circuit_and_cooldown_calls_take_milliseconds(settings, capsys):
    server = StalledRedis()
    settings.CACHES = {"default": project_settings._cache_config(server.url, 0.2, 0.2)}
    store = services.CacheStore(cache)
    try:
        with _watchdog():
            started = time.perf_counter()
            for _ in range(3):
                assert evaluate(store) is BudgetOutcome.STORE_UNAVAILABLE
            stalled = time.perf_counter() - started
            assert stalled >= 0.54, "positive control must exercise three real read timeouts"
            assert server.connections_after_settling(3) == 3
            started = time.perf_counter()
            for n in range(50):
                assert services.evaluate_budget(store, f"cooldown-{n}", 2, 60) is BudgetOutcome.STORE_UNAVAILABLE
            skipped = time.perf_counter() - started
            assert skipped < 0.1, f"50 cooldown checks cost {skipped:.4f}s; expected milliseconds"
            assert server.connections_after_settling(3) == 3
            print(f"actual silent Redis: first3={stalled:.6f}s, cooldown50={skipped:.6f}s, connections=3")
    finally:
        cache.close()
        server.close()


@needs_sigalrm
@pytest.mark.parametrize("field,query,verified", [
    ("requestPasswordReset", REQUEST_RESET, True),
    ("resendVerificationEmail", RESEND_VERIFICATION, False),
])
def test_default_circuit_preserves_mail_outage_ceiling(client, settings, field, query, verified):
    sender = _CapturingSender()
    account_services.set_email_sender(sender)
    account_services._reset_reset_send_degraded_window()
    account_services._reset_degraded_send_window()
    settings.SELAHCUE_RESET_SEND_DEGRADED_CEILING = (1, 60)
    settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING = (1, 60)
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0
    server = StalledRedis()
    try:
        emails = [_account(sender, f"circuit-{n}@budget.example", f"circuit-account-{n}", verified=verified) for n in range(3)]
        sender.verify_tokens.clear()
        sender.reset_tokens.clear()
        settings.CACHES = {"default": project_settings._cache_config(server.url, 0.2, 0.2)}
        with _watchdog():
            responses, timings = _post_each(client, query, emails)
        _assert_every_request_accepted(responses, field)
        sent = sender.reset_tokens if verified else sender.verify_tokens
        assert len(sent) == 1
        assert server.connections_after_settling(3) == 3
        assert timings[0] >= 0.54, "initial request must really wait on three budget timeouts"
        assert max(timings[1:]) < 0.2, timings
        # Device activation retains fail-open policy on the SAME open circuit.
        response = client.post("/v1/activations", data=ACTIVATION_BODY, content_type="application/json")
        assert response.status_code == 404
        assert server.connections_after_settling(3) == 3
    finally:
        cache.close()
        server.close()
        account_services.set_email_sender(account_services.EmailSender())


def test_real_redis_healthy_limits_and_recovery_probe(clock):
    url = os.environ.get("SELAHCUE_CIRCUIT_TEST_REDIS_URL")
    if not url:
        pytest.skip("set SELAHCUE_CIRCUIT_TEST_REDIS_URL for a dedicated Redis integration run")
    backend = RedisCache(url, {"KEY_PREFIX": f"circuit-{uuid.uuid4()}"})
    store = services.CacheStore(backend)
    try:
        assert [evaluate(store) for _ in range(3)] == [BudgetOutcome.ALLOWED, BudgetOutcome.ALLOWED, BudgetOutcome.DENIED]
        broken = trip()
        assert evaluate(store) is BudgetOutcome.STORE_UNAVAILABLE
        clock.now += 5
        assert evaluate(store) is BudgetOutcome.DENIED
        # Probe success (including denial) closed circuit, so next error touches store.
        evaluate(broken)
        assert broken.calls == 4
    finally:
        backend.delete("private-test-key")
        backend._cache.get_client(write=True).connection_pool.disconnect()


@pytest.mark.parametrize("value", ["", "  "])
def test_blank_circuit_settings_use_defaults(value):
    result = settings_child(CACHE_CIRCUIT_FAILURE_THRESHOLD=value, CACHE_CIRCUIT_COOLDOWN=value)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [3, 5.0]


def test_failure_from_before_recovery_does_not_reopen_new_epoch(clock):
    entered = threading.Event()
    release = threading.Event()

    class OldFailure:
        def incr_with_expiry(self, key, window):
            entered.set()
            assert release.wait(5)
            raise RuntimeError("private old error")

    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(evaluate, OldFailure())
        assert entered.wait(5)
        trip()
        clock.now += 5
        backend = LocMemCache("circuit-recovered-epoch", {})
        backend.clear()
        assert evaluate(services.CacheStore(backend)) is BudgetOutcome.ALLOWED
        release.set()
        assert old.result(timeout=5) is BudgetOutcome.STORE_UNAVAILABLE
    broken = FailingStore()
    for _ in range(3):
        evaluate(broken)
    assert broken.calls == 3, "old error must not consume a failure in the recovered epoch"


def test_simultaneous_closed_failures_trip_without_serializing_store_io(clock):
    barrier = threading.Barrier(9)

    class ConcurrentFailures:
        def incr_with_expiry(self, key, window):
            barrier.wait(timeout=5)
            raise RuntimeError("private concurrent failure")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(evaluate, ConcurrentFailures()) for _ in range(8)]
        barrier.wait(timeout=5)
        assert [future.result(timeout=5) for future in futures] == [BudgetOutcome.STORE_UNAVAILABLE] * 8
    later = FailingStore()
    assert evaluate(later) is BudgetOutcome.STORE_UNAVAILABLE
    assert later.calls == 0
