from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg, CustomerStatus
from selahcue_api.apps.audit.models import AuditResult
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.catalogue.models import LicensePlanAssignment, Plan
from selahcue_api.apps.catalogue.services import plan_device_instances_for_issuance
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus, LicenseKeyType
from selahcue_api.apps.license_keys.state_machine import (
    AUDIT_TARGET_TYPE,
    EXTEND_ACTION,
    PRIOR_STATUS,
    IllegalLicenseTransition,
    LicenseTransitionResult,
    PriorStatusTarget,
    apply_license_status_transition,
    earlier_success_event,
)
from selahcue_api.apps.throttling.guards import enforce_budget, spend_budget
from selahcue_api.apps.throttling.services import BudgetOutcome
from selahcue_api.graphql.context import (
    ACTOR_ID_MAX_LENGTH,
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
    # No `device_limit` here, on purpose (86ak5mn0m). The number of device instances a licence
    # admits is the PLAN's `device_instances`, copied onto the key at issuance; a staff-typed
    # value beside it is how a licence came to be displayed as one thing and enforced as
    # another. Whether one licence should ever get a count different from its plan is an open
    # owner question, and if it is ever yes it belongs in the catalogue as a plan row, not
    # here as a number typed per issuance.
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


# A full licence key as `_generate_full_key` writes it: `SC-<TYPE>-` then eight groups of four.
# Built from the same constants so a change to the key shape moves this with it. Case-insensitive
# because the person pasting it may have retyped it. It matches the canonical spelling only: a
# key broken across lines or re-grouped by hand evades it, which is the honest limit of a check
# that refuses on a pattern.
_FULL_KEY_IN_TEXT_RE = re.compile(
    rf"SC-[A-Z_]+(?:-[{KEY_ALPHABET}]{{{KEY_GROUP_SIZE}}}){{{KEY_BODY_GROUPS}}}", re.IGNORECASE
)


def _require_reason_without_a_credential(raw_reason: str) -> str:
    """`require_reason`, and refuse a reason that contains a full licence key.

    FLOW-504 is "leaked key kill", so the person writing the reason has the leaked key in front
    of them and pasting it is the natural slip. The audit trail is append-only and NFR-508
    allows no plaintext licensing credential at rest, so a key that lands there can never be
    taken back. Refused rather than redacted: quietly rewriting the reason would falsify the
    record, and a refusal tells the person what to do instead (name the licence by its masked
    key or its id).
    """
    reason = require_reason(raw_reason)
    if _FULL_KEY_IN_TEXT_RE.search(reason):
        raise SafeAPIError(
            ErrorCode.VALIDATION_FAILED,
            "The reason contains a full licence key. Refer to the licence by its masked key or "
            "its id instead; the audit trail keeps what is written here permanently.",
        )
    return reason


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


# Statuses whose key can still be used, or can still come back into use, so a second key for
# the same org may not overlap its dates. REVOKED, ARCHIVED and CONVERTED are over and do not
# block. A status added to `LicenseKeyStatus` later is in NEITHER list in the test until
# someone decides, and `tests/test_one_valid_key_per_org.py` fails on that, so the choice
# cannot be skipped. The same file derives, from `LEGAL_TRANSITIONS`, every status a key can
# be revived from and fails if one is missing here, so this set cannot drift from the state
# machine either.
#
# EXPIRED blocks because the state machine still allows EXPIRED -> ACTIVATED (a late
# renewal), so an expired key is not yet a dead one. SUSPENDED is a reversible hold.
KEY_STATUSES_THAT_BLOCK_AN_OVERLAPPING_KEY = frozenset(
    {
        LicenseKeyStatus.ISSUED,
        LicenseKeyStatus.ACTIVATED,
        LicenseKeyStatus.EXPIRING,
        LicenseKeyStatus.EXPIRED,
        LicenseKeyStatus.SUSPENDED,
    }
)


def _issued_by(actor_id: str, idempotency_key: str) -> AppLicenseKey | None:
    """The key this actor already issued under this idempotency key, if any."""
    return (
        AppLicenseKey.objects.select_related("customer")
        .filter(generated_by_actor_id=actor_id, idempotency_key=idempotency_key)
        .first()
    )


def lock_customer_for_key_changes(customer_id) -> CustomerOrg:
    """Take the org's row lock and return the org. STEP ONE for any writer that adds a key to
    an org or moves a key's dates, followed by `require_no_overlapping_license_key`.

    The lock is what makes "at most one valid key per org" hold under concurrency: without it
    two simultaneous issuances both read "no overlapping key", both pass, and both insert. It
    is held to the end of the caller's transaction, so the second issuance waits here and then
    sees the first one's key. The lock is on the ORG, not the key, because the thing being
    protected is a property of the org: the new key does not exist yet to be locked.

    It is `FOR NO KEY UPDATE`, not `FOR UPDATE`. Two holders of either still exclude each
    other, which is all the race needs, but `FOR UPDATE` would also block every INSERT of a
    row that references the org (a device, a user, a session, a key) for as long as the lock
    is held, because those inserts take `FOR KEY SHARE` on the org row. We change no key
    column of the org, so the weaker lock is the right one.

    Must be called inside `transaction.atomic()`. On a backend with row locks (Postgres) Django
    raises `TransactionManagementError` if it is not; on SQLite `select_for_update` is a
    silent no-op whether or not a transaction is open, so nothing there will tell you the lock
    is missing. This is the only place the org lock is taken, so removing it turns the
    Postgres test red (which is why that test exists and why it cannot run on SQLite).
    """
    try:
        return CustomerOrg.objects.select_for_update(no_key=True).get(id=customer_id)
    except (CustomerOrg.DoesNotExist, ValueError) as error:
        raise SafeAPIError(ErrorCode.NOT_FOUND) from error


def require_no_overlapping_license_key(
    customer: CustomerOrg,
    *,
    starts_at: datetime,
    expires_at: datetime,
    exclude_key_id: int | None = None,
    requested_by: str = "",
) -> None:
    """Refuse with POLICY_DENIED if `customer` holds another key whose dates overlap
    `[starts_at, expires_at)` and whose status can still be in use. Writes nothing.

    THE ONE RULE, in one place. Issuance calls it; a future extend or renew writer must call it
    too, passing `exclude_key_id` for the key being moved (a key always overlaps itself).
    `customer` must be the row returned by `lock_customer_for_key_changes` in the same
    transaction, or the check is only as good as a read.

    `starts_at` and `expires_at` must be timezone-AWARE: the comparison is between instants,
    and a naive value is read in the server's current time zone (with a warning). Issuance
    coerces to UTC before calling; a new caller has to do the same.

    The window is half-open: a key that starts at the instant another expires does NOT overlap
    it (renewal today is issuing a new key that starts when the old one ends), and one second
    earlier does. Keys the org already holds that overlap each other are left as they are
    (grandfathered); only new dates are refused.

    The hint in the message names the LATEST expiry among the keys in the way, because that is
    the date from which the org is free of all of them. For a grandfathered org holding two
    overlapping keys the earliest expiry would still be refused by the other key.
    """
    blocking = AppLicenseKey.objects.filter(
        customer=customer,
        status__in=KEY_STATUSES_THAT_BLOCK_AN_OVERLAPPING_KEY,
        starts_at__lt=expires_at,
        expires_at__gt=starts_at,
    )
    if exclude_key_id is not None:
        blocking = blocking.exclude(pk=exclude_key_id)
    held = blocking.order_by("-expires_at", "pk").first()
    if held is None:
        return
    logger.warning(
        "refused licence dates for customer %s, %s to %s: they overlap licence %s "
        "(status %s, %s to %s), and an organisation may hold at most one valid licence at a "
        "time. Requested by actor %s.",
        customer.pk,
        starts_at.isoformat(),
        expires_at.isoformat(),
        held.pk,
        held.status,
        held.starts_at.isoformat(),
        held.expires_at.isoformat(),
        requested_by or "<unknown>",
    )
    raise SafeAPIError(
        ErrorCode.POLICY_DENIED,
        f"This organisation already holds licence {held.pk} ({held.status}) that runs from "
        f"{held.starts_at.isoformat()} to {held.expires_at.isoformat()}, and an organisation "
        "may hold at most one valid licence at a time. Dates that do not overlap it begin at "
        f"or after {held.expires_at.isoformat()}.",
    )


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
    if data.seat_limit < 1:
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
        existing = _issued_by(staff.actor_id, idempotency_key)
        if existing is not None:
            return GenerateLicenseKeyResult(license_key=existing, full_key=None, created=False)

        # The secret is generated and HASHED before the org lock is taken, not after. The hash
        # (PBKDF2) costs ~250 ms of CPU, and held under the lock it made every other write for
        # the org wait that long behind each issuance, measured at p50 366 ms of lock hold
        # against ~5 ms without it. The price is that a request that turns out to be a replay of
        # a racing original, or is refused by a check below, has spent one hash for nothing;
        # that is a rare staff action and a cheaper trade than holding the lock. A plain replay
        # (the look above) returns before any of this runs.
        full_key = _generate_full_key(key_type)
        prefix, suffix, masked_key = _mask(full_key)
        secret_hash = make_password(full_key)
        secret_fingerprint = _fingerprint(full_key)

        # Locks the org row for the rest of this transaction (one key per org, below). The
        # idempotent replay above deliberately runs BEFORE the overlap check: a retry of an
        # issuance that already succeeded must still return its key, and it would otherwise be
        # refused by the very overlap the first attempt created.
        customer = lock_customer_for_key_changes(data.customer_id)

        # ...and again, now that the lock is held. A retry that raced the original request got
        # past the first look (the original had not committed yet), then queued on the lock
        # behind it. The original's key is committed and visible by the time the lock is ours,
        # so this returns it as the replay it is; without this look the overlap check below
        # would refuse the retry with POLICY_DENIED, a regression of the concurrency-safe
        # idempotency this function had before the org lock existed.
        existing = _issued_by(staff.actor_id, idempotency_key)
        if existing is not None:
            return GenerateLicenseKeyResult(license_key=existing, full_key=None, created=False)

        if customer.status == CustomerStatus.ARCHIVED:
            raise SafeAPIError(ErrorCode.POLICY_DENIED)

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

        # 86ak5mn0m: the key's device limit is the PLAN's seat count, copied here once and from
        # then on the key's own field (the number activation enforces, the manifest publishes
        # and the refresh endpoint reports). A plan that cannot express "this many seats" is
        # refused rather than defaulted: a made-up number is a limit nobody chose.
        device_limit = plan_device_instances_for_issuance(plan)
        if device_limit is None:
            logger.warning(
                "refused to issue a licence for customer %s on plan %r (%s): the plan has no "
                "usable `device_instances` value (absent, unlimited, below 1, or the dimension "
                "is switched off), so the licence would have no seat limit. Set the plan's "
                "seat count in the catalogue first. Requested by actor %s.",
                data.customer_id,
                plan.code,
                plan.display_name,
                staff.actor_id,
            )
            raise SafeAPIError(
                ErrorCode.POLICY_DENIED,
                f"Plan {plan.code!r} ({plan.display_name}) has no usable device-instance "
                "count: its `device_instances` grant is missing, unlimited or below 1. A "
                "licence takes its device limit from its plan, so set a seat count on the "
                "plan in the catalogue and issue again.",
            )

        # At most one valid key per org (86ak5mn0m). The org row is locked above, so two
        # simultaneous issuances to one org queue here and the second sees the first's key.
        require_no_overlapping_license_key(
            customer, starts_at=starts_at, expires_at=expires_at, requested_by=staff.actor_id
        )

        license_key = AppLicenseKey(
            customer=customer,
            key_type=key_type,
            status=LicenseKeyStatus.ISSUED,
            key_prefix=prefix,
            key_suffix=suffix,
            masked_key=masked_key,
            secret_hash=secret_hash,
            secret_fingerprint=secret_fingerprint,
            starts_at=starts_at,
            expires_at=expires_at,
            timezone=data.timezone.strip() or "UTC",
            feature_scope=data.feature_scope.strip().upper(),
            seat_limit=data.seat_limit,
            device_limit=device_limit,
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
            existing = _issued_by(staff.actor_id, idempotency_key)
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


# --- Authorisation with an audited refusal (86ak1090r, AC 2 and AC 11) ---------------------
#
# The writer performs no authorisation, so each staff mutation gates itself FIRST: before the
# licence is looked up, before the budget is spent, before the writer is reached. A caller who
# is authenticated but not permitted is refused with PERMISSION_DENIED and the attempt is
# recorded, because "someone without the permission tried to revoke a licence" is exactly what
# an investigator needs to find (PRD §19: "§15 actor gating + FR-508 audit").
#
# What is deliberately NOT audited: an unauthenticated caller, and an identity too long or
# malformed to be written to the trail. There is no actor to attribute the row to.
#
# The refusal row is written for a caller we do not trust, so it is built defensively and
# BOUNDED. Every free-text field it carries is validated or replaced, never stored as sent,
# and two budgets cap how many rows the refusal path can produce: one per identity, one global
# (actor ids are free to vary on the dev header bridge, so a per-identity cap alone is not a
# bound). Past a budget the call is still refused; it just stops writing rows, and the shared
# throttle layer reports the sustained denial in the log once a minute.
REVOKE_PERMISSION_DENIED_ACTION = "license_key.revoke_permission_denied"
EXTEND_PERMISSION_DENIED_ACTION = "license_key.extend_permission_denied"
EXTEND_REFUSED_ACTION = "license_key.extend_refused"

REFUSAL_AUDIT_SCOPE = "admin_licence_refusal_audit"
REFUSAL_AUDIT_SETTING = "SELAHCUE_THROTTLE_ADMIN_LICENSE_REFUSAL_AUDIT"
REFUSAL_AUDIT_BUDGET = (5, 60)
REFUSAL_AUDIT_GLOBAL_SETTING = "SELAHCUE_THROTTLE_ADMIN_LICENSE_REFUSAL_AUDIT_GLOBAL"
REFUSAL_AUDIT_GLOBAL_BUDGET = (100, 60)

_PERMISSION_REFUSAL_CODE = "permission_denied"
_UNRESOLVED_TARGET = "unresolved"
_INVALID_REQUEST_ID = "invalid-idempotency-key"


def _authorise(
    actor: ActorContext | None,
    permission: StaffPermission,
    *,
    denied_action: str | None,
    raw_idempotency_key: str,
    raw_license_key_id: str,
    raw_reason: str,
) -> ActorContext:
    """`require_staff_permission`, plus an audit row when an identified actor is refused.

    `denied_action=None` keeps the plain gate (suspend and reinstate, which predate this and
    audit only transition refusals).
    """
    try:
        return require_staff_permission(actor, permission)
    except SafeAPIError as error:
        if denied_action is not None and actor is not None and error.code is ErrorCode.PERMISSION_DENIED:
            _audit_permission_refusal(
                actor,
                permission=permission,
                action=denied_action,
                raw_idempotency_key=raw_idempotency_key,
                raw_license_key_id=raw_license_key_id,
                raw_reason=raw_reason,
            )
        raise


def _audit_permission_refusal(
    actor: ActorContext,
    *,
    permission: StaffPermission,
    action: str,
    raw_idempotency_key: str,
    raw_license_key_id: str,
    raw_reason: str,
) -> None:
    """Best effort, bounded, and never able to change the answer the caller gets."""
    actor_id = actor.actor_id or ""
    if not actor_id or len(actor_id) > ACTOR_ID_MAX_LENGTH or has_control_characters(actor_id):
        return  # cannot be written to the trail; the refusal itself is unaffected

    identity = hashlib.sha256(f"{actor.kind.value}:{actor_id}".encode("utf-8")).hexdigest()[:32]
    if spend_budget(
        REFUSAL_AUDIT_SCOPE, identity, REFUSAL_AUDIT_SETTING, REFUSAL_AUDIT_BUDGET
    ) is BudgetOutcome.DENIED:
        return
    if spend_budget(
        f"{REFUSAL_AUDIT_SCOPE}_global",
        "all",
        REFUSAL_AUDIT_GLOBAL_SETTING,
        REFUSAL_AUDIT_GLOBAL_BUDGET,
    ) is BudgetOutcome.DENIED:
        return

    # No lookup: whether the licence exists must not change what an unauthorised caller sees,
    # and a refused caller does not get to make the database work.
    target_id = _clean_license_key_id(raw_license_key_id) or _UNRESOLVED_TARGET
    try:
        request_id = validate_idempotency_key(raw_idempotency_key)
    except SafeAPIError:
        request_id = _INVALID_REQUEST_ID
    try:
        reason = _require_reason_without_a_credential(raw_reason)
    except SafeAPIError:
        reason = ""

    try:
        record_audit_event(
            actor,
            action=action,
            target_type=AUDIT_TARGET_TYPE,
            target_id=target_id,
            request_id=request_id,
            reason=reason,
            result=AuditResult.DENIED,
            after={
                "required_permission": permission.value,
                "refusal_code": _PERMISSION_REFUSAL_CODE,
            },
        )
    except Exception:  # noqa: BLE001 - the record of a refusal must never undo the refusal
        logger.exception(
            "could not record a permission refusal for actor kind %s (%s); the call was still "
            "refused.",
            actor.kind.value,
            action,
        )


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
    cleaned = _clean_license_key_id(raw_id)
    if cleaned is None:
        raise SafeAPIError(ErrorCode.NOT_FOUND)
    try:
        return AppLicenseKey.objects.select_related("customer").get(pk=int(cleaned))
    except AppLicenseKey.DoesNotExist as error:
        raise SafeAPIError(ErrorCode.NOT_FOUND) from error


def _clean_license_key_id(raw_id: str) -> str | None:
    """The id as digits, or None when the text cannot name a licence. One rule for both the
    lookup and the refusal audit row, so a value the lookup would reject is never recorded."""
    cleaned = (raw_id or "").strip()
    if (
        not cleaned
        or len(cleaned) > _MAX_LICENSE_KEY_ID_DIGITS
        or not (cleaned.isascii() and cleaned.isdecimal())
    ):
        return None
    return cleaned


def _lifecycle_mutation(
    actor: ActorContext | None,
    *,
    permission: StaffPermission,
    to_status: LicenseKeyStatus | PriorStatusTarget,
    raw_idempotency_key: str,
    raw_license_key_id: str,
    raw_reason: str,
    denied_action: str | None = None,
) -> LicenseTransitionResult:
    staff = _authorise(
        actor,
        permission,
        denied_action=denied_action,
        raw_idempotency_key=raw_idempotency_key,
        raw_license_key_id=raw_license_key_id,
        raw_reason=raw_reason,
    )
    _require_autocommit()
    _enforce_lifecycle_budget(staff)
    idempotency_key = validate_idempotency_key(raw_idempotency_key)
    reason = _require_reason_without_a_credential(raw_reason)
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


# --- Revoke (86ak1090r: FR-505, FLOW-504, NFR-503) ---------------------------------------------
@dataclass(frozen=True)
class RevokeLicenseKeyData:
    idempotency_key: str
    license_key_id: str
    reason: str


def revoke_license_key(
    actor: ActorContext | None, data: RevokeLicenseKeyData
) -> LicenseTransitionResult:
    """Permanently kill a licence (FR-505). Staff only, reason mandatory.

    Writes REVOKED through the state machine and nothing else: it does not touch a device
    token. Tokens already issued are revoked by the hourly cascade (`cascade_license_
    revocations`, NFR-503: at most 65 minutes online exposure), while activation and manifest
    issuance refuse at once because REVOKED is outside `ACTIVATABLE_KEY_STATUSES`. The cached
    offline entitlement runs to its own expiry, the accepted DEC-004/005 trade-off (RISK-501).

    Allowed from every status the table gives a REVOKED edge (ISSUED, ACTIVATED, EXPIRING,
    EXPIRED, SUSPENDED, CONVERTED). Revoking an already REVOKED licence is a no-op
    (`changed=False`, no second audit row, nothing for a second cascade to do). Revoking an
    ARCHIVED licence is refused with CONFLICT and one durable DENIED audit row. REVOKED is
    permanent: no mutation moves a licence out of it except archiving.
    """
    return _lifecycle_mutation(
        actor,
        permission=StaffPermission.REVOKE_LICENSE_KEY,
        to_status=LicenseKeyStatus.REVOKED,
        raw_idempotency_key=data.idempotency_key,
        raw_license_key_id=data.license_key_id,
        raw_reason=data.reason,
        denied_action=REVOKE_PERMISSION_DENIED_ACTION,
    )


# --- Extend (86ak1090r: FR-509, FLOW-503) ------------------------------------------------------
#
# Which statuses a licence may be extended from, and what each becomes. Decided here, flagged in
# the PR for the owner; no change to the transition table is needed for any of it.
#
#   ISSUED, ACTIVATED  the date moves; the status stays. An ISSUED licence must not be
#                      "activated" by an extension: nothing has activated it.
#   EXPIRING, EXPIRED  the date moves and the status becomes ACTIVATED through the writer (the
#                      FR-509 renewal edges, already in the table). An EXPIRING licence that
#                      never had a device ends ACTIVATED with none, because the table has no
#                      EXPIRING -> ISSUED edge; it stays activatable.
#   SUSPENDED          refused: a hold is lifted by reinstating first (which returns the status
#                      it came from), so extending underneath a hold would make the hold's
#                      recorded prior status describe a window that no longer exists.
#   CONVERTED          refused: superseded by a successor licence.
#   REVOKED, ARCHIVED  refused: terminal.
EXTENDABLE_SOURCES = frozenset(
    {
        LicenseKeyStatus.ISSUED,
        LicenseKeyStatus.ACTIVATED,
        LicenseKeyStatus.EXPIRING,
        LicenseKeyStatus.EXPIRED,
    }
)
_EXTENDS_TO_ACTIVATED = frozenset({LicenseKeyStatus.EXPIRING, LicenseKeyStatus.EXPIRED})

# A technical sanity bound, NOT a product rule. Issuance has no ceiling and the PRD names no
# maximum term, so this only has to stop an absurd date (year 9999, a typo of three extra
# digits) from becoming a signed entitlement cached offline until it. Five years from NOW.
# Flagged for the owner; changing it is one constant.
MAX_EXTENSION_FROM_NOW = timedelta(days=5 * 365)


@dataclass(frozen=True)
class ExtendLicenseKeyData:
    idempotency_key: str
    license_key_id: str
    new_expires_at: datetime
    reason: str


class _ExtendRefused(Exception):
    """Internal control flow: abandons the extend transaction so nothing is written, then the
    DENIED audit row is recorded OUTSIDE it (same shape as the writer's own refusal)."""

    def __init__(
        self, *, error: SafeAPIError, refusal_code: str, before: AppLicenseKey, requested: datetime
    ) -> None:
        self.error = error
        self.refusal_code = refusal_code
        self.before_status = before.status
        self.before_prior_status = before.prior_status
        self.before_expires_at = before.expires_at
        self.requested = requested
        super().__init__(refusal_code)


def _require_new_expiry(value: datetime) -> datetime:
    """The requested expiry as an aware UTC instant, or VALIDATION_FAILED.

    Naive values are REFUSED rather than coerced to UTC the way issuance does it: a licence
    window moved by a mis-read zone is an hours-wrong entitlement, and the console can always
    send an offset. In the future, because an activatable licence whose window is already over
    activates nothing; at most `MAX_EXTENSION_FROM_NOW` ahead, because of the year-9999 typo.
    """
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    try:
        instant = value.astimezone(dt_timezone.utc)
    except (OverflowError, ValueError) as error:  # year 9999 with a negative offset, etc.
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED) from error
    now = timezone.now()
    if instant <= now or instant > now + MAX_EXTENSION_FROM_NOW:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    return instant


def _move_expiry(locked: AppLicenseKey, new_expires_at: datetime) -> None:
    """The one place an extension writes the date. A named seam so the tests can make exactly
    this step fail and watch the status change and the audit row roll back with it."""
    locked.expires_at = new_expires_at
    locked.save(update_fields=["expires_at", "updated_at"])


def extend_license_key(
    actor: ActorContext | None, data: ExtendLicenseKeyData
) -> LicenseTransitionResult:
    """Move a licence's `expires_at` forward and return a lapsed one to ACTIVATED (FR-509).

    Staff only, reason mandatory. See `EXTENDABLE_SOURCES` for what each status does. The new
    expiry must be timezone-aware, strictly later than the current one, in the future, and
    within `MAX_EXTENSION_FROM_NOW`; it may not overlap another valid licence of the
    organisation (the rule `require_no_overlapping_license_key` documents for exactly this
    caller); and an archived customer's licence is not extended.

    One transaction holds the organisation row lock, then the licence row lock, and commits the
    new date, the status change and the single audit row together. Retries: the idempotency key
    is per user intent. A retry of a request that took effect applies nothing and reports the
    licence's CURRENT state with `changed=False` and the original audit row, checked under the
    lock BEFORE anything else so it is never judged against the state the first call produced.
    A new key with the date already in effect is rejected (VALIDATION_FAILED), not applied twice.

    Lock order is organisation then licence. Revoke, suspend and activation take only the
    licence lock, so nothing takes them in the opposite order.
    """
    staff = _authorise(
        actor,
        StaffPermission.EXTEND_LICENSE_KEY,
        denied_action=EXTEND_PERMISSION_DENIED_ACTION,
        raw_idempotency_key=data.idempotency_key,
        raw_license_key_id=data.license_key_id,
        raw_reason=data.reason,
    )
    _require_autocommit()
    _enforce_lifecycle_budget(staff)
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    reason = _require_reason_without_a_credential(data.reason)
    new_expires_at = _require_new_expiry(data.new_expires_at)
    license_key = _get_license_key_or_not_found(data.license_key_id)

    try:
        return _extend_under_locks(
            license_key,
            staff=staff,
            idempotency_key=idempotency_key,
            reason=reason,
            new_expires_at=new_expires_at,
        )
    except _ExtendRefused as refused:
        # Outside the atomic block that raised it: the transaction rolled back, this row does not.
        record_audit_event(
            staff,
            action=EXTEND_REFUSED_ACTION,
            target_type=AUDIT_TARGET_TYPE,
            target_id=str(license_key.pk),
            request_id=idempotency_key,
            reason=reason,
            result=AuditResult.DENIED,
            before={
                "status": refused.before_status,
                "prior_status": refused.before_prior_status,
                "expires_at": refused.before_expires_at.isoformat(),
            },
            after={
                "status": refused.before_status,
                "prior_status": refused.before_prior_status,
                "expires_at": refused.before_expires_at.isoformat(),
                "requested_expires_at": refused.requested.isoformat(),
                "refusal_code": refused.refusal_code,
            },
        )
        raise refused.error from None


def _extend_under_locks(
    license_key: AppLicenseKey,
    *,
    staff: ActorContext,
    idempotency_key: str,
    reason: str,
    new_expires_at: datetime,
) -> LicenseTransitionResult:
    writer_refusal: IllegalLicenseTransition | None = None
    with transaction.atomic():
        customer = lock_customer_for_key_changes(license_key.customer_id)
        locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)
        before_status = LicenseKeyStatus(locked.status)
        old_expires_at = locked.expires_at

        # 1. A retry of a request that already took effect, decided before anything else.
        earlier = earlier_success_event(
            staff, action=EXTEND_ACTION, license_key_id=locked.pk, request_id=idempotency_key
        )
        if earlier is not None:
            return LicenseTransitionResult(
                license_key=locked,
                from_status=before_status,
                to_status=before_status,
                changed=False,
                audit_event=earlier,
            )

        # 2. Refusals that are audited.
        if before_status not in EXTENDABLE_SOURCES:
            raise _ExtendRefused(
                error=SafeAPIError(ErrorCode.CONFLICT),
                refusal_code="status_not_extendable",
                before=locked,
                requested=new_expires_at,
            )
        if customer.status == CustomerStatus.ARCHIVED:
            raise _ExtendRefused(
                error=SafeAPIError(ErrorCode.POLICY_DENIED),
                refusal_code="customer_archived",
                before=locked,
                requested=new_expires_at,
            )

        # 3. Input that only the locked row can judge. Not audited: it is a bad request.
        if new_expires_at <= old_expires_at:
            raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

        try:
            require_no_overlapping_license_key(
                customer,
                starts_at=locked.starts_at,
                expires_at=new_expires_at,
                exclude_key_id=locked.pk,
                requested_by=staff.actor_id,
            )
        except SafeAPIError as error:
            if error.code is not ErrorCode.POLICY_DENIED:
                raise
            raise _ExtendRefused(
                error=error,
                refusal_code="overlaps_another_licence",
                before=locked,
                requested=new_expires_at,
            ) from None

        # 4. Apply. The status goes through the writer, never assigned here.
        if before_status in _EXTENDS_TO_ACTIVATED:
            try:
                transition = apply_license_status_transition(
                    locked,
                    to_status=LicenseKeyStatus.ACTIVATED,
                    actor=staff,
                    reason=reason,
                    request_id=idempotency_key,
                    action=EXTEND_ACTION,
                    extra_before={"expires_at": old_expires_at.isoformat()},
                    extra_after={"expires_at": new_expires_at.isoformat()},
                    # Wrapped on purpose: the date, the status and the audit row commit together.
                    # A refusal is unreachable while the renewal edges stay in the table, and if
                    # one does arise it is caught right here, inside the block, so its DENIED row
                    # commits (the "caught inside" case of the writer's durability contract).
                    allow_wrapping_transaction=True,
                )
            except IllegalLicenseTransition as refusal:
                writer_refusal = refusal
            else:
                _move_expiry(locked, new_expires_at)
                return LicenseTransitionResult(
                    license_key=locked,
                    from_status=before_status,
                    to_status=LicenseKeyStatus.ACTIVATED,
                    changed=True,
                    audit_event=transition.audit_event,
                )
        else:
            _move_expiry(locked, new_expires_at)
            event = record_audit_event(
                staff,
                action=EXTEND_ACTION,
                target_type=AUDIT_TARGET_TYPE,
                target_id=str(locked.pk),
                request_id=idempotency_key,
                reason=reason,
                result=AuditResult.SUCCESS,
                before={
                    "status": before_status.value,
                    "prior_status": locked.prior_status,
                    "expires_at": old_expires_at.isoformat(),
                },
                after={
                    "status": locked.status,
                    "prior_status": locked.prior_status,
                    "expires_at": new_expires_at.isoformat(),
                },
            )
            return LicenseTransitionResult(
                license_key=locked,
                from_status=before_status,
                to_status=before_status,
                changed=True,
                audit_event=event,
            )

    # Reached only when the writer refused: the block committed just its DENIED row. Every other
    # path above returns or raises, so a missing refusal here is a bug in this function. Raised
    # explicitly rather than asserted, because `python -O` strips an assert.
    if writer_refusal is None:
        raise RuntimeError("extend finished its transaction without a result or a refusal")
    raise writer_refusal
