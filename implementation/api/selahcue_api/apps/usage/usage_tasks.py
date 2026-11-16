"""Durable usage job authority, bounded publication, and worker entrypoints."""
from contextlib import contextmanager
from datetime import timedelta
import time
from uuid import UUID, uuid4

from django.db import connection, connections, transaction
from django.utils import timezone

from selahcue_api.apps.providers.configuration import get_provider_configuration
from selahcue_api.apps.providers.contracts import ProviderConfigurationError

from .models import UsageOutbox, UsageWork
from .observation_contracts import RetentionKind, UsageFailureCode as Code, UsageRejected

TASKS = {
    "SCAN": "usage.scan", "RECONCILE": "usage.reconcile", "ATTRIBUTE": "usage.attribute",
    "MINT_RECOVERY": "usage.recover_mint", "RETENTION": "usage.retain",
}
_OUTSTANDING = ("PENDING", "PUBLISHING", "SENT")
_PAGE_OR_PUBLISH_DELAYS = {1: timedelta(seconds=5), 2: timedelta(seconds=30)}
_REPLACEMENT_COOLDOWN = timedelta(seconds=120)


def require_usage_role(*, maintenance=False):
    try:
        return get_provider_configuration(required_role="maintenance" if maintenance else "usage")
    except ProviderConfigurationError:
        raise UsageRejected(Code.CONFIG_UNAVAILABLE) from None


@contextmanager
def bounded_transaction(*, deadline=None, deadline_ns=None, monotonic_ns=time.monotonic_ns):
    local_limit = monotonic_ns() + 10_000_000_000
    deadline_ns = local_limit if deadline_ns is None else min(local_limit, deadline_ns)
    if deadline is not None:
        deadline_ns = min(deadline_ns, int(deadline * 1_000_000_000))
    if deadline_ns <= monotonic_ns():
        raise UsageRejected(Code.TASK_BUDGET)
    with transaction.atomic():
        if connection.vendor != "postgresql":
            yield
            return

        def guard(execute, sql, params, many, context):
            # An inner atomic block may need to recover a failed transaction
            # or close its savepoint after the work deadline. The PostgreSQL
            # connection cannot accept SET LOCAL while awaiting that rollback.
            if sql.lstrip().upper().startswith(("ROLLBACK TO SAVEPOINT ", "RELEASE SAVEPOINT ")):
                return execute(sql, params, many, context)
            remaining_ms = (deadline_ns - monotonic_ns()) // 1_000_000
            if remaining_ms <= 0:
                raise UsageRejected(Code.TASK_BUDGET)
            # Use the same atomic driver cursor without recursing through this
            # Django execution wrapper. SET values are computed finite ints.
            context["cursor"].cursor.execute(
                f"SET LOCAL lock_timeout = '{min(2000, remaining_ms)}ms'; "
                f"SET LOCAL statement_timeout = '{min(5000, remaining_ms)}ms'"
            )
            return execute(sql, params, many, context)

        with connection.execute_wrapper(guard):
            yield


def _outbox(work, now):
    return UsageOutbox.objects.get_or_create(
        work=work, generation=work.execution_generation,
        defaults={"available_at": max(now, work.due_at), "created_at": now, "updated_at": now},
    )[0]


def ensure_work(kind, subject_key, now, **subject):
    work, created = UsageWork.objects.select_for_update().get_or_create(
        kind=kind, subject_key=subject_key, state__in=("PENDING", "RUNNING"),
        defaults={
            **subject, "created_at": now, "updated_at": now, "due_at": now, "state": "PENDING",
        },
    )
    if created:
        _outbox(work, now)
    return work


def next_generation(work, now, *, due_at=None, code=None):
    work.state, work.lease_id, work.lease_until = "PENDING", None, None
    work.execution_generation += 1
    work.last_error = code
    work.due_at = due_at or now
    work.updated_at = now
    work.save(update_fields=(
        "state", "lease_id", "lease_until", "execution_generation", "last_error", "due_at", "updated_at",
    ))
    _outbox(work, now)


