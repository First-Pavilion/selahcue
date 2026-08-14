import json
from datetime import timedelta

import pytest
from django.utils import timezone


@pytest.fixture(autouse=True)
def _fresh_throttle_budget():
    """`/v1` is rate limited per (endpoint, client IP), and the default LocMemCache lives for
    the whole pytest process — so budget spent by an earlier test would otherwise leak into
    this one and 429 it. Reset the window instead of loosening the limits."""
    from django.core.cache import cache

    cache.clear()


def _seed_license_key(*, tag, device_limit=3, starts_at=None, expires_at=None):
    """Create a customer + issue a license key via the real service, returning
    (customer_id, full_key). The full key is show-once, so we capture it here to present it
    at activation — mirroring how the desktop would hold the enrollment key."""
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

    customer = CustomerOrg.objects.create(
        name=f"Activation Church {tag}",
        slug=f"activation-church-{tag}",
        primary_contact_email=f"ops+{tag}@activation.example",
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
            reason="Pilot for device activation tests.",
        ),
    )
    return str(customer.id), result.full_key


def _activate(client, *, license_key, fingerprint="fp-1", idem="act-default-0001", platform="macos", **extra):
    body = {
        "idempotency_key": idem,
        "license_key": license_key,
        "device_fingerprint": fingerprint,
        "platform": platform,
    }
    body.update(extra)
    return client.post("/v1/activations", data=json.dumps(body), content_type="application/json")


@pytest.mark.django_db
def test_activation_issues_show_once_device_token_and_activates_the_key(client):
    _customer_id, full_key = _seed_license_key(tag="ok")

    response = _activate(client, license_key=full_key, fingerprint="mac-booth-1", idem="act-ok-000001")
    assert response.status_code == 200
    body = response.json()
    assert body["created"] is True

    token = body["activation_token"]
    assert token.startswith("SC-DEV-")
    assert body["token"]["masked"] != token
    assert body["token"]["prefix"] == token[:12]
    assert body["token"]["suffix"] == token[-4:]
    assert body["device"]["device_public_id"].startswith("dev_")
    assert body["device"]["platform"] == "macos"

    from selahcue_api.apps.audit.models import AuditEvent
    from selahcue_api.apps.devices.models import Device, DeviceToken
    from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

    device = Device.objects.get()
    token_row = DeviceToken.objects.get()
    # Show-once secrecy: the full token is never stored in plaintext.
    assert full_key  # (the presented enrollment key)
    assert token not in token_row.token_hash
    assert token != token_row.token_fingerprint
    assert token_row.token_prefix == token[:12]
    # First activation flips the enrollment key ISSUED -> ACTIVATED.
    assert AppLicenseKey.objects.get().status == LicenseKeyStatus.ACTIVATED
    assert body["license"]["status"] == LicenseKeyStatus.ACTIVATED

    # Audit: exactly one device.activated, and the full token never leaks into it.
    activated = AuditEvent.objects.filter(action="device.activated")
    assert activated.count() == 1
    audit_json = json.dumps(
        [{"action": e.action, "after": e.after, "before": e.before} for e in activated],
        default=str,
    )
    # Neither the device token NOR the presented enrollment key ever leaks into the audit trail.
    assert token not in audit_json
    assert full_key not in audit_json


@pytest.mark.django_db
def test_activation_is_idempotent_and_never_replays_the_token(client):
    _customer_id, full_key = _seed_license_key(tag="idem")

    first = _activate(client, license_key=full_key, fingerprint="mac-1", idem="act-idem-0001")
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["created"] is True
    assert first_body["activation_token"]

    second = _activate(client, license_key=full_key, fingerprint="mac-1", idem="act-idem-0001")
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["created"] is False
    assert second_body["activation_token"] is None
    assert second_body["device"]["device_public_id"] == first_body["device"]["device_public_id"]
    assert first_body["activation_token"] not in json.dumps(second_body)

    from selahcue_api.apps.devices.models import Device, DeviceToken

    assert Device.objects.count() == 1
    assert DeviceToken.objects.count() == 1


@pytest.mark.django_db
def test_reactivating_a_known_device_returns_it_without_a_new_token(client):
    # Same install (fingerprint) re-enrolling with a DIFFERENT idempotency key is still one device.
    _customer_id, full_key = _seed_license_key(tag="known")

    first = _activate(client, license_key=full_key, fingerprint="mac-known", idem="act-known-0001")
    second = _activate(client, license_key=full_key, fingerprint="mac-known", idem="act-known-0002")
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["activation_token"] is None

    from selahcue_api.apps.devices.models import Device, DeviceToken

    assert Device.objects.count() == 1
    assert DeviceToken.objects.count() == 1


@pytest.mark.django_db
def test_unknown_key_is_not_found_and_creates_nothing(client):
    response = _activate(client, license_key="SC-TRIAL-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX", idem="act-unknown-1")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

    from selahcue_api.apps.devices.models import Device

    assert Device.objects.count() == 0


