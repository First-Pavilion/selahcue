"""Metadata-only boundaries between the usage reader, durable jobs and ledger."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from selahcue_api.apps.providers.contracts import ProviderKind, ProviderScope

from .contracts import UTCInterval


class DGCompletion(StrEnum):
    COMPLETE = "COMPLETE"
    COMPLETION_UNKNOWN = "COMPLETION_UNKNOWN"


class Attribution(StrEnum):
    EXACT_KEY = "EXACT_KEY"
    PROJECT_ONLY = "PROJECT_ONLY"
    UNATTRIBUTED = "UNATTRIBUTED"
    DISCREPANCY = "DISCREPANCY"


class ScanPurpose(StrEnum):
    INITIAL = "INITIAL"
    RECENT = "RECENT"
    HEALTH = "HEALTH"
    HISTORY = "HISTORY"


class ScanState(StrEnum):
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class UsageHealthState(StrEnum):
    CURRENT = "CURRENT"
    BLOCKED = "BLOCKED"
    UNRESOLVED = "UNRESOLVED"


class UsageFailureCode(StrEnum):
    CONFIG_UNAVAILABLE = "CONFIG_UNAVAILABLE"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    SCOPE_MISSING = "SCOPE_MISSING"
    INVALID_CURSOR = "INVALID_CURSOR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    TRANSPORT_TIMEOUT = "TRANSPORT_TIMEOUT"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    CLAIM_STALE = "CLAIM_STALE"
    RETRIES_EXHAUSTED = "RETRIES_EXHAUSTED"
    HISTORY_UNAVAILABLE = "HISTORY_UNAVAILABLE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    METRIC_UNKNOWN = "METRIC_UNKNOWN"
    ARITHMETIC_OVERFLOW = "ARITHMETIC_OVERFLOW"
    PLACEMENT_GAP = "PLACEMENT_GAP"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    DATABASE_BUSY = "DATABASE_BUSY"
    PUBLICATION_FAILED = "PUBLICATION_FAILED"
    TASK_BUDGET = "TASK_BUDGET"


class HealthReason(StrEnum):
    THRESHOLD = "THRESHOLD"
    UNQUANTIFIABLE = "UNQUANTIFIABLE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    COVERAGE_MISSING = "COVERAGE_MISSING"
    COVERAGE_STALE = "COVERAGE_STALE"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    SCOPE_MISSING = "SCOPE_MISSING"


class ObservationIssue(StrEnum):
    METRIC_UNKNOWN = "METRIC_UNKNOWN"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    PLACEMENT_GAP = "PLACEMENT_GAP"
    ARITHMETIC_OVERFLOW = "ARITHMETIC_OVERFLOW"
    ANCIENT_FACT = "ANCIENT_FACT"


class UsageProfile(StrEnum):
    DG_LISTEN_V1 = "DG_LISTEN_V1"
    OA_COMPLETIONS_1H_V1 = "OA_COMPLETIONS_1H_V1"


class RetentionKind(StrEnum):
    PAGE_DETAIL = "PAGE_DETAIL"
    SUPERSEDED_VERSION = "SUPERSEDED_VERSION"
    TERMINAL_SCAN_WORK = "TERMINAL_SCAN_WORK"
    NORMALIZED_RECORD = "NORMALIZED_RECORD"
    TERMINAL_RESERVATION = "TERMINAL_RESERVATION"
    EXPIRED_WEEK = "EXPIRED_WEEK"


class UsageRejected(Exception):
    def __init__(self, code: UsageFailureCode):
        self.code = code
        super().__init__(code)


class UsageReadFailed(UsageRejected):
    pass


@dataclass(frozen=True, slots=True)
class DeepgramRequestObservation:
    request_id: str
    project_id: str | None
    api_key_id: str | None
    created_at: datetime
    completion: DGCompletion
    completed_at: datetime | None
    duration_seconds: Decimal | None
    response_code: int | None


@dataclass(frozen=True, slots=True)
class OpenAIBucketDimensions:
    project_id: str | None
    api_key_id: str | None
    model: str | None
    batch: bool | None


@dataclass(frozen=True, slots=True)
class OpenAIBucketMetrics:
    input_tokens: int | None
    output_tokens: int | None
    input_cached_tokens: int | None
    input_audio_tokens: int | None
    input_cached_audio_tokens: int | None
    output_audio_tokens: int | None
    num_model_requests: int | None


@dataclass(frozen=True, slots=True)
class OpenAIUsageBucketObservation:
    start: datetime
    end: datetime
    dimensions: OpenAIBucketDimensions
    metrics: OpenAIBucketMetrics


ProviderObservation = DeepgramRequestObservation | OpenAIUsageBucketObservation


@dataclass(frozen=True, slots=True)
class UsagePageReceipt:
    scope: ProviderScope
    interval: UTCInterval
    profile: UsageProfile
    requested_cursor: str | None
    terminal_page_seen: bool
    oa_bucket_starts: tuple[datetime, ...] = ()


@dataclass(frozen=True, slots=True)
class UsagePage:
    records: tuple[ProviderObservation, ...]
    next_cursor: str | None
    receipt: UsagePageReceipt


@dataclass(frozen=True, slots=True)
class ObservedCoverage:
    scan_id: UUID
    scope: ProviderScope
    interval: UTCInterval
    scan_started_at: datetime
    scan_finished_at: datetime
    terminal_page_seen: bool


@dataclass(frozen=True, slots=True)
class IngestResult:
    inserted: int
    revised: int
    duplicates: int
    unattributed: int


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    org_id: int
    corrected_weeks: tuple[int, ...]
    settled_reservations: tuple[UUID, ...]
    observed_through: datetime | None
    blocked_reason: UsageFailureCode | None


@dataclass(frozen=True, slots=True)
class ProviderUsageHealth:
    provider: ProviderKind
    status: UsageHealthState
    checked_at: datetime
    revision: int | None
    valid_until: datetime | None
    reason: HealthReason | None


@dataclass(frozen=True, slots=True)
class MintRecoveryResult:
    attempt_id: UUID
    state: Literal["unchanged", "recovered_unknown", "unavailable"]
    changed: bool


@dataclass(frozen=True, slots=True)
class UsageClaim:
    page_id: int
    lease_id: UUID
    lane_fence: int
    scan_generation: int
    work_id: UUID
    work_generation: int


@dataclass(frozen=True, slots=True)
class AttributionBatchResult:
    next_after: int | None
    scanned: int
    changed: int
    exhausted: bool


@dataclass(frozen=True, slots=True)
class RetentionBatchResult:
    scanned: int
    deleted: int
    deferred: int
    has_more: bool