def _fail_publication(work, delivery, now):
    delivery.first_failure_at = delivery.first_failure_at or now
    delivery.last_error = Code.PUBLICATION_FAILED
    delivery.lease_id = delivery.lease_until = None
    delivery.updated_at = now
    if delivery.publish_attempts >= 3:
        delivery.state = "FAILED"
        delivery.save()
        next_generation(work, now, due_at=now + _REPLACEMENT_COOLDOWN, code=Code.PUBLICATION_FAILED)
    else:
        delivery.state = "PENDING"
        delivery.available_at = max(now, delivery.first_failure_at + _PAGE_OR_PUBLISH_DELAYS[delivery.publish_attempts])
        delivery.save()


def _parse_uuid(value):
    if type(value) is not str or len(value) != 36:
        raise ValueError
    identifier = UUID(value)
    if str(identifier) != value:
        raise ValueError
    return identifier


def queue_for(kind):
    return "celery" if kind == "RETENTION" else "provider_usage"


def _claim_publication(work_id, maintenance, clock):
    with bounded_transaction():
        work = UsageWork.objects.select_for_update().filter(pk=work_id, state="PENDING").first()
        if work is None or (work.kind == "RETENTION") != maintenance:
            return None
        delivery = UsageOutbox.objects.select_for_update().filter(
            work=work, generation=work.execution_generation,
        ).first()
        now = clock()
        if work.due_at > now:
            return None
        if delivery is None:
            delivery = _outbox(work, now)
        if delivery.state == "PUBLISHING" and delivery.lease_until <= now:
            _fail_publication(work, delivery, now)
        elif delivery.state == "SENT" and delivery.sent_at + timedelta(seconds=30) <= now:
            _fail_publication(work, delivery, now)
        if delivery.state != "PENDING" or delivery.available_at > now:
            return None
        delivery.state = "PUBLISHING"
        delivery.lease_id = uuid4()
        delivery.lease_until = now + timedelta(seconds=30)
        delivery.publish_attempts += 1
        delivery.updated_at = now
        delivery.save()
        return work.kind, delivery.pk, delivery.lease_id


def _finish_publication(work_id, delivery_id, lease, sent, clock):
    with bounded_transaction():
        work = UsageWork.objects.select_for_update().filter(pk=work_id).first()
        if work is None:
            return
        delivery = UsageOutbox.objects.select_for_update().filter(pk=delivery_id, work=work).first()
        now = clock()
        if (
            delivery is None or delivery.state != "PUBLISHING" or delivery.lease_id != lease
            or delivery.lease_until <= now or delivery.generation != work.execution_generation
            or work.state != "PENDING"
        ):
            return
        if not sent:
            _fail_publication(work, delivery, now)
            return
        delivery.state = "SENT"
        delivery.lease_id = delivery.lease_until = None
        delivery.sent_at = delivery.updated_at = now
        delivery.save()


def publish_work(work_id, *, app, maintenance=False, clock=timezone.now):
    require_usage_role(maintenance=maintenance)
    authorized = _claim_publication(work_id, maintenance, clock)
    if authorized is None:
        return
    kind, delivery_id, lease = authorized
    sent = False
    connections.close_all()
    try:
        app.send_task(
            TASKS[kind], kwargs={"work_id": str(work_id)}, task_id=str(delivery_id),
            queue=queue_for(kind), retry=False, ignore_result=True,
        )
        sent = True
    except Exception:
        # Transport errors can contain broker URLs or credential representations.
        pass
    _finish_publication(work_id, delivery_id, lease, sent, clock)


def claim_work(work_id, delivery_id, kind, queue, *, clock=timezone.now, deadline_ns=None):
    if queue != queue_for(kind):
        return None
    with bounded_transaction(deadline_ns=deadline_ns):
        work = UsageWork.objects.select_for_update().filter(pk=work_id, kind=kind, state="PENDING").first()
        if work is None:
            return None
        delivery = UsageOutbox.objects.select_for_update().filter(
            pk=delivery_id, work=work, generation=work.execution_generation, state__in=("PUBLISHING", "SENT"),
        ).first()
        now = clock()
        if delivery is None or work.due_at > now:
            return None
        work.state = "RUNNING"
        work.lease_id = uuid4()
        work.lease_until = now + timedelta(seconds=20 if kind == "RETENTION" else 130)
        work.started_at = work.updated_at = now
        work.save()
        delivery.state = "ACKED"
        delivery.acked_at = delivery.updated_at = now
        delivery.lease_id = delivery.lease_until = None
        delivery.save()
        return work


