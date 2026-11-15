"""Immutable provider metadata and finite internal errors."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
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
class ProviderDeploymentPolicy:
    schema_version: Literal[1]
    accounting_mode: Literal["observed_records_with_late_corrections"]
    accepted_by: str
    accepted_at: datetime
    scopes: tuple[ProviderScopePolicy, ...]


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
