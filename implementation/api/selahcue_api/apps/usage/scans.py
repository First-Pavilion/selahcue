"""Frozen observation intervals, a fenced per-scope page lane, and scan completion."""
from datetime import timedelta
import time
from uuid import uuid4

from django.db import connection
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone

from selahcue_api.apps.providers.adapters import deepgram_usage, openai_usage
from selahcue_api.apps.providers.contracts import ProviderScope
from selahcue_api.apps.providers.models import ProviderCapacityPool, ProviderCredential

from . import health
from .contracts import UTCInterval
from .models import (
    ProviderUsageRecord, UsageCoverageGap, UsageObservedInterval, UsagePageClaim, UsageScan, UsageScanRequirement,
    UsageScope, UsageWork,
)
from .observation_contracts import (
    Attribution, DGCompletion, ObservedCoverage, ScanPurpose, ScanState, UsageClaim, UsageFailureCode as Code, UsageProfile, UsageRejected,
)
from .observations import RETENTION_AGE, bump_scope, dirty_orgs, ingest_observations, set_gap
from .usage_tasks import _PAGE_OR_PUBLISH_DELAYS, bounded_transaction, ensure_work, require_usage_role

_COOLDOWN = timedelta(seconds=120)
_CLASS = {
    ScanPurpose.INITIAL: 0, ScanPurpose.RECENT: 0, ScanPurpose.HEALTH: 1, ScanPurpose.HISTORY: 2,
}


def enroll_scope(provider, parent, now):
    provider_health = health.lock_provider(provider, now)
    pool_id = ProviderCapacityPool.objects.filter(provider=provider, parent_scope_id=parent).values_list("pk", flat=True).first()
    scope, created = UsageScope.objects.select_for_update().get_or_create(
        provider=provider, parent_scope_id=parent,
        defaults={"created_at": now, "updated_at": now, "pool_id": pool_id},
    )
    evaluation = health.scope_health(scope, now)
    if scope.pool_id is None and pool_id is not None:
        scope.pool_id = pool_id
        scope.updated_at = now
        scope.save(update_fields=("pool", "updated_at"))
        created = True
    if created:
        health.update_provider(provider_health, now)
    return provider_health, scope, evaluation


def floor_second(value):
    return value.replace(microsecond=0)


def floor_hour(value):
    return value.replace(minute=0, second=0, microsecond=0)


def profile_for(provider):
    return UsageProfile.DG_LISTEN_V1 if provider == "deepgram" else UsageProfile.OA_COMPLETIONS_1H_V1


def schedule_scan(scope, purpose, start, end, now, epoch, *, requirements=()):
    if end <= start:
        return None
    probe = UsageScan.objects.filter(
        scope=scope, profile=profile_for(scope.provider), requested_start=start, requested_end=end,
    )
    scan = probe.filter(state=ScanState.PARTIAL).first()
    if scan is not None and scan.policy_epoch_id != epoch.pk:
        return None  # The old claim must fail under its own policy provenance.
    if scan is None:
        prior = probe if purpose == ScanPurpose.HISTORY else UsageScan.objects.filter(scope=scope, purpose=purpose)
        if prior.filter(state=ScanState.FAILED, replacement_not_before__gt=now).exists():
            return None
        scan = UsageScan.objects.create(
            scope=scope, purpose=purpose, profile=profile_for(scope.provider),
            requested_start=start, requested_end=end, generation=scope.next_scan_generation,
            policy_epoch=epoch, policy_digest=epoch.digest, started_at=now, created_at=now, updated_at=now,
        )
        scope.next_scan_generation += 1
        scope.updated_at = now
        scope.save(update_fields=("next_scan_generation", "updated_at"))
        UsagePageClaim.objects.create(scan=scan, ordinal=0, created_at=now, updated_at=now)
    for kind, org_id, mapping, lower, upper in requirements:
        if start <= lower < upper <= end:
            UsageScanRequirement.objects.get_or_create(
                scan=scan, org_id=org_id, mapping=mapping, kind=kind, required_start=lower, required_end=upper,
                defaults={"created_at": now},
            )
    ensure_work("SCAN", str(scan.pk), now, scope=scope, scan=scan)
    return scan