def finish_work(work_id, lease, *, pending=False, due_at=None, code=None, clock=timezone.now,
                deadline_ns=None, monotonic_ns=time.monotonic_ns):
    with bounded_transaction(deadline_ns=deadline_ns, monotonic_ns=monotonic_ns):
        from .models import UsageOrgState

        org_id = UsageWork.objects.filter(pk=work_id, kind="RECONCILE").values_list("org_id", flat=True).first()
        subject = UsageOrgState.objects.select_for_update().filter(org_id=org_id).first() if org_id else None
        work = UsageWork.objects.select_for_update().filter(pk=work_id, state="RUNNING", lease_id=lease).first()
        now = clock()
        if work is None or work.lease_until <= now:
            return
        dirty = subject is not None and subject.applied_revision < subject.dirty_revision
        if pending or dirty:
            next_generation(work, now, due_at=due_at if pending else subject.next_due_at, code=code)
        else:
            work.state = "COMPLETE" if code is None else "FAILED"
            work.finished_at = work.updated_at = now
            work.lease_id = work.lease_until = None
            work.last_error = code
            work.save()


def run_scan_work(work_id: UUID, *, clock=timezone.now, monotonic_ns=time.monotonic_ns, deadline_ns=None) -> None:
    from .scans import run_scan

    deadline_ns = monotonic_ns() + 120_000_000_000 if deadline_ns is None else deadline_ns
    require_usage_role()
    with bounded_transaction(deadline_ns=deadline_ns, monotonic_ns=monotonic_ns):
        work = UsageWork.objects.filter(pk=work_id, kind="SCAN", state="RUNNING").first()
    if work is None:
        return
    status, due_at, error = run_scan(work, clock=clock, monotonic_ns=monotonic_ns, deadline_ns=deadline_ns)
    finish_work(
        work_id, work.lease_id, pending=status == "PENDING", due_at=due_at, code=error, clock=clock,
        deadline_ns=deadline_ns, monotonic_ns=monotonic_ns,
    )


def run_claimed(work, *, clock=timezone.now, deadline_ns=None):
    if work.kind == "SCAN":
        run_scan_work(work.pk, clock=clock, deadline_ns=deadline_ns)
        return
    now = clock()
    if work.kind == "RECONCILE":
        from .reconciliation import reconcile_org
        result = reconcile_org(work.org_id, now, clock=clock)
        pending = result.blocked_reason is not None
        error = result.blocked_reason
    elif work.kind == "ATTRIBUTE":
        from .observations import attribute_scope_batch
        result = attribute_scope_batch(work.scope_id, after=None, clock=clock)
        pending, error = not result.exhausted, None
    elif work.kind == "MINT_RECOVERY":
        from selahcue_api.apps.providers.stt_recovery import recover_abandoned_stt_mint
        result = recover_abandoned_stt_mint(work.attempt_id, clock=clock)
        pending, error = result.state == "unavailable", None
    else:
        from .retention import prune_usage_batch
        result = prune_usage_batch(
            RetentionKind(work.retention_kind), clock=clock,
            deadline=None if deadline_ns is None else (deadline_ns - 2_000_000_000) / 1_000_000_000,
        )
        pending, error = result.has_more, None
    finish_work(
        work.pk, work.lease_id, pending=pending, due_at=now + timedelta(seconds=60) if pending else None,
        code=error, clock=clock, deadline_ns=deadline_ns,
    )


def repair_delivery_batch(app, *, maintenance, remaining, deadline, clock=timezone.now):
    now = clock()
    candidates = UsageWork.objects.filter(state__in=("PENDING", "RUNNING"), due_at__lte=now)
    candidates = candidates.filter(kind="RETENTION") if maintenance else candidates.exclude(kind="RETENTION")
    count = 0
    keys = candidates.order_by("due_at", "id").values_list("id", flat=True)[:remaining]
    for key in keys:
        if time.monotonic() >= deadline:
            break
        with bounded_transaction():
            work = UsageWork.objects.select_for_update().get(pk=key)
            now = clock()
            if work.state == "RUNNING" and work.lease_until <= now:
                next_generation(work, now)
            elif work.state == "PENDING" and not UsageOutbox.objects.filter(
                work=work, generation=work.execution_generation,
            ).exists():
                _outbox(work, now)
        publish_work(key, app=app, maintenance=maintenance, clock=clock)
        count += 1
    return count


