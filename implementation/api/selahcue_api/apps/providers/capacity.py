"""Capacity and outbox primitives. The caller owns the provider and pool locks."""
from contextlib import contextmanager
from datetime import timedelta
from uuid import uuid4

from django.db import DatabaseError, connection, connections, transaction
from django.db.models import Count, Max, Q

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.graphql.context import ActorContext, ActorKind

from .bootstrap import get_initialized_provider_entrypoint
from .configuration import get_provider_configuration, has_creation_authority, selected_role, valid_evidence, valid_id
from .contracts import (
    AllowanceState, CapacityUnavailableCode as Capacity, ClaimState, ConfigErrorCode,
    OutboxKind, OutboxState, ProviderConfigurationError, ProviderScope, ProvisioningAuditContext,
    ProvisioningErrorCode as Error, ProvisioningRejected, ResourceCountState, ScanState,
)
from .models import (
    ProviderCapacityPool, ProviderCreateAllowance, ProviderExternalResource, ProviderGlobalBudget,
    ProviderInventoryScan, ProviderProvisioningOutbox, ProviderResourceClaim,
)

POLL = timedelta(seconds=5)
LEASE = timedelta(seconds=30)
FRESHNESS = timedelta(seconds=300)
REFRESH = timedelta(seconds=60)
LIVE_OUTBOX = (OutboxState.PENDING, OutboxState.PUBLISHING, OutboxState.SENT)
WORKER = "provider-provisioning-worker"


def worker_configuration(*, operator=False):
    config = get_provider_configuration(required_role="provisioner")
    entrypoint = get_initialized_provider_entrypoint()
    accepted = ("operator",) if operator else ("operator", "celery_worker")
    if selected_role() != "provisioner" or entrypoint not in accepted:
        raise ProviderConfigurationError(ConfigErrorCode.PCFG_ROLE_MISMATCH)
    return config


def local_scope(config, scope):
    return next((entry for entry in config.policy.scopes if entry.scope == scope), None) if config.policy else None


def local_credential(config, scope):
    return next((entry for entry in config.provisioning_credentials if entry.scope == scope), None)


def scope_of(pool):
    return ProviderScope(pool.provider, pool.parent_scope_id)


def positive_id(value):
    return type(value) is int and 0 < value <= 9223372036854775807


def mutate(row, at, **changes):
    for name, value in changes.items():
        setattr(row, name, value)
    row.updated_at = at
    row.save(update_fields=(*changes, "updated_at"))


@contextmanager
def atomic():
    try:
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '2000ms'")
                    cursor.execute("SET LOCAL statement_timeout = '5000ms'")
            yield
    except DatabaseError:
        raise ProvisioningRejected(Error.INTERNAL_FAILURE) from None


def close_database():
    # Inspect initialized connections without opening a previously unused alias.
    active = connections.all(initialized_only=True)
    if any(conn.in_atomic_block or (conn.connection is not None and not conn.get_autocommit()) for conn in active):
        raise ProvisioningRejected(Error.INTERNAL_FAILURE)
    connections.close_all()
    if any(conn.connection is not None for conn in connections.all(initialized_only=True)):
        raise ProvisioningRejected(Error.INTERNAL_FAILURE)


def validate_audit(audit):
    from uuid import UUID

    if not (
        type(audit) is ProvisioningAuditContext and valid_id(audit.operator_id)
        and len(audit.operator_id) <= 128 and type(audit.request_id) is UUID
        and valid_evidence(audit.evidence_ref)
    ):
        raise ProvisioningRejected(Error.INVALID_CONTEXT)


def worker_audit(evidence_ref):
    return ProvisioningAuditContext(WORKER, uuid4(), evidence_ref)


def audit_event(action, target, at, audit, **metadata):
    record_audit_event(
        ActorContext(kind=ActorKind.SERVICE, actor_id=audit.operator_id),
        action=f"PROVIDER_PROVISIONING_{action}", target_type="provider_provisioning", target_id=str(target),
        request_id=str(audit.request_id), reason=audit.evidence_ref,
        after={"observed_at": at.isoformat(), **metadata}, source_surface="provider_provisioning_internal",
    )


def lock_budget_pools(provider, parent_ids):
    budget = ProviderGlobalBudget.objects.select_for_update().filter(provider=provider).first()
    pools = list(ProviderCapacityPool.objects.select_for_update().filter(
        budget=budget, provider=provider, parent_scope_id__in=parent_ids,
    ).order_by("provider", "parent_scope_id")) if budget else []
    return budget, pools


def matching_scope_epoch(pool, scope_policy):
    from .policy_publication import canonical_scope, decode_scope, digest

    epoch = pool.current_epoch
    if epoch is None or epoch.pool_id != pool.pk or scope_policy is None:
        return None
    try:
        stored = decode_scope(epoch.policy)
    except ProvisioningRejected:
        return None
    if epoch.digest != digest(canonical_scope(scope_policy)) or stored != scope_policy:
        return None
    return epoch


