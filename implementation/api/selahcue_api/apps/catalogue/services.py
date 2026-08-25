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
from typing import Any, Mapping

from django.db import IntegrityError, transaction

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

    `values` maps a dimension key to `bool`, `int`, or `None` (= no limit). `plan` is None
    only when the catalogue resolves nothing at all — an unseeded database — in which case
    `values` is empty and the caller keeps whatever it had.
    """

    plan: Plan | None
    values: Mapping[str, Any]
    # Display only. FR-545: a client must never branch on this, and nothing here does.
    plan_display_label: str
    # The dimension key flagged `governs_instance_limit`, if one is present and granted.
    instance_limit_key: str | None

    @property
    def instance_limit(self) -> int | None:
        """The resolved seat cap, or None when the catalogue does not express one."""
        if self.instance_limit_key is None:
            return None
        value = self.values.get(self.instance_limit_key)
        return value if isinstance(value, int) and not isinstance(value, bool) else None


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


def _plan_grant_map(plan: Plan) -> Mapping[str, Any]:
    """`{"values": {key: typed}, "instance_limit_key": key|None}`, cached per revision.

    The instance-limit key is cached alongside the values so a cache hit costs no further
    query at all — resolving a licence is then one revision read plus one override read.
    """
    revision = current_revision()
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
            logger.warning(
                "catalogue dimension %r has no readable value for plan %s; omitting it",
                dimension.key,
                plan.pk,
            )
            continue
        values[dimension.key] = value

    instance_dimension = next(
        (dimension for dimension in dimensions if dimension.governs_instance_limit), None
    )
    resolved = {
        "values": values,
        "instance_limit_key": (
            instance_dimension.key
            if instance_dimension is not None and instance_dimension.key in values
            else None
        ),
    }
    GRANT_CACHE.put(plan.pk, revision, resolved)
    return resolved


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
    try:
        plan = resolve_plan_for_license(license_key)
    except Exception:  # pragma: no cover - defensive; never deny a manifest over catalogue state
        logger.exception("catalogue plan resolution failed; issuing without grants")
        return ResolvedEntitlement(plan=None, values={}, plan_display_label="", instance_limit_key=None)

    if plan is None:
        return ResolvedEntitlement(plan=None, values={}, plan_display_label="", instance_limit_key=None)

    try:
        resolved = _plan_grant_map(plan)
        values = dict(resolved["values"])
        instance_limit_key = resolved["instance_limit_key"]

        # Per-licence deviations, applied last. Bounded by the dimension cap: a licence
        # cannot carry more overrides than there are dimensions it can override.
        overrides = (
            LicenseGrantOverride.objects.filter(
                license_key=license_key, dimension__is_active=True
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
            if dimension.governs_instance_limit:
                instance_limit_key = dimension.key
    except Exception:  # pragma: no cover - defensive
        logger.exception("catalogue grant resolution failed; issuing without grants")
        return ResolvedEntitlement(plan=None, values={}, plan_display_label="", instance_limit_key=None)

    return ResolvedEntitlement(
        plan=plan,
        values=values,
        plan_display_label=plan.display_name,
        instance_limit_key=instance_limit_key if instance_limit_key in values else None,
    )


# --- Writes -----------------------------------------------------------------------------


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
