"""Accounting and recovery boundaries exercised through observed provider facts."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from provider_helpers import DEEPGRAM, audit, cold_provider_cache, identity, provider_mounts
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.providers.contracts import RegistryReason
from selahcue_api.apps.providers.models import ProviderCredential
from selahcue_api.apps.providers.registry import retire_mapping
from selahcue_api.apps.usage.contracts import UTCInterval
from selahcue_api.apps.usage.models import ProviderUsageRecord, UsageWeek, UsageWeekProjection
from selahcue_api.apps.usage.readiness import read_stt_readiness
from selahcue_api.apps.usage.reconciliation import reconcile_org, settlement_floor
from selahcue_api.apps.usage.weeks import local_week
from test_effective_org_plan import church, device, licence, staff_grant
from test_provider_observations import NOW, begin_scan, clock, request, usage_runtime
from test_provider_reservation_binding import active_mapping
from test_usage_reconciliation import MONDAY, observed, reserve_stt, set_issued


def frozen_week(org, zone, instant):
    bounds = local_week(zone, instant)
    return UsageWeek.objects.create(
        org=org, tz_name=bounds.tz_name, week_start_local=bounds.monday,
        starts_at=bounds.start, ends_at=bounds.end, counted_from=bounds.start,
        admissions_start_at=bounds.admissions_start_at, high_water_rank=1,
        opening_stt_seconds_limit=1200, high_water_stt_seconds_limit=1200,
        opening_notes_limit=1, high_water_notes_limit=1,
    )


@pytest.mark.django_db
def test_historical_materialization_pauses_after_sixteen_and_resumes_without_freshness_reset(usage_runtime, clock):
    org = church()
    mapping = active_mapping(org, identity(key="continuation"))
    prior = frozen_week(org, "UTC", MONDAY - timedelta(weeks=20))
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(prior.ends_at, NOW))
    observed(initial, [request(key="continuation", duration=5)], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason == "REVISION_CONFLICT"
    assert UsageWeekProjection.objects.count() == 16
    assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=NOW).status != "current_observed"
    result = reconcile_org(org.pk, NOW, clock=clock)
    assert result.blocked_reason is None
    assert UsageWeekProjection.objects.count() == 20
    assert UsageWeek.objects.get(org=org, starts_at=MONDAY).stt_seconds_settled == 5
    assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=NOW).valid_until == NOW + timedelta(seconds=300)


@pytest.mark.django_db
def test_missing_historical_predecessor_blocks_instead_of_guessing_old_accounting(usage_runtime, clock):
    org = church()
    mapping = active_mapping(org, identity(key="no-predecessor"))
    current = frozen_week(org, "UTC", MONDAY)
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY-timedelta(days=4), NOW))
    observed(initial, [request(key="no-predecessor", duration=5, created=MONDAY-timedelta(days=2))], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason == "PLACEMENT_GAP"
    record = ProviderUsageRecord.objects.get()
    assert record.placed_week_id is None and record.issue == "PLACEMENT_GAP"
    assert list(UsageWeek.objects.values_list("pk", flat=True)) == [current.pk]
    assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=NOW).blocked_reason == "placement_gap"


@pytest.mark.django_db
def test_observed_facts_before_at_and_after_upgrade_counted_from(usage_runtime, clock):
    org = church()
    install = device(licence(org))
    mapping = active_mapping(org, identity(key="counted-from"))
    before = NOW - timedelta(hours=3)
    original = reserve_stt(install, mapping.mapping_id, before).week
    upgrade = NOW - timedelta(hours=2)
    staff_grant(org, "CORE", upgrade, NOW + timedelta(days=1))
    reserve_stt(install, mapping.mapping_id, upgrade)
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(initial, [
        request("before-upgrade", key="counted-from", duration=101, created=upgrade-timedelta(microseconds=1)),
        request("at-upgrade", key="counted-from", duration=11, created=upgrade),
        request("after-upgrade", key="counted-from", duration=7, created=upgrade+timedelta(microseconds=1)),
    ], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    original.refresh_from_db()
    assert (original.counted_from, original.stt_seconds_settled) == (upgrade, 18)
    assert ProviderUsageRecord.objects.filter(placed_week=original).count() == 3


@pytest.mark.django_db
def test_historical_two_zone_edits_preserve_dst_and_half_open_successor_boundary(usage_runtime, clock):
    org = church("UTC")
    mapping = active_mapping(org, identity(key="dst-continuation"))
    anchor = frozen_week(org, "America/New_York", datetime(2026, 10, 20, 12, tzinfo=UTC))
    org.timezone = "America/New_York"
    org.save(update_fields=("timezone",))
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(anchor.ends_at, NOW))
    observed(initial, [request("dst-fall", key="dst-continuation", duration=1500, created=anchor.ends_at)], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    dst = UsageWeek.objects.get(org=org, starts_at=anchor.ends_at)
    assert (dst.ends_at - dst.starts_at).total_seconds() == 169 * 3600
    original_current = UsageWeek.objects.get(org=org, starts_at__lte=NOW, ends_at__gt=NOW)
    assert original_current.stt_seconds_carried_debt == 0
    org.timezone = "Etc/GMT+12"
    org.save(update_fields=("timezone",))
    clock.value = original_current.ends_at + timedelta(hours=8)
    upper = clock()
    boundary = begin_scan(DEEPGRAM, start=upper, interval=UTCInterval(original_current.starts_at, upper))
    observed(boundary, [
        request("at-succ-end", key="dst-continuation", duration=12, created=original_current.ends_at),
    ], upper)
    assert reconcile_org(org.pk, upper, clock=clock).blocked_reason is None
    successor = UsageWeek.objects.get(org=org, starts_at=original_current.ends_at)
    assert successor.tz_name == "Etc/GMT+12"
    assert (successor.stt_seconds_settled, successor.stt_seconds_carried_debt) == (12, 0)
    assert UsageWeekProjection.objects.get(week=successor).predecessor_week_id == original_current.pk
    assert ProviderUsageRecord.objects.get(request_id="at-succ-end").placed_week_id == successor.pk


@pytest.mark.parametrize(("mint_offset", "expected"), [
    (None, 1800), (0, 1830), (800, 2030),
])
def test_early_future_renewal_and_late_historical_mint_floor(mint_offset, expected):
    authorized = NOW + timedelta(seconds=900)
    minted = None if mint_offset is None else NOW + timedelta(seconds=mint_offset)
    reservation = SimpleNamespace(authorized_until=authorized, last_minted_at=minted)
    assert settlement_floor(reservation) == NOW + timedelta(seconds=expected)


@pytest.mark.django_db
def test_retired_incomplete_fact_holds_new_active_and_original_slices(usage_runtime, clock, provider_mounts):
    org = church()
    install = device(licence(org))
    old = active_mapping(org, identity(key="retired-incomplete"))
    earlier = NOW - timedelta(hours=2)
    first = reserve_stt(install, old.mapping_id, earlier)
    set_issued(first, earlier)
    row = ProviderCredential.objects.get(pk=old.mapping_id)
    retire_mapping(
        mapping_id=row.pk, expected_revision=row.revision, now=earlier + timedelta(minutes=1),
        audit=audit(RegistryReason.RETIRE),
    )
    active = active_mapping(org, identity(key="active-complete"))
    second = reserve_stt(install, active.mapping_id, earlier + timedelta(minutes=2))
    set_issued(second, earlier + timedelta(minutes=2))
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(initial, [request(key="retired-incomplete", completed=False, duration=None)], NOW)
    current = reconcile_org(org.pk, NOW, clock=clock)
    assert current.blocked_reason is None and current.settled_reservations == ()
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.state, second.state) == ("ISSUED", "ISSUED")


@pytest.mark.django_db
@pytest.mark.parametrize(("state", "retry"), (("40001", True), ("40P01", True), ("08006", False)))
def test_reconcile_retries_only_errors_with_known_rollback(state, retry, usage_runtime, clock, monkeypatch):
    from django.db import OperationalError
    from selahcue_api.apps.usage import reconciliation
    from selahcue_api.apps.usage.observation_contracts import ReconcileResult

    class EngineError(Exception):
        sqlstate = state

    attempts = []
    usage_runtime()
    complete = ReconcileResult(123, (), (), None, None)

    def commit(org, at, read_clock):
        attempts.append((org, at))
        if len(attempts) == 1:
            raise OperationalError("inert") from EngineError()
        return complete

    monkeypatch.setattr(reconciliation, "_reconcile", commit)
    if retry:
        assert reconcile_org(123, NOW, clock=clock) == complete
    else:
        with pytest.raises(OperationalError):
            reconcile_org(123, NOW, clock=clock)
    assert len(attempts) == (2 if retry else 1)


@pytest.mark.django_db
def test_spring_dst_projected_accounting_week_has_167_hours(usage_runtime, clock):
    org = church("America/New_York")
    active_mapping(org, identity(key="spring-clock"))
    before_dst = datetime(2026, 2, 24, 12, tzinfo=UTC)
    anchor = frozen_week(org, "America/New_York", before_dst)
    usage_runtime()
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(anchor.ends_at, NOW))
    observed(scan, [request("spring-clock", key="spring-clock", duration=3, created=anchor.ends_at)], NOW)
    result = reconcile_org(org.pk, NOW, clock=clock)
    assert result.blocked_reason == "REVISION_CONFLICT"  # Retained continuation extends beyond this batch.
    spring = UsageWeek.objects.get(org=org, starts_at=anchor.ends_at)
    assert (spring.ends_at-spring.starts_at).total_seconds() == 167*3600
    assert UsageWeekProjection.objects.get(week=spring).predecessor_week_id == anchor.pk
    assert ProviderUsageRecord.objects.get().placed_week_id == spring.pk
