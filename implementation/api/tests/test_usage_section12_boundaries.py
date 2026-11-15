"""Finite Task 6 contract cases for provider, evidence and durable worker boundaries."""
from datetime import timedelta
from uuid import uuid4

import pytest

from provider_helpers import DEEPGRAM, OPENAI, cold_provider_cache, identity, provider_mounts
from selahcue_api.apps.providers.adapters import openai_usage, usage_transport
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.usage.contracts import UTCInterval
from selahcue_api.apps.usage.health import read_provider_usage_health
from selahcue_api.apps.usage.models import ScopeUsageHealth, UsageReservation
from selahcue_api.apps.usage.observation_contracts import RetentionKind, ScanPurpose, UsageReadFailed, UsageRejected
from selahcue_api.apps.usage.observations import ingest_observations
from selahcue_api.apps.usage.readiness import read_stt_readiness
from selahcue_api.apps.usage.reconciliation import reconcile_org
from selahcue_api.apps.usage.retention import prune_usage_batch
from test_effective_org_plan import church, device, licence
from test_provider_observations import (
    COVERAGE, NOW, begin_scan, bucket, clock, complete, dg_data, oa_data, page_claim, parse_dg, parse_oa, request,
    result, task_for, usage_runtime,
)
from test_provider_reservation_binding import active_mapping
from test_usage_reconciliation import MONDAY, observed, reserve_stt


@pytest.mark.parametrize("payload", [
    {"object": "page", "data": [], "has_more": False, "next_page": "forbidden"},
    {"object": "page", "data": [], "has_more": True, "next_page": None},
    {"object": "page", "data": [], "has_more": 1, "next_page": "forbidden"},
])
def test_openai_pagination_flag_matches_cursor_presence(payload):
    with pytest.raises(UsageReadFailed):
        openai_usage._parse_page(payload, OPENAI, COVERAGE, None)


@pytest.mark.django_db
def test_openai_rejects_persisted_cursor_cycle_before_applying_page(usage_runtime, clock):
    usage_runtime()
    scan = begin_scan(OPENAI)
    work = task_for(scan, NOW)
    for incoming, following in ((None, "cursor-a"), ("cursor-a", "cursor-b")):
        page = parse_oa(oa_data(following=following), cursor=incoming)
        ingest_observations(page, scan.pk, claim=page_claim(work, NOW))
    page = parse_oa(oa_data(following="cursor-a"), cursor="cursor-b")
    with pytest.raises(UsageRejected, match="INVALID_CURSOR"):
        ingest_observations(page, scan.pk, claim=page_claim(work, NOW))
    assert scan.usagepageclaim_set.filter(state="APPLIED").count() == 2


def test_openai_exact_record_body_depth_identity_and_cursor_neighbors():
    valid = result(3, input_cached_tokens=2, project_id="p" * 256)
    hour = COVERAGE.start
    allowed_model = parse_oa(oa_data(bucket(hour, result(3, model="π" * 256))))
    assert len(allowed_model.records[0].dimensions.model) == 256
    with pytest.raises(UsageReadFailed):
        parse_oa(oa_data(bucket(hour, result(3, model="π" * 257))))
    cursor = "π" * 2048
    data = oa_data(bucket(hour, *([valid] * 500)), bucket(hour + timedelta(hours=1), *([valid] * 500)), following=cursor)
    parsed = parse_oa(data)
    assert (len(parsed.records), parsed.next_cursor) == (1000, cursor)
    with pytest.raises(UsageReadFailed):
        parse_oa(oa_data(bucket(hour, *([valid] * 500)), bucket(hour + timedelta(hours=1), *([valid] * 501))))
    with pytest.raises(UsageReadFailed):
        parse_oa(oa_data(following=cursor + "x"))
    with pytest.raises(UsageReadFailed):
        parse_oa(oa_data(bucket(hour, result(3, project_id="p" * 257))))
    body = b'{"discard":null}'
    assert usage_transport.metadata_json(body.ljust(1_048_576, b" ")) == {"discard": None}
    with pytest.raises(UsageReadFailed, match="RESPONSE_TOO_LARGE"):
        usage_transport.metadata_json(body.ljust(1_048_577, b" "))
    assert usage_transport.metadata_json(b'{"data":' + b"[" * 15 + b"0" + b"]" * 15 + b"}")
    with pytest.raises(UsageReadFailed):
        usage_transport.metadata_json(b'{"data":' + b"[" * 16 + b"0" + b"]" * 16 + b"}")


