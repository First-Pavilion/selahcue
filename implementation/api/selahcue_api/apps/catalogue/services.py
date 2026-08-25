"""Resolve a licence to typed entitlement values, and edit the catalogue (FR-544/FR-545).

`resolve_entitlement()` is a pure read used by the entitlement manifest builder. It has one
hard rule beyond correctness: **it never raises on bad or missing catalogue data.** An
unseeded catalogue, a malformed `raw_value`, a deleted dimension — every one of them
degrades to "this dimension is simply not granted", and the manifest still issues. The
alternative is a licensing lookup that can refuse a device its entitlement because someone
typed "fivve" into an admin field, which is exactly the class of failure NFR-024 forbids.

Nothing in this module compares a plan code or a display name against a literal. That is
enforced by a source sweep in `tests/test_product_catalogue_slice.py`, not by good manners.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.catalogue.cache import GRANT_CACHE
from selahcue_api.apps.catalogue.models import (
    UNLIMITED,
    CatalogueRevision,
    GrantDimension,
    GrantValueType,
    LicenseGrantOverride,
    LicensePlanAssignment,
    MAX_GRANT_DIMENSIONS,
    Plan,
    PlanGrant,
    PlanScopeAlias,
    is_reserved_grant_key,
    validate_grant_key,
)
from selahcue_api.graphql.context import (
    ActorContext,
    StaffPermission,
    require_reason,
    require_staff_permission,
    validate_idempotency_key,
)
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
from selahcue_api.graphql.redaction import is_restricted_payload_field

logger = logging.getLogger(__name__)

_TRUTHY = frozenset({"true", "1", "yes", "on"})
_FALSEY = frozenset({"false", "0", "no", "off"})


class _Unset:
    """Sentinel distinct from None, because None is a legitimate value ("no limit")."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<unset>"


_UNSET = _Unset()


@dataclass(frozen=True)
class ResolvedEntitlement:
    """What a licence actually grants, as typed values.

    `values` maps a dimension key to `bool`, `int`, or `None`. The three states are
    distinct and must stay that way:

        key present, int/bool   the catalogue grants exactly this
        key present, None       granted without a ceiling (``unlimited``)
        key ABSENT              the catalogue expresses nothing; the client's own default
                                applies

    `plan` is None only when the catalogue resolves nothing at all — an unseeded database —
    in which case `values` is empty and the caller keeps whatever it had.

    Deliberately carries no seat-limit accessor. `AppLicenseKey.device_limit` is the number
    activation enforces and the only one the manifest publishes as `instances_limit`; a
    second, catalogue-derived seat number reachable from here is how the two came to
    disagree inside one signed artefact.
    """

    plan: Plan | None
    values: Mapping[str, Any]
    # Display only. FR-545: a client must never branch on this, and nothing here does.
    plan_display_label: str


def current_revision() -> int:
    """The catalogue's revision counter — one primary-key read.

    Missing row (fresh database, migrations not yet applied in some tooling path) reads as
    0 rather than raising: this is on the manifest-issuance path.
    """
    try:
        row = CatalogueRevision.objects.filter(pk=CatalogueRevision.SINGLETON_PK).values("revision").first()
    except Exception:  # pragma: no cover - defensive; a DB error must not deny entitlement
        logger.exception("catalogue revision unreadable; treating the cache as cold")
        return -1
    return int(row["revision"]) if row else 0


def coerce_grant_value(value_type: str, raw_value: str) -> Any:
    """Typed value for a stored string, or `_UNSET` when it cannot be read.

    Raising here would let one bad admin edit deny a device its manifest.
    """
    raw = (raw_value or "").strip()
    if not raw:
        return _UNSET
    if value_type == GrantValueType.BOOLEAN:
        lowered = raw.lower()
        if lowered in _TRUTHY:
            return True
        if lowered in _FALSEY:
            return False
        return _UNSET
    if value_type == GrantValueType.INTEGER:
        if raw.lower() == UNLIMITED:
            return None
        try:
            parsed = int(raw)
        except ValueError:
            return _UNSET
        return parsed if parsed >= 0 else _UNSET
    return _UNSET


