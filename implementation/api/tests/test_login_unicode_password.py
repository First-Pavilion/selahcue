"""Malformed Unicode must be an ordinary credential refusal, never an HTTP 500."""
import json
import logging

import pytest
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import CustomerSession
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError
from test_native_account_surface import PASSWORD, native_client, post_json, seed_org, seed_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("malformed", ["\ud800", "\udfff", "prefix\ud800suffix"])
def test_native_malformed_password_is_wrong_password_for_every_account_state(
    malformed, settings, caplog, monkeypatch,
):
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1000, 60)
    cache.clear()
    org = seed_org()
    known = seed_user(org)
    locked = seed_user(org, email="locked-unicode@example.invalid")
    locked.locked_until = timezone.now() + timezone.timedelta(minutes=5)
    locked.save(update_fields=["locked_until"])
    client = native_client()
    client.raise_request_exception = False
    baseline = post_json(client, "/v1/sessions", {
        "email": "unknown-unicode@example.invalid", "password": "wrong-password",
    })
    assert baseline.status_code == 401
    assert baseline.json()["error"]["code"] == "UNAUTHENTICATED"
    original = PBKDF2PasswordHasher.encode
    calls = []

    def real_encode(self, password, salt, iterations=None):
        calls.append(1)
        return original(self, password, salt, iterations)

    monkeypatch.setattr(PBKDF2PasswordHasher, "encode", real_encode)
    caplog.clear()
    responses = [post_json(client, "/v1/sessions", {"email": email, "password": malformed})
                 for email in (known.email, "unknown-unicode@example.invalid", locked.email)]
    assert [(r.status_code, r.json()) for r in responses] == [
        (baseline.status_code, baseline.json()),
    ] * 3
    assert len(calls) == 3, "each refused request must still perform a real password hash"
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert not [record for record in caplog.records if record.exc_info]
    for response in responses:
        assert response["Cache-Control"] == "no-store"
        assert not response.cookies
    known.refresh_from_db()
    locked.refresh_from_db()
    assert known.failed_login_count == 1
    assert locked.failed_login_count == 0
    assert not CustomerSession.objects.exists()


def test_malformed_password_reaches_normal_account_lockout(settings):
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1000, 60)
    cache.clear()
    user = seed_user(seed_org())
    client = native_client()
    client.raise_request_exception = False
    for _ in range(services.LOGIN_LOCKOUT_THRESHOLD):
        response = post_json(client, "/v1/sessions", {"email": user.email, "password": "\ud800"})
        assert response.status_code == 401
    user.refresh_from_db()
    assert user.locked_until > timezone.now()
    assert post_json(client, "/v1/sessions", {"email": user.email, "password": PASSWORD}).status_code == 401


def test_graphql_malformed_password_matches_ordinary_wrong_password():
    user = seed_user(seed_org())
    client = Client()

    def login(password):
        return client.post("/graphql/account", data=json.dumps({
            "query": "mutation($i: LoginInput!) { login(input: $i) { sessionToken } }",
            "variables": {"i": {"email": user.email, "password": password}},
        }), content_type="application/json")

    wrong = login("wrong-password")
    malformed = login("\ud800")
    assert malformed.status_code == wrong.status_code == 200
    assert malformed.json() == wrong.json()
    assert malformed.json()["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


def test_direct_login_keeps_byte_password_compatibility():
    user = seed_user(seed_org())
    result = services.login(services.LoginData(user.email, PASSWORD.encode("utf-8")))
    assert result.session_token
    with pytest.raises(SafeAPIError) as caught:
        services.login(services.LoginData(user.email, b"\xff"))
    assert caught.value.code == ErrorCode.UNAUTHENTICATED


def test_safe_hash_substitute_never_authenticates_even_if_it_matches(settings):
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1000, 60)
    cache.clear()
    user = seed_user(seed_org(), password="")
    response = post_json(native_client(), "/v1/sessions", {"email": user.email, "password": "\ud800"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert not CustomerSession.objects.exists()
    user.refresh_from_db()
    assert user.failed_login_count == 1


def test_native_malformed_password_still_spends_source_throttle(settings):
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (10, 60)
    cache.clear()
    responses = [post_json(native_client(), "/v1/sessions", {
        "email": "unknown-throttled@example.invalid", "password": "\ud800",
    }) for _ in range(11)]
    assert [response.status_code for response in responses] == [401] * 10 + [429]
    assert responses[-1].json()["error"]["code"] == "RATE_LIMITED"
