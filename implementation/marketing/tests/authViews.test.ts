/**
 * Source-level controls on the three auth views.
 *
 * These assert on the FILES rather than on rendered output, because what they guard
 * cannot be seen in a render. Raised as LOW-3 by Sana: the headless suite runs Chrome
 * with `--virtual-time-budget`, which fast-forwards timers, so an address-keyed
 * `setTimeout` would render identical text after different wall-clock delays. The
 * enumeration comparison now measures elapsed virtual time as a fourth facet — but the
 * cheaper and more direct guard is simply that these views contain no timers at all, and
 * that guard belongs where it can be stated plainly.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'
import { readFileSync } from 'node:fs'

const VIEWS = ['views/SignInView.vue', 'views/SignUpView.vue', 'views/ForgotPasswordView.vue'] as const

/**
 * Everything else on the auth path where a timer would be just as effective an oracle.
 *
 * Quinn's LOW-2: once this file became the named control for the timing channel, covering
 * only three view files left a hole the size of the rest of the feature — a delay added
 * to `account.ts` or `sessionStore.ts` sits directly in the request path and is invisible
 * to a control that reads the views.
 *
 * `graphql.ts` is deliberately NOT in this list: it uses `setTimeout` legitimately, for
 * the request and bootstrap deadlines. It gets its own, stronger assertion below.
 */
const AUTH_PATH_MODULES = [
  'lib/api/account.ts',
  'lib/auth/session.ts',
  'lib/auth/sessionStore.ts',
  'lib/auth/signupPolicy.ts',
  'lib/auth/redirect.ts',
  'components/auth/AuthShell.vue',
  'components/auth/AuthBanner.vue',
  'components/auth/StatusDisc.vue',
] as const

function source(relative: string): string {
  return readFileSync(new URL(`../src/${relative}`, import.meta.url), 'utf8')
}

/**
 * The file with its comments removed.
 *
 * Necessary, and the first version of this file proved it: these views DOCUMENT the
 * simulated code they replaced — "a `setTimeout(…, 1000)` that faked every outcome, a
 * hardcoded `error@test.com` failure" — so a naive grep failed on the prose explaining
 * why the thing is banned. Stripping comments is what makes these assertions about code.
 *
 * Crude on purpose: it does not parse, and a `//` inside a string literal would be
 * over-stripped. That direction is safe here (it can only remove more), and
 * `codeIsIntact` below refuses to let the stripping quietly empty the file.
 */
function codeOnly(view: string): string {
  return source(view)
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1 ')
}

/**
 * Guard against the guard being vacuous.
 *
 * Every assertion below is of the form "this string is absent". If `codeOnly` ever
 * over-stripped — a regex change, a syntax it mishandles — it would return something
 * close to empty and every one of them would pass while checking nothing. This asserts
 * the stripped text still contains the view's real machinery.
 */
function codeIsIntact(name: string, code: string): void {
  if (name.endsWith('.vue')) {
    // A component's proof of life is its template. `AuthShell.vue` is pure markup — its
    // `<script setup>` holds nothing but the comment explaining the design — so requiring
    // a declaration there would fail on a file that is entirely correct.
    assert.ok(code.includes('<template>'), `${name}: stripping removed the template`)
  } else {
    assert.ok(
      /\b(function|const|export)\b/.test(code),
      `${name}: stripping removed the script`,
    )
  }
  assert.ok(code.length > 150, `${name}: stripping left only ${code.length} chars`)
}