def _active_dimensions() -> list[GrantDimension]:
    """Active dimensions, capped and sanitised.

    The cap bounds how large one cache entry can get. The sanitising matters more: grant
    keys land in the signed manifest payload, which is run through
    `assert_no_restricted_payload_fields`. A dimension somebody names `content` or `secret`
    would make that assertion raise and deny EVERY device its manifest — a catalogue row
    able to take down licensing globally. Dropping the row here instead costs one grant.
    """
    dimensions = []
    for dimension in GrantDimension.objects.filter(is_active=True).order_by("sort_order", "key")[
        :MAX_GRANT_DIMENSIONS
    ]:
        if is_restricted_payload_field(dimension.key):
            logger.warning(
                "catalogue dimension %r collides with a restricted payload field; ignoring it",
                dimension.key,
            )
            continue
        dimensions.append(dimension)
    return dimensions


def _plan_grant_map(plan: Plan, revision: int) -> Mapping[str, Any]:
    """`{dimension key: typed value}` for a plan, cached per catalogue revision.

    The revision is passed in rather than read here, so one resolution costs exactly one
    revision read however many times this is consulted.
    """
    cached = GRANT_CACHE.get(plan.pk, revision)
    if cached is not None:
        return cached

    dimensions = _active_dimensions()
    granted = {
        grant.dimension_id: grant.raw_value
        for grant in PlanGrant.objects.filter(
            plan=plan, dimension_id__in=[dimension.pk for dimension in dimensions]
        ).only("dimension_id", "raw_value")
    }

    values: dict[str, Any] = {}
    for dimension in dimensions:
        raw = granted.get(dimension.pk, dimension.default_raw_value)
        value = coerce_grant_value(dimension.value_type, raw)
        if value is _UNSET and dimension.pk in granted:
            # An unreadable plan value falls back to the dimension's own default before
            # giving up, so one bad edit costs that plan's override, not the dimension.
            value = coerce_grant_value(dimension.value_type, dimension.default_raw_value)
        if value is _UNSET:
            if raw.strip():
                # A value was written and could not be read — that is an operator error
                # worth surfacing. An empty default is a deliberate "no catalogue-wide
                # default", so it must not be logged as though something were wrong.
                logger.warning(
                    "catalogue dimension %r has no readable value for plan %s; omitting it",
                    dimension.key,
                    plan.pk,
                )
            continue
        values[dimension.key] = value

    GRANT_CACHE.put(plan.pk, revision, values)
    return values


def resolve_plan_for_license(license_key) -> Plan | None:
    """Assignment → legacy scope alias → designated fallback. None when none exist."""
    assignment = (
        LicensePlanAssignment.objects.select_related("plan").filter(license_key=license_key).first()
    )
    if assignment is not None:
        return assignment.plan

    scope = (getattr(license_key, "feature_scope", "") or "").strip().upper()
    if scope:
        alias = PlanScopeAlias.objects.select_related("plan").filter(feature_scope=scope).first()
        if alias is not None:
            return alias.plan

    return Plan.objects.filter(is_fallback=True).first()


def resolve_entitlement(license_key) -> ResolvedEntitlement:
    """The typed grants a licence carries right now.

    Degrades rather than raises: an empty catalogue yields an empty `values` map and the
    caller keeps whatever it already had (which is how "no loss of current entitlement"
    holds even before migration 0002 has run).
    """
    empty = ResolvedEntitlement(plan=None, values={}, plan_display_label="")
    try:
        plan = resolve_plan_for_license(license_key)
    except Exception:  # pragma: no cover - defensive; never deny a manifest over catalogue state
        logger.exception("catalogue plan resolution failed; issuing without grants")
        return empty

    if plan is None:
        return empty

    try:
        values = dict(_plan_grant_map(plan, current_revision()))

        # Per-licence deviations, applied last. Bounded by the dimension cap: a licence
        # cannot carry more overrides than there are dimensions it can override.
        overrides = (
            LicenseGrantOverride.objects.filter(license_key=license_key, dimension__is_active=True)
            .filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
            )
            .select_related("dimension")
            # Ordered before slicing: an unordered slice would make WHICH override the cap
            # drops depend on the backend's row order, so the same licence could resolve
            # differently on two servers.
            .order_by("dimension__sort_order", "dimension__key")[:MAX_GRANT_DIMENSIONS]
        )
        for override in overrides:
            dimension = override.dimension
            if is_restricted_payload_field(dimension.key):
                # Same reasoning as `_active_dimensions`: a grant key must never be able to
                # trip the payload redaction guard and deny the manifest.
                continue
            value = coerce_grant_value(dimension.value_type, override.raw_value)
            if value is _UNSET:
                logger.warning(
                    "catalogue override for dimension %r is unreadable; keeping the plan value",
                    dimension.key,
                )
                continue
            values[dimension.key] = value
    except Exception:  # pragma: no cover - defensive
        logger.exception("catalogue grant resolution failed; issuing without grants")
        return empty

    return ResolvedEntitlement(
        plan=plan,
        values=values,
        plan_display_label=plan.display_name,
    )


