"""Provider projection, durable cursor and health boundary tests."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import http.server
import json
import threading
import time
from uuid import uuid4

import pytest
from django.db import transaction

from provider_helpers import (
    DEEPGRAM, OPENAI, cold_provider_cache, identity, provider_mounts,
)
from test_effective_org_plan import church
from test_provider_reservation_binding import active_mapping
from selahcue_api.apps.providers.adapters import deepgram_usage as dg, openai_usage as oa
from selahcue_api.apps.providers.adapters import usage_transport
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.providers.contracts import ProvisioningAuditContext
from selahcue_api.apps.providers.policy_publication import publish_provider_policy
from selahcue_api.apps.usage.contracts import UTCInterval
from selahcue_api.apps.usage.health import read_provider_usage_health
from selahcue_api.apps.usage.models import ProviderUsageRecord, ProviderUsageVersion, ScopeUsageHealth, UsageScan
from selahcue_api.apps.usage.observation_contracts import (
    DGCompletion, ObservedCoverage, ScanPurpose, UsageFailureCode, UsageReadFailed, UsageRejected,
)
from selahcue_api.apps.usage.observations import ingest_observations
from selahcue_api.apps.usage.scans import _claim_page, enroll_scope, finish_scan, schedule_scan
from selahcue_api.apps.usage.usage_tasks import _claim_publication, claim_work, finish_work

NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)
COVERAGE = UTCInterval(NOW - timedelta(hours=24), NOW)


def dg_data(entries=(), page=0):
    return {"page": page, "limit": 100, "requests": list(entries)}


def request(request_id="synthetic-request", *, key=None, completed=True, duration=0.1, created=None):
    response = {"code": 200, "details": {"duration": duration, "transcript": "discard me"}}
    if completed:
        response["completed"] = max(NOW - timedelta(minutes=1), (created or COVERAGE.start) + timedelta(seconds=1)).isoformat()
    return {
        "request_id": request_id, "project_uuid": DEEPGRAM.parent_scope_id, "api_key_id": key,
        "created": (created or NOW - timedelta(minutes=2)).isoformat(), "response": response,
        "tag": "never trust me",
    }


def oa_data(*buckets, following=None):
    return {"object": "page", "data": buckets, "has_more": following is not None, "next_page": following}


def bucket(start, *results):
    return {"object": "bucket", "start_time": int(start.timestamp()),
            "end_time": int(start.timestamp()) + 3600, "results": results}


def result(input_tokens, output_tokens=1, **fields):
    return {"object": "organization.usage.completions.result", "input_tokens": input_tokens,
            "output_tokens": output_tokens, **fields}


def parse_dg(payload, *, interval=COVERAGE, cursor=None):
    return dg._parse_page(usage_transport.metadata_json(json.dumps(payload).encode()), DEEPGRAM, interval, cursor)


def parse_oa(payload, *, interval=COVERAGE, cursor=None):
    return oa._parse_page(usage_transport.metadata_json(json.dumps(payload).encode()), OPENAI, interval, cursor)


def test_deepgram_fields_and_immutable_half_open_boundary():
    unknown = request(completed=False)
    at_end = request("boundary", created=NOW)
    found = parse_dg(dg_data([unknown, at_end]))
    assert found.next_cursor is None
    assert found.receipt.terminal_page_seen is True
    assert len(found.records) == 1
    entry = found.records[0]
    assert (entry.completion, entry.completed_at, entry.duration_seconds, entry.api_key_id) == (
        DGCompletion.COMPLETION_UNKNOWN, None, Decimal("0.1"), None,
    )
    assert "discard me" not in repr(found)
    assert "never trust me" not in repr(found)


def test_deepgram_page_zero_and_page_one_use_exact_short_page_rule():
    entries = [request(f"req-{n}") for n in range(100)]
    first = parse_dg(dg_data(entries))
    second = parse_dg(dg_data(entries[:99], page=1), cursor="1")
    assert (first.receipt.requested_cursor, first.next_cursor, len(first.records)) == (None, "1", 100)
    assert (second.next_cursor, second.receipt.terminal_page_seen) == (None, True)


@pytest.mark.parametrize("bad", [
    b"true", b"NaN", b"-1", b"1e1001", b"0.00000000000000000001", b"100000000000000000000",
])
def test_duration_rejects_nonexact_numeric_inputs(bad):
    payload = json.dumps(dg_data([request(duration="sentinel")])).encode().replace(b'"sentinel"', bad)
    with pytest.raises(UsageReadFailed, match="INVALID_RESPONSE"):
        dg._parse_page(usage_transport.metadata_json(payload), DEEPGRAM, COVERAGE, None)


@pytest.mark.parametrize(("lexeme", "expected"), [
    (b"99999999999999999999.999999999999999999", Decimal("99999999999999999999.999999999999999999")),
    (b"0.00000000000000000100000", Decimal("0.000000000000000001")),
    (b"0.0000000000000000000", Decimal(0)),
])
def test_duration_preserves_exact_numeric_limits(lexeme, expected):
    payload = json.dumps(dg_data([request(duration="sentinel")])).encode().replace(b'"sentinel"', lexeme)
    page = dg._parse_page(usage_transport.metadata_json(payload), DEEPGRAM, COVERAGE, None)
    assert page.records[0].duration_seconds == expected


@pytest.mark.parametrize("data", [
    b'{"page":0,"limit":100}', b'{"page":0,"limit":101,"requests":[]}',
    b'{"page":0,"limit":100,"requests":[],"page":1}',
    b'{"page":0,"limit":100,"requests":[],"discard":"\\ud800"}',
    b'{"page":0,"limit":100,"requests":[],"discard":' + b"[" * 16 + b"0" + b"]" * 16 + b"}",
])
def test_metadata_schema_rejects_missing_duplicate_or_overdeep_fields(data):
    with pytest.raises(UsageReadFailed):
        dg._parse_page(usage_transport.metadata_json(data), DEEPGRAM, COVERAGE, None)


def test_openai_keeps_hourly_empty_buckets_and_distinct_nullable_dimensions():
    hour = COVERAGE.start
    found = parse_oa(oa_data(
        bucket(hour),
        bucket(hour + timedelta(hours=1), result(3, batch=True), result(0, batch=False), result(None, batch=None)),
    ))
    assert found.receipt.oa_bucket_starts == (hour, hour + timedelta(hours=1))
    assert tuple((item.dimensions.batch, item.metrics.input_tokens) for item in found.records) == (
        (True, 3), (False, 0), (None, None),
    )
    assert all(item.dimensions.project_id is None for item in found.records)


@pytest.mark.parametrize("payload", [
    oa_data(bucket(NOW)),
    oa_data(bucket(COVERAGE.start), bucket(COVERAGE.start)),
    oa_data(bucket(COVERAGE.start, result(1, input_cached_tokens=2))),
    oa_data(bucket(COVERAGE.start, result(True))),
    oa_data(bucket(COVERAGE.start, result(2**63))),
    oa_data(bucket(COVERAGE.start, result(2, object="wrong.result"))),
])
def test_openai_refuses_incompatible_buckets(payload):
    with pytest.raises(UsageReadFailed, match="INVALID_RESPONSE"):
        parse_oa(payload)


@pytest.fixture
def usage_runtime(provider_mounts):
    provider_mounts("provisioner", capable=True)
    initialize_provider_runtime(entrypoint="operator")
    publish_provider_policy(
        cleanup_authorizations=(), audit=ProvisioningAuditContext("synthetic-operator", uuid4(), "test-receipt"),
        clock=lambda: NOW - timedelta(hours=2),
    )

    def usage():
        provider_mounts("usage", capable=True)
        initialize_provider_runtime(entrypoint="celery_worker")

    return usage


def begin_scan(scope, *, interval=COVERAGE, start=NOW, purpose=ScanPurpose.RECENT, org=None, mapping=None):
    with transaction.atomic():
        _, row, _ = enroll_scope(scope.provider, scope.parent_scope_id, start)
        requirements = () if org is None else (
            ("CURRENT", org.pk, mapping, interval.start, interval.end),
        )
        return schedule_scan(
            row, purpose, interval.start, interval.end, start, row.pool.current_epoch,
            requirements=requirements,
        )


def task_for(scan, at):
    work = scan.usagework_set.get()
    delivery = _claim_publication(work.pk, False, lambda: at)
    assert delivery is not None
    return claim_work(work.pk, delivery[1], "SCAN", "provider_usage", clock=lambda: at)


def page_claim(work, at):
    claim = _claim_page(
        work, clock=lambda: at, monotonic_ns=lambda: 0, deadline=120_000_000_000,
    )
    assert claim is not None
    return claim[0]


def complete(scan, scope, at=NOW):
    finish_scan(scan.pk, ObservedCoverage(
        scan.pk, scope, UTCInterval(scan.requested_start, scan.requested_end), scan.started_at, at, True,
    ))


@pytest.fixture
def clock(monkeypatch):
    class TestClock:
        value = NOW

        def __call__(self):
            return self.value

    current = TestClock()
    monkeypatch.setattr("django.utils.timezone.now", current)
    return current


@pytest.mark.django_db
def test_duplicate_deepgram_fact_and_partial_page_do_not_claim_coverage(usage_runtime, clock):
    usage_runtime()
    many = [request("duplicate")] * 100
    scan = begin_scan(DEEPGRAM)
    work = task_for(scan, NOW)
    first = parse_dg(dg_data(many))
    applied = ingest_observations(first, scan.pk, claim=page_claim(work, NOW))
    assert (applied.inserted, applied.duplicates, ProviderUsageRecord.objects.count()) == (1, 99, 1)
    scan.refresh_from_db()
    assert scan.state == "PARTIAL"
    from selahcue_api.apps.usage.models import UsageObservedInterval
    assert not UsageObservedInterval.objects.filter(scan=scan).exists()
    assert read_provider_usage_health("deepgram", NOW).status == "UNRESOLVED"
    with pytest.raises(UsageRejected, match="CLAIM_STALE"):
        complete(scan, DEEPGRAM)
    finish_work(work.pk, work.lease_id, pending=True, clock=clock)


@pytest.mark.django_db
@pytest.mark.parametrize("second_result", [False, True])
def test_openai_empty_bucket_cannot_repeat_on_next_page(usage_runtime, clock, second_result):
    usage_runtime()
    scan = begin_scan(OPENAI)
    work = task_for(scan, NOW)
    hour = COVERAGE.start
    first = parse_oa(oa_data(bucket(hour), following="page-two"))
    ingest_observations(first, scan.pk, claim=page_claim(work, NOW))
    repeated = parse_oa(oa_data(bucket(hour, *([result(0)] if second_result else []))), cursor="page-two")
    with pytest.raises(UsageRejected, match="INVALID_RESPONSE"):
        ingest_observations(repeated, scan.pk, claim=page_claim(work, NOW))
    assert not ProviderUsageRecord.objects.exists()


@pytest.mark.django_db
def test_openai_values_replace_and_reuse_original_version(usage_runtime, clock):
    usage_runtime()
    for offset, amount in enumerate((7, 3, 7)):
        clock.value = NOW + timedelta(seconds=offset + 1)
        scan = begin_scan(OPENAI, start=clock(), purpose=ScanPurpose.HEALTH)
        work = task_for(scan, clock())
        page = parse_oa(oa_data(bucket(COVERAGE.start, result(amount, model="test model", batch=False))))
        result_status = ingest_observations(page, scan.pk, claim=page_claim(work, clock()))
        assert result_status.inserted + result_status.revised == 1
        complete(scan, OPENAI, clock())
        record = ProviderUsageRecord.objects.get()
        assert record.current_version.input_tokens == amount
    assert ProviderUsageVersion.objects.count() == 2
    assert record.accepted_generation == 3
    assert record.current_version.revision == 1


@pytest.mark.django_db
def test_health_uses_only_unattributed_operational_population(usage_runtime, clock):
    org = church()
    mapping = active_mapping(org, identity(key="mapped-credential"))
    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = task_for(scan, NOW)
    ingest_observations(parse_dg(dg_data([request(key="mapped-credential", duration=60)])),
                        scan.pk, claim=page_claim(work, NOW))
    complete(scan, DEEPGRAM)
    projection = ScopeUsageHealth.objects.get(scope_id=scan.scope_id)
    assert (projection.observed_total, projection.unquantifiable_count, projection.state) == (0, 0, "CURRENT")
    assert ProviderUsageRecord.objects.get().mapping_id == mapping.mapping_id

    clock.value = NOW + timedelta(seconds=1)
    scan = begin_scan(DEEPGRAM, start=clock())
    work = task_for(scan, clock())
    ingress = request("unmapped", completed=False, duration=60)
    ingest_observations(parse_dg(dg_data([ingress])), scan.pk, claim=page_claim(work, clock()))
    complete(scan, DEEPGRAM, clock())
    projected = read_provider_usage_health("deepgram", clock())
    assert (projected.status, projected.reason) == ("BLOCKED", "THRESHOLD")


def test_actual_isolated_child_round_trip_connects_only_to_inert_loopback(tmp_path, monkeypatch):
    evidence = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            evidence["path"] = self.path
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"page":0,"limit":100,"requests":[]}')

        def log_message(self, *_):
            return

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    child = tmp_path / "loopback_child.py"
    child.write_text(
        "import http.client, os, runpy\n"
        f"child = runpy.run_path({str(usage_transport._CHILD)!r})\n"
        "assert 'TEST_PROVIDER_SECRET' not in os.environ\n"
        "assert 'DJANGO_SETTINGS_MODULE' not in os.environ\n"
        "def loopback(host, *, port, timeout, context):\n"
        "    assert (host, port) == ('api.deepgram.com', 443)\n"
        f"    return http.client.HTTPConnection('127.0.0.1', {server.server_port}, timeout=timeout)\n"
        "http.client.HTTPSConnection = loopback\n"
        "child['main']()\n"
    )
    monkeypatch.setenv("TEST_PROVIDER_SECRET", "dummy_must_not_inherit")
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "test.dummy.inheritance")
    started = time.monotonic_ns()
    payload = {
        "schema_version": 1, "provider": "deepgram", "parent_scope_id": "local-test-parent",
        "profile": "DG_LISTEN_V1", "start_time": int(COVERAGE.start.timestamp()),
        "end_time": int(COVERAGE.end.timestamp()), "cursor": None,
        "credential_b64": "c3ludGhldGlj", "io_deadline_ns": started + 9_000_000_000,
    }
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result_bytes = usage_transport._run(payload, started=started, child=child)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
    assert usage_transport.metadata_json(result_bytes) == dg_data()
    assert evidence["path"].startswith("/v1/projects/local-test-parent/requests?")
    assert evidence["path"].endswith("&limit=100&page=0&endpoint=listen")
    assert time.monotonic_ns() - started < 10_000_000_000


@pytest.mark.django_db
def test_distinct_empty_buckets_publish_only_from_the_current_lease(usage_runtime, clock):
    usage_runtime()
    scan = begin_scan(OPENAI)
    work = task_for(scan, NOW)
    first = parse_oa(oa_data(bucket(COVERAGE.start), following="page-two"))
    old = page_claim(work, NOW)
    ingest_observations(first, scan.pk, claim=old)
    following = parse_oa(oa_data(bucket(COVERAGE.start + timedelta(hours=1))), cursor="page-two")
    claim = page_claim(work, NOW)
    with pytest.raises(UsageRejected, match="CLAIM_STALE"):
        ingest_observations(following, scan.pk, claim=old)
    ingest_observations(following, scan.pk, claim=claim)
    complete(scan, OPENAI, NOW)
    assert not ProviderUsageRecord.objects.exists()
    assert read_provider_usage_health("openai", NOW).status == "CURRENT"


@pytest.mark.django_db
def test_openai_receipt_cannot_omit_occupied_bucket(usage_runtime, clock):
    from dataclasses import replace

    usage_runtime()
    scan = begin_scan(OPENAI)
    work = task_for(scan, NOW)
    page = parse_oa(oa_data(bucket(COVERAGE.start, result(4))))
    incomplete = replace(page, receipt=replace(page.receipt, oa_bucket_starts=()))
    with pytest.raises(UsageRejected, match="INVALID_RESPONSE"):
        ingest_observations(incomplete, scan.pk, claim=page_claim(work, NOW))
    assert not ProviderUsageRecord.objects.exists()


@pytest.mark.django_db
def test_openai_maybe_overlapping_null_group_is_retained_without_double_count(usage_runtime, clock):
    usage_runtime()
    hour = COVERAGE.start
    for offset, results in enumerate((
        (result(6, model=None),),
        (result(6, model="model-a"),),
        (result(6, model=None), result(4, model="model-a")),
    )):
        clock.value = NOW + timedelta(seconds=offset)
        scan = begin_scan(OPENAI, start=clock(), purpose=ScanPurpose.HEALTH)
        work = task_for(scan, clock())
        ingest_observations(parse_oa(oa_data(bucket(hour, *results))), scan.pk, claim=page_claim(work, clock()))
        complete(scan, OPENAI, clock())
        selected = ScopeUsageHealth.objects.get(scope_id=scan.scope_id)
        if offset == 1:
            assert ProviderUsageRecord.objects.filter(attribution="DISCREPANCY").count() == 2
            assert selected.observed_total == 7  # prior known-breach latch remains selected
        if offset == 2:
            assert ProviderUsageRecord.objects.filter(attribution="UNATTRIBUTED").count() == 2
            assert selected.observed_total == 12


@pytest.mark.django_db
def test_higher_generation_with_retreating_window_cannot_replace_health(usage_runtime, clock):
    usage_runtime()
    scan = begin_scan(DEEPGRAM, purpose=ScanPurpose.HEALTH)
    work = task_for(scan, NOW)
    ingest_observations(parse_dg(dg_data([request(completed=False, duration=60)])),
                        scan.pk, claim=page_claim(work, NOW))
    complete(scan, DEEPGRAM)
    prior = ScopeUsageHealth.objects.get(scope_id=scan.scope_id)
    clock.value = NOW + timedelta(seconds=1)
    end = NOW - timedelta(hours=1)
    earlier_window = UTCInterval(end - timedelta(hours=24), end)
    later = begin_scan(DEEPGRAM, interval=earlier_window, start=clock(), purpose=ScanPurpose.HEALTH)
    work = task_for(later, clock())
    ingest_observations(parse_dg(dg_data(), interval=earlier_window), later.pk, claim=page_claim(work, clock()))
    complete(later, DEEPGRAM, clock())
    actual = ScopeUsageHealth.objects.get(pk=prior.pk)
    assert (actual.complete_scan_id, actual.selected_generation, actual.selected_window_end, actual.valid_until) == (
        scan.pk, scan.generation, NOW, prior.valid_until,
    )


def test_stalled_inert_child_is_killed_and_reaped(tmp_path):
    import os

    child = tmp_path / "stalled_child.py"
    pid_file = tmp_path / "pid"
    child.write_text(
        "import os, time\n"
        f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
        "time.sleep(30)\n"
    )
    wall = time.monotonic()
    started = time.monotonic_ns() - 8_500_000_000
    with pytest.raises(UsageReadFailed, match="TRANSPORT_TIMEOUT"):
        usage_transport._run({}, started=started, child=child)
    pid = int(pid_file.read_text())
    assert time.monotonic() - wall < 1.5
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.django_db
def test_page_retry_deadlines_are_persisted_and_fourth_read_is_impossible(usage_runtime, clock):
    from selahcue_api.apps.usage.models import UsageCoverageGap
    from selahcue_api.apps.usage.scans import _apply_failure, run_scan

    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = task_for(scan, NOW)
    first = page_claim(work, NOW)
    _apply_failure(work, first, UsageFailureCode.TRANSPORT_ERROR, clock)
    for offset in (1, 4, 6, 29):
        clock.value = NOW + timedelta(seconds=offset)
        if offset == 6:
            second = page_claim(work, clock())
            _apply_failure(work, second, UsageFailureCode.TRANSPORT_ERROR, clock)
            continue
        assert _claim_page(work, clock=clock, monotonic_ns=lambda: 0, deadline=120_000_000_000) is None
    clock.value = NOW + timedelta(seconds=30)
    third = page_claim(work, clock())
    _apply_failure(work, third, UsageFailureCode.TRANSPORT_TIMEOUT, clock)
    scan.refresh_from_db()
    assert (scan.state, scan.replacement_not_before) == ("FAILED", clock() + timedelta(seconds=120))
    assert scan.usagepageclaim_set.get().attempts == 3
    assert run_scan(work, clock=clock, monotonic_ns=lambda: 0)[0] == "FAILED"
    assert UsageCoverageGap.objects.filter(last_scan=scan, state="OPEN").count() == 1


@pytest.mark.django_db
def test_worker_ack_precedes_publisher_success_and_wrong_queue_cannot_claim(usage_runtime, clock):
    from selahcue_api.apps.usage.models import UsageOutbox
    from selahcue_api.apps.usage.usage_tasks import _finish_publication

    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = scan.usagework_set.get()
    _, delivery, lease = _claim_publication(work.pk, False, clock)
    assert claim_work(work.pk, delivery, "SCAN", "celery", clock=clock) is None
    accepted = claim_work(work.pk, delivery, "SCAN", "provider_usage", clock=clock)
    assert accepted.pk == work.pk
    _finish_publication(work.pk, delivery, lease, True, clock)
    assert UsageOutbox.objects.get(pk=delivery).state == "ACKED"
    assert claim_work(work.pk, delivery, "SCAN", "provider_usage", clock=clock) is None
    assert UsageOutbox.objects.get(pk=delivery).publish_attempts == 1
    assert scan.usagepageclaim_set.get().attempts == 0