@pytest.mark.django_db
def test_mapped_complete_unknown_duration_blocks_only_its_org(usage_runtime, clock):
    org, other = church(), church()
    bad = active_mapping(org, identity(key="amount-missing"))
    good = active_mapping(other)
    usage_runtime()
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(scan, [request(key="amount-missing", duration=None)], NOW)
    assert read_provider_usage_health("deepgram", NOW).status == "CURRENT"
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason == "METRIC_UNKNOWN"
    assert read_stt_readiness(org_id=org.pk, mapping_id=bad.mapping_id, at=NOW).status != "current_observed"
    assert reconcile_org(other.pk, NOW, clock=clock).blocked_reason is None
    assert read_stt_readiness(org_id=other.pk, mapping_id=good.mapping_id, at=NOW).status == "current_observed"


@pytest.mark.django_db
def test_oa_input_output_are_quantifiable_with_or_without_optional_cache(usage_runtime, clock):
    usage_runtime()
    for offset, facts in enumerate((result(8, 3), result(8, 3, input_cached_tokens=4))):
        clock.value = NOW + timedelta(seconds=offset)
        scan = begin_scan(OPENAI, start=clock())
        work = task_for(scan, clock())
        authority = page_claim(work, clock())
        ingest_observations(parse_oa(oa_data(bucket(COVERAGE.start, facts))), scan.pk, claim=authority)
        complete(scan, OPENAI, clock())
        evaluation = ScopeUsageHealth.objects.get(scope_id=scan.scope_id)
        assert (evaluation.state, evaluation.observed_total, evaluation.unquantifiable_count) == ("BLOCKED", 11, 0)


@pytest.mark.django_db
def test_threshold_latch_clears_on_new_complete_zero_evidence_but_not_expired_or_replayed_scan(usage_runtime, clock):
    usage_runtime()
    blocked = begin_scan(DEEPGRAM)
    observed(blocked, [request(duration=60, created=NOW - timedelta(hours=1))], NOW)
    baseline = ScopeUsageHealth.objects.get(scope_id=blocked.scope_id)
    assert baseline.state == "BLOCKED"
    clock.value += timedelta(seconds=1)
    stale = begin_scan(DEEPGRAM, start=clock())
    work = task_for(stale, clock())
    ingest_observations(
        parse_dg(dg_data([request(duration=0, created=NOW - timedelta(hours=1))])),
        stale.pk, claim=page_claim(work, clock()),
    )
    clock.value += timedelta(seconds=300)
    complete(stale, DEEPGRAM, clock())
    complete(blocked, DEEPGRAM, clock())
    baseline.refresh_from_db()
    assert baseline.complete_scan_id == blocked.pk and baseline.state == "BLOCKED"

    end = clock()
    fresh = begin_scan(DEEPGRAM, start=end, interval=UTCInterval(end - timedelta(days=1), end))
    observed(fresh, [request(duration=0, created=NOW - timedelta(hours=1))], end)
    baseline.refresh_from_db()
    assert baseline.complete_scan_id == fresh.pk and baseline.state == "CURRENT"
    assert baseline.observed_total == 0 and baseline.valid_until == end + timedelta(seconds=300)


@pytest.mark.django_db
def test_excluded_mapped_metric_correction_does_not_invalidate_selected_health(usage_runtime, clock):
    active_mapping(church(), identity(key="excluded"))
    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    observed(scan, [request(key="excluded", duration=30)], NOW)
    before = ScopeUsageHealth.objects.get(scope_id=scan.scope_id)
    clock.value += timedelta(seconds=1)
    replacement = begin_scan(DEEPGRAM, start=clock())
    work = task_for(replacement, clock())
    ingest_observations(
        parse_dg(dg_data([request(key="excluded", duration=31)])),
        replacement.pk, claim=page_claim(work, clock()),
    )
    after = ScopeUsageHealth.objects.get(pk=before.pk)
    assert (after.state, after.facts_revision, after.complete_scan_id) == ("CURRENT", before.facts_revision, scan.pk)


