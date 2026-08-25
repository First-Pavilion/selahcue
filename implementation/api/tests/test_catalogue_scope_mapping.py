"""Migration equivalence: no pre-catalogue licence loses anything (FR-544 acceptance).

Exercises migration `0003_map_existing_feature_scopes` by **importing the migration module
itself** and calling its function against real models. That keeps the guarantee testable
without the migration having to import application code — a migration that depends on a
module someone can later delete or rename breaks `migrate` everywhere, including on a fresh
database, which is a worse failure than the drift it was avoiding.

The claim under test, stated precisely:

    For every licence that existed before the catalogue, the entitlement resolved AFTER the
    mapping grants exactly what the licence granted BEFORE it: the same seat cap (still
    `AppLicenseKey.device_limit`, which the catalogue does not touch and the manifest
    publishes directly), uncapped screen and NDI outputs, no watermark, and no hosted STT
    allowance — because nothing capped outputs, nothing drew a watermark, and hosted STT
    did not exist.

Parametrised over several distinct `feature_scope` values, since "per existing value" is
what the acceptance criterion asks for and a single value would not distinguish a working
mapping from one that happens to land on the fallback anyway.

Module-local seeding helpers, mirroring tests/test_entitlement_manifest_slice.py.
"""

from __future__ import annotations

import importlib
from datetime import timedelta

import pytest
from django.apps import apps as django_apps
from django.utils import timezone

from selahcue_api.apps.catalogue.cache import GRANT_CACHE
from selahcue_api.apps.catalogue.models import LicenseGrantOverride, Plan, PlanScopeAlias
from selahcue_api.apps.catalogue.services import resolve_entitlement
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus, LicenseKeyType

pytestmark = pytest.mark.django_db

SEAT_KEY = "device_instances"
SCREEN_KEY = "screen_outputs"
NDI_KEY = "ndi_outputs"
STT_KEY = "stt_minutes_per_period"
WATERMARK_KEY = "watermark"

MIGRATION_MODULE = "selahcue_api.apps.catalogue.migrations.0003_map_existing_feature_scopes"

# The estate as it looks before the catalogue: assorted scopes, assorted seat caps,
# including the blank scope and the mixed casing the two issuance paths actually produce.
PRE_CATALOGUE_LICENSES = [
    ("CHURCH", 3),
    ("core", 1),
    ("pro", 7),
    ("INTERNAL_QA", 25),
    ("", 2),
]


@pytest.fixture(autouse=True)
def _cold_grant_cache():
    GRANT_CACHE.clear()
    yield
    GRANT_CACHE.clear()


def _migration():
    """The migration module, imported by name — its name starts with a digit, so this is
    `import_module` rather than an import statement."""
    return importlib.import_module(MIGRATION_MODULE)


def _seed_pre_catalogue_estate():
    """Licences as they existed before this catalogue, with no catalogue rows of their own."""
    from selahcue_api.apps.accounts.models import CustomerOrg

    org = CustomerOrg.objects.create(
        name="Mapping Church",
        slug="mapping-church",
        primary_contact_email="ops@mapping.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=30,
        device_limit=1,
        created_by_actor_id="staff_ops_1",
        idempotency_key="mapping-org",
    )
    now = timezone.now().replace(microsecond=0)
    keys = {}
    for index, (feature_scope, device_limit) in enumerate(PRE_CATALOGUE_LICENSES):
        keys[feature_scope] = AppLicenseKey.objects.create(
            customer=org,
            key_type=LicenseKeyType.PAID,
            status=LicenseKeyStatus.ACTIVATED,
            key_prefix=f"SC-PAID-{index}",
            key_suffix=f"{index:04d}",
            masked_key=f"SC-PAID-{index}...{index:04d}",
            secret_hash="x",
            secret_fingerprint=f"mapping-fp-{index}",
            starts_at=now,
            expires_at=now + timedelta(days=365),
            timezone="Africa/Lagos",
            feature_scope=feature_scope,
            seat_limit=30,
            device_limit=device_limit,
            territory="NG",
            generated_by_actor_id="staff_ops_1",
            generated_reason="Issued before the catalogue existed.",
            idempotency_key=f"mapping-license-{index}",
        )
    return keys


def _run_mapping():
    """Run the migration's forward function against the CURRENT models.

    `django_apps` stands in for the historical registry the executor would pass; the
    migration only calls `get_model`, so the two are interchangeable here and this exercises
    the real code path rather than a copy of it.
    """
    return _migration().map_scopes(django_apps, None)


