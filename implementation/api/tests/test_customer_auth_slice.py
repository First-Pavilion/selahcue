"""Traditional email/password customer auth (DEC-007 / ADR-0023) — AUTH-2..AUTH-5.

Covers self-serve signup, email verification, login/session/logout/refresh, and password reset,
with the no-enumeration + session-invalidation invariants.
"""

import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import date
from io import StringIO

import pytest
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, OperationalError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import (
    CredentialToken,
    CredentialTokenPurpose,
    CustomerOrg,
    CustomerRole,
    CustomerSession,
    CustomerUser,
    CustomerUserStatus,
)
from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.apps.throttling import guards
from selahcue_api.graphql.context import ActorContext, ActorKind
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


@pytest.fixture(autouse=True)
def _fresh_reset_throttle_budget():
    """`request_password_reset` / `confirm_password_reset` now spend a per-client-IP budget
    (86akcmfd4) in the SAME default LocMemCache used everywhere else, which persists for the
    whole pytest process. This file's Django test client defaults every call to
    REMOTE_ADDR=127.0.0.1, so without a per-test reset every test in this module would share
    ONE budget and the later ones would start seeing RATE_LIMITED instead of the codes they
    assert on. Mirrors `_fresh_throttle_budget` in test_resend_verification.py, which pins the
    same fixture for the same reason on the resend mutation.

    The failed-confirm trace (86ak5r2pt) also keeps process-local state -- its outage ceiling and
    its once-a-minute report tallies -- so that is reset here too, for the same reason.
    """
    cache.clear()
    services._reset_trace_reporting()


# --- helpers ---------------------------------------------------------------
def post_account(client, query, variables=None, *, bearer=None, **request_meta):
    # `request_meta` goes straight to the test client (REMOTE_ADDR, HTTP_X_FORWARDED_FOR...).
    extra = dict(request_meta)
    if bearer is not None:
        extra["HTTP_AUTHORIZATION"] = f"Bearer {bearer}"
    # Email dispatch is registered with `transaction.on_commit` so a rolled-back signup or
    # reset cannot leave a live email pointing at a token row that was never committed. Under
    # `django_db`'s rollback the outer atomic never commits, so those callbacks would never
    # run and the capturing sender would see nothing. `captureOnCommitCallbacks` is Django's
    # own API for exactly this: it runs the callbacks that are still pending at the end of the
    # request — callbacks discarded by a rolled-back savepoint are NOT among them, so the
    # rollback property this fix exists for is still enforced here, not papered over.
    with TestCase.captureOnCommitCallbacks(execute=True):
        return client.post(
            "/graphql/account",
            data=json.dumps({"query": query, "variables": variables or {}}),
            content_type="application/json",
            **extra,
        )


def body(response):
    return json.loads(response.content)


def error_code(response):
    payload = body(response)
    errors = payload.get("errors") or []
    if not errors:
        return None
    return (errors[0].get("extensions") or {}).get("code")


class CapturingSender(services.EmailSender):
    def __init__(self):
        self.verify_tokens = []
        self.reset_tokens = []
        self.exists_notifications = []

    def send_email_verification(self, user, raw_token):
        self.verify_tokens.append(raw_token)

    def send_password_reset(self, user, raw_token):
        self.reset_tokens.append(raw_token)

    def send_account_exists(self, email):
        self.exists_notifications.append(email)


@pytest.fixture
def sender():
    captured = CapturingSender()
    services.set_email_sender(captured)
    yield captured
    services.set_email_sender(services.EmailSender())


REGISTER = """
    mutation Register($input: RegisterCustomerUserInput!) {
      registerCustomerUser(input: $input) { accepted }
    }
"""
VERIFY = "mutation Verify($t: String!) { verifyEmail(token: $t) { verified } }"
LOGIN = """
    mutation Login($input: LoginInput!) {
      login(input: $input) { sessionToken expiresAt role orgId }
    }
"""
REFRESH = "mutation { refreshSession { sessionToken expiresAt } }"
LOGOUT = "mutation Logout($all: Boolean) { logout(allSessions: $all) { revoked } }"
REQUEST_RESET = "mutation Req($e: String!) { requestPasswordReset(email: $e) { accepted } }"
CONFIRM_RESET = """
    mutation Confirm($input: ConfirmPasswordResetInput!) {
      confirmPasswordReset(input: $input) { reset }
    }
"""
VIEWER = "query { accountViewer { surface actorId orgId } }"


def register_input(idem="signup-000001", email="pastor@grace.example", password="correct-horse-battery", **over):
    payload = {
        "idempotencyKey": idem,
        "email": email,
        "password": password,
        "orgName": "Grace Chapel",
        "country": "NG",
    }
    payload.update(over)
    return {"input": payload}


def signup_and_verify(client, sender, *, email="pastor@grace.example", password="correct-horse-battery", idem="sv-signup-0001"):
    post_account(client, REGISTER, register_input(idem=idem, email=email, password=password))
    token = sender.verify_tokens[-1]
    post_account(client, VERIFY, {"t": token})
    return email, password


# --- AUTH-2: signup --------------------------------------------------------
@pytest.mark.django_db
def test_signup_new_email_creates_invited_admin_and_trial_org(client, sender):
    resp = post_account(client, REGISTER, register_input())
    assert body(resp)["data"]["registerCustomerUser"]["accepted"] is True

    user = CustomerUser.objects.get()
    assert user.status == CustomerUserStatus.INVITED
    assert user.role == CustomerRole.ADMIN
    assert user.email_verified_at is None
    assert user.email == "pastor@grace.example"

    org = CustomerOrg.objects.get(id=user.customer_id)
    assert org.status == "TRIAL" and org.plan == "TRIAL"
    assert org.created_by_actor_id.startswith("self_signup:")  # namespaced per-email (finding-5 fix)
    # exactly one EMAIL_VERIFY token minted, delivered once via the seam
    assert len(sender.verify_tokens) == 1
    assert CredentialToken.objects.filter(purpose=CredentialTokenPurpose.EMAIL_VERIFY).count() == 1


@pytest.mark.django_db
def test_password_is_hashed_never_plaintext(client, sender):
    post_account(client, REGISTER, register_input(password="s3cret-passphrase"))
    user = CustomerUser.objects.get()
    assert user.password_hash != "s3cret-passphrase"
    assert check_password("s3cret-passphrase", user.password_hash)
    # never echoed in any response
    resp = post_account(client, REGISTER, register_input(idem="signup-000002", email="two@grace.example", password="s3cret-passphrase"))
    assert "s3cret-passphrase" not in resp.content.decode()


@pytest.mark.django_db
def test_signup_existing_email_is_uniform_and_creates_no_duplicate(client, sender):
    post_account(client, REGISTER, register_input(idem="dup-signup-0001"))
    resp = post_account(client, REGISTER, register_input(idem="dup-signup-0002"))  # same email, new idem
    assert body(resp)["data"]["registerCustomerUser"]["accepted"] is True
    assert CustomerUser.objects.filter(email="pastor@grace.example").count() == 1
    # the real owner is notified out-of-band; the caller is never told the account exists
    assert sender.exists_notifications == ["pastor@grace.example"]


@pytest.mark.django_db
def test_signup_idempotent_replay_same_key(client, sender):
    post_account(client, REGISTER, register_input(idem="replay-00001"))
    post_account(client, REGISTER, register_input(idem="replay-00001"))
    assert CustomerUser.objects.count() == 1
    assert CustomerOrg.objects.count() == 1


@pytest.mark.django_db
def test_two_different_emails_same_idempotency_key_both_register(client, sender):
    # Finding-5 fix: self-signup idempotency is namespaced PER-EMAIL, so a shared/colliding client
    # key cannot alias two distinct signups and silently drop the second. Also covers finding-3:
    # two same-named orgs get distinct slugs (no slug-collision mis-caught as a replay).
    post_account(client, REGISTER, register_input(idem="shared-key-0001", email="alpha@grace.example"))
    post_account(client, REGISTER, register_input(idem="shared-key-0001", email="bravo@grace.example"))
    assert CustomerUser.objects.filter(email="alpha@grace.example").count() == 1
    assert CustomerUser.objects.filter(email="bravo@grace.example").count() == 1
    assert CustomerOrg.objects.count() == 2
    assert CustomerOrg.objects.values_list("slug", flat=True).distinct().count() == 2


@pytest.mark.django_db
def test_signup_weak_password_rejected(client, sender):
    resp = post_account(client, REGISTER, register_input(password="short"))
    assert error_code(resp) == "VALIDATION_FAILED"
    assert CustomerUser.objects.count() == 0


@pytest.mark.django_db
def test_signup_audit_failure_rolls_back_everything(client, sender, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("audit down")

    monkeypatch.setattr("selahcue_api.apps.accounts.services.record_audit_event", boom)
    post_account(client, REGISTER, register_input())
    assert CustomerUser.objects.count() == 0
    assert CustomerOrg.objects.count() == 0
    assert sender.verify_tokens == [], "a rolled-back signup must not send a verification email"


@pytest.mark.django_db(transaction=True)
def test_rolled_back_signup_queues_no_verification_email(sender):
    """The dispatch is registered with `transaction.on_commit`, so it must not fire when the
    surrounding transaction rolls back. This ran inline until now: the email was published to
    Redis mid-transaction, and a rollback left a real message in the broker carrying a token
    for a CredentialToken row that no longer existed — the recipient got a link that fails
    validation with no explanation.

    `transaction=True` because a rollback has to be a REAL one: under the default
    `django_db` the test's own atomic block never commits, so nothing here would be observable.
    """
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            services.register_customer_user(
                services.RegisterCustomerUserData(
                    idempotency_key="rollback-0001",
                    email="rollback@grace.example",
                    password="correct-horse-battery",
                    org_name="Rollback Chapel",
                    country="NG",
                )
            )
            raise RuntimeError("caller aborted after the signup succeeded")

    assert CustomerUser.objects.filter(email="rollback@grace.example").count() == 0
    assert sender.verify_tokens == [], (
        "the verification email was dispatched for a signup that never committed"
    )


# --- AUTH-3: email verification -------------------------------------------
@pytest.mark.django_db
def test_verify_email_activates_user(client, sender):
    post_account(client, REGISTER, register_input())
    token = sender.verify_tokens[-1]
    resp = post_account(client, VERIFY, {"t": token})
    assert body(resp)["data"]["verifyEmail"]["verified"] is True
    user = CustomerUser.objects.get()
    assert user.status == CustomerUserStatus.ACTIVE
    assert user.email_verified_at is not None


@pytest.mark.django_db
def test_verify_token_is_single_use(client, sender):
    post_account(client, REGISTER, register_input())
    token = sender.verify_tokens[-1]
    post_account(client, VERIFY, {"t": token})
    resp = post_account(client, VERIFY, {"t": token})
    assert error_code(resp) == "VALIDATION_FAILED"


@pytest.mark.django_db
def test_verify_unknown_expired_consumed_are_uniform(client, sender):
    # unknown token
    assert error_code(post_account(client, VERIFY, {"t": "SC-EVF-does-not-exist"})) == "VALIDATION_FAILED"
    # expired token
    post_account(client, REGISTER, register_input())
    raw = sender.verify_tokens[-1]
    ct = CredentialToken.objects.get(purpose=CredentialTokenPurpose.EMAIL_VERIFY)
    ct.expires_at = timezone.now() - timezone.timedelta(minutes=1)
    ct.save(update_fields=["expires_at"])
    assert error_code(post_account(client, VERIFY, {"t": raw})) == "VALIDATION_FAILED"


# --- 86akcn92k: verify_email gets a per-client-IP budget --------------------------------
# `verify_email` was unauthenticated with no budget at all — scoped OUT of 86akcmfd4's
# required follow-up because DEC-013 named the RESET paths specifically, and this endpoint's
# 256-bit token entropy means a throttle here bounds flood cost only, not a practical guess.
# Still worth closing: an unauthenticated endpoint with literally no ceiling is reachable at
# an unlimited rate by definition.
@pytest.mark.django_db
def test_verify_email_nth_call_is_refused_and_earlier_calls_are_not(client, settings, sender):
    """Asserts the WHOLE sequence, not just the last response — inspecting only call 3 would
    equally pass for a limiter that refuses everything or one that trips on the wrong call.
    Uses three DISTINCT invalid tokens across the pre-limit calls (mirroring
    `test_confirm_reset_nth_call_is_refused_and_earlier_calls_are_not` in
    test_password_reset_throttle.py) — proof the budget is spent by request COUNT, not by
    which token was offered."""
    settings.SELAHCUE_THROTTLE_VERIFY_EMAIL_IP = (2, 3600)

    first = post_account(client, VERIFY, {"t": "SC-EVF-guess-one"})
    second = post_account(client, VERIFY, {"t": "SC-EVF-guess-two"})
    third = post_account(client, VERIFY, {"t": "SC-EVF-guess-three"})

    # Calls 1-2 are WITHIN budget: each reaches the service and gets the same collapsed
    # VALIDATION_FAILED every invalid token gets today — proof they were refused by TOKEN
    # validity, not by the limiter.
    assert error_code(first) == "VALIDATION_FAILED"
    assert error_code(second) == "VALIDATION_FAILED"
    # Call 3 is the FIRST the limiter refuses, regardless of what token it carried.
    assert error_code(third) == "RATE_LIMITED", (
        f"expected the 3rd call over a (2, 3600) budget to be refused, got {error_code(third)!r}"
    )


@pytest.mark.django_db
def test_verify_email_budget_is_per_client_ip(client, settings):
    """The POSITIVE CONTROL the ticket calls for by name: without this, "refused at N" is
    indistinguishable from a limiter that shares ONE bucket across every caller."""
    settings.SELAHCUE_THROTTLE_VERIFY_EMAIL_IP = (1, 3600)

    def call(remote_addr):
        response = client.post(
            "/graphql/account",
            data=json.dumps({"query": VERIFY, "variables": {"t": "SC-EVF-does-not-exist"}}),
            content_type="application/json",
            REMOTE_ADDR=remote_addr,
        )
        return error_code(response)

    assert call("203.0.113.21") == "VALIDATION_FAILED"
    assert call("203.0.113.21") == "RATE_LIMITED", "the SAME address must exhaust its own budget"
    assert call("203.0.113.22") == "VALIDATION_FAILED", "a DIFFERENT address must have its own, unspent budget"
    assert call("203.0.113.22") == "RATE_LIMITED"


@pytest.mark.django_db
def test_verify_email_throttle_does_not_disturb_the_no_oracle_collapse(client, settings, sender):
    """The new RATE_LIMITED code must not become a sixth, more-informative token-failure
    code: within budget, unknown/expired/consumed tokens must still collapse to the SAME
    VALIDATION_FAILED they always have (this is `test_verify_unknown_expired_consumed_are_
    uniform`'s own contract — this test just pins that the throttle addition didn't touch
    it)."""
    settings.SELAHCUE_THROTTLE_VERIFY_EMAIL_IP = (100, 3600)
    assert error_code(post_account(client, VERIFY, {"t": "SC-EVF-does-not-exist"})) == "VALIDATION_FAILED"

    post_account(client, REGISTER, register_input())
    raw = sender.verify_tokens[-1]
    ct = CredentialToken.objects.get(purpose=CredentialTokenPurpose.EMAIL_VERIFY)
    ct.expires_at = timezone.now() - timezone.timedelta(minutes=1)
    ct.save(update_fields=["expires_at"])
    assert error_code(post_account(client, VERIFY, {"t": raw})) == "VALIDATION_FAILED"


@pytest.mark.django_db
def test_raw_verify_token_never_stored_plaintext(client, sender):
    post_account(client, REGISTER, register_input())
    raw = sender.verify_tokens[-1]
    ct = CredentialToken.objects.get(purpose=CredentialTokenPurpose.EMAIL_VERIFY)
    assert raw != ct.token_hash and raw not in ct.token_hash
    assert raw != ct.token_fingerprint
    assert ct.masked_token != raw


def test_credential_token_hash_is_per_token_and_distinct_from_the_fingerprint():
    """WHAT THIS PINS: the DEC-013 cheap-hash mint itself — `_credential_token_hash`.

    MUST FAIL if either control it names is removed:
      1. returning a CONSTANT for every token (the hash stops depending on the token);
      2. dropping the DISTINCT LABEL so `token_hash` is an exact copy of `token_fingerprint`
         — the precise thing the function's own docstring says must not happen ("a column
         that merely repeated the lookup key would confirm nothing").

    The pre-existing row assertions nearby (`raw not in token_hash`) survive BOTH mutations:
    a constant contains no raw token, and neither does the fingerprint. Hence this test.

    Pure: HMAC over SECRET_KEY, no DB, so no `django_db` marker is needed.
    """
    token_a = "SC-EVF-" + "a" * 32
    token_b = "SC-EVF-" + "b" * 32
    assert token_a != token_b, "the two sample tokens must differ or nothing below is a test"

    hash_a = services._credential_token_hash(token_a)
    hash_b = services._credential_token_hash(token_b)
    fingerprint_a = services._fingerprint(token_a)
    fingerprint_b = services._fingerprint(token_b)

    # POSITIVE CONTROL, asserted BEFORE the contract. Without it, "the values differ" is
    # indistinguishable from a DEAD mechanism: a function returning fresh randomness per call
    # would satisfy every distinctness assertion below while hashing nothing.
    assert hash_a == services._credential_token_hash(token_a), (
        "_credential_token_hash is not deterministic, so the distinctness contracts below "
        "were not exercised — they would also pass for a function returning fresh randomness"
    )
    assert len(hash_a) == 64 and set(hash_a) <= set("0123456789abcdef"), (
        f"_credential_token_hash no longer returns an HMAC-SHA256 hex digest ({hash_a!r}), so "
        "the shape this column is specified to hold was not exercised"
    )
    # The comparison below is only meaningful while `_fingerprint` is itself token-dependent.
    assert fingerprint_a != fingerprint_b, (
        "_fingerprint is not input-dependent, so 'token_hash differs from token_fingerprint' "
        "was not exercised against a live lookup key"
    )

    # CONTRACT 1 — dies if the hash is a constant.
    assert hash_a != hash_b, (
        "_credential_token_hash returned the same digest for two DIFFERENT tokens: the "
        "at-rest hash no longer depends on the token it is supposed to confirm"
    )

    # CONTRACT 2 — dies if the distinct label is dropped.
    assert hash_a != fingerprint_a and hash_b != fingerprint_b, (
        "_credential_token_hash produced the same value as _fingerprint for the same token: "
        "the DEC-013 distinct label is gone, so token_hash is an exact copy of the lookup "
        "key token_fingerprint and confirms nothing"
    )


# --- AUTH-4: login / session / logout / refresh ---------------------------
@pytest.mark.django_db
def test_login_unknown_email_and_wrong_password_are_identical(client, sender):
    signup_and_verify(client, sender)
    unknown = post_account(client, LOGIN, {"input": {"email": "nobody@grace.example", "password": "whatever-long-1"}})
    wrong = post_account(client, LOGIN, {"input": {"email": "pastor@grace.example", "password": "wrong-password-12"}})
    assert error_code(unknown) == "UNAUTHENTICATED"
    assert error_code(wrong) == "UNAUTHENTICATED"
    assert body(unknown)["errors"][0]["message"] == body(wrong)["errors"][0]["message"]


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=False)
@pytest.mark.django_db
def test_login_success_mints_session_and_viewer_resolves_without_trust_headers(client, sender):
    email, password = signup_and_verify(client, sender)
    resp = post_account(client, LOGIN, {"input": {"email": email, "password": password}})
    data = body(resp)["data"]["login"]
    assert data["sessionToken"] and data["role"] == "ADMIN"
    # the session token authenticates the account surface with header-trust OFF
    viewer = post_account(client, VIEWER, bearer=data["sessionToken"])
    vd = body(viewer)["data"]["accountViewer"]
    assert vd["surface"] == "account" and vd["orgId"] == data["orgId"]


