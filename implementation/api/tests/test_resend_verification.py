"""Resend-verification mutation (86ak120ac / DEC-007).

Uma's /verify states V3-V6 and desktop A13 all offer "Resend verification email"; before
this slice there was no mutation anywhere in the API for them to call, so a user whose
24-hour link lapsed had no self-service route back — they could not verify, could not sign
in, and could not ask for a new link.

THE TWO PROPERTIES THIS FILE PINS
---------------------------------
1. NO ENUMERATION. The response is byte-identical for an unknown address, a known
   unverified account, and a known already-verified account. An unauthenticated
   email-sending endpoint is a particularly attractive existence oracle.
2. NO TIMING ORACLE. Dispatching a real email is measurably slower than doing nothing —
   `make_password` alone is ~120ms on the reference machine — so a naive implementation
   leaks existence through latency even with an identical body. `test_response_timing_...`
   is a real probe, and it runs against a sender that simulates broker latency so the
   dispatch cost is inside the measured window rather than assumed away.
"""

import json
import statistics
import time

import pytest
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import (
    CredentialToken,
    CredentialTokenPurpose,
    CustomerOrg,
    CustomerRole,
    CustomerStatus,
    CustomerUser,
    CustomerUserStatus,
)
from selahcue_api.apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db


RESEND = """
    mutation Resend($e: String!) {
      resendVerificationEmail(email: $e) { accepted }
    }
"""
VERIFY = "mutation Verify($t: String!) { verifyEmail(token: $t) { verified } }"


