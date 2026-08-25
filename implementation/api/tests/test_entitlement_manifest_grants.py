"""The manifest carries typed values, never a tier name (FR-545).

The point of separating value from label: a client that branches on `"pro"` misreads every
future tier, and every rename becomes a client release — to machines that are deliberately
offline. So the payload gains a `grants` map whose keys come from catalogue rows and whose
values are booleans and integers, while `feature_scope` and `plan_display_label` are for
humans only.

The change is ADDITIVE, and `test_every_field_the_previous_version_carried_is_still_present`
is what actually protects an older desktop client — not the version number, which nothing
currently reads. `entitlement_version` therefore stays at 1: bumping it for an addition
would teach the first consumer that the number is noise, so a genuinely breaking change
later could not be gated on it.

Module-local seeding helpers, mirroring tests/test_entitlement_manifest_slice.py; a shared
conftest.py is deliberately not used here.
"""

from __future__ import annotations

import base64
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from selahcue_api.apps.catalogue.cache import GRANT_CACHE
from selahcue_api.apps.catalogue.models import (
    GrantDimension,
    GrantValueType,
    LicenseGrantOverride,
    LicensePlanAssignment,
    Plan,
    PlanGrant,
    PlanScopeAlias,
)
from selahcue_api.apps.devices.models import Device
from selahcue_api.apps.entitlements.services import build_entitlement_manifest
from selahcue_api.apps.entitlements.signing import load_signing_key, verify_envelope

TEST_SEED_B64 = base64.b64encode(bytes(range(32))).decode("ascii")

pytestmark = pytest.mark.django_db

SEAT_KEY = "device_instances"
SCREEN_KEY = "screen_outputs"
NDI_KEY = "ndi_outputs"
STT_KEY = "stt_minutes_per_period"
WATERMARK_KEY = "watermark"

# Every field the manifest carried before the catalogue landed. An older client caches and
# reads these; losing one is the break this suite exists to catch.
VERSION_1_FIELDS = (
    "entitlement_version",
    "device_public_id",
    "device_fingerprint",
    "customer_org_id",
    "license_status",
    "license_valid_now",
    "license_starts_at",
    "license_expires_at",
    "feature_scope",
    "territory",
    "instances_used",
    "instances_limit",
    "issued_at",
    "not_before",
    "expires_at",
)


@pytest.fixture(autouse=True)
def _cold_grant_cache():
    GRANT_CACHE.clear()
    yield
    GRANT_CACHE.clear()


