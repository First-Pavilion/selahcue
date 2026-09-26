"""Per-client-IP throttle on `requestPasswordReset` / `confirmPasswordReset` (86akcmfd4).

DEC-013's required follow-up. `DECISION-LOG.md` records that removing PBKDF2 from the
credential-token mint shrank the branch-timing gap that lets a caller infer whether an email
or token is live, but shrank the concealing noise FASTER — "roughly a 2x reduction in remote
attack cost" — and that the trade was accepted CONDITIONAL on a throttle landing to bound how
many times that gap can be sampled: "Until it lands, the oracle repeats indefinitely and
alerts no one." Before this file, both mutations were reachable at an unlimited rate.

THE PROPERTY THIS FILE PINS is NOT "the timing gap is closed" — it explicitly is not; see the
comments in `apps/accounts/services.py` on `request_password_reset`'s unminted branch — it is
"a single source cannot sample either mutation an unbounded number of times."

THE TEST THAT MATTERS MOST is `test_spoofed_forwarded_for_does_not_mint_a_fresh_budget_for_*`.
Without it, a caller-controlled `X-Forwarded-For` value would buy a fresh budget per request
and the limiter would bound nothing. `client_ip()` itself is exhaustively covered in
test_throttling.py; what these two tests pin is that THIS integration (the GraphQL resolver in
`account_schema.py`) actually calls it, rather than reading the header directly. Mutation-
verified: replacing that call with a raw `request.META["HTTP_X_FORWARDED_FOR"]` read turns both
red (see the accompanying handoff evidence — the mutation is not left in this file).

A companion risk `test_spoofed_forwarded_for_...` cannot catch on its own: a limiter that never
varies its key at all (e.g. the caller IP was silently never threaded through) would ALSO make
that test pass, for the wrong reason — every caller would share one bucket, so a spoofed header
trivially "fails" to mint a fresh one. `test_separate_callers_have_separate_budgets_for_*` is the
positive control that rules this out: two distinct real source IPs MUST each get their own
budget.

THE F4 GAP (Sana, security review round 1): every test above uses a NON-EXISTENT email or
token, so none of them ever enters `request_password_reset`'s MINT branch — they cannot see
`enforce_budget` move to the wrong side of the `transaction.atomic()` block it currently
guards. If it moved below, still unconditional, every assertion above would still pass, and a
21st request against a REAL account would mint a token, commit, dispatch the reset email, and
ONLY THEN be told RATE_LIMITED — the throttled response's own timing becomes a new oracle, and
a caller believed to be refused would still receive working mail.
`test_a_throttled_request_against_a_real_account_mints_nothing_and_sends_nothing` is the test
that closes this: it exhausts the budget against an EXISTING, VERIFIED account and asserts the
throttled call left NO new `CredentialToken` row and sent NO new email. Mutation-verified the
same way as the header test above (see the handoff evidence).
"""

import json
import logging

import pytest
from django.core.cache import cache
from django.test import TestCase

from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import CredentialToken, CredentialTokenPurpose, CustomerUser
from selahcue_api.apps.throttling import guards


def post_account(client, query, variables=None, **extra):
    # Mirrors tests/test_customer_auth_slice.py's helper: email dispatch is registered with
    # `transaction.on_commit`, which `django_db`'s rollback never runs unless captured.
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
    errors = body(response).get("errors") or []
    if not errors:
        return None
    return (errors[0].get("extensions") or {}).get("code")


REQUEST_RESET = "mutation Req($e: String!) { requestPasswordReset(email: $e) { accepted } }"
CONFIRM_RESET = """
    mutation Confirm($input: ConfirmPasswordResetInput!) {
      confirmPasswordReset(input: $input) { reset }
    }
"""


class _BrokenStore:
    """A limiter store standing in for a Redis outage — every call raises, exactly like
    `apps.throttling.services.evaluate_budget`'s own `except Exception` branch expects."""

    def incr_with_expiry(self, key, window_seconds):
        raise RuntimeError("redis is down")


