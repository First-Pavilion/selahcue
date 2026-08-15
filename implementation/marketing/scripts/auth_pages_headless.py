#!/usr/bin/env python3
"""Behavioural state check for the /verify and /reset token-landing pages.

Serves the REAL production bundle from `dist/` over a local HTTP server with SPA
fallback, drives it in headless Chrome with a scripted `fetch` stub, and asserts the
rendered DOM for every state the design defines and every state the API can actually
produce.

This is the counterpart to `npm test`: those tests pin the pure logic (password policy,
error classification, token parsing), this one proves the pages built from that logic
actually render the right thing — real Vue, real router, real CSS, real focus and ARIA.
It follows the pattern already established by `scripts/operator_headless.py`.

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
    2  infrastructure problem (no dist, Chrome timeout, no results block)
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
EXPECTED_MIN_CHECKS = 465


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

  function json(body, status) {
    return new Response(JSON.stringify(body), {
      status: status || 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Scripted API. Keyed by scenario; every entry mirrors a real response shape from
  // selahcue_api (errors come back on HTTP 200 with extensions.code).
  var REPLIES = {
    'verify-success':      function () { return json({ data: { verifyEmail: { verified: true } } }); },
    'verify-invalid':      function () { return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] }); },
    'verify-loading':      function () { return new Promise(function () {}); },
    'verify-unreachable':  function () { throw new TypeError('Failed to fetch'); },
    'verify-resend':       function (op) {
      if (op === 'VerifyEmail') return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] });
      return json({ data: { resendVerification: { accepted: true } } });
    },
    // Lands on V3 so the resend form exists, then the driver submits a malformed address.
    'verify-bad-email':    function () { return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] }); },
    'verify-resend-fails': function (op) {
      if (op === 'VerifyEmail') return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] });
      // What actually happens today: the mutation does not exist, so the field is
      // unknown and the server collapses it to VALIDATION_FAILED.
      return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] });
    },
    'reset-success':       function () { return json({ data: { confirmPasswordReset: { reset: true } } }); },
    'reset-invalid':       function () { return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] }); },
    'reset-unreachable':   function () { throw new TypeError('Failed to fetch'); },
    'reset-fresh-link':    function (op) {
      if (op === 'ConfirmPasswordReset') return json({ errors: [{ extensions: { code: 'VALIDATION_FAILED' } }] });
      return json({ data: { requestPasswordReset: { accepted: true } } });
    }
  };

  window.fetch = function (url, init) {
    var body = {};
    try { body = JSON.parse((init && init.body) || '{}'); } catch (e) {}
    var op = (/mutation\s+(\w+)/.exec(body.query || '') || [])[1] || '';
    calls.push({ url: String(url), op: op, variables: body.variables || {}, raw: (init && init.body) || '' });
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

    // No stale copy from the superseded gap-fill doc.
    check('copy never says 15 minutes', lower.indexOf('15 minute') === -1);
    check('copy never says 8 characters', lower.indexOf('8 character') === -1);

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
      await wait(120);
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
            calls[0].raw.indexOf('mutation VerifyEmail($token') !== -1);
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
      check('resend called the assumed mutation name',
            calls.some(function (c) { return c.op === 'ResendVerification'; }));
      check('resend sent the email as a variable',
            calls.some(function (c) { return c.variables.email === 'pastor@yourchurch.org'; }));
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
]


def main() -> int:
    if not (DIST / "index.html").is_file():
        print(f"FAIL: no built bundle at {DIST}. Run `npm run build` first.")
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

        server.shutdown()

    fails = [line for line in body if line.startswith("FAIL")]
    for line in body:
        if line.startswith("FAIL"):
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
