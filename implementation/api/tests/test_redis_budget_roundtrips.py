"""Real Redis wire/count/TTL evidence for 17tnw2b1wvf.

Do not infer round trips from Django cache API calls: redis-py may send more
than one command, while a pipeline can send several commands in one packet.
The counting wrapper observes actual packed-command writes; initialization
and control writes are reported separately from packets carrying budget keys.
"""

import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.core.cache import cache, caches
from django.core.cache.backends.redis import RedisCache
from redis import Redis
from redis.connection import Connection
from redis.exceptions import ConnectionError as RedisConnectionError

from selahcue_api.apps.throttling.services import BudgetOutcome, CacheStore, evaluate_budget

pytestmark = pytest.mark.django_db


@pytest.fixture
def redis_counter():
    if not os.getenv("CACHE_URL"):
        if os.getenv("CI"):
            pytest.fail("the mandatory hosted Redis budget gate requires CACHE_URL")
        pytest.skip("real Redis counter controls require CACHE_URL")
    backend = caches["default"]
    assert isinstance(backend, RedisCache), "this gate must exercise the real Redis backend"
    cache.clear()
    key = f"throttle:wvf:{uuid.uuid4().hex}"
    redis_key = backend.make_and_validate_key(key)
    raw = backend._cache.get_client(redis_key, write=True)
    assert raw.ping(), "the Redis control connection must work before any budget assertion"
    try:
        yield backend, raw, key, redis_key
    finally:
        raw.delete(redis_key)
        cache.clear()


def test_an_accepted_three_budget_request_uses_at_most_three_actual_redis_roundtrips(
    client, settings, monkeypatch, redis_counter,
):
    backend, raw, _, _ = redis_counter
    for name in (
        "SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL", "SELAHCUE_THROTTLE_RESET_REQUEST",
        "SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS",
    ):
        setattr(settings, name, (50, 60))
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    writes = []
    spends = []
    real_send = Connection.send_packed_command
    real_spend = CacheStore.incr_with_expiry

    def record_send(connection, command, *args, **kwargs):
        packed = command if isinstance(command, bytes) else b"".join(command)
        parts = packed.split(b"\r\n", 3)
        assert len(parts) == 4 and parts[0].startswith(b"*"), "unknown Redis wire frame"
        writes.append({
            "operation": parts[2].decode("ascii").upper(),
            "budget": b"throttle:password_reset_request" in packed,
        })
        return real_send(connection, command, *args, **kwargs)

    def record_spend(store, key, window):
        count = real_spend(store, key, window)
        spends.append((key, window, count))
        return count

    monkeypatch.setattr(Connection, "send_packed_command", record_send)
    monkeypatch.setattr(CacheStore, "incr_with_expiry", record_spend)
    # Force one new connection so initialization is observed rather than silently
    # omitted; it is not charged to the accepted request's budget packet ceiling.
    raw.connection_pool.disconnect()
    measurements = {}
    for phase in ("first-hit", "existing-counter"):
        writes.clear()
        spends.clear()
        response = client.post(
            "/graphql/account",
            data=json.dumps({"query": 'mutation { requestPasswordReset(email: "missing@wvf.example") { accepted } }'}),
            content_type="application/json", REMOTE_ADDR="203.0.113.81",
        )
        assert response.status_code == 200, response.content
        assert response.json() == {"data": {"requestPasswordReset": {"accepted": True}}}
        assert [key.split(":")[1] for key, _, _ in spends] == [
            "password_reset_request_global", "password_reset_request_ip", "password_reset_request_addr",
        ]
        assert len({key for key, _, _ in spends}) == 3
        expected_count = 1 if phase == "first-hit" else 2
        assert [(window, count) for _, window, count in spends] == [(60, expected_count)] * 3
        budget = [entry["operation"] for entry in writes if entry["budget"]]
        control = [entry["operation"] for entry in writes if not entry["budget"]]
        measurements[phase] = {"budgetPackets": len(budget), "budgetOperations": budget,
                               "connectionAndControlPackets": len(control), "controlOperations": control}
    print("WVF_REAL_REDIS_WIRE " + json.dumps(measurements, sort_keys=True), flush=True)
    # Assert only after both measurements are captured: a first-hit regression
    # must not hide the independent existing-counter measurement (or vice versa).
    for phase, result in measurements.items():
        assert 1 <= result["budgetPackets"] <= 3, (phase, result)


