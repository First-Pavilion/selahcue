"""Durable mapping identity, custody envelope and history invariants."""
from uuid import uuid4

from django.db import DEFAULT_DB_ALIAS, IntegrityError, connections, models, router
from django.db.models import F, Q, Value
from django.db.models.functions import Length
from django.db.models.lookups import Exact, GreaterThanOrEqual, LessThanOrEqual

from .configuration import valid_id
from .contracts import (
    AdminOperation, AllowanceState, AttemptState, ChainState, ClaimState, CLEANUP_OPS,
    OutboxKind, OutboxState, ProvisioningErrorCode, ProviderMappingState as State, RecoveryCollection,
    RecoveryEvidenceKind, ResourceCountState, ScanState, StageState,
    LOCAL_MINT_FAILURES, UNCERTAIN_MINT_FAILURES, MintFailureCode, SttMintState,
)

EXTERNAL_FIELDS = ("external_project_id", "external_service_account_id", "external_api_key_id")
ENVELOPE_FIELDS = ("secret_version", "wrapping_key_id", "secret_nonce", "secret_ciphertext")
OWNING_STATES = (State.PROVISIONING.value, State.ACTIVE.value)
TERMINAL_STATES = (State.FAILED.value, State.RETIRED.value)

_NO_ENVELOPE = Q(**{f"{name}__isnull": True for name in ENVELOPE_FIELDS})
_HAS_ENVELOPE = (
    Q(**{f"{name}__isnull": False for name in ENVELOPE_FIELDS})
    & Q(secret_version=1)
    & Exact(Length("secret_nonce"), Value(12))
    & GreaterThanOrEqual(Length("secret_ciphertext"), Value(17))
    & LessThanOrEqual(Length("secret_ciphertext"), Value(4112))
)


class ProviderCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    org = models.ForeignKey("selahcue_accounts.CustomerOrg", on_delete=models.PROTECT)
    provider = models.CharField(max_length=8, choices=[("deepgram", "Deepgram"), ("openai", "OpenAI")])
    parent_scope_id = models.CharField(max_length=256)
    external_project_id = models.CharField(max_length=256, null=True)
    external_service_account_id = models.CharField(max_length=256, null=True)
    external_api_key_id = models.CharField(max_length=256, null=True)
    state = models.CharField(max_length=12, choices=[(item.value, item.value) for item in State],
                             default=State.PROVISIONING.value)
    secret_version = models.PositiveSmallIntegerField(null=True)
    wrapping_key_id = models.CharField(max_length=256, null=True)
    secret_nonce = models.BinaryField(null=True)
    secret_ciphertext = models.BinaryField(null=True)
    revision = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    activated_at = models.DateTimeField(null=True)
    terminal_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "provider"], condition=Q(state__in=OWNING_STATES),
                                    name="provider_credential_owner_uniq"),
            models.UniqueConstraint(
                fields=["provider", "external_project_id", "external_api_key_id"],
                condition=Q(external_api_key_id__isnull=False), name="provider_credential_key_uniq",
            ),
            models.UniqueConstraint(
                fields=["external_project_id"], condition=Q(provider="openai", external_project_id__isnull=False),
                name="provider_openai_project_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(provider="deepgram", external_project_id__isnull=False,
                      external_project_id=F("parent_scope_id"), external_service_account_id__isnull=True)
                    | (
                        Q(provider="openai")
                        & (Q(external_service_account_id__isnull=True) | Q(external_project_id__isnull=False))
                        & (Q(external_api_key_id__isnull=True) | Q(external_service_account_id__isnull=False))
                    )
                ), name="provider_credential_identity_shape",
            ),
            models.CheckConstraint(condition=_NO_ENVELOPE | _HAS_ENVELOPE, name="provider_credential_envelope"),
            models.CheckConstraint(
                condition=(
                    Q(state__in=[item.value for item in State], revision__gte=1)
                    & (
                        Q(state__in=OWNING_STATES, terminal_at__isnull=True)
                        | Q(state__in=TERMINAL_STATES, terminal_at__isnull=False)
                    )
                    & (
                        (Q(state__in=(State.PROVISIONING.value, State.FAILED.value)) & _NO_ENVELOPE
                         & Q(activated_at__isnull=True))
                        | (Q(state=State.RETIRED.value, activated_at__isnull=True) & _NO_ENVELOPE)
                        | (
                            Q(state__in=(State.ACTIVE.value, State.RETIRED.value), activated_at__isnull=False,
                              external_project_id__isnull=False, external_api_key_id__isnull=False)
                            & _HAS_ENVELOPE
                        )
                    )
                ), name="provider_credential_state_shape",
            ),
        ]

    def save(self, *args, **kwargs):
        # PostgreSQL is authoritative even for bulk updates and direct SQL.
        ids = (self.parent_scope_id, self.wrapping_key_id, *(getattr(self, name) for name in EXTERNAL_FIELDS))
        if not valid_id(self.parent_scope_id) or any(value is not None and not valid_id(value) for value in ids):
            raise IntegrityError("Invalid provider mapping identifier")
        alias = kwargs.get("using") or router.db_for_write(type(self), instance=self) or DEFAULT_DB_ALIAS
        if connections[alias].vendor == "sqlite":
            if self._state.adding:
                if self.state != State.PROVISIONING or self.revision != 1:
                    raise IntegrityError("Invalid initial provider mapping state")
            else:
                before = type(self).objects.using(alias).filter(pk=self.pk).first()
                if before is None:
                    raise IntegrityError("Provider mapping history is immutable")
                self._validate_history(before)
        return super().save(*args, **kwargs)

    def _validate_history(self, before):
        immutable = ("id", "org_id", "provider", "parent_scope_id", "created_at")
        old_state = before.state
        transitions = {
            State.PROVISIONING: {State.PROVISIONING, State.ACTIVE, State.FAILED, State.RETIRED},
            State.ACTIVE: {State.ACTIVE, State.RETIRED},
            State.FAILED: {State.FAILED},
            State.RETIRED: {State.RETIRED},
        }
        if (
            any(getattr(self, name) != getattr(before, name) for name in immutable)
            or any(
                getattr(self, name) != getattr(before, name)
                and (old_state != State.PROVISIONING or getattr(before, name) is not None)
                for name in EXTERNAL_FIELDS
            )
            or self.state not in transitions[old_state]
            or self.revision != before.revision + 1
            or (before.activated_at is not None and self.activated_at != before.activated_at)
            or (before.activated_at is None and self.activated_at is not None
                and not (old_state == State.PROVISIONING and self.state == State.ACTIVE))
            or (before.terminal_at is not None and self.terminal_at != before.terminal_at)
        ):
            raise IntegrityError("Provider mapping history is immutable")

    def delete(self, *args, **kwargs):
        raise IntegrityError("Provider mapping history is retained")


# Provisioning rows use explicitly sampled timestamps. Mutable history is protected
# at the ORM boundary and by a migration-owned trigger on PostgreSQL.


def _fk(target, *, optional=False):
    return models.ForeignKey(target, on_delete=models.PROTECT, null=optional, related_name="+")


def _text(length=256, *, optional=False):
    return models.CharField(max_length=length, null=optional)


def _enum(enum, *, optional=False):
    return models.CharField(
        max_length=max(map(len, enum)), choices=[(entry.value, entry.value) for entry in enum], null=optional,
    )


def _timestamp(*, optional=True):
    return models.DateTimeField(null=optional)


def _check(name, condition):
    return models.CheckConstraint(name=f"prov_{name}", condition=condition)


def _unique(name, *fields, condition=None):
    return models.UniqueConstraint(name=f"prov_{name}", fields=fields, condition=condition)


def _choice(field, enum, *, nullable=False):
    condition = Q(**{f"{field}__in": tuple(map(str, enum))})
    return condition | Q(**{f"{field}__isnull": True}) if nullable else condition


_NO_LEASE = Q(lease_id__isnull=True, lease_until__isnull=True)
_HAS_LEASE = Q(lease_id__isnull=False, lease_until__isnull=False)
_UNRESOLVED = tuple(map(str, (
    AttemptState.PREPARED, AttemptState.DISPATCHED, AttemptState.OUTCOME_UNKNOWN,
    AttemptState.RECOVERING, AttemptState.OPERATOR_REQUIRED,
)))
_LIVE_OUTBOX = (OutboxState.PENDING, OutboxState.PUBLISHING, OutboxState.SENT)
_ATTEMPT_TERMINAL = (AttemptState.SUCCEEDED, AttemptState.DEFINITE_FAILURE, AttemptState.CANCELLED)
_OPERATIONAL_EVIDENCE = (RecoveryEvidenceKind.CLEANUP_SUCCESS, RecoveryEvidenceKind.PROVIDER_CLEANUP_CONFIRMED)


