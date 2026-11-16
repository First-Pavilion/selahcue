"""Private incremental planning for complete recent-scan requirements."""
from django.db.models import OuterRef, Q, Subquery

from selahcue_api.apps.providers.models import ProviderCapacityPool, ProviderCredential

from . import health
from .models import (
    UsagePageClaim, UsageRecentMember, UsageRecentPlan, UsageReservation, UsageScan, UsageScanRequirement, UsageWeek,
)
from .observation_contracts import ScanPurpose
from .reconciliation import settlement_floor
from .scans import floor_second, schedule_scan
from .usage_tasks import ensure_work
from .weeks import local_week


def _mapping_batch(plan, limit):
    cutoff = plan.cutoff
    rows = ProviderCredential.objects.filter(
        provider="deepgram", parent_scope_id=plan.scope.parent_scope_id, activated_at__lte=cutoff,
    ).filter(Q(terminal_at__isnull=True) | Q(terminal_at__gt=cutoff))
    if plan.mapping_after is not None:
        rows = rows.filter(pk__gt=plan.mapping_after)
    weeks = UsageWeek.objects.filter(org_id=OuterRef("org_id"))
    current = weeks.filter(starts_at__lte=cutoff, ends_at__gt=cutoff).order_by("-starts_at")
    previous = weeks.filter(ends_at__lte=cutoff).order_by("-starts_at")
    candidates = list(rows.annotate(
        counted=Subquery(current.values("counted_from")[:1]),
        prior_label=Subquery(previous.values("week_start_local")[:1]),
        prior_end=Subquery(previous.values("ends_at")[:1]),
    ).order_by("pk").values("pk", "org_id", "org__timezone", "counted", "prior_label", "prior_end")[:limit])
    found = []
    if any(row["counted"] is not None and row["counted"] > cutoff for row in candidates):
        plan.phase = "DISCARD"
        return [], len(candidates)
    for row in candidates:
        after = (row["prior_label"], row["prior_end"]) if row["prior_end"] else None
        start = row["counted"] or local_week(row["org__timezone"], cutoff, previous=after).start
        found.append(("CURRENT", row["org_id"], row["pk"], floor_second(start)))
    if candidates:
        plan.mapping_after = candidates[-1]["pk"]
    if len(candidates) < limit:
        plan.phase = "OPEN"
    return found, len(candidates)


def _open_batch(plan, limit):
    rows = UsageReservation.objects.filter(
        meter="stt", state="ISSUED", admitted_at__lte=plan.cutoff,
        provider_mapping__provider="deepgram", provider_mapping__parent_scope_id=plan.scope.parent_scope_id,
    )
    if plan.open_after is not None:
        rows = rows.filter(pk__gt=plan.open_after)
    candidates = list(rows.select_related("week").order_by("pk")[:limit])
    found = [
        ("OPEN", row.org_id, None, floor_second(min(row.week.counted_from, row.authorized_from)))
        for row in candidates if settlement_floor(row) <= plan.cutoff
    ]
    if candidates:
        plan.open_after = candidates[-1].pk
    if len(candidates) < limit:
        plan.phase = "TRANSFER"
    return found, len(candidates)


def _stage(plan, found, now):
    rows = [
        UsageRecentMember(plan=plan, kind=kind, org_id=org, mapping=mapping, required_start=start, created_at=now)
        for kind, org, mapping, start in found if start < plan.cutoff
    ]
    if rows:
        UsageRecentMember.objects.bulk_create(rows)
        plan.lowest_start = min(row.required_start for row in rows) if plan.lowest_start is None else min(
            plan.lowest_start, *(row.required_start for row in rows),
        )


