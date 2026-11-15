"""Apply current provider facts to frozen STT accounting weeks."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING

from django.db import DatabaseError, connection
from django.db.models import Case, DecimalField, F, OuterRef, Q, Subquery, Sum, Value, When
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.catalogue.org_plans import effective_plan
from selahcue_api.apps.providers.models import ProviderCredential
from selahcue_api.graphql.context import ActorContext, ActorKind

from . import health
from .contracts import ReservationState as Reservation
from .models import (
    ProviderUsageRecord, SttOrgCoverage, SttOrgReadiness, SttOrgReadinessScope, SttScopeReadiness,
    UsageCoverageGap, UsageObservedInterval, UsageOrgState, UsageReconcileAudit, UsageReservation,
    UsageScanRequirement, UsageScope, UsageWeek, UsageWeekProjection,
)
from .observation_contracts import (
    Attribution, DGCompletion, ObservationIssue, ReconcileResult, UsageFailureCode as Code,
    UsageHealthState, UsageRejected,
)
from .observations import RETENTION_AGE, bump_scope, set_gap
from .usage_tasks import bounded_transaction, require_usage_role
from .weeks import WEEK, local_week, utc_instant

_MAX_PROJECTIONS = 16
_MAX_BIGINT = 2**63 - 1
_ACTOR = ActorContext(kind=ActorKind.SERVICE, actor_id="usage-reconciliation")


@dataclass(frozen=True)
class _Fragment:
    observation: UsageObservedInterval
    start: datetime
    end: datetime


def settlement_floor(reservation):
    buffer = timedelta(seconds=900)
    minted = reservation.last_minted_at
    if minted is None:
        return reservation.authorized_until + buffer
    ttl = timedelta(seconds=30)
    return max(reservation.authorized_until + ttl + buffer, minted + ttl + timedelta(seconds=300) + buffer)


def _geometry(weeks, org_zone, target, now):
    previous = next((week for week in reversed(weeks) if week.ends_at <= target), None)
    successor = next((week for week in weeks if week.starts_at > target), None)
    if previous is None:
        bounds = local_week(org_zone, target)
        if not bounds.start <= now < bounds.end:
            return None
    else:
        bounds = local_week(
            org_zone, previous.ends_at, previous=(previous.week_start_local, previous.ends_at),
        )
        if bounds.start != previous.ends_at or bounds.monday != previous.week_start_local + WEEK:
            return None
    if successor is not None and (bounds.end > successor.starts_at or bounds.monday >= successor.week_start_local):
        return None
    return bounds, previous, successor


def _project(org, weeks, plan, target, now):
    selection = _geometry(weeks, org.timezone, target, now)
    if selection is None:
        return None
    bounds, predecessor, successor = selection
    row = UsageWeek.objects.create(
        org=org, week_start_local=bounds.monday, tz_name=bounds.tz_name,
        starts_at=bounds.start, ends_at=bounds.end, admissions_start_at=bounds.admissions_start_at,
        counted_from=bounds.start, high_water_rank=plan.rank, opening_stt_seconds_limit=plan.stt_seconds_limit,
        opening_notes_limit=plan.notes_limit, high_water_stt_seconds_limit=plan.stt_seconds_limit,
        high_water_notes_limit=plan.notes_limit, stt_seconds_carried_debt=0, notes_carried_debt=0,
    )
    UsageWeekProjection.objects.create(
        week=row, reconciled_at=now, created_at=now, selected_plan_id=plan.plan_id, selected_rank=plan.rank,
        catalogue_revision=plan.catalogue_revision, selected_timezone=bounds.tz_name,
        opening_stt_seconds_limit=plan.stt_seconds_limit, opening_notes_limit=plan.notes_limit,
        predecessor_week=predecessor, successor_week=successor,
    )
    weeks.append(row)
    weeks.sort(key=lambda item: item.starts_at)
    return row


def _place(records, weeks, org, plan, scopes, now):
    eligible = records.exclude(issue=ObservationIssue.ANCIENT_FACT).filter(event_at__lte=now)
    affected_scopes, affected_weeks = set(), set()
    projected = 0
    while True:
        accounted_week = UsageWeek.objects.filter(
            pk__in=[week.pk for week in weeks],
            starts_at__lte=OuterRef("event_at"), ends_at__gt=OuterRef("event_at"),
        ).values("pk")[:1]
        placement = Subquery(accounted_week)
        changed = eligible.alias(accounting_week=placement).filter(accounting_week__isnull=False).exclude(
            placed_week_id=F("accounting_week"),
        )
        affected = list(changed.values_list("scope_id", "placed_week_id").distinct())
        if affected:
            affected_scopes.update(scope for scope, _ in affected)
            affected_weeks.update(week for _, week in affected if week is not None)
            changed.update(
                placed_week_id=placement, updated_at=now,
                issue=Case(When(issue=ObservationIssue.PLACEMENT_GAP, then=Value(None)), default=F("issue")),
            )
        unresolved = eligible.filter(placed_week=None).order_by("event_at", "pk").first()
        current = next((week for week in weeks if week.starts_at <= now < week.ends_at), None)
        if unresolved is None and current is not None:
            UsageCoverageGap.objects.filter(
                record_id__in=eligible.filter(placed_week__isnull=False).values("pk"),
                reason=Code.PLACEMENT_GAP, state="OPEN",
            ).update(state="RESOLVED", resolved_at=now, updated_at=now)
            return None, current, affected_scopes, affected_weeks
        if projected >= _MAX_PROJECTIONS:
            return Code.REVISION_CONFLICT, current, affected_scopes, affected_weeks
        target = unresolved.event_at if unresolved is not None else now
        if _project(org, weeks, plan, target, now) is None:
            if unresolved is not None:
                scope = scopes[unresolved.scope_id]
                set_gap(scope, Code.PLACEMENT_GAP, now, record=unresolved, org_id=org.pk)
                unresolved.issue, unresolved.updated_at = ObservationIssue.PLACEMENT_GAP, now
                unresolved.save(update_fields=("issue", "updated_at"))
                affected_scopes.add(scope.pk)
            return Code.PLACEMENT_GAP, current, affected_scopes, affected_weeks
        projected += 1


def _weekly_totals(records):
    usable = records.filter(
        attribution=Attribution.EXACT_KEY, current_version__completion=DGCompletion.COMPLETE,
        current_version__duration_seconds__isnull=False, placed_week__isnull=False,
        event_at__gte=F("placed_week__counted_from"), event_at__lt=F("placed_week__ends_at"),
    ).exclude(issue__in=(ObservationIssue.ANCIENT_FACT, ObservationIssue.IDENTITY_CONFLICT, ObservationIssue.PLACEMENT_GAP))
    if connection.vendor == "sqlite":
        scaled = {}
        for key, amount in usable.values_list("placed_week_id", "current_version__duration_seconds"):
            scaled[key] = scaled.get(key, 0) + health.to_attoseconds(amount)
        return {key: -(-amount // 10**18) for key, amount in scaled.items()}
    aggregate = usable.values("placed_week_id").annotate(
        amount=Sum("current_version__duration_seconds", output_field=DecimalField(max_digits=58, decimal_places=18)),
    )
    totals = {}
    for row in aggregate:
        total = row["amount"].to_integral_value(rounding=ROUND_CEILING)
        if total > _MAX_BIGINT:
            raise UsageRejected(Code.ARITHMETIC_OVERFLOW)
        totals[row["placed_week_id"]] = int(total)
    return totals


def _audit(org, revision, action, week, successor, amount, now):
    subject = str(week.pk)
    row, created = UsageReconcileAudit.objects.get_or_create(
        org=org, dirty_revision=revision, action=action, subject=subject,
        defaults={"source_week": week, "successor_week": successor, "units": amount, "event_at": now, "created_at": now},
    )
    if created:
        event = record_audit_event(
            _ACTOR, action="usage." + action.lower(), target_type="UsageWeek", target_id=subject,
            request_id=str(row.pk), after={"org_id": org.pk, "revision": revision, "units": amount},
            source_surface="provider_usage",
        )
        row.audit_event = event
        row.save(update_fields=("audit_event",))


def _publish_totals(org, revision, weeks, current, totals, affected, now):
    corrected = set()
    for week in weeks:
        if week.pk not in affected:
            continue
        total = totals.get(week.pk, 0)
        if week.stt_seconds_settled == total:
            continue
        previous = max(0, week.stt_seconds_settled - week.high_water_stt_seconds_limit)
        overrun = max(0, total - week.high_water_stt_seconds_limit)
        if overrun and overrun != previous:
            successor = current if current is not None and current.starts_at == week.ends_at else None
            _audit(org, revision, "OVERRUN_RECORDED", week, successor, overrun, now)
            written_off = overrun if successor is None and week.ends_at <= now else (
                max(0, overrun - successor.opening_stt_seconds_limit) if successor else 0
            )
            if written_off:
                _audit(org, revision, "OVERRUN_WRITTEN_OFF", week, successor, written_off, now)
        week.stt_seconds_settled = total
        week.save(update_fields=("stt_seconds_settled",))
        corrected.add(week.pk)
    if current is not None:
        predecessor = next((week for week in weeks if week.ends_at == current.starts_at), None)
        if predecessor is not None:
            debt = min(
                current.opening_stt_seconds_limit,
                max(0, predecessor.stt_seconds_settled - predecessor.high_water_stt_seconds_limit),
            )
            if current.stt_seconds_carried_debt != debt:
                current.stt_seconds_carried_debt = debt
                current.save(update_fields=("stt_seconds_carried_debt",))
                corrected.add(current.pk)
    return tuple(week.pk for week in weeks if week.pk in corrected)


def _relevant_scopes(mapping, reservations, records, scopes, state):
    parents = {mapping.parent_scope_id} if mapping is not None else set()
    mapping_ids = [item.provider_mapping_id for item in reservations if item.provider_mapping_id is not None]
    parents.update(ProviderCredential.objects.filter(pk__in=mapping_ids).values_list("parent_scope_id", flat=True))
    dependent = records.filter(
        Q(issue__isnull=False) | Q(current_version__completion=DGCompletion.COMPLETION_UNKNOWN)
        | Q(placed_week__isnull=True) | Q(updated_at__gte=state.last_completed_at or state.created_at),
    )
    scope_ids = set(dependent.values_list("scope_id", flat=True).distinct())
    required = {scope.pk: scope for scope in scopes.values()
                if scope.parent_scope_id in parents or scope.pk in scope_ids}
    return required if parents <= {scope.parent_scope_id for scope in required.values()} else None


def _fragments(scope, mapping, now, lower, upper=None):
    if upper is not None and upper <= lower:
        return ()
    live_epoch = scope.pool.current_epoch_id if scope.pool_id else None
    if live_epoch is None:
        return None
    observed = UsageObservedInterval.objects.filter(
        scope=scope, profile="DG_LISTEN_V1", scan_started_at__gte=mapping.activated_at,
        scan_started_at__gt=now - health.FRESHNESS, scan_started_at__lte=now,
        scan__policy_epoch_id=live_epoch, end__gt=lower,
    ).order_by("start", "-end", "-scan_started_at", "pk")
    intervals = list(observed)
    end = upper if upper is not None else max((row.end for row in intervals), default=lower)
    fragments = []
    point = lower
    while point < end:
        usable = [row for row in intervals if row.start <= point < row.end]
        if not usable:
            return None
        chosen = max(usable, key=lambda row: (row.end, row.scan_started_at, row.pk))
        part_end = min(chosen.end, end)
        fragments.append(_Fragment(chosen, point, part_end))
        point = part_end
    return tuple(fragments)


def _pending_requirements(org_id, mapping_id, scope, fragments):
    if not fragments:
        return True
    lower, upper = min(part.start for part in fragments), max(part.end for part in fragments)
    requirements = UsageScanRequirement.objects.filter(
        org_id=org_id, scan__scope=scope, kind__in=("INITIAL", "CURRENT", "OPEN"),
        scan__state__in=("PARTIAL", "FAILED"), scan__page_ordinal__gt=0,
        required_start__lt=upper, required_end__gt=lower,
    ).filter(Q(mapping=mapping_id) | Q(mapping__isnull=True))
    for candidate in requirements.select_related("scan"):
        if not UsageObservedInterval.objects.filter(
            scope=scope, start__lte=candidate.required_start, end__gte=candidate.required_end,
            scan__generation__gt=candidate.scan.generation,
        ).exists():
            return True
    return False


def _open_coverage(scope, mapping, reservations, now):
    extra = []
    for row in reservations:
        if row.provider_mapping_id is None:
            continue
        if row.provider_mapping.parent_scope_id != scope.parent_scope_id:
            continue
        floor = settlement_floor(row)
        if row.state != Reservation.ISSUED or floor > now:
            continue
        fragments = _fragments(scope, mapping, now, row.authorized_from, floor)
        if fragments is None:
            return None
        extra.extend(fragments)
    return extra


def _publish(org, mapping, state, provider_health, required, current, reservations, now):
    if not required or provider_health.status != UsageHealthState.CURRENT:
        return None
    vector = []
    for scope in sorted(required.values(), key=lambda value: value.parent_scope_id):
        base = _fragments(scope, mapping, now, current.counted_from)
        extra = _open_coverage(scope, mapping, reservations, now)
        if not base or extra is None:
            return None
        fragments = (*base, *extra)
        if _pending_requirements(org.pk, mapping.pk, scope, fragments):
            return None
        ready = SttScopeReadiness.objects.filter(scope=scope).first()
        if ready is None:
            return None
        expiry = min(part.observation.scan_started_at + health.FRESHNESS for part in fragments)
        through = max(part.end for part in fragments)
        vector.append((ready, expiry, through, fragments))
    valid = min(provider_health.valid_until, *(row[1] for row in vector))
    through = min(row[2] for row in vector)
    if valid <= now or through > now:
        return None
    existing = SttOrgReadiness.objects.filter(org=org).first()
    if (
        existing is not None and existing.mapping == mapping.pk
        and existing.org_dirty_revision == state.dirty_revision
        and existing.health_revision == provider_health.revision
        and existing.observed_through == through and existing.valid_until == valid
        and set(existing.sttorgreadinessscope_set.values_list("scope_id", "scope_revision"))
        == {(row[0].pk, row[0].revision) for row in vector}
    ):
        return through
    publication, created = SttOrgReadiness.objects.update_or_create(
        org=org,
        defaults={
            "mapping": mapping.pk, "published_at": now, "observed_through": through, "valid_until": valid,
            "placement_gap": False, "health_id": "deepgram", "health_revision": provider_health.revision,
            "org_dirty_revision": state.dirty_revision, "updated_at": now,
            "created_at": existing.created_at if existing else now,
            "publication_revision": (existing.publication_revision + 1) if existing else 1,
        },
    )
    if not created:
        SttOrgCoverage.objects.filter(publication=publication).delete()
        SttOrgReadinessScope.objects.filter(publication=publication).delete()
    details = set()
    for ready, expiry, covered, fragments in vector:
        SttOrgReadinessScope.objects.create(
            publication=publication, scope=ready, scope_revision=ready.revision,
            coverage_valid_until=expiry, observed_through=covered, created_at=now,
        )
        details.update((part.observation.pk, part.start, part.end) for part in fragments)
    SttOrgCoverage.objects.bulk_create([
        SttOrgCoverage(
            publication=publication, observed_interval_id=pk, required_start=start, required_end=end, created_at=now,
        )
        for pk, start, end in sorted(details)
    ])
    return through


def _reconcile(org_id, at, clock):
    with bounded_transaction():
        org = CustomerOrg.objects.select_for_update(no_key=True).filter(pk=org_id).first()
        if org is None:
            return ReconcileResult(org_id, (), (), None, Code.SCOPE_MISSING)
        weeks = list(UsageWeek.objects.select_for_update().filter(
            org=org, ends_at__gte=at - RETENTION_AGE - WEEK,
        ).order_by("starts_at", "pk"))
        reservations = list(UsageReservation.objects.select_for_update().filter(
            org=org, meter="stt", state__in=(Reservation.RESERVED, Reservation.ISSUED),
        ).order_by("pk"))
        health.lock_provider("deepgram", at)
        scopes = {
            scope.pk: scope for scope in UsageScope.objects.select_for_update().filter(
                provider="deepgram",
            ).order_by("provider", "parent_scope_id")
        }
        # Observation versions and membership cannot change while the same
        # provider lock is held. Read them only after it, never across snapshots
        # on either side of that authority boundary.
        state, _ = UsageOrgState.objects.select_for_update().get_or_create(
            org=org, defaults={"created_at": at, "updated_at": at, "next_due_at": at},
        )
        now = utc_instant(clock())
        if now - at > WEEK or at > now:
            raise UsageRejected(Code.REVISION_CONFLICT)
        active = ProviderCredential.objects.filter(org=org, provider="deepgram", state="ACTIVE").first()
        plan = effective_plan(org, now)
        records = ProviderUsageRecord.objects.filter(mapping__org=org, provider="deepgram")
        totals_records = records.filter(event_at__gte=at - RETENTION_AGE - WEEK)
        block, current, affected, prior_placements = _place(totals_records, weeks, org, plan, scopes, now)
        for scope_id in sorted(affected):
            bump_scope(scopes[scope_id], now)
        if block == Code.REVISION_CONFLICT:
            return ReconcileResult(org_id, (), (), None, block)
        totals = _weekly_totals(totals_records)
        if any(total > _MAX_BIGINT for total in totals.values()):
            raise UsageRejected(Code.ARITHMETIC_OVERFLOW)
        affected_weeks = prior_placements | set(totals_records.exclude(placed_week_id=None).values_list(
            "placed_week_id", flat=True,
        ).distinct())
        corrected = _publish_totals(org, state.dirty_revision, weeks, current, totals, affected_weeks, now)
        blocked_gaps = UsageCoverageGap.objects.filter(org=org, state="OPEN")
        if block or blocked_gaps.filter(reason=Code.PLACEMENT_GAP).exists():
            return ReconcileResult(org_id, corrected, (), None, Code.PLACEMENT_GAP)
        if records.filter(issue__in=(ObservationIssue.IDENTITY_CONFLICT, ObservationIssue.METRIC_UNKNOWN)).exists():
            return ReconcileResult(org_id, corrected, (), None, Code.METRIC_UNKNOWN)
        required = _relevant_scopes(active, reservations, records, scopes, state)
        if required is None or current is None:
            return ReconcileResult(org_id, corrected, (), None, Code.SCOPE_MISSING)
        settled = []
        if not records.filter(current_version__completion=DGCompletion.COMPLETION_UNKNOWN).exists():
            by_parent = {scope.parent_scope_id: scope for scope in required.values()}
            for row in reservations:
                floor = settlement_floor(row)
                if row.state != Reservation.ISSUED or floor > now or row.provider_mapping_id is None:
                    continue
                scope = by_parent.get(row.provider_mapping.parent_scope_id)
                activation = active or row.provider_mapping
                if scope is not None and activation.activated_at is not None and _fragments(
                    scope, activation, now, row.authorized_from, floor,
                ):
                    row.state = Reservation.SETTLED
                    row.save(update_fields=("state",))
                    settled.append(row.pk)
        if active is None or active.activated_at is None:
            return ReconcileResult(org_id, corrected, tuple(settled), None, Code.SCOPE_MISSING)
        health_state = health.read_provider_usage_health("deepgram", now)
        through = _publish(org, active, state, health_state, required, current, reservations, now)
        if through is None:
            return ReconcileResult(org_id, corrected, tuple(settled), None, Code.REVISION_CONFLICT)
        state.applied_revision = state.dirty_revision
        state.last_completed_at = state.updated_at = now
        state.save(update_fields=("applied_revision", "last_completed_at", "updated_at"))
        return ReconcileResult(org_id, corrected, tuple(settled), through, None)


def reconcile_org(org_id: int, at: datetime, *, clock=timezone.now) -> ReconcileResult:
    require_usage_role()
    if type(org_id) is not int or org_id <= 0 or at.utcoffset() != timedelta(0):
        raise ValueError("Expected a valid org ID and UTC cutoff")
    for attempt in range(2):
        try:
            return _reconcile(org_id, at, clock)
        except UsageRejected as error:
            if error.code == Code.REVISION_CONFLICT and attempt == 0:
                at = utc_instant(clock())
                continue
            return ReconcileResult(org_id, (), (), None, error.code)
        except DatabaseError as error:
            sqlstate = getattr(error.__cause__, "sqlstate", None)
            if sqlstate not in {"40001", "40P01", "55P03", "57014"}:
                raise
            if attempt == 0 and sqlstate in {"40001", "40P01"}:
                at = utc_instant(clock())
                continue
            return ReconcileResult(org_id, (), (), None, Code.DATABASE_BUSY)