class _History(models.Model):
    created_at = _timestamp(optional=False)

    immutable = ()
    fill_once = ()
    transitions = None
    append_only = False

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        alias = kwargs.get("using") or router.db_for_write(type(self), instance=self) or DEFAULT_DB_ALIAS
        if not self._state.adding:
            before = type(self).objects.using(alias).get(pk=self.pk)
            if (
                self.append_only
                or any(getattr(before, name) != getattr(self, name) for name in ("created_at", *self.immutable))
                or any(getattr(before, name) not in (None, getattr(self, name)) for name in self.fill_once)
                or (self.transitions is not None and self.state != before.state
                    and self.state not in self.transitions.get(before.state, ()))
            ):
                raise IntegrityError("Provider provisioning history is retained")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise IntegrityError("Provider provisioning history is retained")


class _UUIDHistory(_History):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    class Meta:
        abstract = True


class _Mutable(_UUIDHistory):
    updated_at = _timestamp(optional=False)

    class Meta:
        abstract = True


class ProviderGlobalBudget(_History):
    id = models.BigAutoField(primary_key=True)
    provider = _text(8)
    current_epoch = _fk("GlobalPolicyEpoch", optional=True)
    updated_at = _timestamp(optional=False)
    immutable = ("provider",)

    class Meta:
        constraints = [_unique("budget_provider", "provider"), _check("budget_kind", _choice("provider", ("deepgram", "openai")))]


class GlobalPolicyEpoch(_UUIDHistory):
    budget = _fk(ProviderGlobalBudget)
    digest = _text(64)
    create_per_hour = models.PositiveBigIntegerField()
    create_per_day = models.PositiveBigIntegerField()
    published_by = _text(128)
    request_id = models.UUIDField()
    evidence_ref = _text(2048)
    append_only = True

    class Meta:
        constraints = [_unique("global_digest", "budget", "digest")]


class ProviderCapacityPool(_History):
    id = models.BigAutoField(primary_key=True)
    provider = _text(8)
    parent_scope_id = _text()
    budget = _fk(ProviderGlobalBudget)
    current_epoch = _fk("ScopePolicyEpoch", optional=True)
    next_slot = models.PositiveBigIntegerField(default=1)
    latest_complete_scan = _fk("ProviderInventoryScan", optional=True)
    inventory_valid_until = _timestamp()
    updated_at = _timestamp(optional=False)
    immutable = ("provider", "parent_scope_id", "budget_id")

    class Meta:
        constraints = [
            _unique("pool_parent", "provider", "parent_scope_id"),
            _check("pool_kind", _choice("provider", ("deepgram", "openai")) & Q(next_slot__gte=1)),
        ]


class ScopePolicyEpoch(_UUIDHistory):
    pool = _fk(ProviderCapacityPool)
    digest = _text(64)
    policy = models.JSONField()
    cleanup_authorized = models.BooleanField()
    cleanup_evidence_ref = _text(2048, optional=True)
    publication_digest = _text(64)
    published_by = _text(128)
    request_id = models.UUIDField()
    evidence_ref = _text(2048)
    append_only = True

    class Meta:
        constraints = [
            _unique("scope_digest", "pool", "publication_digest"),
            _check("cleanup_auth", Q(cleanup_authorized=True, cleanup_evidence_ref__isnull=False)
                   | Q(cleanup_authorized=False, cleanup_evidence_ref__isnull=True)),
        ]