@pytest.mark.django_db
def test_queued_refresh_keeps_publication_but_applied_partial_and_failure_refuse(usage_runtime, clock):
    from selahcue_api.apps.usage.models import UsageScan
    from selahcue_api.apps.usage.observation_contracts import UsageFailureCode
    from selahcue_api.apps.usage.scans import _apply_failure

    org = church()
    mapping = active_mapping(org, identity(key="partial-owned"))
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(initial, [], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    clock.value += timedelta(seconds=1)
    interval = UTCInterval(MONDAY, clock())
    replacement = begin_scan(DEEPGRAM, interval=interval, start=clock(), org=org, mapping=mapping.mapping_id)
    assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=clock()).status == "current_observed"
    work = task_for(replacement, clock())
    rows = [request("partial", key="partial-owned", duration=2)] * 100
    ingest_observations(parse_dg(dg_data(rows), interval=interval), replacement.pk, claim=page_claim(work, clock()))
    assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=clock()).status == "stale"
    assert reconcile_org(org.pk, clock(), clock=clock).blocked_reason == "REVISION_CONFLICT"
    first_failure = clock()
    for offset in (0, 5, 30):
        clock.value = first_failure + timedelta(seconds=offset)
        claim = page_claim(work, clock())
        _apply_failure(work, claim, UsageFailureCode.TRANSPORT_ERROR, clock)
    assert UsageScan.objects.get(pk=replacement.pk).state == "FAILED"
    assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=clock()).status == "stale"


@pytest.mark.django_db
def test_unsigned_lost_delivery_rearms_only_after_persisted_confirmation_deadline(usage_runtime, clock):
    from selahcue_api.apps.usage.models import UsageOutbox
    from selahcue_api.apps.usage.usage_tasks import _claim_publication, _finish_publication, claim_work

    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = scan.usagework_set.get()
    _, delivery, lease = _claim_publication(work.pk, False, clock)
    _finish_publication(work.pk, delivery, lease, True, clock)
    assert claim_work(work.pk, uuid4(), "SCAN", "provider_usage", clock=clock) is None
    clock.value += timedelta(seconds=29)
    assert _claim_publication(work.pk, False, clock) is None
    clock.value += timedelta(seconds=1)
    assert _claim_publication(work.pk, False, clock) is None
    attempt = UsageOutbox.objects.get(pk=delivery)
    assert (attempt.state, attempt.publish_attempts, attempt.available_at) == ("PENDING", 1, clock() + timedelta(seconds=5))
    clock.value += timedelta(seconds=5)
    assert _claim_publication(work.pk, False, clock)[1] == delivery
    assert scan.usagepageclaim_set.get().attempts == 0


@pytest.mark.django_db
def test_expired_reading_claim_retains_attempt_and_releases_its_scope_lane(usage_runtime, clock):
    from selahcue_api.apps.usage.scans import _claim_page

    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = task_for(scan, NOW)
    first = page_claim(work, NOW)
    clock.value += timedelta(seconds=30)
    assert _claim_page(work, clock=clock, monotonic_ns=lambda: 0, deadline=120_000_000_000) is None
    stalled = scan.usagepageclaim_set.get()
    assert (stalled.state, stalled.attempts, stalled.last_error) == ("PENDING", 1, "TRANSPORT_TIMEOUT")
    clock.value += timedelta(seconds=5)
    renewed = page_claim(work, clock())
    assert renewed.lane_fence > first.lane_fence and renewed.lease_id != first.lease_id
    assert scan.usagepageclaim_set.get().attempts == 2


