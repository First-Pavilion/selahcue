from datetime import timedelta

import pytest

from provider_helpers import DEEPGRAM, cold_provider_cache, identity, provider_mounts
from test_effective_org_plan import church
from test_provider_reservation_binding import active_mapping
from test_provider_observations import (
    NOW, begin_scan, clock, complete, dg_data, page_claim, parse_dg,
    request, task_for, usage_runtime,
)
from selahcue_api.apps.usage.models import ProviderUsageRecord, UsageOrgState, UsageWork
from selahcue_api.apps.usage.observations import ingest_observations, dirty_orgs
from selahcue_api.apps.usage.health import read_provider_usage_health
from selahcue_api.apps.usage.usage_tasks import (
    bounded_transaction, _claim_publication, claim_work, finish_work,
)


@pytest.mark.django_db
def test_same_scan_conflict_cannot_be_erased_by_repeating_first_value(usage_runtime, clock):
    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = task_for(scan, NOW)
    rows = [request("one-id", duration=value) for value in (0, 60, 0)]
    ingest_observations(parse_dg(dg_data(rows)), scan.pk, claim=page_claim(work, NOW))
    complete(scan, DEEPGRAM)
    record = ProviderUsageRecord.objects.get()
    actual_health = read_provider_usage_health("deepgram", NOW)
    assert record.attribution == "DISCREPANCY"
    assert actual_health.status != "CURRENT"


@pytest.mark.django_db
def test_compatible_same_scan_identity_enrichment_does_not_create_conflict(usage_runtime, clock):
    org = church()
    mapping = active_mapping(org, identity(key="one-key"))
    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = task_for(scan, NOW)
    rows = [request("one-id", key=key, duration=0) for key in (None, "one-key")]
    ingest_observations(parse_dg(dg_data(rows)), scan.pk, claim=page_claim(work, NOW))
    record = ProviderUsageRecord.objects.get()
    assert record.attribution == "EXACT_KEY"
    assert record.mapping_id == mapping.mapping_id


@pytest.mark.django_db
def test_dirty_update_between_reconcile_commit_and_work_finish_keeps_work_pending(usage_runtime, clock):
    org = church()
    usage_runtime()
    with bounded_transaction():
        dirty_orgs([org.pk], NOW)
    work = UsageWork.objects.get(kind="RECONCILE")
    delivery = _claim_publication(work.pk, False, clock)
    work = claim_work(work.pk, delivery[1], "RECONCILE", "provider_usage", clock=clock)
    # The first reconciliation transaction commits its captured revision.
    UsageOrgState.objects.filter(org=org).update(applied_revision=1, last_completed_at=NOW)
    # Ingestion lands before run_claimed invokes finish_work.
    with bounded_transaction():
        dirty_orgs([org.pk], NOW + timedelta(seconds=1))
    finish_work(work.pk, work.lease_id, clock=clock)
    state = UsageOrgState.objects.get(org=org)
    assert (state.dirty_revision, state.applied_revision) == (2, 1)
    assert UsageWork.objects.filter(kind="RECONCILE", org=org, state__in=("PENDING", "RUNNING")).exists()


@pytest.mark.django_db
def test_ancient_fact_later_attributed_still_blocks_placement_readiness(usage_runtime, clock, provider_mounts):
    from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
    from selahcue_api.apps.usage.contracts import UTCInterval
    from selahcue_api.apps.usage.models import UsageCoverageGap
    from selahcue_api.apps.usage.observations import attribute_scope_batch
    from selahcue_api.apps.usage.reconciliation import reconcile_org
    from selahcue_api.apps.usage.readiness import read_stt_readiness
    from test_usage_reconciliation import observed, MONDAY

    usage_runtime()
    ancient = NOW - timedelta(weeks=105)
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(ancient - timedelta(days=1), ancient + timedelta(days=1)))
    observed(scan, [request("ancient-later-known", key="late-binding", duration=2, created=ancient)], NOW)
    record = ProviderUsageRecord.objects.get()
    assert record.issue == "ANCIENT_FACT" and record.mapping_id is None
    assert UsageCoverageGap.objects.get(record=record).org_id is None

    provider_mounts("provisioner", capable=True)
    initialize_provider_runtime(entrypoint="operator")
    org = church()
    mapping = active_mapping(org, identity(key="late-binding"))
    usage_runtime()
    changed = attribute_scope_batch(scan.scope_id, after=None, clock=clock)
    assert changed.changed == 1
    record.refresh_from_db()
    assert record.mapping_id == mapping.mapping_id and record.issue == "ANCIENT_FACT"
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW), org=org, mapping=mapping.mapping_id)
    observed(initial, [], NOW)
    result = reconcile_org(org.pk, NOW, clock=clock)
    ready = read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=NOW)
    assert result.blocked_reason == "PLACEMENT_GAP"
    assert ready.status != "current_observed"


