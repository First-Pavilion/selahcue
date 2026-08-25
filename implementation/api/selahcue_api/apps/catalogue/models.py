"""Product catalogue — plans, grant dimensions and grant values as DATA (FR-544).

The whole point of this app is that **nothing here is an enum of tiers**. `Plan.code` has
no `choices`, `GrantDimension.key` has no `choices`, and no value in this package is
compared against a tier name anywhere in the codebase. Renaming "Platinum", adding a
fourth tier, or changing Pro's STT allowance from 5 hours to 8 is an UPDATE against a row
— no deploy, no migration, no client release (DEC-008; owner verbatim: "the names can
change in the nearest future, the hrs for STT can also change as this is dependent on the
AI subscription we start using").

Three layers resolve an entitlement, most specific first (`services.resolve_entitlement`):

    LicenseGrantOverride   one licence deviates on one dimension, time-boxed and audited
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

**The catalogue does not publish seat caps to the manifest.** `AppLicenseKey.device_limit`
is the number activation actually enforces, and it is the only number the manifest reports
as `instances_limit`. A plan's `device_instances` grant is the catalogue's view of what a
tier *should* allow; FR-516's write-back is what makes a plan change move `device_limit`,
so the two agree by construction rather than by coincidence. A signed, offline-cached
artefact must never carry two fields that disagree about the same quantity.
"""

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

# Dimension keys travel into a SIGNED payload, and a signed manifest is cached offline for
# the licence's lifetime — so once a key ships it is effectively permanent. The field is
# operator-settable free text, which makes an allow-list (not just the restricted-field
# denylist in graphql/redaction.py) the right shape: lowercase, ASCII, snake_case, starting
# with a letter. Anything else is refused at write time AND by a database check constraint.
GRANT_KEY_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"

# Held back for first-party payload use, so a future internal key can never collide with
# one an operator already shipped in a signed manifest. Forbidden outright rather than
# merely discouraged: the seeded dimensions use plain names and need none of these.
RESERVED_GRANT_KEY_PREFIXES = ("selahcue_", "sc_")

validate_grant_key = RegexValidator(
    regex=GRANT_KEY_PATTERN,
    message=(
        "A grant dimension key must be lowercase ASCII snake_case, start with a letter, "
        "and be at most 64 characters."
    ),
)


class GrantValueType(models.TextChoices):
    BOOLEAN = "BOOLEAN", "Boolean flag"
    INTEGER = "INTEGER", "Integer count"


# The one non-numeric INTEGER value. Resolves to Python ``None`` and serialises as JSON
# ``null``, meaning "no limit" — which is what every licence issued before this catalogue
# existed effectively had on outputs and NDI, since nothing enforced them.
#
# ``unlimited`` and "not granted" are DELIBERATELY different states with different
# encodings: ``null`` means the catalogue grants this dimension without a ceiling, while an
# ABSENT key means the catalogue expresses nothing about it and the client applies its own
# default. Collapsing the two onto one value is how a payload ends up contradicting itself.
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


def is_reserved_grant_key(key: str) -> bool:
    return str(key).lower().startswith(RESERVED_GRANT_KEY_PREFIXES)


class Plan(models.Model):
    """One assignable tier, as a row.

    `code` is an internal stable handle for operators and migrations. It is deliberately
    NOT choices-constrained and deliberately never compared against a literal in code —
    `tests/test_product_catalogue_slice.py` sweeps the source to prove it.
    `display_name` is free to change at any time and changes nothing behavioural.

    Deliberately no `status`/`is_public` columns: nothing offers plans yet (there is no
    pricing surface and no self-serve assignment), so a lifecycle flag would be a field
    declared and never read — indistinguishable from one that is read and enforced. They
    come back with the surface that needs them.
    """

    code = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
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
            models.Index(fields=["sort_order"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self) -> str:
        return self.display_name


class GrantDimension(models.Model):
    """One thing a plan can grant — an output cap, a seat count, a watermark flag.

    All five DEC-008 dimensions are rows seeded by migration 0002; a sixth is an INSERT.

    An EMPTY `default_raw_value` is meaningful and supported: it means "no catalogue-wide
    default", so a plan that declares nothing for this dimension leaves the key ABSENT from
    the resolved grants rather than publishing a value nobody chose.
    """

    key = models.CharField(max_length=64, unique=True, validators=[validate_grant_key])
    display_name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    value_type = models.CharField(max_length=16, choices=GrantValueType.choices)
    default_raw_value = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # The allow-list, at the database. A validator alone only binds callers that
            # remember to run `full_clean()`; this binds every writer including a shell.
            models.CheckConstraint(
                condition=models.Q(key__regex=GRANT_KEY_PATTERN),
                name="catalogue_grant_key_charset",
            ),
            models.CheckConstraint(
                condition=~models.Q(key__startswith="selahcue_")
                & ~models.Q(key__startswith="sc_"),
                name="catalogue_grant_key_not_reserved",
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

    A per-customer exception to the commercial model, so it carries the same ceremony as
    any other entitlement write: who granted it, why, and — by default — when it lapses.
    `expires_at` is nullable so a deliberate permanent exception is expressible, but the
    service time-boxes by default, because every legitimate case observed so far is
    temporary and a forgotten override is an unpriced entitlement that nobody revisits.
    """

    license_key = models.ForeignKey(
        "selahcue_license_keys.AppLicenseKey",
        on_delete=models.CASCADE,
        related_name="catalogue_grant_overrides",
    )
    dimension = models.ForeignKey(GrantDimension, on_delete=models.CASCADE, related_name="overrides")
    raw_value = models.CharField(max_length=64)
    granted_by_actor_id = models.CharField(max_length=128)
    reason = models.TextField()
    # NULL = never expires (deliberate, and the exception rather than the rule).
    expires_at = models.DateTimeField(null=True, blank=True)
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
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"license {self.license_key_id}:{self.dimension.key}={self.raw_value}"


class CatalogueRevision(models.Model):
    """Single row (pk=1) bumped whenever cached catalogue data changes (see signals.py).

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