def _unresolved_history_day(scope, retained_start):
    open_gap = UsageCoverageGap.objects.filter(record_id=OuterRef("pk"), state="OPEN")
    candidates = ProviderUsageRecord.objects.filter(scope=scope, event_at__lt=retained_start).filter(
        Q(issue__isnull=False)
        | Q(attribution__in=(Attribution.UNATTRIBUTED, Attribution.DISCREPANCY))
        | Q(current_version__completion=DGCompletion.COMPLETION_UNKNOWN)
        | Exists(open_gap)
    ).order_by("event_at", "pk")
    timestamps = candidates.values_list("event_at", flat=True)
    after = scope.history_recovery_after
    selected = timestamps.filter(event_at__gte=after).first() if after is not None else None
    if selected is None:
        selected = timestamps.first()
    return None if selected is None else selected.replace(hour=0, minute=0, second=0, microsecond=0)


def _advance_history(scope, start, end):
    fields = []
    if scope.history_next_start == start:
        scope.history_next_start = end
        fields.append("history_next_start")
    if scope.history_recovery_pending == start:
        scope.history_recovery_after = end
        scope.history_recovery_pending = None
        fields.extend(("history_recovery_after", "history_recovery_pending"))
    if fields:
        scope.save(update_fields=fields)


def _history_opportunity(scope, epoch, retained_start, aligned_end, now, *, recovery):
    day = timedelta(days=1)
    if recovery:
        lower = scope.history_recovery_pending
        if lower is None:
            lower = _unresolved_history_day(scope, retained_start)
            if lower is None:
                return False
            scope.history_recovery_pending = lower
            scope.save(update_fields=("history_recovery_pending",))
    else:
        lower = scope.history_next_start
        if lower is None or lower + day > aligned_end:
            lower = retained_start
            scope.history_next_start = lower
            scope.save(update_fields=("history_next_start",))
    upper = lower + day
    if UsageCoverageGap.objects.filter(
        scope=scope, start=lower, end=upper, reason=Code.HISTORY_UNAVAILABLE, state="OPEN",
    ).exists():
        _advance_history(scope, lower, upper)
        return True
    return schedule_scan(
        scope, ScanPurpose.HISTORY, lower, upper, now, epoch,
        requirements=(("HISTORY", None, None, lower, upper),),
    ) is not None


def schedule_history(scope, epoch, aligned_end, now):
    # Both windows use the existing HISTORY lane/class. Reuse pending work,
    # and alternate opportunities even when the older day remains unresolved.
    retained_start = (now - RETENTION_AGE).replace(hour=0, minute=0, second=0, microsecond=0)
    for recovery in (scope.history_recovery_turn, not scope.history_recovery_turn):
        if _history_opportunity(scope, epoch, retained_start, aligned_end, now, recovery=recovery):
            if scope.history_recovery_turn == recovery:
                scope.history_recovery_turn = not recovery
                scope.save(update_fields=("history_recovery_turn",))
            return


def _matching_policy(scope, scan):
    epoch, local = health.producer_policy(scope)
    if epoch.pk != scan.policy_epoch_id or epoch.digest != scan.policy_digest:
        raise UsageRejected(Code.POLICY_MISMATCH)
    return local


def _scope_orgs(scope, scan):
    if scope.provider != "deepgram":
        return ()
    orgs = set(scan.usagescanrequirement_set.exclude(org=None).values_list("org_id", flat=True))
    orgs.update(ProviderCredential.objects.filter(
        provider="deepgram", parent_scope_id=scope.parent_scope_id, state="ACTIVE",
    ).values_list("org_id", flat=True))
    return orgs


def _finish_failed(provider, scope, evaluation, scan, code, now):
    scan.state, scan.failure_code = ScanState.FAILED, code
    scan.finished_at = scan.updated_at = now
    scan.replacement_not_before = now + _COOLDOWN
    scan.save(update_fields=("state", "failure_code", "finished_at", "updated_at", "replacement_not_before"))
    set_gap(scope, code, now, start=scan.requested_start, end=scan.requested_end, scan=scan)
    health.operational_audit(
        "usage.scan_failed", "UsageScan", scan.pk, request_id=scan.pk, reason=code,
        after={"scope_id": scope.pk, "generation": scan.generation},
    )
    if scan.page_ordinal > 0 and scope.provider == "deepgram":
        dirty_orgs(scan.usagescanrequirement_set.exclude(org=None).values_list("org_id", flat=True), now)
    if code in (Code.CONFIG_UNAVAILABLE, Code.SCOPE_MISSING, Code.POLICY_MISMATCH):
        health.producer_failure(provider, evaluation, code, now)