@pytest.mark.django_db
def test_login_unverified_is_policy_denied(client, sender):
    post_account(client, REGISTER, register_input())  # not verified
    resp = post_account(client, LOGIN, {"input": {"email": "pastor@grace.example", "password": "correct-horse-battery"}})
    assert error_code(resp) == "POLICY_DENIED"


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=False)
@pytest.mark.django_db
def test_logout_revokes_session_but_never_touches_device_tokens(client, sender):
    from selahcue_api.apps.devices.models import Device, DeviceStatus, DeviceToken, DeviceTokenStatus
    from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

    email, password = signup_and_verify(client, sender)
    token = body(post_account(client, LOGIN, {"input": {"email": email, "password": password}}))["data"]["login"]["sessionToken"]
    org = CustomerOrg.objects.get()
    lk = AppLicenseKey.objects.create(
        customer=org, key_type="TRIAL", status=LicenseKeyStatus.ACTIVATED,
        key_prefix="SC-X", key_suffix="ZZZZ", masked_key="SC-X...ZZZZ",
        secret_hash="x", secret_fingerprint="devfp", feature_scope="core", territory="GLOBAL",
        starts_at=timezone.now() - timezone.timedelta(days=1), expires_at=timezone.now() + timezone.timedelta(days=30),
        timezone="UTC", seat_limit=1, device_limit=1,
        generated_by_actor_id="staff", generated_reason="test fixture", idempotency_key="lk-1",
    )
    dev = Device.objects.create(
        license_key=lk, customer=org, device_public_id="dev_x", device_fingerprint="fp",
        platform="macos", status=DeviceStatus.ACTIVE, activated_by_actor_id="dev_x", idempotency_key="d-1",
    )
    dtok = DeviceToken.objects.create(
        device=dev, token_prefix="SC-DEV-AAAA", token_suffix="ZZZZ", masked_token="SC-DEV-AAAA...ZZZZ",
        token_hash="x", token_fingerprint="dtokfp", status=DeviceTokenStatus.ACTIVE,
        issued_at=timezone.now(), expires_at=timezone.now() + timezone.timedelta(days=30),
    )

    assert body(post_account(client, LOGOUT, bearer=token))["data"]["logout"]["revoked"] is True
    # account session is dead...
    assert error_code(post_account(client, VIEWER, bearer=token)) == "UNAUTHENTICATED"
    # ...but the device token is untouched (never-blank)
    dtok.refresh_from_db()
    assert dtok.status == DeviceTokenStatus.ACTIVE


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=False)
@pytest.mark.django_db
def test_refresh_rotates_the_token(client, sender):
    email, password = signup_and_verify(client, sender)
    first = body(post_account(client, LOGIN, {"input": {"email": email, "password": password}}))["data"]["login"]["sessionToken"]
    rotated = body(post_account(client, REFRESH, bearer=first))["data"]["refreshSession"]["sessionToken"]
    assert rotated != first
    assert error_code(post_account(client, VIEWER, bearer=first)) == "UNAUTHENTICATED"
    assert body(post_account(client, VIEWER, bearer=rotated))["data"]["accountViewer"]["surface"] == "account"


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=False)
@pytest.mark.django_db
def test_expired_session_returns_no_actor(client, sender):
    email, password = signup_and_verify(client, sender)
    token = body(post_account(client, LOGIN, {"input": {"email": email, "password": password}}))["data"]["login"]["sessionToken"]
    session = CustomerSession.objects.get()
    # Keep expires_at > issued_at (CHECK constraint): backdate both into the past.
    session.issued_at = timezone.now() - timezone.timedelta(days=40)
    session.expires_at = timezone.now() - timezone.timedelta(days=1)
    session.save(update_fields=["issued_at", "expires_at"])
    assert error_code(post_account(client, VIEWER, bearer=token)) == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_login_lockout_blocks_without_leaking_a_distinct_code(client, sender):
    signup_and_verify(client, sender)
    for _ in range(services.LOGIN_LOCKOUT_THRESHOLD):
        post_account(client, LOGIN, {"input": {"email": "pastor@grace.example", "password": "definitely-wrong"}})
    # Even the CORRECT password is now refused — proof the account is locked (it would otherwise
    # succeed) — but the code is UNAUTHENTICATED, NOT a distinct RATE_LIMITED that would reveal the
    # account exists.
    locked = post_account(client, LOGIN, {"input": {"email": "pastor@grace.example", "password": "correct-horse-battery"}})
    assert error_code(locked) == "UNAUTHENTICATED"
    # A locked (existing) account is indistinguishable from an unknown email — no enumeration oracle.
    unknown = post_account(client, LOGIN, {"input": {"email": "nobody@grace.example", "password": "correct-horse-battery"}})
    assert error_code(unknown) == "UNAUTHENTICATED"
    assert body(locked)["errors"][0]["message"] == body(unknown)["errors"][0]["message"]


# --- AUTH-5: password reset ------------------------------------------------
@pytest.mark.django_db
def test_request_reset_is_uniform_for_existing_and_missing(client, sender):
    signup_and_verify(client, sender)
    existing = post_account(client, REQUEST_RESET, {"e": "pastor@grace.example"})
    missing = post_account(client, REQUEST_RESET, {"e": "ghost@grace.example"})
    assert body(existing)["data"]["requestPasswordReset"]["accepted"] is True
    assert body(missing)["data"]["requestPasswordReset"]["accepted"] is True
    # only the existing account produced a token
    assert len(sender.reset_tokens) == 1


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=False)
@pytest.mark.django_db
def test_confirm_reset_changes_password_and_revokes_all_sessions(client, sender):
    email, password = signup_and_verify(client, sender)
    old_session = body(post_account(client, LOGIN, {"input": {"email": email, "password": password}}))["data"]["login"]["sessionToken"]
    post_account(client, REQUEST_RESET, {"e": email})
    reset_token = sender.reset_tokens[-1]
    new_password = "brand-new-passphrase-9"
    resp = post_account(client, CONFIRM_RESET, {"input": {"token": reset_token, "newPassword": new_password}})
    assert body(resp)["data"]["confirmPasswordReset"]["reset"] is True

    # old session invalidated by the password change
    assert error_code(post_account(client, VIEWER, bearer=old_session)) == "UNAUTHENTICATED"
    # new password works, old password does not
    assert error_code(post_account(client, LOGIN, {"input": {"email": email, "password": password}})) == "UNAUTHENTICATED"
    ok = post_account(client, LOGIN, {"input": {"email": email, "password": new_password}})
    assert body(ok)["data"]["login"]["sessionToken"]


@pytest.mark.django_db
def test_reset_token_is_single_use(client, sender):
    email, password = signup_and_verify(client, sender)
    post_account(client, REQUEST_RESET, {"e": email})
    reset_token = sender.reset_tokens[-1]
    post_account(client, CONFIRM_RESET, {"input": {"token": reset_token, "newPassword": "first-new-passphrase"}})
    resp = post_account(client, CONFIRM_RESET, {"input": {"token": reset_token, "newPassword": "second-new-passphrase"}})
    assert error_code(resp) == "VALIDATION_FAILED"


# --- FR-551 / DEC-012(a): the token is validated BEFORE the password --------
#
# WHAT WAS WRONG. `confirm_password_reset` used to call `_validate_password` before it
# looked the token up, and both raised the same collapsed VALIDATION_FAILED. A user
# holding a perfectly good link who typed a short password was told their LINK was
# broken, fetched a fresh link, retyped the same short password, and looped.
#
# WHY THE SPLIT IS SAFE is written out ONCE, beside `ErrorCode.PASSWORD_INVALID` in
# `selahcue_api/graphql/errors.py`. Do not restate the argument here — it was already
# maintained in four places and one copy had drifted by the first review round. This block
# owns exactly one thing the canonical copy cannot: WHICH TEST CATCHES WHICH MUTATION.
#
# WHAT EACH TEST BELOW ACTUALLY GUARDS. The catch map is the point of this block: the
# mutations are different, and different tests catch each. Do not delete a test as
# redundant without re-deriving this table — and keep it ACCURATE, because a catch map
# that overstates one test's reach is worse than none. Two earlier versions of this block
# undercounted mutation B: the first said ONE test caught it, the correction said THREE, and
# eleven lines below the same block already said FOUR and listed four. Neither of the first
# two was re-run. Measured, B was caught by FOUR before review round 2 and by FIVE now that a
# third live-token test exists.
#
# The counts below are MEASURED, by applying each mutation and running this whole file.
# Do not adjust one from reasoning alone; re-run it.
#
#   Mutation A — move the `_validate_password` call back above the token lookup, keeping
#                `code=ErrorCode.PASSWORD_INVALID`. The ORDER is wrong again.
#                Caught by TWO tests (2 failed, 35 passed): the two dead-token tests,
#                `..._never_mentions_the_password` and `..._stays_collapsed`. Under A any
#                token that is not live answers PASSWORD_INVALID and hands an
#                UNAUTHENTICATED caller a brand-new oracle.
#                NOT caught by the live-token tests, which still see PASSWORD_INVALID.
#
#   Mutation B — the full revert: move it back AND drop the code argument.
#                Caught by FIVE tests (5 failed, 32 passed): all three live-token tests,
#                which then see the collapsed VALIDATION_FAILED — the original defect —
#                `test_a_rejected_password_does_not_burn_the_users_link`, and
#                `..._stays_collapsed` via its positive control.
#
#   Mutation F — move the call below the row lookup but ABOVE the purpose/consumed/expired
#                block. The subtlest, and the most dangerous.
#                Caught ONLY by `test_a_dead_but_real_token_with_a_weak_password_stays_collapsed`
#                (1 failed, 36 passed).
#                Under F a token that EXISTS but is spent/expired/wrong-purpose answers
#                PASSWORD_INVALID while an unknown token still answers VALIDATION_FAILED —
#                so an unauthenticated caller can tell "this token never existed" from
#                "this token existed", with NO valid token of their own. That is a direct
#                FR-529 breach and strictly worse than the sanctioned live-token oracle.
#                Every other test in this file stays GREEN under F. It was found in review,
#                not by the suite, which is exactly why the test below exists.
#
#   Mutation D — move the call BELOW `token.consumed_at = now`.
#                Caught by NOTHING (37 passed here; 523 passed across the whole API suite),
#                and that is CORRECT, not a gap: the link-preservation property comes from the
#                enclosing `transaction.atomic()` rolling the consume back, so D changes
#                no observable behaviour. `test_a_rejected_password_does_not_burn_the_users_link`
#                guards the PROPERTY, never the placement — see its docstring. What guards
#                the transaction boundary itself is
#                `test_a_failed_reset_rolls_back_the_consume_and_the_password`, and D
#                together with `atomic()` removed is caught by FIVE tests. The redundancy is
#                real defence in depth, not a gap with a justification attached.
#
#   Mutation P — delete `token.purpose != CredentialTokenPurpose.PASSWORD_RESET` from the
#                guard, so an EMAIL_VERIFY token can reset a password.
#                Caught by THREE tests (3 failed, 34 passed here; 3 failed, 520 passed
#                across the whole API suite):
#                `test_a_live_verify_token_is_refused_by_the_reset_mutation`,
#                `test_every_token_failure_stays_mutually_indistinguishable` and
#                `..._stays_collapsed`.
#                Before review round 2 it was caught by NOTHING in the repository — all 520
#                tests passed with the clause deleted. Every wrong-purpose fixture was built
#                from `sender.verify_tokens[-1]` AFTER `signup_and_verify` had spent it, so
#                `consumed_at` did the refusing and the purpose clause never decided
#                anything. The fixtures below are now LIVE verify tokens from an unverified
#                second registration, which is the only shape that reaches this clause.
#
#   Mutation U — drop `<= MAX_PASSWORD_LENGTH` from `_validate_password`, removing the
#                upper length bound.
#                Caught by ONE test (1 failed, 36 passed here; 1 failed, 522 passed across
#                the whole API suite):
#                `test_a_live_token_with_an_over_long_password_blames_the_password`.
#                Its positive control catches a SECOND mutation nothing else does: the
#                bound moved by one, `<=` to `<` (1 failed, 36 passed).
#                Before review round 2 it was caught by NOTHING — 520 passed. The lower
#                bound and the whitespace branch were both pinned; the third branch of the
#                same condition was exercised by no test in the repository.
#
# `test_signup_weak_password_rejected` above is NOT coverage for any of this: signup is a
# different function and would keep passing however broken this path became.

