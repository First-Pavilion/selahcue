"""Demand admission and durable provider provisioning transitions."""
import logging
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from django.db import connection
from django.db.models import Q

from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.devices.cloud_eligibility import CloudEligibilityFacts, cloud_eligibility
from selahcue_api.apps.devices.models import Device, DeviceToken
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.apps.license_keys.selection import aware_utc
from selahcue_api.apps.usage.contracts import CloudContext
from selahcue_api.apps.usage.services import remaining

from . import registry
from .bootstrap import get_initialized_provider_entrypoint
from .capacity import (
    LEASE, LIVE_OUTBOX, POLL, atomic, audit_event, cancel_outboxes, capacity_refusal, close_database,
    create_epochs, enqueue, local_credential, local_scope, lock_budget_pools, matching_scope_epoch,
    mutate, observe_resource, positive_id, scope_of, validate_audit, worker_audit, worker_configuration,
)
from .configuration import get_provider_configuration, valid_id
from .contracts import (
    AdminOperation as Op, AllowanceState, AttemptState, CapacityUnavailable, CapacityUnavailableCode as Capacity,
    ChainState, ClaimState, CLEANUP_OPS, CREATE_OPS, Clock, OutboxKind, OutboxState, ProviderMappingState,
    ProviderPartialIdentity, ProviderScope, ProvisioningErrorCode as Error, ProvisioningPending,
    ProvisioningRejected, ProvisioningResult, ReadyMapping, RecoveryCollection, RecoveryEvidenceKind,
    RecoveryResult, RegistryAuditContext, RegistryReason, ResourceCountState, StageState,
)
from .models import (
    OWNING_STATES, ProviderCapacityPool, ProviderCreateAllowance, ProviderCredential,
    ProviderExternalResource, ProviderGlobalBudget, ProviderProvisioningOutbox, ProviderRecoveryEvidence,
    ProviderResourceClaim, ProvisioningAttempt, ProvisioningDemand, ProvisioningStage,
)
from .policy_publication import canonical, digest

INTENT_ACTOR = "provider-provisioning-intent"
METER_PROVIDER = {"stt": "deepgram", "notes": "openai"}
MARKER_SUFFIX = {
    Op.DG_CREATE_KEY: "dgkey", Op.OA_CREATE_PROJECT: "oaproj", Op.OA_CREATE_SERVICE_ACCOUNT_KEY: "oasvc",
    Op.DG_REVOKE_KEY: "dgrevoke", Op.OA_REVOKE_KEY: "oakeydel", Op.OA_DELETE_SERVICE_ACCOUNT: "oasvcdel",
    Op.OA_ARCHIVE_PROJECT: "oaarchive",
}
CREATE_STAGES = {"deepgram": (Op.DG_CREATE_KEY,), "openai": (Op.OA_CREATE_PROJECT, Op.OA_CREATE_SERVICE_ACCOUNT_KEY)}
CHAIN_TERMINAL = (ChainState.READY, ChainState.FAILED, ChainState.RETIRED)
ATTEMPT_TERMINAL = (AttemptState.SUCCEEDED, AttemptState.CANCELLED, AttemptState.DEFINITE_FAILURE)
UNKNOWN_STATES = (AttemptState.OUTCOME_UNKNOWN, AttemptState.RECOVERING, AttemptState.OPERATOR_REQUIRED)
ROUND_DELAYS = (5, 30, 120)
logger = logging.getLogger(__name__)


def _refuse(code):
    raise ProvisioningRejected(code)


def _require_outer():
    if connection.in_atomic_block or not connection.get_autocommit():
        _refuse(Error.INVALID_CONTEXT)


def _locked(model, ident, *, fields=()):
    query = model.objects.select_for_update()
    if fields:
        query = query.only(*fields)
    return query.filter(pk=ident).first()


def _lock_original(org_id, license_id, device_id, token_id):
    org = _locked(CustomerOrg, org_id)
    key = _locked(AppLicenseKey, license_id, fields=("customer_id", "status", "starts_at", "expires_at"))
    device = _locked(Device, device_id, fields=("customer_id", "license_key_id", "status"))
    token = _locked(DeviceToken, token_id, fields=("device_id", "status", "issued_at", "expires_at"))
    return org, key, device, token


def _eligibility(rows, meter, at):
    org, key, device, token = rows
    if not all(rows):
        return Error.INELIGIBLE
    facts = CloudEligibilityFacts(
        org.pk, org.status, key.pk, key.customer_id, key.status, key.starts_at, key.expires_at,
        device.pk, device.customer_id, device.license_key_id, device.status,
        token.pk, token.device_id, token.status, token.issued_at, token.expires_at,
    )
    if not cloud_eligibility(facts, at=at):
        return Error.INELIGIBLE
    minimum = 300 if meter == "stt" else 1
    if not any(row.meter == meter and row.remaining >= minimum for row in remaining(org, at)):
        return Error.ALLOWANCE_UNAVAILABLE
    return None


def _registry_audit(reason, ref, *, actor="provider-provisioning-worker"):
    return RegistryAuditContext(actor, uuid4(), reason, ref)


def _scope(mapping):
    return ProviderScope(mapping.provider, mapping.parent_scope_id)


def _choose_pool(config, budget, pools, provider, at):
    if not config.provisioning_requested:
        return Capacity.DISABLED
    configured = {row.scope.parent_scope_id for row in config.policy.scopes if row.scope.provider == provider}
    published = {pool.parent_scope_id for pool in pools}
    refusals = [Capacity.POLICY_UNCONFIGURED] if configured - published else []
    for pool in pools:
        refusal = capacity_refusal(config, budget, pool, at, additional_claims=1,
                                   additional_creates=len(CREATE_STAGES[provider]))
        if refusal is None:
            return pool
        refusals.append(refusal)
    return next((code for code in Capacity if code in refusals), Capacity.POLICY_UNCONFIGURED)


def _target(stage):
    return stage.target_project_id, stage.target_service_account_id, stage.target_api_key_id


def _identity_tuple(identity):
    return identity.project_id, identity.service_account_id, identity.api_key_id


def _registry_identity(mapping):
    return (mapping.external_project_id, mapping.external_service_account_id, mapping.external_api_key_id)


def _prepare(mapping, pool, stage, at):
    operation = stage.operation
    request_digest = digest(canonical({
        "operation": operation, "provider": pool.provider, "parent_scope_id": pool.parent_scope_id,
        "mapping_id": str(mapping.pk), "marker": stage.marker,
        "project_id": stage.target_project_id, "service_account_id": stage.target_service_account_id,
        "api_key_id": stage.target_api_key_id,
    }))
    attempt = ProvisioningAttempt.objects.create(
        stage=stage, sequence=stage.attempt_count + 1, state=AttemptState.PREPARED,
        request_digest=request_digest, next_action_at=at, recovery_collection=RecoveryCollection.NONE,
        created_at=at, updated_at=at,
    )
    mutate(stage, at, current_attempt_id=attempt.pk, attempt_count=attempt.sequence)
    return attempt


def _new_stage(claim, op, at, *, state=StageState.READY, target=(None, None, None), evidence=None):
    return ProvisioningStage.objects.create(
        claim=claim, operation=op, state=state, marker=f"scp1-{claim.mapping_id}-{MARKER_SUFFIX[op]}",
        target_project_id=target[0], target_service_account_id=target[1], target_api_key_id=target[2],
        ownership_evidence=evidence, created_at=at, updated_at=at,
    )


def _hold(stage, at):
    return ProviderCreateAllowance.objects.create(
        stage=stage, state=AllowanceState.HELD, created_at=at, updated_at=at,
    )


def _allocate(config, demand, pool, at, *, previous=None):
    scope = scope_of(pool)
    evidence_ref = local_scope(config, scope).controls_evidence_ref
    snapshot = registry.begin_mapping(
        mapping_id=uuid4(), org_id=demand.org_id, scope=scope, now=at,
        audit=_registry_audit(RegistryReason.PROVISION_INTENT, evidence_ref, actor=INTENT_ACTOR),
    )
    mapping_id = snapshot.mapping_id
    claim = ProviderResourceClaim.objects.create(
        demand=demand, mapping_id=mapping_id, pool=pool, slot=pool.next_slot, generation=int(previous is not None),
        previous_claim=previous, state=ClaimState.HELD, created_at=at, updated_at=at,
    )
    mutate(pool, at, next_slot=pool.next_slot + 1)
    for index, operation in enumerate(CREATE_STAGES[pool.provider]):
        target = (scope.parent_scope_id, None, None) if pool.provider == "deepgram" else (None, None, None)
        stage = _new_stage(claim, operation, at, state=StageState.BLOCKED if index else StageState.READY, target=target)
        _hold(stage, at)
        if index == 0:
            _prepare(ProviderCredential(pk=mapping_id), pool, stage, at)
    mutate(demand, at, current_mapping_id=mapping_id, state=ChainState.QUEUED,
           replacement_count=claim.generation, last_error_code=None)
    enqueue(pool.pk, OutboxKind.PROVISION, at, mapping_id=mapping_id)
    audit_event("REPLACEMENT" if previous else "INTENT", mapping_id, at,
                worker_audit(evidence_ref), generation=claim.generation, capacity_slot=claim.slot)
    return mapping_id


