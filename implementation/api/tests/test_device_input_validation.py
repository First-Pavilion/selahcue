"""17tnw2b1wqd: real activation transports must refuse malformed input before writes."""

import json

import pytest
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from licensing_test_support import issue_key, seat_plan_code, seed_org
from selahcue_api.apps.accounts.models import CustomerRole, CustomerUser, CustomerUserStatus
from selahcue_api.apps.accounts.services import LoginData, _fingerprint, login
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import Device, DeviceToken
from selahcue_api.apps.devices.services import ActivateDeviceData, activate_device
from selahcue_api.graphql.errors import SafeAPIError

pytestmark = pytest.mark.django_db


@pytest.fixture
def activation(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.SELAHCUE_THROTTLE_ACTIVATION = (10000, 60)
    cache.clear()
    org = seed_org("input-validation")
    key = issue_key(org, tag="input-validation", plan_code=seat_plan_code(3))
    email = "admin@activation.example"
    CustomerUser.objects.create(
        customer=org, email=email, email_fingerprint=_fingerprint(email),
        password_hash=make_password("activation-password"), status=CustomerUserStatus.ACTIVE,
        role=CustomerRole.ADMIN, email_verified_at=timezone.now(),
        created_by_actor_id="fixture", idempotency_key="input-admin-0001",
    )
    session = login(LoginData(email=email, password="activation-password")).session_token
    return {
        "idempotency_key": "activation-input-0001",
        "license_key": key.full_key,
        "device_fingerprint": "booth-install",
        "platform": "macos",
        "app_version": "1.0.0",
        "display_name": "Sound booth",
    }, session


def send_activation(activation, route, changes):
    payload, session = activation
    payload = {**payload, **changes}
    headers = {}
    if route == "account":
        payload.pop("license_key")
        headers["HTTP_AUTHORIZATION"] = f"Bearer {session}"
    return Client(enforce_csrf_checks=True, raise_request_exception=False).post(
        "/v1/activations:with-session" if route == "account" else "/v1/activations",
        data=json.dumps(payload), content_type="application/json", **headers,
    )


def assert_refused(response, audit_count):
    assert response.status_code == 400, response.content[:300]
    assert response["Content-Type"].startswith("application/json")
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert Device.objects.count() == 0
    assert DeviceToken.objects.count() == 0
    assert AuditEvent.objects.count() == audit_count


@pytest.mark.parametrize("route", ["key", "account"])
@pytest.mark.parametrize("field", ["device_fingerprint", "platform", "app_version", "display_name", "idempotency_key"])
@pytest.mark.parametrize("bad", ["bad\x00value", "bad\x1bvalue", "bad\x9bvalue"])
def test_control_characters_are_refused_before_activation(activation, route, field, bad):
    count = AuditEvent.objects.count()
    assert_refused(send_activation(activation, route, {field: bad}), count)


@pytest.mark.parametrize("route", ["key", "account"])
@pytest.mark.parametrize("field", ["device_fingerprint", "platform", "app_version", "display_name", "idempotency_key"])
@pytest.mark.parametrize("bad", [{"nested": "value"}, ["value"], 12, True, None])
def test_non_string_metadata_is_not_coerced(activation, route, field, bad):
    count = AuditEvent.objects.count()
    assert_refused(send_activation(activation, route, {field: bad}), count)


@pytest.mark.parametrize("route", ["key", "account"])
def test_unknown_platform_is_refused(activation, route):
    count = AuditEvent.objects.count()
    assert_refused(send_activation(activation, route, {"platform": "amiga"}), count)


@pytest.mark.parametrize("route", ["key", "account"])
@pytest.mark.parametrize("platform", ["macos", "windows", "linux"])
def test_supported_platforms_still_activate(activation, route, platform):
    response = send_activation(activation, route, {"platform": platform})
    assert response.status_code == 200, response.content
    assert response.json()["device"]["platform"] == platform
    assert Device.objects.count() == DeviceToken.objects.count() == 1


@pytest.mark.parametrize("route", ["key", "account"])
@pytest.mark.parametrize("body", [b"[" * 1200000, b" " * 2700000], ids=["nested", "oversized"])
def test_nested_and_oversized_bodies_return_json_refusal(activation, route, body):
    count = AuditEvent.objects.count()
    response = Client(raise_request_exception=False).post(
        "/v1/activations:with-session" if route == "account" else "/v1/activations",
        data=body, content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {activation[1]}",
    )
    assert_refused(response, count)


def test_shared_service_refuses_metadata_controls_without_transport_coercion(activation):
    payload, _ = activation
    payload = {**payload, "presented_key": payload["license_key"], "display_name": "booth\x00name"}
    payload.pop("license_key")
    with pytest.raises(SafeAPIError) as refusal:
        activate_device(ActivateDeviceData(**payload))
    assert refusal.value.code.value == "VALIDATION_FAILED"
    assert not Device.objects.exists()


@pytest.mark.parametrize("bad", [{"key": "value"}, ["key"], 12, None, "key\x00value"])
def test_enrollment_credential_is_not_coerced(activation, bad):
    count = AuditEvent.objects.count()
    assert_refused(send_activation(activation, "key", {"license_key": bad}), count)
