/**
 * Copy that more than one auth page says must have exactly one definition.
 *
 * MEDIUM-6 (Cody). Five views shipped byte-identical strings — `RESEND_FAILED` in three
 * files, `RESEND_RATE_LIMITED` in three, the rate-limit banner in two, and the
 * "Only the newest link works" / "Didn't arrive?" pair in five. The reasoning against that
 * is already written in the views: `SignInView.vue` holds its rejection copy as a constant
 * "so there is no seam for a future edit to slip a second variant into". The reasoning was
 * applied within each file and not across them, and five copies is five seams.
 *
 * It matters here more than it usually would. These pages exist to be indistinguishable
 * from one another in the ways that could reveal whether an address is registered, so
 * "the two pages agree word for word" is the property under test, not a preference. A
 * well-meant edit to one page's rate-limit copy that missed the other would be a
 * difference between two states the API answers identically.
 *
 * This is the control that makes a sixth copy a failing test rather than something a
 * reviewer has to notice. It consumes `messages.ts` itself — the shared strings are read
 * from the module, not restated here — so a mutation to a message is not something this
 * file can silently disagree with.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'
import { readFileSync } from 'node:fs'
import * as MESSAGES from '../src/lib/auth/messages.ts'

const AUTH_VIEWS = [
  'SignInView.vue',
  'SignUpView.vue',
  'ForgotPasswordView.vue',
  'VerifyView.vue',
  'ResetView.vue',
] as const

function view(name: string): string {
  return readFileSync(new URL(`../src/views/${name}`, import.meta.url), 'utf8')
}

/** Collapse the whitespace a template wraps across lines, so a re-wrap is not a copy. */
function flat(text: string): string {
  return text.replace(/\s+/g, ' ')
}

describe('shared auth copy has one definition', () => {
  test('the module actually holds shared copy', () => {
    // The premise. Without it, emptying `messages.ts` would make every assertion below
    // pass by having nothing to look for.
    const values = Object.values(MESSAGES).filter((value) => typeof value === 'string')
    assert.ok(values.length >= 6, `expected the shared copy, found ${values.length} strings`)
    for (const value of values) {
      assert.ok(value.length > 10, `a shared message is suspiciously short: ${value}`)
    }
  })

  test('no view re-declares a shared message as a literal', () => {
    const offences: string[] = []
    for (const name of AUTH_VIEWS) {
      const source = flat(view(name))
      for (const [key, value] of Object.entries(MESSAGES)) {
        if (typeof value !== 'string') continue
        if (source.includes(flat(value))) {
          offences.push(`${name} contains a second copy of ${key}: "${value}"`)
        }
      }
    }
    assert.deepEqual(
      offences,
      [],
      `shared copy must be imported from '@/lib/auth/messages.ts', not repeated:\n  ` +
        offences.join('\n  '),
    )
  })

  test('the views that use a shared message import it', () => {
    // The other half. Without this, a view could satisfy the test above by DELETING the
    // copy rather than by importing it — which would be a regression the first test reads
    // as a pass.
    let importing = 0
    for (const name of AUTH_VIEWS) {
      if (view(name).includes("from '@/lib/auth/messages.ts'")) importing += 1
    }
    assert.equal(
      importing,
      AUTH_VIEWS.length,
      `${AUTH_VIEWS.length - importing} auth view(s) reference no shared copy at all — ` +
        'check the copy was moved rather than dropped',
    )
  })

  test('the rate-limit copy never implies the account exists', () => {
    // The reason `RESEND_RATE_LIMITED` is worded the way it is, asserted rather than left
    // to a comment. A limiter that spent its budget before looking the account up is not
    // evidence the account is real, and copy like "too many requests for this account"
    // would claim it is.
    const rateLimited = [MESSAGES.RESEND_RATE_LIMITED, MESSAGES.RATE_LIMITED_BODY].join(' ')
    for (const claim of ['this account', 'your account', 'that address', 'this address']) {
      assert.ok(
        !rateLimited.toLowerCase().includes(claim),
        `rate-limit copy says "${claim}", which describes what the server knows rather ` +
          'than what the caller did',
      )
    }
  })
})
