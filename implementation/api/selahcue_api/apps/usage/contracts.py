from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID

from selahcue_api.apps.catalogue.contracts import EffectivePlan

Meter = Literal["stt", "notes"]


class ReservationState(StrEnum):
    RESERVED = "RESERVED"
    ISSUED = "ISSUED"
    SETTLED = "SETTLED"
    RELEASED = "RELEASED"


class ReservationRejected(Exception):
    """A coded ledger refusal for the caller to translate at the API boundary."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CloudContext:
    org_id: int
    license_id: int
    device_id: int
    meter: Meter
    effective_plan: EffectivePlan
    provider_mapping_id: UUID | None
    policy_version: str


@dataclass(frozen=True)
class SessionRequest:
    idempotency_key: UUID
    action: Literal["start", "renew"]
    previous_reservation_id: UUID | None
    socket_mode: Literal["new", "existing"]
    retry: bool
    consent_version: str
    policy_version: str


@dataclass(frozen=True)
class ReservationDecision:
    reservation_id: UUID
    state: ReservationState
    units: int
    authorized_from: datetime
    authorized_until: datetime
    retry_count: int


@dataclass(frozen=True)
class QuotaSnapshot:
    meter: Meter
    limit: int
    settled: int
    held: int
    carried_debt: int
    remaining: int
    as_of: datetime
    resets_at: datetime
    status: Literal["current_observed", "stale", "not_initialized"]


@dataclass(frozen=True)
class UTCInterval:
    start: datetime
    end: datetime

    def __post_init__(self):
        if (
            self.start.utcoffset() != timedelta(0)
            or self.end.utcoffset() != timedelta(0)
            or self.start >= self.end
        ):
            raise ValueError("Expected increasing UTC bounds")


@dataclass(frozen=True)
class DeliveryCreditResult:
    created: bool
    credited_units: int
    week_id: int


@dataclass(frozen=True, slots=True)
class SttReadiness:
    org_id: int
    mapping_id: UUID
    status: Literal["current_observed", "stale", "not_initialized"]
    checked_at: datetime
    observed_through: datetime | None
    valid_until: datetime | None
    publication_revision: int | None
    blocked_reason: Literal[
        "reader_missing", "coverage_missing", "coverage_stale", "reconciliation_pending",
        "placement_gap", "unattributed_limit",
    ] | None

    def __post_init__(self):
        from selahcue_api.apps.usage.weeks import utc_instant

        if not isinstance(self.checked_at, datetime):
            raise ValueError("Invalid STT readiness check time")
        for field in ("checked_at", "observed_through", "valid_until"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, utc_instant(value))
        if type(self.org_id) is not int or self.org_id <= 0 or type(self.mapping_id) is not UUID:
            raise ValueError("Invalid STT readiness identity")
        if self.publication_revision is not None and (
            type(self.publication_revision) is not int or self.publication_revision <= 0
        ):
            raise ValueError("Invalid STT readiness revision")
        if self.status == "current_observed":
            valid = (
                self.blocked_reason is None and self.publication_revision is not None
                and self.observed_through is not None and self.valid_until is not None
                and self.checked_at < self.valid_until
            )
        else:
            valid = self.status in ("stale", "not_initialized") and self.blocked_reason in (
                "reader_missing", "coverage_missing", "coverage_stale",
                "reconciliation_pending", "placement_gap", "unattributed_limit",
            )
        if not valid:
            raise ValueError("Invalid STT readiness evidence")
