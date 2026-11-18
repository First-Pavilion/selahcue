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


def established_v2_recovery(client, *, tag):
    """A real v1 installation and a separate, explicit ADMIN recovery intent."""
    from uuid import uuid4

    key, _ = _seed_license_key(tag=tag, device_limit=1)
    session = admin_session(client, key.customer)
    response = post(client, SESSION, body(uuid4().hex), session)
    assert response.status_code == 200
    initial = response.json()
    request = body(uuid4().hex, expected=initial["device"]["device_public_id"], operation_version=2)
    return key, session, initial, request


@pytest.mark.django_db(transaction=True)
def test_bound_v2_admin_recovers_undisclosed_live_replacement(client):
    from selahcue_api.apps.audit.models import AuditEvent
    from selahcue_api.apps.devices.models import DeviceActivationOperation, DeviceTokenStatus
    from test_license_revoke_extend import _extend

    key, session, initial, request = established_v2_recovery(client, tag="v2-lost-rotation")
    device_before = list(Device.objects.values())
    original = initial["activation_token"]
    original_pk = DeviceToken.objects.get().pk
    _extend(key, key.expires_at + timedelta(days=30), idem="v2-lost-rotation-extension")
    key.refresh_from_db()
    assert DeviceToken.objects.get(pk=original_pk).staff_extension_generation < key.staff_extension_generation
    rotated = post(client, "/v1/license:refresh", {"token_rotation": "staff-extension-v1"}, original)
    assert rotated.status_code == 200
    assert rotated.json()["activation_token"]
    # Simulate loss of custody: keep only the database identity, never the response credential.
    del rotated
    undisclosed = DeviceToken.objects.get(status=DeviceTokenStatus.ACTIVE)
    assert undisclosed.pk != original_pk
    assert undisclosed.staff_extension_generation == key.staff_extension_generation
    assert post(client, "/v1/license:refresh", {}, original).status_code == 401

    recovered = post(client, SESSION, request, session)
    assert recovered.status_code == 200
    result = recovered.json()
    assert result["operation_version"] == 2
    assert result["operation_state"] == "completed"
    assert result["idempotency_key"] == request["idempotency_key"]
    assert result["created"] is False and result["reminted"] is True
    assert result["device"]["device_public_id"] == initial["device"]["device_public_id"]
    assert "no-store" in recovered["Cache-Control"]
    replacement = result["activation_token"]
    assert replacement and replacement != original
    assert list(Device.objects.values()) == device_before
    assert DeviceToken.objects.count() == 3
    live = DeviceToken.objects.get(status=DeviceTokenStatus.ACTIVE)
    assert live.pk not in {original_pk, undisclosed.pk}
    assert live.staff_extension_generation == key.staff_extension_generation
    assert DeviceToken.objects.filter(pk__in=[original_pk, undisclosed.pk], status=DeviceTokenStatus.REVOKED).count() == 2
    receipt = DeviceActivationOperation.objects.get(operation_key=request["idempotency_key"])
    assert receipt.outcome == "REMINTED"
    assert receipt.auth_path == "account_session"
    assert receipt.result_token_id == receipt.issued_token_pk == live.pk
    assert receipt.device_id == live.device_id
    assert DeviceActivationOperation.objects.count() == 2

    replay = post(client, SESSION, request, session)
    assert replay.status_code == 200
    assert replay.json()["operation_version"] == 2
    assert replay.json()["operation_state"] == "replay"
    assert replay.json()["activation_token"] is None
    assert "no-store" in replay["Cache-Control"]
    assert DeviceToken.objects.count() == 3
    assert DeviceActivationOperation.objects.count() == 2
    usable = post(client, "/v1/license:refresh", {"token_rotation": "staff-extension-v1"}, replacement)
    assert usable.status_code == 200
    assert "activation_token" not in usable.json()
    assert post(client, "/v1/license:refresh", {}, original).status_code == 401
    audits = json.dumps(list(AuditEvent.objects.values("before", "after", "reason")))
    assert original not in audits and replacement not in audits


