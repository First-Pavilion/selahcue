from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from django.conf import settings

from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


class ActorKind(str, Enum):
    STAFF = "staff"
    CUSTOMER = "customer"
    DEVICE = "device"
    SERVICE = "service"


class StaffPermission(str, Enum):
    VIEW_PLATFORM_HEALTH = "view_platform_health"
    VIEW_CUSTOMERS = "view_customers"
    MANAGE_CUSTOMERS = "manage_customers"
    GENERATE_LICENSE_KEY = "generate_license_key"
    EXTEND_LICENSE_KEY = "extend_license_key"
    REVOKE_LICENSE_KEY = "revoke_license_key"
    GRANT_ENTITLEMENT = "grant_entitlement"
    REVOKE_ENTITLEMENT = "revoke_entitlement"
    VIEW_DIAGNOSTICS = "view_diagnostics"
    VIEW_AUDIT = "view_audit"


@dataclass(frozen=True)
class ActorContext:
    kind: ActorKind
    actor_id: str
    org_id: str | None = None
    staff_permissions: frozenset[StaffPermission] = frozenset()


IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{12,128}$")


def parse_staff_permissions(raw_permissions: str | Iterable[str] | None) -> frozenset[StaffPermission]:
    if raw_permissions is None:
        return frozenset()
    if isinstance(raw_permissions, str):
        values = [value.strip() for value in raw_permissions.split(",")]
    else:
        values = [str(value).strip() for value in raw_permissions]

    permissions: set[StaffPermission] = set()
    for value in values:
        if not value:
            continue
        try:
            permissions.add(StaffPermission(value))
        except ValueError:
            continue
    return frozenset(permissions)


def actor_from_request(request) -> ActorContext | None:
    if not settings.SELAHCUE_TRUST_ACTOR_HEADERS:
        return None

    kind_value = request.headers.get("X-SelahCue-Actor-Kind")
    actor_id = request.headers.get("X-SelahCue-Actor-Id")
    if not kind_value or not actor_id:
        return None
    try:
        kind = ActorKind(kind_value)
    except ValueError:
        return None
    return ActorContext(
        kind=kind,
        actor_id=actor_id,
        org_id=request.headers.get("X-SelahCue-Org-Id"),
        staff_permissions=parse_staff_permissions(request.headers.get("X-SelahCue-Staff-Permissions")),
    )


def actor_from_info(info) -> ActorContext | None:
    context = getattr(info, "context", None)
    request = getattr(context, "request", None)
    if request is not None:
        return actor_from_request(request)
    actor = getattr(context, "actor", None)
    return actor if isinstance(actor, ActorContext) else None


def require_staff_permission(
    actor: ActorContext | None,
    permission: StaffPermission,
) -> ActorContext:
    if actor is None:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if actor.kind is not ActorKind.STAFF:
        raise SafeAPIError(ErrorCode.PERMISSION_DENIED)
    if permission not in actor.staff_permissions:
        raise SafeAPIError(ErrorCode.PERMISSION_DENIED)
    return actor


def require_customer_org(actor: ActorContext | None, org_id: str) -> ActorContext:
    if actor is None:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if actor.kind is not ActorKind.CUSTOMER:
        raise SafeAPIError(ErrorCode.PERMISSION_DENIED)
    if not actor.org_id or actor.org_id != org_id:
        raise SafeAPIError(ErrorCode.NOT_FOUND)
    return actor


def validate_idempotency_key(value: str) -> str:
    cleaned = value.strip()
    if not IDEMPOTENCY_RE.fullmatch(cleaned):
        raise SafeAPIError(
            ErrorCode.VALIDATION_FAILED,
            "Idempotency key must be 12-128 characters using letters, numbers, '.', '_', ':', or '-'.",
        )
    return cleaned


def require_reason(value: str, *, min_length: int = 8, max_length: int = 1000) -> str:
    cleaned = " ".join(value.strip().split())
    if not min_length <= len(cleaned) <= max_length:
        raise SafeAPIError(
            ErrorCode.VALIDATION_FAILED,
            f"Reason must be between {min_length} and {max_length} characters.",
        )
    return cleaned