# 5 characters — below MIN_PASSWORD_LENGTH, so it can only fail the LENGTH branch.
SHORT_PASSWORD = "short"
# Whitespace only, but LONG ENOUGH to clear the length rule, so it can only fail the
# all-whitespace branch. That isolation is the point.
BLANK_PASSWORD = " " * (services.MIN_PASSWORD_LENGTH + 2)
# The two sides of the UPPER length bound, one character apart. The pair is what makes the
# test bite: `OVER_LONG_PASSWORD` alone proves only that SOME long password is refused,
# which stays true if the bound creeps downwards. `AT_LIMIT_PASSWORD` pins WHERE the
# boundary is by being accepted.
AT_LIMIT_PASSWORD = "x" * services.MAX_PASSWORD_LENGTH
OVER_LONG_PASSWORD = "x" * (services.MAX_PASSWORD_LENGTH + 1)
# The password used where the request is meant to SUCCEED. A literal here is what let
# `test_a_failed_reset_rolls_back_the_consume_and_the_password` go quietly vacuous under a
# raised MIN_PASSWORD_LENGTH while its siblings failed loudly.
GOOD_PASSWORD = "a-perfectly-good-passphrase"

# Pin the premises. Each assertion below must be able to FAIL on a plausible edit —
# an assertion whose subject is derived from the constant it is compared against is
# arithmetic wearing a guard's clothes, and review round 2 removed one of those.
#
# If MIN_PASSWORD_LENGTH is ever lowered past 5, `SHORT_PASSWORD` becomes a VALID password
# and every test below quietly stops testing anything — passing for the wrong reason. Fail
# loudly at import instead.
assert len(SHORT_PASSWORD) < services.MIN_PASSWORD_LENGTH, (
    "SHORT_PASSWORD is no longer short enough to be rejected — the FR-551 tests would pass vacuously"
)
# `MIN <= len(BLANK_PASSWORD)` was the other half of this assertion and is arithmetic:
# BLANK_PASSWORD is MIN + 2 spaces, so it can never fire. What CAN fire is the property the
# constant exists for, and the upper bound if MAX is ever pulled below MIN + 2.
assert BLANK_PASSWORD.strip() == "", (
    "BLANK_PASSWORD is no longer all-whitespace — it would stop isolating the whitespace branch"
)
assert len(BLANK_PASSWORD) <= services.MAX_PASSWORD_LENGTH, (
    "BLANK_PASSWORD no longer isolates the all-whitespace branch — it would fail on LENGTH instead"
)
assert AT_LIMIT_PASSWORD.strip() and OVER_LONG_PASSWORD.strip(), (
    "the length-bound passwords became blank — they would fail the WHITESPACE branch, not LENGTH"
)
assert services.MIN_PASSWORD_LENGTH <= services.MAX_PASSWORD_LENGTH, (
    "MAX_PASSWORD_LENGTH fell below MIN_PASSWORD_LENGTH — no password satisfies the policy and "
    "the upper-bound test would pass for the wrong reason"
)
assert services.MIN_PASSWORD_LENGTH <= len(GOOD_PASSWORD) <= services.MAX_PASSWORD_LENGTH, (
    "GOOD_PASSWORD no longer satisfies the password policy — every test that expects the reset "
    "to SUCCEED would instead be measuring a rejected password"
)


def live_reset_token(client, sender, *, email="pastor@grace.example"):
    """Sign up, verify, and return a freshly minted, live PASSWORD_RESET token."""
    signup_and_verify(client, sender, email=email)
    post_account(client, REQUEST_RESET, {"e": email})
    return sender.reset_tokens[-1]


def token_row(raw_token):
    return CredentialToken.objects.get(token_fingerprint=services._fingerprint(raw_token))


def error_message(response):
    errors = body(response).get("errors") or []
    return errors[0].get("message") if errors else None


def live_verify_token(client, sender, *, email="deacon@grace.example", idem="live-verify-0001"):
    """Register WITHOUT verifying, and return the resulting EMAIL_VERIFY token — live and
    UNCONSUMED.

    This is the only fixture that can exercise the purpose clause in `confirm_password_reset`.
    `signup_and_verify` SPENDS the verify token it mints, so `sender.verify_tokens[-1]` after
    it is a consumed token: offered to the reset mutation it is refused by `consumed_at`, and
    `token.purpose != PASSWORD_RESET` never decides anything. Every wrong-purpose fixture in
    this file was built that way until review round 2, which is why deleting the purpose clause
    left all 520 tests in the repository passing.
    """
    post_account(client, REGISTER, register_input(idem=idem, email=email))
    return sender.verify_tokens[-1]


def assert_only_the_purpose_clause_can_refuse(raw_token):
    """Premise for every wrong-purpose case: the token must be REAL, UNCONSUMED and UNEXPIRED,
    so the only thing that can refuse it is its PURPOSE.

    Asserting the purpose alone — which is what this file used to do — pins the wrong property.
    It confirms the fixture is a verification token and says nothing about whether the clause
    under test is the one doing the work.
    """
    row = token_row(raw_token)
    assert row.purpose == CredentialTokenPurpose.EMAIL_VERIFY, (
        "the wrong-purpose case was NOT set up — this is not a verification token"
    )
    assert row.consumed_at is None, (
        "the wrong-purpose token is already SPENT, so `consumed_at` refuses it and the purpose "
        "clause is never reached — this case proves nothing about purpose"
    )
    assert row.expires_at > timezone.now(), (
        "the wrong-purpose token has EXPIRED, so `expires_at` refuses it and the purpose clause "
        "is never reached — this case proves nothing about purpose"
    )


@pytest.mark.django_db
def test_a_live_token_with_a_short_password_blames_the_password(client, sender):
    """The regression test for the defect itself. Catches mutation B."""
    reset_token = live_reset_token(client, sender)

    resp = post_account(client, CONFIRM_RESET, {"input": {"token": reset_token, "newPassword": SHORT_PASSWORD}})

    # POSITIVE CONTROL, asserted FIRST and before the contract: prove the token was
    # genuinely live, so a PASSWORD_INVALID cannot be mistaken for a token that was never
    # any good. Without this the assertion below could pass on a dead token.
    assert token_row(reset_token).consumed_at is None, (
        "the token was already spent, so the valid-token-plus-weak-password case was NOT exercised"
    )
    assert error_code(resp) == "PASSWORD_INVALID", (
        "a user holding a WORKING link was told VALIDATION_FAILED — indistinguishable from a "
        "dead link, which is the FR-551 loop returning"
    )


@pytest.mark.django_db
def test_a_live_token_with_an_all_whitespace_password_blames_the_password(client, sender):
    """The other `_validate_password` branch: long enough, but nothing but spaces."""
    reset_token = live_reset_token(client, sender)

    resp = post_account(client, CONFIRM_RESET, {"input": {"token": reset_token, "newPassword": BLANK_PASSWORD}})

    assert token_row(reset_token).consumed_at is None, (
        "the token was already spent, so the whitespace branch was NOT exercised behind a live token"
    )
    assert error_code(resp) == "PASSWORD_INVALID"


@pytest.mark.django_db
def test_a_live_token_with_an_over_long_password_blames_the_password(client, sender):
    """The THIRD branch of `_validate_password` — the UPPER length bound. Catches mutation U.

    Nothing in the repository exercised it before this test: with `<= MAX_PASSWORD_LENGTH`
    deleted from the condition, all 520 tests passed. The lower bound and the all-whitespace
    branch were each pinned; this half of the same `if` was not.
    """
    reset_token = live_reset_token(client, sender)

    # PREMISE, asserted BEFORE the request, deliberately. Its siblings assert liveness after
    # theirs, where it doubles as a contract — but here the mutation this test exists to catch
    # (the bound removed) makes the request SUCCEED and consume the token, so a post-request
    # liveness assertion would fire first and report "the token was already spent", which is
    # the wrong diagnosis for the right failure.
    assert token_row(reset_token).consumed_at is None, (
        "the reset token was not live before the request, so this case never got behind a "
        "validated token at all"
    )

    rejected = post_account(
        client, CONFIRM_RESET, {"input": {"token": reset_token, "newPassword": OVER_LONG_PASSWORD}}
    )
    assert error_code(rejected) == "PASSWORD_INVALID", (
        f"a password one character past MAX_PASSWORD_LENGTH answered {error_code(rejected)}. If "
        "that is None the reset SUCCEEDED: the upper length bound is gone, the server no longer "
        "matches the client's mirror of the same rule, and an arbitrarily long password now "
        "reaches make_password, where KDF work scales with its length"
    )
    assert token_row(reset_token).consumed_at is None, (
        "the over-long password was refused but the user's link was burnt anyway"
    )

    # POSITIVE CONTROL, on the SAME link: exactly MAX_PASSWORD_LENGTH is still ACCEPTED. Without
    # it the assertion above also passes if the bound has crept DOWNWARDS, or if long passwords
    # are refused for some unrelated reason — "refused" would not be evidence that the boundary
    # is where the policy says it is. The pair is one character apart, so it pins the boundary
    # itself rather than the fact that some long password is rejected. Measured: `<=` changed to
    # `<` on the upper bound is caught here and nowhere else.
    accepted = post_account(
        client, CONFIRM_RESET, {"input": {"token": reset_token, "newPassword": AT_LIMIT_PASSWORD}}
    )
    assert error_code(accepted) is None, (
        f"a password of exactly MAX_PASSWORD_LENGTH was refused with {error_code(accepted)} — the "
        "bound has moved, so the refusal asserted above proves nothing about where it is"
    )
    assert body(accepted)["data"]["confirmPasswordReset"]["reset"] is True


@pytest.mark.django_db
def test_a_rejected_password_does_not_burn_the_users_link(client, sender):
    """A failed password must cost the user nothing. Their link still works.

    SCOPE, precisely. This guards the user-visible PROPERTY, not the placement of the
    `_validate_password` call relative to the consume. Moving that call below
    `token.consumed_at = now` (mutation D) leaves this test green, because the enclosing
    `transaction.atomic()` rolls the consume back either way. The transaction is what
    delivers the property; the placement is redundant defence in depth.

    What this test DOES catch is mutation B — the full revert — via the PASSWORD_INVALID
    assertion below. What guards the transaction boundary is
    `test_a_failed_reset_rolls_back_the_consume_and_the_password`.
    """
    email = "pastor@grace.example"
    reset_token = live_reset_token(client, sender, email=email)

    rejected = post_account(client, CONFIRM_RESET, {"input": {"token": reset_token, "newPassword": SHORT_PASSWORD}})
    assert error_code(rejected) == "PASSWORD_INVALID"
    assert token_row(reset_token).consumed_at is None

    # THE POINT: the SAME link, second attempt, now with an acceptable password.
    good_password = "a-long-enough-passphrase"
    accepted = post_account(client, CONFIRM_RESET, {"input": {"token": reset_token, "newPassword": good_password}})
    assert body(accepted)["data"]["confirmPasswordReset"]["reset"] is True
    assert body(post_account(client, LOGIN, {"input": {"email": email, "password": good_password}}))["data"]["login"]["sessionToken"]


@pytest.mark.django_db
def test_a_dead_token_with_a_weak_password_never_mentions_the_password(client, sender):
    """The ORDERING pin, and the anti-enumeration guard. Catches mutation A.

    An unauthenticated caller must never be able to tell a live token from a dead one, and
    PASSWORD_INVALID would tell them exactly that: it can only be answered from behind a
    validated token, so receiving it is proof the token was good.
    """
    signup_and_verify(client, sender)

    resp = post_account(
        client, CONFIRM_RESET, {"input": {"token": "SC-PRS-not-a-real-token", "newPassword": SHORT_PASSWORD}}
    )

    assert error_code(resp) == "VALIDATION_FAILED", (
        "a caller with NO valid token learned that their password was the problem — which "
        "means the password is being checked before the token again, and PASSWORD_INVALID "
        "has become a live-token oracle (FR-529)"
    )


@pytest.mark.django_db
def test_a_live_verify_token_is_refused_by_the_reset_mutation(client, sender):
    """The PURPOSE clause, which nothing in the repository guarded. Catches mutation P.

    A token minted for EMAIL_VERIFY must not reset a password, even while it is perfectly
    live. Deleting `token.purpose != CredentialTokenPurpose.PASSWORD_RESET` from the guard
    left all 520 tests passing before this test existed — every wrong-purpose fixture in the
    file was a token `signup_and_verify` had already spent, so `consumed_at` was doing the
    refusing.

    The password is deliberately VALID and the token deliberately LIVE, so the purpose is the
    only thing left that can refuse this request.
    """
    verify_token = live_verify_token(client, sender)
    assert_only_the_purpose_clause_can_refuse(verify_token)

    resp = post_account(
        client, CONFIRM_RESET, {"input": {"token": verify_token, "newPassword": GOOD_PASSWORD}}
    )

    assert error_code(resp) == "VALIDATION_FAILED", (
        f"an EMAIL_VERIFY token answered {error_code(resp)} instead of the collapsed code. If "
        "that is None the reset SUCCEEDED, and a verification link — which is emailed on every "
        "signup attempt for an address, including one that already has an account — can now take "
        "the account over"
    )
    assert token_row(verify_token).consumed_at is None, (
        "the refused verification token was consumed anyway, so the caller has also burnt it"
    )


@pytest.mark.django_db
def test_every_token_failure_stays_mutually_indistinguishable(client, sender):
    """FR-529 / CON-P6, unchanged by this fix. `confirm_password_reset`'s docstring names FIVE
    collapsed classes — malformed, unknown, wrong-purpose, consumed, expired — and this test
    covers all five. It used to cover four: malformed was named by the service docstring and
    sent by no test in the repository.

    Every class must answer identically, same code AND same message, and none may leak
    PASSWORD_INVALID. Every request below deliberately carries a VALID password, so the only
    thing that can vary between them is the token.
    """
    email = "pastor@grace.example"
    signup_and_verify(client, sender, email=email)
    good_password = "another-fine-passphrase"

    # malformed. Three shapes, and they are NOT three code paths — worth saying, because the
    # docstring's flat list of five reads as if they were. An empty or whitespace-only token
    # raises at the `if not token_value` guard, ABOVE the transaction, and is the only malformed
    # shape with an exit of its own. A non-empty wrong-shape token is fingerprinted like any
    # other and misses, so it is `unknown` by construction and cannot diverge from it. Only the
    # first adds a distinct path; the third is here so nobody reads the docstring as claiming
    # more than that.
    empty = post_account(client, CONFIRM_RESET, {"input": {"token": "", "newPassword": good_password}})
    whitespace = post_account(client, CONFIRM_RESET, {"input": {"token": "   ", "newPassword": good_password}})
    wrong_shape = post_account(
        client, CONFIRM_RESET, {"input": {"token": "not-a-token-shape", "newPassword": good_password}}
    )

    # unknown
    unknown = post_account(client, CONFIRM_RESET, {"input": {"token": "SC-PRS-nobody-minted-this", "newPassword": good_password}})

    # consumed
    post_account(client, REQUEST_RESET, {"e": email})
    spent = sender.reset_tokens[-1]
    post_account(client, CONFIRM_RESET, {"input": {"token": spent, "newPassword": "a-first-new-passphrase"}})
    assert token_row(spent).consumed_at is not None, "the consumed case was NOT set up — token never spent"
    consumed = post_account(client, CONFIRM_RESET, {"input": {"token": spent, "newPassword": good_password}})

    # expired
    post_account(client, REQUEST_RESET, {"e": email})
    stale = sender.reset_tokens[-1]
    row = token_row(stale)
    row.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    row.save(update_fields=["expires_at"])
    expired = post_account(client, CONFIRM_RESET, {"input": {"token": stale, "newPassword": good_password}})

    # wrong purpose — a LIVE, UNCONSUMED EMAIL_VERIFY token offered to the reset mutation. It
    # used to be `sender.verify_tokens[-1]`, which `signup_and_verify` had already spent, so
    # this case was a second `consumed` case wearing a wrong-purpose label.
    verify_token = live_verify_token(client, sender, idem="collapse-purpose-0001", email="verger@grace.example")
    assert_only_the_purpose_clause_can_refuse(verify_token)
    wrong_purpose = post_account(client, CONFIRM_RESET, {"input": {"token": verify_token, "newPassword": good_password}})

    responses = {
        "malformed_empty": empty,
        "malformed_whitespace": whitespace,
        "malformed_wrong_shape": wrong_shape,
        "unknown": unknown,
        "consumed": consumed,
        "expired": expired,
        "wrong_purpose": wrong_purpose,
    }
    for name, resp in responses.items():
        assert error_code(resp) == "VALIDATION_FAILED", f"{name} did not return the collapsed code"
    # SECOND-ORDER, and NOT an independent guard. The earlier annotation here said it "bites only
    # if the view's scrubbing is ALSO removed — a real regression, just not one the codes above
    # would catch", which reads as a claim that this line guards that regression. It does not, and
    # this was measured: with `safe_graphql_error` dropped from `SafeGraphQLView.process_result`,
    # this whole file stays GREEN. The reason is that every raise on this path is a bare
    # `_validation_error()` with no custom message, so all seven responses already carry
    # `SAFE_MESSAGES[VALIDATION_FAILED]` whether or not the view rebuilds them. Firing this line
    # needs TWO regressions at once, and the second — a service raising differing messages under
    # one code — is not reachable from this path today. Kept as a cheap pin for the day a raise
    # site here does carry a custom message; the code assertions above are what bite.
    assert len({error_message(resp) for resp in responses.values()}) == 1, (
        "the token failures are no longer byte-identical — the view's message scrubbing "
        "has been lost and the message itself has become an oracle"
    )