def test_real_redis_fixed_window_starts_at_first_hit_and_is_not_extended(redis_counter):
    backend, raw, key, redis_key = redis_counter
    store = CacheStore(backend)
    assert store.incr_with_expiry(key, 60) == 1
    assert 0 < raw.pttl(redis_key) <= 60_000
    assert raw.pexpire(redis_key, 30_000)
    before = raw.pttl(redis_key)
    assert store.incr_with_expiry(key, 60) == 2
    after = raw.pttl(redis_key)
    assert 0 < after <= before <= 30_000, "a repeated hit restarted the fixed window"
    assert store.incr_with_expiry(key, 60) == 3
    assert 0 < raw.pttl(redis_key) <= after


def test_real_redis_expired_counter_restarts_at_one_with_an_expiry(redis_counter):
    backend, raw, key, redis_key = redis_counter
    store = CacheStore(backend)
    assert store.incr_with_expiry(key, 60) == 1
    # Redis expires this key immediately; no scheduler sleep or guessed clock
    # delay is needed to establish the missing-key rollover boundary.
    assert raw.pexpire(redis_key, 0)
    assert raw.pttl(redis_key) == -2
    assert store.incr_with_expiry(key, 60) == 1
    assert 0 < raw.pttl(redis_key) <= 60_000


def test_real_redis_counter_does_not_leave_an_existing_persistent_key(redis_counter):
    backend, raw, key, redis_key = redis_counter
    assert raw.set(redis_key, 7)
    assert raw.pttl(redis_key) == -1, "the negative setup must really be persistent"
    assert CacheStore(backend).incr_with_expiry(key, 60) == 8
    assert int(raw.get(redis_key)) == 8, "repair must retain the count rather than granting a reset"
    assert 0 < raw.pttl(redis_key) <= 60_000, "counter remained permanently throttled without expiry"


def test_real_redis_concurrent_first_hits_have_exact_counts_and_an_expiry(redis_counter):
    backend, raw, key, redis_key = redis_counter
    barrier = threading.Barrier(8)

    def spend(_):
        barrier.wait(timeout=10)
        return CacheStore(backend).incr_with_expiry(key, 60)

    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(spend, range(32)))
    assert sorted(results) == list(range(1, 33)), "concurrent calls lost or duplicated counter units"
    assert int(raw.get(redis_key)) == 32
    assert 0 < raw.pttl(redis_key) <= 60_000


def test_real_redis_recreation_with_a_lost_reply_cannot_leave_a_persistent_key(
    redis_counter, monkeypatch,
):
    backend, raw, key, redis_key = redis_counter
    store = CacheStore(backend)
    assert store.incr_with_expiry(key, 60) == 1
    real_execute = Redis.execute_command
    injected = []

    def reply_lost_after_write(client, *args, **kwargs):
        operation = args[0].decode() if isinstance(args[0], bytes) else str(args[0])
        carries_key = redis_key in args or redis_key.encode() in args
        if (not injected and carries_key
                and operation.upper() in {"INCR", "INCRBY", "EVAL", "EVALSHA"}):
            # Expire at the actual Redis command boundary. The old split path
            # has already passed EXISTS; an atomic path sees a missing key.
            assert real_execute(client, "PEXPIRE", redis_key, 0) == 1
            reply = real_execute(client, *args, **kwargs)
            assert int(reply) == 1
            injected.append(operation.upper())
            # Simulate a lost successful reply at the client boundary, after
            # the real Redis write. No mocked counter outcome or fake TTL.
            raise RedisConnectionError("test-only lost counter reply")
        return real_execute(client, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Redis, "execute_command", reply_lost_after_write)
        outcome = evaluate_budget(store, key, 10, 60)
    assert len(injected) == 1, "the failure control never reached the actual write boundary"
    assert outcome is BudgetOutcome.STORE_UNAVAILABLE, "caller outage policy must retain the unavailable outcome"
    assert int(raw.get(redis_key)) == 1
    assert 0 < raw.pttl(redis_key) <= 60_000, "a lost reply stranded the recreated counter permanently"
    print("WVF_LOST_REPLY_CONTROL " + json.dumps({"operation": injected[0], "outcome": outcome.value}), flush=True)


def test_real_redis_invalid_counter_is_unavailable_without_destroying_its_state(redis_counter):
    backend, raw, key, redis_key = redis_counter
    assert raw.set(redis_key, "not-an-integer", ex=60)
    before = raw.pttl(redis_key)
    assert evaluate_budget(CacheStore(backend), key, 10, 60) is BudgetOutcome.STORE_UNAVAILABLE
    assert raw.get(redis_key) == b"not-an-integer"
    assert 0 < raw.pttl(redis_key) <= before
