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