def _transfer(plan, scope, epoch, now, limit):
    if plan.lowest_start is None:
        plan.delete()
        return 0
    scan = plan.scan
    if scan is None:
        scan = schedule_scan(scope, ScanPurpose.RECENT, plan.lowest_start, plan.cutoff, now, epoch, plan=plan)
        if scan is None:
            return 0
        plan.scan = scan
        plan.save(update_fields=("scan",))
    members = list(plan.usagerecentmember_set.order_by("pk")[:limit])
    names = {(row.kind, row.org_id, row.mapping, row.required_start) for row in members}
    UsageScanRequirement.objects.bulk_create([
        UsageScanRequirement(
            scan=scan, kind=kind, org_id=org, mapping=mapping, required_start=start,
            required_end=plan.cutoff, created_at=now,
        ) for kind, org, mapping, start in names
    ], ignore_conflicts=True)
    if members:
        plan.usagerecentmember_set.filter(pk__in=[row.pk for row in members]).delete()
    if plan.usagerecentmember_set.exists():
        return len(members)
    if UsageScan.objects.filter(
        scope=scope, profile=scan.profile, requested_start=scan.requested_start, requested_end=plan.cutoff,
        state="PARTIAL", planning=False,
    ).exists():
        return len(members)
    health_start = plan.cutoff - health.HEALTH_WINDOW
    if scan.requested_start <= health_start:
        UsageScanRequirement.objects.get_or_create(
            scan=scan, kind="HEALTH", org=None, mapping=None, required_start=health_start,
            required_end=plan.cutoff, defaults={"created_at": now},
        )
    if not ProviderCapacityPool.objects.filter(pk=scope.pool_id, current_epoch=epoch).exists():
        plan.phase = "DISCARD"
        plan.save(update_fields=("phase",))
        return len(members)
    scan.planning = False
    scan.updated_at = now
    scan.save(update_fields=("planning", "updated_at"))
    UsagePageClaim.objects.create(scan=scan, ordinal=0, created_at=now, updated_at=now)
    ensure_work("SCAN", str(scan.pk), now, scope=scope, scan=scan)
    plan.delete()
    return len(members)


def _discard(plan, limit):
    if plan.scan_id is not None:
        keys = list(plan.scan.usagescanrequirement_set.order_by("pk").values_list("pk", flat=True)[:limit])
        if keys:
            plan.scan.usagescanrequirement_set.filter(pk__in=keys).delete()
            return len(keys)
    keys = list(plan.usagerecentmember_set.order_by("pk").values_list("pk", flat=True)[:limit])
    if keys:
        plan.usagerecentmember_set.filter(pk__in=keys).delete()
        return len(keys)
    scan = plan.scan
    plan.delete()
    if scan is not None:
        scan.delete()
    return 0


def advance_recent(scope, epoch, now, cutoff, *, limit):
    """Advance one capped scope planning batch under its existing sweep lock."""
    plan = UsageRecentPlan.objects.filter(scope=scope).first()
    if plan is None:
        plan = UsageRecentPlan.objects.create(
            scope=scope, epoch=epoch, generation=scope.next_scan_generation, captured_at=now,
            cutoff=cutoff, created_at=now, updated_at=now,
        )
        scope.next_scan_generation += 1
        scope.save(update_fields=("next_scan_generation",))
    if plan.epoch_id != epoch.pk or plan.generation >= scope.next_scan_generation:
        plan.phase = "DISCARD"
        plan.save(update_fields=("phase",))
    if plan.phase == "DISCARD":
        return max(1, _discard(plan, limit))
    scanned = 0
    if plan.phase == "MAPPINGS":
        found, scanned = _mapping_batch(plan, limit)
        _stage(plan, found, now)
    if plan.phase == "OPEN" and scanned < limit:
        found, consumed = _open_batch(plan, limit - scanned)
        _stage(plan, found, now)
        scanned += consumed
    plan.updated_at = now
    plan.save(update_fields=("phase", "mapping_after", "open_after", "lowest_start", "updated_at"))
    if plan.phase == "TRANSFER" and scanned < limit:
        scanned += _transfer(plan, scope, epoch, now, limit - scanned)
    return max(1, scanned)