@pytest.fixture(autouse=True)
def _fresh_cache(settings):
    """Isolate every test's budget from its neighbours and from the module-level throttle
    logs' own suppression window, and pin `SELAHCUE_TRUSTED_PROXY_COUNT` to the documented
    "trust REMOTE_ADDR only" default so a stray override elsewhere cannot leak in."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    cache.clear()
    services._reset_floor_overrun_reporting()


class _CapturingSender(services.EmailSender):
    """Module-local capture of dispatched mail, matching the shape of
    tests/test_customer_auth_slice.py's `CapturingSender` (module-local by convention — see
    conftest.py: shared seeding helpers are deliberately not shared across test files). Only
    the two methods this file needs are overridden."""

    def __init__(self):
        self.verify_tokens = []
        self.reset_tokens = []

    def send_email_verification(self, user, raw_token):
        self.verify_tokens.append(raw_token)

    def send_password_reset(self, user, raw_token):
        self.reset_tokens.append(raw_token)


def _existing_verified_account(sender, *, email="verified@budget.example", idem="throttle-verified-0001"):
    """A REAL, ACTIVE, email-verified CustomerUser, built through the actual signup + verify
    SERVICE calls (not hand-built ORM rows) so it carries the exact same `email_fingerprint`
    the code under test computes — a hand-rolled fixture that drifted from `_email_fingerprint`
    would make the "mint branch" case below silently degenerate into the "no such user" case.
    """
    with TestCase.captureOnCommitCallbacks(execute=True):
        services.register_customer_user(
            services.RegisterCustomerUserData(
                idempotency_key=idem,
                email=email,
                password="correct-horse-battery-1",
                org_name="Budget Chapel",
                country="NG",
            )
        )
    services.verify_email(sender.verify_tokens[-1])
    return email


# --- the positive control: refused at N, and a benign caller still gets through -----------
@pytest.mark.django_db
def test_request_reset_nth_call_is_refused_and_earlier_calls_are_not(client, settings):
    """Asserts the WHOLE sequence, not just the last response — inspecting only call 3 would
    equally pass for a limiter that refuses everything or one that trips on the wrong call."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST = (2, 3600)
    first = post_account(client, REQUEST_RESET, {"e": "one@budget.example"})
    second = post_account(client, REQUEST_RESET, {"e": "two@budget.example"})
    third = post_account(client, REQUEST_RESET, {"e": "three@budget.example"})

    # Calls 1-2 are WITHIN budget: they reach the service and return the uniform accepted:true
    # (no-enumeration is unchanged by this ticket) — proof they were not refused by the limiter.
    assert error_code(first) is None and body(first)["data"]["requestPasswordReset"]["accepted"] is True
    assert error_code(second) is None and body(second)["data"]["requestPasswordReset"]["accepted"] is True
    # Call 3 is the FIRST refused — not earlier.
    assert error_code(third) == "RATE_LIMITED", (
        f"expected the 3rd call over a (2, 3600) budget to be refused, got {error_code(third)!r}"
    )


@pytest.mark.django_db
def test_confirm_reset_nth_call_is_refused_and_earlier_calls_are_not(client, settings):
    """Mixes THREE distinct invalid-token shapes across the pre-limit calls — proof the budget
    is spent by request COUNT, not by which token was offered (constraint: RATE_LIMITED must
    not correlate with token validity, see the module docstring and the handoff notes)."""
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM = (3, 3600)
    empty = post_account(client, CONFIRM_RESET, {"input": {"token": "", "newPassword": "irrelevant-pw-1"}})
    unknown = post_account(
        client, CONFIRM_RESET, {"input": {"token": "SC-PRS-nobody-minted-this", "newPassword": "irrelevant-pw-1"}}
    )
    malformed = post_account(
        client, CONFIRM_RESET, {"input": {"token": "not-a-token-shape", "newPassword": "irrelevant-pw-1"}}
    )
    fourth = post_account(
        client, CONFIRM_RESET, {"input": {"token": "SC-PRS-yet-another-guess", "newPassword": "irrelevant-pw-1"}}
    )

    # Calls 1-3 are WITHIN budget: each reaches the service and gets the SAME collapsed
    # VALIDATION_FAILED every invalid token gets today (FR-529 / CON-P6, unchanged) — proof
    # they were refused by TOKEN validity, not by the limiter.
    assert error_code(empty) == "VALIDATION_FAILED"
    assert error_code(unknown) == "VALIDATION_FAILED"
    assert error_code(malformed) == "VALIDATION_FAILED"
    # Call 4 is the FIRST one the limiter refuses, regardless of what token it carried.
    assert error_code(fourth) == "RATE_LIMITED", (
        f"expected the 4th call over a (3, 3600) budget to be refused, got {error_code(fourth)!r}"
    )