@pytest.mark.django_db
def test_known_ancient_direct_ingestion_control_blocks_readiness(usage_runtime, clock):
    from selahcue_api.apps.usage.contracts import UTCInterval
    from selahcue_api.apps.usage.reconciliation import reconcile_org
    from selahcue_api.apps.usage.readiness import read_stt_readiness
    from test_usage_reconciliation import observed, MONDAY

    org = church()
    mapping = active_mapping(org, identity(key="already-known"))
    usage_runtime()
    ancient = NOW - timedelta(weeks=105)
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(ancient - timedelta(days=1), ancient + timedelta(days=1)))
    observed(scan, [request("ancient-known", key="already-known", duration=2, created=ancient)], NOW)
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW), org=org, mapping=mapping.mapping_id)
    observed(initial, [], NOW)
    result = reconcile_org(org.pk, NOW, clock=clock)
    ready = read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=NOW)
    assert result.blocked_reason == "PLACEMENT_GAP"
    assert ready.status != "current_observed"


@pytest.mark.django_db
def test_direct_scan_work_charges_setup_against_the_dispatch_deadline(usage_runtime, clock, monkeypatch):
    from selahcue_api.apps.usage import scans, usage_tasks

    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = task_for(scan, NOW)
    current_ns = [10_000_000_000]
    actual_role = usage_tasks.require_usage_role

    def slow_setup(*args, **kwargs):
        current_ns[0] += 106_000_000_000
        return actual_role(*args, **kwargs)

    monkeypatch.setattr(usage_tasks, "require_usage_role", slow_setup)
    monkeypatch.setattr(scans.deepgram_usage, "read_usage_page", lambda *_: parse_dg(dg_data()))
    usage_tasks.run_scan_work(work.pk, clock=clock, monotonic_ns=lambda: current_ns[0])
    page = scan.usagepageclaim_set.get()
    assert (page.state, page.attempts) == ("PENDING", 0)


def test_initial_discovery_does_not_schedule_after_selection_exhausts_deadline(monkeypatch, clock):
    from selahcue_api.apps.usage import usage_tasks

    monotonic = [0]
    scheduled = []

    def select(*_args, **_kwargs):
        monotonic[0] = 10
        return object()

    monkeypatch.setattr(usage_tasks.time, "monotonic", lambda: monotonic[0])
    monkeypatch.setattr(usage_tasks, "_initial_candidate", select)
    monkeypatch.setattr(usage_tasks, "_initial_scan", lambda *_args, **_kwargs: scheduled.append(True) or True)
    assert usage_tasks._initial_batch(1, 10, clock) == (1, 0)
    assert scheduled == []


@pytest.mark.django_db
def test_overrun_writes_the_event_link_in_the_initial_audit_insert(usage_runtime):
    from django.db import connection, transaction
    from selahcue_api.apps.usage.models import UsageReconcileAudit
    from selahcue_api.apps.usage.reconciliation import _audit
    from test_effective_org_plan import device, licence
    from test_usage_reconciliation import reserve_stt

    org = church()
    install = device(licence(org))
    mapping = active_mapping(org)
    week = reserve_stt(install, mapping.mapping_id, NOW).week
    if connection.vendor == "sqlite":
        with connection.cursor() as cursor:
            cursor.execute("""CREATE TEMP TRIGGER test_reconcile_append_only BEFORE UPDATE ON
                selahcue_usage_usagereconcileaudit BEGIN SELECT RAISE(ABORT, 'immutable audit'); END""")
    try:
        with transaction.atomic():
            for _ in range(2):
                _audit(org, 1, "OVERRUN_RECORDED", week, None, 40, NOW)
        row = UsageReconcileAudit.objects.get()
        assert row.audit_event.action == "usage.overrun_recorded"
        assert row.audit_event.actor_kind == "service"
        assert row.units == 40
    finally:
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER test_reconcile_append_only")


