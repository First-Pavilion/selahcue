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
