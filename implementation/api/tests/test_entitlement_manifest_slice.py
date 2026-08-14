"""Signed offline entitlement manifest — service + HTTP behaviour.

Issuance is an ALLOW-LIST. The parametrised licence-status test is driven off
`LicenseKeyStatus`, so adding a ninth status fails this suite rather than silently
qualifying for a signed multi-year entitlement.
"""

import base64
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import Device, DeviceStatus
from selahcue_api.apps.devices.services import ACTIVATABLE_KEY_STATUSES
from selahcue_api.apps.entitlements.services import build_entitlement_manifest
from selahcue_api.apps.entitlements.signing import (
    SigningKeyUnavailable,
    load_signing_key,
    verify_envelope,
)
from selahcue_api.apps.license_keys.models import LicenseKeyStatus
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

TEST_SEED_B64 = base64.b64encode(bytes(range(32))).decode("ascii")

pytestmark = pytest.mark.django_db


# Module-local seeding helpers, mirroring tests/test_license_refresh_slice.py. The shipped
# slices each build their own rather than sharing a conftest.py — follow that.
def _seed_license_key(*, tag, device_limit=3, starts_at=None, expires_at=None):
    """Returns (AppLicenseKey, full_key)."""
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

    customer = CustomerOrg.objects.create(
        name=f"Manifest Church {tag}",
        slug=f"manifest-church-{tag}",
        primary_contact_email=f"ops+{tag}@manifest.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        device_limit=device_limit,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"customer-org-{tag}",
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
            idempotency_key=f"license-key-{tag}",
            customer_id=str(customer.id),
            key_type="TRIAL",
            feature_scope="CHURCH",
            starts_at=starts_at or now,
            expires_at=expires_at or (now + timedelta(days=30)),
            timezone="Africa/Lagos",
            seat_limit=5,
            device_limit=device_limit,
            territory="NG",
            reason="Pilot for entitlement-manifest tests.",
        ),
    )
    return result.license_key, result.full_key


def _activate(client, *, full_key, tag):
    """Activate over HTTP, as the refresh slice does. Returns (device_token, device_public_id)."""
    body = {
        "idempotency_key": f"manifest-act-{tag}",
        "license_key": full_key,
        "device_fingerprint": f"fp-manifest-{tag}",
        "platform": "macos",
    }
    resp = client.post("/v1/activations", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200, resp.content
    payload = resp.json()
    return payload["activation_token"], payload["device"]["device_public_id"]


@pytest.fixture(autouse=True)
def signing_key(settings):
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    return TEST_SEED_B64


@pytest.fixture
def activated(client):
    """An activated device on a live licence. Returns (Device, device_token, AppLicenseKey)."""
    key, full_key = _seed_license_key(tag="m1")
    token, device_public_id = _activate(client, full_key=full_key, tag="m1")
    device = Device.objects.get(device_public_id=device_public_id)
    # First activation flips the key ISSUED -> ACTIVATED (devices/services.py), so the
    # in-memory object returned at creation is stale. Refresh, or assertions compare
    # against a status the database no longer holds.
    key.refresh_from_db()
    return device, token, key


def _payload(token):
    result = build_entitlement_manifest(token)
    return verify_envelope(
        result.envelope, public_key=load_signing_key(TEST_SEED_B64).public_key()
    )


def test_manifest_is_signed_and_verifies(activated):
    device, token, _key = activated
    result = build_entitlement_manifest(token)
    assert result.envelope["alg"] == "Ed25519"
    payload = verify_envelope(
        result.envelope, public_key=load_signing_key(TEST_SEED_B64).public_key()
    )
    assert payload["device_public_id"] == device.device_public_id


def test_manifest_is_bound_to_the_requesting_device(activated):
    device, token, _key = activated
    payload = _payload(token)
    assert payload["device_public_id"] == device.device_public_id
    assert payload["device_fingerprint"] == device.device_fingerprint


def test_expiry_equals_the_licence_window_exactly(activated):
    _device, token, key = activated
    payload = _payload(token)
    assert payload["expires_at"] == key.expires_at.isoformat()
    assert payload["not_before"] == key.starts_at.isoformat()


def test_license_status_passes_through_verbatim(activated):
    _device, token, key = activated
    payload = _payload(token)
    assert payload["license_status"] == key.status
    assert payload["license_status"] in {s.value for s in LicenseKeyStatus}


@pytest.mark.parametrize("status", [s.value for s in LicenseKeyStatus])
def test_only_activatable_statuses_are_issued_a_manifest(activated, status):
    """Every enum member, so a newly added status denies by default."""
    _device, token, key = activated
    # Keep expires_at in the future so the device token stays live and auth still passes —
    # this is what makes the REVOKED case reachable at all.
    key.status = status
    key.save(update_fields=["status", "updated_at"])

    if status in {s.value for s in ACTIVATABLE_KEY_STATUSES}:
        assert build_entitlement_manifest(token).envelope["alg"] == "Ed25519"
    else:
        with pytest.raises(SafeAPIError) as caught:
            build_entitlement_manifest(token)
        assert caught.value.code == ErrorCode.POLICY_DENIED


def test_licence_not_yet_started_is_denied(activated):
    _device, token, key = activated
    key.starts_at = timezone.now() + timedelta(days=1)
    key.save(update_fields=["starts_at", "updated_at"])
    with pytest.raises(SafeAPIError) as caught:
        build_entitlement_manifest(token)
    assert caught.value.code == ErrorCode.POLICY_DENIED


def test_unknown_token_is_unauthenticated(activated):
    with pytest.raises(SafeAPIError) as caught:
        build_entitlement_manifest("not-a-real-token")
    assert caught.value.code == ErrorCode.UNAUTHENTICATED


def test_empty_token_is_unauthenticated(activated):
    with pytest.raises(SafeAPIError) as caught:
        build_entitlement_manifest("")
    assert caught.value.code == ErrorCode.UNAUTHENTICATED


def test_revoked_device_is_unauthenticated_not_policy_denied(activated):
    """DeviceStatus has only ACTIVE and REVOKED; the shipped auth helper owns this."""
    device, token, _key = activated
    device.status = DeviceStatus.REVOKED
    device.save(update_fields=["status", "updated_at"])
    with pytest.raises(SafeAPIError) as caught:
        build_entitlement_manifest(token)
    assert caught.value.code == ErrorCode.UNAUTHENTICATED


def test_missing_signing_key_fails_loudly(activated, settings):
    _device, token, _key = activated
    settings.ENTITLEMENT_SIGNING_KEY = ""
    with pytest.raises(SigningKeyUnavailable):
        build_entitlement_manifest(token)


def test_instances_are_reported(activated):
    _device, token, key = activated
    payload = _payload(token)
    assert payload["instances_limit"] == key.device_limit
    assert (
        payload["instances_used"]
        == Device.objects.filter(license_key=key, status=DeviceStatus.ACTIVE).count()
    )


def test_issuance_is_audited(activated):
    _device, token, _key = activated
    before = AuditEvent.objects.filter(action="entitlement.manifest_issued").count()
    build_entitlement_manifest(token)
    assert (
        AuditEvent.objects.filter(action="entitlement.manifest_issued").count() == before + 1
    )


def test_no_token_material_in_the_payload(activated):
    _device, token, _key = activated
    payload = _payload(token)
    assert token not in str(payload)
    for banned in ("device_token", "full_key", "secret", "token_hash"):
        assert banned not in payload