def _finish_failure(provider, scope, evaluation, scan, page, code, now):
    page.last_error = code
    page.first_failure_at = page.first_failure_at or now
    page.lease_id = page.lease_until = page.lane_fence = None
    page.updated_at = now
    scope.lane_lease_id = scope.lane_lease_until = scope.lane_scan_id = scope.lane_page_ordinal = None
    scope.save(update_fields=("lane_lease_id", "lane_lease_until", "lane_scan", "lane_page_ordinal"))
    if page.attempts >= 3:
        page.state, page.retry_at = "FAILED", None
        page.save()
        _finish_failed(provider, scope, evaluation, scan, code, now)
    else:
        page.state = "PENDING"
        page.retry_at = max(now, page.first_failure_at + _PAGE_OR_PUBLISH_DELAYS[page.attempts])
        page.save()
    if code == Code.IDENTITY_CONFLICT and (
        evaluation.window_start is None or scan.requested_end > evaluation.window_start
    ):
        health.invalidate(provider, evaluation, scan.generation, scan.requested_end, now)
        set_gap(scope, code, now, start=scan.requested_start, end=scan.requested_end, scan=scan)


def _next_page(scope, now):
    rows = UsageScan.objects.filter(
        Q(usagepageclaim__retry_at__isnull=True) | Q(usagepageclaim__retry_at__lte=now),
        scope=scope, state=ScanState.PARTIAL, usagepageclaim__state="PENDING",
        usagepageclaim__ordinal=F("page_ordinal"), usagework__kind="SCAN",
        usagework__state__in=("RUNNING", "PENDING"), usagework__due_at__lte=now,
    )
    classes = ((ScanPurpose.INITIAL, ScanPurpose.RECENT), (ScanPurpose.HEALTH,), (ScanPurpose.HISTORY,))
    for offset in range(3):
        group = (scope.scheduling_turn + offset) % 3
        selected = rows.filter(purpose__in=classes[group]).order_by(
            F("last_served_at").asc(nulls_first=True), "created_at", "pk",
        ).first()
        if selected is not None:
            return selected
    return None


def _claim_page(work, *, clock, monotonic_ns, deadline):
    hint = UsageScope.objects.values_list("provider", flat=True).get(pk=work.scope_id)
    with bounded_transaction():
        now = clock()
        provider = health.lock_provider(hint, now)
        scope = health.lock_scope(hint, work.scope_id)
        evaluation = health.scope_health(scope, now)
        now = clock()
        if scope.lane_lease_until is not None:
            if scope.lane_lease_until > now:
                return None
            abandoned = UsageScan.objects.select_for_update().get(pk=scope.lane_scan_id)
            page = UsagePageClaim.objects.select_for_update().get(scan=abandoned, ordinal=scope.lane_page_ordinal)
            _finish_failure(provider, scope, evaluation, abandoned, page, Code.TRANSPORT_TIMEOUT, now)
        if deadline - monotonic_ns() < 15_000_000_000:
            return None
        scan = _next_page(scope, now)
        if scan is None or scan.pk != work.scan_id:
            return None
        scan = UsageScan.objects.select_for_update().get(pk=scan.pk)
        page = UsagePageClaim.objects.select_for_update().get(scan=scan, state="PENDING", ordinal=scan.page_ordinal)
        if not UsageWork.objects.filter(
            pk=work.pk, execution_generation=work.execution_generation, state="RUNNING",
            lease_id=work.lease_id, lease_until__gt=now,
        ).exists():
            return None
        try:
            _matching_policy(scope, scan)
        except UsageRejected as error:
            _finish_failed(provider, scope, evaluation, scan, error.code, now)
            return None
        now = clock()
        if deadline - monotonic_ns() < 15_000_000_000:
            return None
        scope.lane_fence += 1
        scope.lane_scan_id, scope.lane_page_ordinal = scan.pk, page.ordinal
        scope.lane_lease_id, scope.lane_lease_until = uuid4(), now + timedelta(seconds=30)
        scope.scheduling_turn = (_CLASS[scan.purpose] + 1) % 3
        scope.last_served_at = scope.updated_at = now
        scope.save()
        scan.last_served_at = scan.updated_at = now
        scan.save(update_fields=("last_served_at", "updated_at"))
        page.state = "READING"
        page.lease_id, page.lease_until, page.lane_fence = scope.lane_lease_id, scope.lane_lease_until, scope.lane_fence
        page.attempts += 1
        page.retry_at = None
        page.dispatched_at = page.updated_at = now
        page.save()
        return UsageClaim(
            page.pk, page.lease_id, scope.lane_fence, scan.generation, work.pk, work.execution_generation,
        ), ProviderScope(scope.provider, scope.parent_scope_id), UTCInterval(scan.requested_start, scan.requested_end), page.requested_cursor