def ensure_provider_ready(context: CloudContext, *, authenticated_token_id: int,
                          clock: Clock = timezone.now) -> ReadyMapping | ProvisioningPending | CapacityUnavailable:
    config = get_provider_configuration(required_role="web")
    _require_outer()
    if (
        get_initialized_provider_entrypoint() not in ("wsgi", "asgi") or type(context) is not CloudContext
        or not all(positive_id(value) for value in (context.org_id, context.license_id, context.device_id,
                                                     authenticated_token_id))
        or type(context.meter) is not str or context.meter not in METER_PROVIDER
        or not isinstance(context.policy_version, str) or not 0 < len(context.policy_version) <= 64
        or "\x00" in context.policy_version
        or context.provider_mapping_id is not None and type(context.provider_mapping_id) is not UUID
    ):
        _refuse(Error.INVALID_CONTEXT)
    provider = METER_PROVIDER[context.meter]
    parents = [row.scope.parent_scope_id for row in config.policy.scopes if row.scope.provider == provider] if config.policy else []
    with atomic():
        original = _lock_original(context.org_id, context.license_id, context.device_id, authenticated_token_id)
        org, key, device, token = original
        if org is None or key is None or device is None:
            _refuse(Error.INVALID_CONTEXT)
        if (key.customer_id != org.pk or device.customer_id != org.pk or device.license_key_id != key.pk
                or (token is not None and token.device_id != device.pk)):
            _refuse(Error.INVALID_CONTEXT)
        demands = ProvisioningDemand.objects.filter(org_id=org.pk, provider=provider)
        owners = ProviderCredential.objects.filter(org_id=org.pk, provider=provider, state__in=OWNING_STATES)
        # The org lock serializes all registry and demand writers. Reusing an
        # owner does not depend on publication, inventory or a global lock.
        budget, pools = (None, []) if owners.exists() or demands.exists() else lock_budget_pools(provider, parents)
        demand = demands.select_for_update().first()
        owner = owners.select_for_update().only("org_id", "provider", "parent_scope_id", "state").first()
        at = aware_utc(clock())
        if context.provider_mapping_id is not None and context.provider_mapping_id != (
            owner.pk if owner else demand.current_mapping_id if demand else None
        ):
            _refuse(Error.INVALID_CONTEXT)
        ineligible = _eligibility(original, context.meter, at)
        if ineligible:
            _refuse(ineligible)
        if provider not in config.requested_public_providers:
            return CapacityUnavailable(Capacity.DISABLED)
        if owner is not None:
            if local_scope(config, _scope(owner)) is None:
                return CapacityUnavailable(Capacity.POLICY_UNCONFIGURED)
            if owner.state == ProviderMappingState.ACTIVE:
                return ReadyMapping(owner.pk, owner.org_id, provider)
        if demand is not None and demand.state in (ChainState.FAILED, ChainState.RETIRED):
            _refuse(Error.OPERATOR_REQUIRED)
        if owner is not None:
            return ProvisioningPending(owner.pk)
        if demand is not None:
            if demand.state != ChainState.WAITING_CAPACITY or demand.current_mapping_id is None:
                _refuse(Error.OPERATOR_REQUIRED)
            return ProvisioningPending(demand.current_mapping_id)
        choice = _choose_pool(config, budget, pools, provider, at)
        if isinstance(choice, Capacity):
            return CapacityUnavailable(choice)
        demand = ProvisioningDemand.objects.create(
            org=org, provider=provider, trigger_license=key, trigger_device=device, trigger_token_pk=authenticated_token_id,
            meter=context.meter, policy_version=context.policy_version, state=ChainState.QUEUED,
            created_at=at, updated_at=at,
        )
        return ProvisioningPending(_allocate(config, demand, choice, at))


@dataclass
class _Chain:
    original: tuple | None
    budget: ProviderGlobalBudget
    pools: list
    pool: ProviderCapacityPool
    demand: ProvisioningDemand
    mapping: ProviderCredential
    claim: ProviderResourceClaim
    stages: list
    attempts: dict
    allowances: list


def _lock_chain(mapping_id, config, *, original=True, all_parents=False):
    refs = ProviderResourceClaim.objects.filter(mapping_id=mapping_id).values(
        "pk", "pool_id", "pool__parent_scope_id", "demand_id", "demand__provider", "demand__org_id",
        "demand__trigger_license_id", "demand__trigger_device_id", "demand__trigger_token_pk",
    ).first()
    if refs is None:
        _refuse(Error.INVALID_CONTEXT)
    org_id = refs["demand__org_id"]
    facts = None
    if original:
        facts = _lock_original(org_id, refs["demand__trigger_license_id"], refs["demand__trigger_device_id"],
                               refs["demand__trigger_token_pk"])
    else:
        _locked(CustomerOrg, org_id)
    provider = refs["demand__provider"]
    parents = {refs["pool__parent_scope_id"]}
    if all_parents and config.policy:
        parents.update(row.scope.parent_scope_id for row in config.policy.scopes if row.scope.provider == provider)
    budget, pools = lock_budget_pools(provider, parents)
    pool = next((entry for entry in pools if entry.pk == refs["pool_id"]), None)
    demand = _locked(ProvisioningDemand, refs["demand_id"])
    mapping = _locked(ProviderCredential, mapping_id)
    claim = _locked(ProviderResourceClaim, refs["pk"])
    if (
        not all((budget, pool, demand, mapping, claim)) or demand.org_id != mapping.org_id
        or demand.provider != mapping.provider or _scope(mapping) != scope_of(pool)
        or claim.demand_id != demand.pk or claim.pool_id != pool.pk or claim.mapping_id != mapping.pk
        or local_scope(config, scope_of(pool)) is None
    ):
        _refuse(Error.INVALID_CONTEXT)
    stages = list(ProvisioningStage.objects.select_for_update().filter(claim=claim).order_by("pk"))
    attempts = {row.pk: row for row in ProvisioningAttempt.objects.select_for_update().filter(
        stage_id__in=[stage.pk for stage in stages],
    ).order_by("pk")}
    allowances = list(ProviderCreateAllowance.objects.select_for_update().filter(
        stage_id__in=[stage.pk for stage in stages],
    ).order_by("pk"))
    # Existing publications can be in flight independently of the chain.
    # Lock their rows before sampling the transaction's decision instant.
    list(ProviderProvisioningOutbox.objects.select_for_update().filter(
        mapping_id=mapping.pk, state__in=LIVE_OUTBOX,
    ).order_by("pk").values_list("pk", flat=True))
    return _Chain(facts, budget, pools, pool, demand, mapping, claim, stages, attempts, allowances)


def _result(chain):
    state = ChainState(chain.demand.state)
    return ProvisioningResult(chain.mapping.pk, state, None if state in CHAIN_TERMINAL else 5)


def _recovery_result(attempt):
    state = AttemptState(attempt.state)
    return RecoveryResult(attempt.pk, state, state == AttemptState.OPERATOR_REQUIRED)


def _chain_change(chain, at, state, error=None):
    mutate(chain.demand, at, state=state, last_error_code=error)


