"""Durable outbox delivery, inventory progression and bounded reconciliation."""
from time import monotonic
from uuid import UUID, uuid4

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db.models import Exists, OuterRef, Q, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from selahcue_api.apps.license_keys.selection import aware_utc

from .adapters.contracts import InventoryPage, InventoryRequest, ReadFailed
from .capacity import (
    FRESHNESS, LEASE, POLL, REFRESH, atomic, audit_event, cancel_outboxes, close_database, enqueue,
    local_credential, mutate, positive_id, queue_scan, scope_of, worker_audit,
    worker_configuration,
)
from .configuration import valid_id
from .contracts import (
    AttemptState, ChainState, OutboxKind, OutboxState, ProvisioningErrorCode as Error,
    ProvisioningRejected, ResourceCountState, ScanState, StageState,
)
from .models import (
    ProviderCapacityPool, ProviderExternalResource, ProviderGlobalBudget, ProviderInventoryItem, ProviderInventoryScan,
    ProviderProvisioningOutbox, ProvisioningAttempt, ProvisioningDemand,
)
from .provisioning import (
    _adapter, _expire_attempt, _lock_chain, _locked, _next_provision, _next_recovery, _next_stage,
    _provision_mapping, _recover_provisioning_attempt, _require_outer, _valid_pagination,
)

QUEUE = "provider_provisioning"
OPTIONS = dict(ignore_result=True, acks_late=True, reject_on_worker_lost=True, max_retries=0,
               soft_time_limit=15, time_limit=20)
_NAMES = {
    OutboxKind.PROVISION: "providers.provision",
    OutboxKind.RECOVER: "providers.recover",
    OutboxKind.INVENTORY_PAGE: "providers.inventory_page",
}


def _lock_pool(pool_id):
    budget_id = ProviderCapacityPool.objects.filter(pk=pool_id).values_list("budget_id", flat=True).first()
    if budget_id is None:
        raise ProvisioningRejected(Error.INVALID_CONTEXT)
    _locked(ProviderGlobalBudget, budget_id)
    return _locked(ProviderCapacityPool, pool_id)


def refresh_inventory(pool_id: int, *, clock=timezone.now) -> UUID | None:
    config = worker_configuration()
    _require_outer()
    if not positive_id(pool_id):
        raise ProvisioningRejected(Error.INVALID_CONTEXT)
    with atomic():
        pool = _lock_pool(pool_id)
        if pool.current_epoch_id is None or local_credential(config, scope_of(pool)) is None:
            return None
        scans = ProviderInventoryScan.objects.select_for_update().filter(pool=pool)
        if scans.filter(state=ScanState.PARTIAL).exists():
            return None
        last = scans.order_by("-started_at", "-pk").first()
        at = aware_utc(clock())
        if last is not None and at < last.started_at + REFRESH:
            return None
        return queue_scan(pool, at).pk


def inventory_page(scan_id: UUID, *, clock=timezone.now) -> None:
    _inventory_page(scan_id, clock=clock, outbox_id=None, enough_time=lambda: True)


def _lock_scan(scan_id):
    pool_id = ProviderInventoryScan.objects.filter(pk=scan_id).values_list("pool_id", flat=True).first()
    if pool_id is None:
        raise ProvisioningRejected(Error.INVALID_CONTEXT)
    pool = _lock_pool(pool_id)
    scan = _locked(ProviderInventoryScan, scan_id)
    list(ProviderProvisioningOutbox.objects.select_for_update().filter(
        scan=scan, state__in=(OutboxState.PENDING, OutboxState.PUBLISHING, OutboxState.SENT),
    ).order_by("pk").values_list("pk", flat=True))
    return pool, scan


def _lock_inventory_delivery(outbox_id, scan):
    if outbox_id is None:
        return None, True
    row = _locked(ProviderProvisioningOutbox, outbox_id)
    if row is None or row.state not in (OutboxState.PUBLISHING, OutboxState.SENT):
        return None, False
    return row, (
        row.kind == OutboxKind.INVENTORY_PAGE and row.scan_id == scan.pk and row.pool_id == scan.pool_id
        and (row.requested_page_number, row.requested_cursor) == (scan.page_number, scan.cursor)
    )


