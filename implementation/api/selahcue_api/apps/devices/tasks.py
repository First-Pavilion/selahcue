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
from django.db.models import Q
from django.utils import timezone

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.devices.models import DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.services import ACTIVATABLE_KEY_STATUSES
from selahcue_api.apps.license_keys.models import LicenseKeyStatus
from selahcue_api.graphql.context import ActorContext, ActorKind

# The cascade acts on its own authority, on a schedule, with no request behind it.
CASCADE_ACTOR_ID = "revocation-cascade"


def _licences_whose_tokens_survive() -> Q:
    """Licences whose device tokens the cascade LEAVES alone.

    Every activatable status, plus SUSPENDED **when it was suspended from an activatable
    status**. Decided (D3 / DEC-010, FR-504): a suspension is a reversible commercial hold, so
    "running devices keep working" — refusing a NEW activation and killing an EXISTING token
    are separate mechanisms, and suspension does only the first. Before this the cascade
    treated SUSPENDED exactly like REVOKED (both sit outside the activatable set), which would
    have made the suspend mutation token-killing the moment it shipped.

    The qualifier matters: suspending an EXPIRED or CONVERTED licence must not rescue tokens
    the cascade would otherwise have killed. A licence suspended from such a status keeps
    being treated as the status it came from, so its tokens still die — and the exemption
    stays deny-by-default, keyed on the recorded `prior_status`.

    Narrowed here, in the smallest possible way, because 86ak5mn0c cannot honour its own
    acceptance criteria (tokens survive a suspension; SUSPENDED and REVOKED differ observably)
    otherwise. The rest of the cascade rework — row locking and the key-driven scan — stays on
    86ak1099u.
    """
    activatable = list(ACTIVATABLE_KEY_STATUSES)
    return Q(device__license_key__status__in=activatable) | Q(
        device__license_key__status=LicenseKeyStatus.SUSPENDED,
        device__license_key__prior_status__in=activatable,
    )


def cascade_license_revocations(batch_size: int = 500) -> int:
    """Revoke ACTIVE device tokens whose licence has left an activatable status — except a
    licence SUSPENDED from an activatable status, a reversible hold that must not kill a
    running device (D3).

    Idempotent: already-revoked tokens are excluded by the `status=ACTIVE` filter, so a
    redelivered run (CELERY_TASK_ACKS_LATE) finds nothing and writes no second audit row.
    Bounded by `batch_size` so a large tenant cannot produce an unbounded query or an
    unbounded working set — beat re-runs hourly and drains the remainder.
    """
    stale = list(
        DeviceToken.objects.select_related("device__license_key")
        .filter(status=DeviceTokenStatus.ACTIVE)
        .exclude(_licences_whose_tokens_survive())
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