def _refuse_create(chain, at, code):
    # Retain dispatched allowances and counted projects; only unsent work can be cancelled.
    for stage in chain.stages:
        attempt = chain.attempts.get(stage.current_attempt_id)
        if attempt is not None and attempt.state == AttemptState.PREPARED:
            mutate(attempt, at, state=AttemptState.CANCELLED, completed_at=at, next_action_at=None, error_code=code)
        if stage.operation in CREATE_OPS and stage.state == StageState.READY:
            mutate(stage, at, state=StageState.CANCELLED)
    for allowance in chain.allowances:
        if allowance.state == AllowanceState.HELD:
            mutate(allowance, at, state=AllowanceState.RELEASED, released_at=at)
    if chain.claim.state == ClaimState.COUNTED:
        _chain_change(chain, at, ChainState.RECOVERY_REQUIRED, Error.SECRET_LOST)
    else:
        unsent = not any(attempt.dispatch_started_at for attempt in chain.attempts.values())
        if unsent:
            evidence = _evidence(chain, None, RecoveryEvidenceKind.LOCAL_NOT_SENT, _registry_identity(chain.mapping),
                                 worker_audit("original-demand-cancelled-before-dispatch"), at)
            _release_claim(chain, evidence, at)
            _fail_registry(chain, at)
        _chain_change(chain, at, ChainState.FAILED, code)


def _fail_registry(chain, at):
    if chain.mapping.state == ProviderMappingState.PROVISIONING:
        registry.fail_mapping(mapping_id=chain.mapping.pk, expected_revision=chain.mapping.revision, now=at,
                              audit=_registry_audit(RegistryReason.DEFINITE_FAILURE, "proved-noncreation"))


def _release_claim(chain, evidence, at):
    mutate(chain.claim, at, state=ClaimState.RELEASED, released_at=at, release_evidence_id=evidence.pk)
    audit_event("CAPACITY_RELEASE", chain.claim.pk, at, worker_audit(evidence.evidence_ref))


def _evidence(chain, attempt, kind, identity, audit, at, *, operation=None):
    return ProviderRecoveryEvidence.objects.create(
        pool=chain.pool, mapping=chain.mapping, attempt=attempt, kind=kind, operation=operation,
        project_id=identity[0], service_account_id=identity[1], api_key_id=identity[2],
        operator_id=audit.operator_id, request_id=audit.request_id, evidence_ref=audit.evidence_ref,
        observed_at=at, created_at=at,
    )


def _adapter(provider):
    from .adapters import deepgram_admin, openai_admin
    return deepgram_admin if provider == "deepgram" else openai_admin


def _work_delivery(outbox_id, chain, kind, attempt=None):
    if outbox_id is None:
        return None
    row = _locked(ProviderProvisioningOutbox, outbox_id)
    if row is None or row.state not in (OutboxState.PUBLISHING, OutboxState.SENT):
        return False
    if (row.kind != kind or row.mapping_id != chain.mapping.pk or row.pool_id != chain.pool.pk
            or (attempt is not None and row.attempt_id != attempt.pk)):
        return row, False
    if attempt is not None and (
        row.requested_recovery_round, row.requested_collection, row.requested_page_number, row.requested_cursor,
    ) != (
        attempt.recovery_round, attempt.recovery_collection, attempt.recovery_page_number, attempt.recovery_cursor,
    ):
        return row, False
    return row, True


def _accept_delivery(delivery, at):
    if delivery is None:
        return True
    if delivery is False:
        return False
    row, matches = delivery
    if not matches:
        mutate(row, at, state=OutboxState.CANCELLED, lease_id=None, lease_until=None, error_code=Error.INTERNAL_FAILURE)
        audit_event("OUTBOX_FAILURE", row.pk, at, worker_audit("invalid-outbox-subject"), error_code=Error.INTERNAL_FAILURE)
        return False
    mutate(row, at, state=OutboxState.ACKED, lease_id=None, lease_until=None, acked_at=at)
    return True


def _stages_in_order(chain):
    operations = chain.claim.cleanup_required_operations or CREATE_STAGES[chain.pool.provider]
    return [next(stage for stage in chain.stages if stage.operation == operation) for operation in operations]


def _next_stage(chain):
    return next((stage for stage in _stages_in_order(chain) if stage.state not in (StageState.DONE, StageState.CANCELLED)), None)


def _next_provision(chain, at, *, due=None):
    enqueue(chain.pool.pk, OutboxKind.PROVISION, at, mapping_id=chain.mapping.pk, due=due)


def _next_recovery(chain, attempt, at):
    enqueue(chain.pool.pk, OutboxKind.RECOVER, at, mapping_id=chain.mapping.pk,
            attempt=attempt, due=attempt.next_action_at)


def _mark_unknown(chain, attempt, at, code):
    unknown_since = attempt.unknown_since or at
    due = max(at, unknown_since + timedelta(seconds=ROUND_DELAYS[min(attempt.recovery_round, 2)]))
    mutate(attempt, at, state=AttemptState.OUTCOME_UNKNOWN, lease_id=None, lease_until=None,
           unknown_since=unknown_since, next_action_at=due, error_code=code,
           recovery_scan_started_at=None)
    if chain.demand.state in (ChainState.QUEUED, ChainState.WORKING):
        _chain_change(chain, at, ChainState.RECOVERY_REQUIRED, code)
    _next_recovery(chain, attempt, at)


def _expire_attempt(chain, attempt, at):
    if attempt.state in (AttemptState.DISPATCHED, AttemptState.RECOVERING) and attempt.lease_until is not None:
        if attempt.lease_until <= at:
            cancel_outboxes(ProviderProvisioningOutbox.objects.filter(attempt=attempt), at)
            _mark_unknown(chain, attempt, at, Error.OUTCOME_UNKNOWN)
            if attempt.recovery_round >= 3:
                _operator_required(chain, _stage_by_attempt(chain, attempt), attempt, at)
        return True
    return False


def _replacement(chain, config, at):
    if chain.claim.generation != 0 or chain.demand.replacement_count != 0:
        _refuse(Error.IDENTITY_CONFLICT)
    if chain.mapping.state != ProviderMappingState.RETIRED or not _cleanup_complete(chain):
        _refuse(Error.IDENTITY_CONFLICT)
    ineligible = _eligibility(chain.original, chain.demand.meter, at)
    if ineligible == Error.INELIGIBLE:
        _chain_change(chain, at, ChainState.FAILED, ineligible)
        return _result(chain)
    if ineligible or chain.pool.provider not in config.requested_public_providers:
        _next_provision(chain, at, due=at + POLL)
        return _result(chain)
    choice = _choose_pool(config, chain.budget, chain.pools, chain.pool.provider, at)
    if isinstance(choice, Capacity):
        _next_provision(chain, at, due=at + POLL)
        return _result(chain)
    mapping_id = _allocate(config, chain.demand, choice, at, previous=chain.claim)
    return ProvisioningResult(mapping_id, ChainState.QUEUED, 5)


def provision_mapping(mapping_id: UUID, *, clock: Clock = timezone.now) -> ProvisioningResult:
    return _provision_mapping(mapping_id, clock=clock, outbox_id=None, enough_time=lambda: True)


