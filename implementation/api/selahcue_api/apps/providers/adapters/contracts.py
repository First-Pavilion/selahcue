"""Pure typed boundary between provider orchestration and administrative HTTP."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from ..contracts import AdminOperation, ProviderPartialIdentity, ProviderScope, ProvisioningErrorCode, SecretBytes

Collection = Literal["DG_KEYS", "OA_PROJECTS", "OA_SERVICE_ACCOUNTS", "OA_KEYS"]


@dataclass(frozen=True, slots=True)
class AdminRequest:
    operation: AdminOperation
    scope: ProviderScope
    mapping_id: UUID
    attempt_id: UUID
    marker: str
    project_id: str | None
    service_account_id: str | None
    api_key_id: str | None


@dataclass(frozen=True, slots=True)
class InventoryRequest:
    collection: Collection
    scope: ProviderScope
    project_id: str | None
    cursor: str | None


@dataclass(frozen=True, slots=True)
class Created:
    identity: ProviderPartialIdentity
    secret: SecretBytes | None = field(repr=False)
    expires_at: datetime | None
    provider_request_id: str | None
    created_at: datetime | None


@dataclass(frozen=True, slots=True)
class NotCreated:
    code: ProvisioningErrorCode
    proof: Literal["LOCAL_NOT_SENT"] = "LOCAL_NOT_SENT"


@dataclass(frozen=True, slots=True)
class MutationUnknown:
    code: ProvisioningErrorCode
    known_identity: ProviderPartialIdentity


@dataclass(frozen=True, slots=True)
class CleanupConfirmed:
    identity: ProviderPartialIdentity
    provider_request_id: str | None


@dataclass(frozen=True, slots=True)
class InventoryRecord:
    external_id: str
    marker: str | None
    created_at: datetime | None
    status: Literal["active", "expired", "archived", "unknown"]
    owner_id: str | None


@dataclass(frozen=True, slots=True)
class InventoryPage:
    records: tuple[InventoryRecord, ...]
    next_cursor: str | None
    terminal_page_seen: bool


@dataclass(frozen=True, slots=True)
class ReadFailed:
    code: ProvisioningErrorCode