@pytest.mark.django_db
def test_mapped_conflict_cannot_clear_on_later_page_of_same_scan(usage_runtime, clock):
    from selahcue_api.apps.usage.models import UsageCoverageGap

    org = church()
    mapping = active_mapping(org, identity(key="mapped-conflicted"))
    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = task_for(scan, NOW)
    fact = request("across-pages", key="mapped-conflicted", duration=0)
    conflict = request("across-pages", key="mapped-conflicted", duration=60)
    first = parse_dg(dg_data([fact, conflict, *[fact] * 98]))
    ingest_observations(first, scan.pk, claim=page_claim(work, NOW))
    repeat = parse_dg(dg_data([fact], page=1), cursor="1")
    ingest_observations(repeat, scan.pk, claim=page_claim(work, NOW))
    complete(scan, DEEPGRAM)
    row = ProviderUsageRecord.objects.get()
    assert row.mapping_id == mapping.mapping_id
    assert (row.issue, row.conflict_generation) == ("IDENTITY_CONFLICT", scan.generation)
    assert UsageCoverageGap.objects.filter(record=row, org=org, state="OPEN", reason="IDENTITY_CONFLICT").exists()


@pytest.mark.django_db
def test_compatible_null_project_and_key_enrich_but_conflicting_key_does_not(usage_runtime, clock):
    org = church()
    mapping = active_mapping(org, identity(key="verified"))
    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = task_for(scan, NOW)
    missing = request("enrichment", duration=0)
    missing["project_uuid"] = None
    bound = request("enrichment", key="verified", duration=0)
    other = request("contradiction", key="verified", duration=0)
    contradicts = request("contradiction", key="unrelated-key", duration=0)
    page = parse_dg(dg_data([missing, bound, missing, other, contradicts]))
    ingest_observations(page, scan.pk, claim=page_claim(work, NOW))
    rows = {item.request_id: item for item in ProviderUsageRecord.objects.all()}
    assert rows["enrichment"].mapping_id == mapping.mapping_id
    assert rows["enrichment"].current_version.safe_facts["api_key_id"] == "verified"
    assert rows["enrichment"].issue is None
    assert rows["contradiction"].mapping_id == mapping.mapping_id
    assert rows["contradiction"].issue == "IDENTITY_CONFLICT"


@pytest.mark.django_db
def test_recent_plan_stages_all_members_before_work_and_preserves_intent_after_restart(usage_runtime, clock):
    from selahcue_api.apps.usage.models import UsageRecentPlan, UsageScope, UsageScan
    from selahcue_api.apps.usage.usage_tasks import _schedule_periodic
    from test_usage_reconciliation import seed_old_unresolved_days

    mapped = [active_mapping(church()).mapping_id for _ in range(3)]
    usage_runtime()
    scope, _ = seed_old_unresolved_days(clock)
    assert _schedule_periodic(scope, "RECENT_SCOPE", clock, limit=2) == 2
    assert UsageRecentPlan.objects.get(scope=scope).usagerecentmember_set.count() == 2
    assert not UsageScan.objects.filter(scope=scope, purpose="RECENT").exists()
    assert _schedule_periodic(UsageScope.objects.get(pk=scope.pk), "RECENT_SCOPE", clock, limit=2) == 2
    staged = UsageScan.objects.get(scope=scope, purpose="RECENT")
    assert staged.planning
    assert staged.usagescanrequirement_set.count() == 1
    assert not staged.usagepageclaim_set.exists() and not staged.usagework_set.exists()
    clock.value += timedelta(seconds=301)
    _schedule_periodic(UsageScope.objects.get(pk=scope.pk), "RECENT_SCOPE", clock, limit=2)
    staged.refresh_from_db()
    assert not staged.planning
    assert (staged.started_at, staged.requested_end) == (NOW, NOW)
    assert set(staged.usagescanrequirement_set.values_list("mapping", flat=True)) >= set(mapped)
    assert staged.usagework_set.filter(state="PENDING").count() == 1
    assert not UsageRecentPlan.objects.filter(scope=scope).exists()


