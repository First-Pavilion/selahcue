"""Actual outer-sweep accounting for staged requirements."""
from datetime import timedelta
from uuid import UUID

import pytest

from provider_helpers import DEEPGRAM, cold_provider_cache, provider_mounts
from selahcue_api.apps.providers.contracts import ProviderScope, ProvisioningAuditContext
from selahcue_api.apps.providers.policy_publication import publish_provider_policy
from selahcue_api.apps.usage import recent, usage_tasks
from selahcue_api.apps.usage.models import UsageRecentMember, UsageRecentPlan, UsageScan
from selahcue_api.apps.usage.scans import enroll_scope
from test_effective_org_plan import church
from test_provider_observations import NOW, clock, usage_runtime
from test_usage_reconciliation import MONDAY, seed_old_unresolved_days
from test_usage_retained_history_load import _runtime


@pytest.mark.django_db
def test_real_sweeps_charge_two_large_transfers_and_discard_to_the_shared_cap(
    provider_mounts, settings, tmp_path, clock, monkeypatch,
):
    labels = (DEEPGRAM, ProviderScope("deepgram", "budget-transfer"), ProviderScope("deepgram", "budget-discard"))
    _runtime("provisioner", provider_mounts, settings, tmp_path, labels)
    publish_provider_policy(
        cleanup_authorizations=(), audit=ProvisioningAuditContext("budget", UUID(int=16), "budget-fixture"),
        clock=lambda: NOW - timedelta(hours=1),
    )
    _runtime("usage", provider_mounts, settings, tmp_path, labels)
    org = church()
    scopes = []
    for index, label in enumerate(labels):
        with usage_tasks.bounded_transaction():
            _, scope, _ = enroll_scope(label.provider, label.parent_scope_id, NOW)
            plan = UsageRecentPlan.objects.create(
                scope=scope, epoch=scope.pool.current_epoch, generation=scope.next_scan_generation,
                captured_at=NOW, cutoff=NOW, created_at=NOW, updated_at=NOW, lowest_start=MONDAY,
                phase="DISCARD" if index == 2 else "TRANSFER",
            )
            scope.next_scan_generation += 1
            scope.save(update_fields=("next_scan_generation",))
            UsageRecentMember.objects.bulk_create([
                UsageRecentMember(
                    plan=plan, org=org, kind="CURRENT", mapping=UUID(int=1000 * index + row + 1),
                    required_start=MONDAY, created_at=NOW,
                ) for row in range(127)
            ])
            scopes.append(scope)
    # Disable only broker delivery. The real sweep still performs discovery,
    # persists stage/cursor transitions and creates the business work.
    monkeypatch.setattr(usage_tasks, "repair_delivery_batch", lambda *args, **kwargs: 0)
    consumed = []
    for _ in range(16):
        before = UsageRecentMember.objects.count()
        charged = usage_tasks.sweep_usage(limit=100, clock=clock)
        after = UsageRecentMember.objects.count()
        actual = before - after
        consumed.append(actual)
        assert actual <= charged <= 100
        if not UsageRecentPlan.objects.filter(scope__in=scopes).exists():
            break
        clock.value += timedelta(seconds=60)
    assert sum(consumed) == 381 and len([items for items in consumed if items]) >= 4
    for scope in scopes[:2]:
        scan = UsageScan.objects.get(scope=scope, purpose="RECENT", requested_end=NOW)
        assert not scan.planning and scan.started_at == NOW
        assert scan.usagescanrequirement_set.filter(kind="CURRENT").count() == 127
        assert scan.usagework_set.filter(kind="SCAN").count() == 1
    assert not UsageScan.objects.filter(scope=scopes[2], purpose="RECENT").exists()


@pytest.mark.django_db
def test_discovery_transition_uses_only_the_unspent_transfer_allowance(usage_runtime, clock):
    from test_provider_reservation_binding import active_mapping

    for _ in range(3):
        active_mapping(church())
    usage_runtime()
    scope, _ = seed_old_unresolved_days(clock)
    with usage_tasks.bounded_transaction():
        _, locked, _ = enroll_scope("deepgram", scope.parent_scope_id, NOW)
        assert recent.advance_recent(locked, locked.pool.current_epoch, NOW, NOW, limit=4) == 4
    scan = UsageScan.objects.get(scope=scope, purpose="RECENT")
    assert scan.planning
    assert scan.usagescanrequirement_set.filter(kind="CURRENT").count() == 1
    assert UsageRecentMember.objects.filter(plan__scope=scope).count() == 2
    assert not scan.usagework_set.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("members", (1, 100, 250))
