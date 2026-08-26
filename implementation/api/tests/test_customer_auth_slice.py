"""Traditional email/password customer auth (DEC-007 / ADR-0023) — AUTH-2..AUTH-5.

Covers self-serve signup, email verification, login/session/logout/refresh, and password reset,
with the no-enumeration + session-invalidation invariants.
"""

import json

import pytest
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
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
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus


# --- helpers ---------------------------------------------------------------
def post_account(client, query, variables=None, *, bearer=None):
    extra = {}
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


@pytest.mark.django_db
def test_raw_verify_token_never_stored_plaintext(client, sender):
    post_account(client, REGISTER, register_input())
    raw = sender.verify_tokens[-1]
    ct = CredentialToken.objects.get(purpose=CredentialTokenPurpose.EMAIL_VERIFY)
    assert raw != ct.token_hash and raw not in ct.token_hash
    assert raw != ct.token_fingerprint
    assert ct.masked_token != raw


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
        timezone="UTC", device_limit=1,
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
        timezone="UTC", device_limit=device_limit,
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
