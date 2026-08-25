"""Product catalogue — plans, grant dimensions and grant values as DATA (FR-544).

The whole point of this app is that **nothing here is an enum of tiers**. `Plan.code` has
no `choices`, `GrantDimension.key` has no `choices`, and no value in this package is
compared against a tier name anywhere in the codebase. Renaming "Platinum", adding a
fourth tier, or changing Pro's STT allowance from 5 hours to 8 is an UPDATE against a row
— no deploy, no migration, no client release (DEC-008; owner verbatim: "the names can
change in the nearest future, the hrs for STT can also change as this is dependent on the
AI subscription we start using").

Three layers resolve an entitlement, most specific first (`services.resolve_entitlement`):

    LicenseGrantOverride   one licence deviates on one dimension (how the pre-catalogue
                           `device_limit` values are preserved, see migration 0003)
    PlanGrant              the plan's value for that dimension
    GrantDimension.default the catalogue-wide default when a plan declares nothing

And a licence reaches a plan, most specific first:

    LicensePlanAssignment  explicit, the forward-looking operator lever
    PlanScopeAlias         the legacy `feature_scope` label bridge (FR-545 demotes that
                           field to a display label; this is what carries the old rows)
    Plan(is_fallback=True) the designated fallback

**Dimension KEYS are a wire contract; plan codes and grant VALUES are data.** The client
(EPIC-PL-C) is written against `screen_outputs`, `ndi_outputs`, `watermark`, … and never
against a tier name — that is precisely FR-545. So a dimension key is a stable identifier
in the same sense a JSON field name is; a plan code is not, and must never be branched on.
"""

from __future__ import annotations

from django.db import models


class PlanStatus(models.TextChoices):
    """Lifecycle of a catalogue row — NOT a tier. Adding a tier never touches this."""

    ACTIVE = "ACTIVE", "Active"
    # Still resolvable for licences already on it, but not offered to new ones.
    RETIRED = "RETIRED", "Retired"


class GrantValueType(models.TextChoices):
    BOOLEAN = "BOOLEAN", "Boolean flag"
    INTEGER = "INTEGER", "Integer count"


# The one non-numeric INTEGER value. Resolves to Python ``None`` and serialises as JSON
# ``null``, meaning "no limit" — which is what every licence issued before this catalogue
# existed effectively had on outputs and NDI, since nothing enforced them.
UNLIMITED = "unlimited"

# A single plan's grant map is cached (see cache.py); this caps how large one cache entry
# can get, so inserting ten thousand dimension rows cannot grow an entry without bound.
# Dimensions past the cap are simply not emitted, which degrades to the client's own
# default rather than failing (NFR-024).
MAX_GRANT_DIMENSIONS = 64

# Pinning the premise beside the constant: a cap of 0/1 would make the "the 65th dimension
# is dropped, the first 64 survive" test vacuous, and a cap below the five decided
# dimensions (DEC-008) would silently drop a decided grant.
assert MAX_GRANT_DIMENSIONS >= 8, "MAX_GRANT_DIMENSIONS must leave room for the decided dimensions"


class Plan(models.Model):
    """One purchasable/assignable tier, as a row.

    `code` is an internal stable handle for operators and migrations. It is deliberately
    NOT choices-constrained and deliberately never compared against a literal in code —
    `tests/test_product_catalogue_slice.py` sweeps the source to prove it.
    `display_name` is free to change at any time and changes nothing behavioural.
    """

    code = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=PlanStatus.choices, default=PlanStatus.ACTIVE)
    # Offered on public surfaces (pricing page, portal). The legacy bridge plan is not.
    is_public = models.BooleanField(default=True)
    # The plan used when a licence resolves to nothing else. Exactly one row may carry it.
    is_fallback = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Partial unique over the literal True: at most one fallback plan can exist,
            # enforced by the database rather than by a convention someone can forget.
            models.UniqueConstraint(
                fields=["is_fallback"],
                condition=models.Q(is_fallback=True),
                name="uniq_catalogue_fallback_plan",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "sort_order"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self) -> str:
        return self.display_name


