import pytest as _pytest
pytestmark = _pytest.mark.django_db

import json

import pytest
from django.test import RequestFactory

SESSION = "/v1/stt/session"
QUOTA = "/v1/quota"

@pytest.mark.parametrize(("path", "method", "allow"), [
    (SESSION, "GET", "POST"), (SESSION, "HEAD", "POST"), (SESSION, "OPTIONS", "POST"),
    (QUOTA, "POST", "GET"), (QUOTA, "HEAD", "GET"), (QUOTA, "OPTIONS", "GET"),
])
def test_method_refusals_are_safe(client, path, method, allow):
    reply = client.generic(method, path)
    assert reply.status_code == 405
    assert reply["Allow"] == allow
    assert reply["Cache-Control"] == "no-store"
    if method != "HEAD":
        assert reply.json()["error"] == {
            "code": "VALIDATION_FAILED", "message": "Request method not supported.",
        }


def test_quota_requires_bearer_even_with_query_token(client):
    reply = client.get(QUOTA + "?device_token=synthetic")
    assert reply.status_code == 401
    assert reply["Cache-Control"] == "no-store"


@pytest.mark.parametrize("change", [
    {"action": "renew"}, {"socket": "existing"}, {"retry": False},
    {"consent_version": "\ud800"}, {"idempotency_key": True}, {"unknown": None},
])
def test_invalid_session_shape_refused_before_authentication(client, change):
    body = {
        "idempotency_key": "12345678-1234-1234-1234-000000000001",
        "action": "start", "socket": "new", "consent_version": "stt-direct-audio-v1",
        "policy_version": "stt-direct-v1",
    }
    reply = client.post(SESSION, json.dumps(body | change), content_type="application/json")
    assert reply.status_code == 400
    assert reply.json()["error"]["code"] == "VALIDATION_FAILED"
    assert reply["Cache-Control"] == "no-store"


@pytest.mark.parametrize("meta", [
    {}, {"CONTENT_LENGTH": "-1"}, {"CONTENT_LENGTH": "8193"},
    {"CONTENT_LENGTH": "1,1"}, {"CONTENT_LENGTH": "1", "HTTP_TRANSFER_ENCODING": "chunked"},
])
def test_unsupported_framing_does_not_read_or_authenticate(meta):
    from django.urls import resolve

    request = RequestFactory().post(SESSION, b"X", content_type="application/json")
    request.META.pop("CONTENT_LENGTH", None)
    request.META.update(meta)

    def forbidden(*args):
        pytest.fail("Unsupported framing attempted to read request body")

    request.read = forbidden
    reply = resolve(SESSION).func(request)
    assert reply.status_code == 400
    assert reply["Cache-Control"] == "no-store"