def _apply_failure(work, claim, code, clock):
    provider_name = UsageScope.objects.values_list("provider", flat=True).get(pk=work.scope_id)
    with bounded_transaction():
        now = clock()
        provider = health.lock_provider(provider_name, now)
        scope = health.lock_scope(provider_name, work.scope_id)
        evaluation = health.scope_health(scope, now)
        scan = UsageScan.objects.select_for_update().get(pk=work.scan_id)
        page = UsagePageClaim.objects.select_for_update().get(scan=scan, pk=claim.page_id)
        now = clock()
        if (
            scan.state != ScanState.PARTIAL or scope.lane_lease_id != claim.lease_id
            or scope.lane_fence != claim.lane_fence or page.state != "READING"
            or page.lease_id != claim.lease_id or page.lease_until <= now
            or not UsageWork.objects.filter(
                pk=work.pk, state="RUNNING", execution_generation=claim.work_generation, lease_until__gt=now,
            ).exists()
        ):
            return
        _finish_failure(provider, scope, evaluation, scan, page, code, now)


def _terminal_chain(scan):
    # One ordered window verifies the whole persisted chain without materializing
    # an unbounded cursor list in the task process.
    sql = """
        SELECT COUNT(*), SUM(CASE
               WHEN state <> 'APPLIED' OR ordinal <> position - 1
                 OR (ordinal = 0 AND requested_cursor IS NOT NULL)
                 OR (ordinal > 0 AND (prior_cursor IS NULL OR requested_cursor <> prior_cursor
                                      OR requested_cursor IS NULL))
                 OR (ordinal = %s AND NOT terminal) OR (ordinal <> %s AND terminal)
               THEN 1 ELSE 0 END)
        FROM (SELECT state, ordinal, terminal, requested_cursor,
                     ROW_NUMBER() OVER (ORDER BY ordinal) AS position,
                     LAG(next_cursor) OVER (ORDER BY ordinal) AS prior_cursor
                FROM selahcue_usage_usagepageclaim WHERE scan_id = %s) AS chain
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [scan.page_ordinal - 1, scan.page_ordinal - 1,
                            scan.pk.hex if connection.vendor == "sqlite" else scan.pk])
        count, invalid = cursor.fetchone()
    return count == scan.page_ordinal and count > 0 and invalid == 0


def finish_scan(scan_id, coverage: ObservedCoverage) -> None:
    require_usage_role()
    hint = UsageScan.objects.filter(pk=scan_id).values_list("scope_id", "scope__provider").first()
    if hint is None:
        raise UsageRejected(Code.CLAIM_STALE)
    with bounded_transaction():
        now = timezone.now()
        provider = health.lock_provider(hint[1], now)
        scope = health.lock_scope(hint[1], hint[0])
        evaluation = health.scope_health(scope, now)
        scan = UsageScan.objects.select_for_update().get(pk=scan_id)
        now = timezone.now()
        if (
            coverage.scan_id != scan.pk or coverage.scope != ProviderScope(scope.provider, scope.parent_scope_id)
            or coverage.interval != UTCInterval(scan.requested_start, scan.requested_end)
            or coverage.scan_started_at != scan.started_at or coverage.terminal_page_seen is not True
            or coverage.scan_finished_at.utcoffset() != timedelta(0)
            or not scan.started_at <= coverage.scan_finished_at <= now
        ):
            raise UsageRejected(Code.CLAIM_STALE)
        if scan.state == ScanState.COMPLETE:
            return
        if (
            scan.state != ScanState.PARTIAL or scope.lane_scan_id == scan.pk or scan.next_cursor is not None
            or not _terminal_chain(scan)
            or not UsagePageClaim.objects.filter(
                scan=scan, ordinal=scan.page_ordinal - 1, completed_at__lte=coverage.scan_finished_at,
            ).exists()
        ):
            raise UsageRejected(Code.CLAIM_STALE)
        try:
            policy = _matching_policy(scope, scan)
        except UsageRejected as error:
            _finish_failed(provider, scope, evaluation, scan, error.code, now)
            return
        scan.finished_at = coverage.scan_finished_at
        scan.updated_at = now
        scan.state, scan.terminal_page_seen = ScanState.COMPLETE, True
        scan.save(update_fields=("finished_at", "updated_at", "state", "terminal_page_seen"))
        UsageObservedInterval.objects.create(
            scan=scan, scope=scope, start=scan.requested_start, end=scan.requested_end,
            scan_started_at=scan.started_at, scan_finished_at=scan.finished_at, profile=scan.profile, created_at=now,
        )
        ready = bump_scope(scope, now)
        if ready is not None and (
            ready.latest_complete_scan_id is None
            or (
                ready.latest_complete_scan.generation <= scan.generation
                and ready.observed_through <= scan.requested_end
            )
        ):
            ready.latest_complete_scan = scan
            ready.scan_started_at, ready.scan_finished_at = scan.started_at, scan.finished_at
            ready.observed_through = scan.requested_end
            ready.valid_until = scan.started_at + health.FRESHNESS
            ready.save()
        health.publish_evaluation(provider, scope, evaluation, scan, policy.unattributed_usage_threshold, now)
        UsageCoverageGap.objects.filter(
            scope=scope, record=None, state="OPEN", start__gte=scan.requested_start, end__lte=scan.requested_end,
            last_scan__generation__lt=scan.generation,
        ).update(state="RESOLVED", resolved_at=now, updated_at=now)
        if scan.usagescanrequirement_set.filter(kind="HISTORY").exists():
            _advance_history(scope, scan.requested_start, scan.requested_end)
        dirty_orgs(_scope_orgs(scope, scan), now)


def run_scan(work, *, clock, monotonic_ns):
    deadline = monotonic_ns() + 120_000_000_000
    for _ in range(11):
        # Also checks immediately after the tenth read to recover applied terminal
        # metadata without spending a new provider attempt.
        scan = UsageScan.objects.select_related("scope").get(pk=work.scan_id)
        if scan.state != ScanState.PARTIAL:
            return scan.state, None, scan.failure_code
        if UsagePageClaim.objects.filter(scan=scan, ordinal=scan.page_ordinal - 1, state="APPLIED", terminal=True).exists():
            finish_scan(
                scan.pk, ObservedCoverage(scan.pk, ProviderScope(scan.scope.provider, scan.scope.parent_scope_id),
                                          UTCInterval(scan.requested_start, scan.requested_end), scan.started_at, clock(), True),
            )
            scan.refresh_from_db()
            return scan.state, None, scan.failure_code
        if _ == 10:
            break
        authorized = _claim_page(work, clock=clock, monotonic_ns=monotonic_ns, deadline=deadline)
        if authorized is None:
            break
        claim, scope, interval, cursor = authorized
        reader = deepgram_usage if scope.provider == "deepgram" else openai_usage
        try:
            page = reader.read_usage_page(scope, interval, cursor)
            ingest_observations(page, work.scan_id, claim=claim)
        except UsageRejected as error:
            _apply_failure(work, claim, error.code, clock)
            break
    scan = UsageScan.objects.get(pk=work.scan_id)
    if scan.state != ScanState.PARTIAL:
        return scan.state, None, scan.failure_code
    retry_at = UsagePageClaim.objects.filter(scan=scan, ordinal=scan.page_ordinal).values_list("retry_at", flat=True).first()
    return "PENDING", retry_at or clock() + timedelta(seconds=1), None