@pytest.mark.django_db
def test_retention_does_not_delete_open_or_mint_attempt_bound_reservations(
    usage_runtime, provider_mounts, clock,
):
    from selahcue_api.apps.providers.models import SttMintAttempt

    org = church()
    install = device(licence(org))
    mapping = active_mapping(org)
    live = reserve_stt(install, mapping.mapping_id, NOW - timedelta(minutes=2))
    tied = reserve_stt(install, mapping.mapping_id, NOW - timedelta(minutes=1))
    SttMintAttempt.objects.create(
        reservation=tied, owner_nonce=uuid4(), request_receipt_id=uuid4(), trigger_token_pk=1, mapping_revision=2,
        state="PREPARED", prepared_at=NOW, dispatch_not_after=NOW+timedelta(seconds=3),
    )
    UsageReservation.objects.filter(pk__in=(live.pk, tied.pk)).update(created_at=NOW-timedelta(weeks=105))
    UsageReservation.objects.filter(pk=tied.pk).update(state="RELEASED")
    provider_mounts("maintenance", capable=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    removal = prune_usage_batch(RetentionKind.TERMINAL_RESERVATION, clock=clock)
    assert removal.deleted == 0 and removal.scanned == removal.deferred == 1
    assert set(UsageReservation.objects.values_list("pk", flat=True)) == {live.pk, tied.pk}


@pytest.mark.django_db
@pytest.mark.parametrize(("disruption", "reason"), [
    ("blocked_historical", "THRESHOLD"),
    ("unenrolled_published", "SCOPE_MISSING"),
    ("missing_evaluation", "COVERAGE_MISSING"),
    ("current_epoch_missing", "POLICY_MISMATCH"),
    ("changed_epoch", "POLICY_MISMATCH"),
    ("reported_producer_failure", "SCOPE_MISSING"),
    ("expired_without_report", "COVERAGE_STALE"),
])
def test_consumer_includes_historical_scopes_outside_its_local_subset(
    usage_runtime, provider_mounts, clock, disruption, reason,
):
    from selahcue_api.apps.providers.models import ProviderCapacityPool, ScopePolicyEpoch
    from selahcue_api.apps.usage.models import UsageScope
    from selahcue_api.apps.usage.usage_tasks import _schedule_periodic
    from test_usage_retained_history_load import _complete_scope, _historical_parent

    usage_runtime()
    initial = begin_scan(DEEPGRAM)
    observed(initial, [], NOW)
    template = ProviderCapacityPool.objects.get(provider="deepgram", parent_scope_id=DEEPGRAM.parent_scope_id)
    historical = _historical_parent(template, "archived-metadata-scope")
    pool = ProviderCapacityPool.objects.get(provider="deepgram", parent_scope_id=historical.parent_scope_id)
    if disruption != "unenrolled_published":
        if disruption in ("missing_evaluation", "current_epoch_missing"):
            UsageScope.objects.create(
                provider="deepgram", parent_scope_id=historical.parent_scope_id, pool=pool,
                created_at=NOW, updated_at=NOW,
            )
        else:
            scan, _ = _complete_scope(historical, MONDAY, NOW, NOW, health_input=True)
            scope = scan.scope
            assert read_provider_usage_health("deepgram", NOW).status == "CURRENT"
    if disruption == "blocked_historical":
        ScopeUsageHealth.objects.filter(scope=scope).update(state="BLOCKED", reason="THRESHOLD", observed_total=1)
    elif disruption == "current_epoch_missing":
        pool.current_epoch = None
        pool.save(update_fields=("current_epoch",))
    elif disruption == "changed_epoch":
        old = pool.current_epoch
        pool.current_epoch = ScopePolicyEpoch.objects.create(
            pool=pool, digest="8"*64, publication_digest="9"*64, policy=old.policy, cleanup_authorized=False,
            published_by="fixture-operator", request_id=uuid4(), evidence_ref="policy-change", created_at=NOW,
        )
        pool.save(update_fields=("current_epoch",))
    elif disruption == "reported_producer_failure":
        _schedule_periodic(scope, "RECENT_SCOPE", clock)
    provider_mounts("web", stt=True, capable=True)
    config = initialize_provider_runtime(entrypoint="wsgi")
    assert not config.usage_credentials
    at = NOW
    if disruption == "expired_without_report":
        assert read_provider_usage_health("deepgram", NOW+timedelta(seconds=299)).status == "CURRENT"
        at += timedelta(seconds=300)
    result = read_provider_usage_health("deepgram", at)
    assert result.status != "CURRENT" and result.reason == reason


@pytest.mark.django_db
def test_unrelated_partial_history_does_not_block_republication_after_scope_revision(usage_runtime, clock):
    org = church()
    mapping = active_mapping(org)
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(initial, [], NOW)
    first = reconcile_org(org.pk, NOW, clock=clock)
    assert first.blocked_reason is None
    lower, upper = NOW - timedelta(days=30), NOW - timedelta(days=29)
    clock.value += timedelta(seconds=1)
    interval = UTCInterval(lower, upper)
    backfill = begin_scan(DEEPGRAM, interval=interval, start=clock(), purpose=ScanPurpose.HISTORY)
    work = task_for(backfill, clock())
    rows = [request("outside-current", duration=1, created=lower + timedelta(hours=1))] * 100
    ingest_observations(parse_dg(dg_data(rows), interval=interval), backfill.pk, claim=page_claim(work, clock()))
    assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=clock()).status == "stale"
    assert read_provider_usage_health("deepgram", clock()).status == "CURRENT"
    again = reconcile_org(org.pk, clock(), clock=clock)
    assert again.blocked_reason is None and again.observed_through == first.observed_through
    assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=clock()).status == "current_observed"