@pytest.mark.django_db
def test_a_dead_but_real_token_with_a_weak_password_stays_collapsed(client, sender):
    """The FR-529 hole that a green suite did not see. Catches mutation F.

    Every OTHER weak-password test in this file uses an UNKNOWN token, which fails at the
    row lookup — so none of them ever drives a weak password into the
    purpose/consumed/expired block. That left a mutation which every other test in this file
    passes (measured with this test present: 1 failed, 36 passed) while turning the API into
    an enumeration oracle:

        unknown        -> VALIDATION_FAILED     ("this token never existed")
        consumed       -> PASSWORD_INVALID      ("this token EXISTED")
        expired        -> PASSWORD_INVALID
        wrong purpose  -> PASSWORD_INVALID

    An UNAUTHENTICATED caller holding no valid token could then separate "never existed"
    from "existed" just by attaching a short password — strictly worse than the sanctioned
    live-token oracle, which at least requires a working link first.

    So: a token that is REAL but cannot be used must answer exactly like one that never
    existed, no matter what the password is.
    """
    email = "pastor@grace.example"
    signup_and_verify(client, sender, email=email)

    # consumed — mint one and spend it
    post_account(client, REQUEST_RESET, {"e": email})
    spent = sender.reset_tokens[-1]
    post_account(client, CONFIRM_RESET, {"input": {"token": spent, "newPassword": "a-first-new-passphrase"}})

    # expired — mint one and age it out
    post_account(client, REQUEST_RESET, {"e": email})
    stale = sender.reset_tokens[-1]
    stale_row = token_row(stale)
    stale_row.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    stale_row.save(update_fields=["expires_at"])

    # wrong purpose — a LIVE, UNCONSUMED EMAIL_VERIFY token offered to the reset mutation. This
    # case used to be `sender.verify_tokens[-1]`, already spent by `signup_and_verify`, so it
    # was a second `consumed` case and the catch map's three dead-but-real states were two.
    verify_token = live_verify_token(client, sender, idem="dead-purpose-0001", email="sexton@grace.example")

    # PREMISES, asserted before the contract. Each row must be REAL and unusable for the
    # right reason; if any of these slips, the case below stops exercising the clause it
    # names and passes for the wrong reason.
    assert token_row(spent).consumed_at is not None, "the consumed case was NOT set up — token never spent"
    assert token_row(stale).expires_at <= timezone.now(), "the expired case was NOT set up — token still live"
    assert token_row(stale).consumed_at is None, "the expired token was spent, so it is not testing EXPIRY"
    assert_only_the_purpose_clause_can_refuse(verify_token)

    dead_but_real = {"consumed": spent, "expired": stale, "wrong_purpose": verify_token}
    for name, raw in dead_but_real.items():
        resp = post_account(client, CONFIRM_RESET, {"input": {"token": raw, "newPassword": SHORT_PASSWORD}})
        assert error_code(resp) == "VALIDATION_FAILED", (
            f"a {name} token answered {error_code(resp)} for a weak password. If that is "
            f"PASSWORD_INVALID, the password is being checked before the token's state, and "
            f"an unauthenticated caller can now tell a token that EXISTED from one that never "
            f"did (FR-529)"
        )

    # POSITIVE CONTROL. Without this, every assertion above would still pass if
    # PASSWORD_INVALID had been deleted outright or the weak password had silently become
    # acceptable — "refused" would be indistinguishable from a dead mechanism.
    post_account(client, REQUEST_RESET, {"e": email})
    live = sender.reset_tokens[-1]
    live_resp = post_account(client, CONFIRM_RESET, {"input": {"token": live, "newPassword": SHORT_PASSWORD}})
    assert error_code(live_resp) == "PASSWORD_INVALID", (
        "the SAME weak password behind a LIVE token no longer reports PASSWORD_INVALID, so "
        "the collapse asserted above proves nothing — the mechanism is dead, not working"
    )


@pytest.mark.django_db
def test_a_failed_reset_rolls_back_the_consume_and_the_password(client, sender, monkeypatch):
    """The transaction boundary itself — the thing that actually preserves the user's link.

    `test_a_rejected_password_does_not_burn_the_users_link` cannot catch the loss of
    `transaction.atomic()`, because with the password check above the consume the property
    holds without it. This test bites: it fails the reset AFTER the token has been consumed
    and the password written, at the audit call, so only a real rollback can restore both.

    Mirrors `test_signup_audit_failure_rolls_back_everything`, which does the same job for
    signup.
    """
    email = "pastor@grace.example"
    reset_token = live_reset_token(client, sender, email=email)
    original = CustomerUser.objects.get(email=email).password_hash

    reached_audit = []

    def boom(*a, **k):
        reached_audit.append(True)
        raise RuntimeError("audit down")

    monkeypatch.setattr("selahcue_api.apps.accounts.services.record_audit_event", boom)
    post_account(client, CONFIRM_RESET, {"input": {"token": reset_token, "newPassword": GOOD_PASSWORD}})

    # PREMISE, asserted BEFORE the contract, because the two assertions below describe a
    # post-state that is IDENTICAL to a request refused long before the consume ever happened.
    # Measured both ways. Swap this test's password for one `_validate_password` rejects and,
    # before this assertion existed, the file stayed GREEN at 35 passed — the test proving
    # nothing about the transaction boundary while looking exactly as healthy. With this
    # assertion the same swap fails here, and only here (1 failed, 36 passed). The realistic
    # trigger is drift in the password, which is now `GOOD_PASSWORD` and pinned against the
    # policy at import; this is the second lock, and it catches any other early raise too.
    assert reached_audit, (
        "the reset never reached the audit call, so nothing was consumed and no password was "
        "written — the rollback was never exercised and the two assertions below prove nothing"
    )
    assert token_row(reset_token).consumed_at is None, (
        "the token stayed consumed through a failed reset — the user's link is burnt and the "
        "password was never changed, the worst of both outcomes"
    )
    assert CustomerUser.objects.get(email=email).password_hash == original, (
        "the password was changed even though the reset failed"
    )


# --- 86ak5r2pt: a failed confirm leaves a trace, and the budget in front of it is pinned --------
#
# The per-IP budget on `confirmPasswordReset` already existed on main (86akcmfd4) and
# `test_password_reset_throttle.py` covers its basics. What this section adds is (1) the
# trace a failed confirm never left, and (2) the budget properties that file does not pin: the
# confirm budget's value, a LIVE token offered behind an exhausted budget, the retry-after-
# weak-password flow, fail-open that still completes a real reset and still traces, and
# `X-Forwarded-For` honoured behind the proxy count (that file only proves it is IGNORED at 0).
FAILED_ACTION = services.RESET_CONFIRM_FAILED_ACTION
OUTCOME = services.ResetConfirmOutcome
# The Django test client's default REMOTE_ADDR, and so the source every un-overridden call has.
TEST_CLIENT_ADDR = "127.0.0.1"
UNRESOLVED_TARGET = ("credential_token", "unresolved")
# Pseudonyms rotate daily, so a test that writes a row just before UTC midnight and computes the
# expected value just after would flake. Every test here runs on this day unless it moves it.
TEST_DAY = date(2026, 10, 26)


@pytest.fixture(autouse=True)
def _pinned_audit_day(monkeypatch):
    monkeypatch.setattr(services, "_audit_source_day", lambda: TEST_DAY)


def pseudo(address, day=TEST_DAY):
    """The actor id the trace writes for a source already in `client_ip()`'s form."""
    return services.audit_source_pseudonym(address, day)


def failed_rows():
    return list(AuditEvent.objects.filter(action=FAILED_ACTION).order_by("id"))


def failed_rows_as_text():
    """EVERY column of EVERY failure row, flattened to one string, so a token that turned up in
    any column (request_id, target_id, reason, before, after, actor_id...) is found."""
    return json.dumps(list(AuditEvent.objects.filter(action=FAILED_ACTION).values()), default=str)


def confirm(client, token, password, **extra):
    return post_account(client, CONFIRM_RESET, {"input": {"token": token, "newPassword": password}}, **extra)


@dataclass(frozen=True)
class FailureCase:
    token: str
    password: str
    code: str
    outcome: "services.ResetConfirmOutcome"
    target: tuple


def build_failure_scenarios(client, sender):
    """One request for every way a confirm can fail, each set up so that ONLY the clause named
    can refuse it. Nothing here calls the mutation on a case that is meant to fail, so the
    failure rows are all produced by the caller. (The one successful confirm that spends the
    `consumed` token writes a completed row, not a failure row.)"""
    elder_email = "elder@grace.example"
    signup_and_verify(client, sender, email="pastor@grace.example")
    pastor = CustomerUser.objects.get(email="pastor@grace.example")

    post_account(client, REQUEST_RESET, {"e": pastor.email})
    spent = sender.reset_tokens[-1]
    first_ok = confirm(client, spent, "a-first-new-passphrase")
    assert body(first_ok)["data"]["confirmPasswordReset"]["reset"] is True
    assert token_row(spent).consumed_at is not None, "the consumed case was NOT set up"

    post_account(client, REQUEST_RESET, {"e": pastor.email})
    stale = sender.reset_tokens[-1]
    stale_row = token_row(stale)
    stale_row.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    stale_row.save(update_fields=["expires_at"])
    assert token_row(stale).consumed_at is None, "the expired case was spent, so it is not testing EXPIRY"

    # A different user, because minting a reset supersedes (consumes) the user's earlier live ones.
    signup_and_verify(client, sender, email=elder_email, idem="sv-signup-0002")
    elder = CustomerUser.objects.get(email=elder_email)
    post_account(client, REQUEST_RESET, {"e": elder_email})
    live = sender.reset_tokens[-1]

    verify_token = live_verify_token(client, sender, idem="trace-purpose-0001", email="verger@grace.example")
    assert_only_the_purpose_clause_can_refuse(verify_token)
    verger_id = str(token_row(verify_token).customer_user_id)

    pastor_target = ("customer_user", str(pastor.id))
    good = "another-fine-passphrase"
    vf = "VALIDATION_FAILED"
    return {
        "malformed_empty": FailureCase("", good, vf, OUTCOME.MALFORMED_TOKEN, UNRESOLVED_TARGET),
        "malformed_whitespace": FailureCase("   ", good, vf, OUTCOME.MALFORMED_TOKEN, UNRESOLVED_TARGET),
        "wrong_shape": FailureCase("not-a-token-shape", good, vf, OUTCOME.UNKNOWN_TOKEN, UNRESOLVED_TARGET),
        "unknown": FailureCase("SC-PRS-nobody-minted-this", good, vf, OUTCOME.UNKNOWN_TOKEN, UNRESOLVED_TARGET),
        "consumed": FailureCase(spent, good, vf, OUTCOME.CONSUMED, pastor_target),
        "expired": FailureCase(stale, good, vf, OUTCOME.EXPIRED, pastor_target),
        "wrong_purpose": FailureCase(verify_token, good, vf, OUTCOME.WRONG_PURPOSE, ("customer_user", verger_id)),
        "password_rejected": FailureCase(
            live, SHORT_PASSWORD, "PASSWORD_INVALID", OUTCOME.PASSWORD_REJECTED, ("customer_user", str(elder.id))
        ),
    }


@pytest.mark.django_db
def test_every_failed_confirm_leaves_exactly_one_record_naming_its_outcome(client, sender):
    """AC3. One row per failed attempt, for EVERY class, carrying the outcome class, the source
    (as a pseudonym), a per-attempt id and a timestamp. The rows are written after the reset's
    transaction has rolled back: a row written inside it would be rolled back with it, and the
    five classes that fail inside the transaction (unknown, consumed, expired, wrong purpose,
    rejected password) would have no row at all. Only the empty token raises outside it."""
    scenarios = build_failure_scenarios(client, sender)
    assert failed_rows() == [], "setup itself produced failure rows, so the counts below prove nothing"

    for name, case in scenarios.items():
        before = len(failed_rows())
        resp = confirm(client, case.token, case.password)
        assert error_code(resp) == case.code, f"{name}: the case did not fail the way it was built to"
        rows = failed_rows()
        assert len(rows) == before + 1, f"{name}: expected exactly one new failure row, got {len(rows) - before}"
        row = rows[-1]
        assert row.after == {"outcome": case.outcome.value}, name
        assert row.result == AuditResult.DENIED, name
        assert row.actor_kind == ActorKind.ANONYMOUS.value, name
        assert row.actor_id == pseudo(TEST_CLIENT_ADDR), name
        assert row.source_surface == services.ACCOUNT_AUDIT_SURFACE, name
        assert (row.target_type, row.target_id) == case.target, name
        assert row.before == {}, name
        assert re.fullmatch(r"[0-9a-f]{32}", row.request_id), f"{name}: request_id {row.request_id!r}"
        assert row.created_at is not None, name

    rows = failed_rows()
    assert len(rows) == len(scenarios)
    assert len({row.request_id for row in rows}) == len(rows), "attempt ids must be distinct per attempt"
    covered_elsewhere = {OUTCOME.UNCLASSIFIED, OUTCOME.INTERNAL_ERROR}  # see their own tests below
    assert {row.after["outcome"] for row in rows} == {
        outcome.value for outcome in OUTCOME if outcome not in covered_elsewhere
    }, "a failure class has no scenario in this test, so it is untested"


def contains_any(text, needles):
    return [needle for needle in needles if needle and needle in text]