class ProvisioningDemand(_Mutable):
    org = _fk("selahcue_accounts.CustomerOrg")
    provider = _text(8)
    trigger_license = _fk("selahcue_license_keys.AppLicenseKey")
    trigger_device = _fk("selahcue_devices.Device")
    trigger_token_pk = models.PositiveBigIntegerField()
    meter = _text(5)
    policy_version = _text(64)
    state = _enum(ChainState)
    replacement_count = models.PositiveBigIntegerField(default=0)
    last_error_code = _enum(ProvisioningErrorCode, optional=True)
    current_mapping = _fk(ProviderCredential, optional=True)
    immutable = ("org_id", "provider", "trigger_license_id", "trigger_device_id", "trigger_token_pk",
                 "meter", "policy_version")
    transitions = {
        ChainState.QUEUED: (ChainState.WORKING, ChainState.RECOVERY_REQUIRED, ChainState.FAILED),
        ChainState.WORKING: (ChainState.READY, ChainState.RECOVERY_REQUIRED, ChainState.FAILED),
        ChainState.RECOVERY_REQUIRED: (ChainState.WORKING, ChainState.WAITING_CAPACITY, ChainState.FAILED),
        ChainState.WAITING_CAPACITY: (ChainState.QUEUED, ChainState.FAILED),
        ChainState.READY: (ChainState.RETIRED,),
        ChainState.FAILED: (ChainState.RECOVERY_REQUIRED,),
    }

    class Meta:
        constraints = [
            _unique("demand_org_provider", "org", "provider"),
            _check("demand_state", _choice("state", ChainState)
                   & _choice("last_error_code", ProvisioningErrorCode, nullable=True)
                   & Q(trigger_token_pk__gte=1, replacement_count__lte=1)
                   & (Q(provider="deepgram", meter="stt") | Q(provider="openai", meter="notes"))),
        ]


class ProviderResourceClaim(_Mutable):
    demand = _fk(ProvisioningDemand)
    mapping = models.OneToOneField(ProviderCredential, on_delete=models.PROTECT)
    pool = _fk(ProviderCapacityPool)
    slot = models.PositiveBigIntegerField()
    generation = models.PositiveBigIntegerField()
    previous_claim = _fk("self", optional=True)
    state = _enum(ClaimState)
    resource = _fk("ProviderExternalResource", optional=True)
    released_at = _timestamp()
    release_evidence = _fk("ProviderRecoveryEvidence", optional=True)
    cleanup_started_at = _timestamp()
    cleanup_required_operations = models.JSONField(null=True)
    immutable = ("demand_id", "mapping_id", "pool_id", "slot", "generation", "previous_claim_id")
    fill_once = ("resource_id", "released_at", "release_evidence_id", "cleanup_started_at",
                 "cleanup_required_operations")
    transitions = {ClaimState.HELD: (ClaimState.COUNTED, ClaimState.RELEASED),
                   ClaimState.COUNTED: (ClaimState.RELEASED,)}

    class Meta:
        constraints = [
            _unique("claim_slot", "pool", "slot"), _unique("claim_generation", "demand", "generation"),
            _unique("claim_resource", "resource", condition=Q(resource__isnull=False)),
            _check("claim_generation_shape", Q(slot__gte=1) & (
                Q(generation=0, previous_claim__isnull=True) | Q(generation=1, previous_claim__isnull=False))),
            _check("claim_shape",
                   Q(state=ClaimState.HELD, resource__isnull=True, released_at__isnull=True, release_evidence__isnull=True)
                   | Q(state=ClaimState.COUNTED, resource__isnull=False, released_at__isnull=True, release_evidence__isnull=True)
                   | Q(state=ClaimState.RELEASED, released_at__isnull=False, release_evidence__isnull=False)),
            _check("claim_cleanup", Q(cleanup_started_at__isnull=True, cleanup_required_operations__isnull=True)
                   | Q(cleanup_started_at__isnull=False, cleanup_required_operations__isnull=False)),
        ]


class ProviderExternalResource(_Mutable):
    pool = _fk(ProviderCapacityPool)
    provider = _text(8)
    resource_scope_id = _text()
    external_id = _text()
    count_state = models.CharField(
        max_length=8, choices=[(state.value, state.value) for state in ResourceCountState],
        default=ResourceCountState.COUNTED.value,
    )
    first_seen_at = _timestamp(optional=False)
    last_seen_at = _timestamp(optional=False)
    exclusion_evidence = _fk("ProviderRecoveryEvidence", optional=True)
    immutable = ("pool_id", "provider", "resource_scope_id", "external_id", "first_seen_at")

    class Meta:
        constraints = [
            _unique("external_identity", "provider", "resource_scope_id", "external_id"),
            _check("external_state", _choice("provider", ("deepgram", "openai"))
                   & (Q(count_state=ResourceCountState.COUNTED, exclusion_evidence__isnull=True)
                      | Q(count_state=ResourceCountState.EXCLUDED, exclusion_evidence__isnull=False))),
        ]


