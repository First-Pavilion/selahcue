#!/usr/bin/env python3
"""Behavioural state check for the auth pages: /verify, /reset, /signin, /signup, /forgot-password.

Serves the REAL production bundle from `dist/` over a local HTTP server with SPA
fallback, drives it in headless Chrome with a scripted `fetch` stub, and asserts the
rendered DOM for every state the design defines and every state the API can actually
produce.

This is the counterpart to `npm test`: those tests pin the pure logic (password policy,
error classification, token parsing), this one proves the pages built from that logic
actually render the right thing — real Vue, real router, real CSS, real focus and ARIA.
It follows the pattern already established by `scripts/operator_headless.py`.

THE ENUMERATION PROBE (86ak11r67)
---------------------------------
Some of what this file has to prove is not a property of ONE render, it is an EQUALITY
between two. "No response reveals whether an email address is registered" cannot be
asserted by looking at a single page: it needs the page a registered address produces and
the page an unregistered one produces, side by side, identical.

So scenarios can RECORD normalised text under a key (`record()` in the driver, emitted in
an `ENUMERATION` block), and `EQUIVALENCE_GROUPS` below asserts that the recordings from
the paired scenarios match exactly. Email addresses are masked before recording, so the
two halves can use genuinely different addresses and still be comparable — a client that
started saying "that address is already registered" for one of them would fail here.

Both the rendered TEXT and the sequence of GraphQL OPERATIONS are compared: leaking by
sending a second request for one branch and not the other would be just as effective an
oracle as leaking in the copy.

Why HTTP and not file://: the app uses `createWebHistory`, so vue-router needs real
paths (`/verify`, `/reset`) and a server that falls back to index.html for them.

Chrome is resolved via CHROME_BIN, then PATH, then the macOS app bundle. If Chrome is
absent this exits 0 with a loud SKIP so a Chrome-less box is not blocked — UNLESS
SELAHCUE_HEADLESS_REQUIRE=1, which turns a missing Chrome into a hard failure so a CI
gate can never silently no-op.

Usage:
    npm run build && npm run test:states

Exit codes:
    0  all checks passed (or Chrome absent and not required)
    1  one or more checks FAILED
    2  infrastructure problem (no dist, a STALE dist, Chrome timeout, no results block)
    4  the suite silently shrank — fewer checks ran than expected
"""

from __future__ import annotations

import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKETING = HERE.parent
DIST = Path(os.environ.get("SELAHCUE_MARKETING_DIST") or (MARKETING / "dist"))

# Floor on the number of checks that must run, so a driver regression that silently runs
# FEWER checks (and therefore reports 0 FAIL) still fails. Set TIGHT to the real count.
# Bump it when adding checks; never lower it to mask a lost one.
#
# It HAS moved down once, deliberately: 1384 → 1381 when the `elapsed` facet stopped being
# gated and became reported evidence, removing three comparisons and adding three INFO
# lines. The guard did its job and refused the run until this number was changed on
# purpose, which is the only acceptable way for it to go down.
#
# 1384 → 1483 in the PR #17 review round. What was added: 24 surface comparisons (the three
# pairs at two new moments — before submit and in flight — times four facets), 6 in-flight
# reach checks, 3 re-gated `elapsed` comparisons, 9 forward-path checks on failure states
# that had none, 3 whole scenarios for the `?next=` round trip, and one declared
# button-expectation check, and one scenario (32 checks) for the permanent-input-error
# path MEDIUM-5 reported, plus two of the coverage gaps Quinn named — C-008's live-looking
# stale hint, and RATE_LIMITED actually rendering at sign-in. `verify-loading` gives 3 back by declaring itself button-less.
#
# WHAT THIS NUMBER IS AND IS NOT (Quinn, LOW-1): it counts LINES PUSHED TO `results`, not
# assertions — she verified that by pushing two non-assertion INFO lines and watching the
# total rise 1384 → 1386. Combined with the 462 broadcast negatives from the banned-phrase
# loop, all of which pass together whenever `cardText()` returns `''`, the floor is weaker
# evidence than its size suggests. It catches a driver regression that runs FEWER checks;
# it is not a measure of coverage, and it should not be read as one.
#
# 1556 -> 1707 in review round 3. What was added: the rendered rate-limit claim ban (4
# phrases x 6 states that reach a rate-limited screen = 24), the 6 markers recording that
# those states were scanned at all, 1 cross-scenario check asserting every rate-limited
# scenario was among them, and THREE NEW SCENARIOS -- `signup-rate-limited`,
# `signup-resend-rate-limited` and `signin-resend-rate-limited` -- which exist because
# three of the six rate-limit call sites were reached by no scenario at all.
#
# THAT ROUND SET THE FLOOR TO 1677 AND THE SUITE ACTUALLY RAN 1707. Not a failure — a
# floor that is 30 short is still a floor — but 30 checks could then be deleted without
# the alarm sounding, which is the property the number exists to have. Recorded rather
# than quietly corrected, because "the constant drifted below the measurement" is the same
# class of defect as the stale error table this batch is fixing, and the fix is the same:
# re-measure, do not remember.
#
# 1707 -> 1746 with `reset-password-invalid` (W-03), the scenario that renders
# PASSWORD_INVALID. Measured on the tree that ships it, twice.
#
# 1746 -> 1751 with W-05's credential sweep: `signin-success` traded two rows (a length
# probe and the two-name token check) for seven — two canaries proving the reader reaches
# sessionStorage and document.cookie, one proving the canaries were removed again, one
# non-vacuity row, one asserting the scenario typed a credential at all, the value-based
# sweep itself, and the old name-based check kept as a complement. Measured on the tree
# that ships it, not derived from the arithmetic.
EXPECTED_MIN_CHECKS = 1751


def find_chrome() -> str | None:
    env = os.environ.get("CHROME_BIN")
    if env and os.path.exists(env):
        return env
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    for path in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ):
        if os.path.exists(path):
            return path
    return None


# ------------------------------------------------------------------- shared auth copy ---
# ONE DEFINITION, READ NOT RESTATED.
#
# `src/lib/auth/messages.ts` owns the phrases rate-limit copy may never say, and the
# rate-limit copy itself. Both are read out of that source here and injected into the
# driver, for the reason MEDIUM-6 keeps re-teaching: a list restated in a second place is a
# second thing to forget to update, and the check that reads the stale copy still passes.
#
# The specific defect this closes: `tests/authCopy.test.ts` scanned the CONSTANTS in
# messages.ts for these phrases. A view that appended to a constant at one of its four call
# sites — `RESEND_RATE_LIMITED + ' for that address'` — left every constant clean and
# rendered a forbidden phrase, and both gates stayed green. A forbidden string is only
# forbidden where the scanner looks; this makes the scanner look at the rendered page.
MESSAGES_TS = MARKETING / "src" / "lib" / "auth" / "messages.ts"

# WHICH scenarios must actually reach a rate-limited state and be scanned.
#
# A ban that never fires is indistinguishable from a ban that fires and holds, so the
# coverage is asserted rather than assumed -- but a bare COUNT was not enough, and the
# mutation that proved it is worth recording. Appending " for this account" to
# `SignInView`'s `RESEND_RATE_LIMITED` passed BOTH gates with the count at 3: the sign-in
# rate-limit scenario exercises the BANNER (`RATE_LIMITED_TITLE`), and the resend branch on
# the same page was reached by nothing. Six call sites across four views render rate-limit
# copy; three of them were being scanned, and a count of three said "covered".
#
# So the rule is derived from the scenario list instead of written as a number: every
# scenario whose name says it is a rate-limited state must have been scanned. Adding such a
# scenario automatically requires it to render rate-limit copy, and a scenario that stops
# rendering it fails here instead of quietly leaving a call site unscanned.
RATE_LIMIT_CLAIM_SCENARIOS_MIN = 6


def rate_limited_scenarios() -> list[str]:
    return [name for name, _ in SCENARIOS if "rate-limited" in name]


def read_ts_string_array(source: str, name: str) -> list[str]:
    """Pull `export const NAME = ['a', 'b'] as const` out of the TypeScript."""
    match = re.search(
        r"export const " + re.escape(name) + r"\s*=\s*\[(.*?)\]", source, re.S
    )
    if not match:
        print(f"FAIL: could not find {name} in {MESSAGES_TS}")
        raise SystemExit(2)
    return re.findall(r"'([^']*)'", match.group(1))


def read_ts_string(source: str, name: str) -> str:
    """Pull `export const NAME = '...'` (or a two-line continuation) out of the TypeScript."""
    match = re.search(
        r"export const " + re.escape(name) + r"\s*=\s*\n?\s*(['\"])(.*?)\1", source, re.S
    )
    if not match:
        print(f"FAIL: could not find {name} in {MESSAGES_TS}")
        raise SystemExit(2)
    return match.group(2)


def shared_copy() -> dict:
    source = MESSAGES_TS.read_text(encoding="utf-8")
    phrases = read_ts_string_array(source, "ADDRESS_CLAIM_PHRASES")
    if len(phrases) < 4:
        print(f"FAIL: ADDRESS_CLAIM_PHRASES has only {len(phrases)} entries")
        raise SystemExit(2)
    return {
        "claims": phrases,
        # The copy whose PRESENCE marks a state as rate-limited. Read from the module for
        # the same reason as the phrases: a trigger built from a stale copy stops firing
        # silently, and a scan that never triggers passes.
        "rateLimitMarkers": [
            read_ts_string(source, "RESEND_RATE_LIMITED"),
            read_ts_string(source, "RATE_LIMITED_TITLE"),
        ],
    }


# --------------------------------------------------------------------------- driver ---
# Injected into <head> so it runs BEFORE the app module. It must, because it has to
# capture the scenario name out of the query string before the view scrubs the query,
# and it has to replace `fetch` before onMounted fires.

