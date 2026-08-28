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
from datetime import datetime, timedelta

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

# The DATABASE requires an actor and a reason on `Plan` and `PlanGrant` rows (migration
# 0004), exactly as it already did on assignments and overrides — a bare `objects.create()`
# is refused. Supplied here so these tests exercise the rows, not the constraint.
ACCOUNTABLE = {
    "changed_by_actor_id": "staff_ops_1",
    "reason": "Catalogue tests: fixture row.",
}


SEAT_KEY = "device_instances"
SCREEN_KEY = "screen_outputs"
NDI_KEY = "ndi_outputs"
STT_KEY = "stt_minutes_per_period"
WATERMARK_KEY = "watermark"

# Every field the manifest carried before the catalogue landed, WITH its JSON type. An
# older client caches and reads these; losing one breaks it, and so does silently changing
# one's type — `license_valid_now` becoming a string, or `territory` becoming a list, is
# exactly the "retyped" case the bump rule in `entitlements/services.py` names, and a
# presence-only check waves it straight through.
VERSION_1_FIELDS = (
    ("entitlement_version", int),
    ("device_public_id", str),
    ("device_fingerprint", str),
    ("customer_org_id", str),
    ("license_status", str),
    ("license_valid_now", bool),
    ("license_starts_at", str),
    ("license_expires_at", str),
    ("feature_scope", str),
    ("territory", str),
    ("instances_used", int),
    ("instances_limit", int),
    ("issued_at", str),
    ("not_before", str),
    ("expires_at", str),
)


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
    """Returns (AppLicenseKey, full_key). Mirrors tests/test_entitlement_manifest_slice.py.

    The ORG's `device_limit` is deliberately set to a DIFFERENT number from the licence's.
    Both columns are called `device_limit`, and when a test seeds them to the same value any
    assertion about seats passes whichever one the code reads — so a change to which column
    activation enforces becomes invisible. Keeping them apart is what lets that show up.
    """
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
        # Deliberately NOT `device_limit` — see the docstring.
        device_limit=device_limit + 7,
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
            plan_code="LEGACY",
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
    """Accountability columns are supplied because the DATABASE now requires them — a bare
    `objects.create()` is refused (see the catalogue slice's constraint tests)."""
    LicensePlanAssignment.objects.update_or_create(
        license_key=license_key,
        defaults={
            "plan": Plan.objects.get(code=code),
            "assigned_by_actor_id": "staff_ops_1",
            "reason": "Manifest grant tests.",
        },
    )


# --- Values, not names ---------------------------------------------------------------------