@pytest.fixture(autouse=True)
def _fresh_throttle_budget():
    """`/v1` is rate limited per (endpoint, client IP) and the LocMemCache lives for the whole
    pytest process, so budget spent earlier would otherwise 429 this module."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture(autouse=True)
def signing_key(settings):
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    return TEST_SEED_B64


def _seed_license_key(*, tag, device_limit=3, feature_scope="CHURCH"):
    """Returns (AppLicenseKey, full_key). Mirrors tests/test_entitlement_manifest_slice.py."""
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

    customer = CustomerOrg.objects.create(
        name=f"Grants Church {tag}",
        slug=f"grants-church-{tag}",
        primary_contact_email=f"ops+{tag}@grants.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        device_limit=device_limit,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"grants-org-{tag}",
    )
    now = timezone.now().replace(microsecond=0)
    actor = ActorContext(
        kind=ActorKind.STAFF,
        actor_id="staff_ops_1",
        staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}),
    )
    result = generate_license_key(
        actor,
        GenerateLicenseKeyData(
            idempotency_key=f"grants-license-{tag}",
            customer_id=str(customer.id),
            key_type="TRIAL",
            feature_scope=feature_scope,
            starts_at=now,
            expires_at=now + timedelta(days=30),
            timezone="Africa/Lagos",
            seat_limit=5,
            device_limit=device_limit,
            territory="NG",
            reason="Pilot for entitlement-manifest grant tests.",
        ),
    )
    return result.license_key, result.full_key


def _activate(client, *, full_key, tag):
    body = {
        "idempotency_key": f"grants-act-{tag}",
        "license_key": full_key,
        "device_fingerprint": f"fp-grants-{tag}",
        "platform": "macos",
    }
    resp = client.post("/v1/activations", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200, resp.content
    payload = resp.json()
    return payload["activation_token"], payload["device"]["device_public_id"]


@pytest.fixture
def activated(client):
    """An activated device on a live licence. Returns (Device, device_token, AppLicenseKey)."""
    key, full_key = _seed_license_key(tag="g1")
    token, device_public_id = _activate(client, full_key=full_key, tag="g1")
    device = Device.objects.get(device_public_id=device_public_id)
    # First activation flips the key ISSUED -> ACTIVATED, so the in-memory object is stale.
    key.refresh_from_db()
    return device, token, key


def _payload(token):
    result = build_entitlement_manifest(token)
    return verify_envelope(
        result.envelope, public_key=load_signing_key(TEST_SEED_B64).public_key()
    )


def _assign(license_key, code):
    LicensePlanAssignment.objects.update_or_create(
        license_key=license_key, defaults={"plan": Plan.objects.get(code=code)}
    )


# --- Values, not names ---------------------------------------------------------------------


def test_the_manifest_carries_every_decided_dimension_as_a_typed_value(activated):
    _device, token, key = activated
    _assign(key, "PRO")
    grants = _payload(token)["grants"]

    assert grants[SEAT_KEY] == 3
    assert grants[SCREEN_KEY] == 5
    assert grants[NDI_KEY] == 5
    assert grants[STT_KEY] == 300
    assert grants[WATERMARK_KEY] is False
    # Typed, not stringly: a client that has to parse "5" is one bad value from a crash.
    assert isinstance(grants[WATERMARK_KEY], bool)
    assert isinstance(grants[SCREEN_KEY], int) and not isinstance(grants[SCREEN_KEY], bool)


def test_the_free_tier_watermarks_and_the_paid_tiers_do_not(activated):
    _device, token, key = activated
    _assign(key, "FREE")
    assert _payload(token)["grants"][WATERMARK_KEY] is True
    _assign(key, "PLATINUM")
    assert _payload(token)["grants"][WATERMARK_KEY] is False


def test_a_rename_does_not_change_a_single_granted_value(activated):
    _device, token, key = activated
    _assign(key, "PLATINUM")
    before = _payload(token)["grants"]

    plan = Plan.objects.get(code="PLATINUM")
    plan.display_name = "Something Else Entirely"
    plan.save(update_fields=["display_name", "updated_at"])

    after = _payload(token)
    assert after["grants"] == before, "a rename changed the values a client enforces"
    assert after["plan_display_label"] == "Something Else Entirely"


def test_a_tier_that_did_not_exist_when_the_client_shipped_is_carried_verbatim(activated):
    """A brand-new tier introduced as data. Nothing in the manifest path enumerates tiers,
    so an unmodified client receives its values and honours them."""
    _device, token, key = activated
    plan = Plan.objects.create(code="OBSIDIAN", display_name="Obsidian", sort_order=99)
    for dimension_key, raw_value in (
        (SEAT_KEY, "12"),
        (SCREEN_KEY, "14"),
        (NDI_KEY, "15"),
        (STT_KEY, "1234"),
        (WATERMARK_KEY, "false"),
    ):
        PlanGrant.objects.create(
            plan=plan, dimension=GrantDimension.objects.get(key=dimension_key), raw_value=raw_value
        )
    LicensePlanAssignment.objects.update_or_create(license_key=key, defaults={"plan": plan})

    payload = _payload(token)
    assert payload["grants"] == {
        SEAT_KEY: 12,
        SCREEN_KEY: 14,
        NDI_KEY: 15,
        STT_KEY: 1234,
        WATERMARK_KEY: False,
    }
    # Still the enforced number, not the new tier's aspiration.
    assert payload["instances_limit"] == key.device_limit


def test_changing_a_grant_value_reaches_the_next_manifest_with_no_release(activated):
    _device, token, key = activated
    _assign(key, "PRO")
    assert _payload(token)["grants"][STT_KEY] == 300

    grant = PlanGrant.objects.get(plan__code="PRO", dimension__key=STT_KEY)
    grant.raw_value = "480"
    grant.save(update_fields=["raw_value", "updated_at"])

    assert _payload(token)["grants"][STT_KEY] == 480


def test_no_tier_name_appears_anywhere_in_the_signed_payload_except_as_a_label(activated):
    """`plan_display_label` and `feature_scope` are the only places a name may appear, and
    both are documented as display-only. Anything else would invite client branching."""
    _device, token, key = activated
    _assign(key, "PLATINUM")
    payload = _payload(token)

    plan = Plan.objects.get(code="PLATINUM")
    label_fields = {"plan_display_label", "feature_scope"}
    for field, value in payload.items():
        if field in label_fields or not isinstance(value, str):
            continue
        assert value.strip().casefold() != plan.code.casefold()
        assert value.strip().casefold() != plan.display_name.casefold()
    assert set(payload["grants"]).isdisjoint({plan.code, plan.display_name})


# --- One quantity, one field ---------------------------------------------------------------
#
# The manifest is SIGNED and cached offline for the licence's lifetime. Two fields in it
# disagreeing about the same quantity is worse than either being wrong: the client cannot
# tell which to trust, and the artefact outlives the disagreement. `instances_limit` is
# `AppLicenseKey.device_limit` — the number `activate_device` enforces — and nothing else.


@pytest.mark.parametrize(
    "plan_code",
    [None, "LEGACY", "FREE", "PRO", "PLATINUM"],
)
def test_the_manifest_publishes_exactly_the_seat_number_activation_enforces(activated, plan_code):
    """The invariant, stated as a test: whatever the catalogue says about a tier's seats,
    the number the manifest publishes equals the number activation refuses the next device
    over. Not eventually — at all times."""
    _device, token, key = activated
    if plan_code is None:
        LicensePlanAssignment.objects.filter(license_key=key).delete()
        PlanScopeAlias.objects.all().delete()
    else:
        _assign(key, plan_code)

    key.refresh_from_db()
    assert _payload(token)["instances_limit"] == key.device_limit


def test_a_legacy_licence_publishes_no_catalogue_seat_number_at_all(activated):
    """The defect this replaced: `grants.device_instances` was `null` (INTEGER null =
    UNLIMITED) while `instances_limit` said 3. A client written per FR-545 — read the typed
    grants, never the labels — read unlimited seats from a signed artefact. Absent and
    unlimited must stay different states."""
    _device, token, key = activated
    LicensePlanAssignment.objects.filter(license_key=key).delete()
    PlanScopeAlias.objects.all().delete()
    payload = _payload(token)

    assert SEAT_KEY not in payload["grants"], (
        "the catalogue published a seat ceiling for a licence it knows nothing about; "
        "absent and unlimited are different states and must be encoded differently"
    )
    assert payload["instances_limit"] == key.device_limit
    # Positive control: the other grants ARE published, so "absent" is not an empty map.
    assert payload["grants"][WATERMARK_KEY] is False


def test_a_plans_seat_grant_travels_as_advice_and_never_moves_instances_limit(activated):
    """A plan may express a seat count; FR-516's write-back is what makes `device_limit`
    follow it. Until then the manifest must not publish the aspiration as the enforced
    number, or a church is told it has seven seats while the server refuses the fourth."""
    _device, token, key = activated
    _assign(key, "PLATINUM")
    payload = _payload(token)

    assert payload["grants"][SEAT_KEY] == 7
    assert payload["instances_limit"] == key.device_limit == 3


def test_an_override_does_not_move_instances_limit_either(activated):
    _device, token, key = activated
    _assign(key, "FREE")
    LicenseGrantOverride.objects.create(
        license_key=key,
        dimension=GrantDimension.objects.get(key=SEAT_KEY),
        raw_value="4",
        granted_by_actor_id="staff_ops_1",
        reason="Test override.",
    )
    payload = _payload(token)
    assert payload["grants"][SEAT_KEY] == 4
    assert payload["instances_limit"] == key.device_limit == 3


# --- Additive, and safe when the catalogue is not (NFR-024) ---------------------------------


def test_every_field_the_previous_version_carried_is_still_present(activated):
    _device, token, _key = activated
    payload = _payload(token)
    missing = [field for field in VERSION_1_FIELDS if field not in payload]
    assert missing == [], (
        "the manifest dropped a field an already-deployed client reads; the catalogue "
        f"change must be additive: {missing}"
    )


def test_an_empty_catalogue_still_issues_a_signed_manifest(activated):
    """Licensing must not be able to fail because catalogue data is missing."""
    _device, token, key = activated
    LicensePlanAssignment.objects.all().delete()
    PlanScopeAlias.objects.all().delete()
    PlanGrant.objects.all().delete()
    Plan.objects.all().delete()
    GrantDimension.objects.all().delete()

    payload = _payload(token)
    assert payload["grants"] == {}
    assert payload["plan_display_label"] == ""
    assert payload["instances_limit"] == key.device_limit
    # Positive control: it is a real, verifying manifest, not an error object.
    assert payload["device_public_id"] == _device.device_public_id


def test_a_dimension_named_like_a_restricted_field_cannot_deny_the_manifest(activated):
    """`assert_no_restricted_payload_fields` raises on such a key, and the manifest is the
    only enforcement point that exists — one catalogue row must not be able to take
    licensing down for the whole estate."""
    _device, token, key = activated
    _assign(key, "PRO")
    hostile = GrantDimension.objects.create(
        key="signing_key",
        display_name="Hostile",
        value_type=GrantValueType.INTEGER,
        default_raw_value="1",
        sort_order=98,
    )
    PlanGrant.objects.create(plan=Plan.objects.get(code="PRO"), dimension=hostile, raw_value="1")

    payload = _payload(token)
    assert "signing_key" not in payload["grants"]
    # Positive control: the benign grants are still there, so the manifest did not simply
    # come back empty.
    assert payload["grants"][SCREEN_KEY] == 5


def test_the_http_surface_returns_the_grants(client, activated):
    _device, token, key = activated
    _assign(key, "PRO")
    resp = client.get(
        "/v1/entitlements/manifest", headers={"authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.content
    payload = verify_envelope(
        resp.json(), public_key=load_signing_key(TEST_SEED_B64).public_key()
    )
    assert payload["grants"][NDI_KEY] == 5


def test_the_entitlement_version_did_not_move_for_an_additive_change():
    """Bump only when a client that ignores unknown keys and defaults missing ones would
    behave incorrectly. `grants` and `plan_display_label` are neither."""
    from selahcue_api.apps.entitlements.services import ENTITLEMENT_VERSION

    assert ENTITLEMENT_VERSION == 1


def test_an_expired_override_does_not_reach_the_manifest(activated):
    from datetime import timedelta as _timedelta

    _device, token, key = activated
    _assign(key, "FREE")
    LicenseGrantOverride.objects.create(
        license_key=key,
        dimension=GrantDimension.objects.get(key=NDI_KEY),
        raw_value="9",
        granted_by_actor_id="staff_ops_1",
        reason="Lapsed conference loan.",
        expires_at=timezone.now() - _timedelta(seconds=1),
    )
    assert _payload(token)["grants"][NDI_KEY] == 0
    # Positive control: unexpired, the same row does reach the manifest.
    LicenseGrantOverride.objects.filter(license_key=key).update(
        expires_at=timezone.now() + _timedelta(days=1)
    )
    assert _payload(token)["grants"][NDI_KEY] == 9
