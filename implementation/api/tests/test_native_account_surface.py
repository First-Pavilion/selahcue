"""The native-client account surface under `/v1` (86ak5t1gw, ADR-0027).

THE DEFECT THIS FILE EXISTS FOR. DEC-011 part 3 makes account sign-in the primary activation
path, and the desktop reaches it as `login` then `activateDeviceWithSession` on
`POST /graphql/account`. A native client has no cookie jar and no `X-CSRFToken`, so
`CsrfViewMiddleware` answered every one of those requests with a 403 HTML page. Both sides'
wire fixtures agreed with each other and the request still failed, because CSRF is transport
middleware that sits in front of the shape. Nothing in the suite sent a request the way the
desktop sends one, so nothing noticed.

THE FIX IS NOT AN EXEMPTION OF `/graphql/account`. That route authenticates from an AMBIENT
credential — `_read_account_session_token` falls back to the `selahcue_account_session` cookie,
and `login`/`refreshSession` set it — so exempting it would delete the control that protects
cookie-carrying browsers. The desktop instead gets two routes beside the rest of `/v1`
(`POST /v1/sessions`, `POST /v1/activations:with-session`) that are `csrf_exempt` for the same
reason the rest of `/v1` is: they read the session from the `Authorization` header ONLY and
never set a cookie, so there is no ambient authority for a forged request to ride on.

So the properties that matter, and what pins each:

- a native-shaped client succeeds                       -> the end-to-end and live-server tests
- the exemption is sound (no cookie in, no cookie out)  -> the `cookie` tests
- the browser surface is still protected                -> the `browser_surface` tests and the
                                                           exempt-route allow-list
- the new login route is not softer than the old one    -> the throttle / lockout / oracle tests

Django's test client bypasses CSRF unless `enforce_csrf_checks=True`; every client below that
stands in for a real caller sets it, which is the lesson of the original defect.
"""

import json
import urllib.error
import urllib.request

import pytest
from django.contrib.auth.hashers import PBKDF2PasswordHasher, make_password
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import get_resolver
from django.utils import timezone

from selahcue_api import settings as production_settings
from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import (
    CustomerOrg,
    CustomerRole,
    CustomerSession,
    CustomerUser,
    CustomerUserStatus,
)
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import Device, DeviceToken, DeviceTokenStatus
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.graphql.context import ACCOUNT_SESSION_COOKIE

SESSIONS = "/v1/sessions"
ACTIVATE = "/v1/activations:with-session"
PASSWORD = "correct-horse-battery"
EMAIL = "pastor@grace.example"

# Every route that is `csrf_exempt`, by name. Adding a route to this set is a security decision:
# an exempt route must not be able to authenticate from, or set, an ambient browser credential.
EXPECTED_CSRF_EXEMPT_ROUTES = {
    "v1/activations",
    "v1/sessions",
    "v1/activations:with-session",
    "v1/license:refresh",
    "v1/downloads:prepare",
    "v1/downloads/<str:lease_id>:complete",
    "v1/usage-events:batch",
    "webhooks/billing/<str:provider>",
}


@pytest.fixture(autouse=True)
def _fresh_budgets(settings):
    """Throttle buckets live in the process-wide LocMemCache and every test client is
    REMOTE_ADDR=127.0.0.1, so without a reset the tests would share one budget. The budgets are
    also raised so a test that is not ABOUT throttling cannot trip one; the throttle tests
    below set their own."""
    cache.clear()
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1000, 60)
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1000, 60)


# --- helpers ---------------------------------------------------------------
def native_client():
    """A client that behaves like the desktop's `ReqwestTransport`: no cookie to send, no CSRF
    token to send, and — unlike Django's default test client — CSRF actually enforced."""
    return Client(enforce_csrf_checks=True)


def post_json(client, path, payload, **extra):
    return client.post(path, data=json.dumps(payload), content_type="application/json", **extra)


def bearer(token):
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def seed_org(*, tag="grace"):
    return CustomerOrg.objects.create(
        name="Grace Chapel",
        slug=f"{tag}-chapel",
        primary_contact_email=f"office@{tag}.example",
        country="NG",
        created_by_actor_id="test",
        idempotency_key=f"org-{tag}-0001",
    )


def seed_user(org, *, email=EMAIL, password=PASSWORD, role=CustomerRole.ADMIN, verified=True):
    return CustomerUser.objects.create(
        customer=org,
        email=email,
        email_fingerprint=services._fingerprint(email),
        password_hash=make_password(password),
        status=CustomerUserStatus.ACTIVE,
        role=role,
        email_verified_at=timezone.now() if verified else None,
        created_by_actor_id="test",
        idempotency_key=f"user-{email}",
    )


