"""Immutable provider metadata and finite internal errors."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Callable, Literal
from uuid import UUID

ProviderProcessRole = Literal["web", "usage", "provisioner", "notes", "maintenance"]
ProviderKind = Literal["deepgram", "openai"]


class ConfigSource(StrEnum):
    SETTINGS = "settings"
    KEYRING = "keyring"
    USAGE = "usage"
    PROVISIONING = "provisioning"
    POLICY = "policy"


class ConfigErrorCode(StrEnum):
    PCFG_ROLE_INVALID = "PCFG_ROLE_INVALID"
    PCFG_ROLE_MISMATCH = "PCFG_ROLE_MISMATCH"
    PCFG_QUEUE_MISMATCH = "PCFG_QUEUE_MISMATCH"
    PCFG_NOT_INITIALIZED = "PCFG_NOT_INITIALIZED"
    PCFG_FILE_REQUIRED = "PCFG_FILE_REQUIRED"
    PCFG_FILE_UNREADABLE = "PCFG_FILE_UNREADABLE"
    PCFG_FILE_UNSAFE = "PCFG_FILE_UNSAFE"
    PCFG_FILE_TOO_LARGE = "PCFG_FILE_TOO_LARGE"
    PCFG_ENCODING_INVALID = "PCFG_ENCODING_INVALID"
    PCFG_JSON_INVALID = "PCFG_JSON_INVALID"
    PCFG_SCHEMA_INVALID = "PCFG_SCHEMA_INVALID"
    PCFG_SCOPE_MISMATCH = "PCFG_SCOPE_MISMATCH"
    PCFG_KEY_INVALID = "PCFG_KEY_INVALID"
    PCFG_KEY_MISSING = "PCFG_KEY_MISSING"
    PCFG_CAPABILITY_UNCONFIGURED = "PCFG_CAPABILITY_UNCONFIGURED"
    PCFG_NOTES_RUNTIME_UNAVAILABLE = "PCFG_NOTES_RUNTIME_UNAVAILABLE"
    PCFG_INTERNAL_FAILURE = "PCFG_INTERNAL_FAILURE"


class CustodyErrorCode(StrEnum):
    PCUST_ROLE_DENIED = "PCUST_ROLE_DENIED"
    PCUST_IDENTITY_INCOMPLETE = "PCUST_IDENTITY_INCOMPLETE"
    PCUST_STATE_INVALID = "PCUST_STATE_INVALID"
    PCUST_SECRET_INVALID = "PCUST_SECRET_INVALID"
    PCUST_KEY_UNAVAILABLE = "PCUST_KEY_UNAVAILABLE"
    PCUST_ENVELOPE_INVALID = "PCUST_ENVELOPE_INVALID"
    PCUST_AUTHENTICATION_FAILED = "PCUST_AUTHENTICATION_FAILED"


class RegistryErrorCode(StrEnum):
    PREG_INVALID_CONTEXT = "PREG_INVALID_CONTEXT"
    PREG_NOT_FOUND = "PREG_NOT_FOUND"
    PREG_IDENTITY_CONFLICT = "PREG_IDENTITY_CONFLICT"
    PREG_OWNERSHIP_CONFLICT = "PREG_OWNERSHIP_CONFLICT"
    PREG_STATE_CONFLICT = "PREG_STATE_CONFLICT"
    PREG_REVISION_CONFLICT = "PREG_REVISION_CONFLICT"
    PREG_SECRET_MISMATCH = "PREG_SECRET_MISMATCH"
    PREG_INTERNAL_FAILURE = "PREG_INTERNAL_FAILURE"


class ProviderConfigurationError(Exception):
    def __init__(self, code: ConfigErrorCode, source: ConfigSource | None = None):
        self.code = code
        self.source = source
        super().__init__(code.value if source is None else f"{code.value} ({source.value})")


class ProviderCustodyError(Exception):
    def __init__(self, code: CustodyErrorCode):
        self.code = code
        super().__init__(code.value)


class ProviderRegistryError(Exception):
    def __init__(self, code: RegistryErrorCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class SecretBytes:
    value: bytes = field(repr=False)

    def __repr__(self) -> str:
        return "SecretBytes(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, slots=True)
class ProviderScope:
    provider: ProviderKind
    parent_scope_id: str


@dataclass(frozen=True, slots=True)
class WrappingKey:
    key_id: str
    material: SecretBytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class ProviderKeyring:
    active_key_id: str
    keys: tuple[WrappingKey, ...] = field(repr=False)

    def _find(self, key_id: str) -> WrappingKey:
        for key in self.keys:
            if key.key_id == key_id:
                return key
        raise ProviderConfigurationError(ConfigErrorCode.PCFG_KEY_MISSING, ConfigSource.KEYRING)

    def lookup(self, key_id: str) -> SecretBytes:
        return self._find(key_id).material

    def active(self) -> WrappingKey:
        return self._find(self.active_key_id)


@dataclass(frozen=True, slots=True)
class ProviderScopePolicy:
    scope: ProviderScope
    resource_capacity: int | None
    resource_reserve: int | None
    create_per_day: int | None
    create_per_hour: int | None
    capacity_evidence_ref: str | None
    controls_evidence_ref: str | None
    unattributed_usage_threshold: Decimal
    stream_concurrency_capacity: int | None
    notes_policy_id: str | None
    notes_daily_budget_usd: Decimal | None


@dataclass(frozen=True, slots=True)
class ProviderCreationBudget:
    provider: ProviderKind
    create_per_hour: int
    create_per_day: int


@dataclass(frozen=True, slots=True)
class ProviderDeploymentPolicy:
    schema_version: Literal[1]
    accounting_mode: Literal["observed_records_with_late_corrections"]
    accepted_by: str
    accepted_at: datetime
    scopes: tuple[ProviderScopePolicy, ...]
    creation_budgets: tuple[ProviderCreationBudget, ...] = ()


@dataclass(frozen=True, slots=True)
class UsageCredential:
    scope: ProviderScope
    secret: SecretBytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class ProvisioningCredential:
    scope: ProviderScope
    secret: SecretBytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class ProviderConfiguration:
    role: ProviderProcessRole
    requested_public_providers: frozenset[ProviderKind]
    provisioning_requested: bool
    policy: ProviderDeploymentPolicy | None
    keyring: ProviderKeyring | None = field(repr=False)
    usage_credentials: tuple[UsageCredential, ...] = field(repr=False)
    provisioning_credentials: tuple[ProvisioningCredential, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class EncryptedSecret:
    version: Literal[1]
    key_id: str
    nonce: bytes = field(repr=False)
    ciphertext: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class ReadyMapping:
    mapping_id: UUID
    org_id: int
    provider: ProviderKind


class ProviderMappingState(StrEnum):
    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    RETIRED = "RETIRED"


class RegistryReason(StrEnum):
    PROVISION_INTENT = "PROVISION_INTENT"
    PROVISION_STAGE = "PROVISION_STAGE"
    ACTIVATE = "ACTIVATE"
    IMPORT_APPROVED_ALLOCATION = "IMPORT_APPROVED_ALLOCATION"
    RECOVER_EXISTING_SECRET = "RECOVER_EXISTING_SECRET"
    DEFINITE_FAILURE = "DEFINITE_FAILURE"
    RETIRE = "RETIRE"
    REWRAP = "REWRAP"


@dataclass(frozen=True, slots=True)
class ProviderPartialIdentity:
    scope: ProviderScope
    project_id: str | None
    service_account_id: str | None
    api_key_id: str | None


@dataclass(frozen=True, slots=True)
class ProviderExternalIdentity:
    scope: ProviderScope
    project_id: str
    service_account_id: str | None
    api_key_id: str


@dataclass(frozen=True, slots=True)
class RegistryAuditContext:
    operator_id: str
    request_id: UUID
    reason: RegistryReason
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class RegistrySnapshot:
    mapping_id: UUID
    org_id: int
    provider: ProviderKind
    state: ProviderMappingState
    revision: int
    identity: ProviderPartialIdentity


@dataclass(frozen=True, slots=True)
class RotationCursor:
    org_id: int
    mapping_id: UUID


@dataclass(frozen=True, slots=True)
class RotationFailure:
    mapping_id: UUID
    code: CustodyErrorCode | RegistryErrorCode


@dataclass(frozen=True, slots=True)
class RotationBatchResult:
    next_cursor: RotationCursor | None
    scanned: int
    rewrapped: tuple[UUID, ...]
    failures: tuple[RotationFailure, ...]
    exhausted: bool


Clock = Callable[[], datetime]


class CapacityUnavailableCode(StrEnum):
    DISABLED = "DISABLED"
    POLICY_UNCONFIGURED = "POLICY_UNCONFIGURED"
    RESOURCE_CAPACITY = "RESOURCE_CAPACITY"
    DAILY_CREATE_LIMIT = "DAILY_CREATE_LIMIT"
    HOURLY_CREATE_LIMIT = "HOURLY_CREATE_LIMIT"


class ChainState(StrEnum):
    QUEUED = "QUEUED"
    WORKING = "WORKING"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    WAITING_CAPACITY = "WAITING_CAPACITY"
    READY = "READY"
    FAILED = "FAILED"
    RETIRED = "RETIRED"


class AttemptState(StrEnum):
    PREPARED = "PREPARED"
    DISPATCHED = "DISPATCHED"
    SUCCEEDED = "SUCCEEDED"
    DEFINITE_FAILURE = "DEFINITE_FAILURE"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    RECOVERING = "RECOVERING"
    OPERATOR_REQUIRED = "OPERATOR_REQUIRED"
    CANCELLED = "CANCELLED"


class StageState(StrEnum):
    READY = "READY"
    WORKING = "WORKING"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class ClaimState(StrEnum):
    HELD = "HELD"
    COUNTED = "COUNTED"
    RELEASED = "RELEASED"


class AllowanceState(StrEnum):
    HELD = "HELD"
    DISPATCHED = "DISPATCHED"
    RELEASED = "RELEASED"


class OutboxState(StrEnum):
    PENDING = "PENDING"
    PUBLISHING = "PUBLISHING"
    SENT = "SENT"
    ACKED = "ACKED"
    CANCELLED = "CANCELLED"


class ScanState(StrEnum):
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ResourceCountState(StrEnum):
    COUNTED = "COUNTED"
    EXCLUDED = "EXCLUDED"


class AdminOperation(StrEnum):
    DG_CREATE_KEY = "DG_CREATE_KEY"
    OA_CREATE_PROJECT = "OA_CREATE_PROJECT"
    OA_CREATE_SERVICE_ACCOUNT_KEY = "OA_CREATE_SERVICE_ACCOUNT_KEY"
    DG_REVOKE_KEY = "DG_REVOKE_KEY"
    OA_REVOKE_KEY = "OA_REVOKE_KEY"
    OA_DELETE_SERVICE_ACCOUNT = "OA_DELETE_SERVICE_ACCOUNT"
    OA_ARCHIVE_PROJECT = "OA_ARCHIVE_PROJECT"


class OutboxKind(StrEnum):
    PROVISION = "PROVISION"
    RECOVER = "RECOVER"
    INVENTORY_PAGE = "INVENTORY_PAGE"


class RecoveryCollection(StrEnum):
    NONE = "NONE"
    DG_KEYS = "DG_KEYS"
    OA_PROJECTS = "OA_PROJECTS"
    OA_SERVICE_ACCOUNTS = "OA_SERVICE_ACCOUNTS"
    OA_KEYS = "OA_KEYS"


class RecoveryEvidenceKind(StrEnum):
    LOCAL_NOT_SENT = "LOCAL_NOT_SENT"
    PROVIDER_NONCREATION = "PROVIDER_NONCREATION"
    OWNERSHIP = "OWNERSHIP"
    RESOURCE_EXCLUSION = "RESOURCE_EXCLUSION"
    CLEANUP_SUCCESS = "CLEANUP_SUCCESS"
    PROVIDER_CLEANUP_CONFIRMED = "PROVIDER_CLEANUP_CONFIRMED"


class ProvisioningErrorCode(StrEnum):
    INVALID_CONTEXT = "INVALID_CONTEXT"
    INELIGIBLE = "INELIGIBLE"
    ALLOWANCE_UNAVAILABLE = "ALLOWANCE_UNAVAILABLE"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    INVENTORY_UNAVAILABLE = "INVENTORY_UNAVAILABLE"
    TRANSPORT_NOT_SENT = "TRANSPORT_NOT_SENT"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    SECRET_LOST = "SECRET_LOST"
    UNSUPPORTED_EXPIRY = "UNSUPPORTED_EXPIRY"
    PROVIDER_DENIED = "PROVIDER_DENIED"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    CLEANUP_UNKNOWN = "CLEANUP_UNKNOWN"
    OPERATOR_REQUIRED = "OPERATOR_REQUIRED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"

CREATE_OPS = frozenset({
    AdminOperation.DG_CREATE_KEY, AdminOperation.OA_CREATE_PROJECT,
    AdminOperation.OA_CREATE_SERVICE_ACCOUNT_KEY,
})
CLEANUP_OPS = frozenset(AdminOperation) - CREATE_OPS


class ProvisioningRejected(Exception):
    def __init__(self, code: ProvisioningErrorCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class ProvisioningPending:
    mapping_id: UUID
    retry_after_seconds: int = 5

    def __post_init__(self):
        if type(self.retry_after_seconds) is not int or self.retry_after_seconds != 5:
            raise ValueError("The provisioning retry interval is five seconds")


@dataclass(frozen=True, slots=True)
class CapacityUnavailable:
    code: CapacityUnavailableCode


@dataclass(frozen=True, slots=True)
class ProvisioningIntent:
    mapping_id: UUID
    provider: ProviderKind
    org_id: int
    state: ChainState
    attempt_id: UUID
    capacity_slot: int
    last_error_code: ProvisioningErrorCode | None


@dataclass(frozen=True, slots=True)
class ProvisioningResult:
    mapping_id: UUID
    state: ChainState
    retry_after_seconds: int | None


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    attempt_id: UUID
    state: AttemptState
    requires_operator_recovery: bool


@dataclass(frozen=True, slots=True)
class ProvisioningAuditContext:
    operator_id: str
    request_id: UUID
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class ProviderCleanupConfirmation:
    pool_id: int
    mapping_id: UUID
    attempt_id: UUID
    operation: AdminOperation
    identity: ProviderPartialIdentity


@dataclass(frozen=True, slots=True)
class CleanupConfirmationResult:
    evidence_id: UUID
    attempt_id: UUID
    mapping_id: UUID
    attempt_state: AttemptState
    chain_state: ChainState
    replayed: bool


@dataclass(frozen=True, slots=True)
class CleanupAuthorization:
    scope: ProviderScope
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class PolicyPublicationResult:
    global_epochs: tuple[UUID, ...]
    scope_epochs: tuple[UUID, ...]