def _inventory_page(scan_id, *, clock, outbox_id, enough_time):
    config = worker_configuration()
    _require_outer()
    if type(scan_id) is not UUID:
        raise ProvisioningRejected(Error.INVALID_CONTEXT)
    with atomic():
        pool, scan = _lock_scan(scan_id)
        delivery, matching = _lock_inventory_delivery(outbox_id, scan)
        at = aware_utc(clock())
        if not matching:
            if delivery is not None:
                _cancel_invalid(delivery, at)
            return
        if delivery is not None:
            mutate(delivery, at, state=OutboxState.ACKED, acked_at=at, lease_id=None, lease_until=None)
        if scan.state != ScanState.PARTIAL:
            return
        if scan.lease_until is not None:
            if at >= scan.lease_until:
                _retry_page(scan, at, Error.INVENTORY_UNAVAILABLE)
            return
        if outbox_id is None:
            cancel_outboxes(ProviderProvisioningOutbox.objects.filter(scan=scan), at)
        scope = scope_of(pool)
        credential = local_credential(config, scope)
        if credential is None or scan.scope_epoch_id != pool.current_epoch_id:
            _fail_scan(scan, at, Error.POLICY_MISMATCH)
            return
        if not enough_time():
            enqueue(pool.pk, OutboxKind.INVENTORY_PAGE, at, scan=scan, due=at + POLL)
            return
        operation = "DG_KEYS" if pool.provider == "deepgram" else "OA_PROJECTS"
        request = InventoryRequest(operation, scope, None, scan.cursor)
        lease = uuid4()
        page_number = scan.page_number
        mutate(scan, at, lease_id=lease, lease_until=at + LEASE)
    if enough_time():
        close_database()
        page = _adapter(scope.provider).list_page(request, credential)
    else:
        page = ReadFailed(Error.TRANSPORT_NOT_SENT)
    with atomic():
        pool, scan = _lock_scan(scan_id)
        at = aware_utc(clock())
        same_progress = (
            scan.state == ScanState.PARTIAL and scan.lease_id == lease and at < scan.lease_until
            and scan.page_number == page_number and scan.cursor == request.cursor
        )
        if isinstance(page, InventoryPage):
            consistent = _persist_inventory(pool, scan, page, at)
        else:
            consistent = False
        if not same_progress:
            return
        if scan.scope_epoch_id != pool.current_epoch_id:
            _fail_scan(scan, at, Error.POLICY_MISMATCH)
        elif not consistent or not _valid_pagination(page, scan.cursor):
            _retry_page(scan, at, page.code if isinstance(page, ReadFailed) else Error.RESPONSE_INVALID)
        elif page.terminal_page_seen:
            mutate(scan, at, state=ScanState.COMPLETE, finished_at=at, terminal_page_seen=True,
                   lease_id=None, lease_until=None, page_retry_count=0, error_code=None)
            mutate(pool, at, latest_complete_scan_id=scan.pk, inventory_valid_until=scan.started_at + FRESHNESS)
        elif ProviderProvisioningOutbox.objects.filter(scan=scan, requested_cursor=page.next_cursor).exists():
            _fail_scan(scan, at, Error.RESPONSE_INVALID)
        else:
            mutate(scan, at, cursor=page.next_cursor, page_number=page_number + 1, page_retry_count=0,
                   lease_id=None, lease_until=None, error_code=None)
            enqueue(pool.pk, OutboxKind.INVENTORY_PAGE, at, scan=scan)