class ProvisioningStage(_Mutable):
    claim = _fk(ProviderResourceClaim)
    operation = _enum(AdminOperation)
    target_project_id = _text(optional=True)
    target_service_account_id = _text(optional=True)
    target_api_key_id = _text(optional=True)
    marker = _text(64)
    state = _enum(StageState)
    attempt_count = models.PositiveBigIntegerField(default=0)
    current_attempt = _fk("ProvisioningAttempt", optional=True)
    ownership_evidence = _fk("ProviderRecoveryEvidence", optional=True)
    immutable = ("claim_id", "operation", "marker")
    fill_once = ("target_project_id", "target_service_account_id", "target_api_key_id", "ownership_evidence_id")
    transitions = {
        StageState.READY: (StageState.WORKING, StageState.CANCELLED),
        StageState.WORKING: (StageState.DONE, StageState.READY, StageState.BLOCKED, StageState.CANCELLED),
        StageState.BLOCKED: (StageState.READY, StageState.DONE),
    }

    class Meta:
        constraints = [
            _unique("stage_operation", "claim", "operation"),
            _check("stage_shape", _choice("operation", AdminOperation) & _choice("state", StageState)
                   & Q(attempt_count__lte=3)
                   & (~Q(operation__in=tuple(sorted(CLEANUP_OPS))) | Q(ownership_evidence__isnull=False))),
        ]


class ProvisioningAttempt(_Mutable):
    stage = _fk(ProvisioningStage)
    sequence = models.PositiveBigIntegerField()
    state = _enum(AttemptState)
    request_digest = _text(64)
    global_epoch = _fk(GlobalPolicyEpoch, optional=True)
    scope_epoch = _fk(ScopePolicyEpoch, optional=True)
    lease_id = models.UUIDField(null=True)
    lease_until = _timestamp()
    dispatch_started_at = _timestamp()
    completed_at = _timestamp()
    next_action_at = _timestamp()
    unknown_since = _timestamp()
    recovery_round = models.PositiveBigIntegerField(default=0)
    provider_request_id = _text(optional=True)
    observed_project_id = _text(optional=True)
    observed_service_account_id = _text(optional=True)
    observed_api_key_id = _text(optional=True)
    observed_created_at = _timestamp()
    error_code = _enum(ProvisioningErrorCode, optional=True)
    noncreation_evidence = _fk("ProviderRecoveryEvidence", optional=True)
    cleanup_completion_evidence = _fk("ProviderRecoveryEvidence", optional=True)
    recovery_collection = _enum(RecoveryCollection)
    recovery_cursor = _text(optional=True)
    recovery_page_number = models.PositiveBigIntegerField(default=0)
    recovery_candidate_ids = models.JSONField(default=list)
    recovery_candidate_owner_id = _text(optional=True)
    recovery_scan_started_at = _timestamp()
    immutable = ("stage_id", "sequence", "request_digest")
    fill_once = (
        "global_epoch_id", "scope_epoch_id", "dispatch_started_at", "completed_at", "unknown_since",
        "provider_request_id", "observed_project_id", "observed_service_account_id", "observed_api_key_id",
        "observed_created_at", "noncreation_evidence_id", "cleanup_completion_evidence_id",
    )
    transitions = {
        AttemptState.PREPARED: (AttemptState.DISPATCHED, AttemptState.CANCELLED),
        AttemptState.DISPATCHED: (AttemptState.SUCCEEDED, AttemptState.DEFINITE_FAILURE, AttemptState.OUTCOME_UNKNOWN),
        AttemptState.OUTCOME_UNKNOWN: (AttemptState.RECOVERING, AttemptState.OPERATOR_REQUIRED, AttemptState.SUCCEEDED),
        AttemptState.RECOVERING: (AttemptState.OUTCOME_UNKNOWN, AttemptState.SUCCEEDED,
                                 AttemptState.DEFINITE_FAILURE, AttemptState.OPERATOR_REQUIRED),
        AttemptState.OPERATOR_REQUIRED: (AttemptState.RECOVERING, AttemptState.SUCCEEDED),
    }

    class Meta:
        constraints = [
            _unique("attempt_sequence", "stage", "sequence"),
            _unique("attempt_unresolved", "stage", condition=Q(state__in=_UNRESOLVED)),
            _check("attempt_range", Q(sequence__range=(1, 3), recovery_round__lte=3, recovery_page_number__lte=10000)
                   & _choice("state", AttemptState) & _choice("recovery_collection", RecoveryCollection)
                   & _choice("error_code", ProvisioningErrorCode, nullable=True)),
            _check("attempt_lease", _NO_LEASE | (_HAS_LEASE & Q(state__in=(AttemptState.DISPATCHED, AttemptState.RECOVERING)))),
            _check("attempt_completion", Q(state__in=_ATTEMPT_TERMINAL, completed_at__isnull=False)
                   | (~Q(state__in=_ATTEMPT_TERMINAL) & Q(completed_at__isnull=True))),
            _check("attempt_dispatch", Q(state__in=(AttemptState.PREPARED, AttemptState.CANCELLED),
                                         dispatch_started_at__isnull=True, scope_epoch__isnull=True, global_epoch__isnull=True)
                   | (~Q(state__in=(AttemptState.PREPARED, AttemptState.CANCELLED))
                      & Q(dispatch_started_at__isnull=False, scope_epoch__isnull=False))),
        ]