# --- the test that matters most: a spoofed X-Forwarded-For mints nothing ------------------
@pytest.mark.django_db
def test_spoofed_forwarded_for_does_not_mint_a_fresh_budget_for_request_reset(client, settings):
    """`SELAHCUE_TRUSTED_PROXY_COUNT = 0` (set by the autouse fixture): X-Forwarded-For must be
    ignored entirely, so two calls from the SAME real address with DIFFERENT forged headers must
    share ONE budget. Without this, a header is a limiter bypass."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST = (1, 3600)
    first = post_account(
        client,
        REQUEST_RESET,
        {"e": "victim-a@budget.example"},
        REMOTE_ADDR="203.0.113.9",
        HTTP_X_FORWARDED_FOR="1.2.3.4",
    )
    spoofed = post_account(
        client,
        REQUEST_RESET,
        {"e": "victim-b@budget.example"},
        REMOTE_ADDR="203.0.113.9",
        HTTP_X_FORWARDED_FOR="9.9.9.9",  # a DIFFERENT forged header, same real source
    )

    assert error_code(first) is None, "the first call (within budget) must not itself be refused"
    assert error_code(spoofed) == "RATE_LIMITED", (
        "a forged X-Forwarded-For minted a FRESH budget — the limiter is bypassable with one header"
    )


@pytest.mark.django_db
def test_spoofed_forwarded_for_does_not_mint_a_fresh_budget_for_confirm_reset(client, settings):
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM = (1, 3600)
    first = post_account(
        client,
        CONFIRM_RESET,
        {"input": {"token": "SC-PRS-guess-one", "newPassword": "irrelevant-pw-1"}},
        REMOTE_ADDR="203.0.113.10",
        HTTP_X_FORWARDED_FOR="1.2.3.4",
    )
    spoofed = post_account(
        client,
        CONFIRM_RESET,
        {"input": {"token": "SC-PRS-guess-two", "newPassword": "irrelevant-pw-1"}},
        REMOTE_ADDR="203.0.113.10",
        HTTP_X_FORWARDED_FOR="9.9.9.9",
    )

    assert error_code(first) == "VALIDATION_FAILED", "the first call (within budget) must reach the service"
    assert error_code(spoofed) == "RATE_LIMITED", (
        "a forged X-Forwarded-For minted a FRESH budget — the limiter is bypassable with one header"
    )


# --- the companion positive control: two REAL sources never share a budget ----------------
@pytest.mark.django_db
def test_separate_callers_have_separate_budgets_for_request_reset(client, settings):
    """Rules out the OTHER way the spoofed-header test above could pass for the wrong reason:
    a limiter keyed on something constant (client IP never threaded through at all) would also
    make a spoofed header "fail" to mint a fresh budget, because NOTHING would. Two DISTINCT
    real source addresses must each get their own."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST = (1, 3600)

    def call(remote_addr):
        return error_code(
            post_account(client, REQUEST_RESET, {"e": "someone@budget.example"}, REMOTE_ADDR=remote_addr)
        )

    assert call("203.0.113.1") is None
    assert call("203.0.113.1") == "RATE_LIMITED", "the SAME address must exhaust its own budget"
    assert call("203.0.113.2") is None, "a DIFFERENT address must have its own, unspent budget"
    assert call("203.0.113.2") == "RATE_LIMITED"


@pytest.mark.django_db
def test_separate_callers_have_separate_budgets_for_confirm_reset(client, settings):
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM = (1, 3600)

    def call(remote_addr):
        return error_code(
            post_account(
                client,
                CONFIRM_RESET,
                {"input": {"token": "SC-PRS-does-not-exist", "newPassword": "irrelevant-pw-1"}},
                REMOTE_ADDR=remote_addr,
            )
        )

    assert call("198.51.100.1") == "VALIDATION_FAILED"
    assert call("198.51.100.1") == "RATE_LIMITED", "the SAME address must exhaust its own budget"
    assert call("198.51.100.2") == "VALIDATION_FAILED", "a DIFFERENT address must have its own, unspent budget"
    assert call("198.51.100.2") == "RATE_LIMITED"


