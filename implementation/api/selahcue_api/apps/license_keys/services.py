from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg, CustomerStatus
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus, LicenseKeyType
from selahcue_api.apps.license_keys.state_machine import (
    PRIOR_STATUS,
    LicenseTransitionResult,
    PriorStatusTarget,
    apply_license_status_transition,
)
from selahcue_api.apps.throttling.guards import enforce_budget
from selahcue_api.graphql.context import (
    ActorContext,
    StaffPermission,
    has_control_characters,
    require_reason,
    require_staff_permission,
    validate_idempotency_key,
)
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

logger = logging.getLogger(__name__)

KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
KEY_BODY_GROUPS = 8
KEY_GROUP_SIZE = 4


@dataclass(frozen=True)
class GenerateLicenseKeyData:
    idempotency_key: str
    customer_id: str
    key_type: str
    feature_scope: str
    # The catalogue plan this licence is sold on (DEC-014). REQUIRED, and deliberately a
    # field with no default: a licence issued without one used to fall through to the
    # catalogue's fallback plan, which is the most permissive in the catalogue. Giving this
    # a default would restore that path for every caller that forgets it, which is exactly
    # the failure mode DEC-014 closes.
    plan_code: str
    starts_at: datetime
    expires_at: datetime
    timezone: str
    seat_limit: int
    device_limit: int
    territory: str
    reason: str


@dataclass(frozen=True)
class GenerateLicenseKeyResult:
    license_key: AppLicenseKey
    full_key: str | None
    created: bool


def _validation_error() -> SafeAPIError:
    return SafeAPIError(ErrorCode.VALIDATION_FAILED)


def _clean_license_key(license_key: AppLicenseKey) -> None:
    try:
        license_key.full_clean()
    except ValidationError as error:
        raise _validation_error() from error


def _coerce_datetime(value: datetime) -> datetime:
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone=dt_timezone.utc)
    return value.astimezone(dt_timezone.utc)


def _generate_full_key(key_type: LicenseKeyType) -> str:
    groups = [
        "".join(secrets.choice(KEY_ALPHABET) for _ in range(KEY_GROUP_SIZE))
        for _ in range(KEY_BODY_GROUPS)
    ]
    return f"SC-{key_type.value}-{'-'.join(groups)}"


