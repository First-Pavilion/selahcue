"""Product catalogue — plans, limits and grants as data (FR-544).

The load-bearing test in this file is `test_no_plan_name_is_hardcoded_in_the_api_source`.
Everything else can be true while the catalogue is still quietly useless: if one `if plan
== "PRO"` exists anywhere, renaming a tier becomes a release and the owner's stated
requirement is broken. That test parses every module under `selahcue_api/` and fails on a
whole-string literal equal to any seeded plan code or display name — and it asserts, as a
positive control, that it still finds those names inside the one file allowed to contain
them. Without the control, moving or renaming the seed migration would leave a sweep that
searches for nothing and passes forever.

Module-local seeding helpers, mirroring tests/test_entitlement_manifest_slice.py. The
shipped slices each build their own rather than sharing a conftest.py — follow that.
"""

from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

import selahcue_api
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.catalogue import services as catalogue_services
from selahcue_api.apps.catalogue.cache import (
    CACHE_TTL_SECONDS,
    GRANT_CACHE,
    MAX_CACHE_ENTRIES,
    BoundedGrantCache,
)
from selahcue_api.apps.catalogue.models import (
    MAX_GRANT_DIMENSIONS,
    GrantDimension,
    GrantValueType,
    LicenseGrantOverride,
    LicensePlanAssignment,
    Plan,
    PlanGrant,
    PlanScopeAlias,
)
from selahcue_api.apps.catalogue.services import (
    DEFAULT_OVERRIDE_DAYS,
    SetLicenseGrantOverrideData,
    SetPlanGrantData,
    current_revision,
    resolve_entitlement,
    set_license_grant_override,
    set_plan_grant,
)
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus, LicenseKeyType
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = pytest.mark.django_db

API_ROOT = Path(selahcue_api.__file__).resolve().parent
SEED_MIGRATION = (
    API_ROOT / "apps" / "catalogue" / "migrations" / "0002_seed_catalogue_reference_data.py"
)

# Dimension KEYS are a wire contract (FR-545: the client is written against them), so
# naming them in a test is not the thing FR-544 forbids — naming a TIER is.
SEAT_KEY = "device_instances"
SCREEN_KEY = "screen_outputs"
NDI_KEY = "ndi_outputs"
STT_KEY = "stt_minutes_per_period"
WATERMARK_KEY = "watermark"


@pytest.fixture(autouse=True)
def _cold_grant_cache():
    """The grant cache is a process-global; a neighbouring test's entries would otherwise
    survive this test's database rollback and answer from a superseded world."""
    GRANT_CACHE.clear()
    yield
    GRANT_CACHE.clear()


def _org(tag):
    from selahcue_api.apps.accounts.models import CustomerOrg

    return CustomerOrg.objects.create(
        name=f"Catalogue Church {tag}",
        slug=f"catalogue-church-{tag}",
        primary_contact_email=f"ops+{tag}@catalogue.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        device_limit=1,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"catalogue-org-{tag}",
    )


def _license_key(*, tag, feature_scope="CHURCH", device_limit=1, org=None):
    """A licence row created directly, as tests/test_customer_auth_slice.py does — the
    generation service is not under test here and would only add throttle surface."""
    now = timezone.now().replace(microsecond=0)
    return AppLicenseKey.objects.create(
        customer=org or _org(tag),
        key_type=LicenseKeyType.TRIAL,
        status=LicenseKeyStatus.ACTIVATED,
        key_prefix=f"SC-TRIAL-{tag}"[:32],
        key_suffix=tag[-4:].rjust(4, "x"),
        masked_key=f"SC-TRIAL-{tag}...{tag[-4:]}"[:64],
        secret_hash="x",
        secret_fingerprint=f"catalogue-fp-{tag}",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        timezone="Africa/Lagos",
        feature_scope=feature_scope,
        seat_limit=5,
        device_limit=device_limit,
        territory="NG",
        generated_by_actor_id="staff_ops_1",
        generated_reason="Catalogue slice tests.",
        idempotency_key=f"catalogue-license-{tag}",
    )


def _dimension(key):
    return GrantDimension.objects.get(key=key)


def _staff(*permissions):
    return ActorContext(
        kind=ActorKind.STAFF,
        actor_id="staff_ops_1",
        staff_permissions=frozenset(permissions),
    )


