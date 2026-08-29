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
    # Customer-user role (ADMIN/MEMBER) for CUSTOMER actors; None for staff/device/service.
    role: str | None = None


# Cookie carrying the opaque account session token for browser clients (HttpOnly/Secure/SameSite).
ACCOUNT_SESSION_COOKIE = "selahcue_account_session"


IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{12,128}$")

# C0 and C1 control characters, NUL included. Caller-supplied text carrying one of these is
# refused at the service boundary rather than handed to the database, because the two engines
# disagree about it and BOTH answers are wrong:
#
#   Postgres raises `DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes`. That
#   is an unmapped exception, so it escapes as a bare 500-shaped failure that
#   `safe_graphql_error` flattens to the generic "The request is invalid." — masked, unlogged,
#   and indistinguishable from ordinary bad input, which is precisely what the comment beside
#   `MIN_REASON_LENGTH` argues against.
#
#   SQLite raises nothing and STORES the NUL. A control character then sits in the row, and in
#   `feature_scope`'s case travels into a signed manifest cached offline until the licence
#   expires.
#
# Refusing up front is engine-independent, which is the point: catching `DataError` instead
# would run only on Postgres, leaving the SQLite path — the one every local `pytest` takes —
# never executing the handler at all, so a test written for it would pass without exercising
# it. Same lesson as the 0004/0005 migration split.
CONTROL_CHARACTERS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def has_control_characters(value: str) -> bool:
    """True when `value` carries a C0/C1 control character (NUL included)."""
    return bool(CONTROL_CHARACTERS_RE.search(value))


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


def _read_account_session_token(request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer ") :].strip()
        if token:
            return token
    cookie = request.COOKIES.get(ACCOUNT_SESSION_COOKIE)
    return cookie.strip() if cookie else None


def actor_from_request(request) -> ActorContext | None:
    # Production customer auth: an opaque account session token (Authorization: Bearer, or the
    # HttpOnly cookie) resolves to a CUSTOMER actor. This is the sole customer authenticator once
    # header-trust is disabled in prod.
    token = _read_account_session_token(request)
    if token:
        # Lazy import: accounts.services imports this module, so import here to avoid a cycle.
        from selahcue_api.apps.accounts.services import actor_from_session_token

        actor = actor_from_session_token(token)
        if actor is not None:
            return actor

    # Dev/test bridge ONLY: trusted actor headers (staff/device), gated by settings and never
    # enabled in production (SELAHCUE_TRUST_ACTOR_HEADERS=false).
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


def require_customer_role(actor: ActorContext | None, role: str) -> ActorContext:
    """Authorise a CUSTOMER actor of a specific role (e.g. ADMIN for device management, FR-137).
    Distinct codes: no actor → UNAUTHENTICATED; wrong kind or insufficient role → PERMISSION_DENIED."""
    if actor is None:
        raise SafeAPIError(ErrorCode.UNAUTHENTICATED)
    if actor.kind is not ActorKind.CUSTOMER:
        raise SafeAPIError(ErrorCode.PERMISSION_DENIED)
    if actor.role != role:
        raise SafeAPIError(ErrorCode.PERMISSION_DENIED)
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
    # Checked AFTER the collapse above, which already removes tab, newline and carriage
    # return — so anything still in this class is a genuine control character. NUL is the one
    # that matters: `str.split()` does not treat it as whitespace, so it survives the collapse
    # and reaches the database, where Postgres refuses the write and SQLite stores it.
    #
    # This is the single choke point for `reason` across every governed writer — issuance, the
    # two catalogue writers and the licence state machine — so it is fixed once here rather
    # than at each caller.
    if has_control_characters(cleaned):
        raise SafeAPIError(
            ErrorCode.VALIDATION_FAILED,
            "Reason contains a control character. Supply the reason as plain text.",
        )
    return cleaned