# --- fail open on a store outage -----------------------------------------------------------
@pytest.mark.django_db
def test_store_unavailable_fails_open_for_request_reset(client, settings, monkeypatch):
    """A Redis outage must not lock everyone out of password reset — `evaluate_budget`'s
    STORE_UNAVAILABLE outcome is a permit, and `enforce_budget` (built on it, not on
    `should_allow`) must pass that through rather than refusing."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST = (1, 3600)
    monkeypatch.setattr(guards, "CacheStore", lambda _cache: _BrokenStore())
    # Well over the (1, 3600) budget — every one of these would 429 on a healthy store.
    for _ in range(3):
        resp = post_account(client, REQUEST_RESET, {"e": "outage@budget.example"})
        assert error_code(resp) is None, "the limiter store being down must not deny the request"
        assert body(resp)["data"]["requestPasswordReset"]["accepted"] is True


@pytest.mark.django_db
def test_store_unavailable_fails_open_for_confirm_reset(client, settings, monkeypatch):
    settings.SELAHCUE_THROTTLE_RESET_CONFIRM = (1, 3600)
    monkeypatch.setattr(guards, "CacheStore", lambda _cache: _BrokenStore())
    for _ in range(3):
        resp = post_account(
            client, CONFIRM_RESET, {"input": {"token": "SC-PRS-does-not-exist", "newPassword": "irrelevant-pw-1"}}
        )
        # The call must reach the service (VALIDATION_FAILED for the bogus token), never
        # RATE_LIMITED, while the store is down.
        assert error_code(resp) == "VALIDATION_FAILED", (
            f"the limiter store being down must not deny the request, got {error_code(resp)!r}"
        )


# --- F4 (Sana, security review round 1): the throttled call must precede the mint ---------
@pytest.mark.django_db
def test_a_throttled_request_against_a_real_account_mints_nothing_and_sends_nothing(client, settings):
    """Every OTHER test in this file uses a NON-EXISTENT email or token, so none of them can
    see `enforce_budget` land on the wrong side of `request_password_reset`'s
    `transaction.atomic()` block: the mint branch never runs for them regardless of where the
    guard sits. This test uses a REAL, VERIFIED account so the mint branch DOES run, and pins
    that the THROTTLED call — not just the earlier ones — never reaches it.
    """
    settings.SELAHCUE_THROTTLE_RESET_REQUEST = (1, 3600)
    sender = _CapturingSender()
    services.set_email_sender(sender)
    try:
        email = _existing_verified_account(sender)
        user = CustomerUser.objects.get(email=email)

        first = post_account(client, REQUEST_RESET, {"e": email})
        assert error_code(first) is None, "the first call (within budget) must not itself be refused"

        # POSITIVE CONTROL, asserted BEFORE the throttled call: prove the WITHIN-budget call
        # really did reach the mint branch. Without this, a "no new token" result below could
        # equally mean the mint branch never runs at all, which would prove nothing about the
        # throttle's placement.
        minted_count = CredentialToken.objects.filter(
            customer_user=user, purpose=CredentialTokenPurpose.PASSWORD_RESET
        ).count()
        assert minted_count == 1, (
            "the within-budget call did not mint a token — this fixture is not exercising the "
            "mint branch, and the contract below would pass for the wrong reason"
        )
        assert len(sender.reset_tokens) == 1, (
            "the within-budget call did not send a reset email — this fixture is not "
            "exercising the mint branch, and the contract below would pass for the wrong reason"
        )

        second = post_account(client, REQUEST_RESET, {"e": email})
        assert error_code(second) == "RATE_LIMITED"

        # THE CONTRACT. If `enforce_budget` ran AFTER the atomic block instead of before it,
        # this call would still be refused (the guard is unconditional either way) — but only
        # after minting a SECOND token, committing it, and dispatching a SECOND email. The
        # caller would see 429 while their mailbox received a working reset link, and the
        # 429's own timing (mint-then-refuse vs refuse-outright) would become a fresh oracle.
        assert (
            CredentialToken.objects.filter(
                customer_user=user, purpose=CredentialTokenPurpose.PASSWORD_RESET
            ).count()
            == minted_count
        ), "the THROTTLED request minted a new token — enforce_budget is running after the mint"
        assert len(sender.reset_tokens) == 1, (
            "the THROTTLED request sent a SECOND reset email — enforce_budget is running after "
            "the dispatch"
        )
    finally:
        services.set_email_sender(services.EmailSender())


# --- F4, reopened for the two NEW budgets (Sana, PR #107 review round 1, S-2) -------------
# The test above only tightens `SELAHCUE_THROTTLE_RESET_REQUEST` (the pre-existing per-IP
# budget), so it can see `enforce_budget` land on the wrong side of the mint for THAT budget
# only. 86akcn8p4 added two more `enforce_budget` calls (address, global) in the same function
# — each is its own opportunity for the guard to end up below the mint, and the test above
# cannot see either. These two mirror it exactly, tightening the ADDRESS and GLOBAL budgets
# respectively instead.
@pytest.mark.django_db
def test_a_throttled_request_against_a_real_account_via_the_address_budget_mints_nothing(
    client, settings
):
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (1, 900)
    sender = _CapturingSender()
    services.set_email_sender(sender)
    try:
        email = _existing_verified_account(sender, email="f4-addr@budget.example", idem="f4-addr-throttle-001")
        user = CustomerUser.objects.get(email=email)

        first = post_account(client, REQUEST_RESET, {"e": email})
        assert error_code(first) is None

        minted_count = CredentialToken.objects.filter(
            customer_user=user, purpose=CredentialTokenPurpose.PASSWORD_RESET
        ).count()
        assert minted_count == 1, "the within-budget call did not mint — fixture is not exercising the mint branch"
        assert len(sender.reset_tokens) == 1

        second = post_account(client, REQUEST_RESET, {"e": email})
        assert error_code(second) == "RATE_LIMITED"

        assert (
            CredentialToken.objects.filter(
                customer_user=user, purpose=CredentialTokenPurpose.PASSWORD_RESET
            ).count()
            == minted_count
        ), "the THROTTLED request minted a new token via the ADDRESS budget — enforce_budget runs after the mint"
        assert len(sender.reset_tokens) == 1, "the THROTTLED request sent a SECOND email via the ADDRESS budget"
    finally:
        services.set_email_sender(services.EmailSender())


@pytest.mark.django_db
def test_a_throttled_request_against_a_real_account_via_the_global_budget_mints_nothing(
    client, settings
):
    """A DIFFERENT address each call, so only the GLOBAL budget (checked first, before IP or
    address) can be what trips — proving the global spend also precedes the mint."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL = (1, 3600)
    sender = _CapturingSender()
    services.set_email_sender(sender)
    try:
        email = _existing_verified_account(sender, email="f4-global@budget.example", idem="f4-global-throttle-001")
        user = CustomerUser.objects.get(email=email)

        first = post_account(client, REQUEST_RESET, {"e": email})
        assert error_code(first) is None

        minted_count = CredentialToken.objects.filter(
            customer_user=user, purpose=CredentialTokenPurpose.PASSWORD_RESET
        ).count()
        assert minted_count == 1, "the within-budget call did not mint — fixture is not exercising the mint branch"
        assert len(sender.reset_tokens) == 1

        # A DIFFERENT address, so only the exhausted GLOBAL budget can refuse this call.
        second = post_account(client, REQUEST_RESET, {"e": "f4-global-other@budget.example"})
        assert error_code(second) == "RATE_LIMITED"

        assert (
            CredentialToken.objects.filter(
                customer_user=user, purpose=CredentialTokenPurpose.PASSWORD_RESET
            ).count()
            == minted_count
        ), "the THROTTLED request minted a token for the real account — enforce_budget runs after the mint"
        assert len(sender.reset_tokens) == 1, "the THROTTLED request sent a SECOND email via the GLOBAL budget"
    finally:
        services.set_email_sender(services.EmailSender())