@pytest.mark.django_db
def test_no_token_material_reaches_any_audit_column_or_log_line_of_a_failed_confirm(client, sender, caplog):
    """AC4: asserted by a test, not by inspection. Every form of every token offered -- raw,
    fingerprint, at-rest hash, masked form, and the stored row's own copies of those -- plus the
    submitted passwords, must be absent from every column of every failure row AND from every log
    record emitted while the failures happened.

    Whole values are not enough: a line that logs a slice of the token, a prefix of the
    fingerprint or the first characters of the password carries the secret just as well and
    contains none of the whole values. So the search also covers every overlapping 12-character
    window of each token form (any slice of 12 characters or more contains one), and the first
    6 characters of each submitted password."""
    scenarios = build_failure_scenarios(client, sender)

    whole = []
    for case in scenarios.values():
        for secret in (case.token, case.password):
            if len(secret) >= 12:  # shorter strings occur in the haystack by chance
                whole.append(secret)
        if len(case.token) >= 12:
            whole += [services._fingerprint(case.token), services._credential_token_hash(case.token)]
            whole.append(services._mask(case.token)[2])
            if CredentialToken.objects.filter(token_fingerprint=services._fingerprint(case.token)).exists():
                row = token_row(case.token)
                whole += [row.token_fingerprint, row.token_hash, row.masked_token]
    assert len(whole) >= 20, "too few secrets to search for; the scenarios changed shape"

    def windows(value, size=12):
        return {value[i : i + size] for i in range(max(len(value) - size + 1, 1))}

    fragments = set()
    for secret in whole:
        fragments |= windows(secret)
    for case in scenarios.values():
        if len(case.password) >= services.MIN_PASSWORD_LENGTH:
            fragments.add(case.password[:6])
    needles = sorted(set(whole) | fragments)
    assert len(needles) > 500, "the fragment search is not wide enough to catch a slice"

    # POSITIVE CONTROLS. Without them "nothing found" is indistinguishable from a search that
    # cannot find anything. (1) A haystack holding a MIDDLE fragment of a fingerprint and a
    # password's first 6 characters is found: these are the shapes a whole-value search misses.
    a_fingerprint = next(v for v in whole if len(v) == 64 and re.fullmatch(r"[0-9a-f]{64}", v))
    a_password = next(c.password for c in scenarios.values() if len(c.password) >= services.MIN_PASSWORD_LENGTH)
    for planted_fragment in (a_fingerprint[17:37], a_fingerprint[30:42], a_password[:6]):
        assert contains_any(f"prefix {planted_fragment} suffix", needles), (
            f"the search cannot find the fragment {planted_fragment!r}"
        )
    # (2) The log capture: a record that carries a fragment reaches caplog.
    caplog.set_level(logging.DEBUG)
    logging.getLogger(services.__name__).warning("planted %s", a_fingerprint[17:37])
    assert contains_any(caplog.text, needles), "caplog is not capturing the accounts logger"
    caplog.clear()
    # (3) The audit-column half: a REAL failure-action row that carries a fragment in a column
    # the search must cover is found by `failed_rows_as_text`. (`needle in text` on a string the
    # test built itself proves nothing about the query.) Removed again before the real run.
    planted = record_audit_event(
        ActorContext(kind=ActorKind.ANONYMOUS, actor_id="src:planted"),
        action=FAILED_ACTION,
        target_type="credential_token",
        target_id="unresolved",
        request_id=a_fingerprint[:20],
    )
    assert contains_any(failed_rows_as_text(), needles), "the audit search cannot see a planted row"
    planted.delete()
    assert failed_rows() == [], "the planted row was not removed"

    for case in scenarios.values():
        confirm(client, case.token, case.password)

    rows_text = failed_rows_as_text()
    assert len(failed_rows()) == len(scenarios)
    assert "unknown_token" in rows_text and "password_rejected" in rows_text, "the rows were not searched"
    assert contains_any(rows_text, needles) == [], "token or password material reached an audit row"
    assert contains_any(caplog.text, needles) == [], "token or password material reached a log line"


@pytest.mark.django_db
@pytest.mark.parametrize("key", ["reset_token", "raw_token", "token_hash", "resetToken", "Token-Hash"])
def test_the_audit_writer_redacts_reset_token_material_wherever_it_is_put(key):
    """The redaction guard. `device_token`, `full_key` and `secret` were already blocked from audit
    `before`/`after`; a reset token's names were not. Without these names a future caller that
    wrote `after={"reset_token": raw}` would store the credential. The writer replaces the value
    (it does not raise), so the assertion is on what was STORED.

    `token_fingerprint` is deliberately NOT here: see the next test."""
    secret = "SC-PRS-" + "q" * 43
    event = record_audit_event(
        ActorContext(kind=ActorKind.ANONYMOUS, actor_id=TEST_CLIENT_ADDR),
        action="test.redaction",
        target_type="credential_token",
        target_id="unresolved",
        request_id="r" * 32,
        before={key: secret},
        after={key: secret, "outcome": "unknown_token"},
    )
    stored = AuditEvent.objects.get(pk=event.pk)
    assert stored.before == {key: "[redacted]"}
    assert stored.after == {key: "[redacted]", "outcome": "unknown_token"}, (
        "the reset-token name was not redacted, or the redaction swallowed an ordinary field"
    )
    assert secret not in json.dumps(list(AuditEvent.objects.filter(pk=event.pk).values()), default=str)


@pytest.mark.django_db
def test_the_audit_writer_still_stores_a_token_fingerprint_where_a_writer_documents_one():
    """The counterpart of the test above. `device.activated` and `device_token.reminted` store the
    device token's fingerprint under `after["token_fingerprint"]` ON PURPOSE, so an operator can
    follow a device across a renewal. An earlier version of this change put that name in the
    deny-list and turned both rows' value into "[redacted]" without any test noticing. The rows
    themselves are pinned in test_activation_licence_transition.py and test_device_token_remint.py;
    this pins the writer."""
    event = record_audit_event(
        ActorContext(kind=ActorKind.DEVICE, actor_id="dev-1"),
        action="test.fingerprint",
        target_type="device_token",
        target_id="1",
        request_id="r" * 12,
        after={"token_fingerprint": "f" * 64, "superseded_token_fingerprint": "e" * 64},
    )
    assert AuditEvent.objects.get(pk=event.pk).after == {
        "token_fingerprint": "f" * 64,
        "superseded_token_fingerprint": "e" * 64,
    }


@pytest.mark.django_db
def test_the_token_failure_responses_are_byte_identical_and_carry_no_outcome_class(client, sender):
    """FR-529 / CON-P6. The existing indistinguishability test compares the code and the message;
    this compares the whole response, so a class leaking into any other field (an extension, a
    path, a header) is caught too. It also searches the body for every internal outcome name."""
    scenarios = build_failure_scenarios(client, sender)

    responses = {
        name: confirm(client, case.token, case.password)
        for name, case in scenarios.items()
        if case.code == "VALIDATION_FAILED"
    }
    assert len(responses) == 7, "a token-failure class is missing from the comparison"

    def fingerprint_of(resp):
        headers = sorted((k, v) for k, v in resp.headers.items() if k.lower() != "date")
        return resp.status_code, headers, resp.content

    assert len({repr(fingerprint_of(resp)) for resp in responses.values()}) == 1, (
        "two token-failure classes now answer differently on the wire (FR-529)"
    )
    text = next(iter(responses.values())).content.decode()
    for outcome in OUTCOME:
        assert outcome.value not in text, f"the internal outcome {outcome.value!r} reached the response"
    assert "unresolved" not in text and TEST_CLIENT_ADDR not in text


@pytest.mark.django_db
@pytest.mark.parametrize(
    "make_error",
    [
        lambda: RuntimeError("audit store down"),
        lambda: OperationalError("database is gone"),
        lambda: IntegrityError("duplicate key"),
    ],
    ids=["RuntimeError", "OperationalError", "IntegrityError"],
)
def test_a_failure_to_record_a_failed_confirm_changes_nothing_the_caller_sees(
    client, sender, settings, monkeypatch, caplog, make_error
):
    """The trace is best effort. If the audit store refuses the row, the caller must still get the
    answer they would have got -- a 500 in its place would turn an audit outage into a changed
    contract -- and the loss must be reported, once a minute, with a count, without any token
    material and without a traceback (the traceback's frames hold the raw token and the submitted
    password as locals). Parametrised over real database errors as well as a plain RuntimeError."""
    # Out of reach: this test makes 17 more confirms from one address, and the point is the audit
    # fault, not the budget.
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM = (1000, 3600)
    scenarios = build_failure_scenarios(client, sender)
    clock = FakeClock(monkeypatch)

    healthy = {name: confirm(client, c.token, c.password).content for name, c in scenarios.items()}
    assert len(failed_rows()) == len(scenarios)

    real = services.record_audit_event

    def refuse_only_the_failure_rows(actor, **kwargs):
        if kwargs.get("action") == FAILED_ACTION:
            raise make_error()
        return real(actor, **kwargs)

    monkeypatch.setattr(services, "record_audit_event", refuse_only_the_failure_rows)
    caplog.clear()
    faulted = {name: confirm(client, c.token, c.password).content for name, c in scenarios.items()}

    assert faulted == healthy, "an audit write failure changed a response"
    assert len(failed_rows()) == len(scenarios), "a row was written despite the fault"

    def lost_reports():
        return [
            r for r in caplog.records
            if r.name == services.__name__ and "could not write the audit row" in r.getMessage()
        ]

    (first,) = lost_reports()
    message = first.getMessage()
    assert "1 failed" in message and type(make_error()).__name__ in message and pseudo(TEST_CLIENT_ADDR) in message
    # (Not `"Traceback" not in caplog.text`: strawberry's own ERROR logging of the masked
    # resolver errors prints tracebacks of its own; this is about OUR report.)
    assert first.exc_info is None and "Traceback" not in message, "the report carries a traceback"
    assert all(r.exc_info is None for r in caplog.records if r.name == services.__name__)
    for case in scenarios.values():
        if len(case.token) >= 12:
            assert case.token not in caplog.text and services._fingerprint(case.token) not in caplog.text
        if len(case.password) >= 12:
            assert case.password not in caplog.text

    # The other seven losses were counted, not logged, and arrive with the NEXT report.
    clock.advance(services._TRACE_REPORT_INTERVAL_SECONDS + 1)
    confirm(client, "SC-PRS-one-more", GOOD_PASSWORD)
    second = lost_reports()[-1].getMessage()
    assert len(lost_reports()) == 2 and "8 failed" in second, second


@pytest.mark.django_db
def test_a_failure_nobody_classified_is_still_recorded(client, monkeypatch):
    """Every failed confirm leaves a record even if a future raise site forgets to name its class."""

    def refuse(*args, **kwargs):
        raise SafeAPIError(ErrorCode.VALIDATION_FAILED)

    monkeypatch.setattr(services, "_consume_reset_token", refuse)
    assert error_code(confirm(client, "SC-PRS-whatever", GOOD_PASSWORD)) == "VALIDATION_FAILED"
    assert [row.after["outcome"] for row in failed_rows()] == [OUTCOME.UNCLASSIFIED.value]


@pytest.mark.django_db
def test_a_successful_confirm_keeps_its_audit_row_and_leaves_no_failure_record(client, sender):
    """AC3, second half. Also the positive control for every "no failure row" assertion here."""
    reset_token = live_reset_token(client, sender)
    user = CustomerUser.objects.get(email="pastor@grace.example")

    resp = confirm(client, reset_token, GOOD_PASSWORD)

    assert body(resp)["data"]["confirmPasswordReset"]["reset"] is True
    completed = list(AuditEvent.objects.filter(action="customer_user.password_reset_completed"))
    assert len(completed) == 1
    row = completed[0]
    assert (row.actor_kind, row.actor_id) == (ActorKind.CUSTOMER.value, str(user.id))
    assert (row.target_type, row.target_id) == ("customer_user", str(user.id))
    assert (row.source_surface, row.result) == (services.ACCOUNT_AUDIT_SURFACE, AuditResult.SUCCESS)
    assert failed_rows() == []


@pytest.mark.django_db
def test_an_exhausted_budget_refuses_a_live_token_before_it_is_read_and_writes_no_record(client, sender, settings):
    """AC1. The budget must be spent BEFORE the token is looked up. Every other throttle test uses
    a token that does not exist, so none could see the budget move below the consume: a request
    refused as RATE_LIMITED would already have reset the password. Here the exhausted source
    offers a LIVE token and a GOOD password; nothing may change, and the refusal itself writes
    no row (a row per refused request would turn the flood the budget stops into database writes).
    """
    reset_token = live_reset_token(client, sender)
    original_hash = CustomerUser.objects.get(email="pastor@grace.example").password_hash
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM = (2, 3600)

    assert error_code(confirm(client, "SC-PRS-guess-one", GOOD_PASSWORD)) == "VALIDATION_FAILED"
    assert error_code(confirm(client, "SC-PRS-guess-two", GOOD_PASSWORD)) == "VALIDATION_FAILED"
    assert len(failed_rows()) == 2

    refused = confirm(client, reset_token, GOOD_PASSWORD)

    assert error_code(refused) == "RATE_LIMITED"
    assert token_row(reset_token).consumed_at is None, "the throttled call consumed the live token"
    assert CustomerUser.objects.get(email="pastor@grace.example").password_hash == original_hash, (
        "the throttled call changed the password"
    )
    assert not AuditEvent.objects.filter(action="customer_user.password_reset_completed").exists()
    assert len(failed_rows()) == 2, "a throttled request wrote a failure row"

    # CONTROL: the refusal was the BUDGET, not the token -- another source resets with the same link.
    other = confirm(client, reset_token, GOOD_PASSWORD, REMOTE_ADDR="198.51.100.77")
    assert body(other)["data"]["confirmPasswordReset"]["reset"] is True


def test_the_shipped_confirm_budget_is_pinned_and_its_two_copies_agree(settings):
    """The confirm budget is the one reset budget `test_password_reset_throttle.py` does not pin.
    Every behavioural test tightens it to make it trip, so nothing else notices a shipped limit
    being inflated until it limits nothing. Changing it is a decision: update this literal in
    the same change and say why. 20 per hour per source is the figure 86akcmfd4 shipped; a person
    retrying a weak password needs a handful of calls (see the next test). That is per SOURCE:
    until SELAHCUE_TRUSTED_PROXY_COUNT is set in production (86ak10a13) the whole customer base is
    ONE source, and the 20 per hour are shared by everyone."""
    assert settings.SELAHCUE_THROTTLE_RESET_CONFIRM == services.RESET_CONFIRM_IP_BUDGET, (
        "settings.SELAHCUE_THROTTLE_RESET_CONFIRM and the services.py default have drifted"
    )
    assert services.RESET_CONFIRM_IP_BUDGET == (20, 3600)


@pytest.mark.django_db
def test_a_user_who_keeps_choosing_a_weak_password_is_never_blocked_by_the_shipped_budget(client, sender):
    """AC1, second half, under the SHIPPED budget rather than a tightened one. Ten rejected
    passwords in a row from one address -- far past any real retry loop -- are each told
    PASSWORD_INVALID, never RATE_LIMITED, the link stays live throughout, and the eleventh call
    (a good password) completes the reset. Each weak attempt is traced.

    This is a property of ONE source. In production, until SELAHCUE_TRUSTED_PROXY_COUNT is set
    (86ak10a13), every caller is the same source and shares the 20 per hour, so it does not hold
    there: a few people resetting at once, or one person retrying a lot, can exhaust it."""
    reset_token = live_reset_token(client, sender)

    for attempt in range(10):
        resp = confirm(client, reset_token, SHORT_PASSWORD)
        assert error_code(resp) == "PASSWORD_INVALID", f"attempt {attempt + 1} was answered {error_code(resp)!r}"
        assert token_row(reset_token).consumed_at is None

    done = confirm(client, reset_token, GOOD_PASSWORD)

    assert body(done)["data"]["confirmPasswordReset"]["reset"] is True
    assert [row.after["outcome"] for row in failed_rows()] == [OUTCOME.PASSWORD_REJECTED.value] * 10


class _BrokenStore:
    """A limiter store standing in for a Redis outage -- every call raises, exactly as
    `evaluate_budget`'s own `except Exception` branch expects. (Module-local on purpose: see
    conftest.py on shared helpers.)"""

    def incr_with_expiry(self, key, window_seconds):
        raise RuntimeError("redis is down")


@pytest.mark.django_db
def test_when_the_limiter_store_is_down_confirm_still_completes_a_reset_and_still_leaves_a_trace(
    client, sender, settings, monkeypatch
):
    """AC2. Fails OPEN: an unavailable Redis must not lock people out of password reset. The
    existing outage test only offers a token that does not exist, which proves the call reaches
    the service but not that a real reset still completes; and a trace matters most while the
    brake is off."""
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM = (1, 3600)
    reset_token = live_reset_token(client, sender)
    monkeypatch.setattr(guards, "CacheStore", lambda _cache: _BrokenStore())

    for _ in range(3):
        assert error_code(confirm(client, reset_token, SHORT_PASSWORD)) == "PASSWORD_INVALID"
    assert error_code(confirm(client, "SC-PRS-does-not-exist", GOOD_PASSWORD)) == "VALIDATION_FAILED"
    done = confirm(client, reset_token, GOOD_PASSWORD)

    assert body(done)["data"]["confirmPasswordReset"]["reset"] is True
    assert [row.after["outcome"] for row in failed_rows()] == [OUTCOME.PASSWORD_REJECTED.value] * 3 + [
        OUTCOME.UNKNOWN_TOKEN.value
    ]


