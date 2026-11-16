from dataclasses import dataclass


@dataclass(frozen=True)
class EffectivePlan:
    plan_id: int
    rank: int
    catalogue_revision: int
    stt_seconds_limit: int
    notes_limit: int
    source: str
