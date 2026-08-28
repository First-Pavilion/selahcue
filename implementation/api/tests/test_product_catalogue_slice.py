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
import logging
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType

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
    SetLicensePlanAssignmentData,
    SetPlanGrantData,
    current_revision,
    resolve_entitlement,
    set_license_grant_override,
    set_license_plan_assignment,
    set_plan_grant,
)
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus, LicenseKeyType
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = pytest.mark.django_db

# The DATABASE requires an actor and a reason on `Plan` and `PlanGrant` rows (migration
# 0004), exactly as it already did on assignments and overrides — a bare `objects.create()`
# is refused. Supplied here so these tests exercise the rows, not the constraint.
ACCOUNTABLE = {
    "changed_by_actor_id": "staff_ops_1",
    "reason": "Catalogue tests: fixture row.",
}


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
    """Accountability columns supplied because the DATABASE requires them; the governed
    path is `set_license_plan_assignment`, tested separately."""
    return LicensePlanAssignment.objects.create(
        license_key=license_key,
        plan=plan,
        assigned_by_actor_id="staff_ops_1",
        reason="Catalogue slice tests.",
    )


def _override(license_key, dimension_key, raw_value, *, expires_at=None):
    """A row written directly. The governed path is `set_license_grant_override`, tested
    separately; resolution must behave the same however the row got there."""
    return LicenseGrantOverride.objects.create(
        license_key=license_key,
        dimension=_dimension(dimension_key),
        raw_value=raw_value,
        granted_by_actor_id="staff_ops_1",
        reason="Test override for this case.",
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


# Modules that certainly contain branching logic. Naming them is the real breadth control:
# a count can be cleared by empty files, but a named module either got scanned or did not.
MUST_SCAN = frozenset(
    {
        "apps/catalogue/services.py",
        "apps/catalogue/models.py",
        "apps/catalogue/cache.py",
        "apps/entitlements/services.py",
        "apps/devices/services.py",
        "apps/license_keys/services.py",
        "graphql/admin_schema.py",
        "platform/views.py",
    }
)


def _is_substantive(path: Path) -> bool:
    """Whether a module could actually host a tier-name branch.

    `__init__.py`, migrations and `apps.py` are mostly empty or declarative, and there are
    43 of them against 82 modules total — so a sweep that skipped every file able to contain
    a branch would still clear a bare `scanned > 20`. Counting only modules with real
    top-level definitions is what makes the count mean something.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:  # pragma: no cover - a broken module is a different failure
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.If))
        for node in tree.body
    )


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
    scanned = set()
    for path in sorted(API_ROOT.rglob("*.py")):
        if path == SEED_MIGRATION:
            continue
        scanned.add(path)
        for literal in plan_names & _string_constants(path):
            offenders.append(f"{path.relative_to(API_ROOT)}: {literal!r}")

    # Second control, on the ITERATION rather than the scanner: a sweep that reaches almost
    # nothing reports "no offenders" for the wrong reason.
    #
    # Counted in modules that could actually hold a branch, not in files. Of 82 modules here,
    # 43 are structurally empty — `__init__.py`, migrations, `apps.py` — so a skip that
    # excluded every file capable of containing `plan.code == "PRO"` would still clear a
    # plain file count. And named modules on top, because a count of any kind can be gamed
    # by what it happens to include.
    relative = {path.relative_to(API_ROOT).as_posix() for path in scanned}
    missing = MUST_SCAN - relative
    assert not missing, f"the sweep never visited these modules, so it proves nothing: {missing}"

    substantive = sum(1 for path in scanned if _is_substantive(path))
    assert substantive > 20, (
        f"the sweep visited only {substantive} modules capable of holding a branch "
        f"(of {len(scanned)} files), so it proves nothing"
    )

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
    plan = Plan.objects.create(
        code="RUBY", display_name="Ruby", sort_order=40, **ACCOUNTABLE
    )
    novel = {SEAT_KEY: "11", SCREEN_KEY: "13", NDI_KEY: "17", STT_KEY: "1999", WATERMARK_KEY: "false"}
    for dimension_key, raw_value in novel.items():
        PlanGrant.objects.create(
            plan=plan,
            dimension=_dimension(dimension_key),
            raw_value=raw_value,
            **ACCOUNTABLE,
        )

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
            Plan.objects.create(
                code="SECOND-FALLBACK",
                display_name="Second",
                is_fallback=True,
                **ACCOUNTABLE,
            )


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


def test_an_unseeded_catalogue_says_so_in_the_log(caplog):
    """Finding 5's actual gap: an unconfigured catalogue was completely SILENT.

    The WIRE is deliberately unchanged, and no `degraded` field is added — see
    `resolve_entitlement`'s docstring. Absence of a grant already means exactly one thing
    ("the catalogue expresses nothing about this dimension; apply your own default"), which
    is precisely true of a database where the catalogue was never seeded; encoding it
    otherwise would invent a fourth grant state the payload has no room for. The degraded
    case is already distinguishable on the wire without a new field, because a degraded
    manifest is TTL-clamped and an unconfigured one keeps the licence's own expiry — pinned
    by `test_an_unconfigured_catalogue_is_not_treated_as_a_failure` in the manifest slice.

    What was genuinely missing is on the SERVER. If migration 0002 never ran in an
    environment, every manifest would issue with zero grants and nothing anywhere would say
    so. This is the line an operator can alert on.
    """
    key = _license_key(tag="unseededlog")
    PlanScopeAlias.objects.all().delete()
    LicensePlanAssignment.objects.all().delete()
    PlanGrant.objects.all().delete()
    Plan.objects.all().delete()
    GrantDimension.objects.all().delete()

    with caplog.at_level(logging.WARNING, logger=catalogue_services.logger.name):
        resolved = resolve_entitlement(key)

    # Steady state, NOT a failure: this must not start clamping every manifest in an
    # environment whose catalogue is simply not seeded yet.
    assert resolved.plan is None and resolved.degraded is False

    reports = [r for r in caplog.records if "resolved no plan" in r.getMessage()]
    assert reports, (
        "an unseeded catalogue issued an entitlement with NO grants and logged nothing, so "
        "a missing catalogue migration in an environment stays invisible — which is the "
        "whole of what Finding 5 left open"
    )
    assert reports[0].levelno == logging.WARNING
    assert str(key.id) in reports[0].getMessage(), (
        "the warning does not name the licence, so an operator cannot tell which issuance "
        f"it refers to: {reports[0].getMessage()!r}"
    )


def test_a_healthy_resolution_does_not_warn_positive_control(caplog):
    """Positive control for the warning above.

    A warning that fires on every resolution is not a signal, it is noise, and is strictly
    worse than the silence it replaced — an operator who alerts on it would be paged for
    every healthy manifest. It must fire ONLY when nothing resolved.
    """
    key = _license_key(tag="healthylog")
    _assign(key, Plan.objects.get(code="PRO"))

    with caplog.at_level(logging.WARNING, logger=catalogue_services.logger.name):
        resolved = resolve_entitlement(key)

    assert resolved.plan is not None, (
        "the premise failed - nothing resolved, so 'it did not warn' proves nothing"
    )
    assert resolved.values[SCREEN_KEY] == 5
    assert not [r for r in caplog.records if "resolved no plan" in r.getMessage()], (
        "a perfectly healthy resolution logged the unseeded-catalogue warning, which makes "
        "the warning useless for alerting"
    )


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


# --- The cap assert, and where it sits (NFR-024) --------------------------------------------
#
# `assert len(values) <= MAX_GRANT_DIMENSIONS` is the ONE statement on the issuance path that
# can raise, in a module contracted never to raise. Where it sits decides what a violated
# invariant COSTS:
#
#   outside the try   AssertionError escapes `resolve_entitlement` and the licence is DENIED
#                     its manifest — the exact failure the degrade-never-raise design exists
#                     to prevent, and silently gone under `python -O`.
#   inside the try    the violation takes the degraded path: a short-lived manifest, logged
#                     and audited, and the device keeps running.
#
# The invariant cannot be violated through the database — the override queryset is restricted
# to `grants.known` in SQL, so the merged map cannot exceed the cap. That is precisely why NO
# ordinary test distinguishes the two placements, and why these two inject the violation
# directly at `_plan_grant_map`, the seam the shipped degraded-read tests already use.


def _cap_violating_grants(count):
    """A plan map holding `count` keys, bypassing the SQL that makes that impossible."""
    values = {f"synthetic_dimension_{index}": index for index in range(count)}
    assert len(values) == count, "the synthetic keys collided; this map is not the size it says"
    return catalogue_services.CachedGrants(
        values=MappingProxyType(values),
        published=frozenset(),
        known=frozenset(values),
    )


def test_a_violated_grant_cap_degrades_instead_of_raising(monkeypatch, caplog):
    """A broken invariant must cost a short manifest, never the manifest itself."""
    key = _license_key(tag="capviolation")
    _assign(key, Plan.objects.get(code="PRO"))
    monkeypatch.setattr(
        catalogue_services,
        "_plan_grant_map",
        lambda *args, **kwargs: _cap_violating_grants(MAX_GRANT_DIMENSIONS + 1),
    )

    with caplog.at_level(logging.ERROR, logger=catalogue_services.logger.name):
        # Outside the try, this line RAISES and the test dies here rather than failing.
        resolved = resolve_entitlement(key)

    # The MECHANISM, asserted before the contract. The injected map is hand-built, so
    # "degraded" has to be shown to come from the cap assert firing and being CAUGHT —
    # otherwise a fake that upset resolution some other way would satisfy the contract
    # below while the assert went untouched.
    caught = [
        record
        for record in caplog.records
        if record.exc_info and record.exc_info[0] is AssertionError
    ]
    assert caught, (
        "no AssertionError was caught inside `resolve_entitlement`, so the grant-cap assert "
        "never fired and this test exercises nothing about where it sits"
    )
    assert f"against a cap of {MAX_GRANT_DIMENSIONS}" in str(caught[0].exc_info[1]), (
        "an AssertionError was caught, but not the grant-cap one this test is named for: "
        f"{caught[0].exc_info[1]!r}"
    )

    # The contract.
    assert resolved.degraded is True, (
        "a violated grant cap did not produce a DEGRADED entitlement, so the manifest minted "
        "from it would carry the full licence window"
    )
    assert resolved.values == {}
    assert resolved.plan is None


def test_a_grant_map_exactly_AT_the_cap_still_resolves_positive_control(monkeypatch):
    """Positive control for the injection above, one key smaller.

    Without it, `test_a_violated_grant_cap_degrades_instead_of_raising` proves only that
    `_cap_violating_grants` degrades resolution — which a map that was malformed in some
    unrelated way would do just as well. Exactly AT the cap the same construction resolves
    cleanly, so the one thing that differs between the two is the bound.
    """
    key = _license_key(tag="capexact")
    _assign(key, Plan.objects.get(code="PRO"))
    monkeypatch.setattr(
        catalogue_services,
        "_plan_grant_map",
        lambda *args, **kwargs: _cap_violating_grants(MAX_GRANT_DIMENSIONS),
    )

    resolved = resolve_entitlement(key)

    assert resolved.degraded is False, (
        "the hand-built grant map degrades resolution even INSIDE the cap, so the test above "
        "is not measuring the cap at all"
    )
    assert len(resolved.values) == MAX_GRANT_DIMENSIONS
    assert resolved.plan is not None and resolved.plan.code == "PRO"


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
    PlanGrant.objects.create(plan=plan, dimension=hostile, raw_value="1", **ACCOUNTABLE)
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


def test_a_plan_may_declare_unlimited_seats_without_it_reaching_the_wire():
    """`unlimited` means what it says SERVER-SIDE rather than silently meaning "defer to
    device_limit" — and it still never reaches the signed payload.

    This is the exact operator action that reproduced the original defect: `set_plan_grant
    --plan PRO --dimension device_instances --value unlimited` used to emit
    `grants.device_instances = null` (unlimited) beside `instances_limit = 3`. The value is
    now resolved for FR-516 and the portal, and published to nobody."""
    plan = Plan.objects.get(code="PRO")
    PlanGrant.objects.filter(plan=plan, dimension=_dimension(SEAT_KEY)).update(
        raw_value="unlimited"
    )
    GRANT_CACHE.clear()
    key = _license_key(tag="unlimitedseats")
    _assign(key, plan)
    resolved = resolve_entitlement(key)
    assert SEAT_KEY in resolved.values and resolved.values[SEAT_KEY] is None
    assert SEAT_KEY not in resolved.published_values, (
        "the operator lever put an unlimited seat count on the wire beside the enforced "
        "instances_limit — the original defect, reproduced through a pure data edit"
    )


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
        plan = Plan.objects.create(
            code=f"BOUND-{index}", display_name=f"Bound {index}", **ACCOUNTABLE
        )
        PlanGrant.objects.create(
            plan=plan, dimension=dimension, raw_value=str(index + 1), **ACCOUNTABLE
        )
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
        PlanGrant.objects.create(plan=plan, dimension=dimension, raw_value="1", **ACCOUNTABLE)
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
    free text. The constraint binds every writer, including a shell that skips the service.

    Both engines refuse every key here, but not always by the same mechanism, so the
    assertion is on the refusal rather than on one exception class. `GRANT_KEY_PATTERN`
    bounds length itself (`{0,63}` after the leading letter), so the over-long key violates
    the CHECK constraint — which is what fires on SQLite, as `IntegrityError`. Postgres
    never reaches the check: `key` is `varchar(64)`, and the column width is enforced first,
    raising `DataError` (`StringDataRightTruncation`) at the INSERT. Asserting only
    `IntegrityError` therefore passed on the bundled SQLite and failed on the Postgres that
    CI and production run.
    """
    from django.db import DataError, IntegrityError, transaction

    with pytest.raises((IntegrityError, DataError)):
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


# --- Cross-tenant isolation (the shared cache entry) ------------------------------------


def test_one_licences_override_never_leaks_to_another_on_the_same_plan():
    """The cache entry for a plan is PROCESS-GLOBAL and shared by every tenant on it.
    Applying one licence's overrides into that entry, instead of into a copy, hands licence
    A's exception to every other org on the plan — a cross-tenant entitlement leak."""
    plan = Plan.objects.get(code="PRO")
    org = _org("tenants")
    tenant_a = _license_key(tag="tenanta", org=org)
    tenant_b = _license_key(tag="tenantb", org=org)
    _assign(tenant_a, plan)
    _assign(tenant_b, plan)
    _override(tenant_a, NDI_KEY, "99")

    assert resolve_entitlement(tenant_a).values[NDI_KEY] == 99, (
        "tenant A's override did not apply, so this test cannot detect it leaking"
    )
    assert resolve_entitlement(tenant_b).values[NDI_KEY] == 5, (
        "tenant B inherited tenant A's per-licence override from the shared plan cache"
    )
    # Order-independent: resolving B first must not change the answer for A either.
    GRANT_CACHE.clear()
    assert resolve_entitlement(tenant_b).values[NDI_KEY] == 5
    assert resolve_entitlement(tenant_a).values[NDI_KEY] == 99


def test_the_shared_cache_entry_is_read_only():
    """Structural, not disciplinary: a caller who forgets to copy gets a TypeError rather
    than silently corrupting every other tenant's entitlement."""
    from selahcue_api.apps.catalogue.services import _plan_grant_map

    plan = Plan.objects.get(code="PRO")
    grants = _plan_grant_map(plan, current_revision())
    with pytest.raises(TypeError):
        grants.values[NDI_KEY] = 99


# --- Accountability is enforced by the database, not only by the service ------------------


def test_a_bare_override_create_is_refused_without_an_actor_and_reason():
    """The permission check, required reason and audit are worthless if the one path anybody
    in a hurry takes — a shell `objects.create()` — walks straight past them."""
    from django.db import IntegrityError, transaction

    key = _license_key(tag="bareov")
    for kwargs in (
        {"granted_by_actor_id": "", "reason": "Long enough reason."},
        {"granted_by_actor_id": "staff_ops_1", "reason": ""},
        {"granted_by_actor_id": "staff_ops_1", "reason": "short"},
    ):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                LicenseGrantOverride.objects.create(
                    license_key=key, dimension=_dimension(NDI_KEY), raw_value="3", **kwargs
                )
    assert LicenseGrantOverride.objects.count() == 0


def test_a_bare_plan_assignment_create_is_refused_without_an_actor_and_reason():
    """Moving a church between tiers must never be possible without a trace of who and why."""
    from django.db import IntegrityError, transaction

    key = _license_key(tag="bareassign")
    plan = Plan.objects.get(code="PLATINUM")
    for kwargs in (
        {"assigned_by_actor_id": "", "reason": "Long enough reason."},
        {"assigned_by_actor_id": "staff_ops_1", "reason": "short"},
    ):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                LicensePlanAssignment.objects.create(license_key=key, plan=plan, **kwargs)
    assert LicensePlanAssignment.objects.filter(license_key=key).count() == 0


def test_a_properly_attributed_write_is_still_accepted():
    """Positive control: the constraints refuse anonymous writes, not all writes."""
    key = _license_key(tag="attributed")
    assignment = LicensePlanAssignment.objects.create(
        license_key=key,
        plan=Plan.objects.get(code="PRO"),
        assigned_by_actor_id="staff_ops_1",
        reason="Upgraded after the pilot concluded.",
    )
    assert LicensePlanAssignment.objects.filter(pk=assignment.pk).exists()


def test_a_bare_plan_grant_create_is_refused_without_an_actor_and_reason():
    """One row here changes the allowance for EVERY tenant on the plan.

    The override above is a single customer's exception and already carried this. A plan
    grant is the wholesale version of the same act, so it cannot be the one that a shell can
    write anonymously.
    """
    from django.db import IntegrityError, transaction

    plan = Plan.objects.get(code="PLATINUM")
    dimension = _dimension(NDI_KEY)
    PlanGrant.objects.filter(plan=plan, dimension=dimension).delete()
    for kwargs in (
        {"changed_by_actor_id": "", "reason": "Long enough reason."},
        {"changed_by_actor_id": "staff_ops_1", "reason": ""},
        {"changed_by_actor_id": "staff_ops_1", "reason": "short"},
    ):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PlanGrant.objects.create(
                    plan=plan, dimension=dimension, raw_value="99", **kwargs
                )
    # The ENTITY: no row for this (plan, dimension) exists, not merely "some count".
    assert not PlanGrant.objects.filter(plan=plan, dimension=dimension).exists()


def test_a_bare_plan_create_is_refused_without_an_actor_and_reason():
    """`is_fallback` decides what every unassigned licence in the system grants."""
    from django.db import IntegrityError, transaction

    for kwargs in (
        {"changed_by_actor_id": "", "reason": "Long enough reason."},
        {"changed_by_actor_id": "staff_ops_1", "reason": ""},
        {"changed_by_actor_id": "staff_ops_1", "reason": "short"},
    ):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Plan.objects.create(code="ANONYMOUS", display_name="Anonymous", **kwargs)
    assert not Plan.objects.filter(code="ANONYMOUS").exists()


def test_an_attributed_plan_and_plan_grant_write_is_still_accepted():
    """Positive control for BOTH new constraints.

    Without it, "refused" is indistinguishable from a table that rejects every write — and
    the two tests above would pass just as well against a broken model.
    """
    plan = Plan.objects.create(
        code="ATTRIBUTED",
        display_name="Attributed",
        changed_by_actor_id="staff_ops_1",
        reason="Created for the accountability positive control.",
    )
    grant = PlanGrant.objects.create(
        plan=plan,
        dimension=_dimension(NDI_KEY),
        raw_value="4",
        changed_by_actor_id="staff_ops_1",
        reason="Created for the accountability positive control.",
    )
    assert Plan.objects.filter(pk=plan.pk).exists()
    assert PlanGrant.objects.filter(pk=grant.pk).exists()
    # And the row is actually usable, not merely insertable.
    key = _license_key(tag="attrgrant")
    _assign(key, plan)
    assert resolve_entitlement(key).values[NDI_KEY] == 4


def test_the_governed_plan_grant_path_records_who_changed_it():
    """`set_plan_grant` must SUPPLY what the constraint demands, not be blocked by it."""
    actor = _staff(StaffPermission.GRANT_ENTITLEMENT)
    result = set_plan_grant(
        actor,
        SetPlanGrantData(
            idempotency_key="plangrant-accountability-0001",
            plan_code="PRO",
            dimension_key=NDI_KEY,
            raw_value="6",
            reason="Pro NDI allowance raised for the season.",
        ),
    )
    result.grant.refresh_from_db()
    assert result.grant.changed_by_actor_id == actor.actor_id
    assert "Pro NDI allowance raised" in result.grant.reason


# --- The governed assignment path ----------------------------------------------------------


def test_set_license_plan_assignment_moves_the_plan_and_audits_it():
    key = _license_key(tag="govassign")
    before = AuditEvent.objects.filter(action="catalogue.license_plan_assigned").count()
    result = set_license_plan_assignment(
        _staff(StaffPermission.GRANT_ENTITLEMENT),
        SetLicensePlanAssignmentData(
            idempotency_key="catalogue-assign-1",
            license_key_id=str(key.id),
            plan_code="PLATINUM",
            reason="Upgraded after the pilot concluded.",
        ),
    )
    assert result.assignment.plan.code == "PLATINUM"
    assert result.assignment.assigned_by_actor_id == "staff_ops_1"
    assert AuditEvent.objects.filter(action="catalogue.license_plan_assigned").count() == before + 1
    assert resolve_entitlement(key).values[SCREEN_KEY] == 10


def test_set_license_plan_assignment_requires_the_entitlement_permission():
    key = _license_key(tag="govassignperm")
    data = SetLicensePlanAssignmentData(
        idempotency_key="catalogue-assign-2",
        license_key_id=str(key.id),
        plan_code="PLATINUM",
        reason="Attempted without the permission.",
    )
    with pytest.raises(SafeAPIError) as caught:
        set_license_plan_assignment(_staff(StaffPermission.VIEW_CUSTOMERS), data)
    assert caught.value.code == ErrorCode.PERMISSION_DENIED
    assert LicensePlanAssignment.objects.filter(license_key=key).count() == 0


def test_set_license_plan_assignment_replays_idempotently():
    key = _license_key(tag="govassignreplay")
    data = SetLicensePlanAssignmentData(
        idempotency_key="catalogue-assign-3",
        license_key_id=str(key.id),
        plan_code="PLATINUM",
        reason="Upgraded after the pilot concluded.",
    )
    actor = _staff(StaffPermission.GRANT_ENTITLEMENT)
    set_license_plan_assignment(actor, data)
    audited = AuditEvent.objects.filter(action="catalogue.license_plan_assigned").count()
    second = set_license_plan_assignment(actor, data)

    assert second.created is False
    assert AuditEvent.objects.filter(action="catalogue.license_plan_assigned").count() == audited


# --- Replaying an override must not extend its time-box ------------------------------------


def test_replaying_an_override_neither_extends_the_window_nor_re_audits():
    """The 90-day box is the point of the ceremony. A retried request that silently pushes
    it out another 90 days undoes it, quietly, every time the caller retries."""
    key = _license_key(tag="ovreplay")
    _assign(key, Plan.objects.get(code="FREE"))
    data = SetLicenseGrantOverrideData(
        idempotency_key="catalogue-override-replay",
        license_key_id=str(key.id),
        dimension_key=NDI_KEY,
        raw_value="3",
        reason="Conference loan for the summer.",
    )
    actor = _staff(StaffPermission.GRANT_ENTITLEMENT)
    first = set_license_grant_override(actor, data)
    original_expiry = first.override.expires_at
    audited = AuditEvent.objects.filter(action="catalogue.license_grant_override_set").count()

    second = set_license_grant_override(actor, data)

    assert second.created is False
    second.override.refresh_from_db()
    assert second.override.expires_at == original_expiry, (
        "a replay pushed the expiry out, so retrying silently un-time-boxes the override"
    )
    assert (
        AuditEvent.objects.filter(action="catalogue.license_grant_override_set").count() == audited
    ), "a replay wrote a second audit event"


def test_a_genuinely_new_request_does_re_box_the_override():
    """Positive control: a DIFFERENT idempotency key is a new decision and does move the
    window — otherwise the replay guard above would be indistinguishable from a dead write."""
    key = _license_key(tag="ovrebox")
    _assign(key, Plan.objects.get(code="FREE"))
    actor = _staff(StaffPermission.GRANT_ENTITLEMENT)
    first = set_license_grant_override(
        actor,
        SetLicenseGrantOverrideData(
            idempotency_key="catalogue-override-rebox-1",
            license_key_id=str(key.id),
            dimension_key=NDI_KEY,
            raw_value="3",
            reason="Conference loan for the summer.",
        ),
    )
    LicenseGrantOverride.objects.filter(pk=first.override.pk).update(
        expires_at=timezone.now() + timedelta(days=1)
    )
    second = set_license_grant_override(
        actor,
        SetLicenseGrantOverrideData(
            idempotency_key="catalogue-override-rebox-2",
            license_key_id=str(key.id),
            dimension_key=NDI_KEY,
            raw_value="4",
            reason="Loan extended to the winter conference.",
        ),
    )
    assert second.override.raw_value == "4"
    assert second.override.expires_at > timezone.now() + timedelta(days=2)


# --- Scope aliases must be reachable ---------------------------------------------------------


@pytest.mark.parametrize("bad_scope", ["church", "Church", ""])
def test_an_unreachable_scope_alias_is_refused(bad_scope):
    """Resolution upper-cases before lookup, so a lower-case row is never consulted — and
    `unique=True` on the raw value lets it sit silently beside the live one."""
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PlanScopeAlias.objects.create(
                feature_scope=bad_scope, plan=Plan.objects.get(code="PRO")
            )


def test_an_upper_case_scope_alias_is_accepted_and_consulted():
    """Positive control for the constraint above."""
    PlanScopeAlias.objects.create(feature_scope="CHURCH", plan=Plan.objects.get(code="PRO"))
    key = _license_key(tag="aliasok", feature_scope="church")
    assert resolve_entitlement(key).values[SCREEN_KEY] == 5


# --- Value coercion edges ---------------------------------------------------------------------


def test_a_negative_integer_is_refused_rather_than_carried_into_a_manifest():
    """A negative cap is meaningless and a client cannot act on it sensibly; degrade to the
    dimension's default instead of signing it."""
    plan = Plan.objects.get(code="PRO")
    key = _license_key(tag="negative")
    _assign(key, plan)
    grant = PlanGrant.objects.get(plan=plan, dimension=_dimension(NDI_KEY))
    grant.raw_value = "-5"
    grant.save(update_fields=["raw_value", "updated_at"])

    assert resolve_entitlement(key).values[NDI_KEY] == 0
    # Positive control: a non-negative value in the same field is still honoured.
    grant.raw_value = "6"
    grant.save(update_fields=["raw_value", "updated_at"])
    assert resolve_entitlement(key).values[NDI_KEY] == 6


def test_which_overrides_survive_is_decided_by_the_data_not_the_row_order():
    """A licence can carry more override rows than the dimension cap admits.

    If the query selected broadly and discarded afterwards, the slice could be filled
    entirely with rows destined for the bin — silently dropping the overrides that DO apply,
    differently on different backends. The applicable ones are therefore selected in SQL, so
    the outcome is a function of the data.

    `sort_order` here is the INVERSE of insertion order, so a selection that fell back to
    primary-key order would keep a different set — which is what makes this able to fail.
    """
    key = _license_key(tag="ovorder")
    _assign(key, Plan.objects.get(code="PRO"))
    seeded = GrantDimension.objects.filter(is_active=True).count()
    extra = MAX_GRANT_DIMENSIONS + 20

    dimensions = []
    for index in range(extra):
        dimension = GrantDimension.objects.create(
            key=f"ord_{index:03d}",
            display_name=f"Ord {index}",
            value_type=GrantValueType.INTEGER,
            default_raw_value="",
            # Inverse of creation order: the LAST row created sorts first.
            sort_order=2000 + (extra - index),
        )
        _override(key, dimension.key, str(index + 1))
        dimensions.append(dimension)

    values = resolve_entitlement(key).values
    # The active-dimension cap is filled by sort order, so the lowest-sorted extras are in
    # and the highest-sorted are out. Under primary-key order these would be reversed.
    by_sort = sorted(dimensions, key=lambda d: (d.sort_order, d.key))
    admitted = MAX_GRANT_DIMENSIONS - seeded
    assert by_sort[0].key in values, "selection did not honour sort_order"
    assert by_sort[-1].key not in values, "selection did not honour sort_order"
    # Every override that survived is one the plan map actually knows about.
    assert sum(1 for d in dimensions if d.key in values) == admitted

    GRANT_CACHE.clear()
    assert resolve_entitlement(key).values == values, (
        "two resolutions of the same licence disagreed"
    )


def test_overrides_cannot_push_the_merged_map_past_the_stated_cap():
    """The plan map is capped at MAX_GRANT_DIMENSIONS and so is the override slice, so a
    naive merge reaches 2x the cap while claiming to be bounded by it. Bounded either way,
    but the number must be the number the bound says — otherwise the cap documents nothing.
    """
    key = _license_key(tag="mergecap")
    _assign(key, Plan.objects.get(code="PRO"))
    existing = GrantDimension.objects.filter(is_active=True).count()

    created = []
    for index in range(MAX_GRANT_DIMENSIONS + 10):
        dimension = GrantDimension.objects.create(
            key=f"merge_{index:03d}",
            display_name=f"Merge {index}",
            value_type=GrantValueType.INTEGER,
            default_raw_value="",
            sort_order=3000 + index,
        )
        _override(key, dimension.key, str(index + 1))
        created.append(dimension)

    values = resolve_entitlement(key).values
    assert len(values) <= MAX_GRANT_DIMENSIONS, (
        f"the merged map holds {len(values)} grants against a stated cap of "
        f"{MAX_GRANT_DIMENSIONS}; plan grants and overrides were each capped but their "
        "union was not"
    )
    # Positive control: overrides inside the cap DO still apply, so the bound is not being
    # met by discarding every override.
    assert existing < MAX_GRANT_DIMENSIONS
    assert any(dimension.key in values for dimension in created)
