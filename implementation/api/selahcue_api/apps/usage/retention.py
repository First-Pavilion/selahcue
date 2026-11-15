"""Bounded maintenance pruning that preserves unresolved facts and dependencies."""
from datetime import timedelta
import time

from django.db import IntegrityError
from django.db.models import F, Q
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg

from . import health
from .models import (
    ProviderUsageRecord, ProviderUsageVersion, UsageCoverageGap, UsageObservedInterval,
    UsageOutbox, UsagePageClaim, UsageReservation, UsageRetentionCursor, UsageScanRequirement, UsageWeek, UsageWork,
)
from .observation_contracts import Attribution, DGCompletion, RetentionBatchResult, RetentionKind
from .observations import RETENTION_AGE, bump_scope
from .usage_tasks import bounded_transaction, require_usage_role

DETAIL_AGE = timedelta(days=35)
_LIMIT = 100


def _terminal_versions(cutoff):
    return ProviderUsageVersion.objects.filter(
        first_receipt_at__lt=cutoff, record__issue__isnull=True,
        record__attribution__in=(Attribution.EXACT_KEY, Attribution.PROJECT_ONLY),
    ).exclude(record__current_version_id=F("pk")).exclude(completion=DGCompletion.COMPLETION_UNKNOWN)


def _candidates(kind, cutoff):
    if kind == RetentionKind.PAGE_DETAIL:
        return UsagePageClaim.objects.filter(
            created_at__lt=cutoff, scan__state__in=("COMPLETE", "FAILED"), state__in=("APPLIED", "FAILED"),
        ).filter(Q(first_receipt_at__lt=cutoff) | Q(first_receipt_at__isnull=True, updated_at__lt=cutoff))
    if kind == RetentionKind.SUPERSEDED_VERSION:
        return _terminal_versions(cutoff)
    if kind == RetentionKind.TERMINAL_SCAN_WORK:
        return UsageWork.objects.filter(state__in=("COMPLETE", "FAILED"), finished_at__lt=cutoff)
    if kind == RetentionKind.NORMALIZED_RECORD:
        return ProviderUsageRecord.objects.filter(
            retention_at__lt=cutoff, issue__isnull=True,
            attribution__in=(Attribution.EXACT_KEY, Attribution.PROJECT_ONLY),
        ).exclude(current_version__completion=DGCompletion.COMPLETION_UNKNOWN)
    if kind == RetentionKind.TERMINAL_RESERVATION:
        return UsageReservation.objects.filter(created_at__lt=cutoff, state__in=("SETTLED", "RELEASED"))
    return UsageWeek.objects.filter(ends_at__lt=cutoff)


def _references(instance, *, exceptions=()):
    # Every registered reverse relation is checked as a candidate dependency.
    # Looking at declared relations also works before the notes app exists.
    for relation in instance._meta.related_objects:
        model = relation.related_model
        if model in exceptions:
            continue
        if model._base_manager.filter(**{relation.field.attname: instance.pk}).exists():
            return True
    return False


def _delete_single(row):
    # Check CASCADE and SET_NULL relations as dependencies as well as PROTECT.
    # _raw_delete is deliberately a single physical-row delete. The DB FKs
    # detect any dependency that appeared between the check and deletion.
    return type(row).objects.filter(pk=row.pk)._raw_delete("default")


def _delete_page(page, budget):
    if budget == 0:
        return 0
    versions = ProviderUsageVersion.objects.filter(source_page=page)
    if versions.filter(record__issue__isnull=False).exists() or versions.filter(
        completion=DGCompletion.COMPLETION_UNKNOWN,
    ).exists():
        return 0
    versions.update(source_page=None)
    if _references(page):
        return 0
    return _delete_single(page)


