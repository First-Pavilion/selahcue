/**
 * The create-account form's client-side rules, and the idempotency key it submits with.
 *
 * These matter for one reason: `register_customer_user` validates the idempotency key,
 * the email, the password, the org name and the country, and raises the SAME
 * `VALIDATION_FAILED` for every one of them. Anything this module lets through becomes an
 * error the UI cannot attribute — and the attribution a developer reaches for first is
 * the one that must never be made ("the email must be taken"), because a taken address
 * does not raise at all.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'

import {
  IDEMPOTENCY_KEY_PATTERN,
  MAX_ORG_NAME_LENGTH,
  collapseWhitespace,
  detectTimezone,
  isSubmittableSignup,
  newIdempotencyKey,
  validateSignup,
  type SignupFields,
} from '../src/lib/auth/signupPolicy.ts'
import { MIN_PASSWORD_LENGTH } from '../src/lib/auth/passwordPolicy.ts'
import { COUNTRY_CODES, guessCountry } from '../src/lib/auth/countries.ts'

/**
 * PREMISE PIN. The fixtures below are sized against these constants, so a change to
 * either would quietly turn "a 9-character password is refused" into a test of nothing.
 * Assert the premise where it is used, not only where it is declared.
 */
assert.equal(MIN_PASSWORD_LENGTH, 10, 'fixtures below assume the API minimum is 10')
assert.equal(MAX_ORG_NAME_LENGTH, 200, 'fixtures below assume CustomerOrg.name is 200')

const VALID: SignupFields = {
  orgName: 'Grace Community Church',
  displayName: 'Alex Morgan',
  email: 'pastor@yourchurch.org',
  password: 'a-good-passphrase',
  confirmPassword: 'a-good-passphrase',
  country: 'GB',
  agreeTerms: true,
}

describe('a complete, valid form is submittable', () => {
  test('validateSignup returns nothing for it', () => {
    // The positive control for the whole file. Without it, every refusal below is
    // satisfied equally well by a function that refuses everything.
    assert.deepEqual(validateSignup(VALID), {})
    assert.equal(isSubmittableSignup(VALID), true)
  })

  test('the optional display name may be empty', () => {
    assert.deepEqual(validateSignup({ ...VALID, displayName: '' }), {})
  })
})

describe('password — the rule the handoff gets wrong', () => {
  test('a 9-character password is refused before any request is possible', () => {
    const password = 'x'.repeat(MIN_PASSWORD_LENGTH - 1)
    assert.equal(password.length, 9)
    const errors = validateSignup({ ...VALID, password, confirmPassword: password })
    assert.ok(errors.password, 'a password one short of the API minimum must not be submittable')
    assert.match(errors.password, /at least 10 characters/)
  })

  test('there is NO complexity rule — all-lowercase, no digits, is accepted', () => {
    // `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §3c/§4d asks for "one uppercase letter and
    // one number". `_validate_password` is length-only. Enforcing the doc's rule would
    // reject passwords the server accepts, which is a lockout dressed as a safety check.
    assert.deepEqual(
      validateSignup({
        ...VALID,
        password: 'allslowercasenodigits',
        confirmPassword: 'allslowercasenodigits',
      }),
      {},
    )
  })

  test('a mismatched confirmation is refused', () => {
    const errors = validateSignup({ ...VALID, confirmPassword: 'a-different-one' })
    assert.ok(errors.confirmPassword)
  })
})

describe('country — the field the handoff omits entirely', () => {
  test('an empty country is refused', () => {
    // §4a lists four fields and country is not among them. A form built from that list
    // fails EVERY signup with an error that looks exactly like a bad password.
    assert.ok(validateSignup({ ...VALID, country: '' }).country)
  })

  test('a code the API would reject is refused here first', () => {
    for (const country of ['G', 'GBR', 'ZZ', '  ']) {
      assert.ok(
        validateSignup({ ...VALID, country }).country,
        `"${country}" should not have been submittable`,
      )
    }
  })

  test('a lowercase code is accepted and normalised, not rejected', () => {
    // The select emits uppercase, but a restored form value or an autofill may not.
    assert.deepEqual(validateSignup({ ...VALID, country: 'gb' }), {})
  })

  test('the code list is real and guessCountry only ever returns a member of it', () => {
    assert.ok(COUNTRY_CODES.includes('GB'))
    assert.ok(COUNTRY_CODES.includes('US'))
    assert.ok(COUNTRY_CODES.includes('NG'))
    assert.ok(COUNTRY_CODES.length > 200, `expected a full ISO list, got ${COUNTRY_CODES.length}`)
    for (const locale of ['en-GB', 'en-US', 'fr', 'not-a-locale', '']) {
      const guess = guessCountry(locale)
      assert.ok(
        guess === '' || COUNTRY_CODES.includes(guess),
        `guessCountry(${locale}) produced "${guess}", which the form would reject`,
      )
    }
  })
})

