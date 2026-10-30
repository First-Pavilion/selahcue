"""Actual raw JSON decoding on both GraphQL routes, before any authentication."""
import json

import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db
SURFACES = [
    pytest.param("/graphql/admin", "{ adminHealth { surface ready } }", id="admin"),
    pytest.param("/graphql/account", "{ accountViewer { surface actorId orgId } }", id="account"),
]
SAFE_INVALID = {"errors": [{"message": "The request is invalid.", "extensions": {"code": "VALIDATION_FAILED"}}]}


@pytest.fixture
def browser(settings):
    client = Client(enforce_csrf_checks=True, raise_request_exception=False)
    bootstrap = client.get("/graphql/csrf")
    assert bootstrap.status_code == 200
    token = bootstrap.cookies[settings.CSRF_COOKIE_NAME].value
    # CSRF is not an identity credential; no bearer/session or trusted actor headers are set.
    return client, token


def _post(browser, path, body, **headers):
    client, token = browser
    return client.post(path, data=body, content_type="application/json", HTTP_X_CSRFTOKEN=token, **headers)


def _assert_safe_invalid(response):
    assert response.status_code == 400
    assert response["Content-Type"].startswith("application/json")
    assert response.json() == SAFE_INVALID


@pytest.mark.parametrize("path,query", SURFACES)
@pytest.mark.parametrize("shape", ["array", "object"])
def test_unauthenticated_deep_raw_json_is_a_safe_validation_response(browser, settings, path, query, shape):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 2_000_000
    depth = 200_000
    if shape == "array":
        body = b"[" * depth + b'"credential-sentinel-do-not-echo"' + b"]" * depth
    else:
        body = b'{"n":' * depth + b'"credential-sentinel-do-not-echo"' + b"}" * depth
    assert len(body) < settings.DATA_UPLOAD_MAX_MEMORY_SIZE  # Decoder recursion, not size admission.
    _assert_safe_invalid(_post(browser, path, body))


@pytest.mark.parametrize("path,query", SURFACES)
@pytest.mark.parametrize("offset", [-1, 0, 1], ids=["below", "at", "above"])
def test_existing_json_body_size_boundary_is_preserved(browser, settings, path, query, offset):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 256
    base = json.dumps({"query": query}).encode()
    body = base + b" " * (256 + offset - len(base))
    response = _post(browser, path, body)
    if offset > 0:
        _assert_safe_invalid(response)
    else:
        assert response.status_code == 200
        assert response.json()["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("path,query", SURFACES)
def test_raw_invalid_utf8_uses_the_safe_json_envelope(browser, path, query):
    _assert_safe_invalid(_post(browser, path, b"\xffcredential-sentinel-do-not-echo"))


@pytest.mark.parametrize("path,query", SURFACES)
def test_existing_malformed_json_contract_remains(browser, path, query):
    _assert_safe_invalid(_post(browser, path, b"{not-json"))


@pytest.mark.parametrize("path,query", SURFACES)
def test_ordinary_unauthenticated_json_still_reaches_authentication(browser, path, query):
    response = _post(browser, path, json.dumps({"query": query}).encode())
    assert response.status_code == 200
    assert response.json()["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("path,query", SURFACES)
@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True)
def test_normal_authorized_json_still_succeeds(browser, path, query):
    if path.endswith("admin"):
        headers = {"HTTP_X_SELAHCUE_ACTOR_KIND": "staff", "HTTP_X_SELAHCUE_ACTOR_ID": "staff_1",
                   "HTTP_X_SELAHCUE_STAFF_PERMISSIONS": "view_platform_health"}
        expected = {"adminHealth": {"surface": "admin", "ready": True}}
    else:
        headers = {"HTTP_X_SELAHCUE_ACTOR_KIND": "customer", "HTTP_X_SELAHCUE_ACTOR_ID": "customer_1",
                   "HTTP_X_SELAHCUE_ORG_ID": "org_1"}
        expected = {"accountViewer": {"surface": "account", "actorId": "customer_1", "orgId": "org_1"}}
    response = _post(browser, path, json.dumps({"query": query}).encode(), **headers)
    assert response.status_code == 200
    assert response.json() == {"data": expected}


@pytest.mark.parametrize("path,query", SURFACES)
@pytest.mark.parametrize("kind", ["missing-token", "cross-origin"])
def test_csrf_still_refuses_before_decoding(browser, path, query, kind):
    client, token = browser
    headers = {} if kind == "missing-token" else {"HTTP_X_CSRFTOKEN": token, "HTTP_ORIGIN": "https://evil.example"}
    response = client.post(path, data=b"[" * 2000, content_type="application/json", **headers)
    assert response.status_code == 403


@pytest.mark.parametrize("path,query", SURFACES)
def test_get_query_contract_is_unchanged(browser, path, query):
    client, _ = browser
    response = client.get(path, {"query": query})
    assert response.status_code == 405
    assert response.json() == SAFE_INVALID


@pytest.mark.parametrize("path,query", SURFACES)
def test_brackets_in_json_string_do_not_become_a_json_depth_policy(browser, path, query):
    response = _post(browser, path, json.dumps({"query": "[" * 2048}).encode())
    assert response.status_code == 200
    assert response.json()["errors"][0]["extensions"]["code"] == "VALIDATION_FAILED"