def _provision_mapping(mapping_id, *, clock, outbox_id, enough_time):
    from .adapters.contracts import AdminRequest

    config = worker_configuration()
    _require_outer()
    if type(mapping_id) is not UUID:
        _refuse(Error.INVALID_CONTEXT)
    with atomic():
        chain = _lock_chain(mapping_id, config, all_parents=True)
        delivery = _work_delivery(outbox_id, chain, OutboxKind.PROVISION)
        at = aware_utc(clock())
        if not _accept_delivery(delivery, at):
            return _result(chain)
        if outbox_id is None:
            cancel_outboxes(ProviderProvisioningOutbox.objects.filter(kind=OutboxKind.PROVISION, mapping_id=mapping_id), at)
        if chain.demand.current_mapping_id != mapping_id or chain.demand.state in CHAIN_TERMINAL:
            return _result(chain)
        if chain.demand.state == ChainState.WAITING_CAPACITY:
            return _replacement(chain, config, at)
        stage = _next_stage(chain)
        if stage is None:
            if chain.claim.cleanup_started_at is not None:
                finish_cleanup_locked(chain.claim.pk, at=at)
                chain.demand.refresh_from_db()
            elif chain.demand.state == ChainState.WORKING:
                _chain_change(chain, at, ChainState.RECOVERY_REQUIRED, Error.SECRET_LOST)
                _next_provision(chain, at)
            else:
                _start_cleanup(chain, config, at)
            return _result(chain)
        attempt = chain.attempts.get(stage.current_attempt_id)
        if attempt is not None and _expire_attempt(chain, attempt, at):
            return _result(chain)
        if stage.state == StageState.WORKING or (
            attempt is not None and attempt.state in UNKNOWN_STATES
        ):
            return _result(chain)
        if stage.state == StageState.BLOCKED:
            if chain.demand.state == ChainState.RECOVERY_REQUIRED and attempt is not None and (
                attempt.state == AttemptState.DEFINITE_FAILURE and chain.claim.cleanup_started_at is None
            ):
                _start_cleanup(chain, config, at)
            return _result(chain)
        create = stage.operation in CREATE_OPS
        scope = scope_of(chain.pool)
        credential = local_credential(config, scope)
        if credential is None:
            _refuse(Error.POLICY_MISMATCH)
        if create:
            eligibility = _eligibility(chain.original, chain.demand.meter, at)
            if eligibility == Error.INELIGIBLE:
                _refuse_create(chain, at, eligibility)
                if chain.demand.state == ChainState.RECOVERY_REQUIRED:
                    _next_provision(chain, at)
                return _result(chain)
            refusal = eligibility
            if scope.provider not in config.requested_public_providers:
                refusal = Capacity.DISABLED
            allowance = next((row for row in chain.allowances if row.stage_id == stage.pk and row.state == AllowanceState.HELD), None)
            refusal = refusal or capacity_refusal(
                config, chain.budget, chain.pool, at, additional_claims=0, additional_creates=int(allowance is None),
            )
            if refusal is not None or not enough_time():
                return _defer(chain, attempt, at)
            global_epoch, scope_epoch, _ = create_epochs(config, chain.budget, chain.pool, at)
            if allowance is None:
                allowance = _hold(stage, at)
        else:
            global_epoch = None
            scope_epoch = matching_scope_epoch(chain.pool, local_scope(config, scope))
            if scope_epoch is None or not scope_epoch.cleanup_authorized or not enough_time():
                return _defer(chain, attempt, at)
            _validate_cleanup_ownership(chain, stage)
        if attempt is not None and attempt.next_action_at is not None and at < attempt.next_action_at:
            _next_provision(chain, at, due=attempt.next_action_at)
            return _result(chain)
        if attempt is None or attempt.state == AttemptState.DEFINITE_FAILURE:
            attempt = _prepare(chain.mapping, chain.pool, stage, at)
        if attempt.state != AttemptState.PREPARED or attempt.next_action_at is not None and at < attempt.next_action_at:
            return _result(chain)
        lease_id = uuid4()
        mutate(attempt, at, state=AttemptState.DISPATCHED, lease_id=lease_id, lease_until=at + LEASE,
               dispatch_started_at=at, global_epoch_id=global_epoch.pk if global_epoch else None,
               scope_epoch_id=scope_epoch.pk, next_action_at=None)
        if create:
            mutate(allowance, at, state=AllowanceState.DISPATCHED, attempt_id=attempt.pk, dispatched_at=at)
        mutate(stage, at, state=StageState.WORKING)
        if create and chain.demand.state in (ChainState.QUEUED, ChainState.RECOVERY_REQUIRED):
            _chain_change(chain, at, ChainState.WORKING)
        request = AdminRequest(Op(stage.operation), scope, mapping_id, attempt.pk, stage.marker, *_target(stage))
        audit_event("DISPATCH", attempt.pk, at, worker_audit("leased-admin-operation"),
                    operation=stage.operation, sequence=attempt.sequence)
    if enough_time():
        close_database()
        receipt = _adapter(scope.provider).mutate(request, credential)
    else:
        from .adapters.contracts import MutationUnknown
        receipt = MutationUnknown(Error.OUTCOME_UNKNOWN, ProviderPartialIdentity(scope, *_target(stage)))
    return _finalize_mutation(config, request, lease_id, receipt, clock)


def _defer(chain, attempt, at):
    if attempt is not None and attempt.state == AttemptState.PREPARED:
        mutate(attempt, at, next_action_at=at + POLL)
    _next_provision(chain, at, due=at + POLL)
    return _result(chain)


def _stage_by_attempt(chain, attempt):
    return next(stage for stage in chain.stages if stage.pk == attempt.stage_id)


def _process_identity(chain, attempt, identity, at, *, created_at=None, provider_request_id=None):
    if identity.scope != scope_of(chain.pool):
        _refuse(Error.IDENTITY_CONFLICT)
    incoming = _identity_tuple(identity)
    observed_fields = ("observed_project_id", "observed_service_account_id", "observed_api_key_id")
    metadata = {}
    for field, value in zip(observed_fields, incoming, strict=True):
        old = getattr(attempt, field)
        if value is not None and (not valid_id(value) or old not in (None, value)):
            _refuse(Error.IDENTITY_CONFLICT)
        if value is not None and old is None:
            metadata[field] = value
    if provider_request_id is not None and attempt.provider_request_id is None and valid_id(provider_request_id):
        metadata["provider_request_id"] = provider_request_id
    if created_at is not None and attempt.observed_created_at is None:
        metadata["observed_created_at"] = created_at
    if metadata:
        mutate(attempt, at, **metadata)
    if _stage_by_attempt(chain, attempt).operation not in CREATE_OPS:
        return
    resource_id = identity.api_key_id if chain.pool.provider == "deepgram" else identity.project_id
    if resource_id:
        resource = observe_resource(
            chain.pool, resource_id, at,
            restore=chain.claim.state != ClaimState.RELEASED and attempt.state not in ATTEMPT_TERMINAL,
        )
        linked = ProviderResourceClaim.objects.filter(resource=resource).exclude(pk=chain.claim.pk).exists()
        if linked or chain.claim.resource_id not in (None, resource.pk) or chain.claim.state == ClaimState.RELEASED:
            audit_event("RECOVERY", attempt.pk, at, worker_audit("resource-identity-conflict"),
                        error_code=Error.IDENTITY_CONFLICT, state=attempt.state)
            if attempt.state in ATTEMPT_TERMINAL or chain.claim.state == ClaimState.RELEASED:
                return
            _refuse(Error.IDENTITY_CONFLICT)
        if chain.claim.state == ClaimState.HELD:
            mutate(chain.claim, at, state=ClaimState.COUNTED, resource_id=resource.pk)
    if chain.mapping.state == ProviderMappingState.PROVISIONING and any(incoming):
        snapshot = registry.bind_provisioning_identity(
            mapping_id=chain.mapping.pk, expected_revision=chain.mapping.revision, identity=identity, now=at,
            audit=_registry_audit(RegistryReason.PROVISION_STAGE, "observed-provider-identity"),
        )
        chain.mapping.revision = snapshot.revision
        for field, value in zip(("external_project_id", "external_service_account_id", "external_api_key_id"),
                                _identity_tuple(snapshot.identity), strict=True):
            setattr(chain.mapping, field, value)


def _mark_definite(chain, stage, attempt, at, evidence, code):
    mutate(attempt, at, state=AttemptState.DEFINITE_FAILURE, completed_at=at, error_code=code,
           noncreation_evidence_id=evidence.pk, lease_id=None, lease_until=None, next_action_at=None)
    if attempt.sequence < 3:
        mutate(stage, at, state=StageState.READY)
        if chain.demand.state == ChainState.RECOVERY_REQUIRED and stage.operation in CREATE_OPS:
            _chain_change(chain, at, ChainState.WORKING)
        _next_provision(chain, at, due=at + POLL)
        return
    mutate(stage, at, state=StageState.BLOCKED)
    for allowance in chain.allowances:
        if allowance.state == AllowanceState.HELD:
            mutate(allowance, at, state=AllowanceState.RELEASED, released_at=at)
    if stage.operation in CREATE_OPS and chain.claim.state == ClaimState.HELD:
        _release_claim(chain, evidence, at)
        _fail_registry(chain, at)
    _chain_change(chain, at, ChainState.FAILED, Error.RETRY_EXHAUSTED)


def _resolve_attempt(attempt, at, **proof):
    mutate(attempt, at, state=AttemptState.SUCCEEDED, completed_at=at, next_action_at=None,
           lease_id=None, lease_until=None, error_code=None, **proof)
    cancel_outboxes(ProviderProvisioningOutbox.objects.filter(attempt=attempt), at)