def seed_license(org, *, device_limit=3):
    return AppLicenseKey.objects.create(
        customer=org,
        key_type="TRIAL",
        status=LicenseKeyStatus.ACTIVATED,
        key_prefix="SC-LK",
        key_suffix="ZZZZ",
        masked_key="SC-LK...ZZZZ",
        secret_hash="x",
        secret_fingerprint=f"lkfp-{org.id}",
        feature_scope="core",
        territory="GLOBAL",
        starts_at=timezone.now() - timezone.timedelta(days=1),
        expires_at=timezone.now() + timezone.timedelta(days=30),
        timezone="UTC",
        seat_limit=5,
        device_limit=device_limit,
        generated_by_actor_id="staff",
        generated_reason="test fixture",
        idempotency_key=f"lk-{org.id}",
    )


def seed_admin_with_license(*, device_limit=3):
    org = seed_org()
    user = seed_user(org)
    seed_license(org, device_limit=device_limit)
    return org, user


def sign_in(client, *, email=EMAIL, password=PASSWORD, **extra):
    return post_json(client, SESSIONS, {"email": email, "password": password}, **extra)


def session_token(client=None):
    response = sign_in(client or native_client())
    assert response.status_code == 200, response.content
    return response.json()["session_token"]


def activation_payload(idem="native-act-0001", fingerprint="install-native-1", **over):
    payload = {
        "idempotency_key": idem,
        "device_fingerprint": fingerprint,
        "platform": "windows",
        "app_version": "1.0.0",
        "display_name": "Sound booth",
    }
    payload.update(over)
    return payload


def error_body(response):
    return response.json()["error"]


# --- the two routes work for a native-shaped client ------------------------
@pytest.mark.django_db
def test_native_sign_in_needs_no_cookie_and_no_csrf_token_and_sets_no_cookie():
    """The reported defect, reproduced as the desktop sends it: CSRF enforced, no cookie, no
    token. Two assertions carry the safety argument rather than the convenience one: the
    response must not set a cookie (so a cross-site login attempt leaves nothing in the
    victim's browser), and it must not be cacheable (it carries a show-once secret)."""
    seed_admin_with_license()
    client = native_client()

    response = sign_in(client)

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["session_token"]
    assert body["role"] == "ADMIN"
    assert body["org_id"]
    assert body["expires_at"]
    assert (body["surface"], body["operation"]) == ("desktop", "session_login")
    assert not response.cookies, "a native sign-in must never set a cookie"
    assert "Set-Cookie" not in response.headers
    assert "no-store" in response["Cache-Control"]
    assert not client.cookies


@pytest.mark.django_db
def test_native_sign_in_then_activation_registers_a_device_end_to_end():
    org, user = seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    response = post_json(client, ACTIVATE, activation_payload(), **bearer(token))

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["created"] is True
    assert body["reminted"] is False
    assert body["activation_token"].startswith("SC-DEV-")
    assert body["device"]["device_public_id"].startswith("dev_")
    assert body["device"]["platform"] == "windows"
    # The richer /v1 shape: token metadata and the backing licence ride along, which the
    # GraphQL payload for the same operation does not carry.
    assert body["token"]["fingerprint"]
    assert body["license"]["status"] == LicenseKeyStatus.ACTIVATED
    assert (body["surface"], body["operation"]) == ("desktop", "activation_with_session")
    assert "no-store" in response["Cache-Control"]
    assert Device.objects.count() == 1
    assert DeviceToken.objects.count() == 1
    assert not client.cookies

    # Provenance: both rows say they came in over the native surface, and the activation is
    # attributed to the signed-in user, exactly as on the GraphQL path.
    logged_in = AuditEvent.objects.get(action="customer_user.logged_in")
    activated = AuditEvent.objects.get(action="device.activated")
    assert logged_in.source_surface == "desktop_v1"
    assert activated.source_surface == "desktop_v1"
    assert activated.actor_id == str(user.id)


@pytest.mark.django_db
def test_native_activation_replay_is_show_once():
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    first = post_json(client, ACTIVATE, activation_payload(), **bearer(token))
    second = post_json(client, ACTIVATE, activation_payload(), **bearer(token))

    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["activation_token"] is None
    assert Device.objects.count() == 1


@pytest.mark.django_db
def test_a_member_cannot_activate_a_device_over_the_native_route():
    org = seed_org()
    seed_user(org, email="member@grace.example", role=CustomerRole.MEMBER)
    seed_license(org)
    client = native_client()
    token = sign_in(client, email="member@grace.example").json()["session_token"]

    response = post_json(client, ACTIVATE, activation_payload(), **bearer(token))

    assert response.status_code == 403
    assert error_body(response)["code"] == "PERMISSION_DENIED"
    assert Device.objects.count() == 0


@pytest.mark.django_db
def test_native_activation_without_a_session_is_unauthenticated():
    seed_admin_with_license()

    missing = post_json(native_client(), ACTIVATE, activation_payload())
    garbage = post_json(native_client(), ACTIVATE, activation_payload(), **bearer("not-a-session"))

    for response in (missing, garbage):
        assert response.status_code == 401
        assert error_body(response)["code"] == "UNAUTHENTICATED"
    assert Device.objects.count() == 0