@pytest.mark.parametrize("case", [
    "enrollment", "initial", "member", "member_invalid_input", "foreign_identity",
    "fingerprint", "platform", "device_bearer",
])
def test_bound_v2_refuses_enrollment_initial_member_and_foreign_identity(client, case):
    from uuid import uuid4
    from selahcue_api.apps.accounts.models import CustomerRole
    from selahcue_api.apps.devices.models import DeviceActivationOperation

    key, session, initial, request = established_v2_recovery(client, tag=f"v2-deny-{case}")
    route, credential = SESSION, session
    status, code = 409, "ACTIVATION_OPERATION_CONFLICT"
    if case == "enrollment":
        _, enrollment = another_license(key, "v2-deny-enrollment-key")
        route, credential = KEY, None
        request["license_key"] = enrollment
        status, code = 400, "VALIDATION_FAILED"
    elif case == "initial":
        request.update(mode="initial", expected_device_public_id=None)
        status, code = 400, "VALIDATION_FAILED"
    elif case in {"member", "member_invalid_input"}:
        email, password = f"v2-member-{key.customer_id}@fixture.test", "Synthetic-test-only-248!"
        seed_user(key.customer, email=email, password=password, role=CustomerRole.MEMBER)
        credential = post(client, "/v1/sessions", {"email": email, "password": password}).json()["session_token"]
        if case == "member_invalid_input":
            request["operation_version"] = "untrusted-version"
            request["expected_device_public_id"] = "invalid"
        status, code = 403, "PERMISSION_DENIED"
    elif case == "foreign_identity":
        other, _, foreign, _ = established_v2_recovery(client, tag="v2-deny-foreign-target")
        assert other.customer_id != key.customer_id
        request["expected_device_public_id"] = foreign["device"]["device_public_id"]
    elif case == "fingerprint":
        request["device_fingerprint"] = "different-installation"
    elif case == "platform":
        request["platform"] = "windows"
    else:
        credential = initial["activation_token"]
        status, code = 401, "UNAUTHENTICATED"
    request["idempotency_key"] = uuid4().hex
    before = [list(model.objects.order_by("pk").values()) for model in (Device, DeviceToken, DeviceActivationOperation)]
    denied = post(client, route, request, credential)
    assert denied.status_code == status
    assert denied.json()["error"]["code"] == code
    assert "no-store" in denied["Cache-Control"]
    assert denied.json().get("activation_token") is None
    assert "completed_activation" not in denied.json()
    if case in {"foreign_identity", "fingerprint", "platform"}:
        assert denied.json()["operation_version"] == 2
    if case == "member_invalid_input":
        assert denied.json()["operation_version"] == 1  # authority rejects before normalization
    assert [list(model.objects.order_by("pk").values()) for model in (Device, DeviceToken, DeviceActivationOperation)] == before


@pytest.mark.parametrize("first_version,next_version", [(1, 2), (2, 1)])
def test_nonce_cannot_change_protocol_version(client, first_version, next_version):
    from selahcue_api.apps.devices.models import DeviceActivationOperation

    _, session, _, request = established_v2_recovery(client, tag=f"v2-version-{first_version}")
    request["operation_version"] = first_version
    completed = post(client, SESSION, request, session)
    assert completed.status_code == 200
    before = [list(model.objects.order_by("pk").values()) for model in (DeviceToken, DeviceActivationOperation)]
    changed = post(client, SESSION, {**request, "operation_version": next_version}, session)
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "ACTIVATION_OPERATION_CONFLICT"
    assert changed.json()["operation_version"] == next_version
    assert [list(model.objects.order_by("pk").values()) for model in (DeviceToken, DeviceActivationOperation)] == before
    replay = post(client, SESSION, request, session)
    assert replay.status_code == 200
    assert replay.json()["operation_version"] == first_version
    assert replay.json()["activation_token"] is None