describe('org name', () => {
  test('a blank or whitespace-only name is refused', () => {
    assert.ok(validateSignup({ ...VALID, orgName: '' }).orgName)
    assert.ok(validateSignup({ ...VALID, orgName: '     ' }).orgName)
  })

  test('length is measured on the COLLAPSED name, as the server measures it', () => {
    // The service runs `" ".join(value.strip().split())` before `full_clean`, so a name
    // padded with runs of spaces can be under the limit after collapsing. Measuring the
    // raw input would reject a name the server would have taken.
    const padded = `  ${'a'.repeat(MAX_ORG_NAME_LENGTH)}   `
    assert.deepEqual(validateSignup({ ...VALID, orgName: padded }), {})

    const tooLong = 'a'.repeat(MAX_ORG_NAME_LENGTH + 1)
    assert.ok(validateSignup({ ...VALID, orgName: tooLong }).orgName)
  })

  test('length is counted by code point, as Python counts it', () => {
    // JS `.length` counts a surrogate pair twice, so 101 non-BMP characters measure 202
    // in JS and 101 in Python — rejected here, accepted there.
    const emoji = '🎺'.repeat(MAX_ORG_NAME_LENGTH)
    assert.equal(emoji.length, MAX_ORG_NAME_LENGTH * 2)
    assert.deepEqual(validateSignup({ ...VALID, orgName: emoji }), {})
  })

  test('collapseWhitespace matches the service transform', () => {
    assert.equal(collapseWhitespace('  Grace   Community  Church '), 'Grace Community Church')
    assert.equal(collapseWhitespace('\n\tGrace\n'), 'Grace')
    assert.equal(collapseWhitespace('    '), '')
  })
})

describe('terms', () => {
  test('an unchecked box is a reported error, not a disabled button', () => {
    // A disabled primary action gives a keyboard user a dead control and no reason for
    // it. AUTH handoff A12 specifies this message for exactly that reason.
    const errors = validateSignup({ ...VALID, agreeTerms: false })
    assert.equal(errors.terms, 'Accept the terms to continue.')
  })
})

describe('every field is reported at once', () => {
  test('a form wrong in five ways reports all five', () => {
    // Walking someone down a form one error at a time is the slowest possible way to
    // fill it in, and the form renders them together.
    const errors = validateSignup({
      orgName: '',
      displayName: '',
      email: 'not-an-email',
      password: 'short',
      confirmPassword: 'different',
      country: '',
      agreeTerms: false,
    })
    assert.ok(errors.orgName)
    assert.ok(errors.email)
    assert.ok(errors.password)
    assert.ok(errors.confirmPassword)
    assert.ok(errors.country)
    assert.ok(errors.terms)
  })
})

describe('the idempotency key', () => {
  test('the pattern is the API\'s, character for character', () => {
    // `validate_idempotency_key` in graphql/context.py. A key this module generates but
    // the API rejects fails the whole signup on a field the user cannot see or fix.
    assert.equal(IDEMPOTENCY_KEY_PATTERN.source, '^[A-Za-z0-9._:-]{12,128}$')
  })

  test('generated keys satisfy it, and are not repeated', () => {
    const keys = new Set<string>()
    for (let i = 0; i < 200; i += 1) {
      const key = newIdempotencyKey()
      assert.match(key, IDEMPOTENCY_KEY_PATTERN)
      keys.add(key)
    }
    // A colliding key would alias two different churches' signups onto one another,
    // which is why `Math.random` is deliberately not a fallback source.
    assert.equal(keys.size, 200)
  })

  test('it throws rather than returning a key the API would reject', () => {
    // Positive control for the verification step inside the generator: without this, a
    // future refactor could return an unchecked value and nothing would notice until
    // every signup started failing in production.
    const realCrypto = globalThis.crypto
    try {
      Object.defineProperty(globalThis, 'crypto', {
        value: { randomUUID: () => 'too-short', getRandomValues: undefined },
        configurable: true,
      })
      assert.throws(() => newIdempotencyKey(), /secure random/)
    } finally {
      Object.defineProperty(globalThis, 'crypto', { value: realCrypto, configurable: true })
    }
  })
})

describe('timezone', () => {
  test('always returns something the column will hold', () => {
    const zone = detectTimezone()
    assert.equal(typeof zone, 'string')
    assert.notEqual(zone, '')
    assert.ok(zone.length <= 64, `"${zone}" is longer than CustomerOrg.timezone allows`)
  })
})
