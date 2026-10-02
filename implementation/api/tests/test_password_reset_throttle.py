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

THE 86ak65mj5 SECTION AT THE END OF THIS FILE pins the ticket's own acceptance criteria that
the tests above do not reach: the SHIPPED budgets are pinned and never block a person who
mistypes their address (and a legitimate single request sends exactly one email); a throttled
refusal does the same work, returns the same bytes and headers, and takes the same time for a
registered and an unregistered address under EACH of the three budgets (the work is asserted in
COUNTS — zero queries, a fixed cache-call shape — and timing is only a second-line alarm); and
the keys the limiter can create, and how long they live, are bounded by the global budget rather
than by attacker input.
"""

import json
import logging
import statistics
import time
from contextlib import contextmanager

import pytest
from django.core.cache import cache
from django.db import connection
from django.test import TestCase

from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import CredentialToken, CredentialTokenPurpose, CustomerUser
from selahcue_api.apps.throttling import guards
from selahcue_api.apps.throttling.services import CacheStore


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
    """S-5 (Sana, PR #107 re-review): the FIRST version of this test used a different,
    non-existent address for the throttled call, so it never entered the REAL account's mint
    branch regardless of where `enforce_budget` sits — moving the global spend below the mint
    left all assertions green, proving nothing about ordering. Fixed by targeting the SAME real
    address both times, with the IP and address budgets loosened so only the GLOBAL budget
    (checked first) can be what trips the second call — that is what makes this a genuine
    ordering check on the real account's own mint branch, not a duplicate of the address test.
    """
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL = (1, 3600)
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (50, 900)
    settings.SELAHCUE_THROTTLE_RESET_REQUEST = (50, 3600)
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

        # SAME real address again: the address (50, 900) and IP (50, 3600) budgets are both
        # loose enough not to trip on a 2nd call, so only the exhausted GLOBAL (1, 3600)
        # budget can refuse this — and it refuses a call that WOULD otherwise mint again.
        second = post_account(client, REQUEST_RESET, {"e": email})
        assert error_code(second) == "RATE_LIMITED"

        assert (
            CredentialToken.objects.filter(
                customer_user=user, purpose=CredentialTokenPurpose.PASSWORD_RESET
            ).count()
            == minted_count
        ), "the THROTTLED request minted a SECOND token for the real account — enforce_budget runs after the mint"
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


# =============================================================================================
# 86ak65mj5 — the ticket's own acceptance criteria that the sections above do not reach.
#
# The three budgets themselves shipped under 86akcmfd4 / 86akcn8p4 / 86akcn92k, after the ticket
# was written. What nothing proved was (a) the DEFAULT sizing against a real person's mistakes,
# (b) that a throttled refusal is the same for a registered and an unregistered address under
# EACH budget and in TIME, not only in bytes and only for the address budget, and (c) that the
# keys the limiter can create are bounded by the global budget rather than by attacker input.
# =============================================================================================
@pytest.fixture
def capturing_sender():
    captured = _CapturingSender()
    services.set_email_sender(captured)
    yield captured
    services.set_email_sender(services.EmailSender())


def _live_reset_tokens(user):
    return CredentialToken.objects.filter(
        customer_user=user, purpose=CredentialTokenPurpose.PASSWORD_RESET, consumed_at__isnull=True
    ).count()


# --- AC1: the DEFAULT budgets, against what a legitimate person actually does ---------------
@pytest.mark.django_db
def test_one_legitimate_request_sends_exactly_one_email_and_mints_exactly_one_token(
    client, capturing_sender
):
    """The throttle must cost a well-behaved caller NOTHING: one request, one email, one live
    token — under the shipped defaults (nothing is overridden here)."""
    email = _existing_verified_account(capturing_sender, email="single@legit.example", idem="legit-single-0001")
    user = CustomerUser.objects.get(email=email)

    response = post_account(client, REQUEST_RESET, {"e": email})

    assert error_code(response) is None
    assert body(response)["data"]["requestPasswordReset"]["accepted"] is True
    assert len(capturing_sender.reset_tokens) == 1, "a legitimate single request must send exactly one email"
    assert _live_reset_tokens(user) == 1


@pytest.mark.django_db
def test_a_person_who_mistypes_their_address_is_never_blocked_under_the_default_budgets(
    client, capturing_sender
):
    """AC1: 'sized so a legitimate user who mistypes their address twice is never blocked'.
    The shipped defaults are used as they are. The sequence is deliberately the awkward one:
    the SAME typo twice (it looked right the first time), then a DIFFERENT typo, then the right
    address — four calls from one source inside one window."""
    email = _existing_verified_account(capturing_sender, email="real@typo.example", idem="typo-flow-0001")
    user = CustomerUser.objects.get(email=email)
    attempts = [
        "reall@typo.example",
        "reall@typo.example",
        "real@typp.example",
        email,
    ]

    responses = [post_account(client, REQUEST_RESET, {"e": address}) for address in attempts]

    assert [error_code(r) for r in responses] == [None, None, None, None], (
        "the default budgets blocked a person who only mistyped their address"
    )
    assert all(body(r)["data"]["requestPasswordReset"]["accepted"] is True for r in responses)
    assert len(capturing_sender.reset_tokens) == 1, "only the one real address may receive mail"
    assert _live_reset_tokens(user) == 1


@pytest.mark.django_db
def test_retrying_the_same_address_after_a_lost_email_works_three_times_then_stops(
    client, capturing_sender
):
    """The other legitimate pattern: the email did not arrive, so the person asks again. The
    default per-address budget is (3, 900): three requests are served (each really sends and
    supersedes the link before it), the fourth inside the window is refused and sends nothing.
    Pins the shipped trade so changing it is a visible decision rather than a silent one."""
    email = _existing_verified_account(capturing_sender, email="lost@legit.example", idem="legit-lost-0001")
    user = CustomerUser.objects.get(email=email)

    served = [post_account(client, REQUEST_RESET, {"e": email}) for _ in range(3)]
    refused = post_account(client, REQUEST_RESET, {"e": email})

    assert [error_code(r) for r in served] == [None, None, None]
    assert len(capturing_sender.reset_tokens) == 3, "each served retry must really send its own email"
    assert _live_reset_tokens(user) == 1, "a new link must supersede the previous one"
    assert error_code(refused) == "RATE_LIMITED"
    assert len(capturing_sender.reset_tokens) == 3, "the refused fourth request must send nothing"


@pytest.mark.parametrize(
    ("setting_name", "module_default", "shipped"),
    [
        ("SELAHCUE_THROTTLE_RESET_REQUEST", services.RESET_REQUEST_IP_BUDGET, (20, 3600)),
        ("SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS", services.RESET_REQUEST_ADDRESS_BUDGET, (3, 900)),
        ("SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL", services.RESET_REQUEST_GLOBAL_BUDGET, (500, 3600)),
        ("SELAHCUE_RESET_SEND_DEGRADED_CEILING", services.RESET_SEND_DEGRADED_CEILING, (20, 3600)),
    ],
)
def test_the_shipped_reset_budgets_are_pinned_and_their_two_copies_agree(
    settings, setting_name, module_default, shipped
):
    """Two things, each with its own message. (1) `enforce_budget` reads the setting at call time
    and falls back to the module constant only if the setting is missing: two numbers for one
    budget is how a value gets quietly changed in one place while a test pins the other. (2) The
    NUMBER itself is pinned, because every behavioural test above tightens a budget to make it
    trip, so nothing else notices a shipped limit being inflated until it no longer limits
    anything (20 -> 20000 on the IP budget survived every other test in review). Changing a
    shipped budget is a decision: update the literal here in the same change and say why."""
    assert getattr(settings, setting_name) == module_default, (
        f"settings.{setting_name} and the matching services.py default have drifted"
    )
    assert module_default == shipped, (
        f"the shipped {setting_name} is now {module_default}, not {shipped}. If that is deliberate, "
        "update this pin and the reasoning in the PR; if not, a limit was loosened or tightened by accident"
    )


@pytest.mark.django_db
def test_the_default_ip_budget_refuses_the_21st_request_from_one_source(client):
    """AC1's first clause — "repeated calls from one source are throttled" — under the SHIPPED
    defaults rather than a budget tightened to make the test short. Twenty distinct addresses
    from one source are served, the 21st is refused, and a different source is untouched."""
    codes = [
        error_code(
            post_account(client, REQUEST_RESET, {"e": f"source-{n}@default-ip.example"}, REMOTE_ADDR="203.0.113.77")
        )
        for n in range(21)
    ]
    other = post_account(client, REQUEST_RESET, {"e": "elsewhere@default-ip.example"}, REMOTE_ADDR="203.0.113.78")

    assert codes == [None] * 20 + ["RATE_LIMITED"], codes
    assert error_code(other) is None, "a different source must have its own, unspent budget"


# --- AC2: a throttled refusal is the same for a registered and an unregistered address -------
# Each budget gets its own parametrized case, tightened so that budget — and ONLY that budget —
# trips on the second call. A refusal attributed to "some budget" would not show which of the
# three has an existence-dependent step in front of it.
_BUDGET_SETTINGS = {
    "ip": "SELAHCUE_THROTTLE_RESET_REQUEST",
    "address": "SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS",
    "global": "SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL",
}
_TRIPS_AT_ONE = {"ip": (1, 3600), "address": (1, 900), "global": (1, 3600)}
_OUT_OF_REACH = {"ip": (10_000, 3600), "address": (10_000, 900), "global": (10_000, 3600)}
# The budgets a refusal BY each budget has already spent, in order. Global is spent first, then
# the IP, then the address, so a refusal at the IP budget has spent global and IP, and so on.
_SCOPES_SPENT = {
    "global": ("password_reset_request_global",),
    "ip": ("password_reset_request_global", "password_reset_request_ip"),
    "address": (
        "password_reset_request_global",
        "password_reset_request_ip",
        "password_reset_request_addr",
    ),
}


def _only_budget_trips(settings, budget):
    for name, setting_name in _BUDGET_SETTINGS.items():
        setattr(settings, setting_name, _TRIPS_AT_ONE[name] if name == budget else _OUT_OF_REACH[name])


class _QueryCounter:
    """Counts every statement the ORM executes inside `connection.execute_wrapper`.

    Not `CaptureQueriesContext` / `django_assert_num_queries`: those slice `connection.queries_log`,
    which the test client's `request_started` signal CLEARS, so a count taken around a client
    request can read short (the allowed call here read 0 for the address budget). A wrapper sees
    each statement as it runs and is not affected."""

    def __init__(self):
        self.count = 0

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        return execute(sql, params, many, context)


@contextmanager
def _counting_queries():
    counter = _QueryCounter()
    with connection.execute_wrapper(counter):
        yield counter


def _spend_the_allowed_call(client, budget, known, ghost):
    """Use up `budget`'s one allowed call. The REAL account goes first so that call is the one
    that mints — the branch a mis-placed or existence-keyed throttle would treat differently.
    The address budget is per address, so the unknown address must spend its own allowance too;
    the IP and global budgets are shared, so the first call already spent them.

    Returns how many database queries the real account's allowed call made, so a caller that
    asserts a REFUSAL makes none can prove its own query counter is alive."""
    with _counting_queries() as queries:
        first = post_account(client, REQUEST_RESET, {"e": known})
    assert error_code(first) is None, "the within-budget call to the real account was refused"
    if budget == "address":
        second = post_account(client, REQUEST_RESET, {"e": ghost})
        assert error_code(second) is None, "the within-budget call to the unknown address was refused"
    return queries.count


class _RecordingCache:
    """Wraps the cache the limiter spends against and records every call as (method, scope).

    Keys are `throttle:<scope>:<identity>`; only the scope is kept, so what is recorded is the
    SHAPE of the work — which budgets, in which order, how many round trips — and never an
    address or an IP."""

    def __init__(self, real, calls):
        self._real = real
        self._calls = calls

    def __getattr__(self, name):
        target = getattr(self._real, name)
        if not callable(target):
            return target

        def recorded(key, *args, **kwargs):
            self._calls.append((name, key.split(":")[1]))
            return target(key, *args, **kwargs)

        return recorded


@pytest.mark.django_db
@pytest.mark.parametrize("budget", sorted(_BUDGET_SETTINGS))
def test_a_refused_request_does_no_work_beyond_its_budget_checks(
    client, settings, capturing_sender, monkeypatch, budget
):
    """THE DETERMINISTIC GUARD for AC2 — the timing probe below is only the second line.

    A refusal must be the same work for a registered and an unregistered address, and that work
    is only the budget checks. Measured in COUNTS, not milliseconds, so it cannot flake:

    * EXACTLY zero database queries, for both addresses. Zero, not "equal": a lookup moved in
      front of the three spends makes the same one query for both addresses, so a comparison
      between them cannot see it, and it is precisely the cheap-refusal property the throttle
      exists to provide (the existence lookup is what a refused caller must not cost).
    * The same sequence of cache calls for both addresses, and exactly the one expected: global,
      then IP, then address, each as `add` + `incr` (see `CacheStore.incr_with_expiry`) — 2, 4 or
      6 calls. An extra or reordered call is a change to the cost of a refusal.
    * No token minted and no email sent.

    Positive controls, so a dead instrument cannot pass: the real account's ALLOWED call made
    database queries and minted, and the cache recorder saw calls."""
    _only_budget_trips(settings, budget)
    calls = []
    monkeypatch.setattr(guards, "cache", _RecordingCache(guards.cache, calls))
    known = _existing_verified_account(
        capturing_sender, email=f"known-{budget}@counts.example", idem=f"refusal-counts-{budget}"
    )
    ghost = f"ghost-{budget}@counts.example"

    queries_for_the_allowed_call = _spend_the_allowed_call(client, budget, known, ghost)

    assert queries_for_the_allowed_call > 0, "the allowed call made no queries — the query counter is dead"
    assert calls, "the cache recorder saw nothing — the call-shape control is dead"
    tokens_before = CredentialToken.objects.count()
    mails_before = len(capturing_sender.reset_tokens)
    assert mails_before == 1, "the real account's allowed call did not mint — the control is dead"

    shapes = {}
    for label, address in (("registered", known), ("unregistered", ghost)):
        calls.clear()
        with _counting_queries() as queries:
            refused = post_account(client, REQUEST_RESET, {"e": address})
        assert error_code(refused) == "RATE_LIMITED"
        assert queries.count == 0, (
            f"a refusal by the {budget} budget ran {queries.count} database queries for the "
            f"{label} address — something existence-dependent runs before the throttle refuses"
        )
        shapes[label] = list(calls)

    expected = [(method, scope) for scope in _SCOPES_SPENT[budget] for method in ("add", "incr")]
    assert shapes["registered"] == shapes["unregistered"], (
        f"a refusal by the {budget} budget makes different cache calls for a registered and an "
        f"unregistered address: {shapes['registered']} vs {shapes['unregistered']}"
    )
    assert shapes["registered"] == expected, (
        f"a refusal by the {budget} budget should cost exactly {expected}, not {shapes['registered']}"
    )
    assert CredentialToken.objects.count() == tokens_before, "a refusal minted a token"
    assert len(capturing_sender.reset_tokens) == mails_before, "a refusal sent an email"


@pytest.mark.django_db
@pytest.mark.parametrize("budget", sorted(_BUDGET_SETTINGS))
def test_a_throttled_refusal_is_byte_identical_for_a_known_and_an_unknown_address(
    client, settings, capturing_sender, budget
):
    _only_budget_trips(settings, budget)
    known = _existing_verified_account(
        capturing_sender, email=f"known-{budget}@refusal.example", idem=f"refusal-bytes-{budget}"
    )
    ghost = f"ghost-{budget}@refusal.example"
    _spend_the_allowed_call(client, budget, known, ghost)
    mails_before = len(capturing_sender.reset_tokens)
    assert mails_before == 1, "the real account's within-budget call did not mint — the control is dead"

    known_refused = post_account(client, REQUEST_RESET, {"e": known})
    ghost_refused = post_account(client, REQUEST_RESET, {"e": ghost})

    assert error_code(known_refused) == "RATE_LIMITED"
    assert error_code(ghost_refused) == "RATE_LIMITED"
    assert known_refused.status_code == ghost_refused.status_code
    assert known_refused.content == ghost_refused.content, (
        f"the {budget} budget's refusal differs between a registered and an unregistered address"
    )
    # Headers and cookies are part of "byte-identical" too: a header that differed between the
    # two would be an oracle the body comparison cannot see.
    assert dict(known_refused.headers) == dict(ghost_refused.headers), (
        f"the {budget} budget's refusal HEADERS differ between a registered and an unregistered address"
    )
    assert known_refused.cookies.output() == ghost_refused.cookies.output()
    assert len(capturing_sender.reset_tokens) == mails_before, "a refusal must send nothing"


# TIMING — the SECOND line of defence, an alarm; the count-based test above is the deterministic
# guard and is the one to read first when either goes red.
#
# The paired-comparison technique, as `test_resend_verification.py` uses it: the two cases are
# interleaved in time (the order alternates each round) so warm-up, GC and host load land on both
# alike, and a measurement is the MEDIAN of 60 per-round differences rather than one wall-clock
# delta. Every sample is asserted to be a real refusal, so the probe cannot quietly time
# accepted calls.
#
# ONE MEASUREMENT WAS NOT ROBUST ENOUGH (86ak65mj5 review: Vera, Cody, Quinn). On UNMODIFIED code,
# with Postgres and Redis in containers on a host at about twice its core count, a median read
# +/-1 to 1.5 ms in a few percent of probes. So the verdict is "leak" only when TWO independent
# measurements both exceed the tolerance on the SAME side: a real, constant leak exceeds it every
# time, while a host spike rarely repeats and rarely repeats with the same sign. The second
# measurement costs nothing unless the first one is out.
#
# WHAT THIS CAN AND CANNOT SEE — measured, not promised:
#   * A planted existence-dependent delay of exactly 2.0 ms is flagged (the control below). It is
#     busy-waited rather than slept because macOS oversleeps `time.sleep`, which made the margin
#     look bigger locally than a Linux runner would give. The tolerance is 1.0 ms, so the real
#     margin is about 1 ms.
#   * A throttle moved AFTER the mint reads about +0.7 to +0.8 ms on SQLite: under the tolerance,
#     so usually NOT flagged here (2 of 40 probes in the review). On Postgres in containers it
#     reads +3 to +15 ms and is. That mutant, and a lookup or a small existence-dependent query
#     in front of the spends (+0.1 to +0.3 ms), are caught by the count-based test, not by this.
#   * It is not a proof of constant time, and it says nothing about the UNTHROTTLED path (the
#     +0.437 ms registered-vs-unregistered branch gap of DEC-013): padding that is 86ak7kka2.
_TIMING_WARMUP_ROUNDS = 8
_TIMING_ROUNDS = 60
_REFUSAL_GAP_TOLERANCE_SECONDS = 0.001
_PLANTED_DELAY_SECONDS = 0.002
_CONTROL_ATTEMPTS = 5


def _busy_wait(seconds):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


def _paired_refusal_gap(client, known, ghost):
    """Median over rounds of (time to refuse `known`) - (time to refuse `ghost`)."""
    gaps = []
    for round_number in range(_TIMING_WARMUP_ROUNDS + _TIMING_ROUNDS):
        order = (known, ghost) if round_number % 2 == 0 else (ghost, known)
        elapsed = {}
        for address in order:
            started = time.perf_counter()
            response = post_account(client, REQUEST_RESET, {"e": address})
            elapsed[address] = time.perf_counter() - started
            assert error_code(response) == "RATE_LIMITED", "a timed sample was not a refusal"
        if round_number >= _TIMING_WARMUP_ROUNDS:
            gaps.append(elapsed[known] - elapsed[ghost])
    return statistics.median(gaps)


def _refusal_timing_verdict(client, known, ghost):
    """(leak, measurements). `leak` only if two independent measurements both exceed the
    tolerance on the SAME side; the second is taken only when the first is out."""
    first = _paired_refusal_gap(client, known, ghost)
    if abs(first) <= _REFUSAL_GAP_TOLERANCE_SECONDS:
        return False, [first]
    second = _paired_refusal_gap(client, known, ghost)
    same_side = (first > 0) == (second > 0)
    return same_side and abs(second) > _REFUSAL_GAP_TOLERANCE_SECONDS, [first, second]


@pytest.mark.django_db
@pytest.mark.parametrize("budget", sorted(_BUDGET_SETTINGS))
def test_a_throttled_refusal_takes_the_same_time_for_a_known_and_an_unknown_address(
    client, settings, capturing_sender, budget
):
    _only_budget_trips(settings, budget)
    known = _existing_verified_account(
        capturing_sender, email=f"known-{budget}@timing.example", idem=f"refusal-timing-{budget}"
    )
    ghost = f"ghost-{budget}@timing.example"
    _spend_the_allowed_call(client, budget, known, ghost)

    leak, gaps = _refusal_timing_verdict(client, known, ghost)

    shown = ", ".join(f"{gap * 1000:+.2f}" for gap in gaps)
    assert not leak, (
        f"two independent paired measurements of {budget}-budget refusals (registered minus "
        f"unregistered, ms: {shown}) both exceeded the +/-{_REFUSAL_GAP_TOLERANCE_SECONDS * 1000:.0f}ms "
        "tolerance on the same side. Repeating on one side is unlikely to be host noise alone, but "
        "read the count-based test first: if "
        "test_a_refused_request_does_no_work_beyond_its_budget_checks passes, re-run on a quieter "
        "host before suspecting the code."
    )


@pytest.mark.django_db
def test_the_refusal_timing_probe_can_see_an_existence_dependent_delay(
    client, settings, capturing_sender, monkeypatch
):
    """The positive control for the test above. Without it, a probe that is simply too noisy or
    too coarse to see anything would pass for the wrong reason. The address budget is made
    deliberately existence-dependent — an exact busy-wait that happens only for the registered
    address — and the SAME verdict, with the SAME tolerance, must flag it.

    Up to five attempts: this proves the probe CAN see a 2.0 ms leak, and a load burst on the host
    must not turn that into a false failure. Under heavy load a single verdict missed the planted
    delay about 7% of the time, in bursts of at most two in a row, so five attempts leave no
    realistic false failure while a blind probe would still fail all five."""
    _only_budget_trips(settings, "address")
    known = _existing_verified_account(
        capturing_sender, email="known-control@timing.example", idem="refusal-timing-control"
    )
    ghost = "ghost-control@timing.example"
    _spend_the_allowed_call(client, "address", known, ghost)

    known_fingerprint = services._email_fingerprint(known)
    real_spend = services.enforce_budget_reporting_outage
    planted = []

    def existence_dependent(scope, identity, setting_name, default):
        if scope == "password_reset_request_addr" and identity == known_fingerprint:
            planted.append(identity)
            _busy_wait(_PLANTED_DELAY_SECONDS)
        return real_spend(scope, identity, setting_name, default)

    monkeypatch.setattr(services, "enforce_budget_reporting_outage", existence_dependent)

    flagged, history = False, []
    for _ in range(_CONTROL_ATTEMPTS):
        flagged, gaps = _refusal_timing_verdict(client, known, ghost)
        history.append(gaps)
        if flagged:
            break

    # A different failure from "the probe is blind": the hook below never ran, which means the
    # control no longer matches the code under test (a renamed scope or function).
    assert planted, "the planted delay never ran — this control's hook no longer matches the code under test"
    assert flagged, (
        f"a planted {_PLANTED_DELAY_SECONDS * 1000:.1f}ms existence-dependent delay was not flagged "
        f"in {_CONTROL_ATTEMPTS} attempts (measurements, ms: "
        f"{[[round(g * 1000, 2) for g in gaps] for gaps in history]}) — the timing probe cannot see "
        "a leak of this size"
    )


# --- bounded memory: the limiter's key space follows the global budget, not the attacker -----
def _record_limiter_keys(monkeypatch):
    """Record every limiter key the code touches, with the expiry window it was given.

    Recorded at `evaluate_budget` rather than by listing the cache, so the assertions mean the
    same thing on LocMemCache (local) and Redis (CI) — `cache._cache` exists only on the former."""
    touched = {}
    real_evaluate = guards.evaluate_budget

    def recording(store, key, limit, window_seconds):
        touched[key] = window_seconds
        return real_evaluate(store, key, limit, window_seconds)

    monkeypatch.setattr(guards, "evaluate_budget", recording)
    return touched


@pytest.mark.django_db
def test_the_keys_the_limiter_can_create_are_bounded_by_the_global_budget_not_by_attacker_input(
    client, settings, monkeypatch
):
    """Every distinct address and every distinct source IP is a distinct cache key, and both are
    attacker-chosen on an unauthenticated endpoint. What stops that being unbounded growth is
    ORDER: the global budget is spent first and raises, so once it is exhausted no further
    address or IP key is ever created. This sprays ten times the global limit of distinct
    addresses from distinct sources and counts the keys the limiter actually touched.

    The within-budget calls are the positive control: exactly `global_limit` address and IP
    keys must have been seen, so a recorder that saw nothing cannot pass. Every key must also
    carry the EXPIRY the budget configures: a key with no (or a huge) window is a key that never
    leaves the store, which is the other half of "bounded"."""
    global_limit = 5
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL = (global_limit, 3600)
    settings.SELAHCUE_THROTTLE_RESET_REQUEST = (10_000, 3600)
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (10_000, 900)
    touched = _record_limiter_keys(monkeypatch)

    outcomes = [
        error_code(
            post_account(
                client, REQUEST_RESET, {"e": f"spray-{n}@bound.example"}, REMOTE_ADDR=f"203.0.113.{n + 1}"
            )
        )
        for n in range(global_limit * 10)
    ]
    assert outcomes[:global_limit] == [None] * global_limit, "the within-budget sprays must be served"
    assert set(outcomes[global_limit:]) == {"RATE_LIMITED"}, "the rest must be refused by the global budget"

    def keys_for(scope):
        return {key for key in touched if key.startswith(f"throttle:{scope}:")}

    assert len(keys_for("password_reset_request_global")) == 1
    assert len(keys_for("password_reset_request_addr")) == global_limit, (
        "address keys were created beyond the global budget — attacker input, not the budget, "
        "now decides how many keys the limiter holds"
    )
    assert len(keys_for("password_reset_request_ip")) == global_limit

    configured_window = {
        "password_reset_request_global": 3600,
        "password_reset_request_ip": 3600,
        "password_reset_request_addr": 900,
    }
    for key, window in touched.items():
        scope = key.split(":")[1]
        assert window == configured_window[scope], (
            f"{scope} was given an expiry of {window}s, not the configured "
            f"{configured_window[scope]}s — a key that outlives its window is unbounded growth"
        )


@pytest.mark.django_db
def test_a_malformed_address_is_rejected_before_any_budget_is_spent(client, settings, monkeypatch):
    """Malformed addresses are rejected before ANY budget is spent, so they cannot mint a limiter
    key (an address's validity is not existence-dependent, so this leaks nothing).

    Its own test, with every budget wide open, because that is the only state in which the
    assertion can bite: after the global budget is spent every request is refused before it
    could create a key, so a check placed there could never fail. The well-formed call at the
    end is the positive control that keys are recorded at all."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL = (10_000, 3600)
    settings.SELAHCUE_THROTTLE_RESET_REQUEST = (10_000, 3600)
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (10_000, 900)
    touched = _record_limiter_keys(monkeypatch)

    for n in range(20):
        rejected = post_account(client, REQUEST_RESET, {"e": f"not-an-address-{n}"})
        assert error_code(rejected) == "VALIDATION_FAILED"
    assert touched == {}, "a malformed address created a limiter key"

    accepted = post_account(client, REQUEST_RESET, {"e": "well-formed@bound.example"})
    assert error_code(accepted) is None
    assert len(touched) == 3, "the recorder saw no keys for a well-formed address — the control is dead"


# --- QA review (Quinn): regressions the suite did not pin -------------------------------------
def _live_reset_token_ids(user):
    return sorted(
        CredentialToken.objects.filter(
            customer_user=user, purpose=CredentialTokenPurpose.PASSWORD_RESET, consumed_at__isnull=True
        ).values_list("id", flat=True)
    )


@pytest.mark.django_db
def test_a_refused_request_leaves_the_real_accounts_live_link_untouched_and_usable(
    client, capturing_sender
):
    """A refused request must not consume or replace the link the person already holds: the
    caller was refused, so nothing about their account may have changed. The last link that was
    actually MAILED must still work."""
    email = _existing_verified_account(capturing_sender, email="victim@live.example", idem="qa-live-link-0001")
    user = CustomerUser.objects.get(email=email)
    served = [post_account(client, REQUEST_RESET, {"e": email}) for _ in range(3)]
    assert [error_code(r) for r in served] == [None, None, None]
    live_before = _live_reset_token_ids(user)
    assert len(live_before) == 1, "control: exactly one live link before the refusal"

    refused = post_account(client, REQUEST_RESET, {"e": email})

    assert error_code(refused) == "RATE_LIMITED"
    assert _live_reset_token_ids(user) == live_before, "a REFUSED request consumed or replaced the live link"
    confirm = post_account(
        client,
        CONFIRM_RESET,
        {"input": {"token": capturing_sender.reset_tokens[-1], "newPassword": "qa-new-passphrase-1"}},
    )
    assert body(confirm)["data"]["confirmPasswordReset"]["reset"] is True, "the last MAILED link stopped working"


class _GlobalKeyOnlyBrokenStore:
    """A limiter store that fails ONLY for the global budget's key — a partial outage."""

    def __init__(self, cache):
        self._real = CacheStore(cache)

    def incr_with_expiry(self, key, window_seconds):
        if key.startswith("throttle:password_reset_request_global:"):
            raise RuntimeError("the shard holding the global key is down")
        return self._real.incr_with_expiry(key, window_seconds)


@pytest.mark.django_db
def test_a_global_budget_outage_does_not_switch_off_the_address_budget(client, settings, monkeypatch):
    """The three spends are three statements joined by `|=`, never `or` (see the comment in
    `request_password_reset`). If the first budget's outage short-circuited the others, a partial
    outage would quietly drop the per-address cap. Nothing else in the suite pins that."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (2, 900)
    monkeypatch.setattr(guards, "CacheStore", lambda cache: _GlobalKeyOnlyBrokenStore(cache))

    codes = [
        error_code(post_account(client, REQUEST_RESET, {"e": "partial@outage.example"})) for _ in range(3)
    ]

    assert codes == [None, None, "RATE_LIMITED"], codes


@pytest.mark.django_db
@pytest.mark.parametrize(
    "spelling",
    ["VICTIM@Variant.Example", "  victim@variant.example  ", "\tvictim@variant.example\n"],
)
def test_every_spelling_that_reaches_the_account_shares_its_one_address_budget(
    client, settings, capturing_sender, spelling
):
    """The address budget's key must be the same fingerprint the account lookup uses. A key built
    from a differently-normalised string would give a padded or re-cased spelling a budget of its
    own while it still reaches the same account — a bypass of the per-address cap."""
    settings.SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS = (1, 900)
    email = _existing_verified_account(capturing_sender, email="victim@variant.example", idem="qa-variant-0001")

    first = post_account(client, REQUEST_RESET, {"e": email})
    second = post_account(client, REQUEST_RESET, {"e": spelling})

    assert error_code(first) is None
    assert error_code(second) == "RATE_LIMITED", f"{spelling!r} reached the account on a budget of its own"
    assert len(capturing_sender.reset_tokens) == 1