def create_epochs(config, budget, pool, at):
    from .policy_publication import canonical_global, digest

    local = local_scope(config, scope_of(pool))
    if not config.provisioning_requested:
        return Capacity.DISABLED
    if local is None or not has_creation_authority(config.policy, local):
        return Capacity.POLICY_UNCONFIGURED
    scope_epoch = matching_scope_epoch(pool, local)
    global_epoch = budget.current_epoch
    limit = next(entry for entry in config.policy.creation_budgets if entry.provider == pool.provider)
    if (
        scope_epoch is None or global_epoch is None or global_epoch.budget_id != budget.pk
        or global_epoch.digest != digest(canonical_global(limit))
        or global_epoch.create_per_hour != limit.create_per_hour
        or global_epoch.create_per_day != limit.create_per_day
        or pool.latest_complete_scan_id is None or pool.inventory_valid_until is None
        or at >= pool.inventory_valid_until
        or pool.latest_complete_scan.scope_epoch_id != scope_epoch.pk
        or pool.latest_complete_scan.state != ScanState.COMPLETE
        or pool.latest_complete_scan.pool_id != pool.pk
    ):
        return Capacity.POLICY_UNCONFIGURED
    return global_epoch, scope_epoch, local


def capacity_refusal(config, budget, pool, at, *, additional_claims, additional_creates):
    epochs = create_epochs(config, budget, pool, at)
    if isinstance(epochs, Capacity):
        return epochs
    global_epoch, _, local = epochs
    occupied = (
        ProviderExternalResource.objects.filter(pool=pool, count_state=ResourceCountState.COUNTED).count()
        + ProviderResourceClaim.objects.filter(pool=pool, state=ClaimState.HELD).count()
    )
    if occupied + additional_claims > local.resource_capacity - local.resource_reserve:
        return Capacity.RESOURCE_CAPACITY
    held = Q(state=AllowanceState.HELD)
    dispatched = Q(state=AllowanceState.DISPATCHED)
    daily = held | (dispatched & Q(dispatched_at__gt=at - timedelta(days=1)))
    hourly = held | (dispatched & Q(dispatched_at__gt=at - timedelta(hours=1)))
    parent = Q(stage__claim__pool=pool)
    totals = ProviderCreateAllowance.objects.filter(stage__claim__pool__budget=budget).filter(daily).aggregate(
        global_day=Count("pk", filter=daily), parent_day=Count("pk", filter=daily & parent),
        global_hour=Count("pk", filter=hourly), parent_hour=Count("pk", filter=hourly & parent),
    )
    if (totals["global_day"] + additional_creates > global_epoch.create_per_day
            or totals["parent_day"] + additional_creates > local.create_per_day):
        return Capacity.DAILY_CREATE_LIMIT
    if (totals["global_hour"] + additional_creates > global_epoch.create_per_hour
            or totals["parent_hour"] + additional_creates > local.create_per_hour):
        return Capacity.HOURLY_CREATE_LIMIT
    return None


def enqueue(pool_id, kind, at, *, mapping_id=None, attempt=None, scan=None, due=None):
    if kind == OutboxKind.PROVISION:
        subject, requested = {"mapping_id": mapping_id}, {}
    elif kind == OutboxKind.RECOVER:
        subject = {"attempt_id": attempt.pk}
        requested = {
            "mapping_id": mapping_id, "requested_recovery_round": attempt.recovery_round,
            "requested_collection": attempt.recovery_collection,
            "requested_page_number": attempt.recovery_page_number, "requested_cursor": attempt.recovery_cursor,
        }
    else:
        subject = {"scan_id": scan.pk}
        requested = {"requested_page_number": scan.page_number, "requested_cursor": scan.cursor}
    rows = ProviderProvisioningOutbox.objects.filter(kind=kind, **subject)
    row = rows.select_for_update().filter(state__in=LIVE_OUTBOX).first()
    if row:
        return row
    generation = (rows.aggregate(value=Max("generation"))["value"] or 0) + 1
    return ProviderProvisioningOutbox.objects.create(
        pool_id=pool_id, kind=kind, state=OutboxState.PENDING, generation=generation,
        created_at=at, updated_at=at, available_at=at if due is None else due,
        **subject, **requested,
    )


def cancel_outboxes(rows, at):
    for row in rows.select_for_update().filter(state__in=LIVE_OUTBOX).order_by("pk"):
        mutate(row, at, state=OutboxState.CANCELLED, lease_id=None, lease_until=None)


def queue_scan(pool, at):
    scan = ProviderInventoryScan.objects.create(
        pool=pool, scope_epoch_id=pool.current_epoch_id, state=ScanState.PARTIAL,
        started_at=at, created_at=at, updated_at=at,
    )
    enqueue(pool.pk, OutboxKind.INVENTORY_PAGE, at, scan=scan)
    return scan


def observe_resource(pool, external_id, at, *, restore=True):
    resource_scope = pool.parent_scope_id if pool.provider == "deepgram" else "organization-project"
    resource, created = ProviderExternalResource.objects.select_for_update().get_or_create(
        provider=pool.provider, resource_scope_id=resource_scope, external_id=external_id,
        defaults={
            "pool_id": pool.pk, "count_state": ResourceCountState.COUNTED,
            "first_seen_at": at, "last_seen_at": at, "created_at": at, "updated_at": at,
        },
    )
    if resource.pool_id != pool.pk:
        raise ProvisioningRejected(Error.IDENTITY_CONFLICT)
    if not created and (resource.count_state != ResourceCountState.EXCLUDED or restore):
        restored = resource.count_state == ResourceCountState.EXCLUDED
        mutate(resource, at, last_seen_at=max(at, resource.last_seen_at), count_state=ResourceCountState.COUNTED,
               exclusion_evidence_id=None)
        if restored:
            audit_event("RECOVERY", resource.pk, at, worker_audit("counted-positive-observation"))
    return resource