def _persist_inventory(pool, scan, page, at):
    consistent = True
    records = {}
    for record in page.records:
        if not valid_id(record.external_id) or record.status not in ("active", "expired", "archived", "unknown"):
            consistent = False
            continue
        metadata = (record.marker, record.created_at, record.status)
        if records.setdefault(record.external_id, metadata) != metadata:
            consistent = False

    resource_scope = pool.parent_scope_id if pool.provider == "deepgram" else "organization-project"
    ids = tuple(records)
    # Deepgram returns a whole project in one response. Batch writes keep the
    # transaction proportional to page bytes instead of issuing SQL per key.
    for index in range(0, len(ids), 1000):
        batch = ids[index:index + 1000]
        items = ProviderInventoryItem.objects.filter(scan=scan, external_id__in=batch)
        existing = {row.external_id: row for row in items}
        new_items = []
        for external_id in batch:
            marker, created_at, status = records[external_id]
            old = existing.get(external_id)
            if old is None:
                new_items.append(ProviderInventoryItem(
                    scan=scan, external_id=external_id, marker=marker,
                    provider_created_at=created_at, provider_status=status, created_at=at,
                ))
            elif (old.marker, old.provider_created_at, old.provider_status) != (marker, created_at, status):
                consistent = False
        ProviderInventoryItem.objects.bulk_create(new_items)

        resources = ProviderExternalResource.objects.filter(provider=pool.provider, resource_scope_id=resource_scope,
                                                            external_id__in=batch)
        seen = {row.external_id: row for row in resources}
        ProviderExternalResource.objects.bulk_create([
            ProviderExternalResource(
                pool=pool, provider=pool.provider, resource_scope_id=resource_scope, external_id=external_id,
                count_state=ResourceCountState.COUNTED, first_seen_at=at, last_seen_at=at, created_at=at, updated_at=at,
            )
            for external_id in batch if external_id not in seen
        ])
        owned = [row.pk for row in seen.values() if row.pool_id == pool.pk]
        if len(owned) != len(seen):
            consistent = False
            audit_event("RECOVERY", scan.pk, at, worker_audit("inventory-cross-parent-conflict"),
                        error_code=Error.IDENTITY_CONFLICT)
        restored = [row.pk for row in seen.values() if row.pool_id == pool.pk
                    and row.count_state == ResourceCountState.EXCLUDED]
        ProviderExternalResource.objects.filter(pk__in=owned).update(
            count_state=ResourceCountState.COUNTED, exclusion_evidence_id=None,
            last_seen_at=Greatest("last_seen_at", Value(at)), updated_at=at,
        )
        for resource_id in restored:
            audit_event("RECOVERY", resource_id, at, worker_audit("counted-positive-observation"))
    return consistent


def _fail_scan(scan, at, code):
    mutate(scan, at, state=ScanState.FAILED, finished_at=at, error_code=code, lease_id=None, lease_until=None)
    cancel_outboxes(ProviderProvisioningOutbox.objects.filter(scan=scan), at)


def _retry_page(scan, at, code):
    count = scan.page_retry_count + 1
    cancel_outboxes(ProviderProvisioningOutbox.objects.filter(scan=scan), at)
    mutate(scan, at, lease_id=None, lease_until=None, page_retry_count=count, error_code=code)
    if count >= 3:
        _fail_scan(scan, at, code)
    else:
        enqueue(scan.pool_id, OutboxKind.INVENTORY_PAGE, at, scan=scan, due=at + POLL)


def _cancel_invalid(row, at):
    mutate(row, at, state=OutboxState.CANCELLED, lease_id=None, lease_until=None, error_code=Error.INTERNAL_FAILURE)
    audit_event("OUTBOX_FAILURE", row.pk, at, worker_audit("invalid-outbox-subject"), error_code=Error.INTERNAL_FAILURE)


def _outbox_uuid(value):
    if type(value) is not str or len(value) != 36:
        raise ProvisioningRejected(Error.INVALID_CONTEXT)
    try:
        parsed = UUID(value)
    except ValueError:
        raise ProvisioningRejected(Error.INVALID_CONTEXT) from None
    if value != str(parsed):
        raise ProvisioningRejected(Error.INVALID_CONTEXT)
    return parsed


def _subject(outbox_id, kind):
    row = ProviderProvisioningOutbox.objects.filter(pk=outbox_id).values("kind", "mapping_id", "attempt_id", "scan_id").first()
    if row is None:
        return None
    if row["kind"] == kind:
        return row[{OutboxKind.PROVISION: "mapping_id", OutboxKind.RECOVER: "attempt_id",
                    OutboxKind.INVENTORY_PAGE: "scan_id"}[kind]]
    with atomic():
        locked = _locked(ProviderProvisioningOutbox, outbox_id)
        if locked.state in (OutboxState.PENDING, OutboxState.SENT, OutboxState.PUBLISHING):
            _cancel_invalid(locked, aware_utc(timezone.now()))
    return None


def _terminal_subject(row):
    if row.kind == OutboxKind.RECOVER:
        return ProvisioningAttempt.objects.filter(
            pk=row.attempt_id,
            state__in=(AttemptState.SUCCEEDED, AttemptState.DEFINITE_FAILURE, AttemptState.CANCELLED,
                       AttemptState.OPERATOR_REQUIRED),
        ).exists()
    if row.kind == OutboxKind.INVENTORY_PAGE:
        return ProviderInventoryScan.objects.filter(pk=row.scan_id).exclude(state=ScanState.PARTIAL).exists()
    return not ProvisioningDemand.objects.filter(current_mapping_id=row.mapping_id).exclude(
        state__in=(ChainState.READY, ChainState.FAILED, ChainState.RETIRED),
    ).exists()