# --- the exemption is sound: no ambient credential in, none out ------------
@pytest.mark.django_db
def test_a_session_cookie_alone_cannot_authenticate_the_native_activation_route():
    """THE property that makes `csrf_exempt` safe here. CSRF protection exists because a browser
    attaches cookies on its own. The native route therefore must not accept the account-session
    cookie as a credential — otherwise a forged cross-site POST, carrying the victim's cookie,
    would be an authenticated activation with the CSRF check switched off.

    The positive control matters as much as the assertion: the SAME cookie IS a working
    credential on the browser surface, so a 401 here is the route refusing a credential that
    would otherwise have been honoured, not a typo in the cookie."""
    seed_admin_with_license()
    token = session_token()

    cookie_only = native_client()
    cookie_only.cookies[ACCOUNT_SESSION_COOKIE] = token
    refused = post_json(cookie_only, ACTIVATE, activation_payload())

    assert refused.status_code == 401
    assert error_body(refused)["code"] == "UNAUTHENTICATED"
    assert Device.objects.count() == 0

    # Positive control: same cookie, browser surface, CSRF not in play (default test client).
    browser = Client()
    browser.cookies[ACCOUNT_SESSION_COOKIE] = token
    mutation = (
        "mutation { activateDeviceWithSession(input: {idempotencyKey: \"ctl-act-0000001\", "
        "deviceFingerprint: \"ctl-1\", platform: \"windows\"}) { created } }"
    )
    honoured = browser.post(
        "/graphql/account", data=json.dumps({"query": mutation}), content_type="application/json"
    )
    assert honoured.json()["data"]["activateDeviceWithSession"]["created"] is True


@pytest.mark.django_db
def test_a_cookie_alongside_a_bad_bearer_does_not_fall_back_to_the_cookie():
    """The browser surface prefers the bearer but FALLS BACK to the cookie when the bearer is
    absent. A native route that copied that fallback for a bad bearer would be the same hole."""
    seed_admin_with_license()
    token = session_token()
    client = native_client()
    client.cookies[ACCOUNT_SESSION_COOKIE] = token

    response = post_json(client, ACTIVATE, activation_payload(), **bearer("not-a-session"))

    assert response.status_code == 401
    assert Device.objects.count() == 0


@pytest.mark.django_db
@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=True)
def test_the_dev_actor_header_bridge_cannot_authenticate_the_native_routes():
    """`SELAHCUE_TRUST_ACTOR_HEADERS` is a dev/test bridge for staff and device actors on the
    GraphQL surfaces. A route exempt from CSRF must not honour a header that any caller can
    forge, however it is configured."""
    org, user = seed_admin_with_license()

    response = post_json(
        native_client(),
        ACTIVATE,
        activation_payload(),
        HTTP_X_SELAHCUE_ACTOR_KIND="customer",
        HTTP_X_SELAHCUE_ACTOR_ID=str(user.id),
        HTTP_X_SELAHCUE_ORG_ID=str(org.id),
    )

    assert response.status_code == 401
    assert Device.objects.count() == 0


