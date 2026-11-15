"""Fail-closed reader until the usage observation producer is installed."""
from datetime import datetime
from uuid import UUID

from .contracts import SttReadiness


def read_stt_readiness(*, org_id: int, mapping_id: UUID, at: datetime) -> SttReadiness:
    return SttReadiness(org_id, mapping_id, "not_initialized", at, None, None, None, "reader_missing")