def _delete_normalized(row, cutoff, budget, now):
    if budget < 2:
        return 0
    if row.placed_week_id is not None:
        week = row.placed_week
        if (
            week.ends_at >= cutoff or week.reservations.filter(state__in=("RESERVED", "ISSUED")).exists()
            or UsageWeek.objects.filter(
                org_id=week.org_id, starts_at=week.ends_at, ends_at__gt=now, stt_seconds_carried_debt__gt=0,
            ).exists()
        ):
            return 0
    if (
        row.current_version_id is None or row.issue is not None
        or row.attribution not in (Attribution.EXACT_KEY, Attribution.PROJECT_ONLY)
        or row.retention_at >= cutoff or _references(row, exceptions=(ProviderUsageVersion,))
        or row.current_version.completion == DGCompletion.COMPLETION_UNKNOWN
    ):
        return 0
    versions = list(ProviderUsageVersion.objects.filter(record=row).order_by("pk")[:budget])
    if not versions or len(versions) >= budget:
        return 0
    row.current_version = None
    row.save(update_fields=("current_version",))
    deleted = sum(_delete_single(version) for version in versions)
    deleted += _delete_single(row)
    bump_scope(row.scope, now)
    return deleted


def _scan_cleanup(work, cutoff, budget, now):
    deleted = 0
    # Outboxes are independent physical rows and may outlive an older work
    # cursor pass. Delete only already recognized terminal deliveries.
    deliveries = list(UsageOutbox.objects.filter(
        work=work, state__in=("ACKED", "FAILED", "CANCELLED"), updated_at__lt=cutoff,
    ).order_by("pk")[:budget])
    for item in deliveries:
        deleted += _delete_single(item)
    if deleted == budget or _references(work):
        return deleted
    scan = work.scan if work.scan_id else None
    if scan is None:
        return deleted + _delete_single(work)
    if scan.state not in ("COMPLETE", "FAILED") or scan.finished_at >= cutoff:
        return deleted
    if UsageCoverageGap.objects.filter(last_scan=scan, state="OPEN").exists():
        return deleted
    if _references(scan, exceptions=(ProviderUsageVersion, UsageObservedInterval, UsageScanRequirement, UsageWork)):
        return deleted
    if UsageWork.objects.filter(scan=scan).exclude(pk=work.pk).exists():
        return deleted + _delete_single(work)
    observed = UsageObservedInterval.objects.filter(scan=scan).first()
    if observed is not None and _references(observed):
        return deleted
    versions = ProviderUsageVersion.objects.filter(source_scan=scan)
    if versions.filter(record__issue__isnull=False).exists() or versions.filter(completion=DGCompletion.COMPLETION_UNKNOWN).exists():
        return deleted
    requirements = list(UsageScanRequirement.objects.filter(scan=scan).order_by("pk")[:budget - deleted])
    physical = 2 + int(observed is not None) + len(requirements)
    if deleted + physical > budget:
        # Expired requirements are eligible now. Keep the work anchor so
        # remaining bounded scan dependencies are revisited on the next pass.
        return deleted + sum(_delete_single(item) for item in requirements)
    deleted += sum(_delete_single(item) for item in requirements)
    if observed is not None:
        deleted += _delete_single(observed)
    versions.update(source_scan=None)
    deleted += _delete_single(work)
    return deleted + _delete_single(scan)



