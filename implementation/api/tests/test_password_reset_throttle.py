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
"""

import json

import pytest
from django.core.cache import cache
from django.test import TestCase

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
    from selahcue_api.apps.accounts import services

    services._reset_floor_overrun_reporting()


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