def publish_outbox(outbox_id: UUID, *, clock=timezone.now) -> None:
    worker_configuration()
    _require_outer()
    if type(outbox_id) is not UUID:
        raise ProvisioningRejected(Error.INVALID_CONTEXT)
    with atomic():
        row = _locked(ProviderProvisioningOutbox, outbox_id)
        at = aware_utc(clock())
        if row is None or row.state != OutboxState.PENDING or row.available_at > at:
            return
        if _terminal_subject(row):
            mutate(row, at, state=OutboxState.CANCELLED, lease_id=None, lease_until=None)
            return
        lease = uuid4()
        task_name = _NAMES[row.kind]
        mutate(row, at, state=OutboxState.PUBLISHING, lease_id=lease, lease_until=at + LEASE,
               publish_count=row.publish_count + 1)
    close_database()
    from selahcue_api.celery import app

    try:
        app.send_task(task_name, kwargs={"outbox_id": str(outbox_id)}, task_id=str(outbox_id),
                      retry=False, queue=QUEUE, ignore_result=True)
    except SoftTimeLimitExceeded:
        raise
    except Exception:
        success = False
    else:
        success = True
    with atomic():
        row = _locked(ProviderProvisioningOutbox, outbox_id)
        at = aware_utc(clock())
        if row.state != OutboxState.PUBLISHING or row.lease_id != lease:
            return
        if success:
            mutate(row, at, state=OutboxState.SENT, sent_at=at, lease_id=None, lease_until=None, error_code=None)
        else:
            if row.error_code != Error.INTERNAL_FAILURE:
                audit_event("OUTBOX_FAILURE", row.pk, at, worker_audit("broker-publish-failed"),
                            error_code=Error.INTERNAL_FAILURE, publish_count=row.publish_count)
            mutate(row, at, state=OutboxState.PENDING, available_at=at + POLL, lease_id=None, lease_until=None,
                   error_code=Error.INTERNAL_FAILURE)


def _reclaim_publication(outbox_id, clock):
    with atomic():
        row = _locked(ProviderProvisioningOutbox, outbox_id)
        at = aware_utc(clock())
        if (
            row.state == OutboxState.PUBLISHING and row.lease_until <= at
            or row.state == OutboxState.SENT and row.sent_at is not None and row.sent_at + LEASE <= at
        ):
            new_state = OutboxState.CANCELLED if _terminal_subject(row) else OutboxState.PENDING
            mutate(row, at, state=new_state, lease_id=None, lease_until=None, available_at=at)


def _sweep_chain(mapping_id, config, clock):
    with atomic():
        chain = _lock_chain(mapping_id, config, original=False)
        at = aware_utc(clock())
        rows = ProviderProvisioningOutbox.objects.filter(mapping_id=mapping_id)
        if chain.demand.current_mapping_id != mapping_id or chain.demand.state in (
            ChainState.READY, ChainState.FAILED, ChainState.RETIRED,
        ):
            cancel_outboxes(rows, at)
            return
        if chain.demand.state == ChainState.WAITING_CAPACITY:
            _next_provision(chain, at)
            return
        stage = _next_stage(chain)
        if stage is None:
            _next_provision(chain, at)
            return
        attempt = chain.attempts.get(stage.current_attempt_id)
        if attempt is None:
            if stage.state == StageState.READY:
                _next_provision(chain, at)
            return
        if _expire_attempt(chain, attempt, at):
            return
        due = attempt.next_action_at
        if due is not None and due > at:
            return
        if attempt.state in (AttemptState.PREPARED, AttemptState.DEFINITE_FAILURE) and stage.state == StageState.READY:
            _next_provision(chain, at)
        elif attempt.state in (AttemptState.OUTCOME_UNKNOWN, AttemptState.RECOVERING):
            _next_recovery(chain, attempt, at)


def _sweep_scan(scan_id, clock):
    with atomic():
        _, scan = _lock_scan(scan_id)
        at = aware_utc(clock())
        if scan.state != ScanState.PARTIAL:
            cancel_outboxes(ProviderProvisioningOutbox.objects.filter(scan=scan), at)
        elif scan.lease_until is None:
            enqueue(scan.pool_id, OutboxKind.INVENTORY_PAGE, at, scan=scan)
        elif scan.lease_until <= at:
            _retry_page(scan, at, Error.INVENTORY_UNAVAILABLE)