@pytest.mark.parametrize("first_version", [1, 2], ids=["v1", "v2"])
@pytest.mark.parametrize("delete_original", [False, True], ids=["revoked", "deleted"])
def test_completed_receipt_never_switches_to_new_result(client, delete_original, first_version):
    from uuid import uuid4
    from selahcue_api.apps.devices.models import DeviceActivationOperation, DeviceTokenStatus

    _, session, initial, request = established_v2_recovery(client, tag=f"v2-receipt-{delete_original}")
    request["operation_version"] = first_version
    first = post(client, SESSION, request, session)
    assert first.status_code == 200
    receipt = DeviceActivationOperation.objects.get(operation_key=request["idempotency_key"])
    original_pk = receipt.result_token_id
    immutable = (receipt.issued_token_pk, receipt.request_digest, receipt.completed_at, receipt.device_id)
    next_request = {**request, "idempotency_key": uuid4().hex, "operation_version": 2}
    second = post(client, SESSION, next_request, session)
    assert second.status_code == 200
    live = DeviceToken.objects.get(status=DeviceTokenStatus.ACTIVE)
    assert live.pk != original_pk
    assert DeviceToken.objects.get(pk=original_pk).status == DeviceTokenStatus.REVOKED
    if delete_original:
        DeviceToken.objects.filter(pk=original_pk).delete()
    token_count = DeviceToken.objects.count()
    replay = post(client, SESSION, request, session)
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "ACTIVATION_OPERATION_COMPLETED"
    assert replay.json()["operation_version"] == first_version
    assert replay.json()["completed_activation"] == {
        "idempotency_key": request["idempotency_key"],
        "device_public_id": initial["device"]["device_public_id"], "platform": "macos",
    }
    assert replay.json().get("activation_token") is None
    assert "no-store" in replay["Cache-Control"]
    receipt.refresh_from_db()
    assert receipt.result_token_id == (None if delete_original else original_pk)
    assert (receipt.issued_token_pk, receipt.request_digest, receipt.completed_at, receipt.device_id) == immutable
    assert DeviceToken.objects.count() == token_count
    assert DeviceToken.objects.get(status=DeviceTokenStatus.ACTIVE).pk == live.pk
    assert DeviceActivationOperation.objects.count() == 3
    assert Device.objects.count() == 1
    original_bearer = first.json()["activation_token"] if first_version == 2 else initial["activation_token"]
    assert post(client, "/v1/license:refresh", {}, original_bearer).status_code == 401
    assert post(client, "/v1/license:refresh", {}, second.json()["activation_token"]).status_code == 200


@pytest.mark.parametrize("route", [KEY, SESSION])
def test_bound_v1_still_refuses_replace_token_field(client, route):
    key, enrollment = _seed_license_key(tag="v1-no-replace-field")
    session = admin_session(client, key.customer) if route == SESSION else None
    request = body(replace_token=True)
    if route == KEY:
        request["license_key"] = enrollment
    response = post(client, route, request, session)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert response.json()["operation_version"] == 1
    assert not Device.objects.exists()
    assert not DeviceToken.objects.exists()


@pytest.mark.parametrize("change", [
    {"replace_token": True}, {"operation_version": True}, {"operation_version": 2.0},
    {"operation_version": "2"}, {"operation_version": 3},
    {"operation_version": {"untrusted": 2}}, {"idempotency_key": "not-a-bound-nonce"},
    {"expected_device_public_id": None},
])
def test_bound_v2_keeps_strict_fields_and_version_types(client, change):
    from selahcue_api.apps.devices.models import DeviceActivationOperation

    _, session, _, request = established_v2_recovery(client, tag="v2-strict")
    before = [list(model.objects.order_by("pk").values()) for model in (Device, DeviceToken, DeviceActivationOperation)]
    denied = post(client, SESSION, {**request, **change}, session)
    assert denied.status_code == 400
    assert denied.json()["error"]["code"] == "VALIDATION_FAILED"
    assert "no-store" in denied["Cache-Control"]
    if "operation_version" in change:
        assert denied.json()["operation_version"] == 1
    missing = {name: value for name, value in request.items() if name != "display_name"}
    assert post(client, SESSION, missing, session).status_code == 400
    assert [list(model.objects.order_by("pk").values()) for model in (Device, DeviceToken, DeviceActivationOperation)] == before


@pytest.mark.parametrize("policy", ["revoked_device", "revoked_license", "suspended_license", "over_allowance"])
def test_bound_v2_policy_denial_leaves_existing_credential_and_receipts_unchanged(client, policy):
    from selahcue_api.apps.devices.models import DeviceActivationOperation, DeviceStatus
    from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

    key, session, _, request = established_v2_recovery(client, tag=f"v2-policy-{policy}")
    if policy == "revoked_device":
        Device.objects.filter(license_key=key).update(status=DeviceStatus.REVOKED)
    elif policy == "over_allowance":
        AppLicenseKey.objects.filter(pk=key.pk).update(device_limit=0)
    else:
        status = LicenseKeyStatus.REVOKED if policy == "revoked_license" else LicenseKeyStatus.SUSPENDED
        key.refresh_from_db()
        AppLicenseKey.objects.filter(pk=key.pk).update(
            status=status, prior_status=key.status if status == LicenseKeyStatus.SUSPENDED else "",
        )
    models = (Device, DeviceToken, DeviceActivationOperation, AppLicenseKey)
    before = [list(model.objects.order_by("pk").values()) for model in models]
    denied = post(client, SESSION, request, session)
    assert denied.status_code == 403
    assert denied.json()["operation_version"] == 2
    assert denied.json().get("activation_token") is None
    assert "completed_activation" not in denied.json()
    assert [list(model.objects.order_by("pk").values()) for model in models] == before