@pytest.fixture(autouse=True)
def _fresh_throttle_budget():
    """The resend budget lives in the default LocMemCache, which persists for the whole
    pytest process — spent budget would otherwise leak between tests and rate-limit them."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture(autouse=True)
def _no_constant_time_floor(settings):
    """Every resend is padded to a fixed duration to close the timing oracle. That is the
    point of the feature, but it would add a quarter-second to every test here, so the
    floor is switched off by default and switched back ON explicitly by the timing test —
    the only test whose subject it actually is."""
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0.0


class CapturingSender(services.EmailSender):
    def __init__(self, dispatch_delay=0.0):
        self.verify_tokens = []
        self.dispatch_delay = dispatch_delay

    def send_email_verification(self, user, raw_token):
        # Simulates the broker round trip a real `.delay()` performs, so the timing probe
        # measures a dispatch cost instead of pretending it is free.
        if self.dispatch_delay:
            time.sleep(self.dispatch_delay)
        self.verify_tokens.append(raw_token)


@pytest.fixture
def sender():
    captured = CapturingSender()
    services.set_email_sender(captured)
    yield captured
    services.set_email_sender(services.EmailSender())


def post_account(client, query, variables=None):
    # Dispatch is registered with `transaction.on_commit`, which under django_db's rollback
    # would never fire. This is Django's own API for running the callbacks still pending at
    # the end of the request; ones discarded by a rolled-back savepoint are NOT among them.
    with TestCase.captureOnCommitCallbacks(execute=True):
        return client.post(
            "/graphql/account",
            data=json.dumps({"query": query, "variables": variables or {}}),
            content_type="application/json",
        )


def body(response):
    return json.loads(response.content)


def error_code(response):
    errors = body(response).get("errors") or []
    return (errors[0].get("extensions") or {}).get("code") if errors else None


def resend(client, email):
    return post_account(client, RESEND, {"e": email})


def _make_user(email, *, verified=False, status=None, tag="x"):
    """Create an org + user directly. Deliberately NOT via the signup mutation: that costs a
    PBKDF2 hash per user and the timing test needs a dozen of them."""
    org = CustomerOrg.objects.create(
        name=f"Resend Church {tag}",
        slug=f"resend-church-{tag}",
        status=CustomerStatus.TRIAL,
        primary_contact_email=email,
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        created_by_actor_id="test",
        idempotency_key=f"resend-org-{tag}",
    )
    return CustomerUser.objects.create(
        customer=org,
        email=email,
        email_fingerprint=services._email_fingerprint(email),
        password_hash="pbkdf2_sha256$dummy",
        status=status or (CustomerUserStatus.ACTIVE if verified else CustomerUserStatus.INVITED),
        role=CustomerRole.ADMIN,
        email_verified_at=timezone.now() if verified else None,
        created_by_actor_id="test",
        idempotency_key=f"resend-user-{tag}",
    )


# --- AC1: a real resend works -----------------------------------------------------------
def test_unverified_account_receives_a_fresh_verification_link(client, sender):
    _make_user("pastor@resend.example", tag="fresh")

    response = resend(client, "pastor@resend.example")

    assert response.status_code == 200
    assert body(response)["data"]["resendVerificationEmail"]["accepted"] is True
    assert len(sender.verify_tokens) == 1
    assert sender.verify_tokens[0].startswith("SC-EVF-")


def test_the_resent_link_completes_verification_end_to_end(client, sender, settings):
    """AC6 through the REAL stack: service -> Celery task -> rendered template -> the link
    in the delivered message actually verifies. (MailHog is the compose equivalent of
    `mail.outbox`; both assert the message that would leave the process.)"""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    settings.FRONTEND_BASE_URL = "https://app.selahcue.test"
    services.set_email_sender(services.get_email_sender())
    from selahcue_api.apps.accounts.email import CeleryEmailSender

    services.set_email_sender(CeleryEmailSender())
    user = _make_user("stranded@resend.example", tag="e2e")
    mail.outbox.clear()

    resend(client, "stranded@resend.example")

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["stranded@resend.example"]
    marker = "/verify?token="
    assert marker in message.body
    token = message.body.split(marker, 1)[1].split()[0].strip().rstrip(".,)")

    verified = post_account(client, VERIFY, {"t": token})
    assert body(verified)["data"]["verifyEmail"]["verified"] is True
    user.refresh_from_db()
    assert user.status == CustomerUserStatus.ACTIVE
    assert user.email_verified_at is not None


# --- AC2: no enumeration ----------------------------------------------------------------
def test_the_three_cases_are_byte_identical(client, sender):
    """Unknown / known-unverified / known-already-verified must be indistinguishable. Any
    difference in status, body or field set re-introduces the oracle the rest of the
    accounts surface was written to avoid."""
    _make_user("unverified@resend.example", tag="enum-u")
    _make_user("verified@resend.example", verified=True, tag="enum-v")

    unknown = resend(client, "ghost@resend.example")
    unverified = resend(client, "unverified@resend.example")
    already = resend(client, "verified@resend.example")

    assert unknown.status_code == unverified.status_code == already.status_code == 200
    assert unknown.content == unverified.content == already.content
    assert body(unknown) == {"data": {"resendVerificationEmail": {"accepted": True}}}

    # Only the genuinely unverified account produced an email.
    assert len(sender.verify_tokens) == 1
    assert CredentialToken.objects.count() == 1


def test_already_verified_and_unknown_addresses_mint_nothing(client, sender):
    _make_user("done@resend.example", verified=True, tag="noop-v")

    resend(client, "done@resend.example")
    resend(client, "nobody@resend.example")

    assert sender.verify_tokens == []
    assert CredentialToken.objects.count() == 0


def test_a_disabled_account_gets_no_new_link(client, sender):
    """A seat that was revoked before it ever verified must not be handed a fresh way in —
    and the caller still cannot tell the difference."""
    _make_user("disabled@resend.example", status=CustomerUserStatus.DISABLED, tag="dis")

    response = resend(client, "disabled@resend.example")

    assert body(response) == {"data": {"resendVerificationEmail": {"accepted": True}}}
    assert sender.verify_tokens == []
    assert CredentialToken.objects.count() == 0


# --- AC3: no timing oracle --------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_response_timing_does_not_distinguish_the_three_cases(client, settings):
    """THE timing probe. `make_password` costs ~120ms and email dispatch costs a broker
    round trip; without deliberate equalisation the unverified case is an order of
    magnitude slower than the unknown one, and the identical body in the test above buys
    nothing at all.

    Each sample uses a FRESH address so the per-address rate limit never interferes, and
    the three cases are interleaved so warm-up or GC drift cannot land on one case.

    `transaction=True` is LOAD-BEARING, not incidental. Every other test here runs inside
    django_db's outer atomic, where the real COMMIT never happens and `transaction.on_commit`
    dispatch is deferred to `captureOnCommitCallbacks` — i.e. it would be measured AFTER the
    service (and its padding) had already returned, which is not what production does. With
    real transactions the callback fires where it really fires: at the atomic exit inside the
    service, INSIDE the padded window. Without this the probe measures a pytest artifact and
    reports a ~60ms leak that the deployed code does not have.
    """
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0.25  # the production default
    # The probe needs `samples * 3` calls from one IP, which the real per-IP and global
    # budgets (10/hr and 500/hr) would refuse partway through — a rate-limited call is fast
    # and would be measured as if it were a fast branch. Lift the two budgets that are not
    # this test's subject; the per-address budget is untouched because each sample uses a
    # fresh address anyway.
    settings.SELAHCUE_THROTTLE_RESEND_IP = (1000, 3600)
    settings.SELAHCUE_THROTTLE_RESEND_GLOBAL = (1000, 3600)
    # 60ms represents a slow but entirely plausible dispatch — a remote broker, or the
    # inline SMTP send that CELERY_TASK_ALWAYS_EAGER performs in dev. It is chosen to be
    # comfortably ABOVE the assertion threshold below, so that removing the constant-time
    # floor makes this test fail rather than merely wobble: the dummy-hash equaliser alone
    # cannot absorb a dispatch cost, and this probe has to be able to see that.
    slow = CapturingSender(dispatch_delay=0.06)
    services.set_email_sender(slow)
    try:
        samples = 5
        for i in range(samples):
            _make_user(f"u{i}@timing.example", tag=f"t-u{i}")
            _make_user(f"v{i}@timing.example", verified=True, tag=f"t-v{i}")

        timings = {"unknown": [], "unverified": [], "verified": []}
        addresses = {
            "unknown": lambda i: f"ghost{i}@timing.example",
            "unverified": lambda i: f"u{i}@timing.example",
            "verified": lambda i: f"v{i}@timing.example",
        }
        # A plain post, NOT `post_account`: under `transaction=True` the on_commit callback
        # already fired inside the service, and wrapping the call in captureOnCommitCallbacks
        # would put an empty-list bookkeeping pass inside the measured window for no reason.
        def timed_resend(email):
            started = time.perf_counter()
            client.post(
                "/graphql/account",
                data=json.dumps({"query": RESEND, "variables": {"e": email}}),
                content_type="application/json",
            )
            return time.perf_counter() - started

        for i in range(samples):
            for case, address in addresses.items():
                timings[case].append(timed_resend(address(i)))

        medians = {case: statistics.median(values) for case, values in timings.items()}
        spread = max(medians.values()) - min(medians.values())
        assert spread < 0.030, (
            f"response time distinguishes the three cases (spread {spread * 1000:.1f}ms): "
            f"{ {c: round(v * 1000, 1) for c, v in medians.items()} }"
        )
        # Guards the equalisation from being satisfied by doing no real work at all.
        assert min(medians.values()) >= 0.25
        assert len(slow.verify_tokens) == samples
    finally:
        services.set_email_sender(services.EmailSender())


# --- AC4: the previous token dies -------------------------------------------------------
def test_issuing_a_new_token_invalidates_the_previous_one(client, sender):
    _make_user("rotate@resend.example", tag="rot")

    resend(client, "rotate@resend.example")
    first_token = sender.verify_tokens[-1]
    resend(client, "rotate@resend.example")
    second_token = sender.verify_tokens[-1]

    assert first_token != second_token
    # The old link no longer verifies...
    assert error_code(post_account(client, VERIFY, {"t": first_token})) == "VALIDATION_FAILED"
    # ...and the new one does.
    assert body(post_account(client, VERIFY, {"t": second_token}))["data"]["verifyEmail"]["verified"] is True


def test_the_raw_token_is_never_stored_in_plaintext(client, sender):
    _make_user("hash@resend.example", tag="hash")
    resend(client, "hash@resend.example")
    raw = sender.verify_tokens[-1]

    token = CredentialToken.objects.get(purpose=CredentialTokenPurpose.EMAIL_VERIFY)
    assert raw not in token.token_hash
    assert raw != token.token_fingerprint
    assert raw != token.masked_token


# --- AC5: rate limiting -----------------------------------------------------------------
def test_per_address_limit_caps_repeated_resends(client, sender, settings):
    settings.SELAHCUE_THROTTLE_RESEND_ADDRESS = (2, 900)
    _make_user("flood@resend.example", tag="flood")

    first = resend(client, "flood@resend.example")
    second = resend(client, "flood@resend.example")
    third = resend(client, "flood@resend.example")

    assert body(first)["data"]["resendVerificationEmail"]["accepted"] is True
    assert body(second)["data"]["resendVerificationEmail"]["accepted"] is True
    assert error_code(third) == "RATE_LIMITED"
    # The refused request sent nothing — the whole point is not flooding the mailbox.
    assert len(sender.verify_tokens) == 2


def test_the_rate_limited_response_does_not_leak_existence(client, sender, settings):
    """A limit that only bites for REAL accounts would be a perfect oracle: the limiter has
    to key on the address itself, spent identically whether or not an account exists."""
    settings.SELAHCUE_THROTTLE_RESEND_ADDRESS = (1, 900)
    _make_user("known@resend.example", tag="leak")

    resend(client, "known@resend.example")
    resend(client, "ghost@resend.example")
    known_limited = resend(client, "known@resend.example")
    ghost_limited = resend(client, "ghost@resend.example")

    assert error_code(known_limited) == "RATE_LIMITED"
    assert error_code(ghost_limited) == "RATE_LIMITED"
    assert known_limited.status_code == ghost_limited.status_code
    assert known_limited.content == ghost_limited.content


def test_a_global_cap_bounds_total_volume(client, sender, settings):
    """Per-address limits alone let an attacker spray thousands of DISTINCT addresses; the
    cost vector is the total send volume, so that needs its own ceiling."""
    settings.SELAHCUE_THROTTLE_RESEND_GLOBAL = (2, 3600)

    assert body(resend(client, "a@resend.example"))["data"]["resendVerificationEmail"]["accepted"] is True
    assert body(resend(client, "b@resend.example"))["data"]["resendVerificationEmail"]["accepted"] is True
    assert error_code(resend(client, "c@resend.example")) == "RATE_LIMITED"


def test_a_single_ip_cannot_spray_distinct_addresses(client, sender, settings):
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    settings.SELAHCUE_THROTTLE_RESEND_IP = (2, 3600)

    assert error_code(resend(client, "one@resend.example")) is None
    assert error_code(resend(client, "two@resend.example")) is None
    assert error_code(resend(client, "three@resend.example")) == "RATE_LIMITED"


# --- AC7: audit -------------------------------------------------------------------------
def test_the_resend_is_audited_without_the_token(client, sender):
    user = _make_user("audited@resend.example", tag="aud")

    resend(client, "audited@resend.example")
    raw = sender.verify_tokens[-1]

    events = AuditEvent.objects.filter(action="customer_user.verification_resent")
    assert events.count() == 1
    assert events.get().target_id == str(user.id)

    dumped = json.dumps(
        [
            {"action": e.action, "after": e.after, "before": e.before, "request_id": e.request_id}
            for e in AuditEvent.objects.all()
        ],
        default=str,
    )
    assert raw not in dumped
    assert "audited@resend.example" not in dumped


def test_no_audit_event_for_unknown_or_verified_addresses(client, sender):
    _make_user("quiet@resend.example", verified=True, tag="quiet")

    resend(client, "quiet@resend.example")
    resend(client, "missing@resend.example")

    assert AuditEvent.objects.filter(action="customer_user.verification_resent").count() == 0


# --- input validation -------------------------------------------------------------------
def test_a_malformed_address_is_validation_failed(client, sender):
    """Syntactic validity is caller-knowable, so refusing it leaks nothing — and it keeps
    junk from consuming the global send budget."""
    assert error_code(resend(client, "not-an-email")) == "VALIDATION_FAILED"
    assert error_code(resend(client, "")) == "VALIDATION_FAILED"
    assert sender.verify_tokens == []


def test_address_matching_is_case_and_whitespace_insensitive(client, sender):
    _make_user("mixed@resend.example", tag="case")

    resend(client, "  MiXeD@Resend.Example  ")

    assert len(sender.verify_tokens) == 1