# --- the browser surface is still protected --------------------------------
@pytest.mark.django_db
def test_browser_surface_still_refuses_a_native_shaped_login():
    """The original defect, pinned as the CORRECT behaviour for `/graphql/account`: a POST with
    no cookie and no token is refused before the resolver runs. The login must not have been
    attempted at all, so no failed-attempt counter moved."""
    _org, user = seed_admin_with_license()

    response = native_client().post(
        "/graphql/account",
        data=json.dumps(
            {
                "query": "mutation($i: LoginInput!) { login(input: $i) { sessionToken } }",
                "variables": {"i": {"email": EMAIL, "password": "wrong-password-1"}},
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response["Content-Type"].startswith("text/html")
    user.refresh_from_db()
    assert user.failed_login_count == 0
    assert CustomerSession.objects.count() == 0


@pytest.mark.django_db
def test_browser_surface_still_refuses_a_cookie_authenticated_activation_without_a_token():
    """This is the forgery the CSRF control exists to stop: the victim's browser attaches the
    session cookie by itself, the attacker's page supplies everything else. Without a token
    the request must die in the middleware, with a valid cookie and a valid body."""
    seed_admin_with_license()
    token = session_token()
    mutation = (
        "mutation { activateDeviceWithSession(input: {idempotencyKey: \"forged-act-00001\", "
        "deviceFingerprint: \"forged-1\", platform: \"windows\"}) { created } }"
    )
    victim_browser = native_client()
    victim_browser.cookies[ACCOUNT_SESSION_COOKIE] = token

    forged = victim_browser.post(
        "/graphql/account", data=json.dumps({"query": mutation}), content_type="application/json"
    )

    assert forged.status_code == 403
    assert Device.objects.count() == 0

    # Positive control: the same browser, after the sanctioned bootstrap, is honoured — so the
    # 403 above is the missing token and nothing else.
    bootstrap = victim_browser.get("/graphql/csrf")
    csrf = bootstrap.cookies["csrftoken"].value
    honoured = victim_browser.post(
        "/graphql/account",
        data=json.dumps({"query": mutation}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert honoured.status_code == 200
    assert honoured.json()["data"]["activateDeviceWithSession"]["created"] is True


def _routes(patterns, prefix=""):
    for entry in patterns:
        route = prefix + str(entry.pattern)
        if hasattr(entry, "url_patterns"):
            yield from _routes(entry.url_patterns, route)
        else:
            yield route, entry.callback


def test_the_set_of_csrf_exempt_routes_is_pinned_and_excludes_every_graphql_route():
    """Option (a) of the ticket — exempt the account route — would pass every behavioural test
    above that does not use a cookie. This pins the SET, so exempting anything is a deliberate
    edit to `EXPECTED_CSRF_EXEMPT_ROUTES`, reviewed as the security decision it is."""
    routes = list(_routes(get_resolver().url_patterns))
    exempt = {route for route, callback in routes if getattr(callback, "csrf_exempt", False)}

    graphql_exempt = {route for route in exempt if route.startswith("graphql/")}
    assert not graphql_exempt, f"a GraphQL route is CSRF-exempt: {graphql_exempt}"
    assert exempt == EXPECTED_CSRF_EXEMPT_ROUTES


# --- the new login route is not softer than the old one --------------------
@pytest.mark.django_db
def test_unknown_email_and_wrong_password_are_indistinguishable_on_the_native_route():
    seed_admin_with_license()

    unknown = sign_in(native_client(), email="nobody@grace.example", password="whatever-password")
    wrong = sign_in(native_client(), password="not-the-password")

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
    assert error_body(unknown)["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_unverified_account_is_policy_denied_only_after_the_right_password():
    org = seed_org()
    seed_user(org, verified=False)

    right = sign_in(native_client())
    wrong = sign_in(native_client(), password="not-the-password")

    assert right.status_code == 403
    assert error_body(right)["code"] == "POLICY_DENIED"
    assert wrong.status_code == 401
    assert CustomerSession.objects.count() == 0


@pytest.mark.django_db
def test_native_sign_in_shares_the_per_account_lockout_with_the_browser_surface():
    """The lockout is state on the account, not on the route, so it is inherited — and a lock
    earned on the native route also stops the browser surface, which is what stops the new
    route from being a way around it."""
    _org, user = seed_admin_with_license()

    for _ in range(services.LOGIN_LOCKOUT_THRESHOLD):
        assert sign_in(native_client(), password="not-the-password").status_code == 401

    user.refresh_from_db()
    assert user.locked_until is not None

    # Even the CORRECT password is refused, with the same code as any other failure...
    locked = sign_in(native_client())
    assert locked.status_code == 401
    assert error_body(locked)["code"] == "UNAUTHENTICATED"
    assert CustomerSession.objects.count() == 0

    # ...and the browser surface sees the same lock.
    browser = Client()
    response = browser.post(
        "/graphql/account",
        data=json.dumps(
            {
                "query": "mutation($i: LoginInput!) { login(input: $i) { sessionToken } }",
                "variables": {"i": {"email": EMAIL, "password": PASSWORD}},
            }
        ),
        content_type="application/json",
    )
    assert response.json()["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_sign_in_is_throttled_per_client_ip(settings):
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (2, 60)
    seed_admin_with_license()
    client = native_client()

    first = sign_in(client, password="not-the-password")
    second = sign_in(client, password="not-the-password")
    # The budget is spent BEFORE the credential is looked at: a throttled caller learns nothing
    # about whether this password was right.
    third = sign_in(client)

    assert (first.status_code, second.status_code) == (401, 401)
    assert third.status_code == 429
    assert error_body(third)["code"] == "RATE_LIMITED"
    assert (third.json()["surface"], third.json()["operation"]) == ("desktop", "session_login")
    assert CustomerSession.objects.count() == 0

    # Per client, not global: another address has its own budget.
    other = sign_in(client, REMOTE_ADDR="203.0.113.7")
    assert other.status_code == 200


@pytest.mark.django_db
def test_a_refused_method_does_not_spend_the_sign_in_budget(settings):
    """`require_POST` sits ABOVE the throttle on purpose, so a 405 cannot be used to burn a
    caller's budget (or a victim's, behind a shared NAT)."""
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1, 60)
    seed_admin_with_license()
    client = native_client()

    for _ in range(3):
        assert client.get(SESSIONS).status_code == 405

    assert sign_in(client).status_code == 200


@pytest.mark.django_db
def test_native_activation_is_throttled_per_client_ip(settings):
    settings.SELAHCUE_THROTTLE_ACTIVATION = (2, 60)
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    first = post_json(client, ACTIVATE, activation_payload(idem="thr-act-0000001"), **bearer(token))
    second = post_json(client, ACTIVATE, activation_payload(idem="thr-act-0000001"), **bearer(token))
    third = post_json(client, ACTIVATE, activation_payload(idem="thr-act-0000001"), **bearer(token))

    assert (first.status_code, second.status_code) == (200, 200)
    assert third.status_code == 429
    assert error_body(third)["code"] == "RATE_LIMITED"
    assert third.json()["operation"] == "activation_with_session"


@pytest.mark.django_db
def test_native_activation_budget_is_separate_from_the_enrollment_key_budget(settings):
    """Same size, separate bucket: a desktop that burned its enrollment-key budget must not be
    locked out of account sign-in activation, or the delegation path could be used to deny the
    primary one."""
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1, 60)
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    spent = post_json(client, "/v1/activations", {"license_key": "SC-NOPE", "device_fingerprint": "x"})
    refused = post_json(client, "/v1/activations", {"license_key": "SC-NOPE", "device_fingerprint": "x"})
    assert spent.status_code != 429
    assert refused.status_code == 429

    response = post_json(client, ACTIVATE, activation_payload(), **bearer(token))
    assert response.status_code == 200


# --- request hygiene --------------------------------------------------------
@pytest.mark.django_db
def test_a_non_json_content_type_is_refused_before_any_credential_is_checked():
    """A cross-site HTML form can send `text/plain` with a JSON-looking body without a CORS
    preflight; `application/json` it cannot. Requiring it keeps a forged form post from ever
    reaching the credential check — it is not counted as a login attempt either."""
    _org, user = seed_admin_with_license()
    body = json.dumps({"email": EMAIL, "password": "not-the-password"})

    response = native_client().post(SESSIONS, data=body, content_type="text/plain")

    assert response.status_code == 400
    assert error_body(response)["code"] == "VALIDATION_FAILED"
    user.refresh_from_db()
    assert user.failed_login_count == 0

    # The same form post with the RIGHT password must not mint a session either.
    right = native_client().post(
        SESSIONS,
        data=json.dumps({"email": EMAIL, "password": PASSWORD}),
        content_type="text/plain",
    )
    assert right.status_code == 400
    assert CustomerSession.objects.count() == 0


@pytest.mark.django_db
def test_a_non_json_content_type_is_refused_on_native_activation():
    seed_admin_with_license()
    token = session_token()

    response = native_client().post(
        ACTIVATE,
        data=json.dumps(activation_payload()),
        content_type="text/plain",
        **bearer(token),
    )

    assert response.status_code == 400
    assert error_body(response)["code"] == "VALIDATION_FAILED"
    assert Device.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        "[]",
        '"a string"',
        '{"email": 1, "password": "x"}',
        '{"email": "a@b.example", "password": null}',
        '{"email": "a@b.example"}',
        json.dumps({"email": "a" * 300 + "@b.example", "password": "x"}),
        json.dumps({"email": "a@b.example", "password": "x" * 5000}),
    ],
)
def test_malformed_sign_in_bodies_are_validation_failures_that_attempt_nothing(raw):
    seed_admin_with_license()

    response = native_client().post(SESSIONS, data=raw, content_type="application/json")

    assert response.status_code == 400
    assert error_body(response)["code"] == "VALIDATION_FAILED"
    assert CustomerSession.objects.count() == 0


@pytest.mark.django_db
def test_native_activation_validates_the_device_fields_like_the_graphql_path():
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    response = post_json(
        client, ACTIVATE, activation_payload(device_fingerprint=""), **bearer(token)
    )

    assert response.status_code == 400
    assert error_body(response)["code"] == "VALIDATION_FAILED"
    assert Device.objects.count() == 0


@pytest.mark.django_db
def test_native_routes_accept_post_only():
    for path in (SESSIONS, ACTIVATE):
        for method in ("get", "put", "delete"):
            assert getattr(native_client(), method)(path).status_code == 405


@pytest.mark.django_db
def test_native_routes_emit_no_cors_headers_so_a_cross_origin_page_cannot_use_them():
    """The `application/json` requirement is only a defence because a cross-origin page needs a
    CORS preflight to send it, and that preflight must FAIL. It does only while the API emits no
    `Access-Control-*` headers (`settings.py`: CORS is deliberately not installed). If someone
    enables CORS for these routes, this is the test that says the CSRF argument no longer holds."""
    seed_admin_with_license()
    origin = {"HTTP_ORIGIN": "https://evil.example"}

    for path in (SESSIONS, ACTIVATE):
        preflight = native_client().options(
            path,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type,authorization",
            **origin,
        )
        assert preflight.status_code == 405
        assert not [h for h in preflight.headers if h.lower().startswith("access-control-")]

    actual = sign_in(native_client(), **origin)
    assert actual.status_code == 200
    assert not [h for h in actual.headers if h.lower().startswith("access-control-")]


@pytest.mark.django_db
def test_the_sign_in_response_never_echoes_credentials():
    seed_admin_with_license()

    response = sign_in(native_client())

    # Status first: a 404 page also contains neither string, and this test would pass on it.
    assert response.status_code == 200
    text = response.content.decode()
    assert PASSWORD not in text
    assert "password" not in text.lower()


# --- the integration evidence the ticket asks for ---------------------------
def _native_request(url, *, payload=None, token=None, method="POST"):
    """One HTTP request exactly as the desktop's `ReqwestTransport` sends it: a `Content-Type`
    and optionally a bearer, over a real socket, with NO cookie handling at all
    (`urlopen`'s default opener has no cookie processor) and no CSRF header."""
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.headers, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read().decode()


@pytest.mark.django_db(transaction=True)
def test_live_server_a_cookieless_client_signs_in_activates_and_refreshes(live_server):
    """AC2 of 86ak5t1gw. A fixture cannot satisfy it — fixtures were the reason it went
    unnoticed — so this talks to a REAL running server over a REAL socket, with a client that has
    no cookie jar and sends no CSRF token, and walks the whole primary path:

        sign in  ->  activate with the session  ->  use the minted device token

    The first request is the original defect, kept as a control: the same kind of client gets
    Django's 403 HTML page from `/graphql/account`. It is both the proof that this test would
    have caught the bug and the proof that the browser surface is still protected."""
    seed_admin_with_license()
    base = live_server.url

    status, headers, body = _native_request(
        f"{base}/graphql/account",
        payload={
            "query": "mutation($i: LoginInput!) { login(input: $i) { sessionToken } }",
            "variables": {"i": {"email": EMAIL, "password": PASSWORD}},
        },
    )
    assert status == 403
    assert headers["Content-Type"].startswith("text/html")
    assert "CSRF" in body

    status, headers, body = _native_request(
        f"{base}{SESSIONS}", payload={"email": EMAIL, "password": PASSWORD}
    )
    assert status == 200, body
    assert headers.get("Set-Cookie") is None
    session = json.loads(body)["session_token"]

    status, headers, body = _native_request(
        f"{base}{ACTIVATE}", payload=activation_payload(), token=session
    )
    assert status == 200, body
    assert headers.get("Set-Cookie") is None
    device_token = json.loads(body)["activation_token"]
    assert device_token.startswith("SC-DEV-")

    # The credential the desktop ends up holding actually works against the rest of /v1.
    status, _headers, body = _native_request(f"{base}/v1/license:refresh", payload={}, token=device_token)
    assert status == 200, body
    assert json.loads(body)["license"]["valid_now"] is True


# --- PR #151 review round: guards that the first cut of this file left open -------------------
@pytest.mark.django_db
@pytest.mark.parametrize(
    "content_type", ["text/plain", "application/x-www-form-urlencoded"], ids=["text-plain", "form"]
)
def test_forged_simple_posts_do_not_spend_the_sign_in_budget(settings, django_assert_num_queries, content_type):
    """A cross-site HTML form can send `text/plain` or form-encoded without a preflight. If the
    content-type refusal ran BELOW the throttle, a hostile page could burn the victim network's
    per-IP budget with requests that can never reach a credential check, and the legitimate JSON
    sign-in behind the same NAT would get a 429. The refusal is a string compare ABOVE the
    throttle: no budget, and no database."""
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1, 60)
    seed_admin_with_license()
    client = native_client()
    forged = json.dumps({"email": EMAIL, "password": "not-the-password"})

    with django_assert_num_queries(0):
        first = client.post(SESSIONS, data=forged, content_type=content_type)
        second = client.post(SESSIONS, data=forged, content_type=content_type)
    legitimate = sign_in(client)

    assert (first.status_code, second.status_code, legitimate.status_code) == (400, 400, 200)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "content_type", ["text/plain", "application/x-www-form-urlencoded"], ids=["text-plain", "form"]
)
def test_forged_simple_posts_do_not_spend_the_native_activation_budget(
    settings, django_assert_num_queries, content_type
):
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1, 60)
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)  # sign-in has its own, generous, budget
    forged = json.dumps(activation_payload())

    with django_assert_num_queries(0):
        first = client.post(ACTIVATE, data=forged, content_type=content_type, **bearer(token))
        second = client.post(ACTIVATE, data=forged, content_type=content_type, **bearer(token))
    legitimate = post_json(client, ACTIVATE, activation_payload(), **bearer(token))

    assert (first.status_code, second.status_code, legitimate.status_code) == (400, 400, 200)
    assert Device.objects.count() == 1