@pytest.mark.django_db
def test_expired_and_not_yet_started_and_revoked_keys_are_policy_denied(client):
    now = timezone.now().replace(microsecond=0)

    # Expired window.
    _cid, expired_key = _seed_license_key(
        tag="expired", starts_at=now - timedelta(days=40), expires_at=now - timedelta(days=10)
    )
    r1 = _activate(client, license_key=expired_key, fingerprint="fp-exp", idem="act-exp-000001")
    assert r1.status_code == 403
    assert r1.json()["error"]["code"] == "POLICY_DENIED"

    # Not yet started.
    _cid2, future_key = _seed_license_key(
        tag="future", starts_at=now + timedelta(days=10), expires_at=now + timedelta(days=40)
    )
    r2 = _activate(client, license_key=future_key, fingerprint="fp-fut", idem="act-fut-000001")
    assert r2.status_code == 403
    assert r2.json()["error"]["code"] == "POLICY_DENIED"

    # Revoked key.
    _cid3, revoked_key = _seed_license_key(tag="revoked")
    from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

    AppLicenseKey.objects.filter(status=LicenseKeyStatus.ISSUED).update(
        status=LicenseKeyStatus.REVOKED
    )
    r3 = _activate(client, license_key=revoked_key, fingerprint="fp-rev", idem="act-rev-000001")
    assert r3.status_code == 403
    assert r3.json()["error"]["code"] == "POLICY_DENIED"

    from selahcue_api.apps.devices.models import Device

    assert Device.objects.count() == 0


@pytest.mark.django_db
def test_instance_limit_is_enforced(client):
    _customer_id, full_key = _seed_license_key(tag="limit", device_limit=1)

    first = _activate(client, license_key=full_key, fingerprint="dev-a", idem="act-lim-000001")
    assert first.status_code == 200 and first.json()["created"] is True

    # A second, different install against a device_limit=1 key is denied.
    second = _activate(client, license_key=full_key, fingerprint="dev-b", idem="act-lim-000002")
    assert second.status_code == 403
    assert second.json()["error"]["code"] == "POLICY_DENIED"

    from selahcue_api.apps.devices.models import Device

    assert Device.objects.count() == 1


@pytest.mark.django_db
def test_missing_required_fields_are_validation_failed(client):
    _customer_id, full_key = _seed_license_key(tag="validation")

    # No device_fingerprint.
    r = client.post(
        "/v1/activations",
        data=json.dumps({"idempotency_key": "act-val-000001", "license_key": full_key, "platform": "macos"}),
        content_type="application/json",
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"

    # Malformed idempotency key.
    r2 = _activate(client, license_key=full_key, fingerprint="fp", idem="short")
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "VALIDATION_FAILED"

    from selahcue_api.apps.devices.models import Device

    assert Device.objects.count() == 0


@pytest.mark.django_db
def test_activation_is_csrf_exempt():
    from django.test import Client

    csrf_client = Client(enforce_csrf_checks=True)
    _customer_id, full_key = _seed_license_key(tag="csrf")
    response = _activate(csrf_client, license_key=full_key, fingerprint="fp-csrf", idem="act-csrf-0001")
    # Not blocked by CSRF (would be 403 with a CSRF error body); the real activation succeeds.
    assert response.status_code == 200
    assert response.json()["created"] is True


@pytest.mark.django_db
def test_activation_rolls_back_when_audit_write_fails(monkeypatch):
    _customer_id, full_key = _seed_license_key(tag="rollback")

    def fail_audit(*args, **kwargs):
        raise RuntimeError("simulated audit storage failure")

    monkeypatch.setattr("selahcue_api.apps.devices.services.record_audit_event", fail_audit)

    from selahcue_api.apps.devices.services import ActivateDeviceData, activate_device

    with pytest.raises(RuntimeError):
        activate_device(
            ActivateDeviceData(
                idempotency_key="act-rollback-1",
                presented_key=full_key,
                device_fingerprint="fp-rollback",
                platform="macos",
            )
        )

    from selahcue_api.apps.devices.models import Device, DeviceToken
    from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

    assert Device.objects.count() == 0
    assert DeviceToken.objects.count() == 0
    # The ISSUED->ACTIVATED flip is inside the same atomic block, so it rolled back too.
    assert AppLicenseKey.objects.get().status == LicenseKeyStatus.ISSUED


@pytest.mark.django_db
def test_revoked_device_reactivation_is_denied(client):
    # A revoked device re-enrolling must be denied (POLICY_DENIED), never handed a dead token as success.
    _customer_id, full_key = _seed_license_key(tag="revdev")
    first = _activate(client, license_key=full_key, fingerprint="fp-rev-dev", idem="act-revdev-0001")
    assert first.status_code == 200 and first.json()["created"] is True

    from selahcue_api.apps.devices.models import Device, DeviceStatus

    Device.objects.update(status=DeviceStatus.REVOKED)

    # Re-enroll the same install with a new idempotency key.
    again = _activate(client, license_key=full_key, fingerprint="fp-rev-dev", idem="act-revdev-0002")
    assert again.status_code == 403
    assert again.json()["error"]["code"] == "POLICY_DENIED"