@pytest.mark.django_db
def test_open_reservation_after_frozen_recent_cutoff_gets_only_a_subsequent_requirement(
    usage_runtime, clock,
):
    from selahcue_api.apps.usage.models import UsageRecentPlan, UsageScan
    from selahcue_api.apps.usage.usage_tasks import _schedule_periodic
    from test_usage_reconciliation import seed_old_unresolved_days, set_issued

    church_with_slice = church()
    install = device(licence(church_with_slice))
    mapping = active_mapping(church_with_slice)
    other = active_mapping(church())
    usage_runtime()
    scope, _ = seed_old_unresolved_days(clock)
    _schedule_periodic(scope, "RECENT_SCOPE", clock, limit=1)
    clock.value += timedelta(seconds=1)
    admitted = reserve_stt(install, mapping.mapping_id, clock())
    set_issued(admitted, clock())
    for _ in range(8):
        _schedule_periodic(scope, "RECENT_SCOPE", clock, limit=2)
        if not UsageRecentPlan.objects.filter(scope=scope).exists():
            break
    old = UsageScan.objects.get(scope=scope, purpose="RECENT", requested_end=NOW)
    assert set(old.usagescanrequirement_set.filter(kind="CURRENT").values_list("mapping", flat=True)) == {
        mapping.mapping_id, other.mapping_id,
    }
    assert not old.usagescanrequirement_set.filter(kind="OPEN").exists()
    clock.value = admitted.authorized_until + timedelta(seconds=900)
    for _ in range(8):
        _schedule_periodic(scope, "RECENT_SCOPE", clock, limit=2)
        if not UsageRecentPlan.objects.filter(scope=scope).exists():
            break
    published = UsageScan.objects.get(scope=scope, purpose="RECENT", requested_end=clock())
    requirement = published.usagescanrequirement_set.get(kind="OPEN", org=church_with_slice)
    assert requirement.required_start <= admitted.authorized_from < requirement.required_end == clock()


@pytest.mark.django_db
def test_empty_database_provider_union_does_not_supply_health():
    assert read_provider_usage_health("deepgram", NOW).status == "UNRESOLVED"
    assert read_provider_usage_health("deepgram", NOW).reason == "COVERAGE_MISSING"


@pytest.mark.django_db
def test_all_three_scan_lanes_get_a_turn_before_current_repeats(usage_runtime, clock):
    from selahcue_api.apps.usage.scans import _next_page

    usage_runtime()
    recent = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW), purpose=ScanPurpose.RECENT)
    healthy = begin_scan(DEEPGRAM, purpose=ScanPurpose.HEALTH)
    previous = NOW - timedelta(days=20)
    history = begin_scan(DEEPGRAM, interval=UTCInterval(previous, previous + timedelta(days=1)), purpose=ScanPurpose.HISTORY)
    works = [task_for(scan, clock()) for scan in (recent, healthy, history)]
    for scan, work in zip((recent, healthy, history), works, strict=True):
        scope = scan.scope
        scope.refresh_from_db()
        assert _next_page(scope, clock()).pk == scan.pk
        interval = UTCInterval(scan.requested_start, scan.requested_end)
        item = request(f"queued-fairness-{scan.purpose}", duration=0, created=interval.start + timedelta(hours=1))
        ingest_observations(
            parse_dg(dg_data([item] * 100), interval=interval), scan.pk, claim=page_claim(work, clock()),
        )
    scope.refresh_from_db()
    assert _next_page(scope, clock()).pk == recent.pk
    assert all(scan.usagepageclaim_set.filter(state="APPLIED").count() == 1 for scan in (recent, healthy, history))


@pytest.mark.django_db
def test_a_running_scan_never_claims_an_eleventh_provider_page(usage_runtime, clock, monkeypatch):
    from selahcue_api.apps.usage import scans

    usage_runtime()
    scan = begin_scan(OPENAI)
    work = task_for(scan, clock())
    cursors = []

    def read(scope, interval, cursor):
        assert scope == OPENAI and interval == COVERAGE
        cursors.append(cursor)
        return parse_oa(oa_data(following=f"cursor-{len(cursors)}"), cursor=cursor)

    monkeypatch.setattr(scans.openai_usage, "read_usage_page", read)
    state, _, _ = scans.run_scan(work, clock=clock, monotonic_ns=lambda: 0)
    assert state == "PENDING" and len(cursors) == 10
    assert scan.usagepageclaim_set.filter(state="APPLIED", attempts=1).count() == 10
    assert scan.usagepageclaim_set.get(ordinal=10).attempts == 0


