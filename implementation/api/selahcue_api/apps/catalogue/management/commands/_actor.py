"""Shared actor construction for the catalogue operator commands.

**The actor is self-asserted.** These commands run on a box where the operator already has
the database and the code, so a CLI cannot meaningfully authenticate anybody — `--actor` is
free text and the permission it grants itself is a formality. That is acceptable for an
operator tool and NOT acceptable for a network surface: when the admin GraphQL gains these
mutations the actor must come from `actor_from_info`, never from an argument.

The value still matters: it is what lands in the audit trail, so "who changed Pro's STT
allowance" has an answer even though the answer is only as trustworthy as shell access.
"""

from __future__ import annotations

import hashlib

from django.core.management.base import CommandError

from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission


def staff_actor(actor_id: str) -> ActorContext:
    cleaned = (actor_id or "").strip()
    if not cleaned:
        raise CommandError("--actor must name the person making this change; it is audited.")
    return ActorContext(
        kind=ActorKind.STAFF,
        actor_id=cleaned,
        staff_permissions=frozenset({StaffPermission.GRANT_ENTITLEMENT}),
    )


def default_idempotency_key(prefix: str, *parts: str) -> str:
    """A deterministic key derived from the arguments, safe for `validate_idempotency_key`.

    Built by HASHING the parts rather than concatenating them: a raw value like
    `--value "quite a lot"` contains spaces, and the pasted-together form would then be
    rejected for its punctuation — surfacing a malformed *value* as a confusing complaint
    about the idempotency key, which is the opposite of a useful error.

    Deterministic on purpose: re-running the identical command is a replay, not a second
    change. Pass `--idempotency-key` explicitly to force a distinct one.
    """
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"{prefix}-{digest}"