@pytest.mark.django_db
def test_the_throttle_runs_before_the_password_hash(monkeypatch, settings):
    """The per-IP budget is only a CPU bound if it is spent BEFORE `check_password`. 25 sign-ins
    against a limit of 10 must cost exactly 10 PBKDF2 computations (found by performance review).
    `PBKDF2PasswordHasher.encode` is the one place `make_password` and `check_password` both spend
    the iterations, so counting it counts every hash."""
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (10, 60)
    hashes = []
    real_encode = PBKDF2PasswordHasher.encode

    def counting_encode(self, password, salt, iterations=None):
        hashes.append(1)
        return real_encode(self, password, salt, iterations)

    monkeypatch.setattr(PBKDF2PasswordHasher, "encode", counting_encode)
    client = native_client()

    statuses = [
        sign_in(client, email=f"nobody{i}@grace.example", password="wrong-password-1").status_code
        for i in range(25)
    ]

    assert statuses == [401] * 10 + [429] * 15
    assert len(hashes) == 10


@pytest.mark.django_db
@pytest.mark.parametrize("path", [SESSIONS, ACTIVATE], ids=["sessions", "activation"])
def test_deeply_nested_json_is_a_validation_failure_not_a_server_error(path):
    """~1.3 MB of `[` fits under Django's 2.5 MB body cap and recurses the JSON parser past the
    interpreter limit. On an unauthenticated route that was an HTTP 500 for the price of one
    request body; it is the same VALIDATION_FAILED as any other body that is not a JSON object."""
    response = native_client().post(path, data="[" * 1_300_000, content_type="application/json")

    assert response.status_code == 400
    assert error_body(response)["code"] == "VALIDATION_FAILED"