@pytest.mark.django_db
def test_forwarded_for_is_honoured_only_behind_a_trusted_proxy_and_the_record_names_that_client(client, settings):
    """AC1 / the ticket's scope. At proxy count 0 the header is ignored: the budget AND the record
    are keyed on the socket peer, whatever the header says. At count 1 the entry the proxy
    appended is the client, for the budget and for the record, and what a caller put to its left
    is ignored. `test_password_reset_throttle.py` proves only the count-0 half. (In production
    this is a property of the code, not of the deployment, until SELAHCUE_TRUSTED_PROXY_COUNT is
    set -- 86ak10a13: unset, every caller shares ONE budget and every row names the proxy.)"""
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM = (1, 3600)

    def call(**extra):
        return error_code(confirm(client, "SC-PRS-a-guess", GOOD_PASSWORD, **extra))

    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    assert call(REMOTE_ADDR="198.51.100.20", HTTP_X_FORWARDED_FOR="203.0.113.50") == "VALIDATION_FAILED"
    assert call(REMOTE_ADDR="198.51.100.20", HTTP_X_FORWARDED_FOR="203.0.113.51") == "RATE_LIMITED", (
        "a forged header bought a fresh budget while no proxy is trusted"
    )

    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 1
    proxy = {"REMOTE_ADDR": "10.0.0.1"}
    assert call(HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.50", **proxy) == "VALIDATION_FAILED"
    assert call(HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.51", **proxy) == "VALIDATION_FAILED", (
        "two clients behind one trusted proxy shared a budget"
    )
    assert call(HTTP_X_FORWARDED_FOR="9.9.9.9, 203.0.113.50", **proxy) == "RATE_LIMITED", (
        "a forged left-hand entry bought a fresh budget behind a trusted proxy"
    )

    assert [row.actor_id for row in failed_rows()] == [
        pseudo("198.51.100.20"),
        pseudo("203.0.113.50"),
        pseudo("203.0.113.51"),
    ]


@pytest.mark.django_db
def test_a_failure_with_no_resolvable_source_is_recorded_under_a_fixed_label(client):
    """Two different ways to have no address, two fixed labels, neither of them an address.
    The resolver had no request at all: `unresolved-client-ip`, the identity the budget falls
    back to, so the record and the budget agree. The request carried no REMOTE_ADDR:
    `client_ip()` itself answers "unknown", and that is what the budget and the row use."""
    with pytest.raises(SafeAPIError):
        services.confirm_password_reset("SC-PRS-whatever", GOOD_PASSWORD, client_ip="")
    assert error_code(confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR="")) == "VALIDATION_FAILED"

    rows = failed_rows()
    assert [row.actor_id for row in rows] == ["src:unresolved-client-ip", "src:unknown"]
    assert all(row.actor_id == pseudo(row.actor_id[len("src:"):]) for row in rows), (
        "a fixed label must be what the pseudonym function returns for those two sources"
    )


@pytest.mark.django_db
def test_an_oversized_source_cannot_stop_the_record_being_written():
    """`actor_id` is 128 wide and a value past it fails the INSERT on Postgres, which on a refusal
    path would silently lose the row (see ACTOR_ID_MAX_LENGTH in graphql/context.py). The actor
    id is now a fixed-length pseudonym whatever the source, so no source can do that; this keeps
    it that way if the representation ever changes."""
    with pytest.raises(SafeAPIError):
        services.confirm_password_reset("SC-PRS-whatever", GOOD_PASSWORD, client_ip="9" * 140)
    (row,) = failed_rows()
    assert re.fullmatch(r"src:v1:[0-9a-f]{32}", row.actor_id)


@pytest.mark.django_db
def test_the_default_budget_refuses_the_21st_confirm_from_one_source(client):
    """AC1's first clause under the SHIPPED budget rather than one tightened to make a test short:
    twenty failed confirms from one source are served and traced, the 21st is refused and writes
    no row, and another source is untouched."""
    codes = [error_code(confirm(client, f"SC-PRS-guess-{n}", GOOD_PASSWORD, REMOTE_ADDR="203.0.113.77")) for n in range(21)]
    other = confirm(client, "SC-PRS-guess-other", GOOD_PASSWORD, REMOTE_ADDR="203.0.113.78")

    assert codes == ["VALIDATION_FAILED"] * 20 + ["RATE_LIMITED"], codes
    assert error_code(other) == "VALIDATION_FAILED", "a different source must have its own, unspent budget"
    assert [row.actor_id for row in failed_rows()] == [pseudo("203.0.113.77")] * 20 + [pseudo("203.0.113.78")]


# --- who the row says did it: a keyed, daily-rotating pseudonym, never the address ----------
@pytest.mark.django_db
def test_the_row_never_holds_the_address_it_was_caused_by(client, caplog):
    caplog.set_level(logging.DEBUG)
    addresses = ["203.0.113.99", "2001:db8:abcd:12:aaaa::1"]
    for address in addresses:
        assert error_code(confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR=address)) == "VALIDATION_FAILED"

    text = failed_rows_as_text()
    needles = ["203.0.113.99", "2001:db8:abcd:12"]
    # CONTROL: the rows were searched (they name their pseudonyms), and a row that DID carry an
    # address would be found.
    assert pseudo("203.0.113.99") in text and pseudo("2001:db8:abcd:12::") in text
    planted = record_audit_event(
        ActorContext(kind=ActorKind.ANONYMOUS, actor_id="203.0.113.99"),
        action=FAILED_ACTION,
        target_type="credential_token",
        target_id="unresolved",
        request_id="r" * 12,
    )
    assert contains_any(failed_rows_as_text(), needles), "the search cannot see an address in a row"
    planted.delete()

    assert contains_any(failed_rows_as_text(), needles) == [], "an address reached the audit table"
    assert contains_any(caplog.text, needles) == [], "an address reached a log line"
def test_the_pseudonym_is_pinned_keyed_rotating_and_per_source():
    """The construction is pinned by an INDEPENDENT recomputation, not by calling the function
    under test: key = SHA-256(key_salt + SECRET_KEY) (Django's salted_hmac), then HMAC-SHA-256 of
    "<UTC date>|<bucket>" under it, first 32 hex characters, prefixed "src:v1:"."""
    import hashlib
    import hmac

    from django.conf import settings as django_settings

    salt = b"selahcue_api.apps.accounts.audit_source.v1"
    key = hashlib.sha256(salt + django_settings.SECRET_KEY.encode()).digest()
    expected = "src:v1:" + hmac.new(key, b"2026-10-26|203.0.113.5", hashlib.sha256).hexdigest()[:32]

    assert services.audit_source_pseudonym("203.0.113.5", date(2026, 10, 26)) == expected
    assert re.fullmatch(r"src:v1:[0-9a-f]{32}", expected)
    # rotating: a new UTC day is a new pseudonym for the same source
    assert services.audit_source_pseudonym("203.0.113.5", date(2026, 10, 27)) != expected
    # per source: two sources never share one on the same day
    assert services.audit_source_pseudonym("203.0.113.6", date(2026, 10, 26)) != expected
    # keyed: it is not a bare hash of the address
    assert hashlib.sha256(b"203.0.113.5").hexdigest()[:32] not in expected
    assert hashlib.sha256(b"2026-10-26|203.0.113.5").hexdigest()[:32] not in expected
    # structurally unlike a credential fingerprint: the derived key is NOT the one `_fingerprint`
    # uses (HMAC keyed by SECRET_KEY itself), so no pseudonym can coincide with a fingerprint.
    old_style_key = hmac.new(django_settings.SECRET_KEY.encode(), b"audit-source-v1", hashlib.sha256).digest()
    assert key != old_style_key
    assert services._fingerprint("2026-10-26|203.0.113.5") not in expected


@pytest.mark.django_db
def test_rows_from_the_same_ipv6_64_share_a_pseudonym_and_other_networks_do_not(client):
    """Record-level, not just in `client_ip()`: the pseudonym is of the /64 bucket, the same string
    the budget is keyed on."""
    for address in ("2001:db8:1:2:aaaa::1", "2001:db8:1:2:bbbb::2", "2001:db8:1:3::1"):
        assert error_code(confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR=address)) == "VALIDATION_FAILED"

    assert [row.actor_id for row in failed_rows()] == [
        pseudo("2001:db8:1:2::"),
        pseudo("2001:db8:1:2::"),
        pseudo("2001:db8:1:3::"),
    ]
    assert pseudo("2001:db8:1:2::") != pseudo("2001:db8:1:3::")


@pytest.mark.django_db
def test_a_source_has_a_different_pseudonym_on_a_different_day(client, monkeypatch):
    confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR="203.0.113.5")
    monkeypatch.setattr(services, "_audit_source_day", lambda: date(2026, 10, 27))
    confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR="203.0.113.5")

    first, second = failed_rows()
    assert first.actor_id == pseudo("203.0.113.5", date(2026, 10, 26))
    assert second.actor_id == pseudo("203.0.113.5", date(2026, 10, 27))
    assert first.actor_id != second.actor_id


@pytest.mark.django_db
def test_an_operator_can_list_the_failed_confirms_from_a_known_address_on_a_day(client):
    """The way back from an address to its rows: `manage.py failed_reset_confirms`."""
    for address in ("203.0.113.5", "203.0.113.5", "203.0.113.6", "2001:db8:1:2:aaaa::1"):
        confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR=address)

    def run(**options):
        out = StringIO()
        call_command("failed_reset_confirms", stdout=out, **options)
        return out.getvalue()

    both = run(ip="203.0.113.5", date="2026-10-26")
    assert f"pseudonym for 2026-10-26: {pseudo('203.0.113.5')}" in both
    assert "2 failed confirm(s)" in both and "outcome=unknown_token" in both
    assert "1 failed confirm(s)" in run(ip="203.0.113.6", date="2026-10-26")
    assert "1 failed confirm(s)" in run(ip="2001:db8:1:2:cccc::9", date="2026-10-26"), "IPv6 is bucketed to its /64"
    assert "0 failed confirm(s)" in run(ip="203.0.113.5", date="2026-10-27"), "pseudonyms rotate: another day, no rows"
    assert services.audit_source_pseudonym_for_address("203.0.113.5", date(2026, 10, 26)) == pseudo("203.0.113.5")
    with pytest.raises(CommandError):
        run(ip="not-an-address")
    with pytest.raises(CommandError):
        run(ip="203.0.113.5", date="yesterday")


# --- a live-token holder cannot make a failure leave no row -----------------------------------
LONE_SURROGATES = "\ud800" * 10


@pytest.mark.django_db
def test_a_password_that_cannot_be_utf8_encoded_is_a_rejected_password_not_a_crash(client, sender):
    """JSON escapes can put lone surrogates in `newPassword`. They pass the length rule, the token
    is marked consumed inside the transaction, and the hasher raised UnicodeEncodeError: not a
    coded refusal, so no row, and the view masked it to VALIDATION_FAILED. Now it is refused where
    every other bad password is, behind a live token as PASSWORD_INVALID, and traced."""
    email = "pastor@grace.example"
    reset_token = live_reset_token(client, sender, email=email)
    user = CustomerUser.objects.get(email=email)
    assert len(LONE_SURROGATES) >= services.MIN_PASSWORD_LENGTH, "the premise: it clears the length rule"

    resp = confirm(client, reset_token, LONE_SURROGATES)

    assert error_code(resp) == "PASSWORD_INVALID"
    assert token_row(reset_token).consumed_at is None
    (row,) = failed_rows()
    assert row.after == {"outcome": OUTCOME.PASSWORD_REJECTED.value}
    assert (row.target_type, row.target_id) == ("customer_user", str(user.id))
    # the same string is refused at signup too, with the collapsed code, and creates nothing
    signup = post_account(client, REGISTER, register_input(idem="signup-surrogate", email="new@grace.example", password=LONE_SURROGATES))
    assert error_code(signup) == "VALIDATION_FAILED"
    assert not CustomerUser.objects.filter(email="new@grace.example").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("where", "make_error"),
    [
        ("hasher", lambda: RuntimeError("hasher exploded")),
        ("hasher", lambda: UnicodeEncodeError("utf-8", "x", 0, 1, "hasher exploded")),
        ("hasher", lambda: OperationalError("database is gone")),
        ("hasher", lambda: IntegrityError("duplicate key")),
        ("token_save", lambda: OperationalError("database is gone")),
        ("token_save", lambda: IntegrityError("duplicate key")),
    ],
    ids=[
        "hasher-RuntimeError",
        "hasher-UnicodeEncodeError",
        "hasher-OperationalError",
        "hasher-IntegrityError",
        "token-save-OperationalError",
        "token-save-IntegrityError",
    ],
)
def test_an_unexpected_failure_inside_the_confirm_still_leaves_one_row_naming_the_user(
    client, sender, monkeypatch, caplog, where, make_error
):
    """A failure that is not a coded refusal -- the hasher blowing up after the token has been
    consumed, or a real database error while saving it -- is not a gap in the trace, and it names
    the account whose link was in use. The response is exactly the one a dead token gets, the
    link is still live (the transaction rolled back), nothing token-shaped reached a log line,
    and the next real reset completes. Parametrised over real DB errors too, so narrowing the
    catch to the exceptions one happens to think of fails here."""
    email = "pastor@grace.example"
    reset_token = live_reset_token(client, sender, email=email)
    user = CustomerUser.objects.get(email=email)
    original = user.password_hash
    fingerprint = services._fingerprint(reset_token)
    dead = confirm(client, "SC-PRS-nobody-minted-this", GOOD_PASSWORD).content
    assert failed_rows()[-1].after == {"outcome": OUTCOME.UNKNOWN_TOKEN.value}

    def explode(*args, **kwargs):
        raise make_error()

    caplog.clear()
    with monkeypatch.context() as patch:
        if where == "hasher":
            patch.setattr(services, "make_password", explode)
        else:
            patch.setattr(CredentialToken, "save", explode)
        resp = confirm(client, reset_token, GOOD_PASSWORD)

    assert resp.content == dead, "an unexpected failure answers differently from a dead token"
    assert token_row(reset_token).consumed_at is None, "the rolled-back transaction must leave the link live"
    assert CustomerUser.objects.get(email=email).password_hash == original
    rows = failed_rows()
    assert len(rows) == 2
    assert rows[-1].after == {"outcome": OUTCOME.INTERNAL_ERROR.value}
    assert (rows[-1].target_type, rows[-1].target_id) == ("customer_user", str(user.id))
    assert reset_token not in caplog.text and fingerprint not in caplog.text and GOOD_PASSWORD not in caplog.text
    # and the account is not stuck: the next real attempt completes
    done = confirm(client, reset_token, GOOD_PASSWORD)
    assert body(done)["data"]["confirmPasswordReset"]["reset"] is True


# --- the flood brakes: they skip the ROW, never the response ---------------------------------
def _fail_from_many_sources(client, count, *, first=1):
    return [
        error_code(confirm(client, f"SC-PRS-flood-{n}", GOOD_PASSWORD, REMOTE_ADDR=f"198.51.100.{n}"))
        for n in range(first, first + count)
    ]


class FakeClock:
    """Moves the clock `services` reads (its `time` name only; the real module is untouched)."""

    def __init__(self, monkeypatch, start=10_000.0):
        self.now = start
        clock = self

        class _Time:
            def monotonic(self):
                return clock.now

            def __getattr__(self, name):
                return getattr(time, name)

        monkeypatch.setattr(services, "time", _Time())

    def advance(self, seconds):
        self.now += seconds


