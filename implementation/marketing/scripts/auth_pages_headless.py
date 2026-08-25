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
EXPECTED_MIN_CHECKS = 1369


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


# --------------------------------------------------------------------------- driver ---
# Injected into <head> so it runs BEFORE the app module. It must, because it has to
# capture the scenario name out of the query string before the view scrubs the query,
# and it has to replace `fetch` before onMounted fires.

DRIVER = r"""
<script>
(function () {
  var QS = new URLSearchParams(location.search);
  var SCENARIO = QS.get('__scenario') || '';
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

  function json(body, status) {
    return new Response(JSON.stringify(body), {
      status: status || 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Mutable state a couple of scenarios need across calls within one page load.
  var registerAttempts = 0;
  var signedOut = false;

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
    'reset-unreachable':   function () { throw new TypeError('Failed to fetch'); },
    'reset-fresh-link':    function (op) {
      if (op === 'ConfirmPasswordReset') return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] });
      return json({ data: { requestPasswordReset: { accepted: true } } });
    },

    // ------------------------------------------------------------------ sign-in (86ak11r67) --
    // `login` returns the SAME UNAUTHENTICATED for an unknown address, a wrong password and
    // a locked-out account, and equalises their timing. These two scenarios differ only in
    // the address typed; EQUIVALENCE_GROUPS asserts their renders are identical.
    'signin-rejected-unknown':        function () { return UNAUTHENTICATED(); },
    'signin-rejected-wrong-password': function () { return UNAUTHENTICATED(); },
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
    'signup-new':          function () { return REGISTERED(); },
    'signup-existing':     function () { return REGISTERED(); },
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

    // ----------------------------------------------------------- forgot password --
    // Same uniformity: `request_password_reset` pads the miss branch with a dummy PBKDF2
    // so a registered and an unregistered address are indistinguishable in code AND time.
    'forgot-registered':   function () { return RESET_REQUESTED(); },
    'forgot-unregistered': function () { return RESET_REQUESTED(); },
    'forgot-form':         function () { return RESET_REQUESTED(); },
    'forgot-bad-email':    function () { return RESET_REQUESTED(); },
    'forgot-failure':      function () { return json({ errors: [{ extensions: { code: 'INTERNAL' } }] }); },
    'forgot-rate-limited': function () { return json({ errors: [{ extensions: { code: 'RATE_LIMITED' } }] }); },

    // --------------------------------------------------------------- route guard --
    'account-guarded':     function () { return UNAUTHENTICATED(); },
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
   * Record normalised text for cross-scenario comparison.
   *
   * Email addresses are masked, so two scenarios may use different addresses and still
   * compare equal — which is the point: the comparison must catch copy that VARIES with
   * the address, not trip over the address itself. Whitespace is collapsed because Vue's
   * rendered indentation is not part of what a user reads.
   */
  function record(key, value) {
    var masked = String(value)
      .replace(/[^\s@]+@[^\s@]+\.[^\s@]+/g, '<EMAIL>')
      .replace(/\s+/g, ' ')
      .trim();
    records.push(key + ' :: ' + masked);
  }

  /** The operation sequence, for the same comparison. A different number or order of
      requests between two branches is an oracle just as surely as different copy is. */
  function opSequence() {
    return calls.map(function (c) { return c.op; }).join(',');
  }

  function recordBranch(key) {
    record(key + '|card', cardText());
    record(key + '|ops', opSequence());
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
    var actionable =
      document.querySelectorAll('.au-card button, .au-card a, .au-card input').length;
    check('a way forward is offered: ' + label, actionable > 0,
          'the card rendered no button, link or field');
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
  function universalChecks() {
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
    check('no unbacked OAuth affordance (DEC-007 chose email/password)',
          text.indexOf('Continue with Google') === -1 && text.indexOf('Google') === -1);

    csrfChecks();

    // COMPUTED geometry, not just class presence. The auth card overrides UiButton's
    // pill radius from a global stylesheet, and global-vs-scoped rules of equal
    // specificity are decided by injection order — which is not something to assume.
    var btn = document.querySelector('.au-btn');
    if (btn) {
      var style = getComputedStyle(btn);
      check('primary button uses the auth card 12px radius, not the marketing pill',
            style.borderRadius === '12px', 'computed: ' + style.borderRadius);
      check('primary button clears the 44px touch target',
            btn.getBoundingClientRect().height >= 44,
            'height: ' + btn.getBoundingClientRect().height);
      check('primary button is full width inside the card',
            Math.abs(btn.getBoundingClientRect().width -
                     document.querySelector('.au-card').clientWidth +
                     (parseFloat(getComputedStyle(document.querySelector('.au-card')).paddingLeft) +
                      parseFloat(getComputedStyle(document.querySelector('.au-card')).paddingRight))) < 2,
            'button ' + btn.getBoundingClientRect().width);
    }

    // The card must not be full-bleed — the surrounding --sc-base margin is what marks
    // it as a focused task (design 13).
    var card = document.querySelector('.au-card');
    if (card) {
      check('card is not full-bleed', card.getBoundingClientRect().width < window.innerWidth,
            'card ' + card.getBoundingClientRect().width + ' vs viewport ' + window.innerWidth);
    }
  }

  function has(text, needle) { return text.indexOf(needle) !== -1; }

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
      universalChecks();
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
      fillSignIn('nobody-has-this-address@nowhere.test', 'whatever-they-typed');
      await wait(50);
      submit();
      await wait(700);
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
      fillSignIn('pastor@yourchurch.org', 'not-the-right-one');
      await wait(50);
      submit();
      await wait(700);
      check('rejection banner shown', has(cardText(), 'Invalid email or password'));
      recordBranch('signin-rejected-wrong-password');
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
      // No token in storage, anywhere. The hint is metadata only.
      // Built key by key: `JSON.stringify(localStorage)` relies on Storage's named
      // properties being own-enumerable, which is true in Chrome and not worth betting a
      // security assertion on. An explicit sweep cannot pass by returning "{}".
      var stored = '';
      for (var i = 0; i < window.localStorage.length; i += 1) {
        var storageKey = window.localStorage.key(i);
        stored += storageKey + '=' + window.localStorage.getItem(storageKey) + ';';
      }
      check('something WAS stored, so the sweep below is not vacuous', stored.length > 0);
      check('no session token was written to localStorage',
            stored.indexOf('sessionToken') === -1 && stored.indexOf('SC-SESSION') === -1,
            'localStorage held: ' + stored);
      check('the stored hint carries only role, org and expiry',
            Object.keys(JSON.parse(window.localStorage.getItem('selahcue.session') || '{}'))
              .sort().join(',') === 'expiresAt,orgId,role');
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
      universalChecks();
    },

    'signup-new': async function () {
      await wait(400);
      fillSignup({ email: 'brand-new-address@yourchurch.org' });
      await wait(80);
      submit();
      await wait(900);
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
      submit();
      await wait(900);
      var text = cardText();
      check('accepted state title', has(text, 'Check your email to finish setting up'));
      // 86ak120kw correction 1, asserted at the surface it would appear on.
      // Checked against text with the address REMOVED. A probe address containing the
      // word being searched for makes the assertion pass or fail on the fixture rather
      // than on the copy — which is exactly what happened on the first run here.
      var withoutAddress = text.replace(/[^\s@]+@[^\s@]+\.[^\s@]+/g, '').toLowerCase();
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
      universalChecks();
    },

    'forgot-registered': async function () {
      await wait(400);
      type('input[type="email"]', 'pastor@yourchurch.org');
      await wait(50);
      submit();
      await wait(800);
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
      submit();
      await wait(800);
      var text = cardText();
      check('sent state title', has(text, 'Check your inbox'));
      check('never says the account was not found',
            !has(text.toLowerCase(), "couldn't find") && !has(text.toLowerCase(), 'no account'));
      check('offers no "create one instead" escape hatch', !has(text, 'Create one'));
      recordBranch('forgot-unregistered');
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
        html = html.replace("</head>", DRIVER + "</head>", 1)
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
    ("signin-unverified", "/signin"),
    ("signin-resend", "/signin"),
    ("signin-success", "/signin"),
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
    # ----------------------------------------------------------- forgot password --
    ("forgot-form", "/forgot-password"),
    ("forgot-bad-email", "/forgot-password"),
    ("forgot-registered", "/forgot-password"),
    ("forgot-unregistered", "/forgot-password"),
    ("forgot-failure", "/forgot-password"),
    ("forgot-rate-limited", "/forgot-password"),
    # ---------------------------------------------------------------- route guard --
    ("account-guarded", "/account"),
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
    sources = max(
        newest_mtime(MARKETING / "src"),
        (MARKETING / "index.html").stat().st_mtime if (MARKETING / "index.html").is_file() else 0.0,
    )
    if sources > built:
        return (
            f"the bundle at {DIST} is OLDER than the sources under {MARKETING / 'src'} "
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
    for label, scenarios in EQUIVALENCE_GROUPS:
        for facet in ("card", "ops"):
            keys = [f"{name}|{facet}" for name in scenarios]
            missing = [key for key in keys if key not in records]
            total += 1
            if missing:
                # Not a pass. A recording that never arrived means the scenario did not
                # reach the state it was meant to compare, and an absent value must never
                # read as "they matched".
                body.append(
                    f"FAIL [enumeration] {label} ({facet}) -- no recording for {missing}"
                )
                continue
            values = {records[key] for key in keys}
            if len(values) == 1:
                body.append(f"PASS [enumeration] {label} ({facet})")
            else:
                rendered = "\n      ".join(f"{key}: {records[key]}" for key in keys)
                body.append(
                    f"FAIL [enumeration] {label} ({facet}) -- these differ:\n      {rendered}"
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