# --- Writes -----------------------------------------------------------------------------

# Overrides are priced exceptions, and an exception nobody revisits is an unpriced
# entitlement. Time-boxed unless a caller deliberately says otherwise.
DEFAULT_OVERRIDE_DAYS = 90

assert DEFAULT_OVERRIDE_DAYS > 0, "a non-positive default would expire every override on creation"


def validate_dimension_key(key: str) -> str:
    """Allow-list a dimension key before it can ever reach a signed payload.

    The database check constraints are the real guarantee; this exists so a caller gets
    `VALIDATION_FAILED` with a useful message instead of an IntegrityError, and so the rule
    is enforced identically on backends whose regex support differs.
    """
    cleaned = (key or "").strip()
    try:
        validate_grant_key(cleaned)
    except ValidationError as error:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED, str(error.messages[0])) from error
    if is_reserved_grant_key(cleaned):
        raise SafeAPIError(
            ErrorCode.VALIDATION_FAILED,
            "That grant dimension key prefix is reserved for first-party use.",
        )
    return cleaned




@dataclass(frozen=True)
class SetPlanGrantData:
    idempotency_key: str
    plan_code: str
    dimension_key: str
    raw_value: str
    reason: str


@dataclass(frozen=True)
class SetPlanGrantResult:
    grant: PlanGrant
    created: bool
    previous_raw_value: str | None


def set_plan_grant(actor: ActorContext | None, data: SetPlanGrantData) -> SetPlanGrantResult:
    """Change what a plan grants on one dimension. The operator lever behind FR-544.

    This is a DATA edit — no migration, no deploy. `plan_code` and `dimension_key` arrive
    from the caller and are looked up; they are never matched against a literal.
    """
    staff = require_staff_permission(actor, StaffPermission.GRANT_ENTITLEMENT)
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    reason = require_reason(data.reason)

    plan_code = (data.plan_code or "").strip()
    dimension_key = (data.dimension_key or "").strip()
    raw_value = (data.raw_value or "").strip()
    if not plan_code or not dimension_key or not raw_value:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

    with transaction.atomic():
        plan = Plan.objects.filter(code=plan_code).first()
        dimension = GrantDimension.objects.filter(key=dimension_key).first()
        if plan is None or dimension is None:
            raise SafeAPIError(ErrorCode.NOT_FOUND)

        # Reject a value the dimension cannot express, rather than storing something that
        # will silently vanish from every manifest at resolution time.
        if coerce_grant_value(dimension.value_type, raw_value) is _UNSET:
            raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

        existing = PlanGrant.objects.filter(plan=plan, dimension=dimension).first()
        previous = existing.raw_value if existing is not None else None
        if existing is not None and existing.raw_value == raw_value:
            # Idempotent replay: the row already says what the caller is asking for.
            return SetPlanGrantResult(grant=existing, created=False, previous_raw_value=previous)

        if existing is not None:
            existing.raw_value = raw_value
            existing.save(update_fields=["raw_value", "updated_at"])
            grant, created = existing, False
        else:
            try:
                with transaction.atomic():
                    grant = PlanGrant.objects.create(
                        plan=plan, dimension=dimension, raw_value=raw_value
                    )
                created = True
            except IntegrityError:
                # A racing writer won the unique (plan, dimension) constraint. Read theirs
                # back and apply ours on top rather than surfacing an internal error.
                grant = PlanGrant.objects.filter(plan=plan, dimension=dimension).first()
                if grant is None:
                    raise SafeAPIError(ErrorCode.CONFLICT) from None
                previous = grant.raw_value
                grant.raw_value = raw_value
                grant.save(update_fields=["raw_value", "updated_at"])
                created = False

        record_audit_event(
            staff,
            action="catalogue.plan_grant_set",
            target_type="catalogue_plan_grant",
            target_id=str(grant.pk),
            request_id=idempotency_key,
            reason=reason,
            before={"raw_value": previous} if previous is not None else None,
            after={
                "plan_code": plan.code,
                "dimension_key": dimension.key,
                "raw_value": grant.raw_value,
            },
        )
        return SetPlanGrantResult(grant=grant, created=created, previous_raw_value=previous)


