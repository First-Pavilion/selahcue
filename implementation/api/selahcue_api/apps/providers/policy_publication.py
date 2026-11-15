"""Content-addressed publication of initialized, role-local provider policy."""
import hashlib
import json
from decimal import Decimal

from django.utils import timezone

from selahcue_api.apps.license_keys.selection import aware_utc

from .capacity import atomic, audit_event, cancel_outboxes, mutate, queue_scan, validate_audit, worker_configuration
from .configuration import PARENT_FIELDS, _policy_scope, valid_evidence
from .contracts import (
    CleanupAuthorization, PolicyPublicationResult, ProvisioningErrorCode, ProvisioningRejected, ScanState,
)
from .models import (
    GlobalPolicyEpoch, ProviderCapacityPool, ProviderGlobalBudget, ProviderInventoryScan,
    ProviderProvisioningOutbox, ScopePolicyEpoch,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def _decimal_string(value: Decimal | None):
    if value is None:
        return None
    if value.is_zero():
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def canonical_global(budget):
    return canonical({"schema_version": 1, "provider": budget.provider,
                      "create_per_hour": budget.create_per_hour, "create_per_day": budget.create_per_day})


def canonical_scope(scope_policy):
    return canonical({
        "schema_version": 1, "provider": scope_policy.scope.provider,
        "parent_scope_id": scope_policy.scope.parent_scope_id,
        "resource_capacity": scope_policy.resource_capacity, "resource_reserve": scope_policy.resource_reserve,
        "create_per_hour": scope_policy.create_per_hour, "create_per_day": scope_policy.create_per_day,
        "capacity_evidence_ref": scope_policy.capacity_evidence_ref,
        "controls_evidence_ref": scope_policy.controls_evidence_ref,
        "unattributed_usage_threshold": _decimal_string(scope_policy.unattributed_usage_threshold),
        "stream_concurrency_capacity": scope_policy.stream_concurrency_capacity,
        "notes_policy_id": scope_policy.notes_policy_id,
        "notes_daily_budget_usd": _decimal_string(scope_policy.notes_daily_budget_usd),
    })


def decode_scope(value):
    # The mounted policy's strict parser owns validation of public scope values.
    from .contracts import ProviderConfigurationError

    try:
        provider = value["provider"]
        parent = PARENT_FIELDS[provider]
        raw = {key: item for key, item in value.items()
               if key not in ("provider", "schema_version", "parent_scope_id") and item is not None}
        raw[parent] = value["parent_scope_id"]
        parsed = _policy_scope(provider, parent, raw)
        if canonical(value) == canonical_scope(parsed):
            return parsed
    except (AttributeError, KeyError, TypeError, ValueError, ProviderConfigurationError):
        pass
    raise ProvisioningRejected(ProvisioningErrorCode.POLICY_MISMATCH)


def publish_provider_policy(*, cleanup_authorizations: tuple[CleanupAuthorization, ...],
                            audit, clock=timezone.now) -> PolicyPublicationResult:
    config = worker_configuration(operator=True)
    validate_audit(audit)
    scopes = config.policy.scopes if config.policy else ()
    budgets = {row.provider: row for row in config.policy.creation_budgets} if config.policy else {}
    references = {}
    if type(cleanup_authorizations) is not tuple:
        raise ProvisioningRejected(ProvisioningErrorCode.INVALID_CONTEXT)
    for entry in cleanup_authorizations:
        if (
            type(entry) is not CleanupAuthorization or entry.scope not in {row.scope for row in scopes}
            or entry.scope in references or not valid_evidence(entry.evidence_ref)
        ):
            raise ProvisioningRejected(ProvisioningErrorCode.INVALID_CONTEXT)
        references[entry.scope] = entry.evidence_ref

    global_epochs, scope_epochs = [], []
    for provider in sorted({row.scope.provider for row in scopes} | budgets.keys()):
        local = sorted((row for row in scopes if row.scope.provider == provider), key=lambda row: row.scope.parent_scope_id)
        with atomic():
            # get_or_create handles the unique-constraint race. Initial creation has no pre-existing row to lock.
            budget = ProviderGlobalBudget.objects.select_for_update().filter(provider=provider).first()
            if budget is None:
                at = aware_utc(clock())
                budget, _ = ProviderGlobalBudget.objects.get_or_create(
                    provider=provider, defaults={"created_at": at, "updated_at": at},
                )
                budget = ProviderGlobalBudget.objects.select_for_update().get(pk=budget.pk)
            pools = {pool.parent_scope_id: pool for pool in ProviderCapacityPool.objects.select_for_update().filter(
                budget=budget, parent_scope_id__in=[row.scope.parent_scope_id for row in local],
            ).order_by("provider", "parent_scope_id")}
            at = aware_utc(clock())
            evidence = {"published_by": audit.operator_id, "request_id": audit.request_id,
                        "evidence_ref": audit.evidence_ref, "created_at": at}

            if provider in budgets:
                configured = budgets[provider]
                hash_value = digest(canonical_global(configured))
                epoch, _ = GlobalPolicyEpoch.objects.get_or_create(
                    budget=budget, digest=hash_value, defaults={
                        **evidence, "create_per_hour": configured.create_per_hour, "create_per_day": configured.create_per_day,
                    },
                )
                if (epoch.create_per_hour, epoch.create_per_day) != (configured.create_per_hour, configured.create_per_day):
                    raise ProvisioningRejected(ProvisioningErrorCode.POLICY_MISMATCH)
                global_epochs.append(epoch.pk)
                if budget.current_epoch_id != epoch.pk:
                    old = budget.current_epoch
                    mutate(budget, at, current_epoch_id=epoch.pk)
                    _record_change(budget.pk, old, epoch, at, audit)

            for policy in local:
                parent = policy.scope.parent_scope_id
                pool = pools.get(parent)
                if pool is None:
                    pool = ProviderCapacityPool.objects.create(
                        provider=provider, parent_scope_id=parent, budget=budget, created_at=at, updated_at=at,
                    )
                body = canonical_scope(policy)
                hash_value = digest(body)
                reference = references.get(policy.scope)
                publication = {"scope_digest": hash_value, "cleanup_authorized": reference is not None,
                               "cleanup_evidence_ref": reference}
                epoch, _ = ScopePolicyEpoch.objects.get_or_create(
                    pool=pool, publication_digest=digest(canonical(publication)), defaults={
                        **evidence, "digest": hash_value, "policy": json.loads(body),
                        "cleanup_authorized": reference is not None, "cleanup_evidence_ref": reference,
                    },
                )
                if (
                    epoch.digest != hash_value or decode_scope(epoch.policy) != policy
                    or epoch.cleanup_authorized != (reference is not None)
                    or epoch.cleanup_evidence_ref != reference
                ):
                    raise ProvisioningRejected(ProvisioningErrorCode.POLICY_MISMATCH)
                scope_epochs.append(epoch.pk)
                if pool.current_epoch_id == epoch.pk:
                    continue
                partial = ProviderInventoryScan.objects.select_for_update().filter(pool=pool, state=ScanState.PARTIAL).first()
                if partial:
                    at = aware_utc(clock())
                    mutate(partial, at, state=ScanState.FAILED, finished_at=at, lease_id=None, lease_until=None,
                           error_code=ProvisioningErrorCode.POLICY_MISMATCH)
                    cancel_outboxes(ProviderProvisioningOutbox.objects.filter(scan=partial), at)
                old = pool.current_epoch
                mutate(pool, at, current_epoch_id=epoch.pk, latest_complete_scan_id=None, inventory_valid_until=None)
                queue_scan(pool, at)
                _record_change(pool.pk, old, epoch, at, audit)
    return PolicyPublicationResult(tuple(global_epochs), tuple(scope_epochs))


def _record_change(target, old, epoch, at, audit):
    audit_event("POLICY_PUBLISH", target, at, audit, old_epoch_id=str(old.pk) if old else None,
                old_policy_digest=old.digest if old else None, new_epoch_id=str(epoch.pk), policy_digest=epoch.digest)
