from __future__ import annotations

from typing import Any

from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.graphql.context import ActorContext
from selahcue_api.graphql.redaction import assert_no_restricted_payload_fields, redact_public_payload


def record_audit_event(
    actor: ActorContext,
    *,
    action: str,
    target_type: str,
    target_id: str,
    request_id: str,
    reason: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    result: AuditResult = AuditResult.SUCCESS,
    source_surface: str = "admin_graphql",
) -> AuditEvent:
    safe_before = redact_public_payload(before or {})
    safe_after = redact_public_payload(after or {})
    assert_no_restricted_payload_fields(safe_before)
    assert_no_restricted_payload_fields(safe_after)

    return AuditEvent.objects.create(
        actor_kind=actor.kind.value,
        actor_id=actor.actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        result=result,
        request_id=request_id,
        source_surface=source_surface,
        before=safe_before,
        after=safe_after,
    )