# --- 86akcn8p4: request_password_reset gets a per-address AND a global budget ------------
# Sana's follow-up finding: 86akcmfd4 gave `request_password_reset` a per-IP budget only, which
# bounds DEC-013's timing-oracle sampling but does nothing about MAIL VOLUME against one victim
# — a distributed attacker sprays distinct source IPs, so `request_password_reset` was the only
# unauthenticated mail-sender in the API with neither a per-address cap nor a global one. These
# tests mirror `test_resend_verification.py`'s own coverage of that exact shape.
@pytest.mark.django_db
def test_request_reset_address_budget_refuses_the_nth_request_and_a_different_address_still_passes(
    client, settings
):
    """THE positive control the ticket calls for by name: refused for the (N+1)th request
    against ONE address, while a DIFFERENT address still passes — without the second half, a
    limiter that refuses everyone regardless of address would equally make the first half pass."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (2, 900)

    first = post_account(client, REQUEST_RESET, {"e": "flood-victim@budget.example"})
    second = post_account(client, REQUEST_RESET, {"e": "flood-victim@budget.example"})
    third = post_account(client, REQUEST_RESET, {"e": "flood-victim@budget.example"})

    assert error_code(first) is None and body(first)["data"]["requestPasswordReset"]["accepted"] is True
    assert error_code(second) is None and body(second)["data"]["requestPasswordReset"]["accepted"] is True
    assert error_code(third) == "RATE_LIMITED", (
        f"expected the 3rd call against ONE address over a (2, 900) budget to be refused, "
        f"got {error_code(third)!r}"
    )

    # A DIFFERENT address must still have its own, unspent budget.
    other = post_account(client, REQUEST_RESET, {"e": "someone-else@budget.example"})
    assert error_code(other) is None, "a different address must not share the exhausted budget"


@pytest.mark.django_db
def test_request_reset_address_budget_refusal_does_not_leak_existence(client, settings):
    """A limit that only bit for REAL accounts would be a perfect oracle: the address budget
    must be spent — and must refuse — identically whether or not the address has an account."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (1, 900)
    sender = _CapturingSender()
    services.set_email_sender(sender)
    try:
        email = _existing_verified_account(sender, email="known-addr-budget@budget.example")

        post_account(client, REQUEST_RESET, {"e": email})
        post_account(client, REQUEST_RESET, {"e": "ghost-addr-budget@budget.example"})
        known_limited = post_account(client, REQUEST_RESET, {"e": email})
        ghost_limited = post_account(client, REQUEST_RESET, {"e": "ghost-addr-budget@budget.example"})

        assert error_code(known_limited) == "RATE_LIMITED"
        assert error_code(ghost_limited) == "RATE_LIMITED"
        assert known_limited.status_code == ghost_limited.status_code
        assert known_limited.content == ghost_limited.content
    finally:
        services.set_email_sender(services.EmailSender())