@pytest.mark.parametrize(("feature_scope", "device_limit"), PRE_CATALOGUE_LICENSES)
def test_each_existing_feature_scope_keeps_exactly_what_it_granted(feature_scope, device_limit):
    keys = _seed_pre_catalogue_estate()
    _run_mapping()

    resolved = resolve_entitlement(keys[feature_scope])

    # The catalogue asserts NOTHING about seats for a legacy licence: absent, not null.
    # `device_limit` stays the single source for that quantity, untouched by this mapping.
    assert SEAT_KEY not in resolved.values, (
        "the catalogue published a seat number for a legacy licence, which can only "
        "disagree with the device_limit the manifest publishes"
    )
    keys[feature_scope].refresh_from_db()
    assert keys[feature_scope].device_limit == device_limit

    # The four dimensions that did not exist before, pinned to the behaviour that did.
    assert resolved.values[SCREEN_KEY] is None, "outputs were uncapped before the catalogue"
    assert resolved.values[NDI_KEY] is None, "NDI was uncapped before the catalogue"
    assert resolved.values[WATERMARK_KEY] is False, "no watermark was drawn before the catalogue"
    assert resolved.values[STT_KEY] == 0, (
        "hosted STT did not exist before the catalogue, and with FR-546 metering unbuilt a "
        "non-zero allowance would be an unmetered one"
    )


def test_every_distinct_scope_gets_an_alias_and_the_blank_one_does_not():
    _seed_pre_catalogue_estate()
    _run_mapping()

    distinct_non_blank = {scope.upper() for scope, _limit in PRE_CATALOGUE_LICENSES if scope}
    assert set(PlanScopeAlias.objects.values_list("feature_scope", flat=True)) == distinct_non_blank
    # A blank scope has nothing to alias; it reaches the same plan through the fallback.
    assert PlanScopeAlias.objects.filter(feature_scope="").exists() is False


def test_the_blank_scope_still_resolves_through_the_fallback():
    keys = _seed_pre_catalogue_estate()
    _run_mapping()
    resolved = resolve_entitlement(keys[""])
    assert resolved.plan is not None and resolved.plan.is_fallback is True
    assert resolved.values[WATERMARK_KEY] is False


def test_the_mapping_writes_no_per_licence_overrides():
    """A day-one override on 100% of rows makes the override table unauditable: nothing in
    it is exceptional any more. Seats are carried by `device_limit`, which needs no row."""
    _seed_pre_catalogue_estate()
    _run_mapping()
    assert LicenseGrantOverride.objects.count() == 0


def test_re_running_the_mapping_converges_instead_of_duplicating():
    """A migration that is re-applied — or resumed after a partial failure — must not
    double-write."""
    _seed_pre_catalogue_estate()
    _run_mapping()
    before = set(PlanScopeAlias.objects.values_list("feature_scope", flat=True))
    _run_mapping()

    assert set(PlanScopeAlias.objects.values_list("feature_scope", flat=True)) == before
    assert PlanScopeAlias.objects.count() == len(before)


def test_a_re_run_never_repoints_an_alias_an_operator_has_moved():
    keys = _seed_pre_catalogue_estate()
    _run_mapping()

    alias = PlanScopeAlias.objects.get(feature_scope="CHURCH")
    alias.plan = Plan.objects.get(code="PRO")
    alias.save(update_fields=["plan", "updated_at"])

    _run_mapping()

    alias.refresh_from_db()
    assert alias.plan.code == "PRO"
    assert resolve_entitlement(keys["CHURCH"]).values[SCREEN_KEY] == 5


def test_the_mapping_refuses_to_run_without_its_reference_data():
    """Silently mapping nothing would leave the estate unmapped and look like success."""
    _seed_pre_catalogue_estate()
    PlanScopeAlias.objects.all().delete()
    Plan.objects.filter(is_fallback=True).update(is_fallback=False)

    with pytest.raises(RuntimeError):
        _run_mapping()
    assert PlanScopeAlias.objects.count() == 0


def test_the_mapping_names_no_tier_and_finds_its_target_by_flag():
    """The bridge plan is located by its data flag. Moving the flag to a different row
    moves the mapping with it — which is what makes the catalogue renameable."""
    _seed_pre_catalogue_estate()
    Plan.objects.filter(is_fallback=True).update(is_fallback=False)
    moved = Plan.objects.get(code="FREE")
    moved.is_fallback = True
    moved.save(update_fields=["is_fallback", "updated_at"])

    _run_mapping()

    assert set(PlanScopeAlias.objects.values_list("plan__code", flat=True)) == {moved.code}


def test_the_reverse_leaves_a_repointed_alias_alone():
    _seed_pre_catalogue_estate()
    _run_mapping()
    moved = PlanScopeAlias.objects.get(feature_scope="CHURCH")
    moved.plan = Plan.objects.get(code="PLATINUM")
    moved.save(update_fields=["plan", "updated_at"])

    _migration().unmap_scopes(django_apps, None)

    remaining = set(PlanScopeAlias.objects.values_list("feature_scope", flat=True))
    assert remaining == {"CHURCH"}, "reversing downgraded an org that had been moved onto a tier"
