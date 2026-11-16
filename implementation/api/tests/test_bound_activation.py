import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import path
from django.utils import timezone

from test_device_token_remint import _expire_tokens, _seed_license_key
from test_native_account_surface import seed_user
from selahcue_api.apps.devices.models import Device, DeviceToken
from selahcue_api.platform import views as platform_views

pytestmark = pytest.mark.django_db
KEY = "/v1/activations:bound"
SESSION = "/v1/activations:bound-with-session"


@pytest.fixture(autouse=True)
def reset_activation_budgets():
    cache.clear()


def post(client, path, body, token=None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.post(path, data=json.dumps(body), content_type="application/json", **headers)


def body(nonce="1" * 32, *, expected=None, **extra):
    return {
        "operation_version": 1, "mode": "initial" if expected is None else "recover",
        "idempotency_key": nonce, "expected_device_public_id": expected,
        "device_fingerprint": "native-booth", "platform": "macos",
        "app_version": "0.1", "display_name": "Main", **extra,
    }


def another_license(first, name):
    from selahcue_api.apps.license_keys.models import AppLicenseKey
    other, key = _seed_license_key(tag=name, device_limit=1)
    AppLicenseKey.objects.filter(pk=other.pk).update(
        customer=first.customer, expires_at=first.expires_at + timedelta(days=20)
    )
    other.refresh_from_db()
    return other, key


def admin_session(client, org):
    email = f"bound-admin-{org.pk}@fixture.test"
    password = "Synthetic-test-only-248!"
    seed_user(org, email=email, password=password)
    return post(client, "/v1/sessions", {"email": email, "password": password}).json()["session_token"]


def test_bound_enrollment_refuses_wrong_licence_and_keeps_correct_nonce_available(client):
    first, enrollment = _seed_license_key(tag="first", device_limit=1)
    later, wrong = another_license(first, "later")
    made = post(client, KEY, body(license_key=enrollment))
    assert made.status_code == 200
    initial = made.json()
    expected = initial["device"]["device_public_id"]
    recover = body("2" * 32, expected=expected)
    _expire_tokens(first, at=timezone.now() - timedelta(hours=1))
    denied = post(client, KEY, {**recover, "license_key": wrong})
    assert denied.status_code in {403, 404, 409}
    assert not Device.objects.filter(license_key=later).exists()
    assert DeviceToken.objects.count() == 1
    done = post(client, KEY, {**recover, "license_key": enrollment})
    assert done.status_code == 200
    assert done.json()["reminted"] and done.json()["device"]["device_public_id"] == expected
    assert Device.objects.count() == 1


def test_bound_admin_initial_replay_and_recovery_ignore_later_licence(client):
    first, _ = _seed_license_key(tag="admin-first", device_limit=1)
    session = admin_session(client, first.customer)
    initial = post(client, SESSION, body(), session)
    assert initial.status_code == 200
    expected = initial.json()["device"]["device_public_id"]
    later, _ = another_license(first, "admin-later")
    replay = post(client, SESSION, body(), session)
    assert replay.status_code == 200
    assert replay.json()["operation_state"] == "replay"
    assert replay.json()["activation_token"] is None
    assert replay.json()["device"]["device_public_id"] == expected
    _expire_tokens(first, at=timezone.now() - timedelta(hours=1))
    recovery = post(client, SESSION, body("2" * 32, expected=expected), session)
    assert recovery.status_code == 200
    assert recovery.json()["reminted"]
    assert not Device.objects.filter(license_key=later).exists()


def test_bound_routes_refuse_missing_or_unknown_fields_and_cookie_authority(client):
    key, enrollment = _seed_license_key(tag="strict")
    payload = body(license_key=enrollment)
    for change in [
        {"unrecognized": True}, {"operation_version": True}, {"mode": "recover"},
        {"expected_device_public_id": "dev_" + "0" * 32}, {"idempotency_key": "old-key-12345"},
    ]:
        reply = post(client, KEY, {**payload, **change})
        assert reply.status_code == 400
        assert "no-store" in reply["Cache-Control"]
    missing = {k: v for k, v in payload.items() if k != "expected_device_public_id"}
    assert post(client, KEY, missing).status_code == 400
    session = admin_session(client, key.customer)
    cookie_only = Client()
    cookie_only.cookies["selahcue_account_session"] = session
    assert post(cookie_only, SESSION, body()).status_code == 401
    assert not Device.objects.exists()


def test_completed_nonce_never_substitutes_a_live_replacement_token(client):
    from selahcue_api.apps.devices.models import DeviceActivationOperation
    first, enrollment = _seed_license_key(tag="deletion", device_limit=1)
    initial = post(client, KEY, body(license_key=enrollment)).json()
    target = initial["device"]["device_public_id"]
    receipt = DeviceActivationOperation.objects.get()
    original = receipt.result_token_id
    DeviceToken.objects.get(pk=original).delete()
    receipt.refresh_from_db()
    assert receipt.result_token_id is None
    assert receipt.issued_token_pk == original
    expired = post(client, KEY, body(license_key=enrollment))
    assert expired.status_code == 409
    assert expired.json()["error"]["code"] == "ACTIVATION_OPERATION_COMPLETED"
    recover = post(client, KEY, body("2" * 32, expected=target, license_key=enrollment))
    assert recover.status_code == 200 and recover.json()["reminted"]
    assert post(client, KEY, body(license_key=enrollment)).status_code == 409
    assert post(client, KEY, body("2" * 32, expected=target, license_key=enrollment)).json()["activation_token"] is None
    assert DeviceToken.objects.count() == Device.objects.count() == 1


@pytest.mark.parametrize("mismatch", ["id", "fingerprint", "platform", "mode", "path", "org"])
def test_completed_operation_cannot_be_retargeted(client, mismatch):
    from selahcue_api.apps.devices.models import DeviceActivationOperation
    first, key = _seed_license_key(tag="target")
    other, wrong = _seed_license_key(tag="foreign")
    initial = post(client, KEY, body(license_key=key)).json()
    expected = initial["device"]["device_public_id"]
    _expire_tokens(first, at=timezone.now() - timedelta(hours=1))
    original = body("2" * 32, expected=expected, license_key=key)
    assert post(client, KEY, original).json()["reminted"]
    changed = dict(original)
    session = None
    route = KEY
    if mismatch == "id":
        changed["expected_device_public_id"] = "dev_" + "3" * 32
    elif mismatch == "fingerprint":
        changed["device_fingerprint"] = "different"
    elif mismatch == "platform":
        changed["platform"] = "windows"
    elif mismatch == "mode":
        changed.update(mode="initial", expected_device_public_id=None)
    elif mismatch == "path":
        route, session = SESSION, admin_session(client, first.customer)
        changed.pop("license_key")
    else:
        changed["license_key"] = wrong
    refused = post(client, route, changed, session)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "ACTIVATION_OPERATION_CONFLICT"
    assert post(client, KEY, original).json()["operation_state"] == "replay"
    assert DeviceActivationOperation.objects.count() == 2
    assert DeviceToken.objects.count() == 2
    assert not Device.objects.filter(license_key=other).exists()


@pytest.mark.parametrize("inactive", ["device", "license", "foreign_org"])
def test_bound_recovery_refuses_before_allocating_an_available_seat(client, inactive):
    from selahcue_api.apps.devices.models import DeviceActivationOperation, DeviceStatus
    from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

    first, key = _seed_license_key(tag="first-scope")
    expected = post(client, KEY, body(license_key=key)).json()["device"]["device_public_id"]
    if inactive == "foreign_org":
        another, _ = _seed_license_key(tag="other-scope")
        org = another.customer
    else:
        another, _ = another_license(first, "alternate-scope")
        org = first.customer
    if inactive == "device":
        Device.objects.update(status=DeviceStatus.REVOKED)
    elif inactive == "license":
        AppLicenseKey.objects.filter(pk=first.pk).update(status=LicenseKeyStatus.REVOKED)
    session = admin_session(client, org)
    denied = post(client, SESSION, body("2" * 32, expected=expected), session)
    assert denied.status_code in {403, 409}
    assert not Device.objects.filter(license_key=another).exists()
    assert DeviceActivationOperation.objects.count() == DeviceToken.objects.count() == 1


def test_legacy_and_bound_route_share_the_enrollment_budget(client, settings):
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1, 60)
    assert post(client, "/v1/activations", body(license_key="invalid")).status_code == 404
    assert post(client, KEY, body(license_key="invalid")).status_code == 429
    assert not Device.objects.exists()