class GrantDimension(models.Model):
    """One thing a plan can grant — a seat cap, an output cap, a watermark flag.

    All five DEC-008 dimensions are rows seeded by migration 0002; a sixth is an INSERT.
    """

    key = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    value_type = models.CharField(max_length=16, choices=GrantValueType.choices)
    # Used when a plan declares no value for this dimension. Also the safe-degrade value.
    default_raw_value = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    # The dimension that supplies the manifest's `instances_limit`. Keeping this as DATA is
    # what stops the manifest builder from naming a dimension key in a code branch.
    governs_instance_limit = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["governs_instance_limit"],
                condition=models.Q(governs_instance_limit=True),
                name="uniq_catalogue_instance_limit_dimension",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active", "sort_order"]),
        ]

    def __str__(self) -> str:
        return self.key


class PlanGrant(models.Model):
    """What one plan grants on one dimension. Changing `raw_value` is the whole point."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="grants")
    dimension = models.ForeignKey(GrantDimension, on_delete=models.CASCADE, related_name="grants")
    raw_value = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plan", "dimension"], name="uniq_catalogue_plan_grant"),
        ]
        indexes = [
            models.Index(fields=["plan"]),
        ]

    def __str__(self) -> str:
        return f"{self.plan.code}:{self.dimension.key}={self.raw_value}"


class PlanScopeAlias(models.Model):
    """Legacy `feature_scope` label → plan.

    `AppLicenseKey.feature_scope` is a free string that predates this catalogue and is
    demoted by FR-545 to a display label. Every distinct value found in the database is
    given a row here by migration 0003 so no existing licence is left unmapped, and so an
    operator can later repoint "CHURCH" at a real tier without touching a licence row.
    """

    feature_scope = models.CharField(max_length=64, unique=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="scope_aliases")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.feature_scope} -> {self.plan.code}"


class LicensePlanAssignment(models.Model):
    """A licence explicitly placed on a plan. The forward-looking operator lever.

    Lives here rather than as a column on `AppLicenseKey` so the catalogue owns its own
    schema and licence issuance stays untouched.
    """

    license_key = models.OneToOneField(
        "selahcue_license_keys.AppLicenseKey",
        on_delete=models.CASCADE,
        related_name="catalogue_plan_assignment",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="license_assignments")
    assigned_by_actor_id = models.CharField(max_length=128, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"license {self.license_key_id} -> {self.plan.code}"


class LicenseGrantOverride(models.Model):
    """One licence deviating from its plan on one dimension.

    This is how the migration preserves entitlement exactly: a licence hand-issued with
    `device_limit=5` keeps 5 whatever its plan says (migration 0003).
    """

    license_key = models.ForeignKey(
        "selahcue_license_keys.AppLicenseKey",
        on_delete=models.CASCADE,
        related_name="catalogue_grant_overrides",
    )
    dimension = models.ForeignKey(GrantDimension, on_delete=models.CASCADE, related_name="overrides")
    raw_value = models.CharField(max_length=64)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["license_key", "dimension"],
                name="uniq_catalogue_license_grant_override",
            ),
        ]
        indexes = [
            models.Index(fields=["license_key"]),
        ]

    def __str__(self) -> str:
        return f"license {self.license_key_id}:{self.dimension.key}={self.raw_value}"


class CatalogueRevision(models.Model):
    """Single row (pk=1) bumped whenever any catalogue row changes (see signals.py).

    The in-process grant cache keys on this, so an operator's data edit takes effect in
    every worker process without a restart — which is what "no release" in FR-544 actually
    requires. One indexed primary-key read per resolution buys that, and unlike a
    cache-backend generation counter it cannot go stale or be flushed independently.
    """

    SINGLETON_PK = 1

    revision = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"catalogue revision {self.revision}"