class ProviderCreateAllowance(_Mutable):
    stage = _fk(ProvisioningStage)
    attempt = models.OneToOneField(ProvisioningAttempt, on_delete=models.PROTECT, null=True)
    state = _enum(AllowanceState)
    dispatched_at = _timestamp()
    released_at = _timestamp()
    immutable = ("stage_id",)
    fill_once = ("attempt_id", "dispatched_at", "released_at")
    transitions = {AllowanceState.HELD: (AllowanceState.DISPATCHED, AllowanceState.RELEASED)}

    class Meta:
        constraints = [
            _unique("allowance_held", "stage", condition=Q(state=AllowanceState.HELD)),
            _check("allowance_shape",
                   Q(state=AllowanceState.HELD, attempt__isnull=True, dispatched_at__isnull=True, released_at__isnull=True)
                   | Q(state=AllowanceState.DISPATCHED, attempt__isnull=False, dispatched_at__isnull=False, released_at__isnull=True)
                   | Q(state=AllowanceState.RELEASED, dispatched_at__isnull=True, released_at__isnull=False)),
        ]
        indexes = [models.Index(fields=("state", "dispatched_at"), name="prov_allowance_time_idx")]


class ProviderRecoveryEvidence(_UUIDHistory):
    pool = _fk(ProviderCapacityPool)
    attempt = _fk(ProvisioningAttempt, optional=True)
    mapping = _fk(ProviderCredential, optional=True)
    kind = _enum(RecoveryEvidenceKind)
    operation = _enum(AdminOperation, optional=True)
    project_id = _text(optional=True)
    service_account_id = _text(optional=True)
    api_key_id = _text(optional=True)
    operator_id = _text(128)
    request_id = models.UUIDField()
    evidence_ref = _text(2048)
    observed_at = _timestamp(optional=False)
    append_only = True

    class Meta:
        constraints = [
            _check("evidence_kind", _choice("kind", RecoveryEvidenceKind) & (
                Q(kind__in=_OPERATIONAL_EVIDENCE, operation__in=tuple(sorted(CLEANUP_OPS)),
                  operation__isnull=False, mapping__isnull=False, attempt__isnull=False)
                | (~Q(kind__in=_OPERATIONAL_EVIDENCE) & Q(operation__isnull=True)))),
            _unique("evidence_attempt", "kind", "attempt", condition=Q(kind=RecoveryEvidenceKind.PROVIDER_CLEANUP_CONFIRMED)),
            _unique("evidence_request", "operator_id", "request_id",
                    condition=Q(kind=RecoveryEvidenceKind.PROVIDER_CLEANUP_CONFIRMED)),
        ]


