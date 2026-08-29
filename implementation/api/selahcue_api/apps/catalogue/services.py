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
from types import MappingProxyType
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
    has_control_characters,
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
class CachedGrants:
    """One plan's resolved grants, as an IMMUTABLE value shared across every tenant on it."""

    values: Mapping[str, Any]
    # Keys whose dimension carries `publish_in_manifest`.
    published: frozenset
    # Every active dimension key inside `MAX_GRANT_DIMENSIONS`, whether or not it resolved
    # to a value. Overrides are restricted to these, so the merged map cannot exceed the
    # cap — without it, a plan's 64 grants plus a licence's 64 overrides make 128 against a
    # stated bound of 64, and the number is then not what the bound says it is.
    known: frozenset


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
    # The subset of `values` whose dimensions are flagged for the signed manifest. A value
    # the server resolves but the client must not act on never appears here — the payload
    # has no way to mark a grant "advisory", so the only safe way to say it is silence.
    published_values: Mapping[str, Any] = MappingProxyType({})
    # True when resolution FAILED rather than found nothing. An unconfigured catalogue and
    # a transient database error both yield no grants, but only one of them should let a
    # two-year signed artefact be minted from it.
    degraded: bool = False


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


def _plan_grant_map(plan: Plan, revision: int) -> CachedGrants:
    """One plan's `CachedGrants`, cached per catalogue revision.

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

    # Read-only on the way in: the entry is shared by every tenant on this plan, and a
    # caller that forgets to copy before applying one licence's overrides must fail loudly
    # rather than leak that licence's entitlement to the others.
    grants = CachedGrants(
        values=MappingProxyType(values),
        published=frozenset(
            dimension.key
            for dimension in dimensions
            if dimension.publish_in_manifest and dimension.key in values
        ),
        known=frozenset(dimension.key for dimension in dimensions),
    )
    GRANT_CACHE.put(plan.pk, revision, grants)
    return grants


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

    An empty result is NOT self-explaining, so `degraded` says which kind it is. "The
    catalogue is unconfigured" is a steady state the caller can trust; "the read blew up"
    is a transient one, and minting a two-year offline artefact from it would honour a
    two-second blip for the life of the licence.

    **An unconfigured catalogue keeps emitting no grants, and that is the right default.**
    Absence already has exactly one meaning on the wire — "the catalogue expresses nothing
    about this dimension; apply your own default" — which is precisely true of a database
    where the catalogue has never been seeded, and it is what makes "no loss of current
    entitlement" hold before migration 0002 runs. Encoding it as anything else would
    invent a fourth grant state the payload has no room for.

    The two states are also already distinguishable to a client without a new field: a
    degraded manifest is clamped to a short TTL, so `expires_at < license_expires_at`
    implies degraded, while an unconfigured one carries the licence's own expiry. (The one
    case they converge is a licence expiring within the degraded TTL, where the clamp is a
    no-op — a manifest with minutes left to live either way.)

    What was genuinely missing is on the SERVER, not the wire: a failed read is logged and
    audited, so an operator can alert on it, while an unconfigured catalogue was completely
    silent. If migration 0002 never ran in an environment, every manifest would issue with
    zero grants and nothing anywhere would say so. Hence the warning below.
    """
    unconfigured = ResolvedEntitlement(plan=None, values={}, plan_display_label="")
    failed = ResolvedEntitlement(plan=None, values={}, plan_display_label="", degraded=True)
    try:
        plan = resolve_plan_for_license(license_key)
    except Exception:  # pragma: no cover - defensive; never deny a manifest over catalogue state
        logger.exception("catalogue plan resolution failed; issuing a degraded entitlement")
        return failed

    if plan is None:
        # Not `degraded`: nothing failed, and clamping the manifest here would shorten every
        # artefact in an environment whose catalogue is simply not seeded yet. But it must
        # not be silent either — reaching this line at all means no assignment, no scope
        # alias and no fallback plan exists, which after DEC-014 means the catalogue's own
        # seed data is missing rather than that this one licence was missed.
        logger.warning(
            "catalogue resolved no plan for licence %s; issuing an entitlement with NO "
            "grants. Nothing failed — the catalogue has no assignment, no matching scope "
            "alias and no fallback plan, so it is unseeded. Check that the catalogue "
            "migrations ran in this environment.",
            getattr(license_key, "id", "<unknown>"),
        )
        return unconfigured

    try:
        grants = _plan_grant_map(plan, current_revision())
        # COPY, always. `grants.values` is the read-only entry shared by every tenant on
        # this plan; the overrides below are one licence's. Writing them into the shared
        # entry would hand licence A's exception to every other org on the same plan —
        # a cross-tenant entitlement leak, from one missing `dict(...)`.
        values = dict(grants.values)
        published = set(grants.published)

        # Per-licence deviations, applied last. Bounded by the dimension cap: a licence
        # cannot carry more overrides than there are dimensions it can override.
        # Restricted to the dimensions in this plan's map, IN SQL. This is the single
        # enforcement point for three separate properties, which is why it is not duplicated
        # in Python afterwards:
        #
        #   * ORDER INDEPENDENCE — selecting broadly and discarding afterwards would make
        #     the outcome depend on row order: a licence with more override rows than the
        #     cap could have its slice filled entirely with rows destined for the bin,
        #     silently dropping the overrides that did apply.
        #   * THE MERGED BOUND — `known` holds at most `MAX_GRANT_DIMENSIONS` keys and the
        #     unique (licence, dimension) constraint allows one override each, so the merged
        #     map cannot exceed the cap the plan map already obeys.
        #   * RESTRICTED KEYS — `known` comes from `_active_dimensions`, which drops keys
        #     colliding with a restricted payload field, so an override cannot smuggle one
        #     into the signed payload and deny this licence its manifest.
        overrides = (
            LicenseGrantOverride.objects.filter(
                license_key=license_key,
                dimension__is_active=True,
                dimension__key__in=grants.known,
            )
            .filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
            )
            .select_related("dimension")
        )
        # No `order_by` and no slice: `known` holds at most `MAX_GRANT_DIMENSIONS` keys and
        # the unique (licence, dimension) constraint allows one override per key, so this
        # returns a bounded set whose MEMBERSHIP does not depend on ordering. Adding either
        # would be a guard no mutation can reach — indistinguishable from a broken one.
        for override in overrides:
            dimension = override.dimension
            # No `known` re-check here on purpose. The queryset above already restricts to
            # `grants.known`, and a second, redundant guard in Python would make BOTH
            # untestable: remove either one and the other silently covers for it, so neither
            # can be shown to work. One enforcement point, in SQL, that a mutation can reach.
            value = coerce_grant_value(dimension.value_type, override.raw_value)
            if value is _UNSET:
                logger.warning(
                    "catalogue override for dimension %r is unreadable; keeping the plan value",
                    dimension.key,
                )
                continue
            values[dimension.key] = value
            # Publishability is a property of the DIMENSION, never of one customer's
            # exception — but an override can be the first thing to give a publishable
            # dimension a value at all (when the plan declares none and the dimension has
            # no default), and that value must still reach the client. So recompute both
            # directions rather than only guarding one: `add` when the override supplies
            # the first value for a publishable dimension, `discard` so an override can
            # never push an unpublishable one onto the wire.
            if dimension.publish_in_manifest:
                published.add(dimension.key)
            else:
                published.discard(dimension.key)

        # The merged map is bounded by the same cap as the plan map, not by cap + overrides.
        #
        # INSIDE the try deliberately. This module is contracted never to raise on the
        # issuance path (NFR-024), and this assert was the one statement on that path that
        # could — turning a broken invariant into a DENIED manifest, which is precisely the
        # failure the degrade-never-raise design exists to prevent. Inside, a violated
        # invariant takes the degraded path instead: the licence still gets a manifest, that
        # manifest is short-lived, and it is logged and audited so an operator sees it.
        #
        # It stays an `assert` rather than a raised error because it restates a property the
        # SQL above already guarantees (overrides are restricted to `known`), so it is a
        # development tripwire, not a runtime control. Under `python -O` it vanishes
        # entirely — also non-raising, so the contract holds either way. The bound itself is
        # covered by a real test with a positive control, never by this line.
        assert len(values) <= MAX_GRANT_DIMENSIONS, (
            f"resolved {len(values)} grants against a cap of {MAX_GRANT_DIMENSIONS}"
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("catalogue grant resolution failed; issuing a degraded entitlement")
        return failed

    return ResolvedEntitlement(
        plan=plan,
        values=values,
        plan_display_label=plan.display_name,
        published_values=MappingProxyType(
            {key: value for key, value in values.items() if key in published}
        ),
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

    # Neither a plan code nor a dimension key can contain a control character, so a value that
    # does takes the SAME NOT_FOUND an unknown code takes. Skipping the query is the fix:
    # Postgres raises an unmapped `DataError` on `filter(code="PRO\x00")` while SQLite already
    # returns None and lands on that refusal. See `CONTROL_CHARACTERS_RE`.
    unlookupable = [
        name
        for name, value in (("plan_code", plan_code), ("dimension_key", dimension_key))
        if has_control_characters(value)
    ]
    if unlookupable:
        logger.warning(
            "refused a plan-grant write: %s contains a control character and cannot name a "
            "catalogue row. Refused as not found. Requested by actor %s.",
            " and ".join(unlookupable),
            staff.actor_id,
        )
        raise SafeAPIError(ErrorCode.NOT_FOUND)

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
            # Who changed it and why travel WITH the value. A stale actor beside a fresh
            # number would name the wrong person for the change that is actually live.
            existing.changed_by_actor_id = staff.actor_id
            existing.reason = reason
            existing.save(
                update_fields=["raw_value", "changed_by_actor_id", "reason", "updated_at"]
            )
            grant, created = existing, False
        else:
            try:
                with transaction.atomic():
                    grant = PlanGrant.objects.create(
                        plan=plan,
                        dimension=dimension,
                        raw_value=raw_value,
                        changed_by_actor_id=staff.actor_id,
                        reason=reason,
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
                grant.changed_by_actor_id = staff.actor_id
                grant.reason = reason
                grant.save(
                    update_fields=["raw_value", "changed_by_actor_id", "reason", "updated_at"]
                )
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

        if existing is not None and existing.idempotency_key == idempotency_key:
            # Idempotent replay. Returning early is not a nicety here: re-saving would push
            # `expires_at` another 90 days into the future and write a second audit event,
            # so a retried request would silently extend the very time-box the ceremony
            # exists to impose.
            return SetLicenseGrantOverrideResult(
                override=existing, created=False, previous_raw_value=previous
            )

        if existing is not None:
            existing.raw_value = raw_value
            existing.granted_by_actor_id = staff.actor_id
            existing.reason = reason
            existing.expires_at = expires_at
            existing.idempotency_key = idempotency_key
            existing.save(
                update_fields=[
                    "raw_value",
                    "granted_by_actor_id",
                    "reason",
                    "expires_at",
                    "idempotency_key",
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
                        idempotency_key=idempotency_key,
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
                override.idempotency_key = idempotency_key
                override.save(
                    update_fields=[
                        "raw_value",
                        "granted_by_actor_id",
                        "reason",
                        "expires_at",
                        "idempotency_key",
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


@dataclass(frozen=True)
class SetLicensePlanAssignmentData:
    idempotency_key: str
    license_key_id: str
    plan_code: str
    reason: str


@dataclass(frozen=True)
class SetLicensePlanAssignmentResult:
    assignment: LicensePlanAssignment
    created: bool
    previous_plan_code: str | None


def set_license_plan_assignment(
    actor: ActorContext | None, data: SetLicensePlanAssignmentData
) -> SetLicensePlanAssignmentResult:
    """Place one licence on a plan — the governed path for the operator lever.

    Moving a church from one tier to another changes what it is entitled to and what it
    will be billed for. Without this, the only way to do it was a bare `objects.create()`
    that recorded neither who did it nor why.
    """
    staff = require_staff_permission(actor, StaffPermission.GRANT_ENTITLEMENT)
    idempotency_key = validate_idempotency_key(data.idempotency_key)
    reason = require_reason(data.reason)
    plan_code = (data.plan_code or "").strip()
    if not plan_code:
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

    # Same refusal as an unknown plan code, for the reason above.
    if has_control_characters(plan_code):
        logger.warning(
            "refused to assign licence %s: plan_code contains a control character, so it "
            "cannot name a catalogue plan. Refused as not found. Requested by actor %s.",
            data.license_key_id,
            staff.actor_id,
        )
        raise SafeAPIError(ErrorCode.NOT_FOUND)

    with transaction.atomic():
        plan = Plan.objects.filter(code=plan_code).first()
        license_key = _license_key_model().objects.filter(id=data.license_key_id).first()
        if plan is None or license_key is None:
            raise SafeAPIError(ErrorCode.NOT_FOUND)

        # The same refusal as issuance (DEC-014), for the same reason. Moving a licence ONTO
        # the fallback grants it the catalogue's most permissive values for the rest of its
        # life, signed and cached offline — identical in effect to issuing onto it, so
        # closing only the issuance door would leave the hole open one function away. The
        # governed path carries a permission, a reason and an audit row, but ceremony does
        # not stop a typo: that is the argument already written beside
        # `accountability_constraints`, applied here.
        #
        # This does NOT touch resolution. A licence with no assignment still falls back
        # exactly as it did (`resolve_plan_for_license`), which is what keeps pre-catalogue
        # licences whole — the refusal is on writing an assignment, not on reading one.
        # Restoring a licence to fallback behaviour therefore means DELETING its assignment
        # row, not assigning the fallback: a deliberate data repair rather than a routine
        # operator lever, which is the right weight for an action that grants unlimited
        # everything.
        if plan.is_fallback:
            logger.warning(
                "refused to assign licence %s to plan %r (%s): it is the catalogue's "
                "designated fallback (is_fallback=True) and grants the catalogue's most "
                "permissive values. To restore fallback behaviour, delete the licence's "
                "assignment row so resolution falls through. Requested by actor %s.",
                data.license_key_id,
                plan.code,
                plan.display_name,
                staff.actor_id,
            )
            raise SafeAPIError(
                ErrorCode.POLICY_DENIED,
                f"Plan {plan.code!r} ({plan.display_name}) is the catalogue's designated "
                "fallback, not a sellable tier. Assigning a licence to it would grant the "
                "catalogue's most permissive values for the rest of the licence's life, "
                "cached offline until it expires. Assign the plan the customer is actually "
                "on; to restore pre-catalogue behaviour, remove the assignment instead.",
            )

        existing = LicensePlanAssignment.objects.select_related("plan").filter(
            license_key=license_key
        ).first()
        previous = existing.plan.code if existing is not None else None

        if existing is not None and existing.idempotency_key == idempotency_key:
            return SetLicensePlanAssignmentResult(
                assignment=existing, created=False, previous_plan_code=previous
            )

        if existing is not None:
            existing.plan = plan
            existing.assigned_by_actor_id = staff.actor_id
            existing.reason = reason
            existing.idempotency_key = idempotency_key
            existing.save(
                update_fields=[
                    "plan",
                    "assigned_by_actor_id",
                    "reason",
                    "idempotency_key",
                    "updated_at",
                ]
            )
            assignment, created = existing, False
        else:
            try:
                with transaction.atomic():
                    assignment = LicensePlanAssignment.objects.create(
                        license_key=license_key,
                        plan=plan,
                        assigned_by_actor_id=staff.actor_id,
                        reason=reason,
                        idempotency_key=idempotency_key,
                    )
                created = True
            except IntegrityError:
                # A racing writer won the one-to-one on the licence.
                assignment = LicensePlanAssignment.objects.select_related("plan").filter(
                    license_key=license_key
                ).first()
                if assignment is None:
                    raise SafeAPIError(ErrorCode.CONFLICT) from None
                previous = assignment.plan.code
                assignment.plan = plan
                assignment.assigned_by_actor_id = staff.actor_id
                assignment.reason = reason
                assignment.idempotency_key = idempotency_key
                assignment.save(
                    update_fields=[
                        "plan",
                        "assigned_by_actor_id",
                        "reason",
                        "idempotency_key",
                        "updated_at",
                    ]
                )
                created = False

        record_audit_event(
            staff,
            action="catalogue.license_plan_assigned",
            target_type="catalogue_license_plan_assignment",
            target_id=str(assignment.pk),
            request_id=idempotency_key,
            reason=reason,
            before={"plan_code": previous} if previous is not None else None,
            after={"license_key_id": str(license_key.id), "plan_code": plan.code},
        )
        return SetLicensePlanAssignmentResult(
            assignment=assignment, created=created, previous_plan_code=previous
        )