# Bare old URLconf models a deployment with current legacy handlers and no strict route.
urlpatterns = [
    path("v1/activations", platform_views.activate_device),
    path("v1/activations:with-session", platform_views.activate_device_with_session),
]


@override_settings(ROOT_URLCONF=__name__)
def test_old_server_bound_route_returns_404_without_calling_legacy_activation(client):
    first, key = _seed_license_key(tag="old-server")
    assert post(client, KEY, body(license_key=key)).status_code == 404
    assert not Device.objects.exists()
    assert not DeviceToken.objects.exists()
    # Negative control: the old URL ignores the strict wire expectation and allocates.
    unsafe = body("2" * 32, expected="dev_" + "7" * 32, license_key=key)
    assert post(client, "/v1/activations", unsafe).status_code == 200
    assert Device.objects.filter(license_key=first).count() == DeviceToken.objects.count() == 1


def test_completed_nonce_stays_unusable_when_its_original_token_is_revoked(client):
    from selahcue_api.apps.devices.models import DeviceActivationOperation, DeviceTokenStatus

    first, key = _seed_license_key(tag="original-revoked", device_limit=1)
    initial = post(client, KEY, body(license_key=key)).json()
    receipt = DeviceActivationOperation.objects.get()
    DeviceToken.objects.filter(pk=receipt.result_token_id).update(status=DeviceTokenStatus.REVOKED)
    old = post(client, KEY, body(license_key=key))
    assert old.status_code == 409
    assert old.json()["error"]["code"] == "ACTIVATION_OPERATION_COMPLETED"
    assert DeviceActivationOperation.objects.count() == DeviceToken.objects.count() == 1
    new = post(client, KEY, body("2" * 32, expected=initial["device"]["device_public_id"], license_key=key))
    assert new.status_code == 200 and new.json()["reminted"]
    assert Device.objects.filter(license_key=first).count() == 1