@pytest.mark.django_db
def test_initial_discovery_wraps_for_smaller_key_activated_behind_cursor(usage_runtime, provider_mounts, clock):
    import time
    from uuid import UUID
    from provider_helpers import SECRET, audit
    from selahcue_api.apps.providers.contracts import RegistryReason
    from selahcue_api.apps.providers.registry import import_existing_mapping
    from selahcue_api.apps.usage.models import UsageDiscoveryCursor, UsageScanRequirement
    from selahcue_api.apps.usage.usage_tasks import _initial_batch

    def add(identifier):
        provider_mounts("provisioner", capable=True)
        initialize_provider_runtime(entrypoint="operator")
        return import_existing_mapping(
            mapping_id=UUID(int=identifier), org_id=church().pk, identity=identity(), secret=SECRET,
            now=NOW-timedelta(seconds=2), audit=audit(RegistryReason.IMPORT_APPROVED_ALLOCATION),
        ).mapping_id

    usage_runtime()
    first = add(8)
    usage_runtime()
    assert _initial_batch(1, time.monotonic()+5, clock) == (1, 1)
    assert UsageDiscoveryCursor.objects.get(purpose="INITIAL_MAPPING").last_uuid == first
    smaller = add(4)
    usage_runtime()
    assert _initial_batch(1, time.monotonic()+5, clock) == (0, 0)
    assert _initial_batch(1, time.monotonic()+5, clock) == (1, 1)
    assert set(UsageScanRequirement.objects.filter(kind="INITIAL").values_list("mapping", flat=True)) == {first, smaller}


@pytest.mark.django_db
def test_attribution_wraps_to_bind_an_older_unattributed_identity(usage_runtime, provider_mounts, clock):
    from selahcue_api.apps.usage.models import ProviderUsageRecord
    from selahcue_api.apps.usage.observations import attribute_scope_batch

    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    observed(scan, [request("first-mapping", key="old-unbound"), request("second-mapping", key="next-unbound")], NOW)
    assert attribute_scope_batch(scan.scope_id, after=None, limit=1, clock=clock).changed == 0
    provider_mounts("provisioner", capable=True)
    initialize_provider_runtime(entrypoint="operator")
    mapping = active_mapping(church(), identity(key="old-unbound"))
    usage_runtime()
    assert attribute_scope_batch(scan.scope_id, after=None, limit=1, clock=clock).changed == 0
    assert attribute_scope_batch(scan.scope_id, after=None, limit=1, clock=clock).exhausted
    assert attribute_scope_batch(scan.scope_id, after=None, limit=1, clock=clock).changed == 1
    assert ProviderUsageRecord.objects.get(request_id="first-mapping").mapping_id == mapping.mapping_id
    state = ScopeUsageHealth.objects.get(scope_id=scan.scope_id)
    assert state.facts_revision > state.applied_facts_revision and state.complete_scan_id == scan.pk


@pytest.mark.django_db
def test_policy_epoch_change_and_runtime_restart_preserve_health_clearing_minima(
    usage_runtime, provider_mounts, clock,
):
    from selahcue_api.apps.providers.contracts import CleanupAuthorization, ProvisioningAuditContext
    from selahcue_api.apps.providers.policy_publication import publish_provider_policy

    usage_runtime()
    blocked = begin_scan(DEEPGRAM)
    observed(blocked, [request(duration=60)], NOW)
    clock.value += timedelta(seconds=1)
    start = clock()
    partial = begin_scan(DEEPGRAM, interval=UTCInterval(start-timedelta(days=1), start), start=start)
    work = task_for(partial, clock())
    ingest_observations(
        parse_dg(dg_data([request(duration=0)] * 100), interval=UTCInterval(partial.requested_start, partial.requested_end)),
        partial.pk, claim=page_claim(work, clock()),
    )
    older = ScopeUsageHealth.objects.get(scope_id=blocked.scope_id)
    assert older.state == "BLOCKED" and older.clear_min_generation == partial.generation
    provider_mounts("provisioner", capable=True)
    initialize_provider_runtime(entrypoint="operator")
    publish_provider_policy(
        cleanup_authorizations=(CleanupAuthorization(DEEPGRAM, "epoch-evidence"),),
        audit=ProvisioningAuditContext("synthetic-operator", uuid4(), "epoch-evidence"),
        clock=clock,
    )
    usage_runtime()
    assert read_provider_usage_health("deepgram", clock()).reason == "POLICY_MISMATCH"
    older.refresh_from_db()
    assert (older.clear_min_generation, older.clear_min_window_end) == (partial.generation, partial.requested_end)


