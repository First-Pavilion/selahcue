"""Migration equivalence: no pre-catalogue licence loses anything (FR-544 acceptance).

Exercises `apps/catalogue/backfill.py` — the function migration 0003 is a thin call to —
directly against real models, so the equivalence it promises is asserted rather than
assumed. The claim under test, stated precisely:

    For every licence that existed before the catalogue, the entitlement resolved AFTER
    the backfill grants exactly what the licence granted BEFORE it: the same seat cap
    (`device_limit`), uncapped screen and NDI outputs, no watermark, and no hosted STT
    allowance — because nothing capped outputs, nothing drew a watermark, and hosted STT
    did not exist.

Parametrised over several distinct `feature_scope` values, since "per existing value" is
what the acceptance criterion asks for and a single value would not distinguish a working
mapping from one that happens to land on the fallback anyway.

Module-local seeding helpers, mirroring tests/test_entitlement_manifest_slice.py.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from selahcue_api.apps.catalogue.backfill import (
    BackfillPreconditionError,
    backfill_licenses_into_catalogue,
)
from selahcue_api.apps.catalogue.cache import GRANT_CACHE
from selahcue_api.apps.catalogue.models import (
    GrantDimension,
    LicenseGrantOverride,
    Plan,
    PlanScopeAlias,
)
from selahcue_api.apps.catalogue.services import resolve_entitlement
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus, LicenseKeyType

pytestmark = pytest.mark.django_db

SEAT_KEY = "device_instances"
SCREEN_KEY = "screen_outputs"
NDI_KEY = "ndi_outputs"
STT_KEY = "stt_minutes_per_period"
WATERMARK_KEY = "watermark"

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


def _seed_pre_catalogue_estate():
    """Licences as they existed before this catalogue, with no catalogue rows of their own."""
    from selahcue_api.apps.accounts.models import CustomerOrg

    org = CustomerOrg.objects.create(
        name="Backfill Church",
        slug="backfill-church",
        primary_contact_email="ops@backfill.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=30,
        device_limit=1,
        created_by_actor_id="staff_ops_1",
        idempotency_key="backfill-org",
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
            secret_fingerprint=f"backfill-fp-{index}",
            starts_at=now,
            expires_at=now + timedelta(days=365),
            timezone="Africa/Lagos",
            feature_scope=feature_scope,
            seat_limit=30,
            device_limit=device_limit,
            territory="NG",
            generated_by_actor_id="staff_ops_1",
            generated_reason="Issued before the catalogue existed.",
            idempotency_key=f"backfill-license-{index}",
        )
    return keys


def _run_backfill():
    return backfill_licenses_into_catalogue(
        license_key_model=AppLicenseKey,
        plan_model=Plan,
        alias_model=PlanScopeAlias,
        dimension_model=GrantDimension,
        override_model=LicenseGrantOverride,
    )


@pytest.mark.parametrize(("feature_scope", "device_limit"), PRE_CATALOGUE_LICENSES)
def test_each_existing_feature_scope_keeps_exactly_what_it_granted(feature_scope, device_limit):
    keys = _seed_pre_catalogue_estate()
    _run_backfill()

    resolved = resolve_entitlement(keys[feature_scope])

    # The one limit that was actually enforced before the catalogue.
    assert resolved.instance_limit == device_limit, (
        f"licence with feature_scope={feature_scope!r} had device_limit={device_limit} and "
        f"now resolves to {resolved.instance_limit}"
    )
    assert resolved.values[SEAT_KEY] == device_limit
    # The four dimensions that did not exist before, pinned to the behaviour that did.
    assert resolved.values[SCREEN_KEY] is None, "outputs were uncapped before the catalogue"
    assert resolved.values[NDI_KEY] is None, "NDI was uncapped before the catalogue"
    assert resolved.values[WATERMARK_KEY] is False, "no watermark was drawn before the catalogue"
    assert resolved.values[STT_KEY] == 0, "hosted STT did not exist before the catalogue"


def test_every_distinct_scope_gets_an_alias_and_the_blank_one_does_not():
    _seed_pre_catalogue_estate()
    result = _run_backfill()

    distinct_non_blank = {scope.upper() for scope, _limit in PRE_CATALOGUE_LICENSES if scope}
    assert set(PlanScopeAlias.objects.values_list("feature_scope", flat=True)) == distinct_non_blank
    assert result.aliases_created == len(distinct_non_blank)
    # A blank scope has nothing to alias; it reaches the same plan through the fallback.
    assert PlanScopeAlias.objects.filter(feature_scope="").exists() is False


def test_the_blank_scope_still_resolves_and_keeps_its_seat_cap():
    keys = _seed_pre_catalogue_estate()
    _run_backfill()
    resolved = resolve_entitlement(keys[""])
    assert resolved.plan is not None and resolved.plan.is_fallback is True
    assert resolved.instance_limit == 2


def test_every_licence_gets_exactly_one_seat_override():
    _seed_pre_catalogue_estate()
    result = _run_backfill()
    assert result.licenses_seen == len(PRE_CATALOGUE_LICENSES)
    assert result.overrides_created == len(PRE_CATALOGUE_LICENSES)
    assert LicenseGrantOverride.objects.count() == len(PRE_CATALOGUE_LICENSES)


def test_re_running_the_backfill_converges_instead_of_duplicating():
    """A migration that is re-applied — or resumed after a partial failure — must not
    double-write, and the unique constraint must be what guarantees it."""
    _seed_pre_catalogue_estate()
    _run_backfill()
    second = _run_backfill()

    assert second.aliases_created == 0
    assert second.overrides_created == 0
    assert LicenseGrantOverride.objects.count() == len(PRE_CATALOGUE_LICENSES)
    assert PlanScopeAlias.objects.count() == len(
        {scope.upper() for scope, _limit in PRE_CATALOGUE_LICENSES if scope}
    )


def test_a_re_run_never_overwrites_an_override_an_operator_has_since_set():
    keys = _seed_pre_catalogue_estate()
    _run_backfill()

    override = LicenseGrantOverride.objects.get(
        license_key=keys["CHURCH"], dimension__key=SEAT_KEY
    )
    override.raw_value = "9"
    override.reason = "Owner granted extra seats."
    override.save(update_fields=["raw_value", "reason", "updated_at"])

    _run_backfill()

    override.refresh_from_db()
    assert override.raw_value == "9"
    assert resolve_entitlement(keys["CHURCH"]).instance_limit == 9


def test_the_backfill_refuses_to_run_without_its_reference_data():
    """Silently mapping nothing would leave the estate unmapped and look like success."""
    _seed_pre_catalogue_estate()
    Plan.objects.filter(is_fallback=True).update(is_fallback=False)

    with pytest.raises(BackfillPreconditionError):
        _run_backfill()
    assert LicenseGrantOverride.objects.count() == 0


def test_the_backfill_names_no_tier_and_finds_its_targets_by_flag():
    """The bridge plan and the seat dimension are located by their data flags. Moving the
    flag to a different row moves the backfill with it — which is what makes the catalogue
    renameable."""
    _seed_pre_catalogue_estate()
    Plan.objects.filter(is_fallback=True).update(is_fallback=False)
    moved = Plan.objects.get(code="FREE")
    moved.is_fallback = True
    moved.save(update_fields=["is_fallback", "updated_at"])

    _run_backfill()

    assert set(PlanScopeAlias.objects.values_list("plan__code", flat=True)) == {moved.code}
