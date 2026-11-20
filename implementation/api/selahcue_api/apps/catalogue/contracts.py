from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EffectivePlan:
    plan_id: int
    rank: int
    catalogue_revision: int
    stt_seconds_limit: int
    notes_limit: int
    source: str
    # When the winning plan stops applying. Set only for `source == "staff_grant"` (the
    # grant's end); a licence or fallback plan has no plan-level end of its own.
    ends_at: datetime | None = None
