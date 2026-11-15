"""Small fixed fake-provider mixed-load check; no production performance claim."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from threading import Event, Lock
from time import monotonic, sleep

import pytest
from django.db import connection, connections
from django.test import Client

from provider_helpers import cold_provider_cache, provider_mounts  # noqa: F401
from selahcue_api.apps.providers import sessions
from selahcue_api.apps.providers.contracts import MintFailureCode, OutcomeUnknown
from selahcue_api.apps.providers.minting import MintReceipt
from selahcue_api.apps.throttling.cloud import evaluate_cloud_budget
from test_cloud_grant_postgres import command, current, live_org, real_budget, token_for, wire  # noqa: F401
from test_effective_org_plan import device

pytestmark = pytest.mark.django_db(transaction=True)


def p95(values):
    return sorted(values)[ceil(0.95 * len(values)) - 1]


def test_fake_mint_failures_under_concurrent_grant_and_refresh(live_org, real_budget, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL is required for this load measurement")
    _, key, _, _, _ = live_org("PRO")
    tokens = [token_for(device(key))[1] for _ in range(32)]
    lock = Lock()
    monitor_stop = Event()
    connections_seen = []
    activity = {"workers": 0, "peak_workers": 0, "mints": 0, "peak_mints": 0}

    def observe():
        try:
            with connection.cursor() as cursor:
                while not monitor_stop.is_set():
                    cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
                    connections_seen.append(cursor.fetchone()[0])
                    monitor_stop.wait(0.015)
        finally:
            connections.close_all()

    def slow_rate(**kwargs):
        sleep(0.012)
        return evaluate_cloud_budget(**kwargs)

    def bounded_failure(*args, **kwargs):
        assert all(connections[alias].connection is None for alias in connections)
        with lock:
            activity["mints"] += 1
            activity["peak_mints"] = max(activity["mints"], activity["peak_mints"])
        try:
            sleep(0.16)
            return MintReceipt(OutcomeUnknown(MintFailureCode.TRANSPORT_TIMEOUT), None)
        finally:
            with lock:
                activity["mints"] -= 1

    monkeypatch.setattr(sessions, "read_stt_readiness", current)
    monkeypatch.setattr(sessions, "evaluate_cloud_budget", slow_rate)
    monkeypatch.setattr(sessions, "mint", bounded_failure)

    def request(raw, name, queued):
        started = monotonic()
        with lock:
            activity["workers"] += 1
            activity["peak_workers"] = max(activity["workers"], activity["peak_workers"])
        try:
            path = "/v1/stt/session" if name == "grant" else "/v1/license:refresh"
            payload = wire(command()) if name == "grant" else {}
            result = Client().post(path, payload, content_type="application/json",
                                   headers={"Authorization": f"Bearer {raw}"})
            return name, result.status_code, monotonic() - queued, started - queued
        finally:
            with lock:
                activity["workers"] -= 1
            connections.close_all()

    with ThreadPoolExecutor(max_workers=9) as pool:
        sampler = pool.submit(observe)
        try:
            baseline = [pool.submit(request, raw, "refresh", monotonic()) for raw in tokens[16:]]
            baseline = [future.result(timeout=10) for future in baseline]
            queued = monotonic()
            futures = [pool.submit(request, raw, "grant" if index % 4 == 0 else "refresh", queued)
                       for index, raw in enumerate(tokens)]
            measured = [future.result(timeout=15) for future in futures]
        finally:
            monitor_stop.set()
            sampler.result(timeout=5)
    counts = Counter((name, status) for name, status, _, _ in measured)
    assert counts == {("grant", 503): 8, ("refresh", 200): 24}
    assert all(status == 200 for _, status, _, _ in baseline)
    assert connections_seen and max(connections_seen) <= 11
    assert activity["peak_workers"] >= 4 and activity["peak_mints"] >= 2
    print(
        "FAKE provider load 32 mixed +16 baseline, eight request workers and one observer; "
        f"statuses={dict(counts)}, grant p95={p95([elapsed for name, _, elapsed, _ in measured if name == 'grant']):.3f}s, "
        f"refresh p95={p95([elapsed for name, _, elapsed, _ in measured if name == 'refresh']):.3f}s, "
        f"baseline refresh p95={p95([elapsed for _, _, elapsed, _ in baseline]):.3f}s, "
        f"all queue p95={p95([wait for _, _, _, wait in measured]):.3f}s, peak PG sessions={max(connections_seen)}, "
        f"peak request workers={activity['peak_workers']}, peak fake mints={activity['peak_mints']}"
    )


def test_two_request_slots_both_waiting_on_mint_queue_refresh(live_org, real_budget, monkeypatch):
    from threading import Barrier

    _, key, _, _, _ = live_org()
    raws = [token_for(device(key))[1] for _ in range(3)]
    in_mint = Barrier(3, timeout=5)

    def stalled_mint(*args, **kwargs):
        assert not any(connections[alias].connection for alias in connections)
        in_mint.wait()
        sleep(3.25)
        return MintReceipt(OutcomeUnknown(MintFailureCode.TRANSPORT_TIMEOUT), None)

    monkeypatch.setattr(sessions, "read_stt_readiness", current)
    monkeypatch.setattr(sessions, "mint", stalled_mint)

    def post(path, raw, payload, submitted):
        entered = monotonic()
        try:
            response = Client().post(path, payload, content_type="application/json",
                                     headers={"Authorization": f"Bearer {raw}"})
            return response.status_code, entered - submitted, monotonic() - submitted
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        stalled = [
            pool.submit(post, "/v1/stt/session", raw, wire(command()), monotonic()) for raw in raws[:2]
        ]
        in_mint.wait()
        delayed = pool.submit(post, "/v1/license:refresh", raws[2], {}, monotonic())
        assert [future.result(timeout=6)[0] for future in stalled] == [503, 503]
        status, wait, elapsed = delayed.result(timeout=6)
        assert status == 200 and wait >= 3
        print(f"FAKE two-slot saturation: refresh returned {status} after {elapsed:.3f}s, queue {wait:.3f}s")