@pytest.mark.django_db
def test_scope_revision_denies_before_bounded_sweep_repairs_affected_orgs(usage_runtime, clock):
    import time
    from selahcue_api.apps.usage.contracts import UTCInterval
    from selahcue_api.apps.usage.models import UsageScope
    from selahcue_api.apps.usage.readiness import read_stt_readiness
    from selahcue_api.apps.usage.reconciliation import reconcile_org
    from selahcue_api.apps.usage.usage_tasks import _reschedule_publications
    from test_usage_reconciliation import MONDAY, observed

    mappings = [(org, active_mapping(org)) for org in (church(), church(), church())]
    usage_runtime()
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(scan, [], NOW)
    for org, mapping in mappings:
        assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
        assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=NOW).status == "current_observed"
    clock.value += timedelta(seconds=1)
    replacement = begin_scan(DEEPGRAM, start=clock(), interval=UTCInterval(MONDAY, clock()))
    work = task_for(replacement, clock())
    ingest_observations(
        parse_dg(dg_data(), interval=UTCInterval(MONDAY, clock())), replacement.pk, claim=page_claim(work, clock()),
    )
    assert not UsageWork.objects.filter(kind="RECONCILE").exists()
    for org, mapping in mappings:
        assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=clock()).status == "stale"
    deadline = time.monotonic() + 10
    for _ in mappings:
        assert _reschedule_publications(clock, 1, deadline) == 1
    assert UsageWork.objects.filter(kind="RECONCILE").count() == 3


@pytest.mark.django_db
def test_retention_stops_before_action_when_the_selection_uses_its_budget(usage_runtime, clock, provider_mounts, monkeypatch):
    from contextlib import contextmanager
    from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
    from selahcue_api.apps.usage import retention
    from selahcue_api.apps.usage.models import UsageReservation
    from selahcue_api.apps.usage.observation_contracts import RetentionKind
    from test_effective_org_plan import device, licence
    from test_usage_reconciliation import reserve_stt

    org = church()
    install = device(licence(org))
    mapping = active_mapping(org)
    reservation = reserve_stt(install, mapping.mapping_id, NOW)
    UsageReservation.objects.filter(pk=reservation.pk).update(state="RELEASED", created_at=NOW - timedelta(weeks=105))
    provider_mounts("maintenance", capable=True)
    initialize_provider_runtime(entrypoint="celery_worker")

    original = retention.bounded_transaction
    elapsed = [retention.time.monotonic()]
    action_called = []
    monkeypatch.setattr(retention.time, "monotonic", lambda: elapsed[0])

    @contextmanager
    def selection(*args, **kwargs):
        with original(*args, **kwargs):
            yield
        elapsed[0] += 11

    monkeypatch.setattr(retention, "bounded_transaction", selection)
    monkeypatch.setattr(retention, "_prune_candidate", lambda *_args, **_kwargs: action_called.append(True))
    outcome = retention.prune_usage_batch(RetentionKind.TERMINAL_RESERVATION, clock=clock)
    assert (outcome.scanned, outcome.deleted, outcome.has_more) == (1, 0, True)
    assert not action_called
    assert UsageReservation.objects.filter(pk=reservation.pk).exists()