def _finalize_mutation(config, request, lease_id, receipt, clock):
    from .adapters.contracts import CleanupConfirmed, Created, MutationUnknown, NotCreated

    activate = False
    with atomic():
        chain = _lock_chain(request.mapping_id, config)
        attempt = chain.attempts[request.attempt_id]
        stage = _stage_by_attempt(chain, attempt)
        at = aware_utc(clock())
        fresh = attempt.state == AttemptState.DISPATCHED and attempt.lease_id == lease_id and at < attempt.lease_until
        if attempt.state == AttemptState.DISPATCHED and not fresh:
            _mark_unknown(chain, attempt, at, Error.OUTCOME_UNKNOWN)
        if isinstance(receipt, (Created, MutationUnknown, CleanupConfirmed)):
            identity = receipt.known_identity if isinstance(receipt, MutationUnknown) else receipt.identity
            _process_identity(chain, attempt, identity, at, created_at=getattr(receipt, "created_at", None),
                              provider_request_id=getattr(receipt, "provider_request_id", None))
        if attempt.state in ATTEMPT_TERMINAL:
            return _result(chain)
        if isinstance(receipt, MutationUnknown):
            if fresh:
                _mark_unknown(chain, attempt, at, receipt.code)
        elif isinstance(receipt, NotCreated):
            if fresh and receipt.proof == "LOCAL_NOT_SENT":
                evidence = _evidence(chain, attempt, RecoveryEvidenceKind.LOCAL_NOT_SENT, _target(stage),
                                     worker_audit("child-proved-no-dispatch"), at)
                _mark_definite(chain, stage, attempt, at, evidence, receipt.code)
        elif isinstance(receipt, CleanupConfirmed):
            if _identity_tuple(receipt.identity) != _target(stage):
                _refuse(Error.IDENTITY_CONFLICT)
            _validate_cleanup_ownership(chain, stage)
            _finish_cleanup_receipt(chain, stage, attempt, receipt, at)
        elif isinstance(receipt, Created):
            evidence = _evidence(chain, attempt, RecoveryEvidenceKind.OWNERSHIP, _identity_tuple(receipt.identity),
                                 worker_audit("validated-create-receipt"), at)
            _resolve_attempt(attempt, at)
            if stage.state == StageState.BLOCKED:
                # An operator-blocked chain retains that disposition on a
                # stale receipt. The compatible receipt is still durable.
                mutate(stage, at, ownership_evidence_id=evidence.pk)
                return _result(chain)
            mutate(stage, at, state=StageState.DONE, ownership_evidence_id=evidence.pk)
            if stage.operation == Op.OA_CREATE_PROJECT:
                if _prepare_project_dependency(chain, receipt.identity.project_id, at):
                    _next_provision(chain, at)
            else:
                activate = fresh and receipt.secret is not None and receipt.expires_at is None
                if not activate:
                    code = Error.UNSUPPORTED_EXPIRY if receipt.expires_at is not None else Error.SECRET_LOST
                    _chain_change(chain, at, ChainState.RECOVERY_REQUIRED, code)
                _next_provision(chain, at, due=at + POLL)
        audit_event("RECEIPT", attempt.pk, at, worker_audit("admin-receipt"),
                    operation=stage.operation, state=attempt.state, error_code=attempt.error_code)
        result = _result(chain)
    return _activate_mapping(config, request, receipt.secret, clock) if activate else result


def _activate_mapping(config, request, secret, clock):
    with atomic():
        chain = _lock_chain(request.mapping_id, config)
        at = aware_utc(clock())
        if chain.mapping.state != ProviderMappingState.PROVISIONING or chain.claim.cleanup_started_at is not None:
            return _result(chain)
        eligibility = _eligibility(chain.original, chain.demand.meter, at)
        epochs = create_epochs(config, chain.budget, chain.pool, at)
        if (
            eligibility or isinstance(epochs, Capacity) or chain.pool.provider not in config.requested_public_providers
            or chain.demand.current_mapping_id != request.mapping_id or chain.demand.state != ChainState.WORKING
            or any(stage.state != StageState.DONE for stage in chain.stages)
        ):
            _chain_change(chain, at, ChainState.RECOVERY_REQUIRED, Error.SECRET_LOST)
            _next_provision(chain, at)
            return _result(chain)
        registry.activate_mapping(
            mapping_id=chain.mapping.pk, expected_revision=chain.mapping.revision, secret=secret, now=at,
            audit=_registry_audit(RegistryReason.ACTIVATE, "validated-one-time-key"),
        )
        _chain_change(chain, at, ChainState.READY)
        cancel_outboxes(ProviderProvisioningOutbox.objects.filter(mapping=chain.mapping), at)
        return _result(chain)


def _first_collection(operation):
    if operation in (Op.DG_CREATE_KEY, Op.DG_REVOKE_KEY):
        return RecoveryCollection.DG_KEYS
    if operation in (Op.OA_CREATE_PROJECT, Op.OA_ARCHIVE_PROJECT):
        return RecoveryCollection.OA_PROJECTS
    if operation == Op.OA_REVOKE_KEY:
        return RecoveryCollection.OA_KEYS
    return RecoveryCollection.OA_SERVICE_ACCOUNTS


def recover_provisioning_attempt(attempt_id: UUID, *, clock: Clock = timezone.now) -> RecoveryResult:
    return _recover_provisioning_attempt(attempt_id, clock=clock, outbox_id=None, enough_time=lambda: True)


def _recover_provisioning_attempt(attempt_id, *, clock, outbox_id, enough_time):
    from .adapters.contracts import InventoryRequest

    config = worker_configuration()
    _require_outer()
    if type(attempt_id) is not UUID:
        _refuse(Error.INVALID_CONTEXT)
    mapping_id = ProvisioningAttempt.objects.filter(pk=attempt_id).values_list(
        "stage__claim__mapping_id", flat=True,
    ).first()
    if mapping_id is None:
        _refuse(Error.INVALID_CONTEXT)
    with atomic():
        chain = _lock_chain(mapping_id, config, original=False)
        attempt = chain.attempts[attempt_id]
        stage = _stage_by_attempt(chain, attempt)
        delivery = _work_delivery(outbox_id, chain, OutboxKind.RECOVER, attempt)
        at = aware_utc(clock())
        if not _accept_delivery(delivery, at):
            return _recovery_result(attempt)
        if outbox_id is None:
            cancel_outboxes(ProviderProvisioningOutbox.objects.filter(attempt=attempt), at)
        if _expire_attempt(chain, attempt, at):
            return _recovery_result(attempt)
        if (
            attempt.state not in (AttemptState.OUTCOME_UNKNOWN, AttemptState.RECOVERING)
            or stage.current_attempt_id != attempt.pk or chain.demand.current_mapping_id != mapping_id
        ):
            return _recovery_result(attempt)
        if attempt.next_action_at is not None and at < attempt.next_action_at or not enough_time():
            _next_recovery(chain, attempt, at)
            return _recovery_result(attempt)
        scope = scope_of(chain.pool)
        credential = local_credential(config, scope)
        if credential is None:
            _refuse(Error.POLICY_MISMATCH)
        new_round = attempt.recovery_scan_started_at is None
        if (new_round and attempt.recovery_round >= 3 or not new_round and
            (attempt.recovery_page_number >= 10000 or at >= attempt.recovery_scan_started_at + timedelta(seconds=300))):
            _operator_required(chain, stage, attempt, at)
            return _recovery_result(attempt)
        lease_id = uuid4()
        progress = (
            {"recovery_round": attempt.recovery_round + 1, "recovery_collection": _first_collection(stage.operation),
             "recovery_page_number": 0, "recovery_candidate_ids": [], "recovery_candidate_owner_id": None,
             "recovery_scan_started_at": at, "recovery_cursor": None} if new_round else {}
        )
        mutate(attempt, at, state=AttemptState.RECOVERING, lease_id=lease_id, lease_until=at + LEASE, **progress)
        requested = (attempt.recovery_round, attempt.recovery_collection, attempt.recovery_page_number, attempt.recovery_cursor)
        project = (attempt.observed_project_id or stage.target_project_id) if (
            attempt.recovery_collection in (RecoveryCollection.OA_SERVICE_ACCOUNTS, RecoveryCollection.OA_KEYS)
        ) else None
        request = InventoryRequest(attempt.recovery_collection, scope, project, attempt.recovery_cursor)
    if enough_time():
        close_database()
        page = _adapter(scope.provider).list_page(request, credential)
    else:
        from .adapters.contracts import ReadFailed
        page = ReadFailed(Error.TRANSPORT_NOT_SENT)
    with atomic():
        chain = _lock_chain(mapping_id, config, original=False)
        attempt = chain.attempts[attempt_id]
        stage = _stage_by_attempt(chain, attempt)
        at = aware_utc(clock())
        if (
            attempt.state == AttemptState.RECOVERING and attempt.lease_id == lease_id and at < attempt.lease_until
            and requested == (attempt.recovery_round, attempt.recovery_collection,
                              attempt.recovery_page_number, attempt.recovery_cursor)
        ):
            _apply_recovery_page(chain, stage, attempt, page, at)
        return _recovery_result(attempt)