def _prune_candidate(kind, key, cutoff, budget, now):
    query = _candidates(kind, cutoff)
    hint = query.filter(pk=key).first()
    if hint is None:
        return 0
    with bounded_transaction():
        if kind == RetentionKind.NORMALIZED_RECORD:
            if hint.mapping_id is not None:
                CustomerOrg.objects.select_for_update(no_key=True).get(pk=hint.mapping.org_id)
            if hint.placed_week_id is not None:
                UsageWeek.objects.select_for_update().get(pk=hint.placed_week_id)
            health.lock_provider(hint.provider, now)
            health.lock_scope(hint.provider, hint.scope_id)
        elif kind in (RetentionKind.PAGE_DETAIL, RetentionKind.SUPERSEDED_VERSION) or (
            kind == RetentionKind.TERMINAL_SCAN_WORK and hint.scope_id is not None
        ):
            if kind == RetentionKind.PAGE_DETAIL:
                source = hint.scan.scope
            elif kind == RetentionKind.SUPERSEDED_VERSION:
                source = hint.source_scope
            else:
                source = hint.scope
            health.lock_provider(source.provider, now)
            health.lock_scope(source.provider, source.pk)
        elif kind in (RetentionKind.EXPIRED_WEEK, RetentionKind.TERMINAL_RESERVATION):
            CustomerOrg.objects.select_for_update(no_key=True).get(pk=hint.org_id)
            if kind == RetentionKind.TERMINAL_RESERVATION:
                UsageWeek.objects.select_for_update().get(pk=hint.week_id)

        row = query.select_for_update(of=('self',)).filter(pk=key).first()
        if row is None:
            return 0
        if kind == RetentionKind.NORMALIZED_RECORD:
            return _delete_normalized(row, cutoff, budget, now)
        if kind == RetentionKind.PAGE_DETAIL:
            return _delete_page(row, budget)
        if kind == RetentionKind.TERMINAL_SCAN_WORK:
            return _scan_cleanup(row, cutoff, budget, now)
        if _references(row):
            return 0
        if kind == RetentionKind.TERMINAL_RESERVATION and UsageCoverageGap.objects.filter(
            org_id=row.org_id, state="OPEN",
        ).exists():
            return 0
        if kind == RetentionKind.EXPIRED_WEEK:
            following = UsageWeek.objects.filter(org_id=row.org_id, starts_at=row.ends_at).first()
            if following is not None and following.ends_at > now and (
                following.stt_seconds_carried_debt or following.notes_carried_debt
            ):
                return 0
        return _delete_single(row)


def prune_usage_batch(kind: RetentionKind, *, clock=timezone.now) -> RetentionBatchResult:
    require_usage_role(maintenance=True)
    if type(kind) is not RetentionKind:
        raise ValueError("Expected a retention kind")
    deadline = time.monotonic() + 10
    now = clock()
    detail = kind in (RetentionKind.PAGE_DETAIL, RetentionKind.SUPERSEDED_VERSION, RetentionKind.TERMINAL_SCAN_WORK)
    uuid_cursor = kind in (RetentionKind.TERMINAL_SCAN_WORK, RetentionKind.TERMINAL_RESERVATION)
    scanned = deleted = deferred = 0
    next_key = None
    while scanned < _LIMIT and deleted < _LIMIT and time.monotonic() < deadline:
        with bounded_transaction():
            cursor, _ = UsageRetentionCursor.objects.select_for_update().get_or_create(
                kind=kind, defaults={
                    "cutoff_at": now - (DETAIL_AGE if detail else RETENTION_AGE),
                    "cycle_started_at": now, "created_at": now, "updated_at": now,
                },
            )
            cutoff = cursor.cutoff_at
            position = cursor.after_uuid if uuid_cursor else cursor.after_id
            candidates = _candidates(kind, cutoff)
            if position is not None:
                candidates = candidates.filter(pk__gt=position)
            next_key = candidates.order_by("pk").values_list("pk", flat=True).first()
            if next_key is None:
                cursor.after_id = cursor.after_uuid = None
                cursor.cutoff_at = now - (DETAIL_AGE if detail else RETENTION_AGE)
                cursor.cycle_started_at = now
            elif uuid_cursor:
                cursor.after_uuid = next_key
            else:
                cursor.after_id = next_key
            cursor.updated_at = now
            cursor.save()
        if next_key is None:
            return RetentionBatchResult(scanned, deleted, deferred, False)
        scanned += 1
        try:
            count = _prune_candidate(kind, next_key, cutoff, _LIMIT - deleted, now)
        except IntegrityError:
            count = 0
        deferred += count == 0
        deleted += count
    return RetentionBatchResult(scanned, deleted, deferred, True)