@pytest.mark.django_db
def test_many_sources_cannot_cause_more_trace_rows_than_the_cross_source_brake_allows(client, settings, monkeypatch, caplog):
    """The per-source budget bounds ONE source; a caller who can pick its own source per request
    (a trusted-proxy hop count set too high lets it pick its left-hand X-Forwarded-For entry)
    gets a fresh per-source budget every time. Every response is still the ordinary one; only
    the rows stop, and the skip is counted and reported once a minute."""
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE = (3, 3600)
    clock = FakeClock(monkeypatch)
    caplog.set_level(logging.WARNING)

    codes = _fail_from_many_sources(client, 10)

    assert codes == ["VALIDATION_FAILED"] * 10, "the brake changed a response"
    assert len(failed_rows()) == 3
    # Nothing was REFUSED, so the shared guard's "refusing requests (RATE_LIMITED)" warning would
    # be false here; the brake reports its own skips (below) in its own words.
    assert not [r for r in caplog.records if "is refusing requests" in r.getMessage()]
    skipped = [r.getMessage() for r in caplog.records if "skipped" in r.getMessage() and r.name == services.__name__]
    assert len(skipped) == 1 and "skipped 1 audit row(s)" in skipped[0]
    # The first skipped row is reported at once, readable and not cut off, and it names the source
    # by its pseudonym, never by the address (the 4th source is the first one past the limit of 3).
    assert "reason=shared brake spent" in skipped[0], skipped[0]
    assert pseudo("198.51.100.4") in skipped[0] and "198.51.100.4" not in skipped[0].replace(pseudo("198.51.100.4"), "")
    clock.advance(services._TRACE_REPORT_INTERVAL_SECONDS + 1)
    _fail_from_many_sources(client, 1, first=11)
    skipped = [r.getMessage() for r in caplog.records if "skipped" in r.getMessage() and r.name == services.__name__]
    assert len(skipped) == 2 and "skipped 7 audit row(s)" in skipped[1], skipped


@pytest.mark.django_db
def test_a_reset_still_completes_while_the_trace_brake_is_spent(client, sender, settings):
    reset_token = live_reset_token(client, sender)
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE = (1, 3600)
    _fail_from_many_sources(client, 3)
    assert len(failed_rows()) == 1

    done = confirm(client, reset_token, GOOD_PASSWORD, REMOTE_ADDR="198.51.100.200")

    assert body(done)["data"]["confirmPasswordReset"]["reset"] is True


class _CountingBrokenStore(_BrokenStore):
    def __init__(self):
        self.calls = 0

    def incr_with_expiry(self, key, window_seconds):
        self.calls += 1
        return super().incr_with_expiry(key, window_seconds)


@pytest.mark.django_db
def test_while_the_limiter_store_is_down_a_process_local_ceiling_bounds_the_rows(client, sender, settings, monkeypatch):
    """With the store down every budget fails open -- right for the response -- and nothing would
    bound the rows. The ceiling is per worker, charged on every failure, and skips only the row."""
    settings.SELAHCUE_RESET_CONFIRM_TRACE_DEGRADED_CEILING = (3, 3600)
    reset_token = live_reset_token(client, sender)
    store = _CountingBrokenStore()
    monkeypatch.setattr(guards, "CacheStore", lambda _cache: store)

    codes = _fail_from_many_sources(client, 10)
    done = confirm(client, reset_token, GOOD_PASSWORD)

    assert codes == ["VALIDATION_FAILED"] * 10
    # One store round trip per request -- the per-source budget's. Once that has failed open the
    # cross-source brake is NOT consulted as well: against a stalled Redis that would cost a
    # second socket timeout on every failed confirm for no extra protection.
    assert store.calls == 11, store.calls
    assert len(failed_rows()) == 3, "the outage ceiling did not bound the rows"
    assert body(done)["data"]["confirmPasswordReset"]["reset"] is True, "the ceiling must never refuse a reset"


@pytest.mark.django_db
def test_the_trace_brakes_hold_bounded_state_however_many_sources_there_are(client, settings, monkeypatch):
    """Bounded memory, in a form that bites: 300 distinct sources, and the shared brake still
    touches ONE limiter key (a per-source key would make it 300), while the report tallies hold
    only scalars, a capped string and a capped set of account ids (a per-source map or list would
    not). Keys are recorded where the code spends a budget, not read off the cache: the cache
    here is LocMemCache, whose `_cache` Redis has no equivalent of, and CI runs Redis."""
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE = (5, 3600)
    touched = _record_limiter_keys(monkeypatch)

    _fail_from_many_sources(client, 250)
    v6_codes = [
        error_code(confirm(client, "SC-PRS-flood-v6", GOOD_PASSWORD, REMOTE_ADDR=f"2001:db8:{n:x}::1"))
        for n in range(50)
    ]

    assert v6_codes == ["VALIDATION_FAILED"] * 50
    assert len(failed_rows()) == 5
    brake_keys = [key for key in touched if services.RESET_CONFIRM_TRACE_SCOPE in key]
    assert len(brake_keys) == 1, brake_keys
    # CONTROL: the recorder saw the per-source keys too, i.e. it records what the code touches.
    assert len([key for key in touched if "password_reset_confirm_ip" in key]) >= 250
    scalars = (int, float, str, type(threading.Lock()))
    for tally in (services._trace_lost_tally, services._trace_skipped_tally):
        assert all(
            isinstance(value, scalars) or (isinstance(value, set) and all(isinstance(i, int) for i in value))
            for value in vars(tally).values()
        ), vars(tally)
        assert len(tally._first) <= services._TRACE_REPORT_DETAIL_MAX
        assert len(tally._accounts) <= services._TRACE_REPORT_ACCOUNTS_MAX
def test_the_shipped_trace_brakes_are_pinned(settings):
    """The module defaults and the shipped settings agree, and the numbers are pinned: a brake
    inflated to nothing passes every behavioural test, which tighten it to make it trip."""
    assert services.RESET_CONFIRM_TRACE_BUDGET == (1000, 3600)
    assert services.RESET_CONFIRM_TRACE_DEGRADED_CEILING == (200, 3600)
    assert services.RESET_CONFIRM_TRACE_ACCOUNT_BUDGET == (60, 3600)
    assert services.RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING == (30, 3600)
    assert services.RESET_CONFIRM_TRACE_ACCOUNT_TABLE_MAX == 1024
    assert settings.SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE == services.RESET_CONFIRM_TRACE_BUDGET
    assert settings.SELAHCUE_RESET_CONFIRM_TRACE_DEGRADED_CEILING == services.RESET_CONFIRM_TRACE_DEGRADED_CEILING
    assert settings.SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE_ACCOUNT == services.RESET_CONFIRM_TRACE_ACCOUNT_BUDGET
    assert (
        settings.SELAHCUE_RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING
        == services.RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING
    )
    assert services._reset_confirm_trace_account_ceilings._max_entries == services.RESET_CONFIRM_TRACE_ACCOUNT_TABLE_MAX


# --- the write itself: a failed INSERT leaves nothing and poisons nothing ---------------------
@pytest.mark.django_db
def test_a_failed_trace_write_leaves_no_half_row_and_does_not_poison_the_callers_transaction(client, monkeypatch):
    """The recorder runs under an enclosing transaction here (pytest-django's, plus an explicit
    one), where its `atomic()` is a savepoint. The write succeeds and is then followed by a real
    database IntegrityError. Without the savepoint the half-written row would survive; and a
    follow-up query, and the next failure's own trace, must still work."""
    real = services.record_audit_event

    def write_then_violate_a_constraint(actor, **kwargs):
        row = real(actor, **kwargs)
        AuditEvent(
            pk=row.pk, actor_kind="x", actor_id="x", action="x", target_type="x", target_id="x", request_id="x"
        ).save(force_insert=True)

    monkeypatch.setattr(services, "record_audit_event", write_then_violate_a_constraint)
    with transaction.atomic():
        assert error_code(confirm(client, "SC-PRS-whatever", GOOD_PASSWORD)) == "VALIDATION_FAILED"
        assert failed_rows() == [], "a half-written row survived the failed write"
        assert CustomerUser.objects.count() == 0, "the caller's transaction was poisoned"

        monkeypatch.setattr(services, "record_audit_event", real)
        assert error_code(confirm(client, "SC-PRS-whatever-else", GOOD_PASSWORD)) == "VALIDATION_FAILED"
        assert len(failed_rows()) == 1


@pytest.mark.django_db
def test_a_spent_verification_token_is_traced_as_the_wrong_kind_of_token(client, sender):
    """A token that is BOTH consumed and the wrong purpose (the email-verification link every
    signup spends). The label is a decision and it is pinned here: `wrong_purpose`. The kind of
    token is the more basic fact -- it could never have reset a password, spent or not -- and
    `consumed` would hide that someone is offering a verification link to the reset mutation."""
    signup_and_verify(client, sender)
    spent_verification = sender.verify_tokens[-1]
    row = token_row(spent_verification)
    assert row.purpose == CredentialTokenPurpose.EMAIL_VERIFY and row.consumed_at is not None, (
        "the premise: a SPENT verification token"
    )

    assert error_code(confirm(client, spent_verification, GOOD_PASSWORD)) == "VALIDATION_FAILED"

    (traced,) = failed_rows()
    assert traced.after == {"outcome": OUTCOME.WRONG_PURPOSE.value}


@pytest.mark.django_db
@pytest.mark.filterwarnings("ignore::django.core.cache.backends.base.CacheKeyWarning")
def test_a_hostile_remote_addr_is_never_stored_raw(client):
    """`client_ip()` falls back to the raw REMOTE_ADDR text when it does not parse. Only the server
    sets that value, never a client header, but if it were hostile nothing may store it: the
    actor id is a hash, `after` holds only the outcome, the attempt id is random."""
    hostile = "evil\x1b[31m host\n'; DROP TABLE x;--"

    assert error_code(confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR=hostile)) == "VALIDATION_FAILED"

    (row,) = failed_rows()
    assert re.fullmatch(r"src:v1:[0-9a-f]{32}", row.actor_id)
    assert row.after == {"outcome": OUTCOME.UNKNOWN_TOKEN.value}
    text = failed_rows_as_text()
    assert "evil" not in text and "DROP" not in text
    for column in (row.actor_id, row.request_id, row.target_type, row.target_id, row.source_surface, row.reason):
        assert column.isprintable(), repr(column)


def _record_limiter_keys(monkeypatch):
    """Record every limiter key the code touches. Recorded at `evaluate_budget`, the same way
    tests/test_password_reset_throttle.py does, so an assertion means the same thing on
    LocMemCache (local) and Redis (CI), where `cache._cache` does not exist."""
    touched = {}
    real_evaluate = guards.evaluate_budget

    def recording(store, key, limit, window_seconds):
        touched[key] = window_seconds
        return real_evaluate(store, key, limit, window_seconds)

    monkeypatch.setattr(guards, "evaluate_budget", recording)
    return touched


# --- the two allowances: noise cannot blind the trace to a probe of an account's link ----------
def _fresh_account_with_a_live_link(client, sender, tag):
    """A verified account with a live reset link; returns (user id, raw token)."""
    email = f"{tag}@grace.example"
    token = live_reset_token(client, sender, email=email)
    return CustomerUser.objects.get(email=email).id, token


def _rows_naming(user_id):
    return [row for row in failed_rows() if (row.target_type, row.target_id) == ("customer_user", str(user_id))]


@pytest.mark.django_db
def test_a_flood_of_unauthenticated_noise_cannot_blind_the_trace_to_a_probe_of_an_account(
    client, sender, settings
):
    """The shared brake is spent only by outcomes that NAME NO ACCOUNT. With it fully spent by 50
    sources' unknown tokens, a rejected password behind account B's live link and a wrong-purpose
    token of account C -- the shapes a probe of a skimmed link takes -- still leave their rows."""
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE = (3, 3600)
    user_b, token_b = _fresh_account_with_a_live_link(client, sender, "bravo")
    verify_c = live_verify_token(client, sender, idem="noise-purpose-0001", email="charlie@grace.example")
    user_c = token_row(verify_c).customer_user_id

    codes = _fail_from_many_sources(client, 50)
    assert codes == ["VALIDATION_FAILED"] * 50
    assert len(failed_rows()) == 3, "the shared brake did not stop at its limit"

    assert error_code(confirm(client, token_b, SHORT_PASSWORD, REMOTE_ADDR="198.51.100.201")) == "PASSWORD_INVALID"
    assert error_code(confirm(client, verify_c, GOOD_PASSWORD, REMOTE_ADDR="198.51.100.202")) == "VALIDATION_FAILED"

    assert [row.after["outcome"] for row in _rows_naming(user_b)] == [OUTCOME.PASSWORD_REJECTED.value]
    assert [row.after["outcome"] for row in _rows_naming(user_c)] == [OUTCOME.WRONG_PURPOSE.value]


@pytest.mark.django_db
def test_one_accounts_allowance_is_its_own_and_noise_cannot_spend_it(client, sender, settings):
    """Account A is probed six times with an allowance of three: exactly three rows for A. A
    stranger's unknown tokens first, and a flood against A, leave account B's row untouched,
    and the stranger's noise did not spend A's allowance either."""
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE_ACCOUNT = (3, 3600)
    user_a, token_a = _fresh_account_with_a_live_link(client, sender, "alpha")
    user_b, token_b = _fresh_account_with_a_live_link(client, sender, "bravo")

    _fail_from_many_sources(client, 10)  # noise that names no account
    for n in range(6):
        confirm(client, token_a, SHORT_PASSWORD, REMOTE_ADDR=f"203.0.113.{n + 10}")
    confirm(client, token_b, SHORT_PASSWORD, REMOTE_ADDR="203.0.113.99")

    assert len(_rows_naming(user_a)) == 3, "the per-account allowance did not bound the rows"
    assert len(_rows_naming(user_b)) == 1, "a flood against account A stopped a row for account B"
    assert len(failed_rows()) == 10 + 3 + 1, "the stranger's noise spent someone's allowance"
    assert token_row(token_a).consumed_at is None and token_row(token_b).consumed_at is None


@pytest.mark.django_db
def test_while_the_limiter_store_is_down_each_account_has_its_own_process_local_allowance(
    client, sender, settings, monkeypatch
):
    """The same split in the outage ceiling: noise spends the shared per-worker ceiling, a named
    outcome spends only its account's, and a second account is unaffected by the first."""
    user_a, token_a = _fresh_account_with_a_live_link(client, sender, "alpha")
    user_b, token_b = _fresh_account_with_a_live_link(client, sender, "bravo")
    settings.SELAHCUE_RESET_CONFIRM_TRACE_DEGRADED_CEILING = (2, 3600)
    settings.SELAHCUE_RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING = (2, 3600)
    monkeypatch.setattr(guards, "CacheStore", lambda _cache: _BrokenStore())

    noise = _fail_from_many_sources(client, 6)
    a_codes = [error_code(confirm(client, token_a, SHORT_PASSWORD)) for _ in range(5)]
    b_codes = [error_code(confirm(client, token_b, SHORT_PASSWORD)) for _ in range(3)]

    assert noise == ["VALIDATION_FAILED"] * 6 and a_codes == ["PASSWORD_INVALID"] * 5 and b_codes == ["PASSWORD_INVALID"] * 3
    assert len(failed_rows()) - len(_rows_naming(user_a)) - len(_rows_naming(user_b)) == 2, "shared ceiling"
    assert len(_rows_naming(user_a)) == 2, "account A's process-local allowance did not bound its rows"
    assert len(_rows_naming(user_b)) == 2, "account B was held to account A's spent allowance"


def test_the_per_account_outage_table_is_bounded_and_counts_each_account_separately(monkeypatch):
    """Bounded memory, in a form that bites: 5000 distinct accounts through a table of 8 never hold
    more than 8, the limit still applies per account, and a window that has lapsed starts over."""
    clock = FakeClock(monkeypatch)
    table = services._AccountCeilings(setting_name="W2_UNSET_SETTING", default=(2, 3600), max_entries=8)

    for account in range(5000):
        assert table.claim(account) is True
    assert len(table._windows) <= 8

    table.reset()
    assert [table.claim(1), table.claim(1), table.claim(1), table.claim(2)] == [True, True, False, True]
    clock.advance(3601)
    assert table.claim(1) is True, "a lapsed window must start over"


def test_the_skip_report_names_at_most_twenty_distinct_accounts():
    tally = services._SuppressedTally()
    assert tally.note("first", 7) is not None  # the first event is released immediately
    for account in range(100):
        tally.note("again", account)
    assert len(tally._accounts) <= services._TRACE_REPORT_ACCOUNTS_MAX
    tally._last_report = float("-inf")
    count, first, accounts = tally.note("last", 3)
    assert len(accounts) <= services._TRACE_REPORT_ACCOUNTS_MAX and accounts == sorted(accounts)
    assert count == 101


