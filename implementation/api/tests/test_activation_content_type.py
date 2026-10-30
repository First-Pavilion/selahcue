"""17tnw2b1wqb: browser-simple requests must not spend a native route's budget."""

import json

import pytest
from django.core.cache import cache
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from licensing_test_support import issue_key, seat_plan_code, seed_org
from selahcue_api.apps.devices.models import Device, DeviceToken

pytestmark = pytest.mark.django_db

SIMPLE_TYPES = ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=test"]


@pytest.fixture
def activation(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1, 60)
    settings.SELAHCUE_THROTTLE_DEVICE_READ = (1, 60)
    cache.clear()
    org = seed_org("content-type")
    result = issue_key(org, tag="content-type", plan_code=seat_plan_code(3))
    return {"license_key": result.full_key, "idempotency_key": "content-type-activation-0001",
            "device_fingerprint": "content-type-install", "platform": "macos"}


def post(client, path, payload, content_type="application/json", **extra):
    return client.post(path, data=json.dumps(payload), content_type=content_type, **extra)


@pytest.mark.parametrize("content_type", SIMPLE_TYPES)
def test_simple_activation_refusals_cannot_spend_the_shared_egress_budget(activation, content_type):
    client = Client(enforce_csrf_checks=True)
    with CaptureQueriesContext(connection) as queries:
        refusals = [post(client, "/v1/activations", activation, content_type) for _ in range(2)]
    assert [r.status_code for r in refusals] == [400, 400]
    assert [r.json()["error"]["code"] for r in refusals] == ["VALIDATION_FAILED"] * 2
    assert len(queries) == 0
    assert Device.objects.count() == DeviceToken.objects.count() == 0
    valid = post(client, "/v1/activations", activation)
    assert valid.status_code == 200, valid.content
    assert valid.json()["created"] is True
    # Positive control: this is the actual one-request throttle, not a bypass.
    assert post(client, "/v1/activations", activation).status_code == 429


@pytest.mark.parametrize("content_type", SIMPLE_TYPES)
def test_simple_refresh_body_refusals_leave_the_device_read_budget_available(activation, content_type):
    client = Client(enforce_csrf_checks=True)
    token = post(client, "/v1/activations", activation).json()["activation_token"]
    body = {"device_token": token}
    with CaptureQueriesContext(connection) as queries:
        refusals = [post(client, "/v1/license:refresh", body, content_type) for _ in range(2)]
    assert [r.status_code for r in refusals] == [400, 400]
    assert len(queries) == 0
    assert post(client, "/v1/license:refresh", body).status_code == 200
    assert post(client, "/v1/license:refresh", body).status_code == 429


@pytest.mark.parametrize("content_type", ["", "text/plain", "application/json"])
def test_refresh_keeps_the_header_authenticated_bodyless_form(activation, content_type):
    client = Client(enforce_csrf_checks=True)
    token = post(client, "/v1/activations", activation).json()["activation_token"]
    response = client.post("/v1/license:refresh", data=b"", content_type=content_type,
                           HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200, response.content
    assert "valid_now" in response.json()["license"]


def test_wrong_method_still_returns_405_without_spending_activation_budget(activation):
    client = Client(enforce_csrf_checks=True)
    assert client.get("/v1/activations").status_code == 405
    assert post(client, "/v1/activations", activation).status_code == 200


def test_refresh_header_exception_still_authenticates_header_and_ignores_body_token(activation):
    client = Client(enforce_csrf_checks=True)
    token = post(client, "/v1/activations", activation).json()["activation_token"]
    response = post(client, "/v1/license:refresh", {"device_token": token}, "text/plain",
                    HTTP_AUTHORIZATION="Bearer invalid-token")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