@pytest.mark.django_db
def test_retention_removes_old_page_and_superseded_version_but_preserves_current_provenance(
    usage_runtime, clock, provider_mounts,
):
    from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
    from selahcue_api.apps.usage.contracts import UTCInterval
    from selahcue_api.apps.usage.models import ProviderUsageVersion, UsagePageClaim
    from selahcue_api.apps.usage.observation_contracts import RetentionKind
    from selahcue_api.apps.usage.retention import prune_usage_batch
    from test_usage_reconciliation import observed

    org = church()
    active_mapping(org, identity(key="retained-facts"))
    usage_runtime()
    old = NOW - timedelta(days=36)
    interval = UTCInterval(old - timedelta(days=1), old)
    event = old - timedelta(hours=1)
    for offset, value in enumerate((1, 2)):
        clock.value = old + timedelta(seconds=offset)
        scan = begin_scan(DEEPGRAM, start=clock(), interval=interval)
        observed(scan, [request("retained-current", key="retained-facts", duration=value, created=event)], clock())
    live = ProviderUsageRecord.objects.get().current_version
    assert live.source_page_id and live.source_scan_id == scan.pk

    provider_mounts("maintenance", capable=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    clock.value = NOW
    assert prune_usage_batch(RetentionKind.PAGE_DETAIL, clock=clock).deleted == 2
    assert prune_usage_batch(RetentionKind.SUPERSEDED_VERSION, clock=clock).deleted == 1
    live.refresh_from_db()
    assert not UsagePageClaim.objects.exists()
    assert ProviderUsageVersion.objects.get().pk == live.pk
    assert live.source_page_id is None and live.source_scan_id == scan.pk
    assert (live.source_interval_start, live.source_interval_end) == (interval.start, interval.end)
    assert live.duration_seconds == 2


@pytest.mark.django_db
def test_outbox_publish_exhaustion_rearms_work_without_spending_page_attempts(usage_runtime, clock):
    from selahcue_api.apps.usage.models import UsageOutbox
    from selahcue_api.apps.usage.usage_tasks import _finish_publication

    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    work = scan.usagework_set.get()
    for offset in (0, 5, 30):
        clock.value = NOW + timedelta(seconds=offset)
        _, delivery, lease = _claim_publication(work.pk, False, clock)
        _finish_publication(work.pk, delivery, lease, False, clock)
    work.refresh_from_db()
    exhausted = UsageOutbox.objects.get(work=work, generation=1)
    assert (exhausted.state, exhausted.publish_attempts) == ("FAILED", 3)
    assert work.execution_generation == 2
    assert work.due_at == clock() + timedelta(seconds=120)
    assert scan.usagepageclaim_set.get().attempts == 0
    clock.value += timedelta(seconds=119)
    assert _claim_publication(work.pk, False, clock) is None
    clock.value += timedelta(seconds=1)
    assert _claim_publication(work.pk, False, clock)[1] == UsageOutbox.objects.get(work=work, generation=2).pk


@pytest.mark.django_db
def test_recent_plan_discards_private_requirements_on_policy_epoch_change(usage_runtime, clock, provider_mounts):
    from uuid import uuid4
    from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
    from selahcue_api.apps.providers.contracts import CleanupAuthorization, ProvisioningAuditContext
    from selahcue_api.apps.providers.policy_publication import publish_provider_policy
    from selahcue_api.apps.usage.models import UsageRecentPlan, UsageScan
    from selahcue_api.apps.usage.usage_tasks import _schedule_periodic
    from test_usage_reconciliation import seed_old_unresolved_days

    for _ in range(3):
        active_mapping(church())
    usage_runtime()
    scope, _ = seed_old_unresolved_days(clock)
    for _ in range(2):
        _schedule_periodic(scope, "RECENT_SCOPE", clock, limit=2)
    provisional = UsageScan.objects.get(scope=scope, purpose="RECENT")
    assert provisional.planning
    clock.value += timedelta(seconds=1)
    provider_mounts("provisioner", capable=True)
    initialize_provider_runtime(entrypoint="operator")
    publish_provider_policy(
        cleanup_authorizations=(CleanupAuthorization(DEEPGRAM, "changed-epoch"),),
        audit=ProvisioningAuditContext("synthetic-operator", uuid4(), "test-receipt"),
        clock=clock,
    )
    usage_runtime()
    for _ in range(4):
        _schedule_periodic(scope, "RECENT_SCOPE", clock, limit=2)
        if not UsageRecentPlan.objects.filter(scope=scope).exists():
            break
    assert not UsageScan.objects.filter(pk=provisional.pk).exists()
    assert not UsageWork.objects.filter(scan_id=provisional.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("gap", (False, True))
def test_required_fragments_preserve_gap_and_oldest_capture_expiry(usage_runtime, clock, gap):
    from selahcue_api.apps.usage.contracts import UTCInterval
    from selahcue_api.apps.usage.readiness import read_stt_readiness
    from selahcue_api.apps.usage.reconciliation import reconcile_org
    from test_usage_reconciliation import MONDAY, observed

    org = church()
    mapping = active_mapping(org)
    usage_runtime()
    end = NOW - timedelta(seconds=60)
    split = end - timedelta(days=1)
    oldest = NOW - timedelta(seconds=200)
    clock.value = oldest
    initial = begin_scan(
        DEEPGRAM, interval=UTCInterval(MONDAY, split - timedelta(seconds=int(gap))), start=oldest,
    )
    observed(initial, [], clock())
    clock.value = end
    next_scan = begin_scan(DEEPGRAM, interval=UTCInterval(split, end), start=end)
    observed(next_scan, [], clock())
    clock.value = NOW
    result = reconcile_org(org.pk, NOW, clock=clock)
    at_now = read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=NOW)
    if gap:
        assert result.blocked_reason == "REVISION_CONFLICT"
        assert at_now.status != "current_observed"
    else:
        assert result.blocked_reason is None and at_now.status == "current_observed"
        assert at_now.valid_until == oldest + timedelta(seconds=300)
        expired = read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=at_now.valid_until)
        assert expired.blocked_reason == "coverage_stale"