def sweep_provisioning(*, limit: int = 100, clock=timezone.now) -> int:
    config = worker_configuration()
    _require_outer()
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ProvisioningRejected(Error.INVALID_CONTEXT)
    until = monotonic() + 15
    processed = 0
    now = aware_utc(clock())
    local_mappings = Q(pk__in=[])
    local_pools = Q(pk__in=[])
    local_scans = Q(pk__in=[])
    for entry in config.policy.scopes if config.policy else ():
        provider, parent = entry.scope.provider, entry.scope.parent_scope_id
        local_mappings |= Q(current_mapping__provider=provider, current_mapping__parent_scope_id=parent)
        local_pools |= Q(provider=provider, parent_scope_id=parent)
        local_scans |= Q(pool__provider=provider, pool__parent_scope_id=parent)
    active_outbox = ProviderProvisioningOutbox.objects.filter(
        mapping_id=OuterRef("current_mapping_id"), state__in=(OutboxState.PENDING, OutboxState.PUBLISHING, OutboxState.SENT),
    )
    mappings = ProvisioningDemand.objects.filter(
        local_mappings, state__in=(ChainState.QUEUED, ChainState.WORKING, ChainState.RECOVERY_REQUIRED,
                                 ChainState.WAITING_CAPACITY), current_mapping__isnull=False,
    ).filter(~Exists(active_outbox)).order_by("updated_at", "pk").values_list("current_mapping_id", flat=True)
    scans = ProviderInventoryScan.objects.filter(local_scans, state=ScanState.PARTIAL).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lte=now),
    ).order_by("updated_at", "pk").values_list("pk", flat=True)
    pools = ProviderCapacityPool.objects.filter(local_pools, current_epoch__isnull=False).filter(~Exists(
        ProviderInventoryScan.objects.filter(pool_id=OuterRef("pk")).filter(
            Q(state=ScanState.PARTIAL) | Q(started_at__gt=now - REFRESH),
        ),
    )).order_by("updated_at", "pk").values_list("pk", flat=True)
    # Bound each class and interleave candidates so progress on a busy provider
    # does not starve its pending publication or inventory.
    pending = ProviderProvisioningOutbox.objects.filter(state=OutboxState.PENDING, available_at__lte=now)
    abandoned = ProviderProvisioningOutbox.objects.filter(
        Q(state=OutboxState.PUBLISHING, lease_until__lte=now)
        | Q(state=OutboxState.SENT, sent_at__lte=now - LEASE),
    )
    from itertools import zip_longest

    tasks = (
        (list(pending.order_by("available_at", "pk").values_list("pk", flat=True)[:min(limit, 20)]),
         lambda row: publish_outbox(row, clock=clock)),
        (list(abandoned.order_by("updated_at", "pk").values_list("pk", flat=True)[:limit]),
         lambda row: _reclaim_publication(row, clock)),
        (list(scans[:limit]), lambda row: _sweep_scan(row, clock)),
        (list(pools[:limit]), lambda row: refresh_inventory(row, clock=clock)),
        (list(mappings[:limit]), lambda row: _sweep_chain(row, config, clock)),
    )
    for batch in zip_longest(*(ids for ids, _ in tasks)):
        for value, (_, process) in zip(batch, tasks, strict=True):
            if value is None:
                continue
            if processed == limit or monotonic() >= until:
                return processed
            try:
                process(value)
            except ProvisioningRejected as error:
                if error.code != Error.INTERNAL_FAILURE:
                    raise
            processed += 1
    return processed


def _consume(kind, outbox_id, service):
    deadline = monotonic() + 20
    worker_configuration()
    identifier = _outbox_uuid(outbox_id)
    subject = _subject(identifier, kind)
    if subject is not None:
        service(subject, clock=timezone.now, outbox_id=identifier, enough_time=lambda: deadline - monotonic() >= 12)


@shared_task(name="providers.provision", **OPTIONS)
def provision_task(outbox_id: str):
    _consume(OutboxKind.PROVISION, outbox_id, _provision_mapping)


@shared_task(name="providers.recover", **OPTIONS)
def recovery_task(outbox_id: str):
    _consume(OutboxKind.RECOVER, outbox_id, _recover_provisioning_attempt)


@shared_task(name="providers.inventory_page", **OPTIONS)
def inventory_page_task(outbox_id: str):
    _consume(OutboxKind.INVENTORY_PAGE, outbox_id, _inventory_page)


@shared_task(name="providers.publish_outbox", **OPTIONS)
def publish_outbox_task(outbox_id: str):
    worker_configuration()
    publish_outbox(_outbox_uuid(outbox_id))


@shared_task(name="providers.sweep", **OPTIONS)
def sweep_task():
    sweep_provisioning()