@pytest.mark.django_db
def test_request_reset_global_budget_refuses_once_exhausted_regardless_of_address_or_ip(
    client, settings
):
    """Per-address limits alone let an attacker spray thousands of DISTINCT addresses; the
    global ceiling is what actually bounds total send cost, same role as
    SELAHCUE_THROTTLE_RESEND_GLOBAL."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL = (2, 3600)

    first = post_account(client, REQUEST_RESET, {"e": "global-a@budget.example"})
    second = post_account(client, REQUEST_RESET, {"e": "global-b@budget.example"})
    third = post_account(client, REQUEST_RESET, {"e": "global-c@budget.example"})

    assert error_code(first) is None
    assert error_code(second) is None
    assert error_code(third) == "RATE_LIMITED", (
        "a THIRD distinct address must still be refused once the shared global budget is spent"
    )


@pytest.mark.django_db
def test_request_reset_address_budget_is_keyed_on_fingerprint_not_raw_email(client, settings):
    """Guards the cache-key-cardinality property the ticket calls out explicitly: the SAME
    address, differently CASED, must share one budget (an attacker minting one Redis key per
    case variation would defeat the point of a per-address cap)."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (1, 900)

    first = post_account(client, REQUEST_RESET, {"e": "MixedCase@Budget.Example"})
    second = post_account(client, REQUEST_RESET, {"e": "mixedcase@budget.example"})

    assert error_code(first) is None
    assert error_code(second) == "RATE_LIMITED", (
        "differently-cased spellings of the same address must share one budget"
    )


@pytest.mark.django_db
def test_request_reset_address_budget_cache_key_is_the_hmac_fingerprint_not_the_raw_email(
    client, settings
):
    """S-1 (Sana, PR #107 review round 1): the test above proves case-insensitivity, which
    would ALSO pass if the key were the raw NORMALISED email (`.strip().lower()`) rather than
    its HMAC fingerprint — normalising before keying makes both spellings collapse either way.
    This asserts the actual Redis/cache key directly, so "keyed on fingerprint" is checked
    rather than inferred from a behaviour that has two possible causes.
    """
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (5, 900)
    email = "fingerprint-check@budget.example"

    resp = post_account(client, REQUEST_RESET, {"e": email})
    assert error_code(resp) is None

    fingerprint = services._email_fingerprint(email)
    fingerprint_key = f"throttle:password_reset_request_addr:{fingerprint}"
    raw_email_key = f"throttle:password_reset_request_addr:{email}"

    assert cache.get(fingerprint_key) == 1, (
        "expected the address budget's cache key to be keyed on the HMAC fingerprint; it was "
        "not found where `_email_fingerprint(email)` says it should be"
    )
    assert cache.get(raw_email_key) is None, (
        "the address budget minted a cache key from the RAW email — an unauthenticated "
        "endpoint keying Redis entries on attacker-chosen text is the unbounded-key-growth "
        "problem this ticket's own scope note calls out"
    )