def _operator_required(chain, stage, attempt, at):
    mutate(attempt, at, state=AttemptState.OPERATOR_REQUIRED, lease_id=None, lease_until=None,
           next_action_at=None, error_code=Error.OPERATOR_REQUIRED)
    if stage.state == StageState.WORKING:
        mutate(stage, at, state=StageState.BLOCKED)
    if chain.demand.state == ChainState.RECOVERY_REQUIRED:
        _chain_change(chain, at, ChainState.FAILED,
                      Error.CLEANUP_UNKNOWN if stage.operation in CLEANUP_OPS else Error.OPERATOR_REQUIRED)
    cancel_outboxes(ProviderProvisioningOutbox.objects.filter(attempt=attempt), at)
    audit_event("RECOVERY", attempt.pk, at, worker_audit("bounded-recovery-exhausted"),
                state=attempt.state, operation=stage.operation)
    logger.warning("Provider provisioning requires operator recovery",
                   extra={"provider_attempt_id": str(attempt.pk), "provider_operation": stage.operation})


def _end_round(chain, stage, attempt, at, reason):
    if attempt.recovery_round >= 3:
        _operator_required(chain, stage, attempt, at)
    else:
        _mark_unknown(chain, attempt, at, reason)


def _valid_pagination(page, cursor):
    if page.terminal_page_seen is True:
        return page.next_cursor is None
    return page.terminal_page_seen is False and valid_id(page.next_cursor) and page.next_cursor != cursor


def _apply_recovery_page(chain, stage, attempt, page, at):
    from .adapters.contracts import InventoryPage

    if at >= attempt.recovery_scan_started_at + timedelta(seconds=300):
        _operator_required(chain, stage, attempt, at)
        return
    if not isinstance(page, InventoryPage) or not _valid_pagination(page, attempt.recovery_cursor):
        _end_round(chain, stage, attempt, at, Error.RESPONSE_INVALID)
        return
    if page.next_cursor is not None and ProviderProvisioningOutbox.objects.filter(
        attempt=attempt, requested_recovery_round=attempt.recovery_round,
        requested_collection=attempt.recovery_collection, requested_cursor=page.next_cursor,
    ).exists():
        _end_round(chain, stage, attempt, at, Error.RESPONSE_INVALID)
        return
    collection = attempt.recovery_collection
    candidates = list(attempt.recovery_candidate_ids)
    ambiguous = False
    for record in page.records:
        if stage.operation in CLEANUP_OPS:
            continue  # Presence and absence are both non-authoritative mutation outcomes.
        if collection == RecoveryCollection.OA_KEYS:
            match = record.owner_id == attempt.recovery_candidate_owner_id
        else:
            match = record.marker == stage.marker
        if match:
            if record.created_at is None or record.created_at < attempt.dispatch_started_at - timedelta(seconds=1):
                ambiguous = True
            elif record.external_id not in candidates and len(candidates) < 2:
                candidates.append(record.external_id)
    if ambiguous or len(candidates) > 1:
        _operator_required(chain, stage, attempt, at)
        return
    if not page.terminal_page_seen:
        mutate(attempt, at, lease_id=None, lease_until=None, recovery_candidate_ids=candidates,
               recovery_page_number=attempt.recovery_page_number + 1, recovery_cursor=page.next_cursor, next_action_at=at)
        _next_recovery(chain, attempt, at)
        return
    if not candidates:
        _end_round(chain, stage, attempt, at, Error.CLEANUP_UNKNOWN if stage.operation in CLEANUP_OPS else Error.OUTCOME_UNKNOWN)
        return
    candidate = candidates[0]
    scope = scope_of(chain.pool)
    if collection == RecoveryCollection.OA_SERVICE_ACCOUNTS:
        identity = ProviderPartialIdentity(scope, stage.target_project_id, candidate, None)
        _process_identity(chain, attempt, identity, at)
        mutate(attempt, at, lease_id=None, lease_until=None, next_action_at=at,
               recovery_collection=RecoveryCollection.OA_KEYS, recovery_page_number=attempt.recovery_page_number + 1,
               recovery_candidate_ids=[], recovery_candidate_owner_id=candidate, recovery_cursor=None)
        _next_recovery(chain, attempt, at)
        return
    if collection == RecoveryCollection.DG_KEYS:
        identity = ProviderPartialIdentity(scope, scope.parent_scope_id, None, candidate)
    elif collection == RecoveryCollection.OA_PROJECTS:
        identity = ProviderPartialIdentity(scope, candidate, None, None)
    else:
        identity = ProviderPartialIdentity(scope, stage.target_project_id, attempt.recovery_candidate_owner_id, candidate)
    _process_identity(chain, attempt, identity, at)
    # A mutable provider label is enough for a provisional local identity and
    # double-count deduplication. It does not permit cleanup or a second POST.
    _operator_required(chain, stage, attempt, at)


def _validate_identity(identity, scope):
    if (
        type(identity) is not ProviderPartialIdentity or identity.scope != scope
        or any(value is not None and not valid_id(value) for value in _identity_tuple(identity))
        or (scope.provider == "deepgram" and (
            identity.service_account_id is not None or identity.project_id not in (None, scope.parent_scope_id)
        ))
    ):
        _refuse(Error.INVALID_CONTEXT)


def _validate_cleanup_ownership(chain, stage):
    evidence = stage.ownership_evidence
    targets = _target(stage)
    if (
        evidence is None or evidence.kind != RecoveryEvidenceKind.OWNERSHIP
        or evidence.mapping_id != chain.mapping.pk or evidence.pool_id != chain.pool.pk
        or any(expected is not None and expected != actual for expected, actual in zip(
            targets, (evidence.project_id, evidence.service_account_id, evidence.api_key_id), strict=True,
        ))
    ):
        _refuse(Error.IDENTITY_CONFLICT)


def _start_cleanup(chain, config, at):
    scope = scope_of(chain.pool)
    epoch = matching_scope_epoch(chain.pool, local_scope(config, scope))
    if epoch is None or not epoch.cleanup_authorized:
        return
    if any(attempt.state in (*UNKNOWN_STATES, AttemptState.DISPATCHED) for attempt in chain.attempts.values()):
        return
    project, account, key = _registry_identity(chain.mapping)
    if scope.provider == "deepgram":
        plan = [(Op.DG_REVOKE_KEY, (project, None, key))] if key else []
    else:
        plan = []
        if key and account:
            plan.append((Op.OA_REVOKE_KEY, (project, account, key)))
        if account:
            plan.append((Op.OA_DELETE_SERVICE_ACCOUNT, (project, account, None)))
        if project:
            plan.append((Op.OA_ARCHIVE_PROJECT, (project, None, None)))
    proofs = []
    for _, ids in plan:
        filters = dict(zip(("project_id", "service_account_id", "api_key_id"), ids, strict=True))
        proof = ProviderRecoveryEvidence.objects.filter(
            mapping=chain.mapping, pool=chain.pool, kind=RecoveryEvidenceKind.OWNERSHIP,
            **{field: value for field, value in filters.items() if value is not None},
        ).order_by("created_at", "pk").first()
        if proof is None:
            return
        proofs.append(proof)
    if not plan:
        return
    mutate(chain.claim, at, cleanup_started_at=at, cleanup_required_operations=[op.value for op, _ in plan])
    for (op, targets), proof in zip(plan, proofs, strict=True):
        _new_stage(chain.claim, op, at, target=targets, evidence=proof)
    _next_provision(chain, at)
    audit_event("CLEANUP", chain.claim.pk, at, worker_audit(epoch.cleanup_evidence_ref),
                stage_count=len(plan), generation=chain.claim.generation)


def _validate_cleanup_proof(chain, stage, attempt):
    evidence = attempt.cleanup_completion_evidence
    if (
        evidence is None or evidence.kind not in (RecoveryEvidenceKind.CLEANUP_SUCCESS,
                                                  RecoveryEvidenceKind.PROVIDER_CLEANUP_CONFIRMED)
        or evidence.pool_id != chain.pool.pk or evidence.mapping_id != chain.mapping.pk
        or evidence.attempt_id != attempt.pk or evidence.operation != stage.operation
        or (evidence.project_id, evidence.service_account_id, evidence.api_key_id) != _target(stage)
    ):
        _refuse(Error.IDENTITY_CONFLICT)