def _fingerprint(full_key: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        full_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _mask(full_key: str) -> tuple[str, str, str]:
    prefix = full_key[:12]
    suffix = full_key[-4:]
    return prefix, suffix, f"{prefix}...{suffix}"


def generate_license_key(
    actor: ActorContext | None,
    data: GenerateLicenseKeyData,
) -> GenerateLicenseKeyResult:
    staff = require_staff_permission(actor, StaffPermission.GENERATE_LICENSE_KEY)
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    reason = require_reason(data.reason)

    try:
        key_type = LicenseKeyType(data.key_type)
    except ValueError as error:
        raise _validation_error() from error

    starts_at = _coerce_datetime(data.starts_at)
    expires_at = _coerce_datetime(data.expires_at)
    if expires_at <= starts_at:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    if data.seat_limit < 1 or data.device_limit < 1:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

    # These three are stored verbatim on the licence, and `feature_scope` travels on into the
    # SIGNED entitlement manifest as a display label — cached offline until the licence
    # expires. A control character in any of them is refused here rather than at the database,
    # where Postgres raises an unmapped `DataError` and SQLite silently stores the byte. See
    # `CONTROL_CHARACTERS_RE`. `reason` is covered by `require_reason` above; `plan_code` is
    # handled at its lookup below, where the answer must match an unknown code instead.
    for field_name, field_value in (
        ("feature_scope", data.feature_scope),
        ("territory", data.territory),
        ("timezone", data.timezone),
    ):
        if has_control_characters(field_value or ""):
            raise SafeAPIError(
                ErrorCode.VALIDATION_FAILED,
                f"`{field_name}` contains a control character. Supply it as plain text.",
            )

    # DEC-014. Naming a plan is now part of issuing a licence.
    #
    # `resolve_plan_for_license` tries the assignment, then a legacy scope alias, then the
    # designated fallback — and the fallback is the most permissive plan in the catalogue
    # (unlimited screens, unlimited NDI, no watermark), because its job is to freeze what
    # pre-catalogue licences already had. `feature_scope` is free staff text, so before this
    # every licence typed with a scope nobody had aliased landed on that fallback silently,
    # was signed, and was cached offline until expiry. Refusing here is the whole fix: the
    # fallback stays exactly as it is for the rows that legitimately need it, and no NEW row
    # can reach it by accident.
    plan_code = (data.plan_code or "").strip()
    if not plan_code:
        raise SafeAPIError(
            ErrorCode.VALIDATION_FAILED,
            "This licence needs a plan. Choose the catalogue plan it is sold on and pass "
            "its code as `plan_code` — a licence issued without one would silently receive "
            "the catalogue's most permissive grants.",
        )

    with transaction.atomic():
        existing = (
            AppLicenseKey.objects.select_related("customer")
            .filter(generated_by_actor_id=staff.actor_id, idempotency_key=idempotency_key)
            .first()
        )
        if existing is not None:
            return GenerateLicenseKeyResult(license_key=existing, full_key=None, created=False)

        try:
            customer = CustomerOrg.objects.get(id=data.customer_id)
        except (CustomerOrg.DoesNotExist, ValueError) as error:
            raise SafeAPIError(ErrorCode.NOT_FOUND) from error
        if customer.status == CustomerStatus.ARCHIVED:
            raise SafeAPIError(ErrorCode.POLICY_DENIED)

        # Imported here, not at module scope: `catalogue` already reaches back into this app
        # (`catalogue.services._license_key_model`), and a module-level import in this
        # direction would close that loop.
        from selahcue_api.apps.catalogue.models import LicensePlanAssignment, Plan

        # A control character cannot name a plan, so this takes the SAME refusal an ordinary
        # unknown code takes rather than inventing a third outcome. Skipping the query is the
        # whole fix: on Postgres `filter(code="PRO\x00")` raises an unmapped `DataError` that
        # escapes as a masked generic failure, while on SQLite the identical call already
        # returns None and lands exactly here. This makes Postgres agree with SQLite, which is
        # the behaviour that was already correct.
        if has_control_characters(plan_code):
            logger.warning(
                "refused to issue a licence for customer %s: plan_code contains a control "
                "character, so it cannot name a catalogue plan. Refused as an unknown plan. "
                "Requested by actor %s.",
                data.customer_id,
                staff.actor_id,
            )
            plan = None
        else:
            plan = Plan.objects.filter(code=plan_code).first()
        if plan is None:
            raise SafeAPIError(
                ErrorCode.NOT_FOUND,
                f"No catalogue plan has the code {plan_code!r}. Issue the licence on a plan "
                "that exists, or add the plan to the catalogue first.",
            )

        # DEC-014, second half: the fallback cannot be sold ON PURPOSE either.
        #
        # The check above closed the SILENT path onto the fallback. This closes the
        # deliberate one. The designated fallback is a no-regression bridge — its display
        # name is literally "Legacy (pre-catalogue)" — and it is the most permissive plan in
        # the catalogue. A typo or a copied admin call that names it grants unlimited
        # outputs, unlimited NDI and no watermark for the licence's ENTIRE LIFE, signed and
        # cached offline until expiry, with no revocation list to take it back.
        #
        # Keyed on `is_fallback`, never on the code: which plan is the fallback is DATA
        # (FR-544/DEC-008), so designating a different one moves this refusal with it and
        # no tier name is hardcoded here — the invariant `test_product_catalogue_slice.py`
        # sweeps the source for.
        #
        # POLICY_DENIED rather than VALIDATION_FAILED: the request is well formed and the
        # plan really exists, so this is policy refusing a legal request — the same shape as
        # the archived-customer refusal above. It also happens to be the more useful code
        # through GraphQL, where `SAFE_MESSAGES` discards this message: the caller at least
        # gets "The current policy does not allow this action." instead of "The request is
        # invalid.", which is the difference between a hint and nothing.
        if plan.is_fallback:
            # The specific reason has to survive somewhere an operator will actually look,
            # because the GraphQL caller will never see it. Audit rows in this service are
            # written on success only — deliberately, and the code review confirmed that —
            # so a refusal has no audit row to carry it. The log is the diagnosis surface.
            logger.warning(
                "refused to issue a licence for customer %s on plan %r (%s): it is the "
                "catalogue's designated fallback (is_fallback=True), which exists to "
                "preserve what pre-catalogue licences already had and grants the "
                "catalogue's most permissive values. Issue on a sellable plan. "
                "Requested by actor %s.",
                data.customer_id,
                plan.code,
                plan.display_name,
                staff.actor_id,
            )
            raise SafeAPIError(
                ErrorCode.POLICY_DENIED,
                f"Plan {plan.code!r} ({plan.display_name}) is the catalogue's designated "
                "fallback, not a sellable tier. It exists to preserve what licences issued "
                "before the catalogue already had, so it carries the most permissive grants "
                "in the catalogue — a licence issued on it would keep them for its whole "
                "life, cached offline until it expires. Issue this licence on the plan the "
                "customer is actually buying.",
            )

        full_key = _generate_full_key(key_type)
        prefix, suffix, masked_key = _mask(full_key)
        license_key = AppLicenseKey(
            customer=customer,
            key_type=key_type,
            status=LicenseKeyStatus.ISSUED,
            key_prefix=prefix,
            key_suffix=suffix,
            masked_key=masked_key,
            secret_hash=make_password(full_key),
            secret_fingerprint=_fingerprint(full_key),
            starts_at=starts_at,
            expires_at=expires_at,
            timezone=data.timezone.strip() or "UTC",
            feature_scope=data.feature_scope.strip().upper(),
            seat_limit=data.seat_limit,
            device_limit=data.device_limit,
            territory=data.territory.strip().upper(),
            generated_by_actor_id=staff.actor_id,
            generated_reason=reason,
            idempotency_key=idempotency_key,
        )
        _clean_license_key(license_key)
        # Concurrency-safe idempotency: a racing call with the same (actor, idempotency_key) can
        # pass the check above; the unique constraint rejects the loser's INSERT. Catch it in a
        # savepoint and return the winner's key as an idempotent replay (full_key=None) rather than
        # a spurious internal error. (Mirrors `activate_device`.)
        try:
            with transaction.atomic():
                license_key.save()
        except IntegrityError:
            existing = (
                AppLicenseKey.objects.select_related("customer")
                .filter(generated_by_actor_id=staff.actor_id, idempotency_key=idempotency_key)
                .first()
            )
            if existing is not None:
                return GenerateLicenseKeyResult(license_key=existing, full_key=None, created=False)
            raise _validation_error()

        # Bind the licence to the plan in the SAME transaction as the licence itself, so a
        # licence can never exist without one. An assignment is what `resolve_plan_for_license`
        # consults first, so this — not `feature_scope` — is what the licence now grants.
        # The accountability columns are the issuing staff's own: whoever issued the licence
        # is who chose the plan, and the database refuses the row without them.
        LicensePlanAssignment.objects.create(
            license_key=license_key,
            plan=plan,
            assigned_by_actor_id=staff.actor_id,
            reason=reason,
            idempotency_key=idempotency_key,
        )

        record_audit_event(
            staff,
            action="license_key.generated",
            target_type="app_license_key",
            target_id=str(license_key.id),
            request_id=idempotency_key,
            reason=reason,
            after={
                "customer_id": str(customer.id),
                "key_type": license_key.key_type,
                "status": license_key.status,
                "key_prefix": license_key.key_prefix,
                "key_suffix": license_key.key_suffix,
                "masked_key": license_key.masked_key,
                "feature_scope": license_key.feature_scope,
                # What the licence actually grants, beside the label that no longer decides
                # it — so the audit row says which plan was chosen at issuance.
                "plan_code": plan.code,
                "starts_at": license_key.starts_at.isoformat(),
                "expires_at": license_key.expires_at.isoformat(),
                "seat_limit": license_key.seat_limit,
                "device_limit": license_key.device_limit,
                "territory": license_key.territory,
            },
        )
        return GenerateLicenseKeyResult(license_key=license_key, full_key=full_key, created=True)


# --- Suspend / reinstate (86ak5mn0c: FR-504, FR-510, FLOW-506; D3 / DEC-010) -----------------
#
# Both mutations are THIN on purpose. The transition table, the row lock, the prior-status
# bookkeeping, the request-level retry recognition and the audit row all live in
# `state_machine.apply_license_status_transition`; what is added here is the half the writer
# deliberately does not do (PRD §19: "§15 actor gating + FR-508 audit"): who may ask, how
# often, and which licence.
#
# Retry semantics, for the console author. The idempotency key is per USER INTENT: send a new
# key for each deliberate action and re-send the same key only to retry that action. A retry of
# a request that took effect applies nothing and reports the licence's CURRENT state with
# `changed=False` (the original audit row is attached, and the GraphQL payload says
# `replayed=true`), even if another staff action has moved the licence on since.
# `changed=False` therefore means either "already in that state" or "this request already took
# effect". Known limit: a request that was itself a
# no-op (already suspended) wrote no audit row, so a later retry of it is not recognised and
# applies if the licence has since moved. Send ONE mutation per HTTP request: the throttle
# applies per call, and a batch of aliased mutations fails as a whole when it runs out of budget.

# Shared by every licence-lifecycle mutation; see the setting's own comment.
LIFECYCLE_BUDGET = (30, 60)
LIFECYCLE_BUDGET_SCOPE = "admin_licence_lifecycle"

# `AppLicenseKey.id` is a BigAutoField: 19 digits can already overflow it, and an id that long
# cannot name a row anyway, so it takes the same refusal as any other id that names nothing.
# Defence in depth only: Django 6.1 answers a lookup past the column's range with no row, so
# removing this cap would not change behaviour today (it is unguarded by a test on purpose).
_MAX_LICENSE_KEY_ID_DIGITS = 18


@dataclass(frozen=True)
class SuspendLicenseKeyData:
    idempotency_key: str
    license_key_id: str
    reason: str


@dataclass(frozen=True)
class ReinstateLicenseKeyData:
    idempotency_key: str
    license_key_id: str
    reason: str


def _require_autocommit() -> None:
    """Refuse to run inside a caller's transaction.

    The writer records a refusal's DENIED audit row AFTER its own `atomic()` unwinds, so the
    row commits on its own — unless this call sits inside a wider transaction and the refusal
    propagates, in which case the denial rolls back with everything else and the one record
    PRD §13 demands for an illegal transition ("refused and audited") is silently lost. Every
    refusal reachable from a staff mutation is exactly that case, so this checks the
    connection instead of trusting a docstring (see "durability of refusals" in
    `state_machine`). The project sets no `ATOMIC_REQUESTS`, so a top-level resolver passes.

    Fails closed BEFORE any change is made. A new caller that really needs both a durable
    denial and a wider transaction needs the agreed `audit` database alias, not an exemption
    here.
    """
    if transaction.get_connection().in_atomic_block:
        logger.error(
            "a licence suspend/reinstate was attempted inside an open transaction; refused "
            "because a DENIED audit row written in this state would be rolled back with the "
            "caller's transaction (durability of refusals, state_machine docstring)."
        )
        raise SafeAPIError(ErrorCode.INTERNAL)


def _enforce_lifecycle_budget(staff: ActorContext) -> None:
    """Spend one unit of the acting staff member's lifecycle budget (FR-539).

    Keyed on a digest of the actor id rather than the raw id: it lands in the cache key, and
    under the header bridge an id is caller-supplied text. Called AFTER the permission gate,
    so the identity being counted has already been authorised and an unauthenticated caller
    cannot spend (or exhaust) a real staff member's budget.
    """
    identity = hashlib.sha256(staff.actor_id.encode("utf-8")).hexdigest()[:32]
    enforce_budget(
        LIFECYCLE_BUDGET_SCOPE,
        identity,
        "SELAHCUE_THROTTLE_ADMIN_LICENSE_LIFECYCLE",
        LIFECYCLE_BUDGET,
    )


def _get_license_key_or_not_found(raw_id: str) -> AppLicenseKey:
    """Resolve a licence reference. Anything that does not name a row — unknown, malformed,
    negative, signed, non-ASCII digits, absurdly long — is the SAME NOT_FOUND, so the refusal
    says nothing about which ids exist or what shape the lookup expects. Whitespace around an
    otherwise valid id is ignored (`str.strip`, which is wider than the ASCII space: it also
    drops some control and Unicode space characters, none of which can be part of an id).

    No tenant filter: staff authority is platform-wide (§15), and a CUSTOMER or DEVICE actor
    never reaches this line because `require_staff_permission` refuses them first, with the
    same answer whether or not the licence exists.
    """
    cleaned = (raw_id or "").strip()
    if (
        not cleaned
        or len(cleaned) > _MAX_LICENSE_KEY_ID_DIGITS
        or not (cleaned.isascii() and cleaned.isdecimal())
    ):
        raise SafeAPIError(ErrorCode.NOT_FOUND)
    try:
        return AppLicenseKey.objects.select_related("customer").get(pk=int(cleaned))
    except AppLicenseKey.DoesNotExist as error:
        raise SafeAPIError(ErrorCode.NOT_FOUND) from error


def _lifecycle_mutation(
    actor: ActorContext | None,
    *,
    permission: StaffPermission,
    to_status: LicenseKeyStatus | PriorStatusTarget,
    raw_idempotency_key: str,
    raw_license_key_id: str,
    raw_reason: str,
) -> LicenseTransitionResult:
    staff = require_staff_permission(actor, permission)
    _require_autocommit()
    _enforce_lifecycle_budget(staff)
    idempotency_key = validate_idempotency_key(raw_idempotency_key)
    reason = require_reason(raw_reason)
    license_key = _get_license_key_or_not_found(raw_license_key_id)

    return apply_license_status_transition(
        license_key,
        to_status=to_status,
        actor=staff,
        reason=reason,
        request_id=idempotency_key,
        # Retry recognition happens inside the writer, under the row lock (see its docstring).
        recognise_retry=True,
    )


def suspend_license_key(
    actor: ActorContext | None, data: SuspendLicenseKeyData
) -> LicenseTransitionResult:
    """Put a licence on a reversible hold (FR-504). Staff only, reason mandatory.

    Decided (D3 / DEC-010): SUSPENDED is soft. This writes the status and nothing else — it
    does not touch a device token, and it must not: running devices keep working, new
    activations and manifest issuance are refused because SUSPENDED is outside
    `ACTIVATABLE_KEY_STATUSES`, and the already-cached offline entitlement runs to its own
    expiry (RISK-501). The pre-suspension status is recorded by the writer in the same
    UPDATE, which is what lets `reinstate_license_key` return to it.

    Suspending an already-SUSPENDED licence is a no-op (`changed=False`, no second audit
    row). Suspending from a status the table does not allow (REVOKED, ARCHIVED) is refused
    with CONFLICT and one durable DENIED audit row.
    """
    return _lifecycle_mutation(
        actor,
        permission=StaffPermission.SUSPEND_LICENSE_KEY,
        to_status=LicenseKeyStatus.SUSPENDED,
        raw_idempotency_key=data.idempotency_key,
        raw_license_key_id=data.license_key_id,
        raw_reason=data.reason,
    )


def reinstate_license_key(
    actor: ActorContext | None, data: ReinstateLicenseKeyData
) -> LicenseTransitionResult:
    """Lift a suspension, returning the licence to EXACTLY the status it held before (FR-510).

    The target is `PRIOR_STATUS` — stored data, read from the row under the writer's lock,
    never a constant. A licence that is not suspended, or whose recorded prior status is
    missing or unusable, is refused with CONFLICT and a durable DENIED row; it is never
    defaulted to ACTIVATED. Devices need no re-activation: their tokens never died, so the
    next `license:refresh` simply reports the licence valid again.
    """
    return _lifecycle_mutation(
        actor,
        permission=StaffPermission.REINSTATE_LICENSE_KEY,
        to_status=PRIOR_STATUS,
        raw_idempotency_key=data.idempotency_key,
        raw_license_key_id=data.license_key_id,
        raw_reason=data.reason,
    )
