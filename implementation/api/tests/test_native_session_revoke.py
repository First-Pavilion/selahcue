"""17tnw2b1wf2: revoke one native account session without ambient authority or device loss."""
import json
import urllib.error
import urllib.request
import uuid

import pytest
from django.core.cache import cache

from selahcue_api import settings as production_settings
from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import CustomerRole
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import DeviceToken, DeviceTokenStatus
from selahcue_api.apps.throttling import guards
from selahcue_api.graphql.context import ACCOUNT_SESSION_COOKIE
from selahcue_api.graphql.errors import SafeAPIError
from test_native_account_surface import (
    ACTIVATE, activation_payload, bearer, native_client, post_json,
    seed_admin_with_license, seed_org, seed_user, session_token,
)

REVOKE = "/v1/sessions:revoke"
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_budgets(settings):
    settings.CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": f"native-revoke-{uuid.uuid4()}",
    }}
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1000, 60)
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1000, 60)
    settings.SELAHCUE_THROTTLE_SESSION_REVOKE = (1000, 60)
    cache.clear()
    guards._reset_denial_log_suppression()
    yield
    guards._reset_denial_log_suppression()


def mint():
    seed_admin_with_license()
    return session_token()


def test_revoke_ends_only_presented_session_and_activated_device_keeps_working():
    token = mint()
    other = session_token()
    client = native_client()
    activated = post_json(client, ACTIVATE, activation_payload(), **bearer(token))
    assert activated.status_code == 200
    device_token = activated.json()["activation_token"]
    response = post_json(client, REVOKE, {}, **bearer(token))
    assert response.status_code == 200
    assert response.json() == {"revoked": True, "surface": "desktop", "operation": "session_revoke"}
    assert not response.cookies
    assert response["Cache-Control"] == "no-store"
    with pytest.raises(SafeAPIError):
        services.authenticate_session(token)
    services.authenticate_session(other)
    assert post_json(client, ACTIVATE, activation_payload(), **bearer(token)).status_code == 401
    assert post_json(client, REVOKE, {}, **bearer(token)).status_code == 401
    refresh = post_json(client, "/v1/license:refresh", {}, **bearer(device_token))
    assert refresh.status_code == 200
    assert refresh.json()["device"]["status"] == "ACTIVE"
    assert DeviceToken.objects.get().status == DeviceTokenStatus.ACTIVE
    event = AuditEvent.objects.get(action="customer_user.logged_out")
    assert event.source_surface == "desktop_v1"
    assert event.after == {"all_sessions": False}
    assert token not in json.dumps(response.json())


@pytest.mark.parametrize("credential,expected", [("cookie", 401), ("body", 400), ("actor_header", 401), ("device", 401)])
def test_only_account_bearer_can_authorize_revoke(credential, expected):
    token = mint()
    client = native_client()
    payload = {}
    extra = {}
    if credential == "cookie":
        client.cookies[ACCOUNT_SESSION_COOKIE] = token
    elif credential == "body":
        payload = {"session_token": token}
    elif credential == "actor_header":
        extra = {"HTTP_X_SELAHCUE_ACTOR_KIND": "customer", "HTTP_X_SELAHCUE_ACTOR_ID": "test"}
    else:
        activated = post_json(client, ACTIVATE, activation_payload(), **bearer(token))
        extra = bearer(activated.json()["activation_token"])
    response = post_json(client, REVOKE, payload, **extra)
    assert response.status_code == expected
    assert not response.cookies
    assert response["Cache-Control"] == "no-store"
    services.authenticate_session(token)
    assert not AuditEvent.objects.filter(action="customer_user.logged_out").exists()


def test_header_revoke_does_not_touch_different_ambient_cookie_session():
    token = mint()
    cookie_token = session_token()
    client = native_client()
    client.cookies[ACCOUNT_SESSION_COOKIE] = cookie_token
    response = post_json(client, REVOKE, {}, **bearer(token))
    assert response.status_code == 200
    assert not response.cookies
    services.authenticate_session(cookie_token)
    with pytest.raises(SafeAPIError):
        services.authenticate_session(token)