DRIVER = r"""
<script>
(function () {
  var QS = new URLSearchParams(location.search);
  var SCENARIO = QS.get('__scenario') || '';
  // Injected from src/lib/auth/messages.ts at serve time -- see shared_copy(). Not typed
  // out here, so this scan and tests/authCopy.test.ts read the SAME list.
  var SHARED_COPY = __SHARED_COPY__;

  /*
   * A DETERMINISTIC BROWSER LOCALE, for the one scenario that asserts what the form does
   * with it. Set here because the driver runs before the app module, and `guessCountry()`
   * is called during SignUpView's setup -- by the time a scenario function runs, the
   * pre-selection has already happened.
   *
   * `guessCountry` is well covered as a FUNCTION (`tests/signupPolicy.test.ts` pins
   * en-GB -> GB and en-US -> US) and was UNWIRED IN PLACE: dropping
   * `const country = ref(guessCountry())` to `ref('')` and removing the now-unused import
   * passed `npm test` 148/148 and this suite at 58 scenarios / 1677 checks / 0 FAIL. Same
   * shape as MEDIUM-2's `safeNextPath`: the unit test proves the rule, and nothing proved
   * the form consults it.
   */
  if (SCENARIO === 'signup-locale-preselect') {
    try {
      Object.defineProperty(navigator, 'language', { get: function () { return 'en-GB'; } });
      Object.defineProperty(navigator, 'languages', { get: function () { return ['en-GB']; } });
    } catch (e) { /* a browser that refuses the override fails the assertion below */ }
  }
  // Captured before the app boots: whether this page was opened WITH a token decides
  // which scrubbing assertion applies below.
  var HAD_TOKEN = QS.get('token') !== null;
  var results = [];
  var calls = [];
  // CSRF bootstraps are tracked SEPARATELY from GraphQL operations so that every existing
  // `calls.length === 1` assertion keeps measuring what it was written to measure. They
  // are still asserted — see csrfChecks() — just not conflated with mutations.
  var csrfCalls = [];
  // Normalised text recorded for cross-scenario comparison. See ENUMERATION above.
  var records = [];
  /**
   * Every secret this scenario actually TYPED, recorded where the typing happens.
   *
   * W-05 (Quinn). The storage sweep in `signin-success` used to assert
   * `stored.indexOf('sessionToken') === -1 && stored.indexOf('SC-SESSION') === -1` — an
   * enumeration of two forbidden NAMES. She planted
   * `window.localStorage.setItem('selahcue.lastCredential', password)` at the top of
   * `sessionStore.signIn`, where the password is in scope, and every gate stayed green:
   * build 0, `npm test` 0 at 132/0, `test:states` 0 at 55 scenarios / 1556 checks / 0
   * FAIL. The visitor's plaintext password persisted on every sign-in, readable by any
   * script on the origin, under a check whose stated job is "No token in storage,
   * anywhere". Eleven lines above it the same scenario already asserted the password was
   * gone from the RENDERED page — it simply never asked storage the same question.
   *
   * This is the same repair the attribute whitelist got: stop remembering a list of names
   * and assert on the VALUE the scenario knows it handled. A name-based rule can only ever
   * catch the leak someone already thought of.
   *
   * Nothing in the tree writes a password to storage today. This is a hole in the control,
   * not a live leak.
   */
  var typedSecrets = [];

  function json(body, status) {
    return new Response(JSON.stringify(body), {
      status: status || 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Mutable state a couple of scenarios need across calls within one page load.
  var registerAttempts = 0;
  var signedOut = false;

  /**
   * C-008's NAMED CASE, which was never scripted (Quinn).
   *
   * The criterion is "the session hint ALONE never grants entry", and both scenarios that
   * exercised the guard's refusal ran with no hint present at all — so they proved the
   * guard refuses an ABSENT hint, which is not the interesting half. The case that matters
   * is a live-LOOKING hint in localStorage with a dead server session: the hint is
   * attacker-writable, and it goes stale in exactly the direction that matters, claiming a
   * session that a password change or a sign-out elsewhere revoked minutes ago.
   *
   * Written here, in the driver, because it must exist BEFORE the app module boots — the
   * route guard runs on the very first navigation.
   */
  var plantedHint = null;
  if (SCENARIO === 'account-stale-hint') {
    plantedHint = JSON.stringify({
      role: 'ADMIN',
      orgId: 'org-harness',
      expiresAt: new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString()
    });
    window.localStorage.setItem('selahcue.session', plantedHint);
  }

  function UNAUTHENTICATED() { return json({ errors: [{ extensions: { code: 'UNAUTHENTICATED' } }] }); }
  function LOGIN_IN(days) {
    return json({ data: { login: {
      expiresAt: new Date(Date.now() + days * 24 * 3600 * 1000).toISOString(),
      role: 'ADMIN', orgId: 'org-harness' } } });
  }
  function LOGIN_OK() {
    // Note the payload carries NO sessionToken: the client does not select it, because
    // the cookie is set by the resolver regardless and the browser must never hold the
    // raw credential. If the client ever starts asking for it, the field is absent here
    // and `data.login.sessionToken` reads undefined — which the scenario asserts on.
    return json({ data: { login: {
      expiresAt: new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString(),
      role: 'ADMIN', orgId: 'org-harness' } } });
  }
  function VIEWER_OK() {
    return json({ data: { accountViewer: { surface: 'account', actorId: 'user-1', orgId: 'org-harness' } } });
  }
  function REGISTERED() { return json({ data: { registerCustomerUser: { accepted: true } } }); }
  function RESET_REQUESTED() { return json({ data: { requestPasswordReset: { accepted: true } } }); }

  // Scripted API. Keyed by scenario; every entry mirrors a real response shape from
  // selahcue_api (errors come back on HTTP 200 with extensions.code).
  var REPLIES = {
    'verify-success':      function () { return json({ data: { verifyEmail: { verified: true } } }); },
    'verify-invalid':      function () { return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] }); },
    'verify-loading':      function () { return new Promise(function () {}); },
    'verify-unreachable':  function () { throw new TypeError('Failed to fetch'); },
    'verify-resend':       function (op) {
      if (op === 'VerifyEmail') return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] });
      // Keyed by the REAL field name from account_schema.py:180 — Strawberry camel-cases
      // `resend_verification_email`. If the client ever asks for a different field, the
      // payload read below misses and this scenario fails, which is the point.
      return json({ data: { resendVerificationEmail: { accepted: true } } });
    },
    'verify-rate-limited': function (op) {
      if (op === 'VerifyEmail') return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] });
      return json({ errors: [{ extensions: { code: 'RATE_LIMITED' } }] });
    },
    // Lands on V3 so the resend form exists, then the driver submits a malformed address.
    'verify-bad-email':    function () { return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] }); },
    'verify-resend-fails': function (op) {
      if (op === 'VerifyEmail') return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] });
      // The mutation rejects the address as malformed. Also stands in for any future
      // regression that renames the field: an unknown field is collapsed to the same
      // VALIDATION_FAILED, and the page must still refuse to claim an email was sent.
      return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] });
    },
    'reset-success':       function () { return json({ data: { confirmPasswordReset: { reset: true } } }); },
    'reset-invalid':       function () { return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] }); },
    // FR-551 / DEC-017. `confirm_password_reset` reaches its password check only after the
    // token has been looked up and found live, so this envelope is the server saying "the
    // link works, the password does not" — the one reset failure that is neither R4 nor R7.
    'reset-password-invalid': function () { return json({ errors: [{ extensions: { code: 'PASSWORD_INVALID' } }] }); },
    'reset-unreachable':   function () { throw new TypeError('Failed to fetch'); },
    'reset-fresh-link':    function (op) {
      if (op === 'ConfirmPasswordReset') return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] });
      return json({ data: { requestPasswordReset: { accepted: true } } });
    },

    // ------------------------------------------------------------------ sign-in (86ak11r67) --
    // `login` returns the SAME UNAUTHENTICATED for an unknown address, a wrong password and
    // a locked-out account, and equalises their timing. These two scenarios differ only in
    // the address typed; EQUIVALENCE_GROUPS asserts their renders are identical.
    // `gated`: the reply is held until the scenario releases it, so the in-flight state
    // actually paints and can be compared. See `gated()` for why these six and not a timer.
    'signin-rejected-unknown':        gated(function () { return UNAUTHENTICATED(); }),
    'signin-rejected-wrong-password': gated(function () { return UNAUTHENTICATED(); }),
    'signin-unverified':   function () { return json({ errors: [{ extensions: { code: 'POLICY_DENIED' } }] }); },
    'signin-resend':       function (op) {
      if (op === 'Login') return json({ errors: [{ extensions: { code: 'POLICY_DENIED' } }] });
      return json({ data: { resendVerificationEmail: { accepted: true } } });
    },
    'signin-unreachable':  function () { throw new TypeError('Failed to fetch'); },
    'signin-form':         function () { return UNAUTHENTICATED(); },
    'signin-validation':   function () { return UNAUTHENTICATED(); },
    'signin-expired':      function () { return UNAUTHENTICATED(); },
    'signin-success':      function (op) {
      if (op === 'Login') return LOGIN_OK();
      return VIEWER_OK();
    },
    // MEDIUM-2 (Quinn): `safeNextPath` is well tested in isolation and was UNTESTED IN
    // PLACE. She replaced `SignInView.vue`'s only call site with a bare
    // `router.replace('/account')` and both gates stayed green — the open-redirect guard
    // could be unwired entirely, and the `?next=` round trip had no end-to-end coverage on
    // either half. These three scenarios sign in from a guarded redirect and assert where
    // the visitor actually lands.
    'signin-next-honoured': function (op) {
      if (op === 'Login') return LOGIN_OK();
      return VIEWER_OK();
    },
    'signin-next-hostile':  function (op) {
      if (op === 'Login') return LOGIN_OK();
      return VIEWER_OK();
    },
    'signin-next-unmatched': function (op) {
      if (op === 'Login') return LOGIN_OK();
      return VIEWER_OK();
    },
    'session-lifecycle':   function (op) {
      if (op === 'Login') return LOGIN_OK();
      if (op === 'Logout') { signedOut = true; return json({ data: { logout: { revoked: true } } }); }
      // The guard probes before sign-out (live) and again after (gone). `signedOut` is
      // flipped by the Logout above, so one scripted surface serves both halves.
      return signedOut ? UNAUTHENTICATED() : VIEWER_OK();
    },
    'signout-failure':     function (op) {
      if (op === 'Login') return LOGIN_OK();
      if (op === 'Logout') throw new TypeError('Failed to fetch');
      return VIEWER_OK();
    },

    // ------------------------------------------------------------- create account --
    // Both return the identical envelope, because `register_customer_user` does: it
    // returns accepted:true for a brand-new address AND for one that already has an
    // account, emailing the real owner out of band instead. EQUIVALENCE_GROUPS asserts
    // the two renders match.
    'signup-new':          gated(function () { return REGISTERED(); }),
    'signup-existing':     gated(function () { return REGISTERED(); }),
    'signup-form':         function () { return REGISTERED(); },
    'signup-short-password': function () { return REGISTERED(); },
    'signup-no-terms':     function () { return REGISTERED(); },
    'signup-no-country':   function () { return REGISTERED(); },
    'signup-unreachable':  function () { throw new TypeError('Failed to fetch'); },
    'signup-rejected':     function () { return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] }); },
    'signup-idempotency':  function () {
      // First attempt dies in transport, second succeeds — the retry the idempotency key
      // exists for. The scenario asserts BOTH carried the same key.
      registerAttempts += 1;
      if (registerAttempts === 1) throw new TypeError('Failed to fetch');
      return REGISTERED();
    },
    'signup-resend':       function (op) {
      if (op === 'RegisterCustomerUser') return REGISTERED();
      return json({ data: { resendVerificationEmail: { accepted: true } } });
    },
    // The three rate-limit call sites no scenario used to reach. Found by mutation:
    // appending " for this account" to SignInView's RESEND_RATE_LIMITED passed BOTH gates,
    // because `signin-rate-limited` exercises the sign-in banner (RATE_LIMITED_TITLE), not
    // the resend branch. Six call sites render rate-limit copy; three were scanned.
    'signup-locale-preselect': function () { return REGISTERED(); },
    'signup-rate-limited': function () { return json({ errors: [{ extensions: { code: 'RATE_LIMITED' } }] }); },
    'signup-resend-rate-limited': function (op) {
      if (op === 'RegisterCustomerUser') return REGISTERED();
      return json({ errors: [{ extensions: { code: 'RATE_LIMITED' } }] });
    },
    'signin-resend-rate-limited': function (op) {
      if (op === 'Login') return json({ errors: [{ extensions: { code: 'POLICY_DENIED' } }] });
      return json({ errors: [{ extensions: { code: 'RATE_LIMITED' } }] });
    },

    // ----------------------------------------------------------- forgot password --
    // Same uniformity: `request_password_reset` pads the miss branch with a dummy PBKDF2
    // so a registered and an unregistered address are indistinguishable in code AND time.
    'forgot-registered':   gated(function () { return RESET_REQUESTED(); }),
    'forgot-unregistered': gated(function () { return RESET_REQUESTED(); }),
    'forgot-form':         function () { return RESET_REQUESTED(); },
    'forgot-bad-email':    function () { return RESET_REQUESTED(); },
    'forgot-failure':      function () { return json({ errors: [{ extensions: { code: 'INTERNAL' } }] }); },
    // MEDIUM-5 (Cody): a PERMANENT input error that the client's mirror let through. The
    // address here is well-formed as far as the client is concerned, so this is the
    // genuine client/server disagreement the mirror narrows to — and it must not be
    // reported as "try again in a moment".
    'forgot-server-rejects-address':
                           function () { return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] }); },
    'forgot-rate-limited': function () { return json({ errors: [{ extensions: { code: 'RATE_LIMITED' } }] }); },

    // --------------------------------------------------------------- route guard --
    'account-guarded':     function () { return UNAUTHENTICATED(); },
    // A hint that looks alive, over a session the server says is dead.
    'account-stale-hint':  function () { return UNAUTHENTICATED(); },
    // RATE_LIMITED at sign-in. `RATE_LIMITED_TITLE`/`_BODY` were dead strings as far as
    // the estate was concerned (Quinn), and rate limiting is a likely production state on
    // a sign-in form — where the copy must not imply the account exists.
    'signin-rate-limited': function () { return json({ errors: [{ extensions: { code: 'RATE_LIMITED' } }] }); },
    'account-allowed':     function () { return VIEWER_OK(); },

    // ------------------------------------------------------------ session refresh --
    // A matched pair. `session-refresh` has 3 days left (inside the 7-day threshold);
    // `session-no-refresh` has 30 (outside it). Without the second, "a refresh happened"
    // would be satisfied just as well by code that rotates on every navigation — which is
    // the thing the threshold exists to prevent, because rotation can strand a session.
    'session-refresh':     function (op) {
      if (op === 'Login') return LOGIN_IN(3);
      if (op === 'RefreshSession') {
        return json({ data: { refreshSession: {
          expiresAt: new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString() } } });
      }
      return VIEWER_OK();
    },
    'session-no-refresh':  function (op) {
      if (op === 'Login') return LOGIN_IN(30);
      return VIEWER_OK();
    }
  };

  window.fetch = function (url, init) {
    // The CSRF bootstrap. Answered the way Django answers it — including SETTING THE
    // COOKIE — so the run reproduces production exactly: the first mutation of a page
    // load is preceded by one GET, and every mutation after it carries the header and
    // needs no further bootstrap. Without the cookie being set here the stub would
    // re-bootstrap on every call, which is correct behaviour for a cookie that never
    // arrives but would not exercise the path that actually ships.
    if (String(url).indexOf('/graphql/csrf') !== -1) {
      csrfCalls.push(String(url));
      document.cookie = 'csrftoken=harness-csrf-token; path=/';
      return Promise.resolve(json({ ready: true }));
    }

    var body = {};
    try { body = JSON.parse((init && init.body) || '{}'); } catch (e) {}
    // `query` too, not just `mutation`: `accountViewer` is the session probe the route
    // guard runs, and it is a query.
    var op = (/(?:mutation|query)\s+(\w+)/.exec(body.query || '') || [])[1] || '';
    calls.push({ url: String(url), op: op, variables: body.variables || {},
                 // `query` is the DECODED document. `raw` is the JSON-encoded body, where
                 // newlines are literal \\n escapes — regexing that with \\s never matches.
                 query: body.query || '', raw: (init && init.body) || '',
                 headers: (init && init.headers) || {} });
    var reply = REPLIES[SCENARIO];
    if (!reply) return Promise.reject(new TypeError('no scripted reply for ' + SCENARIO));
    try { return Promise.resolve(reply(op)); } catch (e) { return Promise.reject(e); }
  };

  function check(name, condition, detail) {
    results.push((condition ? 'PASS' : 'FAIL') + ' [' + SCENARIO + '] ' + name + (condition ? '' : ' -- ' + (detail || '')));
  }

  function cardText() {
    var card = document.querySelector('.au-card');
    return card ? (card.innerText || card.textContent || '') : '';
  }

  function pageText() {
    return (document.body.innerText || document.body.textContent || '');
  }

  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  /**
   * EVERY attribute is signed. There is no whitelist any more, and that is the fix.
   *
   * There used to be a list of twenty-three names, and it was one name short in a way
   * nobody could have predicted from the list itself. Quinn put the signup footer in
   * danger red for the already-registered address and near-black for the new one, keyed
   * off the submitted address, expressed as an INLINE STYLE:
   *
   *     signup-new       computed colour rgb(16, 24, 40)
   *     signup-existing  computed colour rgb(180, 35, 24)
   *
   * `style` was not on the list and `toneSignature()` reads only class names, so the
   * colour channel had a half neither facet could see — in the SETTLED state, in the
   * shipped sample window, with no transience and no timing assumption. `npm test` and
   * `npm run test:states` were both green.
   *
   * Adding `style` would have closed that one hole and left the next one. The list had
   * already been extended twice for exactly this reason (`placeholder`/`title`/`alt` after
   * Cody, `value` after Quinn). A whitelist of attributes is the wrong shape for a facet
   * whose job is to notice ANY difference, so it is inverted: sign everything, and
   * normalise only the two things that are legitimately non-deterministic — generated ids,
   * and the email address itself.
   *
   * `ID_REF_ATTRS` is gone with it. LOW-5 (Quinn): it named `aria-labelledby` and
   * `aria-controls`, neither of which was ever signed, and the comment above claimed `id`
   * and `for` were "collapsed" when they were not signed at all. All three are signed now,
   * and the collapse below applies to every attribute except `class`.
   */

  /**
   * `FormField.vue`'s generator: `'field-' + Math.random().toString(36).substr(2, 9)`.
   * Anchored to that shape — 7-9 base36 characters — rather than to any `field-` token,
   * so `field-error` cannot match it even where the collapse does apply.
   */
  var GENERATED_ID = /field-[a-z0-9]{7,9}\b/g;

  /**
   * MEDIUM-2: the old mask was `[^\s@]+@[^\s@]+\.[^\s@]+`, which is unanchored and
   * greedy over `/` and `?`, so `/signin?u=a@b.com` collapsed to `<EMAIL>` — erasing the
   * DESTINATION along with the address and re-encoding the exact leak this facet was
   * built to catch. The local part is restricted to characters that cannot appear in a
   * path or query separator, so the surrounding URL survives.
   */
  var EMAIL_IN_VALUE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

  /**
   * Record normalised text for cross-scenario comparison.
   *
   * Email addresses are masked, so two scenarios may use different addresses and still
   * compare equal — which is the point: the comparison must catch copy that VARIES with
   * the address, not trip over the address itself. Whitespace is collapsed because Vue's
   * rendered indentation is not part of what a user reads.
   */
  function record(key, value) {
    var masked = String(value)
      .replace(EMAIL_IN_VALUE, '<EMAIL>')
      .replace(/\s+/g, ' ')
      .trim();
    records.push(key + ' :: ' + masked);
  }

  /** The operation sequence, for the same comparison. A different number or order of
      requests between two branches is an oracle just as surely as different copy is. */
  function opSequence() {
    return calls.map(function (c) { return c.op; }).join(',');
  }

  /**
   * Every status/tone class the card is wearing, in DOM order.
   *
   * LOW-3 (Sana): `cardText()` compares WORDS. Two branches with identical copy but a
   * different banner tone — danger red for one address, neutral for another — would be a
   * COLOUR-ONLY oracle that passed the text comparison outright. Colour is meaning here,
   * so it is compared like meaning.
   */
  function toneSignature() {
    // document.body, NOT `.au-card`. Quinn: LOW-2 widened TEXT to the whole page but left
    // COLOUR scoped to the card, and `AuthShell` renders the footer outside it — so a
    // status colour in the footer was uncovered by both.
    var root = document.body;
    if (!root) return 'no-body';
    var tones = [];
    var nodes = root.querySelectorAll('[class*="au-disc-"], [class*="au-banner-"]');
    for (var i = 0; i < nodes.length; i += 1) {
      var matched = String(nodes[i].className).match(/au-(?:disc|banner)-[a-z]+/g);
      if (matched) tones.push(matched.join(' '));
    }
    return tones.join('|') || 'none';
  }

  // Set by the scenarios that record a branch, immediately before the action whose
  // duration matters. See the `elapsed` facet below.
  var submittedAt = 0;
  var settledAt = 0;
  function markSubmit() { submittedAt = Date.now(); settledAt = 0; }

  /**
   * Poll until the card actually shows `marker`, and record WHEN.
   *
   * The first version of the `elapsed` facet was vacuous, and its own mutation test is
   * what proved it: the scenarios did `await wait(700)` and then recorded, so every
   * branch reported ~700ms no matter how long it really took. A planted 900ms
   * address-keyed delay sailed through `elapsed` untouched — the facet was measuring the
   * harness's patience, not the application's behaviour.
   *
   * Polling for the settled state is what makes the number mean something. `settledAt` is
   * the first moment the terminal copy was on screen, so two branches that reach the same
   * words at different times now differ in the one facet built to notice that.
   */
  async function settle(marker, budgetMs) {
    var deadline = Date.now() + (budgetMs || 3000);
    while (Date.now() < deadline) {
      if (cardText().indexOf(marker) !== -1) {
        settledAt = Date.now();
        // A short grace period so late-arriving parts of the same state (a banner
        // rendered on the next tick) are included in the text and tone facets.
        await wait(120);
        return true;
      }
      await wait(20);
    }
    settledAt = Date.now();
    return false;
  }

  /**
   * Attributes that are not text and not colour — the channel four facets could not see.
   *
   * Quinn's mutation is the proof this exists for: a footer link whose VISIBLE TEXT is
   * identical for both branches and whose destination is not.
   *
   *     <router-link :to="submittedEmail.startsWith('second-attempt') ? '/signin' : '/support'">
   *       Contact support
   *     </router-link>
   *
   * `card` and `page` read innerText, `tone` read a class whitelist, `ops` read operation
   * names. All four passed. Registration status was readable straight off the DOM as
   * `href="/signin"` versus `href="/support"`.
   *
   * TWO NORMALISATIONS, both load-bearing. `FormField` generates its id from
   * `Math.random()`, so `id`, `for` and `aria-describedby` differ on EVERY render — left
   * raw, this facet would fail constantly on correct code and be switched off within a
   * week. Ids are collapsed to `<ID>`, which keeps the security-relevant signal (is this
   * field described? is that control disabled?) while discarding the randomness. Email
   * addresses are masked for the same reason the text facets mask them.
   */
  function attributeSignature() {
    var parts = [];
    var nodes = document.body ? document.body.querySelectorAll('*') : [];
    for (var i = 0; i < nodes.length; i += 1) {
      var node = nodes[i];
      // The driver's own output blocks are appended after this runs, but skip them
      // defensively so a future reordering cannot poison the comparison.
      if (node.id === '__results' || node.id === '__records') continue;
      var pairs = [];
      // Sorted, because the DOM makes no promise about attribute ORDER and two renders
      // that differ only in ordering are not a difference a user could ever perceive.
      var names = [];
      for (var a = 0; a < node.attributes.length; a += 1) names.push(node.attributes[a].name);
      names.sort();
      for (var n = 0; n < names.length; n += 1) {
        var attr = names[n];
        var value = String(node.getAttribute(attr));
        // Everything BUT `class`. `/field-[a-z0-9]{7,9}/` is anchored tightly enough that
        // `field-error` and `field-hint` cannot match it, but keeping `class` out of the
        // collapse is what MEDIUM-1 was about and the exclusion stays explicit: two
        // branches differing only in `field-error` (red) versus `field-hint` (muted) must
        // remain a visible difference.
        if (attr !== 'class') value = value.replace(GENERATED_ID, '<ID>');
        value = value.replace(EMAIL_IN_VALUE, '<EMAIL>');
        pairs.push(attr + '=' + value);
      }
      if (pairs.length) parts.push(node.tagName.toLowerCase() + '[' + pairs.join(',') + ']');
    }
    // `document.title` lives in <head>, which this walk never reaches. Signed explicitly
    // rather than left as the one attribute-borne string outside the facet's scope.
    parts.push('title[' + String(document.title).replace(EMAIL_IN_VALUE, '<EMAIL>') + ']');
    return parts.join(' ');
  }

  /**
   * The comparable surface at ONE moment: what the page renders, in words, colour and
   * attributes.
   *
   * Split out of `recordBranch` so the same comparison can be made at moments other than
   * the settled one. `ops` and `elapsed` are deliberately not here — a request sequence and
   * a duration are only meaningful once the interaction has finished.
   */
  function recordSurface(key) {
    record(key + '|card', cardText());
    record(key + '|page', pageText());
    record(key + '|tone', toneSignature());
    record(key + '|attrs', attributeSignature());
  }

  /**
   * The GATE that makes the in-flight window observable.
   *
   * HIGH-2(b) (Quinn): `recordBranch` runs once, after `settle()`, and nothing sampled any
   * earlier state. With the shipped fixtures — which resolved synchronously — the
   * `submitting` state NEVER PAINTED AT ALL, so no facet could ever have seen it. She put
   * an address-keyed status line under the forgot-password form, rendered only while
   * submitting, and both gates stayed green; with 250ms of injected latency, which is what
   * any real network gives, the two branches painted different words.
   *
   * That matters beyond the mutant: `SignInView.vue` and `SignUpView.vue` already ship an
   * `au-note role="status" aria-live="polite"` in that window on EVERY real sign-in, and no
   * facet had ever compared it across branches.
   *
   * A gate rather than an injected delay, deliberately. Chrome runs under
   * `--virtual-time-budget`, so a timer-based fixture would depend on how the fast-forward
   * interleaves with the poll loop. Holding the reply until the scenario releases it is
   * deterministic, and it costs no wall-clock time.
   */
  var gateQueue = [];
  function gated(makeReply) {
    return function (op) {
      return new Promise(function (resolve) {
        gateQueue.push(function () { resolve(makeReply(op)); });
      });
    };
  }
  function releaseGate() {
    var queued = gateQueue;
    gateQueue = [];
    for (var i = 0; i < queued.length; i += 1) queued[i]();
  }

  /**
   * Poll until the form reports itself busy AND the request is genuinely out.
   *
   * Both conditions matter. `aria-busy` alone would be satisfied by the synchronous state
   * flip before `fetch` is called, and `calls.length` alone says nothing about what has
   * been painted. Together they mean: the user is looking at the in-flight state, and the
   * server has not answered.
   */
  async function settleInFlight(budgetMs) {
    var deadline = Date.now() + (budgetMs || 3000);
    while (Date.now() < deadline) {
      if (document.querySelector('form[aria-busy="true"]') && calls.length > 0) return true;
      await wait(20);
    }
    return false;
  }

  function recordBranch(key) {
    record(key + '|card', cardText());
    /**
     * LOW-2 (Sana): the footer lives OUTSIDE `.au-card` (`AuthShell.vue` renders the
     * `#footer` slot after the closing div), so `cardText()` cannot see it. A future edit
     * branching the footer on the address — "Sign in instead" versus "Create an account",
     * exactly the §4c shape — would have passed both existing facets. The whole page is
     * compared as well now.
     */
    record(key + '|page', pageText());
    record(key + '|ops', opSequence());
    record(key + '|tone', toneSignature());
    record(key + '|attrs', attributeSignature());
    /**
     * LOW-3 (Sana): Chrome runs under `--virtual-time-budget`, which fast-forwards
     * timers — so an address-keyed `setTimeout` would render identical text and pass
     * every other facet. It does NOT hide from the clock, though: virtual time advances
     * `Date.now()`, so a delayed branch settles at a measurably different reading.
     * Compared numerically with a tolerance, unlike the string facets.
     *
     * The primary guard on this channel is `tests/authViews.test.ts`, which refuses a
     * timer in these views at all. This is the backstop that catches a delay arriving by
     * some other route.
     */
    record(key + '|elapsed', String(submittedAt && settledAt ? settledAt - submittedAt : -1));
  }

  /**
   * The CSRF bootstrap, asserted wherever a mutation was actually dispatched.
   *
   * Django's CsrfViewMiddleware is active and both GraphQL surfaces declare
   * `*_session_with_csrf`, but the SPA is static files, so nothing ever called
   * `get_token()` and the cookie could not exist — every account mutation was a permanent
   * 403 in a real browser, including on the two views that shipped before this ticket.
   * These two checks are the standing proof that it is seeded, and seeded IN TIME.
   */
  /**
   * Everything a script on this origin can read back, as one string.
   *
   * THREE STORES, not one. `localStorage` was the only one swept, and the sweep was keyed
   * to two token names besides (see `typedSecrets`). Measured on the tree at review time:
   * `sessionStorage` appeared ZERO times across `src/`, `tests/` and `scripts/` — so it
   * was not swept because nothing used it, which is precisely the state in which a new
   * write lands unseen — and `document.cookie` is written by this harness and read by
   * `graphql.ts` and was never swept at all.
   *
   * Built key by key rather than with `JSON.stringify(localStorage)`, for the reason the
   * original sweep gives: that relies on Storage's named properties being own-enumerable,
   * which is true in Chrome and not worth betting a security assertion on. An explicit
   * walk cannot pass by returning "{}".
   */
  function originStorage() {
    var parts = [];
    var i;
    for (i = 0; i < window.localStorage.length; i += 1) {
      var localKey = window.localStorage.key(i);
      parts.push('localStorage[' + localKey + ']=' + window.localStorage.getItem(localKey));
    }
    for (i = 0; i < window.sessionStorage.length; i += 1) {
      var sessionKey = window.sessionStorage.key(i);
      parts.push('sessionStorage[' + sessionKey + ']=' + window.sessionStorage.getItem(sessionKey));
    }
    parts.push('cookie=' + document.cookie);
    return parts.join(';');
  }

  /**
   * What a script on this origin could read after the visitor signed in.
   *
   * The order matters: the POSITIVE CONTROL runs first, because "no secret was found" and
   * "the reader is broken" are the same result, and the second one has to be excluded
   * before the first means anything.
   */
  function credentialStorageChecks() {
    // POSITIVE CONTROL ON THE READER. A marker is planted in the two stores the app does
    // not currently use — the two whose sweep would otherwise be vacuous — and the reader
    // must find both. Removed immediately afterwards, and the removal is asserted, so the
    // canary cannot be mistaken later for something the page wrote.
    var canary = 'sweep-canary-' + SCENARIO;
    window.sessionStorage.setItem('selahcue.sweepCanary', canary);
    document.cookie = 'selahcue_sweep_canary=' + canary + '; path=/';
    var probed = originStorage();
    check('the sweep reads sessionStorage', probed.indexOf('sessionStorage[selahcue.sweepCanary]=' + canary) !== -1,
          'sweep returned: ' + probed);
    check('the sweep reads document.cookie', probed.indexOf('selahcue_sweep_canary=' + canary) !== -1,
          'sweep returned: ' + probed);
    window.sessionStorage.removeItem('selahcue.sweepCanary');
    document.cookie = 'selahcue_sweep_canary=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';

    var stored = originStorage();
    check('the canary is gone before the real sweep', stored.indexOf(canary) === -1,
          'sweep returned: ' + stored);
    check('something WAS stored, so the sweep below is not vacuous',
          stored.indexOf('localStorage[') !== -1 && stored.indexOf('csrftoken') !== -1,
          'sweep returned: ' + stored);

    // THE CHECK THAT MATTERS: the values this scenario actually typed, not a remembered
    // list of names. `typedSecrets` is filled by `typeInto`, so it cannot disagree with
    // what went into the form.
    check('the scenario typed a credential, so the sweep has something to look for',
          typedSecrets.length > 0);
    var leaked = typedSecrets.filter(function (secret) { return stored.indexOf(secret) !== -1; });
    check('nothing the visitor typed is readable from storage on this origin',
          leaked.length === 0,
          'found ' + leaked.length + ' typed secret(s) in: ' + stored);

    // The old name-based rows, kept as a COMPLEMENT rather than as the control. They cover
    // a token this scenario never typed and therefore cannot recognise by value; they are
    // not, and never were, evidence about anything else.
    check('no session token was written to any store on this origin',
          stored.indexOf('sessionToken') === -1 && stored.indexOf('SC-SESSION') === -1,
          'storage held: ' + stored);
  }

  function csrfChecks() {
    if (calls.length === 0) {
      check('no CSRF bootstrap without a GraphQL call', csrfCalls.length === 0,
            'bootstraps=' + csrfCalls.length);
      return;
    }
    check('the CSRF cookie was bootstrapped before the first mutation',
          csrfCalls.length >= 1, 'bootstraps=' + csrfCalls.length);
    // The header on the FIRST call is what proves ordering: a bootstrap issued after the
    // mutation would seed a cookie for next time and leave this request to 403.
    var headers = calls[0].headers || {};
    check('the first mutation carried the CSRF header',
          headers['X-CSRFToken'] === 'harness-csrf-token',
          'headers were: ' + JSON.stringify(headers));
    // Exactly one, not one per request: the cookie set by the bootstrap must be seen and
    // reused, or every page would pay an extra round trip for every action.
    check('the bootstrap happened once, not once per request', csrfCalls.length === 1,
          'bootstraps=' + csrfCalls.length + ' for ' + calls.length + ' calls');
  }

  /**
   * No dead ends (FR-552 / DEC-012), generalised past /verify and /reset.
   *
   * The requirement is written about token failures, but the reason behind it is not
   * specific to tokens: the API deliberately cannot say why something failed, so the
   * client must always offer the next step rather than stopping. Any auth card that
   * reports a failure must therefore carry an actionable control — a form to submit, a
   * button to retry, or a link onward.
   */
  function forwardPathCheck(label) {
    // MEDIUM-1 (Quinn): this used to count `.au-card button, .au-card a, .au-card input`,
    // and EVERY call site is a state where the form is still mounted — so the two text
    // fields satisfied it on their own, whatever else was missing. She hid the submit
    // button and the "Forgot your password?" link whenever a rejection banner was showing,
    // which is a genuine FR-552 dead end: a rejected sign-in card with nothing to press.
    // The suite reported ZERO behavioural failures. Only the shrink guard stopped the run,
    // and it fired for an unrelated reason, reporting something a reader would diagnose as
    // a harness regression.
    //
    // A field you can type into is not a way forward if nothing will accept what you type.
    // What counts now is a control that can actually be ACTUATED — an enabled button, or a
    // link with a real destination — and the message says which was found.
    // AND NOT A CONTROL THAT BELONGS TO A FIELD. Re-planting Quinn's dead end with the
    // first version of this fix showed the geometry checks failing and THIS ONE STILL
    // PASSING, because `FormField.vue` renders an enabled password show/hide toggle inside
    // the card. That is the same proxy she objected to, one element over: revealing what
    // you already typed is not a way out of a state that will not accept it.
    var candidates = document.querySelectorAll('.au-card button:not([disabled])');
    var buttons = 0;
    for (var f = 0; f < candidates.length; f += 1) {
      if (!candidates[f].closest('.form-field')) buttons += 1;
    }
    var links = document.querySelectorAll('.au-card a[href]').length;
    check('a way forward is offered — an enabled button or a real link: ' + label,
          buttons + links > 0,
          'the card rendered ' + buttons + ' actionable button(s) and ' + links +
          ' link(s) outside its fields, so there is nothing to press');
  }

  function type(selector, value) {
    var el = document.querySelector(selector);
    if (!el) return false;
    el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  }

  function submit() {
    var form = document.querySelector('.au-card form');
    if (!form) return false;
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    return true;
  }

  function typeInto(el, value) {
    if (!el) return false;
    // Recorded HERE rather than at each call site, because this is the one place a value
    // enters the page and a per-scenario list would be one more thing to keep in step.
    // Password fields only: a stored address would be a different (and much smaller)
    // question from a stored credential, and banning it would fail a legitimate
    // remember-my-email feature the moment anyone built one.
    if (el.type === 'password' && typeof value === 'string' && value.length > 0 &&
        typedSecrets.indexOf(value) === -1) {
      typedSecrets.push(value);
    }
    el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  }

  /** v-model on a <select> listens for `change`, not `input`. */
  function pick(selector, value) {
    var el = document.querySelector(selector);
    if (!el) return false;
    el.value = value;
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return el.value === value;
  }

  /** v-model on a checkbox listens for `change` too. */
  function tick(selector, value) {
    var el = document.querySelector(selector);
    if (!el) return false;
    el.checked = value;
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  /**
   * Fill the create-account form. `overrides` leaves a field alone when its value is
   * null, which is how the "missing country" and "unticked terms" scenarios produce a
   * form that is complete except for the one thing under test.
   */
  function fillSignup(overrides) {
    var o = overrides || {};
    var texts = document.querySelectorAll('.au-card input[type="text"]');
    var ok = texts.length === 2;
    typeInto(texts[0], o.orgName !== undefined ? o.orgName : 'Grace Community Church');
    typeInto(texts[1], o.displayName !== undefined ? o.displayName : 'Alex Morgan');
    ok = typeInto(document.querySelector('.au-card input[type="email"]'),
                  o.email !== undefined ? o.email : 'pastor@yourchurch.org') && ok;
    // `!== undefined`, not a truthiness test: '' is the "Select a country" option and is
    // exactly what the missing-country scenario needs to set. `|| 'GB'` would have
    // silently filled it in and turned that scenario into a test of nothing.
    ok = pick('.au-card select', o.country !== undefined ? o.country : 'GB') && ok;
    var passwords = document.querySelectorAll('.au-card input[type="password"]');
    ok = passwords.length === 2 && ok;
    var pw = o.password !== undefined ? o.password : 'a-good-passphrase';
    typeInto(passwords[0], pw);
    typeInto(passwords[1], o.confirmPassword !== undefined ? o.confirmPassword : pw);
    if (o.agreeTerms !== false) ok = tick('.au-card input[type="checkbox"]', true) && ok;
    return ok;
  }

  /** Fill the sign-in form. */
  function fillSignIn(email, password) {
    var ok = typeInto(document.querySelector('.au-card input[type="email"]'), email);
    return typeInto(document.querySelector('.au-card input[type="password"]'), password) && ok;
  }

  /**
   * Drive a client-side navigation through the app's OWN router.
   *
   * `history.pushState` plus a synthetic `popstate` was the first attempt and it does not
   * work: the URL changes but vue-router does not re-resolve, so the route guard never
   * runs and a test of the guard silently tests nothing. Going through the router is the
   * only way to exercise `beforeEach` the way a real click does.
   *
   * `__vue_app__` is set on the mount container by Vue's `mount()` in production builds
   * too, so this needs no dev bundle.
   */
  function navigate(path) {
    var container = document.querySelector('#app');
    var app = container && container.__vue_app__;
    var router = app && app.config && app.config.globalProperties.$router;
    if (!router) return false;
    router.push(path).catch(function () {});
    return true;
  }

  // ------------------------------------------------------------------ shared checks --
  /**
   * `options.noPrimaryButton` — a state that legitimately renders no primary button.
   *
   * LOW-1 (Quinn) asked for these checks to stop VANISHING when the button goes missing,
   * and the first attempt at that failed `verify-loading`, which is a spinner with nothing
   * to press and is entirely correct. Guarding on the DOM was the original bug; guarding
   * on nothing is a false alarm. So the expectation is DECLARED by the scenario, and the
   * number of checks is fixed by that declaration rather than by what happens to render.
   *
   * The flag cannot be used to hide a button that went missing, because declaring it
   * asserts the ABSENCE: a state that says it has no primary button and grows one fails
   * just as loudly as one that says it has a button and loses it.
   */
  function universalChecks(options) {
    var expectsButton = !(options && options.noPrimaryButton);
    var text = cardText();

    // The token must be gone from the address bar by the time anything is rendered.
    // A page opened WITHOUT a token has nothing to scrub, so it keeps its query intact
    // (here, the driver's own __scenario) — assert the invariant that actually matters.
    if (HAD_TOKEN) {
      check('token scrubbed from location.search', location.search === '',
            'search was: ' + location.search);
    } else {
      check('no token in location.search', location.search.indexOf('token=') === -1,
            'search was: ' + location.search);
    }
    check('token absent from rendered page text', pageText().indexOf('SC-TESTTOKEN') === -1);

    // No-enumeration: nothing rendered may say whether an address is registered.
    var banned = [
      'already registered', 'already exists', 'no account', 'not found',
      "we've sent", 'we have sent', 'does not exist', "isn't registered",
      'is not registered', 'unknown email', 'no user'
    ];
    var lower = text.toLowerCase();
    for (var i = 0; i < banned.length; i++) {
      check('no enumeration phrase: "' + banned[i] + '"', lower.indexOf(banned[i]) === -1);
    }

    // The site chrome is dropped on these routes (design 2.1).
    check('no site nav rendered', document.querySelector('nav') === null);

    // Exactly one h1, and it is the card title.
    check('exactly one h1', document.querySelectorAll('h1').length === 1,
          'found ' + document.querySelectorAll('h1').length);

    // No stale copy from the superseded gap-fill doc. 86ak120kw corrections 2 and 3.
    check('copy never says 15 minutes', lower.indexOf('15 minute') === -1);
    check('copy never says 8 characters', lower.indexOf('8 character') === -1);
    // 86ak120kw correction 1, and its §5c twin. Neither error may exist on any auth page.
    check('copy never claims an address is taken', lower.indexOf('already have an account with') === -1);

    /*
     * THE RATE-LIMIT CLAIM BAN, READ OFF THE RENDERED PAGE.
     *
     * MEDIUM (Quinn): `tests/authCopy.test.ts` forbids these phrases BY NAME, and scans
     * only `messages.ts`. Appending to the constant at one of its four call sites —
     * `RESEND_RATE_LIMITED + ' for that address'` — leaves the constant clean, ships a page
     * that says it, and passes both gates. A forbidden string is only forbidden where the
     * scanner looks.
     *
     * So this looks at what the page SAYS -- specifically at the DOM subtree that carries
     * the rate-limit message, found by locating the message text in the live document and
     * scanning that element and its container.
     *
     * SCOPED THERE ON PURPOSE, and the first run is why. Scanning the whole page failed on
     * `verify-rate-limited`, on the sentence "If you have already confirmed this address,
     * sign in as normal" -- which is CONDITIONAL, says the same thing whoever is reading it,
     * and is the exact wording `lib/api/account.ts` documents as the safe form. Banning the
     * phrase page-wide is a rule about the wrong thing: the property is that the rate-limit
     * OUTCOME reveals nothing, not that four word-pairs never appear near it.
     *
     * The MESSAGE ELEMENT ITSELF is the span, and not its parent -- widening to the parent
     * put the same conditional sentence back in scope, because the parent of the resend
     * error in `VerifyView` is the template block that also holds the "Already verified?"
     * banner. What this catches is the defect's actual shape: an append at a call site
     * (`RESEND_RATE_LIMITED + ' for that address'`) renders INSIDE the message element,
     * whichever of the four call sites produced it.
     *
     * A leak added as a SIBLING of the message is out of this check's scope and stays the
     * business of the behavioural comparison in EQUIVALENCE_GROUPS/SURFACE_GROUPS, which
     * compares everything the two branches render and needs no phrase list at all. This is
     * a tripwire on the message; that is the boundary.
     *
     * The trigger is the rate-limit copy being ON SCREEN, taken from the same module as the
     * phrases -- not the scenario's name -- so a new rate-limited surface is covered the day
     * it renders that copy rather than the day someone remembers to name it.
     */
    function rateLimitCopyScope() {
      var scope = '';
      var all = document.querySelectorAll('body *');
      for (var m = 0; m < SHARED_COPY.rateLimitMarkers.length; m++) {
        var marker = SHARED_COPY.rateLimitMarkers[m].toLowerCase();
        for (var e = 0; e < all.length; e++) {
          var el = all[e];
          var own = (el.innerText || el.textContent || '').toLowerCase();
          if (own.indexOf(marker) === -1) continue;
          // Innermost only: an ancestor containing the marker also contains the whole card,
          // which is how the page-wide version picked up unrelated conditional copy.
          var deeper = false;
          for (var k = 0; k < el.children.length; k++) {
            var kid = el.children[k];
            if ((kid.innerText || kid.textContent || '').toLowerCase().indexOf(marker) !== -1) {
              deeper = true;
            }
          }
          if (deeper) continue;
          scope += ' ' + own;
        }
      }
      return scope.toLowerCase();
    }

    var rateLimitScope = rateLimitCopyScope();
    if (rateLimitScope.trim() !== '') {
      // Recorded so the Python half can assert this branch was actually reached. A
      // conditional ban that never fires passes exactly like one that fires and holds.
      results.push('PASS [' + SCENARIO + '] RATE-LIMIT STATE SCANNED for address claims');
      for (var c = 0; c < SHARED_COPY.claims.length; c++) {
        check('rate-limit copy claims nothing about the address: "' + SHARED_COPY.claims[c] + '"',
              rateLimitScope.indexOf(SHARED_COPY.claims[c]) === -1,
              'the rendered rate-limit message says "' + SHARED_COPY.claims[c] + '", which ' +
              'tells the caller what the server knows about the address');
      }
    }
    check('no unbacked OAuth affordance (DEC-007 chose email/password)',
          text.indexOf('Continue with Google') === -1 && text.indexOf('Google') === -1);

    csrfChecks();

    // COMPUTED geometry, not just class presence. The auth card overrides UiButton's
    // pill radius from a global stylesheet, and global-vs-scoped rules of equal
    // specificity are decided by injection order — which is not something to assume.
    //
    // LOW-1 (Quinn): these four used to sit inside `if (btn) { … }`, so removing the
    // primary button DROPPED NINE CHECKS across the suite instead of failing one. That is
    // how her FR-552 dead end surfaced as "the suite must not silently shrink" — the right
    // alarm for the wrong reason, pointing a reader at a harness regression. The count is
    // constant now: no button is a FAILURE of the first check and a recorded failure of
    // the other three, not their disappearance.
    var btn = document.querySelector('.au-btn');
    var card = document.querySelector('.au-card');
    if (!expectsButton) {
      check('this state declares no primary button, and has none', !btn,
            'a .au-btn appeared in a state declared to have none');
    } else {
      check('the card offers a primary button', !!btn, 'no .au-btn rendered');
      var btnBox = btn ? btn.getBoundingClientRect() : null;
      check('primary button uses the auth card 12px radius, not the marketing pill',
            !!btn && getComputedStyle(btn).borderRadius === '12px',
            btn ? 'computed: ' + getComputedStyle(btn).borderRadius : 'no button');
      check('primary button clears the 44px touch target',
            !!btnBox && btnBox.height >= 44,
            btnBox ? 'height: ' + btnBox.height : 'no button');
      check('primary button is full width inside the card',
            !!btnBox && !!card &&
            Math.abs(btnBox.width - card.clientWidth +
                     (parseFloat(getComputedStyle(card).paddingLeft) +
                      parseFloat(getComputedStyle(card).paddingRight))) < 2,
            btnBox ? 'button ' + btnBox.width : 'no button');
    }

    // The card must not be full-bleed — the surrounding --sc-base margin is what marks
    // it as a focused task (design 13). Same treatment as the button geometry above: a
    // missing card is a failure, not a vanished check.
    check('card is not full-bleed',
          !!card && card.getBoundingClientRect().width < window.innerWidth,
          card ? 'card ' + card.getBoundingClientRect().width + ' vs viewport ' +
                 window.innerWidth
               : 'no .au-card rendered');
  }

  function has(text, needle) { return text.indexOf(needle) !== -1; }

  /**
   * The password typed by BOTH halves of the sign-in enumeration pair.
   *
   * `login` answers `UNAUTHENTICATED` for an unknown address and for a wrong password
   * alike, so from the client's side the two scenarios differ in exactly one input: the
   * address. Shared here rather than written twice so they cannot drift apart.
   */
  var REJECTED_PASSWORD = 'whatever-they-typed';

  // ---------------------------------------------------------------------- scenarios --
  var SCENARIOS = {
    'verify-loading': async function () {
      // 400ms, not the 120 this started at. The V1 state is pinned by the scripted reply,
      // which is a promise that NEVER resolves — so a longer wait cannot let the page move
      // on and weaken the check. The short wait was implicitly asserting how fast a lazy
      // route chunk mounts, which is not what this scenario is about and made it flaky.
      await wait(400);
      var text = cardText();
      check('V1 title', has(text, 'Verifying your email address'));
      check('V1 body', has(text, 'Keep this tab open'));
      var live = document.querySelector('[role="status"][aria-live="polite"]');
      check('V1 announces politely', live !== null);
      check('V1 shows a progress track', document.querySelector('.au-progress-fill') !== null);
      check('V1 footer offers sign in', has(pageText(), 'Taking too long?'));
      check('V1 dispatched exactly one mutation', calls.length === 1, 'calls=' + calls.length);
      check('V1 called verifyEmail', calls.length > 0 && calls[0].op === 'VerifyEmail');
      check('token sent as a variable, not inlined in the query',
            calls.length > 0 && calls[0].variables.token === 'SC-TESTTOKEN-verify' &&
            calls[0].query.indexOf('mutation VerifyEmail($token') !== -1);
      // V1 is a spinner: there is nothing to press yet, and that is correct. Declared,
      // so the geometry checks below still RUN and still count.
      universalChecks({ noPrimaryButton: true });
    },

    'verify-success': async function () {
      await wait(800);
      var text = cardText();
      check('V2 title', has(text, 'Email address verified'));
      check('V2 body mentions the account is active', has(text, 'your SelahCue account is active'));
      check('V2 primary CTA', has(text, 'Continue to sign in'));
      check('V2 never-blank banner present',
            has(text, "You don't need an account to run SelahCue"));
      check('V2 banner explains offline presentation', has(text, 'Live presentation works offline'));
      check('V2 success disc', document.querySelector('.au-disc-success') !== null);
      check('V2 focus moved to the heading', document.activeElement === document.querySelector('h1'));
      universalChecks();
    },

    'verify-invalid': async function () {
      await wait(800);
      var text = cardText();
      check('V3 title', has(text, "This verification link didn't work"));
      // Names all three causes without claiming which — the API cannot tell us.
      check('V3 names expiry as a possible cause', has(text, 'may have expired'));
      check('V3 names reuse as a possible cause', has(text, 'already been used'));
      check('V3 names mistyping as a possible cause', has(text, 'copied incompletely'));
      check('V3 does NOT assert expiry (V4 is unreachable today)',
            !has(text, 'has expired') && !has(text, 'expire 24 hours after'));
      check('V3 offers a resend field', document.querySelector('input[type="email"]') !== null);
      check('V3 email field has autocomplete',
            (document.querySelector('input[type="email"]') || {}).getAttribute &&
            document.querySelector('input[type="email"]').getAttribute('autocomplete') === 'email');
      check('V3 resend CTA', has(text, 'Send a new verification link'));
      check('V3 already-verified banner', has(text, 'Already verified? Just sign in'));
      check('V3 danger disc', document.querySelector('.au-disc-danger') !== null);
      universalChecks();
    },

    'verify-missing': async function () {
      await wait(500);
      var text = cardText();
      check('V6 title', has(text, 'This page needs a verification link'));
      check('V6 body points at the email', has(text, 'Open the link in the email'));
      check('V6 offers an email field', document.querySelector('input[type="email"]') !== null);
      check('V6 CTA', has(text, 'Send a verification link'));
      // Not an error, so not red.
      check('V6 uses the neutral disc, not the danger disc',
            document.querySelector('.au-disc-neutral') !== null &&
            document.querySelector('.au-disc-danger') === null);
      check('V6 made no API call at all', calls.length === 0, 'calls=' + calls.length);
      universalChecks();
    },

    'verify-unreachable': async function () {
      await wait(800);
      var text = cardText();
      // A transport failure must NOT be reported as a dead link.
      check('transport failure does not claim the link is dead',
            !has(text, "This verification link didn't work"));
      check('transport failure names the connection', has(text, "couldn't reach SelahCue"));
      check('transport failure reassures the link survives', has(text, 'Your link still works'));
      check('transport failure offers a retry', has(text, 'Try again'));
      universalChecks();
    },

    'verify-resend': async function () {
      await wait(600);
      check('starts on the merged failure state', has(cardText(), "This verification link didn't work"));
      check('typed an email', type('input[type="email"]', 'pastor@yourchurch.org'));
      await wait(50);
      check('submitted the resend form', submit());
      await wait(600);
      var text = cardText();
      check('V5 title', has(text, 'Check your inbox'));
      // Load-bearing for no-enumeration: conditional, never a direct claim.
      check('V5 phrasing is conditional ("If ... has a SelahCue account")',
            has(text, 'If pastor@yourchurch.org has a SelahCue account'));
      check('V5 states the 24 hour TTL', has(text, 'expires in 24 hours'));
      check('V5 explains only the newest link works', has(text, 'Only the newest link works'));
      var resendCall = calls.filter(function (c) { return c.op === 'ResendVerification'; })[0];
      check('resend dispatched a mutation', !!resendCall);
      // Pinned against account_schema.py:180. The field is `resendVerificationEmail`, NOT
      // `resendVerification` — it does not follow requestPasswordReset's shorter shape,
      // and a wrong name here fails with the same VALIDATION_FAILED as a dead link, which
      // is exactly the kind of mistake that hides.
      check('resend asks for the real field name resendVerificationEmail',
            !!resendCall && resendCall.query.indexOf('resendVerificationEmail(email: $email)') !== -1,
            'query was: ' + (resendCall ? resendCall.query : 'none'));
      check('resend selects only { accepted }, matching ResendVerificationPayload',
            !!resendCall && /resendVerificationEmail\(email: \$email\)\s*\{\s*accepted\s*\}/.test(resendCall.query),
            'query was: ' + (resendCall ? JSON.stringify(resendCall.query) : 'none'));
      check('resend sent the email as a variable',
            !!resendCall && resendCall.variables.email === 'pastor@yourchurch.org');
      universalChecks();
    },

    'verify-rate-limited': async function () {
      await wait(600);
      check('typed an email', type('input[type="email"]', 'pastor@yourchurch.org'));
      await wait(50);
      check('submitted the resend form', submit());
      await wait(600);
      var text = cardText();
      check('a rate-limited resend does NOT show the sent state', !has(text, 'Check your inbox'));
      check('a rate-limited resend says so', has(text, 'Too many requests'));
      check('a rate-limited resend tells the user to wait', has(text, 'Wait a few minutes'));
      // The per-address budget is spent BEFORE the account is looked up, so a rate limit
      // says nothing about whether the address exists. The copy must not imply it does.
      var lower = text.toLowerCase();
      check('rate-limit copy never implies the account exists',
            lower.indexOf('this account') === -1 && lower.indexOf('your account') === -1 &&
            lower.indexOf('for this address') === -1);
      check('a rate-limited resend stays on the recovery form',
            document.querySelector('input[type="email"]') !== null);
      forwardPathCheck('a rate-limited resend');
      universalChecks();
    },

    'verify-resend-fails': async function () {
      await wait(600);
      check('typed an email', type('input[type="email"]', 'pastor@yourchurch.org'));
      await wait(50);
      check('submitted the resend form', submit());
      await wait(600);
      var text = cardText();
      // The button must never claim to have sent an email that was not sent — which is
      // exactly today's situation, since the mutation does not exist yet.
      check('a failed resend does NOT show the sent state', !has(text, 'Check your inbox'));
      check('a failed resend says so honestly', has(text, "couldn't send"));
      check('a failed resend stays on the recovery form',
            document.querySelector('input[type="email"]') !== null);
      forwardPathCheck('a resend that failed');
      universalChecks();
    },

    'verify-bad-email': async function () {
      await wait(600);
      check('typed a malformed address', type('input[type="email"]', 'not-an-email'));
      await wait(50);
      check('submitted', submit());
      await wait(300);
      check('malformed address is caught on the field', has(cardText(), 'Enter a valid email address'));
      check('no API call was made for a malformed address',
            calls.filter(function (c) { return c.op === 'ResendVerification'; }).length === 0);
      var input = document.querySelector('input[type="email"]');
      check('the field is still on screen to be corrected', input !== null);
      check('errored field is marked invalid', !!input && input.getAttribute('aria-invalid') === 'true');
      check('errored field points at its message', !!input && !!input.getAttribute('aria-describedby'));
      universalChecks();
    },

    // ------------------------------------------------------------------------ reset --
    'reset-form': async function () {
      await wait(500);
      var text = cardText();
      check('R1 title', has(text, 'Choose a new password'));
      check('R1 hint states the real rule', has(text, 'At least 10 characters'));
      check('R1 has two password fields',
            document.querySelectorAll('input[type="password"]').length === 2);
      check('R1 password fields use new-password autocomplete',
            Array.prototype.every.call(document.querySelectorAll('input[type="password"]'),
              function (i) { return i.getAttribute('autocomplete') === 'new-password'; }));
      check('R1 signs-out-everywhere banner', has(text, 'This signs you out everywhere'));
      check('R1 promises devices keep presenting', has(text, 'keep presenting offline'));
      // The reset token is opaque; nothing here knows whose account it is.
      check('R1 never claims to know the account', !has(text, 'resetting the password for'));
      check('R1 made no API call on arrival', calls.length === 0, 'calls=' + calls.length);
      var toggle = document.querySelector('.password-toggle');
      check('password Show toggle exposes pressed state', toggle.getAttribute('aria-pressed') === 'false');
      check('password Show toggle has an accessible name', !!toggle.getAttribute('aria-label'));
      universalChecks();
    },

    // THE correctness case from the ClickUp note.
    'reset-short-password': async function () {
      await wait(500);
      var fields = document.querySelectorAll('input[type="password"]');
      fields[0].value = 'abc123';
      fields[0].dispatchEvent(new Event('input', { bubbles: true }));
      fields[1].value = 'abc123';
      fields[1].dispatchEvent(new Event('input', { bubbles: true }));
      await wait(50);
      check('submitted a 6-character password', submit());
      await wait(500);
      var text = cardText();

      // If this ever regresses, the user is told their link is dead when it is fine.
      check('NO mutation was dispatched for a 6-character password',
            calls.length === 0, 'calls=' + calls.length + ' ' + JSON.stringify(calls.map(function (c) { return c.op; })));
      check('R2 shows the length error', has(text, 'Password must be at least 10 characters'));
      check('R2 does NOT claim the link is dead', !has(text, "This reset link didn't work"));
      check('R2 keeps the user on the form',
            document.querySelectorAll('input[type="password"]').length === 2);
      var first = document.querySelectorAll('input[type="password"]')[0];
      check('errored password field is marked invalid', first.getAttribute('aria-invalid') === 'true');
      check('errored password field points at its message', !!first.getAttribute('aria-describedby'));
      universalChecks();
    },

    'reset-whitespace-password': async function () {
      await wait(500);
      var fields = document.querySelectorAll('input[type="password"]');
      var spaces = '            ';
      fields[0].value = spaces; fields[0].dispatchEvent(new Event('input', { bubbles: true }));
      fields[1].value = spaces; fields[1].dispatchEvent(new Event('input', { bubbles: true }));
      await wait(50);
      submit();
      await wait(500);
      // Long enough on length alone, but _validate_password's `not password.strip()`
      // rejects it with the same VALIDATION_FAILED — the second way to be wrongly told
      // your link is dead.
      check('NO mutation dispatched for an all-whitespace password',
            calls.length === 0, 'calls=' + calls.length);
      check('all-whitespace password is explained', has(cardText(), 'more than spaces'));
      check('all-whitespace does NOT claim the link is dead',
            !has(cardText(), "This reset link didn't work"));
      universalChecks();
    },

    'reset-mismatch': async function () {
      await wait(500);
      var fields = document.querySelectorAll('input[type="password"]');
      fields[0].value = 'a-good-passphrase'; fields[0].dispatchEvent(new Event('input', { bubbles: true }));
      fields[1].value = 'a-different-one';   fields[1].dispatchEvent(new Event('input', { bubbles: true }));
      await wait(50);
      submit();
      await wait(500);
      check('NO mutation dispatched for mismatched passwords', calls.length === 0, 'calls=' + calls.length);
      check('R2 shows the mismatch error', has(cardText(), 'Both passwords must match'));
      universalChecks();
    },

    'reset-success': async function () {
      await wait(500);
      var fields = document.querySelectorAll('input[type="password"]');
      fields[0].value = 'a-good-passphrase'; fields[0].dispatchEvent(new Event('input', { bubbles: true }));
      fields[1].value = 'a-good-passphrase'; fields[1].dispatchEvent(new Event('input', { bubbles: true }));
      await wait(50);
      submit();
      await wait(600);
      var text = cardText();
      check('R6 title', has(text, 'Password updated'));
      check('R6 explains the global sign-out', has(text, 'every other session on this account has been signed out'));
      check('R6 devices-keep-presenting banner', has(text, 'Your devices keep presenting'));
      check('R6 primary CTA', has(text, 'Continue to sign in'));
      check('exactly one mutation dispatched', calls.length === 1, 'calls=' + calls.length);
      check('it was confirmPasswordReset', calls[0].op === 'ConfirmPasswordReset');
      check('token and password sent under input',
            calls[0].variables.input && calls[0].variables.input.token === 'SC-TESTTOKEN-reset' &&
            calls[0].variables.input.newPassword === 'a-good-passphrase');
      check('the password is gone from the rendered page',
            pageText().indexOf('a-good-passphrase') === -1);
      universalChecks();
    },

    'reset-invalid': async function () {
      await wait(500);
      var fields = document.querySelectorAll('input[type="password"]');
      fields[0].value = 'a-good-passphrase'; fields[0].dispatchEvent(new Event('input', { bubbles: true }));
      fields[1].value = 'a-good-passphrase'; fields[1].dispatchEvent(new Event('input', { bubbles: true }));
      await wait(50);
      submit();
      await wait(600);
      var text = cardText();
      check('R4 title', has(text, "This reset link didn't work"));
      check('R4 states the 1 hour TTL', has(text, 'Reset links last 1 hour'));
      check('R4 states single use', has(text, 'work once'));
      check('R4 does NOT assert expiry (R5 is unreachable today)', !has(text, 'has expired'));
      check('R4 reassures the password is unchanged', has(text, 'Your password has not changed'));
      check('R4 offers a fresh link', has(text, 'Send a new reset link'));
      check('R4 offers an email field', document.querySelector('input[type="email"]') !== null);
      universalChecks();
    },

    /*
     * PASSWORD_INVALID, rendered.
     *
     * The client-side guard means this page never sends a password it can itself reject,
     * so the only way to reach this state in the wild is a password the SERVER refuses and
     * the client does not — which is precisely the case where the client cannot say why.
     * The three negatives below are the whole finding: before this branch existed,
     * PASSWORD_INVALID classified as UNKNOWN and the page rendered R7, telling the user
     * something had gone wrong on our side about a failure that is permanent until they
     * type something different.
     */
    'reset-password-invalid': async function () {
      await wait(500);
      var fields = document.querySelectorAll('input[type="password"]');
      fields[0].value = 'a-good-passphrase'; fields[0].dispatchEvent(new Event('input', { bubbles: true }));
      fields[1].value = 'a-good-passphrase'; fields[1].dispatchEvent(new Event('input', { bubbles: true }));
      await wait(50);
      submit();
      await wait(600);
      var text = cardText();

      // The premise: the client passed this password, so the rejection really did come
      // from the server. Without it every assertion below could be satisfied by a page
      // that never made the call.
      check('the mutation was dispatched (the client did not reject this password)',
            calls.length === 1 && calls[0].op === 'ConfirmPasswordReset',
            'calls=' + JSON.stringify(calls.map(function (c) { return c.op; })));

      check('PASSWORD_INVALID does NOT show R4 — the link was live, or the server could ' +
            'not have reached the password check',
            !has(text, "This reset link didn't work"));
      check('PASSWORD_INVALID does NOT show R7 — nothing went wrong on our side',
            !has(text, "We couldn't update your password"));
      check('PASSWORD_INVALID does NOT claim success', !has(text, 'Password updated'));

      check('the password is named as the problem', has(text, "That password wasn't accepted"));
      check('the link is stated to still work', has(text, 'this reset link still works'));
      check('the password is stated unchanged', has(text, 'Your password has not been changed'));

      var banner = document.querySelector('.au-banner-danger');
      check('the rejection is announced', !!banner && banner.getAttribute('role') === 'alert');
      // `PASSWORD_INVALID` carries no policy detail on purpose (`graphql/errors.py:28`) and
      // the client already enforced the rules it knows, so any number here would be
      // invented. The field hint below still says "At least 10 characters" — that is the
      // rule, not a claim about what failed — which is why this is scoped to the banner.
      check('the banner invents no rule the server did not send',
            !!banner && !/\d+\s*character/i.test(banner.innerText || banner.textContent || ''));

      check('the user is left on the form, able to type a different password',
            document.querySelectorAll('input[type="password"]').length === 2 &&
            !document.querySelectorAll('input[type="password"]')[0].disabled);
      check('the plaintext password is not rendered anywhere',
            pageText().indexOf('a-good-passphrase') === -1);
      forwardPathCheck('password rejected by the server');
      universalChecks();
    },

    'reset-unreachable': async function () {
      await wait(500);
      var fields = document.querySelectorAll('input[type="password"]');
      fields[0].value = 'a-good-passphrase'; fields[0].dispatchEvent(new Event('input', { bubbles: true }));
      fields[1].value = 'a-good-passphrase'; fields[1].dispatchEvent(new Event('input', { bubbles: true }));
      await wait(50);
      submit();
      await wait(600);
      var text = cardText();
      // The difference between R7 and R4 is the whole point of classifying NETWORK.
      check('R7 shown, not R4', !has(text, "This reset link didn't work"));
      check('R7 banner title', has(text, "We couldn't update your password"));
      check('R7 states the password is unchanged', has(text, 'Your password has not been changed'));
      check('R7 states the link still works', has(text, 'this link still works until it expires'));
      check('R7 banner is announced', document.querySelector('.au-banner-danger[role="alert"]') !== null);
      check('R7 relabels the primary action', has(text, 'Try again'));
      universalChecks();
    },

    'reset-missing': async function () {
      await wait(500);
      var text = cardText();
      check('no-token state title', has(text, 'This page needs a reset link'));
      check('no-token state states the 1 hour TTL', has(text, 'last 1 hour'));
      check('no-token state offers an email field',
            document.querySelector('input[type="email"]') !== null);
      check('no-token state uses the neutral disc, not danger',
            document.querySelector('.au-disc-neutral') !== null &&
            document.querySelector('.au-disc-danger') === null);
      check('no-token state made no API call', calls.length === 0, 'calls=' + calls.length);
      universalChecks();
    },

    'reset-fresh-link': async function () {
      await wait(500);
      var fields = document.querySelectorAll('input[type="password"]');
      fields[0].value = 'a-good-passphrase'; fields[0].dispatchEvent(new Event('input', { bubbles: true }));
      fields[1].value = 'a-good-passphrase'; fields[1].dispatchEvent(new Event('input', { bubbles: true }));
      await wait(50);
      submit();
      await wait(600);
      check('reached the merged failure state', has(cardText(), "This reset link didn't work"));
      check('typed an email', type('input[type="email"]', 'pastor@yourchurch.org'));
      await wait(50);
      check('requested a fresh link', submit());
      await wait(600);
      var text = cardText();
      check('sent state title', has(text, 'Check your inbox'));
      check('sent state phrasing is conditional',
            has(text, 'If pastor@yourchurch.org has a SelahCue account'));
      check('sent state states the 1 hour TTL, not 24', has(text, 'expires in 1 hour'));
      check('called requestPasswordReset (a mutation that really exists)',
            calls.some(function (c) { return c.op === 'RequestPasswordReset'; }));
      universalChecks();
    },

    // ================================================================= sign in ==
    'signin-form': async function () {
      await wait(400);
      var text = cardText();
      check('title', has(text, 'Sign in to SelahCue'));
      check('two fields', document.querySelectorAll('.au-card input').length === 2);
      check('email field uses email autocomplete',
            document.querySelector('input[type="email"]').getAttribute('autocomplete') === 'email');
      // `current-password`, not `new-password`: a password manager must offer the SAVED
      // credential here, not offer to generate a fresh one.
      check('password field uses current-password autocomplete',
            document.querySelector('input[type="password"]').getAttribute('autocomplete') === 'current-password');
      check('offers the forgot-password route', !!document.querySelector('a[href="/forgot-password"]'));
      check('offers the create-account route', !!document.querySelector('a[href="/signup"]'));
      check('never-blank banner present', has(text, "You don't need an account to run SelahCue"));
      check('banner says presentation works offline', has(text, 'works offline'));
      // The simulated view routed to /account after 800ms with no backend at all.
      check('no unbacked Google button', !has(text, 'Google'));
      check('made no API call on arrival', calls.length === 0, 'calls=' + calls.length);
      check('password Show toggle has an accessible name',
            !!document.querySelector('.password-toggle').getAttribute('aria-label'));
      check('password Show toggle exposes pressed state',
            document.querySelector('.password-toggle').getAttribute('aria-pressed') === 'false');
      universalChecks();
    },

    'signin-validation': async function () {
      await wait(400);
      check('typed a malformed address', fillSignIn('not-an-email', ''));
      await wait(50);
      check('submitted', submit());
      await wait(400);
      var text = cardText();
      check('malformed address is caught on the field', has(text, 'Enter a valid email address'));
      check('empty password is caught on the field', has(text, 'Enter your password'));
      // The important half: an invalid form never reaches the API, so no rate-limit
      // budget is spent and no server error has to be attributed to the wrong cause.
      check('NO login was dispatched for an invalid form', calls.length === 0, 'calls=' + calls.length);
      var input = document.querySelector('input[type="email"]');
      check('errored field is marked invalid', input.getAttribute('aria-invalid') === 'true');
      check('errored field points at its message', !!input.getAttribute('aria-describedby'));
      forwardPathCheck('sign-in field validation');
      universalChecks();
    },

    'signin-expired': async function () {
      await wait(400);
      var text = cardText();
      // Arriving here because a session ended is not an error, and the copy says what to
      // do rather than what went wrong.
      check('explains why they are here', has(text, "You've been signed out"));
      check('reassures that devices kept presenting', has(text, 'kept presenting'));
      check('the form is still there to use', document.querySelectorAll('.au-card input').length === 2);
      check('made no API call', calls.length === 0, 'calls=' + calls.length);
      universalChecks();
    },

    'signin-rejected-unknown': async function () {
      await wait(400);
      // ONE VARIABLE. The pair differs in the ADDRESS and in nothing else — the password
      // string is shared, because the property under test is "the render does not vary
      // with who the user is", and a second difference in the fixture would show up as a
      // difference in the comparison and have to be normalised away. Normalising is where
      // leaks hide (see MEDIUM-2 on the email mask); holding the variable constant is
      // free. Signing the `value` attribute is what made this visible.
      fillSignIn('nobody-has-this-address@nowhere.test', REJECTED_PASSWORD);
      await wait(50);
      // BEFORE SUBMIT. Cody's helper extraction and Sana's computed placeholder both lived
      // here: a bound attribute keyed on the address the user is typing, on screen the
      // whole time the form is up, and gone by the time the settled state is recorded.
      recordSurface('signin-rejected-unknown-presubmit');
      markSubmit();
      submit();
      // IN FLIGHT. The reply is gated, so this is a real paint of the submitting state.
      check('the in-flight state was reached', await settleInFlight());
      recordSurface('signin-rejected-unknown-inflight');
      releaseGate();
      check('the rejection settled', await settle('Invalid email or password'));
      var text = cardText();
      check('rejection banner shown', has(text, 'Invalid email or password'));
      check('rejection is announced', !!document.querySelector('.au-banner-danger[role="alert"]'));
      check('the password field was cleared',
            document.querySelector('input[type="password"]').value === '');
      check('the email was kept for correction',
            document.querySelector('input[type="email"]').value !== '');
      forwardPathCheck('rejected credentials');
      recordBranch('signin-rejected-unknown');
      universalChecks();
    },

    'signin-rejected-wrong-password': async function () {
      await wait(400);
      // A REAL address with a wrong password. The service answers identically to the
      // unknown-address case above and pads the timing; this asserts the client does not
      // undo that. Compared in EQUIVALENCE_GROUPS.
      fillSignIn('pastor@yourchurch.org', REJECTED_PASSWORD);
      await wait(50);
      recordSurface('signin-rejected-wrong-password-presubmit');
      markSubmit();
      submit();
      check('the in-flight state was reached', await settleInFlight());
      recordSurface('signin-rejected-wrong-password-inflight');
      releaseGate();
      check('the rejection settled', await settle('Invalid email or password'));
      check('rejection banner shown', has(cardText(), 'Invalid email or password'));
      recordBranch('signin-rejected-wrong-password');
      forwardPathCheck('rejected credentials (wrong password)');
      universalChecks();
    },

    'signin-unreachable': async function () {
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(700);
      var text = cardText();
      // A dropped connection is not a wrong password. Saying so would send someone to
      // reset a password that was never the problem.
      check('a transport failure is NOT reported as bad credentials',
            !has(text, 'Invalid email or password'));
      check('it names the connection', has(text, "couldn't reach SelahCue"));
      check('it says the account is unaffected', has(text, 'account is unaffected'));
      check('the form is still there to retry', document.querySelectorAll('.au-card input').length === 2);
      forwardPathCheck('unreachable API');
      universalChecks();
    },

    'signin-unverified': async function () {
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(700);
      var text = cardText();
      check('POLICY_DENIED gets its own state', has(text, "isn't ready to sign in yet"));
      // `login` raises POLICY_DENIED for an unverified email AND for a deactivated
      // account and does not say which, so the copy must not assert either.
      check('names verification as a possible cause', has(text, 'verified'));
      check('names deactivation as a possible cause', has(text, 'deactivated'));
      check('does NOT assert which applied', !has(text, 'has not been verified'));
      check('it is not the credential rejection', !has(text, 'Invalid email or password'));
      check('FR-552: a way forward is offered', has(text, 'Send a verification link'));
      forwardPathCheck('unverified account');
      universalChecks();
    },

    'signin-resend': async function () {
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(700);
      check('reached the not-ready state', has(cardText(), "isn't ready to sign in yet"));
      var button = Array.prototype.filter.call(
        document.querySelectorAll('.au-card button'),
        function (b) { return b.textContent.indexOf('Send a verification link') !== -1; })[0];
      check('the resend control exists', !!button);
      if (button) button.click();
      await wait(700);
      var text = cardText();
      check('sent state title', has(text, 'Check your inbox'));
      // Conditional even here. The correct password proves the ACCOUNT exists, but
      // `resendVerificationEmail` answers the same for an already-verified account as for
      // one awaiting verification, and this state is also reachable when the cause was
      // deactivation — in which case nothing was sent.
      check('phrasing stays conditional',
            has(text, 'has a SelahCue account waiting to be verified'));
      check('states the 24 hour TTL', has(text, 'expires in 24 hours'));
      var resend = calls.filter(function (c) { return c.op === 'ResendVerification'; })[0];
      check('dispatched the real resend mutation', !!resend);
      check('asked for the real field name',
            !!resend && resend.query.indexOf('resendVerificationEmail(email: $email)') !== -1);
      universalChecks();
    },

    'signin-success': async function () {
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(1200);
      var login = calls.filter(function (c) { return c.op === 'Login'; })[0];
      check('dispatched Login', !!login);
      check('credentials went under input, as LoginInput declares',
            !!login && login.variables.input &&
            login.variables.input.email === 'pastor@yourchurch.org' &&
            login.variables.input.password === 'a-good-passphrase');
      // THE session-handling control. `_set_session_cookie` runs in the resolver body, so
      // the HttpOnly cookie is set whether or not the field is selected; asking for it
      // would copy a credential the server put out of JavaScript's reach back into the JS
      // heap, the response body and every devtools/HAR capture, for nothing.
      check('the login document does NOT select sessionToken',
            !!login && login.query.indexOf('sessionToken') === -1,
            'query was: ' + (login ? login.query : 'none'));
      check('the password is gone from the rendered page',
            pageText().indexOf('a-good-passphrase') === -1);
      check('landed on the account route', location.pathname === '/account',
            'pathname: ' + location.pathname);
      // The guard asks the server rather than trusting the hint it just wrote.
      check('the route guard probed the server', calls.some(function (c) { return c.op === 'AccountViewer'; }));
      // No token AND no credential in storage, anywhere. The hint is metadata only.
      credentialStorageChecks();
      check('the stored hint carries only role, org and expiry',
            Object.keys(JSON.parse(window.localStorage.getItem('selahcue.session') || '{}'))
              .sort().join(',') === 'expiresAt,orgId,role');
      csrfChecks();
    },

    'signin-next-honoured': async function () {
      // The whole round trip: the guard writes `?next=`, sign-in reads it back through
      // `safeNextPath`, and the visitor lands where they were going. `/support` is a real
      // route that needs no session, so this measures the redirect and nothing else.
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(1500);
      check('a sanitised ?next= is honoured', location.pathname === '/support',
            'pathname: ' + location.pathname);
      check('the page it landed on has content', cardText().length > 0 ||
            pageText().replace(/\s+/g, ' ').trim().length > 40,
            'the destination rendered nothing');
      // NOT `universalChecks()`: that asserts the bare-auth chrome (no site nav, exactly
      // one h1), and this scenario deliberately ends on an ordinary marketing route.
      csrfChecks();
    },

    'signin-next-hostile': async function () {
      // The open-redirect guard, asserted AT ITS CALL SITE rather than only in
      // `redirect.test.ts`. `?next=https://evil.example/pay` is the attack the module's
      // header describes: sign in on the real SelahCue with the real padlock, land on a
      // page you have every reason to trust.
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(1500);
      check('an off-site ?next= is refused and the default is used',
            location.pathname === '/account', 'pathname: ' + location.pathname);
      check('the browser never left this origin', location.hostname === '127.0.0.1',
            'host: ' + location.host);
      csrfChecks();
    },

    'signin-next-unmatched': async function () {
      // MEDIUM-4 (Cody): `?next=/does-not-exist` used to resolve with ZERO matched
      // components and render a blank page — a dead end after a SUCCESSFUL sign-in,
      // reachable from a link. The router now has a catch-all, so the destination is a
      // real page with a way onward.
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(1500);
      check('an unmatched ?next= lands somewhere with content',
            has(pageText(), "We couldn't find that page"),
            'page said: ' + pageText().replace(/\s+/g, ' ').slice(0, 120));
      check('and offers a way forward',
            document.querySelectorAll('a[href="/"], a[href="/support"]').length > 0,
            'no onward link rendered');
      csrfChecks();
    },

    'session-lifecycle': async function () {
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(1200);
      check('signed in and landed on /account', location.pathname === '/account',
            'pathname: ' + location.pathname);
      check('the navbar switched to the signed-in controls', has(pageText(), 'Sign out'));

      var signOut = Array.prototype.filter.call(
        document.querySelectorAll('button'),
        function (b) { return b.textContent.trim().indexOf('Sign out') === 0; })[0];
      check('a sign-out control exists', !!signOut);
      if (signOut) signOut.click();
      await wait(1000);

      check('sign-out revoked the session server-side',
            calls.some(function (c) { return c.op === 'Logout'; }));
      check('the local hint was cleared',
            window.localStorage.getItem('selahcue.session') === null,
            'still held: ' + window.localStorage.getItem('selahcue.session'));
      check('left the account route', location.pathname === '/');

      // AND THE PART THAT MATTERS: the protected route is unreachable afterwards.
      check('drove a real client-side navigation', navigate('/account'));
      await wait(1200);
      check('a protected route now redirects to sign in', location.pathname === '/signin',
            'pathname: ' + location.pathname);
      check('and says why', has(pageText(), "You've been signed out"));
      csrfChecks();
    },

    'signout-failure': async function () {
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(1200);
      var signOut = Array.prototype.filter.call(
        document.querySelectorAll('button'),
        function (b) { return b.textContent.trim().indexOf('Sign out') === 0; })[0];
      if (signOut) signOut.click();
      await wait(1000);
      // The cookie is HttpOnly: only the server can delete it, and it does that by
      // answering the mutation. A failed logout means the session is STILL LIVE, so
      // painting "signed out" over it would be the most consequential lie in this UI —
      // on what is often a shared church office PC.
      check('a failed sign-out says so', has(pageText(), "couldn't sign you out"));
      check('a failed sign-out does NOT clear the local hint',
            window.localStorage.getItem('selahcue.session') !== null);
      check('a failed sign-out leaves the signed-in controls up', has(pageText(), 'Sign out'));
      check('a failed sign-out does not navigate away', location.pathname === '/account',
            'pathname: ' + location.pathname);
    },

    // ========================================================== create account ==
    'signup-form': async function () {
      await wait(400);
      var text = cardText();
      check('title', has(text, 'Create your SelahCue account'));
      check('explains one account per church', has(text, 'One account per church'));
      check('hint states the real rule', has(text, 'At least 10 characters'));
      // 86ak120kw correction 2: the handoff asks for 8 + complexity; the API is 10,
      // length only. universalChecks() also bans the "8 characters" string outright.
      check('does not ask for an uppercase letter', !has(text, 'uppercase'));
      check('does not ask for a number', !has(text, 'one number'));
      // §4b's four-segment strength meter is not built: there is no complexity policy for
      // it to depict, so it would teach a rule the server does not enforce.
      check('no strength meter is drawn', !has(text, 'Weak') && !has(text, 'Strong'));
      check('collects the country the API requires', !!document.querySelector('.au-card select'));
      check('the country control is labelled',
            !!document.querySelector('label[for="signup-country"]'));
      check('the country control offers the full ISO list',
            document.querySelectorAll('.au-card select option').length > 200,
            'options: ' + document.querySelectorAll('.au-card select option').length);
      check('collects an organisation name with the right autocomplete',
            document.querySelectorAll('.au-card input[type="text"]')[0]
              .getAttribute('autocomplete') === 'organization');
      check('both password fields use new-password autocomplete',
            Array.prototype.every.call(document.querySelectorAll('.au-card input[type="password"]'),
              function (i) { return i.getAttribute('autocomplete') === 'new-password'; }));
      check('has a terms checkbox', !!document.querySelector('.au-card input[type="checkbox"]'));
      // A disabled primary action gives a keyboard user a dead control and no reason.
      var cta = document.querySelector('.au-btn-primary');
      check('the primary action is NOT disabled before the terms are ticked',
            !cta.disabled && cta.className.indexOf('is-disabled') === -1);
      check('the terms row clears the 44px touch target',
            document.querySelector('.au-check').getBoundingClientRect().height >= 44,
            'height: ' + document.querySelector('.au-check').getBoundingClientRect().height);
      check('never-blank banner present', has(text, 'You can skip this entirely'));
      check('made no API call on arrival', calls.length === 0, 'calls=' + calls.length);
      universalChecks();
    },

    'signup-short-password': async function () {
      await wait(400);
      check('filled the form', fillSignup({ password: 'abc123def' }));
      await wait(80);
      submit();
      await wait(600);
      var text = cardText();
      // THE correctness case, the same one /reset has. `register_customer_user` validates
      // the password before anything else and raises the same VALIDATION_FAILED as every
      // other field, so an unvalidated submit produces an error nothing can attribute —
      // and the attribution a developer reaches for first is the forbidden one.
      check('NO mutation dispatched for a 9-character password',
            calls.length === 0, 'calls=' + calls.length);
      check('shows the length error', has(text, 'Password must be at least 10 characters'));
      check('never speculates about the address', !has(text.toLowerCase(), 'address'));
      check('keeps the user on the form',
            document.querySelectorAll('.au-card input[type="password"]').length === 2);
      forwardPathCheck('signup rejected for a short password');
      universalChecks();
    },

    'signup-no-terms': async function () {
      await wait(400);
      fillSignup({ agreeTerms: false });
      await wait(80);
      submit();
      await wait(600);
      check('NO mutation dispatched with the terms unticked', calls.length === 0, 'calls=' + calls.length);
      check('says what to do about it', has(cardText(), 'Accept the terms to continue'));
      var box = document.querySelector('.au-card input[type="checkbox"]');
      check('the checkbox is marked invalid', box.getAttribute('aria-invalid') === 'true');
      check('the checkbox points at its message', !!box.getAttribute('aria-describedby'));
      forwardPathCheck('signup rejected for unaccepted terms');
      universalChecks();
    },

    'signup-no-country': async function () {
      await wait(400);
      // Explicitly EMPTY, because `guessCountry()` pre-selects from the browser locale —
      // so "did not touch the field" is not the same as "no country chosen".
      fillSignup({ country: '' });
      await wait(80);
      submit();
      await wait(600);
      // Without this the API rejects EVERY signup with a VALIDATION_FAILED that looks
      // exactly like a bad password — and the handoff's field list omits the field.
      check('NO mutation dispatched without a country', calls.length === 0, 'calls=' + calls.length);
      check('asks for the country', has(cardText(), 'Select your country'));
      forwardPathCheck('signup rejected for a missing country');
      universalChecks();
    },

    'signup-new': async function () {
      await wait(400);
      fillSignup({ email: 'brand-new-address@yourchurch.org' });
      await wait(80);
      recordSurface('signup-new-presubmit');
      markSubmit();
      submit();
      check('the in-flight state was reached', await settleInFlight());
      recordSurface('signup-new-inflight');
      releaseGate();
      check('the accepted state settled', await settle('Check your email to finish setting up'));
      var text = cardText();
      check('accepted state title', has(text, 'Check your email to finish setting up'));
      check('states the 24 hour TTL', has(text, '24 hours'));
      check('FR-552: offers a resend', has(text, 'Resend verification email'));
      var register = calls.filter(function (c) { return c.op === 'RegisterCustomerUser'; })[0];
      check('dispatched registerCustomerUser', !!register);
      check('sent every field under input, camel-cased',
            !!register && register.variables.input &&
            register.variables.input.orgName === 'Grace Community Church' &&
            register.variables.input.country === 'GB' &&
            typeof register.variables.input.idempotencyKey === 'string' &&
            typeof register.variables.input.timezone === 'string');
      check('the idempotency key matches the API pattern',
            !!register && /^[A-Za-z0-9._:-]{12,128}$/.test(register.variables.input.idempotencyKey),
            'key was: ' + (register ? register.variables.input.idempotencyKey : 'none'));
      check('the password is gone from the rendered page',
            pageText().indexOf('a-good-passphrase') === -1);
      recordBranch('signup-new');
      universalChecks();
    },

    'signup-existing': async function () {
      await wait(400);
      // An address that ALREADY has an account. `register_customer_user` returns the same
      // accepted:true and emails the real owner out of band instead; the submitter must
      // learn nothing. Compared against signup-new in EQUIVALENCE_GROUPS.
      fillSignup({ email: 'second-attempt@yourchurch.org' });
      await wait(80);
      recordSurface('signup-existing-presubmit');
      markSubmit();
      submit();
      check('the in-flight state was reached', await settleInFlight());
      recordSurface('signup-existing-inflight');
      releaseGate();
      check('the accepted state settled', await settle('Check your email to finish setting up'));
      var text = cardText();
      check('accepted state title', has(text, 'Check your email to finish setting up'));
      // 86ak120kw correction 1, asserted at the surface it would appear on.
      // Checked against text with the address REMOVED. A probe address containing the
      // word being searched for makes the assertion pass or fail on the fixture rather
      // than on the copy — which is exactly what happened on the first run here.
      // LOW-2 (Quinn): this re-declared, character for character, the exact mask that
      // `EMAIL_IN_VALUE` was fixed to replace — the unanchored form that is greedy over
      // `/` and `?` and swallows a destination along with the address. One definition.
      var withoutAddress = text.replace(EMAIL_IN_VALUE, '').toLowerCase();
      check('never says the address is already registered',
            withoutAddress.indexOf('already') === -1 && withoutAddress.indexOf('taken') === -1 &&
            withoutAddress.indexOf('in use') === -1, 'card said: ' + withoutAddress);
      check('offers no "sign in instead" escape hatch', !has(text, 'Sign in instead'));
      recordBranch('signup-existing');
      universalChecks();
    },

    'signup-unreachable': async function () {
      await wait(400);
      fillSignup({});
      await wait(80);
      submit();
      await wait(900);
      var text = cardText();
      check('does NOT show the accepted state', !has(text, 'Check your email to finish'));
      check('names the connection', has(text, "couldn't reach SelahCue"));
      check('says nothing was created', has(text, 'nothing has been created'));
      check('keeps the form to retry', document.querySelectorAll('.au-card input[type="password"]').length === 2);
      forwardPathCheck('unreachable API on signup');
      universalChecks();
    },

    'signup-rejected': async function () {
      await wait(400);
      fillSignup({});
      await wait(80);
      submit();
      await wait(900);
      var text = cardText();
      var lower = text.toLowerCase();
      check('does NOT show the accepted state', !has(text, 'Check your email to finish'));
      check('reports the failure honestly', has(text, "couldn't create your account"));
      // The whole point: every field was validated first, so a VALIDATION_FAILED that
      // still arrives is a client/server disagreement — NOT evidence the address is taken,
      // which does not raise at all. Guessing otherwise rebuilds the oracle by accident.
      check('never blames the email address',
            lower.indexOf('already') === -1 && lower.indexOf('taken') === -1 &&
            lower.indexOf('in use') === -1);
      forwardPathCheck('rejected signup');
      universalChecks();
    },

    'signup-idempotency': async function () {
      await wait(400);
      fillSignup({});
      await wait(80);
      submit();
      await wait(900);
      check('the first attempt failed in transport', has(cardText(), "couldn't reach SelahCue"));
      submit();
      await wait(900);
      var attempts = calls.filter(function (c) { return c.op === 'RegisterCustomerUser'; });
      check('two attempts were made', attempts.length === 2, 'attempts=' + attempts.length);
      // THE control. After a timeout the client cannot know whether the first request
      // landed; the service namespaces its guard per email fingerprint, so a retry
      // carrying the SAME key converges on the row that already exists. A fresh key on
      // retry — the obvious implementation — races a second org into being.
      check('the retry reused the SAME idempotency key',
            attempts.length === 2 &&
            attempts[0].variables.input.idempotencyKey === attempts[1].variables.input.idempotencyKey,
            attempts.length === 2
              ? attempts[0].variables.input.idempotencyKey + ' vs ' + attempts[1].variables.input.idempotencyKey
              : 'not enough attempts');
      check('the retry succeeded', has(cardText(), 'Check your email to finish setting up'));
      universalChecks();
    },

    'signup-resend': async function () {
      await wait(400);
      fillSignup({});
      await wait(80);
      submit();
      await wait(900);
      check('reached the accepted state', has(cardText(), 'Check your email to finish setting up'));
      var button = Array.prototype.filter.call(
        document.querySelectorAll('.au-card button'),
        function (b) { return b.textContent.indexOf('Resend verification email') !== -1; })[0];
      check('the resend control exists', !!button);
      if (button) button.click();
      await wait(800);
      var text = cardText();
      check('sent state title', has(text, 'Check your inbox'));
      check('phrasing stays conditional', has(text, 'has a SelahCue account waiting to be verified'));
      check('dispatched the resend mutation',
            calls.some(function (c) { return c.op === 'ResendVerification'; }));
      universalChecks();
    },

    // The three states that reach the rate-limit call sites nothing else rendered. Each
    // one exists so `universalChecks`'s rendered claim ban has that call site's output to
    // look at; without them the ban was scanning three of six sites and passing.
    'signup-locale-preselect': async function () {
      await wait(400);
      var select = document.querySelector('.au-card select');
      check('the country field is a select', !!select);
      // THE POINT: with a GB browser the form arrives on GB. `ref('')` fails this, and so
      // does a `guessCountry` that has been reduced to `return ''`.
      check('the country is pre-selected from the browser locale',
            !!select && select.value === 'GB',
            'expected GB for navigator.language=' + navigator.language +
            ', got ' + (select ? JSON.stringify(select.value) : 'no select'));
      // And it is a REAL option, not a value the select cannot show.
      check('the pre-selected country is a real option',
            !!select && Array.prototype.some.call(select.options, function (o) {
              return o.value === 'GB'; }));
      // The label came from Intl.DisplayNames rather than being the bare code -- the other
      // half of the countries.ts gap (`countryOptions` had no test of any kind).
      var chosen = select && Array.prototype.filter.call(select.options, function (o) {
        return o.value === 'GB'; })[0];
      check('the option shows a country NAME, not the two-letter code',
            !!chosen && chosen.textContent.trim() !== 'GB',
            'label was ' + (chosen ? JSON.stringify(chosen.textContent.trim()) : 'absent'));
      check('made no API call on arrival', calls.length === 0, 'calls=' + calls.length);
      universalChecks();
    },

    'signup-rate-limited': async function () {
      await wait(400);
      fillSignup({});
      await wait(80);
      submit();
      await wait(900);
      var text = cardText();
      check('shows the rate-limit banner', has(text, 'Too many attempts'));
      check('tells the caller to wait', has(text, 'Wait a few minutes'));
      check('did not claim the account was created',
            !has(text, 'Check your email to finish setting up'));
      universalChecks();
    },

    'signup-resend-rate-limited': async function () {
      await wait(400);
      fillSignup({});
      await wait(80);
      submit();
      await wait(900);
      check('reached the accepted state', has(cardText(), 'Check your email to finish setting up'));
      var button = Array.prototype.filter.call(
        document.querySelectorAll('.au-card button'),
        function (b) { return b.textContent.indexOf('Resend verification email') !== -1; })[0];
      check('the resend control exists', !!button);
      if (button) button.click();
      await wait(800);
      check('the resend rate limit is reported', has(cardText(), 'Too many requests for a new link'));
      universalChecks();
    },

    'signin-resend-rate-limited': async function () {
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(700);
      check('reached the not-ready state', has(cardText(), "isn't ready to sign in yet"));
      var button = Array.prototype.filter.call(
        document.querySelectorAll('.au-card button'),
        function (b) { return b.textContent.indexOf('Send a verification link') !== -1; })[0];
      check('the resend control exists', !!button);
      if (button) button.click();
      await wait(700);
      check('the resend rate limit is reported', has(cardText(), 'Too many requests for a new link'));
      universalChecks();
    },

    // ========================================================= forgot password ==
    'forgot-form': async function () {
      await wait(400);
      var text = cardText();
      check('title', has(text, 'Reset your password'));
      // 86ak120kw correction 3: the handoff says 15 minutes; the real TTL is 1 hour.
      // universalChecks() bans the "15 minute" string outright as well.
      check('states the real 1 hour TTL', has(text, 'last 1 hour'));
      check('states single use', has(text, 'work once'));
      check('one email field', document.querySelectorAll('.au-card input').length === 1);
      check('email field uses email autocomplete',
            document.querySelector('input[type="email"]').getAttribute('autocomplete') === 'email');
      check('reassures that nothing changes yet', has(text, 'current password keeps working'));
      check('reassures that devices keep presenting', has(text, 'keep presenting offline'));
      check('offers the way back', !!document.querySelector('a[href="/signin"]'));
      check('made no API call on arrival', calls.length === 0, 'calls=' + calls.length);
      universalChecks();
    },

    'forgot-bad-email': async function () {
      await wait(400);
      type('input[type="email"]', 'not-an-email');
      await wait(50);
      submit();
      await wait(400);
      check('malformed address is caught on the field', has(cardText(), 'Enter a valid email address'));
      check('NO API call for a malformed address', calls.length === 0, 'calls=' + calls.length);
      var input = document.querySelector('input[type="email"]');
      check('errored field is marked invalid', input.getAttribute('aria-invalid') === 'true');
      check('the field is still on screen to be corrected', !!input);
      forwardPathCheck('a malformed address on forgot-password');
      universalChecks();
    },

    'forgot-registered': async function () {
      await wait(400);
      type('input[type="email"]', 'pastor@yourchurch.org');
      await wait(50);
      // THE VIEW THIS MATTERS MOST FOR. `ForgotPasswordView` unmounts its email field on
      // the way to the sent state, so the settled recording could never see a bound
      // attribute on it. That is where Cody's `looksRegistered(value)` helper and Sana's
      // computed placeholder both rendered, both passing the whole gate.
      recordSurface('forgot-registered-presubmit');
      markSubmit();
      submit();
      check('the in-flight state was reached', await settleInFlight());
      recordSurface('forgot-registered-inflight');
      releaseGate();
      check('the sent state settled', await settle('Check your inbox'));
      var text = cardText();
      check('sent state title', has(text, 'Check your inbox'));
      check('phrasing is conditional', has(text, 'has a SelahCue account'));
      check('states the 1 hour TTL, not 24', has(text, 'expires in 1 hour'));
      check('dispatched requestPasswordReset',
            calls.some(function (c) { return c.op === 'RequestPasswordReset'; }));
      recordBranch('forgot-registered');
      universalChecks();
    },

    'forgot-unregistered': async function () {
      await wait(400);
      // An address with NO account. `request_password_reset` returns the same accepted:true
      // and pads the miss branch with a dummy PBKDF2 so even the timing matches. The
      // handoff's §5c "We couldn't find an account with this email" would throw all of
      // that away; it is not built. Compared against forgot-registered.
      type('input[type="email"]', 'nobody-has-this@nowhere.test');
      await wait(50);
      recordSurface('forgot-unregistered-presubmit');
      markSubmit();
      submit();
      check('the in-flight state was reached', await settleInFlight());
      recordSurface('forgot-unregistered-inflight');
      releaseGate();
      check('the sent state settled', await settle('Check your inbox'));
      var text = cardText();
      check('sent state title', has(text, 'Check your inbox'));
      check('never says the account was not found',
            !has(text.toLowerCase(), "couldn't find") && !has(text.toLowerCase(), 'no account'));
      check('offers no "create one instead" escape hatch', !has(text, 'Create one'));
      recordBranch('forgot-unregistered');
      universalChecks();
    },

    'forgot-server-rejects-address': async function () {
      await wait(400);
      type('input[type="email"]', 'pastor@yourchurch.org');
      await wait(50);
      submit();
      await wait(700);
      var text = cardText();
      // The defect: `VALIDATION_FAILED` fell into the resend copy — "try again in a
      // moment" — a TRANSIENT message for an error that will never clear. The user
      // retries forever and no link ever comes: the FR-552 dead end reached through a
      // typo the client failed to catch.
      check('a permanent input error is NOT reported as transient',
            !has(text, 'try again in a moment'), 'card said: ' + text);
      check('it is reported on the field, where it can be corrected',
            has(text, 'Enter a valid email address.'), 'card said: ' + text);
      var input = document.querySelector('input[type="email"]');
      check('and the field is marked invalid',
            !!input && input.getAttribute('aria-invalid') === 'true');
      check('the sent state is never shown for a failure', !has(text, 'Check your inbox'));
      forwardPathCheck('an address the server refused');
      universalChecks();
    },

    'forgot-failure': async function () {
      await wait(400);
      type('input[type="email"]', 'pastor@yourchurch.org');
      await wait(50);
      submit();
      await wait(800);
      var text = cardText();
      // The mutation returns accepted:true for EVERY valid address, so an error means the
      // request genuinely did not happen. "Check your inbox" here would send someone to
      // wait for an email that is not coming.
      check('a failed request does NOT show the sent state', !has(text, 'Check your inbox'));
      check('a failed request says so honestly', has(text, "couldn't send a link"));
      check('the form stays available to retry', !!document.querySelector('input[type="email"]'));
      forwardPathCheck('failed reset request');
      universalChecks();
    },

    'forgot-rate-limited': async function () {
      await wait(400);
      type('input[type="email"]', 'pastor@yourchurch.org');
      await wait(50);
      submit();
      await wait(800);
      var text = cardText();
      var lower = text.toLowerCase();
      check('a rate-limited request does NOT show the sent state', !has(text, 'Check your inbox'));
      check('it says so', has(text, 'Too many requests'));
      check('it says to wait rather than inviting an instant retry', has(text, 'Wait a few minutes'));
      // The per-address budget is spent before the account is looked up, so a rate limit
      // is not evidence the address is real. The copy must not imply it is.
      check('rate-limit copy never implies the account exists',
            lower.indexOf('this account') === -1 && lower.indexOf('your account') === -1 &&
            lower.indexOf('for this address') === -1);
      forwardPathCheck('rate-limited reset request');
      universalChecks();
    },

    // =============================================================== route guard ==
    'account-guarded': async function () {
      await wait(1200);
      // The guard asks the SERVER. Local state is attacker-writable and goes stale in the
      // one direction that matters — claiming a session that was revoked minutes ago.
      check('the guard probed the server',
            calls.some(function (c) { return c.op === 'AccountViewer'; }));
      check('a signed-out visitor is redirected to sign in', location.pathname === '/signin',
            'pathname: ' + location.pathname);
      check('and is told why', has(pageText(), "You've been signed out"));
      check('the destination was preserved for after sign-in',
            location.search.indexOf('next=%2Faccount') !== -1 ||
            location.search.indexOf('next=/account') !== -1,
            'search: ' + location.search);
      csrfChecks();
    },

    'account-stale-hint': async function () {
      await wait(1200);
      // The premise, read from what the driver PLANTED rather than from storage — by the
      // time this runs the app has already acted on it, and reading storage here would
      // measure the outcome and call it the setup.
      check('the harness really planted a live-looking hint',
            !!plantedHint && plantedHint.indexOf('expiresAt') !== -1 &&
            Date.parse(JSON.parse(plantedHint).expiresAt) - Date.now() > 20 * 24 * 3600 * 1000,
            'planted: ' + plantedHint);
      check('the guard asked the SERVER rather than trusting the hint',
            calls.some(function (c) { return c.op === 'AccountViewer'; }),
            'ops: ' + calls.map(function (c) { return c.op; }).join(','));
      check('a stale hint does not grant entry', location.pathname === '/signin',
            'pathname: ' + location.pathname);
      check('and the visitor is told why', has(pageText(), "You've been signed out"));
      // And the good behaviour this scenario incidentally proves: a hint the server has
      // contradicted is DROPPED, so the navbar stops painting "Account" for someone whose
      // session is gone. Nothing asserted this before.
      check('a hint the server contradicted is dropped rather than left to mislead',
            window.localStorage.getItem('selahcue.session') === null,
            'hint after: ' + window.localStorage.getItem('selahcue.session'));
      csrfChecks();
    },

    'signin-rate-limited': async function () {
      await wait(400);
      fillSignIn('pastor@yourchurch.org', REJECTED_PASSWORD);
      await wait(50);
      submit();
      await wait(700);
      var text = cardText();
      check('the rate-limit banner is shown', has(text, 'Too many attempts'));
      check('it says what to do', has(text, 'Wait a few minutes'));
      // THE POINT of this copy: a limiter that spent its budget before looking the account
      // up is not evidence the account is real, so nothing here may imply it is.
      check('it never implies the account exists',
            !has(text.toLowerCase(), 'this account') &&
            !has(text.toLowerCase(), 'your account') &&
            !has(text.toLowerCase(), 'that address'),
            'card said: ' + text);
      check('it is NOT reported as a credential failure',
            !has(text, 'Invalid email or password'), 'card said: ' + text);
      check('the password was cleared',
            document.querySelector('input[type="password"]').value === '');
      forwardPathCheck('rate-limited sign-in');
      universalChecks();
    },

    'account-allowed': async function () {
      await wait(1200);
      check('a live session reaches the account route', location.pathname === '/account',
            'pathname: ' + location.pathname);
      check('the guard confirmed it with the server',
            calls.some(function (c) { return c.op === 'AccountViewer'; }));
      csrfChecks();
    },

    'session-refresh': async function () {
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(1500);
      check('signed in', location.pathname === '/account', 'pathname: ' + location.pathname);
      // Inside the last week of the 30-day window, so the guard takes the opportunity.
      check('a session close to expiry was extended',
            calls.some(function (c) { return c.op === 'RefreshSession'; }),
            'ops: ' + calls.map(function (c) { return c.op; }).join(','));
      check('the refresh document does NOT select the rotated token',
            calls.filter(function (c) { return c.op === 'RefreshSession'; })
                 .every(function (c) { return c.query.indexOf('sessionToken') === -1; }));
      // The rotation must be recorded, or the next navigation refreshes again and again.
      var hint = JSON.parse(window.localStorage.getItem('selahcue.session') || '{}');
      check('the stored expiry moved forward',
            Date.parse(hint.expiresAt) - Date.now() > 20 * 24 * 3600 * 1000,
            'hint expiry: ' + hint.expiresAt);
      check('the stored hint still carries no token',
            JSON.stringify(hint).indexOf('sessionToken') === -1);
      csrfChecks();
    },

    'session-no-refresh': async function () {
      await wait(400);
      fillSignIn('pastor@yourchurch.org', 'a-good-passphrase');
      await wait(50);
      submit();
      await wait(1500);
      check('signed in', location.pathname === '/account', 'pathname: ' + location.pathname);
      // THE control on the pair above. Rotation revokes the presented token inside one
      // transaction, so a lost response strands the session — doing it on every
      // navigation would roll that dice several times an hour for nothing.
      check('a session with weeks left is NOT rotated',
            !calls.some(function (c) { return c.op === 'RefreshSession'; }),
            'ops: ' + calls.map(function (c) { return c.op; }).join(','));
      csrfChecks();
    }
  };

  async function run() {
    var fn = SCENARIOS[SCENARIO];
    if (!fn) {
      results.push('FAIL [' + SCENARIO + '] no such scenario in the driver');
    } else {
      try { await fn(); }
      catch (e) { results.push('FAIL [' + SCENARIO + '] driver threw: ' + (e && e.message)); }
    }
    var pre = document.createElement('pre');
    pre.id = '__results';
    pre.textContent = 'RESULTS\n' + results.join('\n') + '\nDONE(' + results.length + ')';
    document.body.appendChild(pre);

    // Separate block, and deliberately not part of DONE(n): these are DATA for the
    // cross-scenario comparison in Python, not checks. Counting them would inflate the
    // total that EXPECTED_MIN_CHECKS guards.
    var recorded = document.createElement('pre');
    recorded.id = '__records';
    recorded.textContent = 'ENUMERATION\n' + records.join('\n') + '\nENDENUMERATION';
    document.body.appendChild(recorded);
  }

  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', function () { setTimeout(run, 0); });
  } else {
    setTimeout(run, 0);
  }
})();
</script>
"""