def _cursor(purpose, now):
    from .models import UsageDiscoveryCursor

    return UsageDiscoveryCursor.objects.select_for_update().get_or_create(
        purpose=purpose, defaults={"created_at": now, "updated_at": now},
    )[0]


def _seek(query, *, key, at_field, cursor):
    from django.db.models import Q

    if cursor.last_at is not None:
        query = query.filter(Q(**{f"{at_field}__gt": cursor.last_at}) | Q(**{
            at_field: cursor.last_at, f"{key}__gt": cursor.last_uuid,
        }))
    return query.order_by(at_field, key).first()


def _save_cursor(cursor, now, *, identifier=None, stamp=None, numeric=None):
    cursor.last_uuid, cursor.last_at, cursor.last_id = identifier, stamp, numeric
    cursor.updated_at = now
    cursor.save()


def _accounting_start(mapping, now):
    from .services import _current_week, _next_week_bounds

    week = _current_week(mapping.org, now)
    if week is not None:
        return week.counted_from
    bounds, _ = _next_week_bounds(mapping.org, now)
    return bounds.start


def _initial_candidate(clock, *, deadline=None):
    from django.db.models import Exists, OuterRef
    from selahcue_api.apps.providers.models import ProviderCredential
    from .models import SttOrgReadiness

    with bounded_transaction(deadline=deadline):
        now = clock()
        cursor = _cursor("INITIAL_MAPPING", now)
        published = SttOrgReadiness.objects.filter(org_id=OuterRef("org_id"), mapping=OuterRef("pk"))
        queryset = ProviderCredential.objects.filter(
            provider="deepgram", state="ACTIVE", activated_at__isnull=False,
        ).filter(~Exists(published)).select_related("org")
        mapping = _seek(queryset, key="pk", at_field="activated_at", cursor=cursor)
        if mapping is None:
            _save_cursor(cursor, now)
            return None
        _save_cursor(cursor, now, identifier=mapping.pk, stamp=mapping.activated_at)
        return mapping


def _initial_scan(mapping, clock, *, deadline=None):
    from . import health
    from .models import UsageObservedInterval, UsageScan, UsageScanRequirement
    from .observation_contracts import ScanPurpose, ScanState
    from .observations import dirty_orgs
    from .scans import enroll_scope, floor_second, schedule_scan

    with bounded_transaction(deadline=deadline):
        start_hint = clock()
        row, scope, evaluation = enroll_scope(mapping.provider, mapping.parent_scope_id, start_hint)
        now = clock()
        try:
            epoch, _ = health.producer_policy(scope)
        except UsageRejected as error:
            health.producer_failure(row, evaluation, error.code, now)
            return False
        start, end = floor_second(_accounting_start(mapping, now)), floor_second(now)
        if start >= end:
            return False
        scan = UsageScan.objects.filter(
            scope=scope, policy_epoch=epoch, planning=False, started_at__gte=mapping.activated_at,
            started_at__gt=now - health.FRESHNESS, requested_start__lte=start, requested_end__gt=start,
            state__in=(ScanState.PARTIAL, ScanState.COMPLETE),
        ).order_by("-requested_end", "-generation").first()
        if scan is not None and scan.state == ScanState.COMPLETE and not UsageObservedInterval.objects.filter(scan=scan).exists():
            scan = None
        if scan is not None:
            _, created = UsageScanRequirement.objects.get_or_create(
                scan=scan, org_id=mapping.org_id, mapping=mapping.pk, kind="INITIAL",
                required_start=start, required_end=min(end, scan.requested_end), defaults={"created_at": now},
            )
            if scan.state == ScanState.COMPLETE and created:
                dirty_orgs((mapping.org_id,), now)
            return created
        return schedule_scan(
            scope, ScanPurpose.INITIAL, start, end, now, epoch,
            requirements=(("INITIAL", mapping.org_id, mapping.pk, start, end),),
        ) is not None