def test_member_can_end_own_session_but_cannot_request_all_sessions():
    seed_user(seed_org(), role=CustomerRole.MEMBER)
    token = session_token()
    client = native_client()
    assert post_json(client, REVOKE, {"all_sessions": True}, **bearer(token)).status_code == 400
    services.authenticate_session(token)
    assert post_json(client, REVOKE, {}, **bearer(token)).status_code == 200


@pytest.mark.parametrize("body", ["[", "[]", '"text"', "null", '{"allSessions":true}'])
def test_malformed_or_unsupported_json_never_revokes(body):
    token = mint()
    response = native_client().post(REVOKE, data=body, content_type="application/json", **bearer(token))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert not response.cookies
    services.authenticate_session(token)


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data"])
def test_simple_posts_and_wrong_method_do_not_spend_revoke_budget(settings, django_assert_num_queries, content_type):
    token = mint()
    settings.SELAHCUE_THROTTLE_SESSION_REVOKE = (1, 60)
    client = native_client()
    with django_assert_num_queries(0):
        for _ in range(2):
            assert client.post(REVOKE, data="{}", content_type=content_type).status_code == 400
        assert client.get(REVOKE).status_code == 405
    assert post_json(client, REVOKE, {}, **bearer(token)).status_code == 200


def test_revoke_has_separate_per_ip_budget_and_preserves_token_on_throttle(settings):
    token = mint()
    settings.SELAHCUE_THROTTLE_SESSION_REVOKE = (1, 60)
    client = native_client()
    assert post_json(client, REVOKE, {}, **bearer("not-a-session")).status_code == 401
    denied = post_json(client, REVOKE, {}, **bearer(token))
    assert denied.status_code == 429
    assert denied.json()["error"]["code"] == "RATE_LIMITED"
    assert denied["Cache-Control"] == "no-store"
    assert 1 <= int(denied["Retry-After"]) <= 60
    services.authenticate_session(token)
    assert post_json(client, REVOKE, {}, REMOTE_ADDR="203.0.113.11", **bearer(token)).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_real_socket_cookieless_revoke_refuses_reuse_and_keeps_device(live_server):
    token = mint()
    def call(path, payload, presented):
        request = urllib.request.Request(
            live_server.url + path, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {presented}"},
        )
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            assert response.headers.get("Set-Cookie") is None
            return response.status, json.load(response)
    status, activated = call(ACTIVATE, activation_payload(), token)
    assert status == 200
    assert call(REVOKE, {}, token)[0] == 200
    assert call(REVOKE, {}, token)[0] == 401
    assert call("/v1/license:refresh", {}, activated["activation_token"])[0] == 200


def test_default_revoke_budget_and_scope_only_denial_log(settings, caplog):
    settings.SELAHCUE_THROTTLE_SESSION_REVOKE = production_settings.SELAHCUE_THROTTLE_SESSION_REVOKE
    token = mint()
    client = native_client()
    responses = [post_json(client, REVOKE, {}, **bearer("PRIVATE-INVALID-SESSION")) for _ in range(60)]
    assert [r.status_code for r in responses[:10]] == [401] * 10
    assert [r.status_code for r in responses[10:]] == [429] * 50
    warnings = [r for r in caplog.records if r.name == "selahcue_api.apps.throttling.guards"]
    assert len(warnings) == 1
    assert "session_revoke" in warnings[0].getMessage()
    assert "PRIVATE-INVALID-SESSION" not in warnings[0].getMessage()
    assert token not in warnings[0].getMessage()
    services.authenticate_session(token)
    # Ending account sessions cannot starve new sign-in or device activation.
    assert session_token(client)
    assert post_json(client, ACTIVATE, activation_payload(), **bearer(token)).status_code == 200