def test_the_manifest_carries_every_decided_dimension_as_a_typed_value(activated):
    _device, token, key = activated
    _assign(key, "PRO")
    grants = _payload(token)["grants"]

    # Seats are resolved but NOT published — `instances_limit` is the one seat number.
    assert SEAT_KEY not in grants
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
    plan = Plan.objects.create(
        code="OBSIDIAN", display_name="Obsidian", sort_order=99, **ACCOUNTABLE
    )
    for dimension_key, raw_value in (
        (SEAT_KEY, "12"),
        (SCREEN_KEY, "14"),
        (NDI_KEY, "15"),
        (STT_KEY, "1234"),
        (WATERMARK_KEY, "false"),
    ):
        PlanGrant.objects.create(
            plan=plan,
            dimension=GrantDimension.objects.get(key=dimension_key),
            raw_value=raw_value,
            **ACCOUNTABLE,
        )
    LicensePlanAssignment.objects.update_or_create(
        license_key=key,
        defaults={
            "plan": plan,
            "assigned_by_actor_id": "staff_ops_1",
            "reason": "Novel tier test.",
        },
    )

    payload = _payload(token)
    # Every publishable dimension of a tier that did not exist when this code was written,
    # carried verbatim. `device_instances` is resolved but unpublished, like every tier's.
    assert payload["grants"] == {
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


def test_a_plans_seat_grant_never_reaches_the_wire_or_moves_instances_limit(activated):
    """A plan may express a seat count, and PLATINUM does. Until something reconciles it
    with `device_limit` it stays off the wire entirely — publishing it would tell a church
    it has seven seats while the server refuses the fourth, in a signed artefact that
    outlives the disagreement."""
    _device, token, key = activated
    _assign(key, "PLATINUM")
    payload = _payload(token)

    assert SEAT_KEY not in payload["grants"]
    assert payload["instances_limit"] == key.device_limit == 3
    # Positive control: the tier's other grants DID come through, so absence is specific to
    # the seat dimension rather than a plan that failed to resolve.
    assert payload["grants"][SCREEN_KEY] == 10


def test_an_override_does_not_move_instances_limit_either(activated):
    _device, token, key = activated
    _assign(key, "FREE")
    LicenseGrantOverride.objects.create(
        license_key=key,
        dimension=GrantDimension.objects.get(key=SEAT_KEY),
        raw_value="4",
        granted_by_actor_id="staff_ops_1",
        reason="Seat override for this test.",
    )
    payload = _payload(token)
    # An override cannot promote an unpublished dimension onto the wire either: publishable
    # is a property of the dimension, not of one customer's exception.
    assert SEAT_KEY not in payload["grants"]
    assert payload["instances_limit"] == key.device_limit == 3


# --- Additive, and safe when the catalogue is not (NFR-024) ---------------------------------


def test_every_field_the_previous_version_carried_is_still_present_and_the_same_type(activated):
    _device, token, _key = activated
    payload = _payload(token)

    missing = [name for name, _type in VERSION_1_FIELDS if name not in payload]
    assert missing == [], (
        "the manifest dropped a field an already-deployed client reads; the catalogue "
        f"change must be additive: {missing}"
    )
    retyped = [
        f"{name}: expected {expected.__name__}, got {type(payload[name]).__name__}"
        for name, expected in VERSION_1_FIELDS
        # bool is a subclass of int, so check it first and exactly.
        if (type(payload[name]) is not expected)
    ]
    assert retyped == [], (
        "a field an already-deployed client reads changed type. That breaks a client just "
        f"as surely as removing it, and it is a case the bump rule names: {retyped}"
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
    PlanGrant.objects.create(
        plan=Plan.objects.get(code="PRO"), dimension=hostile, raw_value="1", **ACCOUNTABLE
    )

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


# --- The pair, asserted -----------------------------------------------------------------
#
# The lesson from the first defect: each half of a pair that must agree was asserted in
# isolation, and the pair itself never was. These relate `grants["device_instances"]` to
# `instances_limit` directly.


@pytest.mark.parametrize("plan_code", [None, "LEGACY", "FREE", "PRO", "PLATINUM"])
def test_the_payload_never_carries_two_seat_numbers(activated, plan_code):
    """The manifest must contain exactly ONE number describing seats.

    `device_instances` is unpublished, so the pair cannot disagree. Should anyone publish it
    later, the equality below becomes the live guard rather than a vacuous branch."""
    _device, token, key = activated
    if plan_code is None:
        LicensePlanAssignment.objects.filter(license_key=key).delete()
        PlanScopeAlias.objects.all().delete()
    else:
        _assign(key, plan_code)
    key.refresh_from_db()

    payload = _payload(token)
    published = payload["grants"]

    assert SEAT_KEY not in published, (
        "the catalogue's seat number reached the signed payload beside instances_limit="
        f"{payload['instances_limit']}. Nothing in the payload marks a grant advisory, so a "
        "client written per FR-545 would enforce the wrong one."
    )
    if SEAT_KEY in published:  # pragma: no cover - guard for a future decision to publish
        assert published[SEAT_KEY] == payload["instances_limit"]
    assert payload["instances_limit"] == key.device_limit


def test_the_unpublished_seat_row_still_exists_for_fr_516_to_read(activated):
    """Unpublished, not deleted. The catalogue still knows what a tier grants — it simply
    does not put it on the wire until something reconciles it with `device_limit`.

    Positive control for the test above: proves the value is absent from the payload
    BECAUSE it is unpublished, not because the plan has no seat grant at all."""
    _device, _token, key = activated
    _assign(key, "PLATINUM")

    dimension = GrantDimension.objects.get(key=SEAT_KEY)
    assert dimension.publish_in_manifest is False
    assert PlanGrant.objects.get(plan__code="PLATINUM", dimension=dimension).raw_value == "7"
    # And the server-side resolution still sees it, so FR-516 has something to act on.
    from selahcue_api.apps.catalogue.services import resolve_entitlement

    resolved = resolve_entitlement(key)
    assert resolved.values[SEAT_KEY] == 7
    assert SEAT_KEY not in resolved.published_values


def test_flipping_the_publish_flag_is_all_it_takes_to_ship_the_value(activated):
    """The day FR-516's write-back lands, publishing is a row edit — not a release."""
    _device, token, key = activated
    _assign(key, "PLATINUM")
    assert SEAT_KEY not in _payload(token)["grants"]

    dimension = GrantDimension.objects.get(key=SEAT_KEY)
    dimension.publish_in_manifest = True
    dimension.save(update_fields=["publish_in_manifest", "updated_at"])

    assert _payload(token)["grants"][SEAT_KEY] == 7


# --- A degraded read must not mint a multi-year artefact ------------------------------------


def test_a_failed_catalogue_read_still_issues_but_expires_in_minutes(activated, monkeypatch):
    """NFR-024 says issue rather than deny. It does not say freeze a two-second blip into a
    signed credential honoured offline for the rest of a two-year licence."""
    from selahcue_api.apps.catalogue import services as catalogue_services
    from selahcue_api.apps.entitlements.services import DEGRADED_MANIFEST_TTL_SECONDS

    _device, token, key = activated
    _assign(key, "PRO")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("catalogue database unavailable")

    monkeypatch.setattr(catalogue_services, "_plan_grant_map", _boom)

    payload = _payload(token)
    assert payload["grants"] == {}
    expires_at = datetime.fromisoformat(payload["expires_at"])
    assert expires_at < key.expires_at, (
        "a manifest built from a FAILED catalogue read carried the full licence window"
    )
    assert expires_at <= timezone.now() + timedelta(seconds=DEGRADED_MANIFEST_TTL_SECONDS + 5)


def test_an_unconfigured_catalogue_is_not_treated_as_a_failure(activated):
    """Positive control for the test above: an empty catalogue is a steady state, so it
    keeps the full licence window. Only a FAILED read is short-lived."""
    _device, token, key = activated
    LicensePlanAssignment.objects.all().delete()
    PlanScopeAlias.objects.all().delete()
    PlanGrant.objects.all().delete()
    Plan.objects.all().delete()
    GrantDimension.objects.all().delete()

    payload = _payload(token)
    assert payload["grants"] == {}
    assert datetime.fromisoformat(payload["expires_at"]) == key.expires_at


def test_a_degraded_issuance_is_audited_so_it_can_be_alerted_on(activated, monkeypatch):
    from selahcue_api.apps.audit.models import AuditEvent, AuditResult
    from selahcue_api.apps.catalogue import services as catalogue_services

    _device, token, key = activated
    _assign(key, "PRO")
    monkeypatch.setattr(
        catalogue_services,
        "_plan_grant_map",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")),
    )

    build_entitlement_manifest(token)
    event = AuditEvent.objects.filter(action="entitlement.manifest_issued").latest("id")
    assert event.after["degraded"] is True
    assert event.result == AuditResult.FAILED


def test_an_override_can_be_the_first_value_a_publishable_dimension_has(activated):
    """A publishable dimension the plan declares nothing for, given a value by a per-licence
    override, must still reach the client — resolving it and then withholding it would be a
    grant the customer paid for and the client never sees."""
    _device, token, key = activated
    _assign(key, "PRO")
    dimension = GrantDimension.objects.create(
        key="extra_widgets",
        display_name="Extra widgets",
        value_type=GrantValueType.INTEGER,
        default_raw_value="",
        sort_order=96,
    )
    assert dimension.publish_in_manifest is True
    assert "extra_widgets" not in _payload(token)["grants"], (
        "the dimension already had a value, so this test cannot show the override supplying one"
    )

    LicenseGrantOverride.objects.create(
        license_key=key,
        dimension=dimension,
        raw_value="4",
        granted_by_actor_id="staff_ops_1",
        reason="Bundled extra widgets for this church.",
    )
    assert _payload(token)["grants"]["extra_widgets"] == 4


def test_an_override_cannot_push_an_unpublishable_dimension_onto_the_wire(activated):
    """The mirror of the test above: `device_instances` is unpublishable, and a per-licence
    exception must not be able to promote it."""
    _device, token, key = activated
    _assign(key, "PRO")
    LicenseGrantOverride.objects.create(
        license_key=key,
        dimension=GrantDimension.objects.get(key=SEAT_KEY),
        raw_value="9",
        granted_by_actor_id="staff_ops_1",
        reason="Extra seats agreed for this church.",
    )
    payload = _payload(token)
    assert SEAT_KEY not in payload["grants"]
    assert payload["instances_limit"] == key.device_limit



def test_a_restricted_name_reaching_via_an_OVERRIDE_cannot_deny_the_manifest(activated):
    """The identical guard on the plan-grant path is tested; this is the override path.

    Without it a single per-licence override on a dimension named like a restricted field
    makes `assert_no_restricted_payload_fields` raise, and that licence can never be issued
    a manifest at all — the one enforcement point that exists, denied by one row."""
    _device, token, key = activated
    _assign(key, "PRO")
    hostile = GrantDimension.objects.create(
        key="device_token",
        display_name="Hostile override target",
        value_type=GrantValueType.INTEGER,
        default_raw_value="",
        sort_order=95,
    )
    LicenseGrantOverride.objects.create(
        license_key=key,
        dimension=hostile,
        raw_value="1",
        granted_by_actor_id="staff_ops_1",
        reason="Override on a restricted-looking dimension.",
    )

    payload = _payload(token)
    assert "device_token" not in payload["grants"]
    # Positive control: the licence still gets a real manifest with its ordinary grants.
    assert payload["grants"][SCREEN_KEY] == 5


def test_the_published_seat_number_is_the_one_activation_actually_refuses_over(client):
    """Ties the payload to BEHAVIOUR, not to another read of the same column.

    `instances_limit == device_limit` compares the field to itself: it stays green even if
    activation starts enforcing a different number entirely (a peer switching the guard to
    `license_key.customer.device_limit` would not disturb it). This activates devices up to
    the number the manifest publishes and asserts the very next one is refused — so the
    published number and the enforced number are demonstrably the same number.
    """
    seat_count = 2
    key, full_key = _seed_license_key(tag="seats", device_limit=seat_count)

    tokens = []
    for index in range(seat_count):
        body = {
            "idempotency_key": f"seats-act-{index}-aaaaaaaaaa",
            "license_key": full_key,
            "device_fingerprint": f"fp-seats-{index}",
            "platform": "macos",
        }
        resp = client.post(
            "/v1/activations", data=json.dumps(body), content_type="application/json"
        )
        assert resp.status_code == 200, resp.content
        tokens.append(resp.json()["activation_token"])

    published_limit = _payload(tokens[0])["instances_limit"]
    assert published_limit == seat_count

    # One more than the published number: activation must refuse it.
    overflow = client.post(
        "/v1/activations",
        data=json.dumps(
            {
                "idempotency_key": "seats-act-overflow-aaaa",
                "license_key": full_key,
                "device_fingerprint": "fp-seats-overflow",
                "platform": "macos",
            }
        ),
        content_type="application/json",
    )
    assert overflow.status_code == 403, (
        "activation admitted a device beyond the seat count the manifest publishes, so the "
        f"published number ({published_limit}) is not the enforced number"
    )
    assert overflow.json()["error"]["code"] == "POLICY_DENIED"

    # And the count the manifest reports as used matches what actually activated.
    assert _payload(tokens[0])["instances_used"] == seat_count