@pytest.mark.django_db
def test_an_empty_bearer_header_does_not_fall_back_to_the_body_on_the_device_routes():
    """`_device_bearer_token` shares `_bearer_from_header` with the native routes. A header that IS
    a bearer credential but empty (`Bearer `) has always been an empty credential, not an absent
    one, so the `device_token` body fallback must stay unreachable behind it."""
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)
    device_token = post_json(client, ACTIVATE, activation_payload(), **bearer(token)).json()[
        "activation_token"
    ]

    fallback = post_json(client, "/v1/license:refresh", {"device_token": device_token})
    shadowed = post_json(
        client,
        "/v1/license:refresh",
        {"device_token": device_token},
        HTTP_AUTHORIZATION="Bearer ",
    )

    assert fallback.status_code == 200  # the body fallback itself is unchanged
    assert shadowed.status_code == 401


@pytest.mark.django_db
def test_the_graphql_surface_still_audits_as_account_graphql():
    """The audit provenance keyword added for the native routes must default to what the GraphQL
    surface always recorded: nothing about WHICH surface a sign-in or an activation came in on
    may drift for a browser caller just because a native route now exists."""
    seed_admin_with_license()
    browser = Client()
    login = browser.post(
        "/graphql/account",
        data=json.dumps(
            {
                "query": "mutation($i: LoginInput!) { login(input: $i) { sessionToken } }",
                "variables": {"i": {"email": EMAIL, "password": PASSWORD}},
            }
        ),
        content_type="application/json",
    )
    token = login.json()["data"]["login"]["sessionToken"]
    activate = browser.post(
        "/graphql/account",
        data=json.dumps(
            {
                "query": (
                    "mutation($i: ActivateDeviceInput!) "
                    "{ activateDeviceWithSession(input: $i) { created } }"
                ),
                "variables": {
                    "i": {
                        "idempotencyKey": "gql-audit-0000001",
                        "deviceFingerprint": "gql-audit-1",
                        "platform": "windows",
                    }
                },
            }
        ),
        content_type="application/json",
        **bearer(token),
    )

    assert activate.json()["data"]["activateDeviceWithSession"]["created"] is True
    assert AuditEvent.objects.get(action="customer_user.logged_in").source_surface == "account_graphql"
    assert AuditEvent.objects.get(action="device.activated").source_surface == "account_graphql"