@pytest.mark.django_db
def test_the_skip_report_lists_the_accounts_whose_rows_were_skipped(client, sender, settings, monkeypatch, caplog):
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE_ACCOUNT = (1, 3600)
    user_a, token_a = _fresh_account_with_a_live_link(client, sender, "alpha")
    user_b, token_b = _fresh_account_with_a_live_link(client, sender, "bravo")
    clock = FakeClock(monkeypatch)
    caplog.set_level(logging.WARNING)

    for token in (token_a, token_a, token_b, token_b):
        confirm(client, token, SHORT_PASSWORD)
    clock.advance(services._TRACE_REPORT_INTERVAL_SECONDS + 1)
    confirm(client, token_a, SHORT_PASSWORD)

    skipped = [r.getMessage() for r in caplog.records if "skipped" in r.getMessage() and r.name == services.__name__]
    assert len(skipped) == 2 and "reason=account allowance spent" in skipped[0], skipped[0]
    assert f"accounts [{min(user_a, user_b)}, {max(user_a, user_b)}]" in skipped[1], skipped[1]


# --- the whole trace body is protected, not just the INSERT ------------------------------------
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("setting", "value", "outage", "named"),
    [
        ("SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE", "garbage", False, False),
        ("SELAHCUE_THROTTLE_RESET_CONFIRM_TRACE_ACCOUNT", "garbage", False, True),
        ("SELAHCUE_RESET_CONFIRM_TRACE_DEGRADED_CEILING", 5, True, False),
        ("SELAHCUE_RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING", 5, True, True),
    ],
)
def test_a_malformed_trace_setting_never_changes_the_answer(
    client, sender, settings, monkeypatch, caplog, setting, value, outage, named
):
    """`_trace_failed_confirm` runs while the original failure is being handled; anything it raises
    would REPLACE that failure (the view then masks it, so a rejected password would be answered
    as a dead token). A malformed setting here must cost a counted row, never the answer."""
    reset_token = live_reset_token(client, sender)
    token, password, code = (reset_token, SHORT_PASSWORD, "PASSWORD_INVALID") if named else ("SC-PRS-nope", GOOD_PASSWORD, "VALIDATION_FAILED")
    healthy = confirm(client, token, password).content
    rows_before = len(failed_rows())
    if outage:
        monkeypatch.setattr(guards, "CacheStore", lambda _cache: _BrokenStore())
    setattr(settings, setting, value)
    services._reset_trace_reporting()
    caplog.clear()

    resp = confirm(client, token, password)

    assert error_code(resp) == code and resp.content == healthy, "a malformed trace setting changed the answer"
    assert len(failed_rows()) == rows_before, "a row was written despite the malformed setting"
    assert [r for r in caplog.records if r.name == services.__name__ and "could not write the audit row" in r.getMessage()]


# --- the day seam's real body, which every other test replaces ---------------------------------
_REAL_AUDIT_SOURCE_DAY = services._audit_source_day


def test_the_real_audit_source_day_is_the_utc_date(monkeypatch):
    from datetime import datetime, timedelta, timezone

    before = datetime.now(timezone.utc).date()
    got = _REAL_AUDIT_SOURCE_DAY()
    assert got in {before, datetime.now(timezone.utc).date()}
    # Not the local date, not today's date by another route: an aware time late on the 26th at
    # UTC-5 is already the 27th in UTC.
    monkeypatch.setattr(
        services.djtz, "now", lambda: datetime(2026, 10, 26, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    )
    assert _REAL_AUDIT_SOURCE_DAY() == date(2026, 10, 27)


@pytest.mark.django_db
def test_the_operator_command_defaults_to_today(client, monkeypatch):
    monkeypatch.setattr(services, "_audit_source_day", _REAL_AUDIT_SOURCE_DAY)
    confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR="203.0.113.5")

    out = StringIO()
    call_command("failed_reset_confirms", ip="203.0.113.5", stdout=out)

    assert "1 failed confirm(s)" in out.getvalue()


@pytest.mark.django_db
def test_an_unencodable_token_is_a_malformed_token_with_the_ordinary_answer(client):
    """Lone surrogates in `token`: hashing would raise. Same collapsed answer, byte for byte, as
    an unknown token, and traced as malformed, not as an internal error."""
    dead = confirm(client, "SC-PRS-nobody-minted-this", GOOD_PASSWORD).content

    resp = confirm(client, "\ud800" * 20, GOOD_PASSWORD)

    assert resp.content == dead
    assert [row.after["outcome"] for row in failed_rows()] == [
        OUTCOME.UNKNOWN_TOKEN.value,
        OUTCOME.MALFORMED_TOKEN.value,
    ]


# --- the UTF-8 check must not turn into an ASCII check ---------------------------------------
NON_ASCII_PASSWORDS = [
    pytest.param("caf\u00e9-cr\u00e8me-br\u00fbl\u00e9e-1", id="accented"),
    pytest.param("\u5bc6\u7801\u5f88\u5b89\u5168\u7684\u5bc6\u7801\u5341\u4e2a\u5b57", id="cjk"),
    pytest.param("horse-\U0001F525-battery-staple", id="emoji"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("password", NON_ASCII_PASSWORDS)
def test_non_ascii_passwords_are_still_accepted_at_signup_and_at_reset(client, sender, password):
    """`_validate_password` now refuses strings that cannot be UTF-8 encoded (lone surrogates). A
    check written as `.encode("ascii")` would pass every test that uses an ASCII password and
    reject every legitimate accented, CJK or emoji one. Pinned through both callers."""
    assert services.MIN_PASSWORD_LENGTH <= len(password) <= services.MAX_PASSWORD_LENGTH, "the premise"
    email = "unicode@grace.example"

    signup = post_account(client, REGISTER, register_input(idem="signup-unicode-1", email=email, password=password))
    assert body(signup)["data"]["registerCustomerUser"]["accepted"] is True
    assert check_password(password, CustomerUser.objects.get(email=email).password_hash)

    post_account(client, VERIFY, {"t": sender.verify_tokens[-1]})
    post_account(client, REQUEST_RESET, {"e": email})
    new_password = password + "-2"
    done = confirm(client, sender.reset_tokens[-1], new_password)

    assert body(done)["data"]["confirmPasswordReset"]["reset"] is True
    assert check_password(new_password, CustomerUser.objects.get(email=email).password_hash)
    assert failed_rows() == []
    login = post_account(client, LOGIN, {"input": {"email": email, "password": new_password}})
    assert body(login)["data"]["login"]["sessionToken"]


# --- the unexpected-failure branch honours the degraded flag too -------------------------------
@pytest.mark.django_db
def test_an_unexpected_failure_does_not_ask_the_failed_store_a_second_time(client, sender, settings, monkeypatch):
    """The wrapper has two failure branches and both must pass the per-source budget's fail-open on
    to the trace. If the unexpected-failure branch forgot it, every such failure would cost a
    second round trip to a store already known to be down (a second socket timeout against a
    stalled Redis). Counted at the store; rows are still bounded by the account's outage allowance."""
    reset_token = live_reset_token(client, sender)
    settings.SELAHCUE_RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING = (2, 3600)
    store = _CountingBrokenStore()
    monkeypatch.setattr(guards, "CacheStore", lambda _cache: store)

    def explode(*args, **kwargs):
        raise OperationalError("database is gone")

    monkeypatch.setattr(services, "make_password", explode)
    for _ in range(3):
        assert error_code(confirm(client, reset_token, GOOD_PASSWORD)) == "VALIDATION_FAILED"

    assert store.calls == 3, f"{store.calls} store round trips for 3 requests"
    assert [row.after["outcome"] for row in failed_rows()] == [OUTCOME.INTERNAL_ERROR.value] * 2


# --- the day basis, pinned near UTC midnight ----------------------------------------------------
@pytest.mark.django_db
def test_the_pseudonym_day_is_the_utc_day_across_midnight_and_the_command_agrees(client, monkeypatch):
    """Frozen at 23:59:30 UTC on the 26th, written at -05:00 (so the wall clock there still says
    the 26th, 18:59), then at 00:00:30 UTC on the 27th (19:00:30 at -05:00): two rows, two
    pseudonyms, one per UTC day. The operator command with no --date uses the same day the
    writer used, at each moment."""
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr(services, "_audit_source_day", _REAL_AUDIT_SOURCE_DAY)
    est = timezone(timedelta(hours=-5))
    late = datetime(2026, 10, 26, 18, 59, 30, tzinfo=est)  # 23:59:30 UTC, the 26th
    monkeypatch.setattr(services.djtz, "now", lambda: late)
    confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR="203.0.113.5")
    out_26 = StringIO()
    call_command("failed_reset_confirms", ip="203.0.113.5", stdout=out_26)

    monkeypatch.setattr(services.djtz, "now", lambda: late + timedelta(seconds=60))  # 00:00:30 UTC, the 27th
    confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR="203.0.113.5")
    out_27 = StringIO()
    call_command("failed_reset_confirms", ip="203.0.113.5", stdout=out_27)

    first, second = failed_rows()
    assert first.actor_id == pseudo("203.0.113.5", date(2026, 10, 26))
    assert second.actor_id == pseudo("203.0.113.5", date(2026, 10, 27))
    assert "pseudonym for 2026-10-26" in out_26.getvalue() and "1 failed confirm(s)" in out_26.getvalue()
    assert "pseudonym for 2026-10-27" in out_27.getvalue() and "1 failed confirm(s)" in out_27.getvalue()


# --- the operator command's own behaviour --------------------------------------------------------
def _run_command(**options):
    out = StringIO()
    call_command("failed_reset_confirms", stdout=out, **options)
    return out.getvalue()


@pytest.mark.django_db
def test_the_command_caps_its_output_and_says_so(client, monkeypatch):
    from selahcue_api.apps.accounts.management.commands import failed_reset_confirms as command

    assert command.MAX_ROWS == 500
    for _ in range(4):
        confirm(client, "SC-PRS-whatever", GOOD_PASSWORD)
    monkeypatch.setattr(command, "MAX_ROWS", 3)

    text = _run_command(ip=TEST_CLIENT_ADDR, date="2026-10-26")

    assert text.count("outcome=") == 3 and "3 failed confirm(s) (first 3 shown)" in text


@pytest.mark.django_db
def test_the_command_shows_the_account_when_the_token_resolved_and_a_dash_when_not(client, sender):
    email = "pastor@grace.example"
    reset_token = live_reset_token(client, sender, email=email)
    user = CustomerUser.objects.get(email=email)
    confirm(client, "SC-PRS-nobody-minted-this", GOOD_PASSWORD)
    confirm(client, reset_token, SHORT_PASSWORD)

    lines = [line for line in _run_command(ip=TEST_CLIENT_ADDR, date="2026-10-26").splitlines() if "outcome=" in line]

    assert [line.split("outcome=")[1] for line in lines] == [
        "unknown_token  account=-",
        f"password_rejected  account={user.id}",
    ]


@pytest.mark.django_db
def test_the_command_accepts_an_address_with_surrounding_whitespace(client):
    confirm(client, "SC-PRS-whatever", GOOD_PASSWORD, REMOTE_ADDR="203.0.113.5")

    assert "1 failed confirm(s)" in _run_command(ip="  203.0.113.5 \t", date="2026-10-26")


# --- AUTH-6: account-based device activation --------------------------------
ACTIVATE = """
    mutation Activate($input: ActivateDeviceInput!) {
      activateDeviceWithSession(input: $input) { fullToken created devicePublicId platform }
    }
"""


def active_license_key(org, *, device_limit=2):
    return AppLicenseKey.objects.create(
        customer=org, key_type="TRIAL", status=LicenseKeyStatus.ACTIVATED,
        key_prefix="SC-LK", key_suffix="ZZZZ", masked_key="SC-LK...ZZZZ",
        secret_hash="x", secret_fingerprint=f"lkfp-{org.id}", feature_scope="core", territory="GLOBAL",
        starts_at=timezone.now() - timezone.timedelta(days=1), expires_at=timezone.now() + timezone.timedelta(days=30),
        timezone="UTC", seat_limit=5, device_limit=device_limit,
        generated_by_actor_id="staff", generated_reason="test fixture", idempotency_key=f"lk-{org.id}",
    )


def login_token(client, email, password):
    return body(post_account(client, LOGIN, {"input": {"email": email, "password": password}}))["data"]["login"]["sessionToken"]


def activate_input(idem, fingerprint="install-1"):
    return {"input": {"idempotencyKey": idem, "deviceFingerprint": fingerprint, "platform": "macos"}}


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=False)
@pytest.mark.django_db
def test_admin_activates_device_via_session_without_enrollment_key(client, sender):
    email, password = signup_and_verify(client, sender)
    token = login_token(client, email, password)
    active_license_key(CustomerOrg.objects.get(), device_limit=2)

    resp = post_account(client, ACTIVATE, activate_input("act-session-0001"), bearer=token)
    data = body(resp)["data"]["activateDeviceWithSession"]
    assert data["created"] is True
    assert data["fullToken"] and data["fullToken"].startswith("SC-DEV-")
    assert data["devicePublicId"].startswith("dev_")
    from selahcue_api.apps.devices.models import DeviceToken
    assert DeviceToken.objects.count() == 1


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=False)
@pytest.mark.django_db
def test_device_limit_enforced_on_account_path(client, sender):
    email, password = signup_and_verify(client, sender)
    token = login_token(client, email, password)
    active_license_key(CustomerOrg.objects.get(), device_limit=1)

    first = post_account(client, ACTIVATE, activate_input("act-lim-0001", "dev-a"), bearer=token)
    assert body(first)["data"]["activateDeviceWithSession"]["created"] is True
    second = post_account(client, ACTIVATE, activate_input("act-lim-0002", "dev-b"), bearer=token)
    assert error_code(second) == "POLICY_DENIED"


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=False)
@pytest.mark.django_db
def test_member_is_denied_device_activation(client, sender):
    signup_and_verify(client, sender)  # first user is ADMIN
    org = CustomerOrg.objects.get()
    active_license_key(org, device_limit=2)
    # a second, MEMBER user in the same org
    member_pw = "member-passphrase-1"
    CustomerUser.objects.create(
        customer=org, email="member@grace.example", email_fingerprint=services._fingerprint("member@grace.example"),
        password_hash=make_password(member_pw), status=CustomerUserStatus.ACTIVE, role=CustomerRole.MEMBER,
        email_verified_at=timezone.now(), created_by_actor_id="test", idempotency_key="member-user-001",
    )
    token = login_token(client, "member@grace.example", member_pw)
    resp = post_account(client, ACTIVATE, activate_input("act-mem-0001"), bearer=token)
    assert error_code(resp) == "PERMISSION_DENIED"


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=False)
@pytest.mark.django_db
def test_activation_without_active_license_is_not_found(client, sender):
    email, password = signup_and_verify(client, sender)
    token = login_token(client, email, password)  # org has NO license key
    resp = post_account(client, ACTIVATE, activate_input("act-nolk-0001"), bearer=token)
    assert error_code(resp) == "NOT_FOUND"


@override_settings(SELAHCUE_TRUST_ACTOR_HEADERS=False)
@pytest.mark.django_db
def test_account_activation_is_idempotent(client, sender):
    email, password = signup_and_verify(client, sender)
    token = login_token(client, email, password)
    active_license_key(CustomerOrg.objects.get(), device_limit=2)
    first = post_account(client, ACTIVATE, activate_input("act-idem-0001", "same-fp"), bearer=token)
    second = post_account(client, ACTIVATE, activate_input("act-idem-0001", "same-fp"), bearer=token)
    assert body(first)["data"]["activateDeviceWithSession"]["created"] is True
    # replay: same device, token NOT re-shown (show-once)
    assert body(second)["data"]["activateDeviceWithSession"]["created"] is False
    assert body(second)["data"]["activateDeviceWithSession"]["fullToken"] is None
    from selahcue_api.apps.devices.models import Device, DeviceToken
    assert Device.objects.count() == 1 and DeviceToken.objects.count() == 1
