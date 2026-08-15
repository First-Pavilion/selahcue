/**
 * Reading the `?token=` off a landing URL, and the email check that guards the
 * request-a-fresh-link forms.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'

import { isMissingToken, readTokenParam } from '../src/lib/auth/tokenParam.ts'
import { EMAIL_INVALID, EMAIL_REQUIRED, validateEmail } from '../src/lib/auth/emailPolicy.ts'

describe('readTokenParam', () => {
  test('reads a plain token', () => {
    assert.equal(readTokenParam('SC-EMAILVERIFY-abc'), 'SC-EMAILVERIFY-abc')
  })

  test('trims, matching the API\'s own (raw_token or "").strip()', () => {
    // Mail clients and copy-paste routinely add whitespace around a pasted link.
    assert.equal(readTokenParam('  SC-EMAILVERIFY-abc \n'), 'SC-EMAILVERIFY-abc')
  })

  test('takes the first value when the query repeats ?token=', () => {
    // vue-router hands back an array for `?token=a&token=b`. Stringifying it would send
    // "a,b" to the API — garbage that fails for a reason nobody could diagnose.
    assert.equal(readTokenParam(['SC-A', 'SC-B']), 'SC-A')
  })

  test('absent, empty, null and whitespace-only all read as no token', () => {
    for (const value of [undefined, null, '', '   ', [], [null]]) {
      assert.equal(readTokenParam(value as never), '', `expected '' for ${JSON.stringify(value)}`)
    }
  })
})

describe('isMissingToken', () => {
  /**
   * The one token failure the client can distinguish on its own — which is why it gets
   * its own state (V6) instead of the merged failure state. Showing a red "this link
   * didn't work" to someone who simply bookmarked /verify would be a lie.
   */
  test('true for a bookmark or a stripped query', () => {
    assert.equal(isMissingToken(undefined), true)
    assert.equal(isMissingToken(''), true)
    assert.equal(isMissingToken('   '), true)
  })

  test('false when a token is present', () => {
    assert.equal(isMissingToken('SC-PASSWORDRESET-abc'), false)
  })
})

describe('validateEmail', () => {
  test('an empty address asks for one', () => {
    assert.equal(validateEmail(''), EMAIL_REQUIRED)
    assert.equal(validateEmail('   '), EMAIL_REQUIRED)
  })

  test('obvious nonsense is caught on the field, not by the API', () => {
    // `_require_valid_email` raises the SAME VALIDATION_FAILED as every token failure, so
    // an unchecked malformed address produces an error the page cannot attribute.
    assert.equal(validateEmail('not-an-email'), EMAIL_INVALID)
    assert.equal(validateEmail('missing@domain'), EMAIL_INVALID)
  })

  test('real-world addresses are accepted — the check must not lock people out', () => {
    for (const address of [
      'pastor@church.org',
      'first.last+tag@yourchurch.co.uk',
      'a@b.io',
      'admin@grace-community.church',
    ]) {
      assert.equal(validateEmail(address), '', `${address} should be accepted`)
    }
  })

  test('surrounding whitespace is tolerated', () => {
    assert.equal(validateEmail('  pastor@church.org  '), '')
  })
})