# --- 86akcn92k (F1): the reset SEND degrades under its own outage ceiling ------------------
# All three budgets above fail OPEN when the limiter store is down (by design — see the
# module comment in services.py). Without a stand-in, an outage would revert
# `request_password_reset` to unmetered mail and unbounded oracle sampling: exactly the
# pre-86akcmfd4 state, reachable by anyone who detects or induces store unavailability. The
# reset send now degrades under `_claim_degraded_reset_send` — its OWN ceiling, never shared
# with resend-verification's.
@pytest.fixture
def reset_limiter_down(monkeypatch):
    monkeypatch.setattr(guards, "CacheStore", lambda _cache: _BrokenStore())
    services._reset_floor_overrun_reporting()
    services._reset_reset_send_degraded_window()


@pytest.mark.django_db
def test_a_limiter_outage_bounds_the_reset_send_without_denying_the_response(
    client, settings, caplog, reset_limiter_down
):
    """THE positive control for F1: many requests during an outage must still all report
    accepted:true (no enumeration oracle from an outage-shaped error) while only the
    ceiling's worth of mail actually leaves."""
    import logging

    settings.SELAHCUE_RESET_SEND_DEGRADED_CEILING = (2, 60)
    sender = _CapturingSender()
    services.set_email_sender(sender)
    try:
        for i in range(5):
            _existing_verified_account(sender, email=f"outage-reset{i}@budget.example", idem=f"outage-reset-{i}")
        sender.reset_tokens.clear()  # the accounts' own setup already sent verify mail, not reset mail

        with caplog.at_level(logging.WARNING, logger=services.logger.name):
            responses = [
                post_account(client, REQUEST_RESET, {"e": f"outage-reset{i}@budget.example"})
                for i in range(5)
            ]

        assert all(error_code(r) is None for r in responses), "an outage must not deny the response"
        assert all(
            body(r)["data"]["requestPasswordReset"]["accepted"] is True for r in responses
        )
        assert len(sender.reset_tokens) == 2, (
            "a limiter outage must bound the reset send, not hand out an unmetered send path"
        )
        skips = [r for r in caplog.records if "limiter unavailable" in r.getMessage()]
        assert len(skips) == 1, "the degradation must be reported, once per interval"
    finally:
        services.set_email_sender(services.EmailSender())


@pytest.mark.django_db
def test_the_reset_degraded_ceiling_is_spent_whether_or_not_the_account_exists(
    client, settings, reset_limiter_down
):
    """The ceiling must not become an existence oracle: an attacker who can watch it drain
    through their own inbox must not be able to tell whether OTHER probed addresses exist by
    watching how fast it empties. Charged on every degraded call, not only sends."""
    settings.SELAHCUE_RESET_SEND_DEGRADED_CEILING = (1, 60)
    sender = _CapturingSender()
    services.set_email_sender(sender)
    try:
        # A call for a NON-EXISTENT address, while the store is down, still spends the shared
        # ceiling — proven by it being empty for the next (REAL) call below.
        first = post_account(client, REQUEST_RESET, {"e": "nonexistent-outage@budget.example"})
        assert error_code(first) is None

        email = _existing_verified_account(sender, email="real-outage@budget.example", idem="real-outage-1")
        sender.reset_tokens.clear()
        second = post_account(client, REQUEST_RESET, {"e": email})

        assert error_code(second) is None, "the response must still be accepted:true"
        assert sender.reset_tokens == [], (
            "the ceiling was exhausted by the FIRST (non-existent-address) call — a real "
            "account's send must be skipped too, or the ceiling leaks account existence"
        )
    finally:
        services.set_email_sender(services.EmailSender())