describe('no auth view can fake, delay or vary an outcome', () => {
  test('none of them contains a timer', () => {
    // This is the named control for C-014 and for the timing channel.
    //
    // The view this replaced ran every outcome through `setTimeout(…, 1000)`, including a
    // hardcoded `error@test.com` failure — a literal address-keyed branch behind a delay.
    // A timer here is how that comes back: two branches with identical copy that settle at
    // different times leak exactly what the copy is careful not to.
    //
    // Scoped to these three. `VerifyView.vue` legitimately uses one to hold its spinner
    // for a 300ms minimum (design §4.1); that is a display floor applied to every
    // outcome equally, not an outcome being simulated.
    for (const view of [...VIEWS, ...AUTH_PATH_MODULES]) {
      const text = codeOnly(view)
      codeIsIntact(view, text)
      for (const timer of ['setTimeout', 'setInterval', 'requestIdleCallback']) {
        assert.ok(
          !text.includes(timer),
          `${view} uses ${timer}. Outcomes here come from the API, never from a clock.`,
        )
      }
    }
  })

  test('none of them inspects an email address against a literal', () => {
    // The other half of the same defect. `email === 'error@test.com'` was the shape of
    // the simulation, and any branch keyed on WHO the user is is the enumeration oracle
    // arriving through the front door.
    //
    // THIS BAN USED TO BE NARROWER THAN IT READ. It matched only a full address in
    // quotes — `@…(com|org|test|net)'` — so a QA mutation of the form
    // `submittedEmail.startsWith('second-attempt')` walked straight past it while doing
    // exactly what the test claims to forbid. Both shapes are refused now: any
    // string-inspection method called on an address-bearing ref, and any direct
    // comparison of one to a literal.
    const ADDRESS_REFS = 'email|submittedEmail|sentToEmail|address|sentToEmail'
    const INSPECTORS = 'startsWith|endsWith|includes|indexOf|lastIndexOf|search|match|slice|substring|charAt'
    const inspection = new RegExp(`\\b(?:${ADDRESS_REFS})(?:\\.value)?\\s*\\.\\s*(?:${INSPECTORS})\\s*\\(`, 'i')
    const comparison = new RegExp(`\\b(?:${ADDRESS_REFS})(?:\\.value)?\\s*[=!]==?\\s*['"\`]`, 'i')
    const fullAddress = /@[\w.-]+\.(com|org|test|net)['"\`]/

    for (const view of VIEWS) {
      const text = codeOnly(view).replace(/placeholder="[^"]*"/g, '')
      codeIsIntact(view, text)
      assert.ok(!inspection.test(text), `${view} inspects an email address as a string`)
      assert.ok(!comparison.test(text), `${view} compares an email address to a literal`)
      assert.ok(!fullAddress.test(text), `${view} contains a hardcoded email address`)
    }
  })

  test('the literal ban actually matches the shapes it claims to', () => {
    // Positive control on the regexes themselves, because the previous version of this
    // test passed for a year of code review while missing the shape QA used to break it.
    // Asserting on samples means "no match" in the test above cannot be the regex being
    // quietly wrong rather than the views being clean.
    const ADDRESS_REFS = 'email|submittedEmail|sentToEmail|address'
    const INSPECTORS = 'startsWith|endsWith|includes|indexOf|lastIndexOf|search|match|slice|substring|charAt'
    const inspection = new RegExp(`\\b(?:${ADDRESS_REFS})(?:\\.value)?\\s*\\.\\s*(?:${INSPECTORS})\\s*\\(`, 'i')
    const comparison = new RegExp(`\\b(?:${ADDRESS_REFS})(?:\\.value)?\\s*[=!]==?\\s*['"\`]`, 'i')

    // Quinn's mutation, verbatim, plus the shape the deleted simulation used.
    assert.ok(inspection.test("submittedEmail.startsWith('second-attempt')"))
    assert.ok(inspection.test('email.value.includes("nowhere")'))
    assert.ok(inspection.test("sentToEmail.indexOf('nobody') !== -1"))
    assert.ok(comparison.test("email.value === 'error@test.com'"))
    assert.ok(comparison.test('email !== "someone"'))

    // And does NOT match the legitimate uses these views actually make, or the ban would
    // be unusable and get deleted rather than fixed.
    assert.ok(!inspection.test('email.value.trim()'))
    assert.ok(!inspection.test('validateEmail(email.value)'))
    assert.ok(!comparison.test("password.value === ''"))
  })

  test('every view reaches the network only through the shared seam', () => {
    // "No second transport path is introduced" (acceptance criterion), asserted rather
    // than reviewed. A raw fetch here would bypass the CSRF bootstrap, the error-envelope
    // handling and the NETWORK classification all at once.
    for (const view of VIEWS) {
      const text = codeOnly(view)
      codeIsIntact(view, text)
      assert.ok(!/\bfetch\s*\(/.test(text), `${view} calls fetch directly`)
      assert.ok(!text.includes('XMLHttpRequest'), `${view} uses XMLHttpRequest`)
      assert.ok(
        text.includes("from '@/lib/api/account.ts'") || text.includes("from '@/lib/auth/sessionStore.ts'"),
        `${view} imports no API wrapper — check this test still points at a real view`,
      )
    }
  })
})

describe('the transport seam', () => {
  const TRANSPORT = 'lib/api/graphql.ts'

  test('its timers are deadlines, not delays', () => {
    // `graphql.ts` is the one module on this path that legitimately uses `setTimeout`:
    // the request deadline and the CSRF bootstrap deadline. It cannot join the blanket
    // ban, so it gets the assertion that actually matters — every timer here is armed
    // from a module CONSTANT, never from anything a caller supplied.
    const text = codeOnly(TRANSPORT)
    codeIsIntact(TRANSPORT, text)

    // To end of LINE, not a balanced-paren match and not a fixed character window.
    //
    // `[^)]*` stops at the arrow function's own closing paren, so every timer reads as
    // `setTimeout((` and the delay is never examined. A fixed window overshoots the other
    // way: it can reach a deadline constant on a NEIGHBOURING line and pass a timer that
    // has nothing to do with one. Both real call sites are single-line, and if one is ever
    // wrapped the count assertion below fails loudly rather than the check going quiet.
    const timers = text.match(/setTimeout\([^\n]*/g) ?? []
    assert.equal(timers.length, 2, `expected exactly the two deadlines, found ${timers.length}`)
    for (const timer of timers) {
      assert.ok(
        /DEFAULT_TIMEOUT_MS|CSRF_BOOTSTRAP_TIMEOUT_MS|options\.timeoutMs/.test(timer),
        `a timer armed from something other than a deadline constant: ${timer.slice(0, 90)}`,
      )
    }
  })

  test('it knows nothing about email addresses', () => {
    // The strongest control available for a generic transport: it cannot branch on
    // registration status because it has no concept of an address to branch on. If this
    // ever fails, something has taught the transport layer who the user is.
    const text = codeOnly(TRANSPORT)
    assert.ok(!/\bemail\b/i.test(text), 'the transport seam references an email address')
  })
})