@pytest.mark.django_db
def test_required_retired_scope_is_still_present_in_current_org_vector(provider_mounts, settings, tmp_path, clock):
    from provider_helpers import audit
    from selahcue_api.apps.providers.contracts import ProviderScope, ProvisioningAuditContext, RegistryReason
    from selahcue_api.apps.providers.models import ProviderCredential
    from selahcue_api.apps.providers.policy_publication import publish_provider_policy
    from selahcue_api.apps.providers.registry import retire_mapping
    from selahcue_api.apps.usage.models import SttOrgReadinessScope
    from test_usage_retained_history_load import _complete_scope, _runtime
    from test_usage_reconciliation import set_issued

    retired_parent = ProviderScope("deepgram", "prior-parent")
    scopes = (DEEPGRAM, retired_parent)
    _runtime("provisioner", provider_mounts, settings, tmp_path, scopes)
    publish_provider_policy(
        cleanup_authorizations=(), audit=ProvisioningAuditContext("fixture-audit", uuid4(), "fixture-scopes"),
        clock=lambda: NOW-timedelta(hours=2),
    )
    org = church()
    install = device(licence(org))
    old = active_mapping(org, identity(retired_parent))
    holder = reserve_stt(install, old.mapping_id, NOW-timedelta(seconds=15))
    set_issued(holder, NOW-timedelta(seconds=15))
    row = ProviderCredential.objects.get(pk=old.mapping_id)
    retire_mapping(mapping_id=row.pk, expected_revision=row.revision, now=NOW-timedelta(seconds=10), audit=audit(RegistryReason.RETIRE))
    new = active_mapping(org, identity(DEEPGRAM))
    _runtime("usage", provider_mounts, settings, tmp_path, scopes)
    for parent in scopes:
        _complete_scope(parent, MONDAY, NOW, NOW, health_input=True)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    vector = SttOrgReadinessScope.objects.filter(publication_id=org.pk)
    assert set(vector.values_list("scope__scope__parent_scope_id", flat=True)) == {
        parent.parent_scope_id for parent in scopes
    }
    assert read_stt_readiness(org_id=org.pk, mapping_id=new.mapping_id, at=NOW).status == "current_observed"