class ProviderInventoryScan(_Mutable):
    pool = _fk(ProviderCapacityPool)
    scope_epoch = _fk(ScopePolicyEpoch)
    state = _enum(ScanState)
    started_at = _timestamp(optional=False)
    finished_at = _timestamp()
    cursor = _text(optional=True)
    page_number = models.PositiveBigIntegerField(default=0)
    page_retry_count = models.PositiveBigIntegerField(default=0)
    terminal_page_seen = models.BooleanField(default=False)
    error_code = _enum(ProvisioningErrorCode, optional=True)
    lease_id = models.UUIDField(null=True)
    lease_until = _timestamp()
    immutable = ("pool_id", "scope_epoch_id", "started_at")
    fill_once = ("finished_at",)
    transitions = {ScanState.PARTIAL: (ScanState.COMPLETE, ScanState.FAILED)}

    class Meta:
        constraints = [
            _unique("scan_partial", "pool", condition=Q(state=ScanState.PARTIAL)),
            _check("scan_shape", Q(page_retry_count__lte=3) & (
                (Q(state=ScanState.PARTIAL, finished_at__isnull=True, terminal_page_seen=False) & (_NO_LEASE | _HAS_LEASE))
                | (Q(state=ScanState.COMPLETE, finished_at__isnull=False, terminal_page_seen=True) & _NO_LEASE)
                | (Q(state=ScanState.FAILED, finished_at__isnull=False, terminal_page_seen=False) & _NO_LEASE))),
        ]


class ProviderInventoryItem(_History):
    id = models.BigAutoField(primary_key=True)
    scan = _fk(ProviderInventoryScan)
    external_id = _text()
    marker = _text(optional=True)
    provider_created_at = _timestamp()
    provider_status = _text(32, optional=True)
    append_only = True

    class Meta:
        constraints = [
            _unique("scan_external_id", "scan", "external_id"),
            _check("item_status", _choice("provider_status", ("active", "expired", "archived", "unknown"), nullable=True)),
        ]


class ProviderProvisioningOutbox(_Mutable):
    pool = _fk(ProviderCapacityPool)
    kind = _enum(OutboxKind)
    mapping = _fk(ProviderCredential, optional=True)
    attempt = _fk(ProvisioningAttempt, optional=True)
    scan = _fk(ProviderInventoryScan, optional=True)
    generation = models.PositiveBigIntegerField()
    state = _enum(OutboxState)
    available_at = _timestamp(optional=False)
    lease_id = models.UUIDField(null=True)
    lease_until = _timestamp()
    publish_count = models.PositiveBigIntegerField(default=0)
    sent_at = _timestamp()
    acked_at = _timestamp()
    error_code = _enum(ProvisioningErrorCode, optional=True)
    requested_recovery_round = models.PositiveBigIntegerField(null=True)
    requested_collection = _enum(RecoveryCollection, optional=True)
    requested_page_number = models.PositiveBigIntegerField(null=True)
    requested_cursor = _text(optional=True)
    immutable = (
        "pool_id", "kind", "mapping_id", "attempt_id", "scan_id", "generation",
        "requested_recovery_round", "requested_collection", "requested_page_number", "requested_cursor",
    )
    fill_once = ("acked_at",)
    transitions = {
        OutboxState.PENDING: (OutboxState.PUBLISHING, OutboxState.CANCELLED),
        OutboxState.PUBLISHING: (OutboxState.PENDING, OutboxState.SENT, OutboxState.ACKED, OutboxState.CANCELLED),
        OutboxState.SENT: (OutboxState.PENDING, OutboxState.ACKED, OutboxState.CANCELLED),
    }

    class Meta:
        constraints = [
            *[
                _unique(f"outbox_{label}_gen", "kind", identity, "generation", condition=Q(kind=kind))
                for label, identity, kind in (("prov", "mapping", OutboxKind.PROVISION),
                                              ("rec", "attempt", OutboxKind.RECOVER),
                                              ("inv", "scan", OutboxKind.INVENTORY_PAGE))
            ],
            *[
                _unique(f"outbox_{label}_live", "kind", identity, condition=Q(kind=kind, state__in=_LIVE_OUTBOX))
                for label, identity, kind in (("prov", "mapping", OutboxKind.PROVISION),
                                              ("rec", "attempt", OutboxKind.RECOVER),
                                              ("inv", "scan", OutboxKind.INVENTORY_PAGE))
            ],
            _check("outbox_subject", Q(generation__gte=1) & (
                Q(kind=OutboxKind.PROVISION, mapping__isnull=False, attempt__isnull=True, scan__isnull=True,
                  requested_recovery_round__isnull=True, requested_collection__isnull=True,
                  requested_page_number__isnull=True, requested_cursor__isnull=True)
                | Q(kind=OutboxKind.RECOVER, mapping__isnull=False, attempt__isnull=False, scan__isnull=True,
                    requested_recovery_round__isnull=False, requested_collection__isnull=False,
                    requested_page_number__isnull=False)
                | Q(kind=OutboxKind.INVENTORY_PAGE, mapping__isnull=True, attempt__isnull=True, scan__isnull=False,
                    requested_recovery_round__isnull=True, requested_collection__isnull=True,
                    requested_page_number__isnull=False))),
            _check("outbox_state", _choice("state", OutboxState) & (
                (Q(state=OutboxState.PUBLISHING) & _HAS_LEASE) | (~Q(state=OutboxState.PUBLISHING) & _NO_LEASE))
                & (Q(state=OutboxState.ACKED, acked_at__isnull=False) | ~Q(state=OutboxState.ACKED))),
        ]
        indexes = [models.Index(fields=("state", "available_at"), name="prov_outbox_due_idx")]