# --- QA-added pins (Quinn, PR #151 review): each kills a mutant that survived the first cut ----
@pytest.mark.django_db
@pytest.mark.parametrize("length,status", [(254, 401), (255, 400)])
def test_email_length_boundary_is_exactly_254(length, status):
    seed_admin_with_license()
    email = "a" * (length - len("@grace.example")) + "@grace.example"
    assert len(email) == length

    response = sign_in(native_client(), email=email, password="x" * 12)

    # 401 = "attempted and failed" (unknown account), 400 = "refused before any attempt".
    assert response.status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize("length,status", [(200, 401), (201, 400)])
def test_password_length_boundary_is_exactly_the_signup_maximum(length, status):
    """A 200-character password can exist (signup allows it), so refusing it on the native route
    would lock that user out of the primary activation path."""
    seed_admin_with_license()

    response = sign_in(native_client(), password="p" * length)

    assert response.status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [{"email": "", "password": PASSWORD}, {"email": EMAIL, "password": ""}],
    ids=["empty-email", "empty-password"],
)
def test_empty_credentials_are_refused_without_counting_as_a_failed_attempt(body):
    _org, user = seed_admin_with_license()

    response = post_json(native_client(), SESSIONS, body)

    assert response.status_code == 400
    user.refresh_from_db()
    assert user.failed_login_count == 0


@pytest.mark.django_db
def test_native_activation_persists_app_version_and_display_name():
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    response = post_json(
        client,
        ACTIVATE,
        activation_payload(app_version="2.3.4", display_name="Balcony rack"),
        **bearer(token),
    )

    assert response.status_code == 200
    device = Device.objects.get()
    assert device.app_version == "2.3.4"
    assert device.display_name == "Balcony rack"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "header",
    ["Bearer {t}", "bearer {t}", "BEARER {t}", "Bearer  {t}", "Bearer {t} "],
    ids=["canonical", "lower", "upper", "double-space", "trailing-space"],
)
def test_bearer_scheme_is_case_insensitive_and_tolerates_padding(header):
    """RFC 7235: the auth-scheme is case-insensitive."""
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    response = post_json(
        client, ACTIVATE, activation_payload(), HTTP_AUTHORIZATION=header.format(t=token)
    )

    assert response.status_code == 200, response.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "header",
    ["Basic {t}", "{t}", "Bearer\t{t}", "Bearer {t}x", "Bearer"],
    ids=["basic", "no-scheme", "tab", "suffix", "scheme-only"],
)
def test_anything_else_in_the_authorization_header_is_unauthenticated(header):
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    response = post_json(
        client, ACTIVATE, activation_payload(), HTTP_AUTHORIZATION=header.format(t=token)
    )

    assert response.status_code == 401
    assert Device.objects.count() == 0


