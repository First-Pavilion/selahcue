"""Use an explicitly disposable Redis endpoint supplied by the integration runner."""
from concurrent.futures import ThreadPoolExecutor
import os
from time import monotonic, sleep
from uuid import uuid4

import pytest
from django.core.cache import caches
from redis import Redis

from selahcue_api.apps.throttling import cloud, services
from selahcue_api.apps.throttling.circuit import CacheCircuit
from selahcue_api.apps.throttling.services import BudgetOutcome

pytestmark = pytest.mark.django_db


@pytest.fixture
def budget_redis(settings):
    url = os.getenv("TEST_STT_REDIS_URL")
    if url is None:
        pytest.skip("Set TEST_STT_REDIS_URL to a disposable Redis endpoint")
    prefix = f"task5-{uuid4().hex}"
    settings.CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": url, "KEY_PREFIX": prefix,
        "OPTIONS": {"socket_connect_timeout": 0.2, "socket_timeout": 0.2},
    }}
    store = Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1)
    assert store.ping()
    yield store
    keys = list(store.scan_iter(match=f"{prefix}:*"))
    if keys:
        store.delete(*keys)
    store.close()


def check(kind="admission", device=1, org=42):
    return cloud.evaluate_cloud_budget(org_id=org, device_id=device, kind=kind)


def keys(kind="admission", device=1, org=42):
    return tuple(caches["default"].make_and_validate_key(key) for key in cloud._raw_keys(org, device, kind))


def test_paired_concurrent_admissions_refuse_without_partial_count(budget_redis):
    with ThreadPoolExecutor(max_workers=10) as workers:
        decisions = list(workers.map(lambda _: check(), range(37)))
        others = list(workers.map(lambda index: check(device=2 + index % 3), range(65)))
    assert sum(result.outcome == BudgetOutcome.ALLOWED for result in decisions) == 10
    assert sum(result.outcome == BudgetOutcome.ALLOWED for result in others) == 20
    assert budget_redis.mget(*keys()) == [b"30", b"10"]
    assert all(1 <= result.retry_after_seconds <= 3600 for result in decisions if result.retry_after_seconds)
    org_key, device_key = keys()
    assert org_key.endswith("cloud:v1:{org:42}:admission:org")
    assert device_key.endswith("cloud:v1:{org:42}:admission:device:1")


def test_renewal_and_quota_have_separate_fixed_windows(budget_redis):
    for _ in range(15):
        assert check("renewal").outcome == BudgetOutcome.ALLOWED
    assert check("renewal").outcome == BudgetOutcome.DENIED
    assert check().outcome == BudgetOutcome.ALLOWED
    for _ in range(120):
        assert check("quota").outcome == BudgetOutcome.ALLOWED
    assert check("quota").outcome == BudgetOutcome.DENIED
    quota_key, = keys("quota")
    budget_redis.pexpire(quota_key, 80)
    started = monotonic()
    assert check("quota").retry_after_seconds == 1
    assert budget_redis.pttl(quota_key) <= 80
    while budget_redis.exists(quota_key):
        assert monotonic() - started < 1
        sleep(0.01)
    assert check("quota").outcome == BudgetOutcome.ALLOWED
    assert budget_redis.get(quota_key) == b"1"
    assert 3590 <= budget_redis.ttl(quota_key) <= 3600


@pytest.mark.parametrize("bad", [b"0", b"-1", b"+1", b"01", b"1.0", b"2147483648", b"\xff"])
def test_corrupt_second_counter_refuses_before_first_write(budget_redis, bad):
    org, device = keys()
    budget_redis.set(device, bad)
    assert check().outcome == BudgetOutcome.STORE_UNAVAILABLE
    assert budget_redis.get(org) is None
    assert budget_redis.get(device) == bad


def test_persistent_exhausted_counter_repairs_without_extending_existing_ttl(budget_redis):
    org, device = keys()
    budget_redis.set(org, 1, px=20000)
    budget_redis.set(device, 10)
    result = check()
    assert (result.outcome, result.retry_after_seconds) == (BudgetOutcome.DENIED, 3600)
    assert budget_redis.mget(org, device) == [b"1", b"10"]
    assert 0 < budget_redis.pttl(org) <= 20_000
    assert budget_redis.ttl(device) == 3600


def test_lost_reply_does_not_repeat_or_refund_real_redis_writes(budget_redis, monkeypatch):
    original = cloud._eval_budget
    calls = 0

    def lost(*args):
        nonlocal calls
        calls += 1
        original(*args)
        raise ConnectionError("synthetic reply loss")

    monkeypatch.setattr(cloud, "_eval_budget", lost)
    decision = check()
    assert decision == cloud.CloudBudgetDecision(BudgetOutcome.STORE_UNAVAILABLE, 3600)
    assert calls == 1
    assert budget_redis.mget(*keys()) == [b"1", b"1"]


def test_locmem_cannot_admit_and_store_circuit_fails_closed(settings, monkeypatch):
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "cloud-unavailable"},
    }
    settings.CACHE_CIRCUIT_FAILURE_THRESHOLD = 1
    settings.CACHE_CIRCUIT_COOLDOWN = 30
    monkeypatch.setattr(services, "CACHE_CIRCUIT", CacheCircuit())
    assert check().outcome == BudgetOutcome.STORE_UNAVAILABLE

    def unexpected(*args):
        pytest.fail("An open circuit contacted the store")

    monkeypatch.setattr(cloud, "_eval_budget", unexpected)
    assert check() == cloud.CloudBudgetDecision(BudgetOutcome.STORE_UNAVAILABLE, 3600)


def test_partial_script_write_refuses_and_does_not_refund(budget_redis, monkeypatch):
    monkeypatch.setattr(cloud, "_SCRIPT", """
    redis.call('SET', KEYS[1], 1, 'EX', 3600)
    return redis.error_reply('ERR synthetic partial write')
    """)
    assert check() == cloud.CloudBudgetDecision(BudgetOutcome.STORE_UNAVAILABLE, 3600)
    assert budget_redis.mget(*keys()) == [b"1", None]


def test_startup_rejects_earlier_redis_hash_tag(settings):
    from django.apps import apps
    from django.core.exceptions import ImproperlyConfigured

    settings.CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:1/0", "KEY_PREFIX": "earlier:{other}",
    }}
    with pytest.raises(ImproperlyConfigured, match="cloud budget hash tag"):
        apps.get_app_config("selahcue_throttling").ready()
    assert check().outcome == BudgetOutcome.STORE_UNAVAILABLE


def test_real_refused_local_connection_denies_without_retry_hint_lookup(settings):
    import socket

    with socket.socket() as unused:
        unused.bind(("127.0.0.1", 0))
        port = unused.getsockname()[1]
        settings.CACHES = {"default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": f"redis://127.0.0.1:{port}",
            "OPTIONS": {"socket_connect_timeout": 0.1, "socket_timeout": 0.1},
        }}
        started = monotonic()
        assert check() == cloud.CloudBudgetDecision(BudgetOutcome.STORE_UNAVAILABLE, 3600)
        assert monotonic() - started < 1