@pytest.mark.django_db
def test_mixed_outbox_dependency_deletes_share_the_physical_batch_cap(usage_runtime, provider_mounts, clock):
    from selahcue_api.apps.usage.models import UsageOutbox, UsageWork

    usage_runtime()
    old = NOW - timedelta(days=36)
    jobs = [
        UsageWork(
            kind="MINT_RECOVERY", attempt_id=uuid4(), subject_key=f"expired-work-{index}", state="COMPLETE",
            due_at=old, started_at=old, finished_at=old, created_at=old, updated_at=old,
        ) for index in range(32)
    ]
    UsageWork.objects.bulk_create(jobs)
    UsageOutbox.objects.bulk_create([
        UsageOutbox(
            work=job, generation=number, state="ACKED", publish_attempts=1, available_at=old,
            acked_at=old, sent_at=old, created_at=old, updated_at=old,
        ) for job in jobs for number in (1, 2, 3)
    ])
    provider_mounts("maintenance", capable=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    first = prune_usage_batch(RetentionKind.TERMINAL_SCAN_WORK, clock=clock)
    assert first.deleted == 100 and first.has_more
    assert UsageWork.objects.count() + UsageOutbox.objects.count() == 28
    following = prune_usage_batch(RetentionKind.TERMINAL_SCAN_WORK, clock=clock)
    assert following.deleted == 28 and not following.has_more
    assert not UsageWork.objects.exists() and not UsageOutbox.objects.exists()


@pytest.mark.django_db
def test_page_detail_age_before_at_after_cutoff_is_strict_and_duplicate_does_not_extend_age(
    usage_runtime, provider_mounts, clock,
):
    from selahcue_api.apps.usage.models import ProviderUsageRecord, UsagePageClaim

    org = church()
    active_mapping(org, identity(key="original-detail-age"))
    usage_runtime()
    cutoff = NOW-timedelta(days=35)
    first_pk, scan_ids = None, []
    event = cutoff - timedelta(minutes=5)
    interval = UTCInterval(cutoff-timedelta(days=1), cutoff-timedelta(seconds=1))
    for microsecond in (-1, 0, 1):
        clock.value = cutoff + timedelta(microseconds=microsecond)
        scan = begin_scan(DEEPGRAM, start=clock(), interval=interval)
        observed(scan, [request("original-detail-age", key="original-detail-age", duration=2, created=event)], clock())
        if first_pk is None:
            first_pk = ProviderUsageRecord.objects.get().current_version_id
        scan_ids.append(scan.pk)
    row = ProviderUsageRecord.objects.get()
    assert row.retention_at == event and row.current_version_id == first_pk
    assert row.current_version.first_receipt_at == cutoff-timedelta(microseconds=1)
    provider_mounts("maintenance", capable=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    clock.value = NOW
    assert prune_usage_batch(RetentionKind.PAGE_DETAIL, clock=clock).deleted == 1
    assert set(UsagePageClaim.objects.values_list("scan_id", flat=True)) == set(scan_ids[1:])
    row.refresh_from_db()
    assert row.current_version.source_page_id is None and row.current_version.source_scan_id == scan_ids[0]


@pytest.mark.django_db
def test_deepgram_positive_threshold_equality_and_exact_health_window_edges(
    provider_mounts, settings, tmp_path, clock,
):
    from provider_helpers import policy_rows, write_mount
    from selahcue_api.apps.providers.contracts import ProvisioningAuditContext
    from selahcue_api.apps.providers.policy_publication import publish_provider_policy

    def role(name):
        provider_mounts(name, capable=True)
        policy = policy_rows(capable=True)
        policy["deepgram"][0]["unattributed_usage_threshold"] = "10"
        settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE = write_mount(tmp_path, "equality-policy", policy)
        initialize_provider_runtime(entrypoint="operator" if name == "provisioner" else "celery_worker")

    role("provisioner")
    publish_provider_policy(
        cleanup_authorizations=(), audit=ProvisioningAuditContext("operator", uuid4(), "threshold-fixture"),
        clock=lambda: NOW-timedelta(hours=1),
    )
    role("usage")
    lower = NOW-timedelta(days=1)
    old = begin_scan(DEEPGRAM, interval=UTCInterval(lower-timedelta(days=1), lower))
    observed(old, [request("before-window", duration=99, created=lower-timedelta(microseconds=1))], NOW)
    clock.value += timedelta(seconds=1)
    current = begin_scan(DEEPGRAM, start=clock(), interval=UTCInterval(lower, NOW))
    observed(current, [
        request("inclusive-start", duration=10, created=lower),
        request("exclusive-end", completed=False, duration=900, created=NOW),
    ], clock())
    selected = ScopeUsageHealth.objects.get(scope_id=current.scope_id)
    assert (selected.state, selected.observed_total, selected.window_start, selected.window_end) == ("CURRENT", 10, lower, NOW)


@pytest.mark.django_db
def test_unresolved_old_facts_are_not_removed_during_normalized_retention(
    usage_runtime, clock, provider_mounts,
):
    from selahcue_api.apps.usage.models import ProviderUsageRecord, UsageCoverageGap

    usage_runtime()
    old = NOW - timedelta(weeks=105)
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(old-timedelta(days=1), old+timedelta(days=1)))
    observed(scan, [
        request("unresolved-old", duration=None, completed=False, created=old),
        request("unmapped-old", duration=0, created=old+timedelta(seconds=1)),
    ], NOW)
    preexisting = set(ProviderUsageRecord.objects.values_list("pk", flat=True))
    provider_mounts("maintenance", capable=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    assert prune_usage_batch(RetentionKind.NORMALIZED_RECORD, clock=clock).deleted == 0
    assert set(ProviderUsageRecord.objects.values_list("pk", flat=True)) == preexisting
    assert UsageCoverageGap.objects.filter(state="OPEN", reason="PLACEMENT_GAP").count() == 2