@dataclass(frozen=True)
class SetLicenseGrantOverrideData:
    idempotency_key: str
    license_key_id: str
    dimension_key: str
    raw_value: str
    reason: str
    # None means "use the default window". Pass `expires_at` explicitly for a different
    # one, or `permanent=True` to opt out of expiry altogether.
    expires_at: "datetime | None" = None
    permanent: bool = False


@dataclass(frozen=True)
class SetLicenseGrantOverrideResult:
    override: LicenseGrantOverride
    created: bool
    previous_raw_value: str | None


def set_license_grant_override(
    actor: ActorContext | None, data: SetLicenseGrantOverrideData
) -> SetLicenseGrantOverrideResult:
    """Grant one licence a deviation from its plan on one dimension.

    This is a commercial exception for a single customer, so it carries the same ceremony
    as any other entitlement write — permission, a required reason, an audit record — plus
    an expiry, because a forgotten override is an entitlement nobody is charging for.
    """
    staff = require_staff_permission(actor, StaffPermission.GRANT_ENTITLEMENT)
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    reason = require_reason(data.reason)
    dimension_key = validate_dimension_key(data.dimension_key)
    raw_value = (data.raw_value or "").strip()
    if not raw_value:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

    if data.permanent:
        expires_at = None
    elif data.expires_at is not None:
        expires_at = data.expires_at
        if expires_at <= timezone.now():
            raise SafeAPIError(ErrorCode.VALIDATION_FAILED)
    else:
        expires_at = timezone.now() + timedelta(days=DEFAULT_OVERRIDE_DAYS)

    with transaction.atomic():
        dimension = GrantDimension.objects.filter(key=dimension_key).first()
        license_key = _license_key_model().objects.filter(id=data.license_key_id).first()
        if dimension is None or license_key is None:
            raise SafeAPIError(ErrorCode.NOT_FOUND)
        if coerce_grant_value(dimension.value_type, raw_value) is _UNSET:
            raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

        existing = LicenseGrantOverride.objects.filter(
            license_key=license_key, dimension=dimension
        ).first()
        previous = existing.raw_value if existing is not None else None

        if existing is not None:
            existing.raw_value = raw_value
            existing.granted_by_actor_id = staff.actor_id
            existing.reason = reason
            existing.expires_at = expires_at
            existing.save(
                update_fields=[
                    "raw_value",
                    "granted_by_actor_id",
                    "reason",
                    "expires_at",
                    "updated_at",
                ]
            )
            override, created = existing, False
        else:
            try:
                with transaction.atomic():
                    override = LicenseGrantOverride.objects.create(
                        license_key=license_key,
                        dimension=dimension,
                        raw_value=raw_value,
                        granted_by_actor_id=staff.actor_id,
                        reason=reason,
                        expires_at=expires_at,
                    )
                created = True
            except IntegrityError:
                # A racing writer won the unique (licence, dimension) constraint.
                override = LicenseGrantOverride.objects.filter(
                    license_key=license_key, dimension=dimension
                ).first()
                if override is None:
                    raise SafeAPIError(ErrorCode.CONFLICT) from None
                previous = override.raw_value
                override.raw_value = raw_value
                override.granted_by_actor_id = staff.actor_id
                override.reason = reason
                override.expires_at = expires_at
                override.save(
                    update_fields=[
                        "raw_value",
                        "granted_by_actor_id",
                        "reason",
                        "expires_at",
                        "updated_at",
                    ]
                )
                created = False

        record_audit_event(
            staff,
            action="catalogue.license_grant_override_set",
            target_type="catalogue_license_grant_override",
            target_id=str(override.pk),
            request_id=idempotency_key,
            reason=reason,
            before={"raw_value": previous} if previous is not None else None,
            after={
                "license_key_id": str(license_key.id),
                "dimension_key": dimension.key,
                "raw_value": override.raw_value,
                "expires_at": expires_at.isoformat() if expires_at else None,
            },
        )
        return SetLicenseGrantOverrideResult(
            override=override, created=created, previous_raw_value=previous
        )


def _license_key_model():
    """Imported lazily: `license_keys` is a peer app and this avoids an import cycle."""
    from selahcue_api.apps.license_keys.models import AppLicenseKey

    return AppLicenseKey