def test_hot_parent_uses_sixty_second_sweeps_with_original_capture_and_completion(
    members, usage_runtime, clock, monkeypatch, capsys,
):
    from selahcue_api.apps.usage import health
    from selahcue_api.apps.usage.contracts import UTCInterval
    from selahcue_api.apps.usage.models import SttOrgCoverage, UsageObservedInterval, UsageScope
    from selahcue_api.apps.usage.reconciliation import _fragments, reconcile_org
    from selahcue_api.apps.usage.scans import _next_page
    from test_provider_observations import complete, dg_data, page_claim, parse_dg, task_for
    from test_provider_reservation_binding import active_mapping
    from selahcue_api.apps.usage.observations import ingest_observations

    orgs = [church() for _ in range(members)]
    mappings = [active_mapping(org) for org in orgs]
    usage_runtime()
    monkeypatch.setattr(usage_tasks, "repair_delivery_batch", lambda *args, **kwargs: 0)
    captured, timeline = None, []
    old_member_total = 0

    def drain(scope):
        for _ in range(100):
            scan = _next_page(scope, clock())
            if scan is None:
                return
            work = task_for(scan, clock())
            page = parse_dg(dg_data(), interval=UTCInterval(scan.requested_start, scan.requested_end))
            ingest_observations(page, scan.pk, claim=page_claim(work, clock()))
            complete(scan, DEEPGRAM, clock())
            usage_tasks.finish_work(work.pk, work.lease_id, clock=clock)
            scope.refresh_from_db()
        pytest.fail("Synthetic phase created over 100 ready scans")

    actual_staged = [0]
    original_stage = recent._stage

    def stage(plan, found, now):
        actual_staged[0] += sum(row[3] < plan.cutoff for row in found)
        return original_stage(plan, found, now)

    monkeypatch.setattr(recent, "_stage", stage)
    for _ in range(18):
        actual_staged[0] = 0
        charged = usage_tasks.sweep_usage(limit=100, clock=clock)
        scope = UsageScope.objects.get(provider="deepgram", parent_scope_id=DEEPGRAM.parent_scope_id)
        current_total = UsageRecentMember.objects.filter(plan__scope=scope).count()
        transferred = old_member_total + actual_staged[0] - current_total
        assert 0 <= actual_staged[0] + transferred <= charged <= 100
        old_member_total = current_total
        pending = UsageRecentPlan.objects.filter(scope=scope).first()
        if captured is None:
            captured = pending.captured_at if pending is not None else clock()
        drain(scope)
        trial = UsageScan.objects.filter(scope=scope, purpose="RECENT", state="COMPLETE", started_at=captured).first()
        timeline.append({"at": clock().isoformat(), "visits": actual_staged[0] + transferred, "charged": charged})
        if trial is not None:
            break
        clock.value += timedelta(seconds=60)
    else:
        pytest.fail(f"RECENT did not complete for {members} members: {timeline}")
    assert trial.usagescanrequirement_set.filter(kind="CURRENT").count() == members
    assert trial.requested_end == captured.replace(microsecond=0)
    assert UsageObservedInterval.objects.filter(scan=trial, scan_started_at=captured).exists()
    org = orgs[0]
    row = org.providercredential_set.get(pk=mappings[0].mapping_id)
    parts = _fragments(scope, row, clock(), MONDAY, trial.requested_end)
    used_trial = bool(parts and any(part.observation.scan_id == trial.pk for part in parts))
    if clock() >= captured + health.FRESHNESS:
        assert not used_trial
    result = reconcile_org(org.pk, clock(), clock=clock)
    sources = list(SttOrgCoverage.objects.filter(publication_id=org.pk).values(
        "observed_interval__scan__purpose", "observed_interval__scan_started_at",
    ))
    if result.blocked_reason is None and clock() >= captured + health.FRESHNESS:
        assert sources and all(
            part["observed_interval__scan_started_at"] > captured for part in sources
        )
    with capsys.disabled():
        print("TASK6_HOT_CADENCE", {
            "members": members, "captured_at": captured.isoformat(), "completed_at": clock().isoformat(),
            "age_seconds": (clock()-captured).total_seconds(), "used_original_fragment": used_trial,
            "observed_through": result.observed_through, "blocked_reason": result.blocked_reason,
            "published_fragments_from_sweep_scheduled_scans": sources, "sweeps": timeline,
        }, flush=True)