@pytest.mark.django_db
def test_oa_verified_project_only_and_unknown_key_have_different_health_population(usage_runtime, clock):
    from provider_helpers import OPENAI
    from selahcue_api.apps.usage.models import ScopeUsageHealth
    from test_provider_observations import COVERAGE, bucket, oa_data, parse_oa, result

    org = church()
    mapping = active_mapping(org, identity(OPENAI, key="openai-verified"))
    usage_runtime()
    initial = begin_scan(OPENAI)
    work = task_for(initial, clock())
    project = "synthetic-openai-project"
    page = parse_oa(oa_data(bucket(COVERAGE.start, result(None, None, project_id=project))))
    ingest_observations(page, initial.pk, claim=page_claim(work, clock()))
    complete(initial, OPENAI, clock())
    retained = ProviderUsageRecord.objects.get()
    assert (retained.attribution, retained.mapping_id) == ("PROJECT_ONLY", mapping.mapping_id)
    ready = ScopeUsageHealth.objects.get(scope_id=initial.scope_id)
    assert (ready.state, ready.observed_total, ready.unquantifiable_count) == ("CURRENT", 0, 0)

    clock.value += timedelta(seconds=1)
    scan = begin_scan(OPENAI, start=clock())
    work = task_for(scan, clock())
    page = parse_oa(oa_data(bucket(
        COVERAGE.start + timedelta(hours=1), result(999, 999, project_id=project, api_key_id="unknown"),
    )))
    ingest_observations(page, scan.pk, claim=page_claim(work, clock()))
    complete(scan, OPENAI, clock())
    current = ScopeUsageHealth.objects.get(scope_id=initial.scope_id)
    assert (current.state, current.observed_total, current.conflict_count) == ("UNRESOLVED", 0, 1)


@pytest.mark.django_db
def test_recent_plan_captures_retirement_and_excludes_post_cutoff_activation(usage_runtime, clock, provider_mounts):
    from uuid import uuid4
    from provider_helpers import SECRET, audit
    from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
    from selahcue_api.apps.providers.contracts import RegistryReason
    from selahcue_api.apps.providers.models import ProviderCredential
    from selahcue_api.apps.providers.registry import import_existing_mapping, retire_mapping
    from selahcue_api.apps.usage.models import UsageRecentPlan, UsageScan
    from selahcue_api.apps.usage.usage_tasks import _schedule_periodic
    from test_usage_reconciliation import seed_old_unresolved_days

    mappings = sorted(active_mapping(church()).mapping_id for _ in range(3))
    usage_runtime()
    scope, _ = seed_old_unresolved_days(clock)
    _schedule_periodic(scope, "RECENT_SCOPE", clock, limit=1)

    clock.value += timedelta(seconds=1)
    provider_mounts("provisioner", capable=True)
    initialize_provider_runtime(entrypoint="operator")
    retired = ProviderCredential.objects.get(pk=mappings[-1])
    retire_mapping(mapping_id=retired.pk, expected_revision=retired.revision, now=clock(), audit=audit(RegistryReason.RETIRE))
    new = import_existing_mapping(
        mapping_id=uuid4(), org_id=church().pk, identity=identity(key="after-cutoff-activation"),
        secret=SECRET, now=clock(), audit=audit(RegistryReason.IMPORT_APPROVED_ALLOCATION),
    )
    usage_runtime()
    for _ in range(10):
        _schedule_periodic(scope, "RECENT_SCOPE", clock, limit=1)
        if not UsageRecentPlan.objects.filter(scope=scope).exists():
            break
    scan = UsageScan.objects.get(scope=scope, purpose="RECENT")
    assert set(scan.usagescanrequirement_set.filter(kind="CURRENT").values_list("mapping", flat=True)) == set(mappings)
    assert not scan.usagescanrequirement_set.filter(mapping=new.mapping_id).exists()
    assert scan.started_at == NOW