@pytest.mark.django_db
def test_a_refused_method_does_not_spend_the_native_activation_budget(settings):
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1, 60)
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    for method in ("get", "put", "delete"):
        for _ in range(3):
            assert getattr(client, method)(ACTIVATE).status_code == 405

    assert post_json(client, ACTIVATE, activation_payload(), **bearer(token)).status_code == 200


@pytest.mark.django_db
def test_the_production_default_sign_in_budget_is_ten_per_minute(settings):
    """The autouse fixture overrides the budget in every other test, so the value that actually
    ships (`settings.py` / `deployments.md`: 10 per minute) would otherwise be exercised nowhere."""
    assert production_settings.SELAHCUE_THROTTLE_SESSION_LOGIN == (10, 60)
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = production_settings.SELAHCUE_THROTTLE_SESSION_LOGIN
    seed_admin_with_license()
    client = native_client()

    statuses = [sign_in(client, password="not-the-password").status_code for _ in range(12)]

    assert statuses == [401] * 10 + [429] * 2


@pytest.mark.django_db
def test_sign_in_and_activation_do_not_spend_each_others_budget(settings):
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (2, 60)
    settings.SELAHCUE_THROTTLE_ACTIVATION = (2, 60)
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)  # one sign-in spent

    # Two activation calls fit the activation budget even though sign-in has already spent one.
    assert post_json(client, ACTIVATE, activation_payload(), **bearer(token)).status_code == 200
    assert post_json(client, ACTIVATE, activation_payload(), **bearer(token)).status_code == 200
    # ...and a second sign-in still fits the sign-in budget.
    assert sign_in(client).status_code == 200


def _application_error_cases():
    return [
        ("sessions-401", lambda c, t: sign_in(c, password="not-the-password")),
        ("sessions-400", lambda c, t: post_json(c, SESSIONS, {})),
        ("activate-401", lambda c, t: post_json(c, ACTIVATE, activation_payload())),
        ("activate-400", lambda c, t: post_json(c, ACTIVATE, {}, **bearer(t))),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("name", [case[0] for case in _application_error_cases()])
def test_application_errors_are_never_cacheable_either(name):
    """An error body is not secret, but a cached 401 for a bearer-authenticated URL is still wrong.
    Scope: the application responses of these two views (not 405 / 429, which are produced by
    Django's `require_POST` and the shared throttle decorator)."""
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    response = dict(_application_error_cases())[name](client, token)

    assert response.status_code in (400, 401)
    assert "no-store" in response["Cache-Control"]


@pytest.mark.django_db
@pytest.mark.xfail(
    strict=True,
    reason="Known, NOT fixed in this PR: the 429 built by the shared `@throttle` decorator "
    "(apps/throttling/decorators.py) carries neither Cache-Control: no-store nor Retry-After. "
    "A Retry-After needs the fixed window's remaining TTL, which the store does not expose, and "
    "any header change in the shared decorator also changes POST /v1/activations and every other "
    "throttled /v1 route, so it needs its own review (follow-up). strict=True turns "
    "this into a failure the day the decorator is fixed, so the xfail cannot go stale.",
)
def test_a_throttled_response_is_no_store_and_says_when_to_retry(settings):
    settings.SELAHCUE_THROTTLE_SESSION_LOGIN = (1, 60)
    seed_admin_with_license()
    client = native_client()
    sign_in(client, password="not-the-password")

    throttled = sign_in(client, password="not-the-password")

    assert throttled.status_code == 429
    assert "no-store" in throttled["Cache-Control"]
    assert throttled["Retry-After"]


@pytest.mark.django_db
def test_a_reminted_device_token_is_attributed_to_the_native_surface():
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)
    first = post_json(client, ACTIVATE, activation_payload(), **bearer(token))
    assert first.status_code == 200
    DeviceToken.objects.update(status=DeviceTokenStatus.REVOKED)

    second = post_json(client, ACTIVATE, activation_payload(idem="native-act-0002"), **bearer(token))

    assert second.status_code == 200
    assert second.json()["reminted"] is True
    assert AuditEvent.objects.get(action="device_token.reminted").source_surface == "desktop_v1"


@pytest.mark.django_db
def test_a_malformed_activation_body_is_labelled_as_the_activation_operation():
    seed_admin_with_license()
    client = native_client()
    token = session_token(client)

    response = client.post(
        ACTIVATE, data="{not json", content_type="application/json", **bearer(token)
    )

    assert response.status_code == 400
    assert (response.json()["surface"], response.json()["operation"]) == (
        "desktop",
        "activation_with_session",
    )