def test_bound_recovery_does_not_accept_a_device_bearer_as_account_authority(client):
    first, key = _seed_license_key(tag="bound-device-authority")
    original = post(client, KEY, body(license_key=key)).json()
    denied = post(client, SESSION, body("2" * 32, expected=original["device"]["device_public_id"]),
                  original["activation_token"])
    assert denied.status_code == 401
    assert DeviceToken.objects.filter(device__license_key=first).count() == 1


def test_unusable_initial_receipt_returns_recorded_identity_without_a_token(client):
    from selahcue_api.apps.devices.models import DeviceActivationOperation

    first, key = _seed_license_key(tag="complete-proof", device_limit=1)
    initial = post(client, KEY, body(license_key=key)).json()
    target = initial["device"]["device_public_id"]
    DeviceToken.objects.all().delete()
    later, other_key = another_license(first, "complete-proof-other")

    rejected = post(client, KEY, body(license_key=other_key))
    assert rejected.status_code == 409
    assert "completed_activation" not in rejected.json()
    completed = post(client, KEY, body(license_key=key))
    assert completed.status_code == 409
    proof = completed.json()["completed_activation"]
    assert proof == {"idempotency_key": "1" * 32, "device_public_id": target, "platform": "macos"}
    assert completed.json().get("activation_token") is None
    assert not DeviceToken.objects.exists()
    assert DeviceActivationOperation.objects.count() == 1
    reminted = post(client, KEY, body("2" * 32, expected=target, license_key=key))
    assert reminted.status_code == 200 and reminted.json()["reminted"]
    assert not Device.objects.filter(license_key=later).exists()
    assert Device.objects.count() == DeviceToken.objects.count() == 1


def test_member_and_no_active_license_refusals_are_versioned_and_leave_no_activation(client):
    from selahcue_api.apps.accounts.models import CustomerRole
    from selahcue_api.apps.devices.models import DeviceActivationOperation
    from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

    key, _ = _seed_license_key(tag="first-refusal")
    email = "member-for-native-first-refusal@fixture.test"
    password = "Synthetic-member-fixture-248!"
    seed_user(key.customer, email=email, password=password, role=CustomerRole.MEMBER)
    member = post(client, "/v1/sessions", {"email": email, "password": password}).json()["session_token"]
    admin = admin_session(client, key.customer)
    AppLicenseKey.objects.filter(pk=key.pk).update(status=LicenseKeyStatus.REVOKED)
    for credential, status, code in [(member, 403, "PERMISSION_DENIED"), (admin, 404, "NOT_FOUND")]:
        refusal = post(client, SESSION, body(), credential)
        assert refusal.status_code == status
        data = refusal.json()
        assert data["operation"] == "activation_bound_with_session"
        assert data["surface"] == "desktop"
        assert data["operation_version"] == 1
        assert data["error"]["code"] == code
        assert "completed_activation" not in data
    assert not DeviceActivationOperation.objects.exists()
    assert not Device.objects.exists()
    assert not DeviceToken.objects.exists()
