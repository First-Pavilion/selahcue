"""The request-owned audit outcome, persisted with the authorization decision."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from selahcue_api.apps.audit.models import AuditResult
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.usage.contracts import SessionRequest
from selahcue_api.apps.usage.services import remaining
from selahcue_api.apps.usage.weeks import utc_instant
from selahcue_api.graphql.context import ActorContext, ActorKind


def wire_time(at: datetime) -> str:
    return utc_instant(at).isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass
class OutcomeRecorder:
    device_public_id: str
    org_id: int
    request: SessionRequest
    request_receipt_id: UUID = field(default_factory=uuid4)
    _used: bool = field(default=False, init=False)

    def record(self, *, org, at, week, row=None, replay=False, reason=None):
        if self._used:
            raise RuntimeError("STT outcome already finalized")
        self._used = True
        snapshot = remaining(org, at)[0]
        return record_audit_event(
            ActorContext(kind=ActorKind.DEVICE, actor_id=self.device_public_id),
            action="cloud.stt.session", target_type="CustomerOrg", target_id=str(self.org_id),
            request_id=str(self.request.idempotency_key), reason=reason.value if reason else "",
            after={
                "meter": "stt", "week_id": week.pk if week else None,
                "limit": snapshot.limit, "remaining": snapshot.remaining,
                "reservation_id": str(row.pk) if row else None,
                "request_receipt_id": str(self.request_receipt_id),
                "action": self.request.action, "replay": replay, "decision_at": wire_time(at),
                "delivery": "unconfirmed",
            },
            result=AuditResult.DENIED if reason else AuditResult.SUCCESS,
            source_surface="native_public_cloud",
        )