def _cleanup_complete(chain):
    operations = chain.claim.cleanup_required_operations
    stages = [stage for stage in chain.stages if stage.operation in CLEANUP_OPS]
    if not (
        chain.claim.cleanup_started_at is not None and type(operations) is list and 1 <= len(operations) <= 3
        and len(set(operations)) == len(operations) and set(operations) == {stage.operation for stage in stages}
    ):
        _refuse(Error.IDENTITY_CONFLICT)
    complete = True
    for stage in stages:
        attempt = chain.attempts.get(stage.current_attempt_id)
        if stage.state != StageState.DONE:
            complete = False
        elif attempt is None or attempt.state != AttemptState.SUCCEEDED:
            _refuse(Error.IDENTITY_CONFLICT)
        else:
            _validate_cleanup_proof(chain, stage, attempt)
    return complete


def finish_cleanup_locked(claim_id: UUID, *, at):
    # The caller owns the chain and all cleanup-stage/attempt locks.
    claim = ProviderResourceClaim.objects.get(pk=claim_id)
    stages = list(ProvisioningStage.objects.filter(claim=claim))
    attempts = ProvisioningAttempt.objects.in_bulk([stage.current_attempt_id for stage in stages if stage.current_attempt_id])
    chain = _Chain(None, None, [], claim.pool, claim.demand, claim.mapping, claim, stages, attempts, [])
    complete = _cleanup_complete(chain)
    if chain.mapping.state == ProviderMappingState.RETIRED:
        if not complete:
            _refuse(Error.IDENTITY_CONFLICT)
        if chain.demand.current_mapping_id != chain.mapping.pk:
            if not (
                claim.generation == 0 and chain.demand.replacement_count == 1
                and ProviderResourceClaim.objects.filter(
                    mapping_id=chain.demand.current_mapping_id, demand=chain.demand, generation=1, previous_claim=claim,
                ).exists()
            ):
                _refuse(Error.IDENTITY_CONFLICT)
            return ChainState(chain.demand.state)
        if chain.demand.state in (ChainState.FAILED, ChainState.RETIRED, ChainState.WAITING_CAPACITY):
            return ChainState(chain.demand.state)
    if not complete:
        next_stage = _next_stage(chain)
        if next_stage is not None and next_stage.state == StageState.READY:
            _next_provision(chain, at)
        return ChainState(chain.demand.state)
    if chain.mapping.state not in (ProviderMappingState.PROVISIONING, ProviderMappingState.ACTIVE):
        _refuse(Error.IDENTITY_CONFLICT)
    registry.retire_mapping(
        mapping_id=chain.mapping.pk, expected_revision=chain.mapping.revision, now=at,
        audit=_registry_audit(RegistryReason.RETIRE, "verified-cleanup-plan"),
    )
    if claim.generation == 1:
        _chain_change(chain, at, ChainState.FAILED, Error.RETRY_EXHAUSTED)
    elif chain.demand.replacement_count == 0:
        _chain_change(chain, at, ChainState.WAITING_CAPACITY)
        _next_provision(chain, at)
    else:
        _refuse(Error.IDENTITY_CONFLICT)
    return ChainState(chain.demand.state)


def _finish_cleanup_receipt(chain, stage, attempt, receipt, at):
    if attempt.state == AttemptState.OPERATOR_REQUIRED and chain.demand.state == ChainState.FAILED and (
        chain.demand.last_error_code in (Error.CLEANUP_UNKNOWN, Error.OPERATOR_REQUIRED)
    ):
        _chain_change(chain, at, ChainState.RECOVERY_REQUIRED)
    if not attempt.scope_epoch.cleanup_authorized or attempt.scope_epoch.pool_id != chain.pool.pk:
        _refuse(Error.IDENTITY_CONFLICT)
    evidence = _evidence(chain, attempt, RecoveryEvidenceKind.CLEANUP_SUCCESS, _identity_tuple(receipt.identity),
                         worker_audit("provider-confirmed-cleanup-response"), at, operation=stage.operation)
    _resolve_attempt(attempt, at, cleanup_completion_evidence_id=evidence.pk)
    mutate(stage, at, state=StageState.DONE)
    finish_cleanup_locked(chain.claim.pk, at=at)
    chain.demand.refresh_from_db()


def confirm_provider_cleanup(confirmation, *, audit, clock: Clock = timezone.now):
    from .contracts import CleanupConfirmationResult, ProviderCleanupConfirmation

    config = worker_configuration(operator=True)
    _require_outer()
    validate_audit(audit)
    if (
        type(confirmation) is not ProviderCleanupConfirmation or not positive_id(confirmation.pool_id)
        or type(confirmation.mapping_id) is not UUID or type(confirmation.attempt_id) is not UUID
        or type(confirmation.operation) is not Op or confirmation.operation not in CLEANUP_OPS
    ):
        _refuse(Error.INVALID_CONTEXT)
    with atomic():
        chain = _lock_chain(confirmation.mapping_id, config, original=False)
        attempt = chain.attempts.get(confirmation.attempt_id)
        _validate_identity(confirmation.identity, scope_of(chain.pool))
        if chain.pool.pk != confirmation.pool_id or attempt is None:
            _refuse(Error.INVALID_CONTEXT)
        stage = _stage_by_attempt(chain, attempt)
        if (
            stage.current_attempt_id != attempt.pk or stage.operation != confirmation.operation
            or _target(stage) != _identity_tuple(confirmation.identity)
            or attempt.dispatch_started_at is None or chain.claim.cleanup_started_at is None
            or attempt.scope_epoch is None or attempt.scope_epoch.pool_id != chain.pool.pk
            or not attempt.scope_epoch.cleanup_authorized or attempt.state in (AttemptState.CANCELLED, AttemptState.DEFINITE_FAILURE)
        ):
            _refuse(Error.INVALID_CONTEXT)
        _validate_cleanup_ownership(chain, stage)
        # Serialize a global operator request key even when two confirmations target different providers.
        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                               [f"selahcue-cleanup:{audit.operator_id}:{audit.request_id}"])
        at = aware_utc(clock())
        if attempt.state == AttemptState.DISPATCHED:
            if attempt.lease_until is None or at < attempt.lease_until:
                _refuse(Error.OPERATOR_REQUIRED)
            _mark_unknown(chain, attempt, at, Error.CLEANUP_UNKNOWN)
        if attempt.state == AttemptState.SUCCEEDED:
            _validate_cleanup_proof(chain, stage, attempt)
        existing = list(ProviderRecoveryEvidence.objects.filter(
            Q(attempt=attempt) | Q(operator_id=audit.operator_id, request_id=audit.request_id),
            kind=RecoveryEvidenceKind.PROVIDER_CLEANUP_CONFIRMED,
        ))
        if existing:
            if len(existing) != 1 or not _exact_confirmation(existing[0], confirmation, audit):
                _refuse(Error.IDENTITY_CONFLICT)
            evidence, replayed = existing[0], True
        else:
            evidence = _evidence(
                chain, attempt, RecoveryEvidenceKind.PROVIDER_CLEANUP_CONFIRMED,
                _identity_tuple(confirmation.identity), audit, at, operation=stage.operation,
            )
            replayed = False
        if attempt.state != AttemptState.SUCCEEDED:
            if attempt.state not in UNKNOWN_STATES:
                _refuse(Error.INVALID_CONTEXT)
            if chain.demand.state == ChainState.FAILED and chain.demand.last_error_code in (
                Error.CLEANUP_UNKNOWN, Error.OPERATOR_REQUIRED,
            ):
                _chain_change(chain, at, ChainState.RECOVERY_REQUIRED)
            _resolve_attempt(attempt, at, cleanup_completion_evidence_id=evidence.pk)
            mutate(stage, at, state=StageState.DONE)
        end_state = finish_cleanup_locked(chain.claim.pk, at=at)
        audit_event("CLEANUP", attempt.pk, at, audit, operation=stage.operation, state=attempt.state,
                    evidence_id=str(evidence.pk), replayed=replayed)
        return CleanupConfirmationResult(evidence.pk, attempt.pk, chain.mapping.pk, AttemptState.SUCCEEDED,
                                         end_state, replayed)


def _exact_confirmation(evidence, confirmation, audit):
    return (
        evidence.operator_id, evidence.request_id, evidence.evidence_ref, evidence.pool_id,
        evidence.mapping_id, evidence.attempt_id, evidence.operation,
        (evidence.project_id, evidence.service_account_id, evidence.api_key_id),
    ) == (
        audit.operator_id, audit.request_id, audit.evidence_ref, confirmation.pool_id,
        confirmation.mapping_id, confirmation.attempt_id, confirmation.operation,
        _identity_tuple(confirmation.identity),
    )