# ---------------------------------------------------------------------------- server ---
class SpaHandler(http.server.SimpleHTTPRequestHandler):
    """Serves dist/ with SPA fallback, injecting the driver into index.html."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, *args):  # keep the run quiet
        pass

    def do_GET(self):  # noqa: N802 (stdlib naming)
        path = self.path.split("?", 1)[0]
        candidate = DIST / path.lstrip("/")
        if path != "/" and candidate.is_file():
            return super().do_GET()

        html = (DIST / "index.html").read_text(encoding="utf-8")
        # Injected at </head>, so it runs before the app's module script.
        driver = DRIVER.replace("__SHARED_COPY__", json.dumps(shared_copy()))
        html = html.replace("</head>", driver + "</head>", 1)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ------------------------------------------------------------------------- scenarios ---
VERIFY_TOKEN = "SC-TESTTOKEN-verify"
RESET_TOKEN = "SC-TESTTOKEN-reset"

SCENARIOS: list[tuple[str, str]] = [
    ("verify-loading", f"/verify?token={VERIFY_TOKEN}"),
    ("verify-success", f"/verify?token={VERIFY_TOKEN}"),
    ("verify-invalid", f"/verify?token={VERIFY_TOKEN}"),
    ("verify-missing", "/verify"),
    ("verify-unreachable", f"/verify?token={VERIFY_TOKEN}"),
    ("verify-resend", f"/verify?token={VERIFY_TOKEN}"),
    ("verify-rate-limited", f"/verify?token={VERIFY_TOKEN}"),
    ("verify-resend-fails", f"/verify?token={VERIFY_TOKEN}"),
    ("verify-bad-email", f"/verify?token={VERIFY_TOKEN}"),
    ("reset-form", f"/reset?token={RESET_TOKEN}"),
    ("reset-short-password", f"/reset?token={RESET_TOKEN}"),
    ("reset-whitespace-password", f"/reset?token={RESET_TOKEN}"),
    ("reset-mismatch", f"/reset?token={RESET_TOKEN}"),
    ("reset-success", f"/reset?token={RESET_TOKEN}"),
    ("reset-invalid", f"/reset?token={RESET_TOKEN}"),
    ("reset-password-invalid", f"/reset?token={RESET_TOKEN}"),
    ("reset-unreachable", f"/reset?token={RESET_TOKEN}"),
    ("reset-missing", "/reset"),
    ("reset-fresh-link", f"/reset?token={RESET_TOKEN}"),
    # ------------------------------------------------------ sign-in (86ak11r67) --
    ("signin-form", "/signin"),
    ("signin-validation", "/signin"),
    ("signin-expired", "/signin?reason=expired"),
    ("signin-rejected-unknown", "/signin"),
    ("signin-rejected-wrong-password", "/signin"),
    ("signin-unreachable", "/signin"),
    ("signin-rate-limited", "/signin"),
    ("signin-unverified", "/signin"),
    ("signin-resend", "/signin"),
    ("signin-resend-rate-limited", "/signin"),
    ("signin-success", "/signin"),
    # The `?next=` round trip, end to end — the half `redirect.test.ts` cannot reach.
    ("signin-next-honoured", "/signin?next=%2Fsupport"),
    ("signin-next-hostile", "/signin?next=https%3A%2F%2Fevil.example%2Fpay"),
    ("signin-next-unmatched", "/signin?next=%2Fdoes-not-exist"),
    ("session-lifecycle", "/signin"),
    ("signout-failure", "/signin"),
    # ------------------------------------------------------------ create account --
    ("signup-form", "/signup"),
    ("signup-short-password", "/signup"),
    ("signup-no-terms", "/signup"),
    ("signup-no-country", "/signup"),
    ("signup-new", "/signup"),
    ("signup-existing", "/signup"),
    ("signup-unreachable", "/signup"),
    ("signup-rejected", "/signup"),
    ("signup-idempotency", "/signup"),
    ("signup-resend", "/signup"),
    ("signup-locale-preselect", "/signup"),
    ("signup-rate-limited", "/signup"),
    ("signup-resend-rate-limited", "/signup"),
    # ----------------------------------------------------------- forgot password --
    ("forgot-form", "/forgot-password"),
    ("forgot-bad-email", "/forgot-password"),
    ("forgot-registered", "/forgot-password"),
    ("forgot-unregistered", "/forgot-password"),
    ("forgot-failure", "/forgot-password"),
    ("forgot-server-rejects-address", "/forgot-password"),
    ("forgot-rate-limited", "/forgot-password"),
    # ---------------------------------------------------------------- route guard --
    ("account-guarded", "/account"),
    ("account-stale-hint", "/account"),
    ("account-allowed", "/account"),
    ("session-refresh", "/signin"),
    ("session-no-refresh", "/signin"),
]


# The enumeration probe. Each group names scenarios whose renders MUST be
# indistinguishable, because the API's answers to them are indistinguishable by design.
#
# This is the assertion an eyeball cannot make and a single-page check cannot express:
# not "does this page look right" but "are these two pages the same". A client that
# started varying its copy, or its request count, with whether an address is registered
# would pass every other check in this file and fail here.
#
# `|card` is the rendered card text with email addresses masked, so the two halves can use
# genuinely different addresses. `|ops` is the GraphQL operation sequence — leaking by
# sending an extra request for one branch is as effective an oracle as leaking in words.
# The facets compared for every group.
#
#   card     the auth card's rendered text, email addresses masked
#   page     the WHOLE page, which is the only way to see the footer — it is rendered
#            outside `.au-card` by AuthShell, so the card facet is blind to it (LOW-2)
#   ops      the sequence of GraphQL operations; an extra request for one branch is an
#            oracle just as surely as different copy
#   tone     the status/tone classes anywhere on the page — the footer included, since
#            AuthShell renders it outside the card; identical copy in a different colour
#            is a colour-only oracle (LOW-3, widened per Quinn)
#   attrs    tag name plus href/disabled/aria-*/type/name/class for every element; the
#            channel the other four are blind to. A link with identical visible text and
#            an address-keyed destination passed all of them (Quinn)
COMPARED_FACETS = ("card", "page", "ops", "tone", "attrs")

# The facets that mean something at a moment OTHER than the settled one. `ops` and
# `elapsed` are excluded: a request sequence and a duration are only meaningful once the
# interaction has finished.
SURFACE_FACETS = ("card", "page", "tone", "attrs")

# GATED, at a WIDE PAIRED DELTA — a decision reversed on this round's evidence.
#
#   elapsed  virtual milliseconds from submit until the terminal copy is actually on
#            screen, found by polling.
#
# This was INFO-only, on the argument that its noise floor was "wider than any useful
# threshold". Vera falsified the operative half of that: she planted this ledger's own
# documented mutation — an address-keyed `setTimeout(900)` in the sign-in submit path — and
# the harness exited 0 with 0 FAIL, printing `elapsed: 920 vs 20` as its only trace, which
# nothing machine-reads. A demonstrated miss of a real oracle shape.
#
# The measurements do not support leaving it ungated. Three reviewers took a baseline
# independently and all three read a constant: Vera 18/18 paired readings at exactly 20 vs
# 20 across three runs, Quinn "a constant 20 vs 20 on every run", Cody 20/20 on all three
# groups. The recorded worst spread on CORRECT code is 321ms, and that was at load 41;
# under the same load the planted 900ms mutant still read a delta of 869ms. A paired-delta
# gate at 600ms fires on every planted mutant on record and on none of the recorded clean
# runs, anyone's.
#
# THE HONEST CAVEAT, because the original reasoning about flakiness was not wrong in kind:
# every one of those readings comes from a DEVELOPER MACHINE. Nobody has measured a CI
# runner's variance, and with this repository's Actions minutes exhausted nobody could. So
# 600ms is calibrated on local runs only. If CI turns this red on correct code, WIDEN IT —
# to 1500ms, which still catches every mutant on record — rather than removing the gate,
# and record the measurement that justified the change here. A gate that cries wolf is
# genuinely worse than no gate; a gate that is known to miss a demonstrated attack is
# worse still.
#
# Paired DELTA rather than an absolute ceiling, because the absolute number is a property
# of the machine and the difference between two branches is a property of the code.
ELAPSED_MAX_PAIRED_DELTA_MS = 600

EQUIVALENCE_GROUPS: list[tuple[str, list[str]]] = [
    (
        "FR-529: unknown email and wrong password are indistinguishable at sign-in",
        ["signin-rejected-unknown", "signin-rejected-wrong-password"],
    ),
    (
        "FR-529/86ak120kw: signup looks the same for a new and an already-registered address",
        ["signup-new", "signup-existing"],
    ),
    (
        "FR-529: forgot-password looks the same for a registered and an unregistered address",
        ["forgot-registered", "forgot-unregistered"],
    ),
]

# THE SAME THREE PAIRS, AT THE TWO MOMENTS THE SETTLED COMPARISON COULD NOT SEE.
#
# This is the round's central fix, and it is the reason the source-level bans in
# `tests/authViews.test.ts` can go back to being tripwires rather than pretending to be the
# boundary. Four demonstrated leaks passed BOTH gates, and every one of them lived in a
# window nothing sampled:
#
#   Cody   an ordinary helper extraction — `function looksRegistered(value: string)` — put
#          the inspection on a parameter no name list has ever heard of, bound to a
#          `:placeholder` on a field that is unmounted by the time the settled state is
#          recorded. Observed on screen: "This address has an account" versus "Enter your
#          email".
#   Sana   a computed `:placeholder` keyed on the address as the user types it, rendering
#          "This address has no account" for the whole time the form is up. Passed
#          `npm test` 110/110, `npm run build`, and 1384 checks / 0 FAIL.
#   Quinn  an address-keyed `au-note` rendered only while `state === 'submitting'` — a
#          window that, with the old synchronous fixtures, never painted at all.
#
# Extending the regexes would have caught the shapes and not the class. Comparing what the
# two branches RENDER, at every moment one of them is on screen, catches all four without
# knowing anything about how the source is written — which is the property the ban can
# never have.
SURFACE_GROUPS: list[tuple[str, list[str]]] = [
    (label + " [before submit]", [f"{name}-presubmit" for name in scenarios])
    for label, scenarios in EQUIVALENCE_GROUPS
] + [
    (label + " [in flight]", [f"{name}-inflight" for name in scenarios])
    for label, scenarios in EQUIVALENCE_GROUPS
]


def newest_mtime(root: Path, suffixes: tuple[str, ...] = ()) -> float:
    newest = 0.0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if suffixes and path.suffix not in suffixes:
            continue
        newest = max(newest, path.stat().st_mtime)
    return newest


def check_bundle_is_current() -> str | None:
    """Refuse to run against a `dist/` older than the sources it claims to be built from.

    This is not hypothetical tidiness — it produced a FALSE GREEN during this script's own
    development. `npm run test:states` chains `npm run build && …`, so a failing build
    stops the chain in CI. But the docstring above invites running this file directly, and
    when it is, a bundle left over from the last good build is served happily: 47
    scenarios pass, 0 FAIL, exit 0, and not one line of the code under test was involved.

    A green that does not depend on the current source is worse than a red, because it is
    trusted. Compare timestamps and fail as infrastructure (exit 2) rather than as a
    behavioural failure (exit 1), because that is what it is.
    """
    built = newest_mtime(DIST)
    # LOW-4 (Sana): `src/` and `index.html` are not the whole input to a build. A change
    # to the Vite config, the dependency list or the lockfile alters the bundle WITHOUT
    # touching `src/` — reopening a narrow version of exactly the false-green window this
    # guard was built to close.
    candidates = [newest_mtime(MARKETING / "src")]
    # `tsconfig.app.json` carries the `@/*` path alias, and everything in `public/` is
    # copied verbatim into `dist/` — both are real build inputs that leave `src/`
    # untouched. Same class as LOW-4; found by Quinn after the first widening.
    candidates.append(newest_mtime(MARKETING / "public"))
    for name in (
        "index.html",
        "vite.config.ts",
        "package.json",
        "package-lock.json",
        "tsconfig.app.json",
    ):
        path = MARKETING / name
        if path.is_file():
            candidates.append(path.stat().st_mtime)
    # LOW-9 (Cody): `VITE_API_BASE_URL` is a BUILD-TIME constant (`graphql.ts:140`), so an
    # env file changes the bundle without touching any input watched above — the same class
    # as LOW-4, one input short. Only `.env.example` exists today, so this is pre-emptive.
    for env_file in sorted(MARKETING.glob(".env*")):
        if env_file.is_file():
            candidates.append(env_file.stat().st_mtime)
    sources = max(candidates)
    if sources > built:
        return (
            f"the bundle at {DIST} is OLDER than its sources (src/, public/, index.html, "
            f"vite.config.ts, tsconfig.app.json, package.json, package-lock.json, .env*) "
            f"({sources - built:.0f}s stale). Run `npm run build` first — this run would "
            "otherwise report on code that is not in the bundle."
        )
    return None


def main() -> int:
    if not (DIST / "index.html").is_file():
        print(f"FAIL: no built bundle at {DIST}. Run `npm run build` first.")
        return 2

    stale = check_bundle_is_current()
    if stale is not None:
        print(f"FAIL: {stale}")
        return 2

    chrome = find_chrome()
    if chrome is None:
        require = os.environ.get("SELAHCUE_HEADLESS_REQUIRE") == "1"
        msg = "no Chrome/Chromium found (set CHROME_BIN or install google-chrome)"
        if require:
            print(f"FAIL: {msg} and SELAHCUE_HEADLESS_REQUIRE=1")
            return 2
        print("!! " * 20)
        print(f"!! SKIPPING the /verify + /reset state check: {msg}")
        print("!! (CI should run this with SELAHCUE_HEADLESS_REQUIRE=1)")
        print("!! " * 20)
        return 0

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", 0), SpaHandler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        body: list[str] = []
        records: dict[str, str] = {}
        total = 0
        for scenario, path in SCENARIOS:
            joiner = "&" if "?" in path else "?"
            url = f"http://127.0.0.1:{port}{path}{joiner}__scenario={scenario}"
            try:
                out = subprocess.run(
                    [
                        chrome,
                        "--headless=new",
                        "--disable-gpu",
                        "--no-sandbox",
                        # The design's own frame size (auth handoff §2.3: 1440x900). At
                        # Chrome's 800x600 default the navbar's desktop group is below its
                        # breakpoint and `display:none`, so any assertion about the
                        # signed-in controls would be measuring the window, not the app.
                        "--window-size=1440,900",
                        "--no-first-run",
                        "--disable-extensions",
                        "--virtual-time-budget=8000",
                        "--dump-dom",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                ).stdout
            except subprocess.TimeoutExpired:
                print(f"FAIL: headless Chrome timed out on scenario {scenario} (infra)")
                server.shutdown()
                return 2

            match = re.search(r"RESULTS\n(.*?)\nDONE\((\d+)\)", out, re.S)
            if not match:
                print(f"NO RESULTS BLOCK for scenario {scenario}. DOM head:\n{out[:1200]}")
                server.shutdown()
                return 2

            lines = [line for line in match.group(1).splitlines() if line.strip()]
            body.extend(lines)
            total += int(match.group(2))

            recorded = re.search(r"ENUMERATION\n(.*?)\nENDENUMERATION", out, re.S)
            if recorded:
                for line in recorded.group(1).splitlines():
                    key, separator, value = line.partition(" :: ")
                    if separator:
                        records[key.strip()] = value

        server.shutdown()

    # The cross-scenario half of the suite. Counted into `total` like any other check, so
    # losing a group trips the EXPECTED_MIN_CHECKS floor rather than passing quietly.
    def compare(label: str, scenarios: list[str], facets: tuple[str, ...]) -> int:
        """One string-equality check per facet. Returns how many checks it ran."""
        ran = 0
        for facet in facets:
            keys = [f"{name}|{facet}" for name in scenarios]
            missing = [key for key in keys if key not in records]
            ran += 1
            if missing:
                # Not a pass. A recording that never arrived means the scenario did not
                # reach the state it was meant to compare, and an absent value must never
                # read as "they matched".
                body.append(
                    f"FAIL [enumeration] {label} ({facet}) -- no recording for {missing}"
                )
                continue

            matched = len({records[key] for key in keys}) == 1
            detail = "\n      ".join(f"{key}: {records[key]}" for key in keys)

            if matched:
                body.append(f"PASS [enumeration] {label} ({facet})")
            else:
                body.append(
                    f"FAIL [enumeration] {label} ({facet}) -- these differ:\n      {detail}"
                )
        return ran

    for label, scenarios in EQUIVALENCE_GROUPS:
        total += compare(label, scenarios, COMPARED_FACETS)

        # `elapsed`, GATED at a wide paired delta. See ELAPSED_MAX_PAIRED_DELTA_MS for the
        # measurements behind the number and the standing caveat about CI variance.
        total += 1
        readings: list[int] = []
        unreadable = []
        for name in scenarios:
            raw = records.get(f"{name}|elapsed")
            if raw is None or not raw.lstrip("-").isdigit() or int(raw) < 0:
                unreadable.append(f"{name}={raw}")
            else:
                readings.append(int(raw))
        shown = " vs ".join(
            f"{name}={records.get(f'{name}|elapsed', '?')}" for name in scenarios
        )
        if unreadable:
            # A missing or -1 reading means a branch never settled, which is not a pass.
            body.append(f"FAIL [enumeration] {label} (elapsed) -- no usable reading: {shown}")
        else:
            delta = max(readings) - min(readings)
            if delta > ELAPSED_MAX_PAIRED_DELTA_MS:
                body.append(
                    f"FAIL [enumeration] {label} (elapsed) -- the two branches settled "
                    f"{delta}ms apart, over the {ELAPSED_MAX_PAIRED_DELTA_MS}ms budget. "
                    f"Readings: {shown}"
                )
            else:
                body.append(
                    f"PASS [enumeration] {label} (elapsed) -- {delta}ms apart "
                    f"(budget {ELAPSED_MAX_PAIRED_DELTA_MS}ms): {shown}"
                )

    # And the same pairs at the two moments the settled comparison could not see.
    for label, scenarios in SURFACE_GROUPS:
        total += compare(label, scenarios, SURFACE_FACETS)

    # THE COVERAGE HALF of the rendered rate-limit scan. The ban inside `universalChecks`
    # only runs when the page is showing rate-limit copy, so a change that stopped those
    # states rendering — or stopped the markers matching — would silently retire the check
    # and every gate would stay green. Counted, and counted into `total`, so losing it trips
    # the floor as well as failing here.
    scanned = {
        line.split("[", 1)[1].split("]", 1)[0]
        for line in body
        if "RATE-LIMIT STATE SCANNED for address claims" in line
    }
    expected = set(rate_limited_scenarios())
    total += 1
    unscanned = sorted(expected - scanned)
    if not unscanned and len(scanned) >= RATE_LIMIT_CLAIM_SCENARIOS_MIN:
        body.append(
            f"PASS [enumeration] the rendered rate-limit claim ban ran on all "
            f"{len(scanned)} rate-limited states: {' '.join(sorted(scanned))}"
        )
    else:
        body.append(
            f"FAIL [enumeration] the rendered rate-limit claim ban did not run on "
            f"{unscanned or 'enough states'} (scanned {len(scanned)}, floor "
            f"{RATE_LIMIT_CLAIM_SCENARIOS_MIN}). A conditional ban that never fires passes "
            "exactly like one that fires and holds -- check those states still render the "
            "rate-limit copy the markers in messages.ts name."
        )

    fails = [line for line in body if line.startswith("FAIL")]
    for line in body:
        # The cross-scenario results are printed whether they pass or fail. They are the
        # ones a reviewer most wants to SEE having run, and a silently-absent group would
        # otherwise be indistinguishable from a passing one.
        if line.startswith("FAIL") or "[enumeration]" in line:
            print(line)
    print(f"\n=== {len(SCENARIOS)} scenarios, {total} checks, {len(fails)} FAIL ===")

    if total < EXPECTED_MIN_CHECKS:
        print(
            f"FAIL: only {total} checks ran; expected >= {EXPECTED_MIN_CHECKS} "
            "(the suite must not silently shrink)"
        )
        return 4
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