class SttMintAttempt(models.Model):
    """Durable dispatch and accounting facts for one initial STT reservation."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    reservation = models.OneToOneField(
        "selahcue_usage.UsageReservation", on_delete=models.PROTECT, related_name="stt_mint_attempt",
    )
    request_receipt_id = models.UUIDField(unique=True, editable=False)
    owner_nonce = models.UUIDField(editable=False)
    trigger_token_pk = models.PositiveBigIntegerField(editable=False)
    mapping_revision = models.PositiveBigIntegerField(editable=False)
    state = models.CharField(max_length=16, choices=[(item.value, item.value) for item in SttMintState])
    prepared_at = models.DateTimeField()
    dispatch_not_after = models.DateTimeField()
    dispatched_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    credential_expires_at = models.DateTimeField(null=True)
    known_mint_received_at = models.DateTimeField(null=True)
    failure_code = models.CharField(
        max_length=32, null=True, choices=[(item.value, item.value) for item in MintFailureCode],
    )
    audit_event = models.OneToOneField("selahcue_audit.AuditEvent", on_delete=models.SET_NULL, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(trigger_token_pk__gt=0, mapping_revision__gt=0, dispatch_not_after__gt=F("prepared_at"))
                    & (Q(dispatched_at__isnull=True) | Q(dispatched_at__gte=F("prepared_at")))
                    & (Q(finished_at__isnull=True) | Q(finished_at__gte=F("prepared_at")))
                    & (
                        Q(credential_expires_at__isnull=True, known_mint_received_at__isnull=True)
                        | Q(credential_expires_at__gt=F("known_mint_received_at"),
                            known_mint_received_at__isnull=False, credential_expires_at__isnull=False)
                    )
                ), name="stt_mint_attempt_time_shape",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state=SttMintState.PREPARED, dispatched_at__isnull=True, finished_at__isnull=True,
                      credential_expires_at__isnull=True, failure_code__isnull=True)
                    | Q(state=SttMintState.DISPATCHED, dispatched_at__isnull=False, finished_at__isnull=True,
                        credential_expires_at__isnull=True, failure_code__isnull=True)
                    | Q(state=SttMintState.UNKNOWN, dispatched_at__isnull=False, finished_at__isnull=False,
                        failure_code__isnull=False, failure_code__in=UNCERTAIN_MINT_FAILURES)
                    | Q(state=SttMintState.GRANTED, dispatched_at__isnull=False, finished_at__isnull=False,
                        credential_expires_at__isnull=False, failure_code__isnull=True)
                    | (
                        Q(state=SttMintState.DISCARDED, dispatched_at__isnull=False, finished_at__isnull=False,
                          credential_expires_at__isnull=False)
                        & (Q(failure_code__isnull=True) | Q(failure_code__in=UNCERTAIN_MINT_FAILURES))
                    )
                    | Q(state=SttMintState.DEFINITE_FAILURE, finished_at__isnull=False,
                        credential_expires_at__isnull=True, failure_code__isnull=False,
                        failure_code__in=LOCAL_MINT_FAILURES)
                ), name="stt_mint_attempt_state_shape",
            ),
        ]
