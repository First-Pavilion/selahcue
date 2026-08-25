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

const VIEWS = ['SignInView.vue', 'SignUpView.vue', 'ForgotPasswordView.vue'] as const

function source(view: string): string {
  return readFileSync(new URL(`../src/views/${view}`, import.meta.url), 'utf8')
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
function codeIsIntact(view: string, code: string): void {
  assert.ok(code.includes('<template>'), `${view}: stripping removed the template`)
  assert.ok(code.includes('async function'), `${view}: stripping removed the script`)
  assert.ok(code.length > 1500, `${view}: stripping left only ${code.length} chars`)
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
    for (const view of VIEWS) {
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

  test('none of them tests an email address against a literal', () => {
    // The other half of the same defect. `email === 'error@test.com'` was the shape of
    // the simulation, and any comparison of an address to a hardcoded string is a branch
    // keyed on who the user is.
    for (const view of VIEWS) {
      const text = codeOnly(view)
      codeIsIntact(view, text)
      assert.ok(
        !/@[\w.-]+\.(com|org|test|net)['"`]/.test(text.replace(/placeholder="[^"]*"/g, '')),
        `${view} compares an address to a literal, outside a placeholder attribute.`,
      )
    }
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
