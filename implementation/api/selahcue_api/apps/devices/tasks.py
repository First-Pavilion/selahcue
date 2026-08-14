"""Periodic revocation cascade.

Revoking a licence key does not cascade to already-issued device tokens: the token's
expiry is the LICENCE's expiry, and `authenticate_device_token` never consults licence
status. This job closes that gap.

Pairs with the entitlement manifest's issuance gate — the gate stops re-issue, this stops
the existing token. **Never blanks live output (NFR-024):** revoking a token stops future
API calls; the desktop keeps its cached entitlement until the licence expires.

Lives in `tasks.py` because that is the only module name Celery's `autodiscover_tasks()`
looks for in an installed app. A task parked anywhere else is scheduled by beat and never
registered by the worker.
"""

from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.devices.models import DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.services import ACTIVATABLE_KEY_STATUSES
from selahcue_api.graphql.context import ActorContext, ActorKind

# The cascade acts on its own authority, on a schedule, with no request behind it.
CASCADE_ACTOR_ID = "revocation-cascade"


def cascade_license_revocations(batch_size: int = 500) -> int:
    """Revoke ACTIVE device tokens whose licence has left an activatable status.

    Idempotent: already-revoked tokens are excluded by the `status=ACTIVE` filter, so a
    redelivered run (CELERY_TASK_ACKS_LATE) finds nothing and writes no second audit row.
    Bounded by `batch_size` so a large tenant cannot produce an unbounded query or an
    unbounded working set — beat re-runs hourly and drains the remainder.
    """
    stale = list(
        DeviceToken.objects.select_related("device__license_key")
        .filter(status=DeviceTokenStatus.ACTIVE)
        .exclude(device__license_key__status__in=list(ACTIVATABLE_KEY_STATUSES))
        .order_by("id")[:batch_size]
    )
    now = timezone.now()
    changed = 0
    for token in stale:
        with transaction.atomic():
            token.status = DeviceTokenStatus.REVOKED
            token.save(update_fields=["status", "updated_at"])
            record_audit_event(
                ActorContext(kind=ActorKind.SERVICE, actor_id=CASCADE_ACTOR_ID),
                action="device_token.revoked_by_cascade",
                target_type="device_token",
                target_id=str(token.id),
                request_id=f"cascade-{now.isoformat()}",
                reason=f"licence status {token.device.license_key.status} is not activatable",
                source_surface="desktop_v1",
                after={"status": DeviceTokenStatus.REVOKED.value},
            )
        changed += 1
    return changed


@shared_task(name="devices.cascade_license_revocations")
def cascade_license_revocations_task() -> int:
    return cascade_license_revocations()