def _initial_batch(limit, deadline, clock):
    scanned, scheduled = 0, 0
    while scanned < limit and time.monotonic() < deadline:
        try:
            mapping = _initial_candidate(clock, deadline=deadline)
            if mapping is None:
                break
            scanned += 1
            if time.monotonic() >= deadline:
                break
            scheduled += _initial_scan(mapping, clock, deadline=deadline)
        except UsageRejected as error:
            if error.code != Code.TASK_BUDGET:
                raise
            break
    return scanned, scheduled


def _limit(limit):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Expected a limit from 1 to 100")


def schedule_initial_stt_scans(*, limit: int = 100) -> int:
    require_usage_role()
    _limit(limit)
    return _initial_batch(limit, time.monotonic() + 10, timezone.now)[1]


def _local_enrollment(config, now, limit, deadline):
    from selahcue_api.apps.providers.models import ProviderCapacityPool
    from .models import UsageScope
    from .scans import enroll_scope

    if config.policy is None or limit == 0:
        return 0
    present = set(UsageScope.objects.values_list("provider", "parent_scope_id"))
    published = ProviderCapacityPool.objects.exclude(usagescope__isnull=False).order_by("pk").values_list(
        "provider", "parent_scope_id",
    )[:limit]
    wanted = sorted({(p.scope.provider, p.scope.parent_scope_id) for p in config.policy.scopes} | set(published))
    count = 0
    for provider, parent in wanted:
        if count == limit or time.monotonic() >= deadline:
            break
        if (provider, parent) in present and not ProviderCapacityPool.objects.filter(
            provider=provider, parent_scope_id=parent, usagescope__isnull=True,
        ).exists():
            continue
        with bounded_transaction():
            enroll_scope(provider, parent, now)
        count += 1
    return count


def _scope_candidate(purpose, clock):
    from .models import UsageScope

    with bounded_transaction():
        now = clock()
        key = _cursor(purpose, now)
        scope = UsageScope.objects.filter(pk__gt=key.last_id or 0).order_by("pk").first()
        _save_cursor(key, now, numeric=scope.pk if scope else None)
        return scope


def _schedule_periodic(hint, purpose, clock, *, deadline=None, limit=100):
    from . import health
    from .models import UsageScope
    from .observation_contracts import ScanPurpose
    from .scans import floor_hour, floor_second, schedule_history, schedule_scan

    with bounded_transaction(deadline=deadline):
        now = clock()
        provider = health.lock_provider(hint.provider, now)
        scope = UsageScope.objects.select_for_update().get(pk=hint.pk)
        evaluation = health.scope_health(scope, now)
        now = clock()
        try:
            epoch, _ = health.producer_policy(scope)
        except UsageRejected as error:
            health.producer_failure(provider, evaluation, error.code, now)
            return 1
        aligned_end = floor_second(now) if scope.provider == "deepgram" else floor_hour(now)
        if purpose == "RECENT_SCOPE":
            from .recent import advance_recent

            consumed = advance_recent(scope, epoch, now, aligned_end, limit=limit) if scope.provider == "deepgram" else 1
            health_start = aligned_end - health.HEALTH_WINDOW
            schedule_scan(
                scope, ScanPurpose.HEALTH, health_start, aligned_end, now, epoch,
                requirements=(("HEALTH", None, None, health_start, aligned_end),),
            )
            ensure_work("ATTRIBUTE", str(scope.pk), now, scope=scope)
            return consumed
        schedule_history(scope, epoch, aligned_end, now)
        return 1


def _recover_candidate(clock):
    from selahcue_api.apps.providers.stt_recovery import mint_attempt_model

    attempt_model = mint_attempt_model()
    if attempt_model is None:
        return False
    with bounded_transaction():
        now = clock()
        cursor = _cursor("RECOVERY", now)
        rows = attempt_model.objects.filter(state="DISPATCHED", dispatch_not_after__lte=now - timedelta(seconds=4))
        row = _seek(rows, key="pk", at_field="dispatch_not_after", cursor=cursor)
        if row is None:
            _save_cursor(cursor, now)
            return False
        _save_cursor(cursor, now, identifier=row.pk, stamp=row.dispatch_not_after)
        ensure_work("MINT_RECOVERY", str(row.pk), now, attempt_id=row.pk)
        return True