def record_recovery_evidence(*, pool_id, mapping_id, attempt_id, kind, identity, audit, clock: Clock = timezone.now) -> UUID:
    config = worker_configuration(operator=True)
    _require_outer()
    validate_audit(audit)
    if (
        not positive_id(pool_id) or mapping_id is not None and type(mapping_id) is not UUID
        or attempt_id is not None and type(attempt_id) is not UUID
        or type(kind) is not RecoveryEvidenceKind or kind not in (
            RecoveryEvidenceKind.OWNERSHIP, RecoveryEvidenceKind.PROVIDER_NONCREATION, RecoveryEvidenceKind.RESOURCE_EXCLUSION,
        )
        or attempt_id is not None and mapping_id is None
    ):
        _refuse(Error.INVALID_CONTEXT)
    with atomic():
        chain = _lock_chain(mapping_id, config, original=False) if mapping_id else None
        if chain is None:
            if kind != RecoveryEvidenceKind.RESOURCE_EXCLUSION:
                _refuse(Error.INVALID_CONTEXT)
            refs = ProviderCapacityPool.objects.filter(pk=pool_id).values("budget_id").first()
            if refs is None:
                _refuse(Error.INVALID_CONTEXT)
            _locked(ProviderGlobalBudget, refs["budget_id"])
            pool = _locked(ProviderCapacityPool, pool_id)
        else:
            pool = chain.pool
        scope = scope_of(pool)
        _validate_identity(identity, scope)
        if pool.pk != pool_id or local_scope(config, scope) is None:
            _refuse(Error.INVALID_CONTEXT)
        attempt = chain.attempts.get(attempt_id) if chain else None
        if attempt_id is not None and attempt is None:
            _refuse(Error.INVALID_CONTEXT)
        if attempt is not None and attempt.dispatch_started_at is None:
            _refuse(Error.INVALID_CONTEXT)
        at = aware_utc(clock())
        ids = _identity_tuple(identity)
        if kind == RecoveryEvidenceKind.RESOURCE_EXCLUSION:
            external_id = identity.api_key_id if pool.provider == "deepgram" else identity.project_id
            resource = ProviderExternalResource.objects.select_for_update().filter(pool=pool, external_id=external_id).first()
            at = aware_utc(clock())
            if resource is None or (chain is not None and chain.claim.resource_id != resource.pk):
                _refuse(Error.INVALID_CONTEXT)
        if chain:
            evidence = _evidence(chain, attempt, kind, ids, audit, at)
        else:
            evidence = ProviderRecoveryEvidence.objects.create(
                pool=pool, kind=kind, project_id=ids[0], service_account_id=ids[1], api_key_id=ids[2],
                operator_id=audit.operator_id, request_id=audit.request_id, evidence_ref=audit.evidence_ref,
                created_at=at, observed_at=at,
            )
        if kind == RecoveryEvidenceKind.RESOURCE_EXCLUSION:
            mutate(resource, at, count_state=ResourceCountState.EXCLUDED, exclusion_evidence_id=evidence.pk)
            if chain and chain.claim.state == ClaimState.COUNTED:
                _release_claim(chain, evidence, at)
        else:
            if attempt is None:
                _refuse(Error.INVALID_CONTEXT)
            _apply_operator_evidence(chain, attempt, identity, kind, evidence, at)
        audit_event("RECOVERY", evidence.pk, at, audit, evidence_kind=kind)
        return evidence.pk


def _apply_operator_evidence(chain, attempt, identity, kind, evidence, at):
    stage = _stage_by_attempt(chain, attempt)
    if (
        stage.current_attempt_id != attempt.pk or stage.operation not in CREATE_OPS
        or chain.demand.current_mapping_id != chain.mapping.pk
    ):
        _refuse(Error.INVALID_CONTEXT)
    if (kind == RecoveryEvidenceKind.OWNERSHIP and attempt.state == AttemptState.SUCCEEDED
        and chain.demand.state == ChainState.FAILED and chain.demand.last_error_code in (
            Error.RETRY_EXHAUSTED, Error.OPERATOR_REQUIRED,
        )):
        _apply_failed_ownership(chain, stage, attempt, identity, evidence, at)
        return
    if attempt.state not in UNKNOWN_STATES:
        _refuse(Error.INVALID_CONTEXT)
    if chain.demand.state == ChainState.FAILED:
        _chain_change(chain, at, ChainState.RECOVERY_REQUIRED)
    if kind == RecoveryEvidenceKind.PROVIDER_NONCREATION:
        if (
            _target(stage) != _identity_tuple(identity)
            or any(observed is not None and observed != target for observed, target in zip(
                (attempt.observed_project_id, attempt.observed_service_account_id, attempt.observed_api_key_id),
                _target(stage), strict=True,
            ))
        ):
            _refuse(Error.IDENTITY_CONFLICT)
        if attempt.state != AttemptState.RECOVERING:
            mutate(attempt, at, state=AttemptState.RECOVERING)
        if stage.state == StageState.BLOCKED:
            mutate(stage, at, state=StageState.READY)
            mutate(stage, at, state=StageState.WORKING)
        _mark_definite(chain, stage, attempt, at, evidence, Error.PROVIDER_DENIED)
        return
    project, account, key = _identity_tuple(identity)
    if (
        stage.operation == Op.DG_CREATE_KEY and (project != chain.pool.parent_scope_id or key is None)
        or stage.operation == Op.OA_CREATE_PROJECT and (project is None or account is not None or key is not None)
        or stage.operation == Op.OA_CREATE_SERVICE_ACCOUNT_KEY and (
            project != stage.target_project_id or account is None or key is None
        )
    ):
        _refuse(Error.INVALID_CONTEXT)
    _process_identity(chain, attempt, identity, at)
    _resolve_attempt(attempt, at)
    if stage.state == StageState.BLOCKED:
        mutate(stage, at, state=StageState.READY)
        mutate(stage, at, state=StageState.WORKING)
    mutate(stage, at, state=StageState.DONE, ownership_evidence_id=evidence.pk)
    if stage.operation == Op.OA_CREATE_PROJECT:
        _prepare_project_dependency(chain, project, at)
    _next_provision(chain, at)


def _prepare_project_dependency(chain, project_id, at):
    account = next(row for row in chain.stages if row.operation == Op.OA_CREATE_SERVICE_ACCOUNT_KEY)
    if (
        account.state != StageState.BLOCKED or account.current_attempt_id is not None
        or account.attempt_count != 0 or chain.claim.cleanup_started_at is not None
    ):
        return False
    mutate(account, at, state=StageState.READY, target_project_id=project_id)
    _prepare(chain.mapping, chain.pool, account, at)
    return True


def _apply_failed_ownership(chain, stage, attempt, identity, evidence, at):
    """Resume recovery or an unsent dependency after fresh ownership evidence."""
    observed = (attempt.observed_project_id, attempt.observed_service_account_id, attempt.observed_api_key_id)
    if (
        _identity_tuple(identity) != observed or not any(observed)
        or chain.mapping.state != ProviderMappingState.PROVISIONING or chain.claim.cleanup_started_at is not None
        or chain.claim.state != ClaimState.COUNTED
        or any(row.state in (*UNKNOWN_STATES, AttemptState.DISPATCHED) for row in chain.attempts.values())
        or ProviderRecoveryEvidence.objects.filter(
            mapping=chain.mapping, attempt=attempt, operator_id=evidence.operator_id,
            request_id=evidence.request_id, kind=RecoveryEvidenceKind.OWNERSHIP,
        ).exclude(pk=evidence.pk).exists()
    ):
        _refuse(Error.INVALID_CONTEXT)
    _chain_change(chain, at, ChainState.RECOVERY_REQUIRED, Error.SECRET_LOST)
    if stage.state == StageState.BLOCKED:
        mutate(stage, at, state=StageState.READY)
        mutate(stage, at, state=StageState.WORKING)
        mutate(stage, at, state=StageState.DONE)
    if stage.operation == Op.OA_CREATE_PROJECT:
        # Reuse the existing hold. Only the regular worker may dispatch after
        # rechecking the original demand and current capacity.
        _prepare_project_dependency(chain, identity.project_id, at)
    _next_provision(chain, at)