def _assign(license_key, plan):
    return LicensePlanAssignment.objects.create(license_key=license_key, plan=plan)


def _override(license_key, dimension_key, raw_value, *, expires_at=None):
    """A row written directly. The governed path is `set_license_grant_override`, tested
    separately; resolution must behave the same however the row got there."""
    return LicenseGrantOverride.objects.create(
        license_key=license_key,
        dimension=_dimension(dimension_key),
        raw_value=raw_value,
        granted_by_actor_id="staff_ops_1",
        reason="Test override.",
        expires_at=expires_at,
    )


def _seeded_plan_names() -> set[str]:
    """Every plan code and display name currently in the catalogue, case-folded."""
    names: set[str] = set()
    for code, display_name in Plan.objects.values_list("code", "display_name"):
        names.add(code.strip().casefold())
        names.add(display_name.strip().casefold())
    names.discard("")
    return names


def _string_constants(path: Path) -> set[str]:
    """Every whole string literal in a module, case-folded.

    Whole strings, not substrings: a docstring that mentions Platinum in a sentence is
    documentation, while `== "PLATINUM"` is the branch this test exists to catch.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.value.strip().casefold()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


# --- The requirement itself ---------------------------------------------------------------


def test_plan_and_dimension_identifiers_are_not_enumerated_in_code():
    """No `choices` on the identifier fields: a tier cannot be added to an enum, because
    there is no enum. Adding one would make this fail."""
    assert Plan._meta.get_field("code").choices is None
    assert GrantDimension._meta.get_field("key").choices is None


def test_no_plan_name_is_hardcoded_in_the_api_source():
    plan_names = _seeded_plan_names()
    assert plan_names, "no plans are seeded, so the sweep would have nothing to look for"

    # Positive control, asserted BEFORE the contract: the scanner and the name set must be
    # demonstrably able to find a tier name, or "no offenders" means only that the sweep is
    # dead. If the seed migration is renamed or its names change, this fails loudly here
    # rather than silently disarming the sweep below.
    assert SEED_MIGRATION.exists(), f"{SEED_MIGRATION} is missing; the sweep's control is gone"
    found_in_seed = plan_names & _string_constants(SEED_MIGRATION)
    assert found_in_seed, (
        "the sweep found no seeded plan name inside the seed migration, so it is not "
        "actually capable of detecting a hardcoded tier name anywhere else"
    )

    offenders = []
    scanned = 0
    for path in sorted(API_ROOT.rglob("*.py")):
        if path == SEED_MIGRATION:
            continue
        scanned += 1
        for literal in plan_names & _string_constants(path):
            offenders.append(f"{path.relative_to(API_ROOT)}: {literal!r}")

    # Second control, on the iteration rather than the scanner: a sweep that reaches almost
    # no files reports "no offenders" for the wrong reason. The API has ~70 modules; 20 is
    # a floor that a broken glob or an over-eager skip cannot clear.
    assert scanned > 20, f"the sweep only visited {scanned} modules, so it proves nothing"

    assert offenders == [], (
        "a plan name is hardcoded in the API source, which makes renaming a tier a code "
        "release (FR-544). Resolve the plan from the catalogue instead:\n  "
        + "\n  ".join(offenders)
    )


def test_renaming_a_plan_changes_nothing_behavioural():
    plan = Plan.objects.get(code="PRO")
    key = _license_key(tag="rename")
    _assign(key, plan)
    before = dict(resolve_entitlement(key).values)

    plan.display_name = "Renamed By The Owner"
    plan.save(update_fields=["display_name", "updated_at"])

    after = resolve_entitlement(key)
    assert after.values == before, "renaming a plan changed what it grants"
    assert after.plan_display_label == "Renamed By The Owner"


def test_changing_a_grant_value_takes_effect_without_a_release():
    """The owner's stated case: Pro's STT allowance moves when the AI subscription does."""
    plan = Plan.objects.get(code="PRO")
    key = _license_key(tag="stt")
    _assign(key, plan)
    assert resolve_entitlement(key).values[STT_KEY] == 300

    grant = PlanGrant.objects.get(plan=plan, dimension=_dimension(STT_KEY))
    grant.raw_value = "480"
    grant.save(update_fields=["raw_value", "updated_at"])

    assert resolve_entitlement(key).values[STT_KEY] == 480


def test_a_signal_bypassing_edit_still_propagates_once_the_ttl_lapses(monkeypatch):
    """`QuerySet.update()` and raw SQL fire no signals, so the revision counter never moves.
    The TTL is the only thing that stops such an edit being invisible until a restart."""
    ticks = [1000.0]
    cache = BoundedGrantCache(clock=lambda: ticks[0])
    monkeypatch.setattr(catalogue_services, "GRANT_CACHE", cache)

    plan = Plan.objects.get(code="PRO")
    key = _license_key(tag="ttl")
    _assign(key, plan)
    assert resolve_entitlement(key).values[NDI_KEY] == 5

    # No signal fires for this, on purpose — that is the blind spot under test.
    PlanGrant.objects.filter(plan=plan, dimension=_dimension(NDI_KEY)).update(raw_value="9")
    assert resolve_entitlement(key).values[NDI_KEY] == 5, (
        "the cached entry was not actually being served, so the TTL below proves nothing"
    )

    ticks[0] += CACHE_TTL_SECONDS + 1
    assert resolve_entitlement(key).values[NDI_KEY] == 9


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("FREE", {SEAT_KEY: 1, SCREEN_KEY: 2, NDI_KEY: 0, STT_KEY: 30, WATERMARK_KEY: True}),
        ("PRO", {SEAT_KEY: 3, SCREEN_KEY: 5, NDI_KEY: 5, STT_KEY: 300, WATERMARK_KEY: False}),
        (
            "PLATINUM",
            {SEAT_KEY: 7, SCREEN_KEY: 10, NDI_KEY: 10, STT_KEY: 600, WATERMARK_KEY: False},
        ),
    ],
)
def test_the_decided_tier_table_is_expressible_and_seeded(code, expected):
    """All five DEC-008 dimensions, as typed values, for each decided tier."""
    key = _license_key(tag=f"table-{code.lower()}")
    _assign(key, Plan.objects.get(code=code))
    assert resolve_entitlement(key).values == expected


def test_a_brand_new_tier_is_honoured_with_no_code_change():
    """A tier that did not exist when this code was written resolves correctly, which is
    only possible if nothing enumerates tiers."""
    plan = Plan.objects.create(code="RUBY", display_name="Ruby", sort_order=40)
    novel = {SEAT_KEY: "11", SCREEN_KEY: "13", NDI_KEY: "17", STT_KEY: "1999", WATERMARK_KEY: "false"}
    for dimension_key, raw_value in novel.items():
        PlanGrant.objects.create(plan=plan, dimension=_dimension(dimension_key), raw_value=raw_value)

    key = _license_key(tag="ruby")
    _assign(key, plan)
    assert resolve_entitlement(key).values == {
        SEAT_KEY: 11,
        SCREEN_KEY: 13,
        NDI_KEY: 17,
        STT_KEY: 1999,
        WATERMARK_KEY: False,
    }


# --- Resolution precedence -----------------------------------------------------------------


def test_an_explicit_assignment_beats_the_legacy_scope_alias():
    PlanScopeAlias.objects.create(feature_scope="CHURCH", plan=Plan.objects.get(code="FREE"))
    key = _license_key(tag="prec1", feature_scope="CHURCH")
    _assign(key, Plan.objects.get(code="PLATINUM"))
    assert resolve_entitlement(key).values[SCREEN_KEY] == 10


def test_a_scope_alias_beats_the_fallback():
    PlanScopeAlias.objects.create(feature_scope="CHURCH", plan=Plan.objects.get(code="PRO"))
    key = _license_key(tag="prec2", feature_scope="CHURCH")
    assert resolve_entitlement(key).values[SCREEN_KEY] == 5


def test_the_scope_alias_lookup_is_case_insensitive():
    """Pre-catalogue rows were written by two different paths and are not uniformly cased."""
    PlanScopeAlias.objects.create(feature_scope="CHURCH", plan=Plan.objects.get(code="PRO"))
    key = _license_key(tag="prec3", feature_scope="church")
    assert resolve_entitlement(key).values[SCREEN_KEY] == 5


def test_an_unmapped_licence_falls_back_to_the_designated_plan():
    key = _license_key(tag="prec4", feature_scope="NEVER-SEEN-BEFORE")
    resolved = resolve_entitlement(key)
    assert resolved.plan is not None
    assert resolved.plan.is_fallback is True


def test_a_licence_override_beats_its_plans_value():
    key = _license_key(tag="prec5", device_limit=1)
    _assign(key, Plan.objects.get(code="PRO"))
    _override(key, NDI_KEY, "9")
    resolved = resolve_entitlement(key)
    assert resolved.values[NDI_KEY] == 9
    # Only the overridden dimension moves.
    assert resolved.values[SCREEN_KEY] == 5


def test_only_one_plan_may_be_the_fallback():
    """A second fallback would make resolution depend on row order. The database refuses."""
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Plan.objects.create(code="SECOND-FALLBACK", display_name="Second", is_fallback=True)


# --- Safe degradation (NFR-024) ------------------------------------------------------------


def test_an_unseeded_catalogue_resolves_to_nothing_and_raises_nothing():
    """A licensing lookup must never be the reason a device is refused its entitlement."""
    key = _license_key(tag="empty")
    PlanScopeAlias.objects.all().delete()
    LicensePlanAssignment.objects.all().delete()
    PlanGrant.objects.all().delete()
    Plan.objects.all().delete()
    GrantDimension.objects.all().delete()

    resolved = resolve_entitlement(key)
    assert resolved.plan is None
    assert resolved.values == {}


def test_an_unreadable_grant_value_degrades_to_the_dimension_default():
    plan = Plan.objects.get(code="PRO")
    key = _license_key(tag="garbage")
    _assign(key, plan)
    grant = PlanGrant.objects.get(plan=plan, dimension=_dimension(NDI_KEY))
    grant.raw_value = "fivve"
    grant.save(update_fields=["raw_value", "updated_at"])

    resolved = resolve_entitlement(key)
    assert resolved.values[NDI_KEY] == 0, "a typo in one field should cost that field, nothing more"
    assert resolved.values[SCREEN_KEY] == 5


def test_a_deactivated_dimension_simply_disappears():
    plan = Plan.objects.get(code="PRO")
    key = _license_key(tag="deactivated")
    _assign(key, plan)
    dimension = _dimension(NDI_KEY)
    dimension.is_active = False
    dimension.save(update_fields=["is_active", "updated_at"])

    resolved = resolve_entitlement(key)
    assert NDI_KEY not in resolved.values
    assert resolved.values[SCREEN_KEY] == 5, "removing one grant must not disturb the others"


def test_a_dimension_named_like_a_restricted_field_is_refused_a_place_in_the_payload():
    """`assert_no_restricted_payload_fields` raises on such a key. If one reached the
    manifest payload, a single catalogue row would deny every device on the estate."""
    plan = Plan.objects.get(code="PRO")
    hostile = GrantDimension.objects.create(
        key="content",
        display_name="Hostile",
        value_type=GrantValueType.INTEGER,
        default_raw_value="1",
        sort_order=99,
    )
    PlanGrant.objects.create(plan=plan, dimension=hostile, raw_value="1")
    key = _license_key(tag="hostile")
    _assign(key, plan)

    resolved = resolve_entitlement(key)
    assert "content" not in resolved.values
    # Positive control: the benign dimensions still resolve, so "absent" is not just a
    # dead resolver.
    assert resolved.values[SCREEN_KEY] == 5


def test_unlimited_and_absent_are_different_states_with_different_encodings():
    """Collapsing them onto one value is how a payload ends up contradicting itself: a
    client cannot tell "granted without a ceiling" from "the catalogue says nothing"."""
    key = _license_key(tag="unlimited", feature_scope="NOT-MAPPED", device_limit=4)
    resolved = resolve_entitlement(key)

    # `unlimited` -> present, None. The bridge plan leaves outputs uncapped, exactly as
    # they were before the catalogue existed.
    assert SCREEN_KEY in resolved.values and resolved.values[SCREEN_KEY] is None
    assert NDI_KEY in resolved.values and resolved.values[NDI_KEY] is None
    # No grant and no dimension default -> the key is ABSENT, not null.
    assert SEAT_KEY not in resolved.values


def test_a_plan_may_still_declare_unlimited_seats_and_it_is_representable():
    """The seat dimension is an ordinary grant now, so `unlimited` means what it says
    rather than silently meaning "defer to device_limit"."""
    plan = Plan.objects.get(code="PRO")
    PlanGrant.objects.filter(plan=plan, dimension=_dimension(SEAT_KEY)).update(
        raw_value="unlimited"
    )
    GRANT_CACHE.clear()
    key = _license_key(tag="unlimitedseats")
    _assign(key, plan)
    values = resolve_entitlement(key).values
    assert SEAT_KEY in values and values[SEAT_KEY] is None


# --- Bounds (repo bounded-memory rule) -----------------------------------------------------


def test_a_cache_hit_returns_exactly_what_the_cold_read_returned():
    plan = Plan.objects.get(code="PRO")
    key = _license_key(tag="hit")
    _assign(key, plan)

    cold = dict(resolve_entitlement(key).values)
    revision = current_revision()
    assert GRANT_CACHE.hits_for(plan.pk, revision) == 0, "the cold read should have stored, not hit"
    warm = dict(resolve_entitlement(key).values)

    hits = GRANT_CACHE.hits_for(plan.pk, revision)
    assert hits == 1, (
        f"expected exactly one cache hit on plan {plan.pk}, got {hits!r} — the cache was "
        "not exercised, so the identity contract below was not exercised either"
    )
    assert warm == cold


def test_the_grant_cache_is_bounded_by_entry_count():
    # Premise pinned inside the test as well as beside the constant: a cap raised past the
    # number of plans built below would make the eviction assertion unreachable.
    assert MAX_CACHE_ENTRIES >= 2
    org = _org("bound")
    dimension = _dimension(SCREEN_KEY)

    licenses = []
    plans = []
    for index in range(MAX_CACHE_ENTRIES + 1):
        plan = Plan.objects.create(code=f"BOUND-{index}", display_name=f"Bound {index}")
        PlanGrant.objects.create(plan=plan, dimension=dimension, raw_value=str(index + 1))
        key = _license_key(tag=f"bound{index}", org=org)
        _assign(key, plan)
        plans.append(plan)
        licenses.append(key)

    # No writes from here on, so the revision — and therefore the cache — is stable.
    for key in licenses:
        resolve_entitlement(key)

    revision = current_revision()
    assert GRANT_CACHE.entry_count() == MAX_CACHE_ENTRIES, (
        "the cache grew past its cap; a per-plan cache with no bound grows with the "
        "catalogue and unbounds lookup cost"
    )
    # The entity, named: the least recently used key is gone, not merely "fewer bytes".
    assert GRANT_CACHE.contains(plans[0].pk, revision) is False
    assert GRANT_CACHE.contains(plans[-1].pk, revision) is True
    assert GRANT_CACHE.hits_for(plans[0].pk, revision) is None

    # Positive control: eviction costs a query, never a wrong answer.
    assert resolve_entitlement(licenses[0]).values[SCREEN_KEY] == 1


def test_one_cache_entry_cannot_hold_unboundedly_many_dimensions():
    """A byte budget would admit this; an entry cap on the count is what actually bites."""
    assert MAX_GRANT_DIMENSIONS >= 8
    existing = GrantDimension.objects.filter(is_active=True).count()
    assert existing < MAX_GRANT_DIMENSIONS, "the seeded dimensions already exceed the cap"

    plan = Plan.objects.get(code="PRO")
    created = []
    # Fill to exactly the cap, then add one more beyond it. Sort order decides which is
    # "beyond", so the last one created is the one that must be dropped.
    for index in range(MAX_GRANT_DIMENSIONS - existing + 1):
        dimension = GrantDimension.objects.create(
            key=f"filler_{index:03d}",
            display_name=f"Filler {index}",
            value_type=GrantValueType.INTEGER,
            default_raw_value="1",
            sort_order=1000 + index,
        )
        PlanGrant.objects.create(plan=plan, dimension=dimension, raw_value="1")
        created.append(dimension)

    key = _license_key(tag="dimcap")
    _assign(key, plan)
    values = resolve_entitlement(key).values

    assert len(values) == MAX_GRANT_DIMENSIONS
    assert created[-1].key not in values, "the dimension past the cap was emitted anyway"
    # Positive control: everything inside the cap is still emitted, so "dropped" is not
    # just a resolver that stopped working.
    assert created[0].key in values
    assert values[SCREEN_KEY] == 5


# --- The operator lever --------------------------------------------------------------------


def test_set_plan_grant_changes_the_value_and_audits_it():
    before = AuditEvent.objects.filter(action="catalogue.plan_grant_set").count()
    result = set_plan_grant(
        _staff(StaffPermission.GRANT_ENTITLEMENT),
        SetPlanGrantData(
            idempotency_key="catalogue-set-grant-1",
            plan_code="PRO",
            dimension_key=STT_KEY,
            raw_value="480",
            reason="AI subscription moved to eight hours.",
        ),
    )
    assert result.grant.raw_value == "480"
    assert result.previous_raw_value == "300"
    assert AuditEvent.objects.filter(action="catalogue.plan_grant_set").count() == before + 1

    key = _license_key(tag="lever")
    _assign(key, Plan.objects.get(code="PRO"))
    assert resolve_entitlement(key).values[STT_KEY] == 480


def test_set_plan_grant_replays_idempotently():
    data = SetPlanGrantData(
        idempotency_key="catalogue-set-grant-2",
        plan_code="PRO",
        dimension_key=NDI_KEY,
        raw_value="6",
        reason="Owner raised the NDI allowance.",
    )
    actor = _staff(StaffPermission.GRANT_ENTITLEMENT)
    first = set_plan_grant(actor, data)
    audited = AuditEvent.objects.filter(action="catalogue.plan_grant_set").count()
    second = set_plan_grant(actor, data)

    assert second.grant.pk == first.grant.pk
    assert second.created is False
    assert PlanGrant.objects.filter(plan__code="PRO", dimension__key=NDI_KEY).count() == 1
    assert AuditEvent.objects.filter(action="catalogue.plan_grant_set").count() == audited, (
        "a replay wrote a second audit event, so the operation is not idempotent"
    )


def test_set_plan_grant_requires_the_entitlement_permission():
    data = SetPlanGrantData(
        idempotency_key="catalogue-set-grant-3",
        plan_code="PRO",
        dimension_key=NDI_KEY,
        raw_value="6",
        reason="Attempted without the permission.",
    )
    with pytest.raises(SafeAPIError) as caught:
        set_plan_grant(_staff(StaffPermission.VIEW_CUSTOMERS), data)
    assert caught.value.code == ErrorCode.PERMISSION_DENIED

    with pytest.raises(SafeAPIError) as caught:
        set_plan_grant(None, data)
    assert caught.value.code == ErrorCode.UNAUTHENTICATED


def test_set_plan_grant_refuses_a_value_the_dimension_cannot_express():
    """Storing it would be worse than refusing: the value would silently vanish from every
    manifest at resolution time, and look like a catalogue that ignores its own rows."""
    with pytest.raises(SafeAPIError) as caught:
        set_plan_grant(
            _staff(StaffPermission.GRANT_ENTITLEMENT),
            SetPlanGrantData(
                idempotency_key="catalogue-set-grant-4",
                plan_code="PRO",
                dimension_key=NDI_KEY,
                raw_value="quite a lot",
                reason="Typo that must not be stored.",
            ),
        )
    assert caught.value.code == ErrorCode.VALIDATION_FAILED
    assert PlanGrant.objects.get(plan__code="PRO", dimension__key=NDI_KEY).raw_value == "5"


def test_set_plan_grant_reports_an_unknown_plan_as_not_found():
    with pytest.raises(SafeAPIError) as caught:
        set_plan_grant(
            _staff(StaffPermission.GRANT_ENTITLEMENT),
            SetPlanGrantData(
                idempotency_key="catalogue-set-grant-5",
                plan_code="NO-SUCH-PLAN",
                dimension_key=NDI_KEY,
                raw_value="6",
                reason="Plan that does not exist.",
            ),
        )
    assert caught.value.code == ErrorCode.NOT_FOUND


# --- Cache invalidation is scoped to what the cache actually holds --------------------------


def test_assigning_an_unrelated_licence_does_not_cold_the_grant_cache():
    """The cache holds one resolved map per PLAN. Assignments, aliases and per-licence
    overrides are read fresh every time and never cached, so bumping the revision for them
    would discard every plan's map for a write that cannot have changed one. Under a
    billing run that assigns many licences, the cache would then never be warm."""
    plan = Plan.objects.get(code="PRO")
    warmer = _license_key(tag="warm")
    _assign(warmer, plan)
    resolve_entitlement(warmer)
    resolve_entitlement(warmer)

    revision = current_revision()
    assert GRANT_CACHE.hits_for(plan.pk, revision) == 1, (
        "the cache was not warm to begin with, so this test could not detect it being "
        "discarded"
    )

    # A write to a model the cache does not hold.
    other = _license_key(tag="other")
    _assign(other, plan)
    LicenseGrantOverride.objects.create(
        license_key=other,
        dimension=_dimension(NDI_KEY),
        raw_value="1",
        granted_by_actor_id="staff_ops_1",
        reason="Unrelated write.",
    )
    PlanScopeAlias.objects.create(feature_scope="UNRELATED", plan=plan)

    assert current_revision() == revision, "an uncached model bumped the cache revision"
    assert GRANT_CACHE.hits_for(plan.pk, revision) == 1, (
        "assigning an unrelated licence discarded the plan's cached grant map"
    )
    # Positive control: a write the cache DOES depend on must still invalidate it.
    grant = PlanGrant.objects.get(plan=plan, dimension=_dimension(NDI_KEY))
    grant.raw_value = "6"
    grant.save(update_fields=["raw_value", "updated_at"])
    assert current_revision() != revision
    assert GRANT_CACHE.hits_for(plan.pk, current_revision()) is None


def test_a_superseded_entry_is_not_reported_as_resident():
    """`contains` shares one validity predicate with `get`. Without that, a residency
    assertion made after a catalogue edit would pass on an entry nothing would serve."""
    plan = Plan.objects.get(code="PRO")
    key = _license_key(tag="superseded")
    _assign(key, plan)
    resolve_entitlement(key)
    stale_revision = current_revision()
    assert GRANT_CACHE.contains(plan.pk, stale_revision) is True

    grant = PlanGrant.objects.get(plan=plan, dimension=_dimension(SCREEN_KEY))
    grant.raw_value = "8"
    grant.save(update_fields=["raw_value", "updated_at"])

    assert current_revision() != stale_revision
    assert GRANT_CACHE.contains(plan.pk, current_revision()) is False
    assert GRANT_CACHE.hits_for(plan.pk, current_revision()) is None


def test_an_expired_entry_is_not_reported_as_resident(monkeypatch):
    ticks = [1000.0]
    cache = BoundedGrantCache(clock=lambda: ticks[0])
    monkeypatch.setattr(catalogue_services, "GRANT_CACHE", cache)

    plan = Plan.objects.get(code="PRO")
    key = _license_key(tag="expiredentry")
    _assign(key, plan)
    resolve_entitlement(key)
    revision = current_revision()
    assert cache.contains(plan.pk, revision) is True

    ticks[0] += CACHE_TTL_SECONDS + 1
    assert cache.contains(plan.pk, revision) is False


# --- Per-licence overrides are governed ------------------------------------------------------


def test_an_override_is_time_boxed_by_default():
    """A forgotten override is an entitlement nobody is charging for."""
    key = _license_key(tag="ovdefault")
    _assign(key, Plan.objects.get(code="FREE"))
    result = set_license_grant_override(
        _staff(StaffPermission.GRANT_ENTITLEMENT),
        SetLicenseGrantOverrideData(
            idempotency_key="catalogue-override-1",
            license_key_id=str(key.id),
            dimension_key=NDI_KEY,
            raw_value="3",
            reason="Conference loan for the summer.",
        ),
    )
    assert result.override.expires_at is not None
    window = result.override.expires_at - timezone.now()
    assert timedelta(days=DEFAULT_OVERRIDE_DAYS - 1) < window <= timedelta(
        days=DEFAULT_OVERRIDE_DAYS
    )
    assert resolve_entitlement(key).values[NDI_KEY] == 3


def test_an_expired_override_stops_applying():
    key = _license_key(tag="ovexpired")
    _assign(key, Plan.objects.get(code="FREE"))
    _override(key, NDI_KEY, "3", expires_at=timezone.now() - timedelta(seconds=1))
    # Falls back to the plan's value, not to the override's.
    assert resolve_entitlement(key).values[NDI_KEY] == 0
    # Positive control: the same row, unexpired, does apply — so "ignored" is not just a
    # resolver that never reads overrides at all.
    LicenseGrantOverride.objects.filter(license_key=key).update(
        expires_at=timezone.now() + timedelta(days=1)
    )
    assert resolve_entitlement(key).values[NDI_KEY] == 3


def test_a_permanent_override_is_possible_but_must_be_asked_for():
    key = _license_key(tag="ovpermanent")
    _assign(key, Plan.objects.get(code="FREE"))
    result = set_license_grant_override(
        _staff(StaffPermission.GRANT_ENTITLEMENT),
        SetLicenseGrantOverrideData(
            idempotency_key="catalogue-override-2",
            license_key_id=str(key.id),
            dimension_key=NDI_KEY,
            raw_value="3",
            reason="Permanent contractual exception.",
            permanent=True,
        ),
    )
    assert result.override.expires_at is None


def test_an_override_records_who_granted_it_why_and_is_audited():
    key = _license_key(tag="ovaudit")
    before = AuditEvent.objects.filter(action="catalogue.license_grant_override_set").count()
    result = set_license_grant_override(
        _staff(StaffPermission.GRANT_ENTITLEMENT),
        SetLicenseGrantOverrideData(
            idempotency_key="catalogue-override-3",
            license_key_id=str(key.id),
            dimension_key=NDI_KEY,
            raw_value="3",
            reason="Pilot extension agreed with the owner.",
        ),
    )
    assert result.override.granted_by_actor_id == "staff_ops_1"
    assert result.override.reason == "Pilot extension agreed with the owner."
    assert (
        AuditEvent.objects.filter(action="catalogue.license_grant_override_set").count()
        == before + 1
    )


def test_an_override_requires_the_entitlement_permission_and_a_reason():
    key = _license_key(tag="ovperm")
    data = SetLicenseGrantOverrideData(
        idempotency_key="catalogue-override-4",
        license_key_id=str(key.id),
        dimension_key=NDI_KEY,
        raw_value="3",
        reason="Long enough reason.",
    )
    with pytest.raises(SafeAPIError) as caught:
        set_license_grant_override(_staff(StaffPermission.VIEW_CUSTOMERS), data)
    assert caught.value.code == ErrorCode.PERMISSION_DENIED

    with pytest.raises(SafeAPIError) as caught:
        set_license_grant_override(
            _staff(StaffPermission.GRANT_ENTITLEMENT),
            SetLicenseGrantOverrideData(
                idempotency_key="catalogue-override-5",
                license_key_id=str(key.id),
                dimension_key=NDI_KEY,
                raw_value="3",
                reason="short",
            ),
        )
    assert caught.value.code == ErrorCode.VALIDATION_FAILED
    assert LicenseGrantOverride.objects.count() == 0


# --- Dimension keys are allow-listed before they can reach a signed payload ------------------


@pytest.mark.parametrize(
    "bad_key",
    ["Screen_Outputs", "screen outputs", "9lives", "with-dash", "UPPER", "", "x" * 65],
)
def test_the_database_refuses_a_malformed_dimension_key(bad_key):
    """A key that ships in a signed manifest is permanent, and the field is operator-settable
    free text. The constraint binds every writer, including a shell that skips the service."""
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            GrantDimension.objects.create(
                key=bad_key,
                display_name="Bad",
                value_type=GrantValueType.INTEGER,
                default_raw_value="1",
            )


@pytest.mark.parametrize("reserved", ["selahcue_meta", "sc_internal"])
def test_the_database_refuses_a_reserved_dimension_key(reserved):
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            GrantDimension.objects.create(
                key=reserved,
                display_name="Reserved",
                value_type=GrantValueType.INTEGER,
                default_raw_value="1",
            )


def test_a_well_formed_dimension_key_is_still_accepted():
    """Positive control: the constraint refuses bad keys, it does not refuse everything."""
    dimension = GrantDimension.objects.create(
        key="alt_output_count",
        display_name="Alt",
        value_type=GrantValueType.INTEGER,
        default_raw_value="1",
        sort_order=97,
    )
    assert GrantDimension.objects.filter(pk=dimension.pk).exists()


@pytest.mark.parametrize("bad_key", ["Screen_Outputs", "sc_internal", "with-dash", ""])
def test_the_override_service_refuses_a_malformed_dimension_key(bad_key):
    key = _license_key(tag="keyval")
    with pytest.raises(SafeAPIError) as caught:
        set_license_grant_override(
            _staff(StaffPermission.GRANT_ENTITLEMENT),
            SetLicenseGrantOverrideData(
                idempotency_key="catalogue-override-6",
                license_key_id=str(key.id),
                dimension_key=bad_key,
                raw_value="3",
                reason="Attempt with a malformed key.",
            ),
        )
    assert caught.value.code == ErrorCode.VALIDATION_FAILED