@pytest.mark.django_db
def test_retention_checkpoints_after_one_hundred_physical_deletions(usage_runtime, clock, provider_mounts):
    from uuid import uuid4
    from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
    from selahcue_api.apps.usage.models import UsageReservation
    from selahcue_api.apps.usage.observation_contracts import RetentionKind
    from selahcue_api.apps.usage.retention import prune_usage_batch
    from test_effective_org_plan import device, licence
    from test_usage_reconciliation import reserve_stt

    org = church()
    install = device(licence(org))
    mapping = active_mapping(org)
    first = reserve_stt(install, mapping.mapping_id, NOW)
    shared = {
        field.attname: getattr(first, field.attname)
        for field in UsageReservation._meta.concrete_fields
        if field.name not in ("id", "idempotency_key", "created_at", "state")
    }
    UsageReservation.objects.bulk_create([
        UsageReservation(**shared, idempotency_key=uuid4(), state="RELEASED") for _ in range(100)
    ])
    UsageReservation.objects.update(created_at=NOW - timedelta(weeks=105), state="RELEASED")
    provider_mounts("maintenance", capable=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    first_batch = prune_usage_batch(RetentionKind.TERMINAL_RESERVATION, clock=clock)
    assert (first_batch.scanned, first_batch.deleted, first_batch.has_more) == (100, 100, True)
    assert UsageReservation.objects.count() == 1
    second_batch = prune_usage_batch(RetentionKind.TERMINAL_RESERVATION, clock=clock)
    assert (second_batch.scanned, second_batch.deleted, second_batch.has_more) == (1, 1, False)
    assert not UsageReservation.objects.exists()


@pytest.mark.django_db
def test_health_scan_keeps_dispatch_authority_during_same_window_planning(usage_runtime, clock):
    from selahcue_api.apps.usage.models import UsageRecentPlan, UsageScan
    from selahcue_api.apps.usage.usage_tasks import _schedule_periodic
    from test_usage_reconciliation import MONDAY, seed_old_unresolved_days

    for _ in range(3):
        active_mapping(church())
    usage_runtime()
    scope, _ = seed_old_unresolved_days(clock)
    clock.value = MONDAY + timedelta(days=1)
    for _ in range(3):
        _schedule_periodic(scope, "RECENT_SCOPE", clock, limit=2)
    healthy = UsageScan.objects.get(scope=scope, purpose="HEALTH", requested_end=clock())
    recent = UsageScan.objects.get(scope=scope, purpose="RECENT", requested_end=clock())
    assert (healthy.requested_start, recent.requested_start) == (MONDAY, MONDAY)
    assert healthy.usagework_set.filter(state="PENDING").exists()
    assert recent.planning and not recent.usagework_set.exists()
    complete_page = parse_dg(dg_data(), interval=healthy_interval(healthy))
    work = task_for(healthy, clock())
    ingest_observations(complete_page, healthy.pk, claim=page_claim(work, clock()))
    complete(healthy, DEEPGRAM, clock())
    _schedule_periodic(scope, "RECENT_SCOPE", clock, limit=2)
    recent.refresh_from_db()
    assert not recent.planning and recent.usagework_set.exists()
    assert not UsageRecentPlan.objects.filter(scope=scope).exists()


def healthy_interval(scan):
    from selahcue_api.apps.usage.contracts import UTCInterval

    return UTCInterval(scan.requested_start, scan.requested_end)


@pytest.mark.django_db
def test_first_observation_captured_before_mapping_activation_cannot_publish(usage_runtime, clock, provider_mounts):
    from uuid import uuid4
    from provider_helpers import SECRET, audit
    from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
    from selahcue_api.apps.providers.contracts import RegistryReason
    from selahcue_api.apps.providers.registry import import_existing_mapping
    from selahcue_api.apps.usage.contracts import UTCInterval
    from selahcue_api.apps.usage.readiness import read_stt_readiness
    from selahcue_api.apps.usage.reconciliation import reconcile_org
    from test_usage_reconciliation import MONDAY, observed

    org = church()
    usage_runtime()
    queued = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    clock.value += timedelta(seconds=1)
    provider_mounts("provisioner", capable=True)
    initialize_provider_runtime(entrypoint="operator")
    mapping = import_existing_mapping(
        mapping_id=uuid4(), org_id=org.pk, identity=identity(), secret=SECRET,
        now=clock(), audit=audit(RegistryReason.IMPORT_APPROVED_ALLOCATION),
    )
    usage_runtime()
    observed(queued, [], clock())
    assert reconcile_org(org.pk, clock(), clock=clock).blocked_reason == "REVISION_CONFLICT"
    assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=clock()).status == "not_initialized"