def _reschedule_publications(clock, limit, deadline):
    from django.db.models import Exists, F, OuterRef, Subquery
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.providers.models import ProviderCredential
    from .models import SttOrgReadiness, SttOrgReadinessScope, SttScopeReadiness, UsageOrgState

    if limit == 0:
        return 0
    with bounded_transaction(deadline=deadline):
        now = clock()
        cursor = _cursor("RECONCILE", now)
        stale_health = SttOrgReadiness.objects.filter(org_id=OuterRef("pk"), health_revision__lt=F("health__revision"))
        stale_scope = SttOrgReadinessScope.objects.filter(
            publication_id=OuterRef("pk"), scope_revision__lt=F("scope__revision")
        )
        dirty = UsageOrgState.objects.filter(org_id=OuterRef("pk"), dirty_revision__gt=F("applied_revision"))
        observed = SttScopeReadiness.objects.filter(valid_until__gt=now).values("scope__parent_scope_id")
        published = SttOrgReadiness.objects.filter(org_id=OuterRef("org_id"), mapping=OuterRef("pk"))
        initial = ProviderCredential.objects.filter(
            org_id=OuterRef("pk"), state="ACTIVE", provider="deepgram",
            parent_scope_id__in=Subquery(observed),
        ).filter(~Exists(published))
        pending = UsageWork.objects.filter(
            org_id=OuterRef("pk"), kind="RECONCILE", state__in=("PENDING", "RUNNING"),
        )
        orgs = list(CustomerOrg.objects.filter(pk__gt=cursor.last_id or 0).filter(
            (Exists(stale_health) | Exists(stale_scope) | Exists(dirty) | Exists(initial)) & ~Exists(pending),
        ).order_by("pk").values_list("pk", flat=True)[:limit])
        for org_id in orgs:
            ensure_work("RECONCILE", str(org_id), now, org_id=org_id)
        _save_cursor(cursor, now, numeric=orgs[-1] if len(orgs) == limit else None)
        return len(orgs)


def sweep_usage(*, limit: int = 100, clock=timezone.now) -> int:
    from selahcue_api.celery import app

    config = require_usage_role()
    _limit(limit)
    deadline = time.monotonic() + 10
    consumed = _local_enrollment(config, clock(), min(limit, max(1, limit // 8)), deadline)
    initial, _ = _initial_batch(min(limit - consumed, max(1, limit // 8)), deadline, clock)
    consumed += initial
    if time.monotonic() < deadline:
        consumed += _reschedule_publications(clock, min(limit - consumed, limit // 8), deadline)
    for purpose in ("RECENT_SCOPE", "HISTORY_SCOPE"):
        for _ in range(min(limit - consumed, max(1, limit // 8))):
            if time.monotonic() >= deadline:
                return consumed
            scope = _scope_candidate(purpose, clock)
            if scope is None:
                break
            if consumed >= limit:
                break
            remaining = limit - consumed
            batch = max(1, remaining - min(remaining // 4, 12)) if purpose == "RECENT_SCOPE" else 1
            consumed += _schedule_periodic(scope, purpose, clock, deadline=deadline, limit=batch)
    for _ in range(min(limit - consumed, max(1, limit // 8))):
        if time.monotonic() >= deadline or not _recover_candidate(clock):
            break
        consumed += 1
    if consumed < limit:
        consumed += repair_delivery_batch(app, maintenance=False, remaining=limit-consumed, deadline=deadline, clock=clock)
    return consumed


def sweep_retention(*, clock=timezone.now):
    from selahcue_api.celery import app

    require_usage_role(maintenance=True)
    deadline = time.monotonic() + 10
    now = clock()
    kinds = tuple(RetentionKind)
    with bounded_transaction():
        cursor = _cursor("RETENTION", now)
        index = (cursor.last_id + 1) % len(kinds) if cursor.last_id is not None else 0
        kind = kinds[index]
        _save_cursor(cursor, now, numeric=index)
        ensure_work("RETENTION", kind.value, now, retention_kind=kind)
    return repair_delivery_batch(app, maintenance=True, remaining=99, deadline=deadline, clock=clock)
