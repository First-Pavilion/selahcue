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
  DISPLAY_NAME_TOO_LONG,
  EMAIL_TOO_LONG,
  IDEMPOTENCY_KEY_PATTERN,
  MAX_DISPLAY_NAME_LENGTH,
  MAX_ORG_NAME_LENGTH,
  MAX_SIGNUP_EMAIL_LENGTH,
  MAX_TIMEZONE_LENGTH,
  collapseWhitespace,
  detectTimezone,
  isSubmittableSignup,
  newIdempotencyKey,
  validateSignup,
  type SignupFields,
} from '../src/lib/auth/signupPolicy.ts'
import { MAX_EMAIL_LENGTH, serverWouldAcceptEmail } from '../src/lib/auth/emailPolicy.ts'
import { MIN_PASSWORD_LENGTH } from '../src/lib/auth/passwordPolicy.ts'
import { COUNTRY_CODES, countryOptions, guessCountry } from '../src/lib/auth/countries.ts'

/**
 * PREMISE PIN. The fixtures below are sized against these constants, so a change to
 * either would quietly turn "a 9-character password is refused" into a test of nothing.
 * Assert the premise where it is used, not only where it is declared.
 */
assert.equal(MIN_PASSWORD_LENGTH, 10, 'fixtures below assume the API minimum is 10')
assert.equal(MAX_ORG_NAME_LENGTH, 200, 'fixtures below assume CustomerOrg.name is 200')
/**
 * LOW-9 (Quinn), and the reason this line is not optional. The display-name boundary
 * fixtures are sized OFF `MAX_DISPLAY_NAME_LENGTH`, which is the only honest way to test a
 * boundary — and it means multiplying the cap by a thousand moves the fixtures with it and
 * every assertion still passes. She did exactly that, in the compiler-invisible form, and
 * `npm run build`, `npm test` and `npm run test:states` were all green with the
 * `DISPLAY_NAME_TOO_LONG` branch unreachable. Pinning the VALUE here is what turns that
 * mutation red; the fixtures stay derived so they still test the boundary and not a number.
 */
assert.equal(
  MAX_DISPLAY_NAME_LENGTH,
  200,
  'fixtures below assume CustomerUser.display_name is 200',
)

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
    // POSITIVE VALUES FIRST. The sweep below allows `''`, which is a free pass: Quinn
    // replaced the whole body of `guessCountry` with `return ''` and `npx vue-tsc -b`,
    // `npm test` and `npm run test:states` all stayed green — the country pre-selection
    // could die for every user with no gate noticing. These two rows are what make the
    // function's actual job load-bearing.
    assert.equal(guessCountry('en-GB'), 'GB')
    assert.equal(guessCountry('en-US'), 'US')

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
    // THE SCOPE OF THIS TEST, stated plainly, because it used to overclaim.
    //
    // Every fixture here is drawn from the region where JavaScript and Python already
    // agree — spaces, tabs, newlines. That made "matches the service transform" a claim
    // this test could not falsify: it passed for the old `/\s+/` implementation, which
    // disagreed with Python on six characters. Sana found the divergence by inspection,
    // not by this test.
    //
    // So these stay as the ordinary-input regression they always were, and the CLAIM is
    // tested where it can actually fail: `tests/serviceText.test.ts` compares the two
    // classifications over all 1,114,112 code points against CPython's own answer. This
    // one asserts the shape of the collapse; that one asserts the character set.
    assert.equal(collapseWhitespace('  Grace   Community  Church '), 'Grace Community Church')
    assert.equal(collapseWhitespace('\n\tGrace\n'), 'Grace')
    assert.equal(collapseWhitespace('    '), '')

    // One fixture FROM the divergence set, so the two files fail together if this
    // function is ever pointed back at a JavaScript-native whitespace rule.
    assert.equal(
      collapseWhitespace('\u001c\u001c\u001c'),
      '',
      'an all-separator org name is empty to the server and must be empty here',
    )
    assert.equal(collapseWhitespace('Grace\u0085Community'), 'Grace Community')
    assert.equal(
      collapseWhitespace('Grace\ufeffCommunity'),
      'Grace\ufeffCommunity',
      'U+FEFF is not whitespace to Python, so collapsing it would validate a different string',
    )
  })

  test('an org name of only information separators is refused, as the server refuses it', () => {
    // The end-to-end consequence of the divergence, at the surface a user meets it on.
    // Before the fix this passed validation, was sent, and came back as an
    // undifferentiated VALIDATION_FAILED with nothing pointing at the field.
    assert.ok(validateSignup({ ...VALID, orgName: '\u001c\u001c\u001c' }).orgName)
    assert.ok(validateSignup({ ...VALID, orgName: '\u0085' }).orgName)
  })
})

describe('display name — optional, but capped like every other CharField', () => {
  /**
   * LOW-9 (Quinn): `DISPLAY_NAME_TOO_LONG` had NO test of any kind. `validateSignup` gives
   * `orgName` a required-check AND a cap and gives `displayName` only the cap, so the cap
   * is the whole of the rule here — and an unexercised branch is not a rule, it is a
   * sentence in a file. The boundary gets the same treatment org name already gets.
   */
  test('exactly at the cap submits, and one character over is refused', () => {
    const atCap = 'a'.repeat(MAX_DISPLAY_NAME_LENGTH)
    assert.deepEqual(validateSignup({ ...VALID, displayName: atCap }), {})

    const overCap = 'a'.repeat(MAX_DISPLAY_NAME_LENGTH + 1)
    assert.deepEqual(validateSignup({ ...VALID, displayName: overCap }), {
      displayName: DISPLAY_NAME_TOO_LONG,
    })
    // The MESSAGE, not just the presence of one: it names the number the user has to get
    // under, and a cap that drifted from the model would ship a number that is a lie.
    assert.match(DISPLAY_NAME_TOO_LONG, /\b200 characters or fewer\b/)
  })

  test('length is measured collapsed and by code point, as the server measures it', () => {
    // Both halves of the same rule org name gets, because `displayName` runs through the
    // same `collapseWhitespace` and the same `codePointLength` and could lose either.
    const padded = `   ${'a'.repeat(MAX_DISPLAY_NAME_LENGTH)}   `
    assert.deepEqual(validateSignup({ ...VALID, displayName: padded }), {})

    const emoji = '🎺'.repeat(MAX_DISPLAY_NAME_LENGTH)
    assert.equal(emoji.length, MAX_DISPLAY_NAME_LENGTH * 2, 'the premise: JS counts these double')
    assert.deepEqual(validateSignup({ ...VALID, displayName: emoji }), {})
  })
})

describe('isSubmittableSignup answers in BOTH directions', () => {
  /**
   * LOW-9 (Quinn): the only assertion this export had was `=== true` for a valid form, and
   * `Object.keys(...).length === 0` mutated to `>= 0` — always true — passed all three
   * gates. A predicate tested in one direction is not tested: "the button is enabled when
   * the form is good" and "the button is always enabled" are the same green.
   *
   * Driven off `validateSignup` rather than off a second list of bad forms, so the two
   * cannot disagree about what invalid means: the row asserts the wrapper agrees with the
   * function it wraps, on a form the function has just been shown to reject.
   */
  test('a valid form is submittable and each broken one is not', () => {
    assert.equal(isSubmittableSignup(VALID), true)

    const broken: Array<[string, Partial<SignupFields>]> = [
      ['no org name', { orgName: '' }],
      ['a display name over the cap', { displayName: 'a'.repeat(MAX_DISPLAY_NAME_LENGTH + 1) }],
      ['a malformed address', { email: 'not-an-email' }],
      ['a short password', { password: 'short', confirmPassword: 'short' }],
      ['a mismatched confirmation', { confirmPassword: 'a-different-one' }],
      ['no country', { country: '' }],
      ['unticked terms', { agreeTerms: false }],
    ]
    for (const [why, override] of broken) {
      const fields = { ...VALID, ...override }
      // The premise, first: if `validateSignup` stopped rejecting this form the row below
      // would be asserting that a VALID form is unsubmittable, which is a different and
      // wrong test. Assert what went unexercised, not just the verdict.
      assert.notDeepEqual(
        validateSignup(fields),
        {},
        `validateSignup accepts a form with ${why} — the submittability row below no ` +
          'longer exercises a rejection',
      )
      assert.equal(
        isSubmittableSignup(fields),
        false,
        `isSubmittableSignup says a form with ${why} may be submitted`,
      )
    }
  })
})

describe('email — the one signup rule `emailPolicy.ts` does not mirror', () => {
  /**
   * `validate_email` caps an address at 320 characters. The MODEL FIELD caps it at 254,
   * and signup is the only surface that writes to the model field. Between those two
   * numbers sits a band of addresses that pass every rule the client had and die at
   * `full_clean` as an unattributed `VALIDATION_FAILED` — the FR-552 dead end reached
   * through a legal address rather than a typo.
   */
  const local = (n: number) => 'a'.repeat(n - '@example.com'.length)
  const at254 = `${local(MAX_SIGNUP_EMAIL_LENGTH)}@example.com`
  const at255 = `${local(MAX_SIGNUP_EMAIL_LENGTH + 1)}@example.com`

  test('the band this rule exists for is real, and the two caps are different numbers', () => {
    // THE PREMISE, pinned first. If the model cap ever equalled the validator cap, every
    // assertion below would still pass while testing nothing, because `validateEmail`
    // would already have refused these addresses for their length.
    assert.equal(MAX_SIGNUP_EMAIL_LENGTH, 254, 'EmailField() default max_length')
    assert.ok(
      MAX_SIGNUP_EMAIL_LENGTH < MAX_EMAIL_LENGTH,
      'the model cap must be BELOW the validator cap or this rule is unreachable',
    )
    assert.equal(at254.length, MAX_SIGNUP_EMAIL_LENGTH)
    assert.equal(at255.length, MAX_SIGNUP_EMAIL_LENGTH + 1)
    // And both are addresses `validate_email` accepts — measured through the mirror, so
    // this stays true if the mirror changes. That is what makes 255 a SIGNUP-only refusal.
    assert.equal(serverWouldAcceptEmail(at254), true)
    assert.equal(
      serverWouldAcceptEmail(at255),
      true,
      'a 255-character address is valid to `validate_email`; only the model field refuses ' +
        'it, which is the entire reason this check is here and not in emailPolicy.ts',
    )
  })

  test('254 characters submits and 255 is refused with a message about the length', () => {
    assert.deepEqual(validateSignup({ ...VALID, email: at254 }), {})
    assert.deepEqual(validateSignup({ ...VALID, email: at255 }), { email: EMAIL_TOO_LONG })
    assert.equal(isSubmittableSignup({ ...VALID, email: at255 }), false)
  })

  test('the length is measured on the normalised address, as the server measures it', () => {
    // The server stores `_normalize_email(raw)`, and `full_clean` measures what is stored.
    // Padding with whitespace must not change the verdict in either direction.
    assert.deepEqual(validateSignup({ ...VALID, email: `   ${at254}   ` }), {})
    assert.deepEqual(validateSignup({ ...VALID, email: `   ${at255}   ` }), {
      email: EMAIL_TOO_LONG,
    })
  })

  test('a malformed address is still called malformed, not long', () => {
    // Ordering control. A 260-character address with a digit TLD is wrong in two ways and
    // must be reported as the one the user can see.
    const malformedAndLong = `${'a'.repeat(254)}@b.12`
    assert.ok(malformedAndLong.length > MAX_SIGNUP_EMAIL_LENGTH)
    assert.notEqual(validateSignup({ ...VALID, email: malformedAndLong }).email, EMAIL_TOO_LONG)
    assert.ok(validateSignup({ ...VALID, email: malformedAndLong }).email)
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

/**
 * Swap in an environment that names a specific zone, run `body`, put the real one back.
 *
 * `detectTimezone` reads a global, so proving it READS anything needs a global whose answer
 * is known. Restored in a `finally` because a leaked stub would silently change what every
 * later test in this process observes.
 */
function withTimeZone(zone: unknown, body: () => void): void {
  const realIntl = globalThis.Intl
  try {
    Object.defineProperty(globalThis, 'Intl', {
      value: {
        ...realIntl,
        DateTimeFormat: function DateTimeFormatStub() {
          return { resolvedOptions: () => ({ timeZone: zone }) }
        },
      },
      configurable: true,
    })
    body()
  } finally {
    Object.defineProperty(globalThis, 'Intl', { value: realIntl, configurable: true })
  }
}

/**
 * `countryOptions` had NO test of any kind, and it has the identical shape to the
 * `detectTimezone` hole: an `Intl` read whose failure path returns something valid.
 *
 * Deleting the whole `Intl.DisplayNames` lookup leaves a select full of two-letter codes.
 * Every option still submits, every existing assertion still passes, and the form is
 * materially worse for every user — 249 codes to hunt through instead of names. Found while
 * closing the timezone gap, because "check whether any other detection here has the same
 * gap" is the actual lesson, not "fix this one function".
 */
describe('country options', () => {
  test('the labels come from Intl.DisplayNames, not from the codes', () => {
    // Stubbed rather than asserted against real ICU data, so the control means the same
    // thing on a runner with a minimal ICU build as it does here. What is being proved is
    // that the lookup's ANSWER reaches the option list.
    const realIntl = globalThis.Intl
    try {
      Object.defineProperty(globalThis, 'Intl', {
        value: {
          ...realIntl,
          DisplayNames: function DisplayNamesStub() {
            return { of: (code: string) => `NAME_FOR_${code}` }
          },
        },
        configurable: true,
      })
      const options = countryOptions()
      const gb = options.find((option) => option.code === 'GB')
      assert.ok(gb, 'GB is missing from the option list')
      assert.equal(
        gb.label,
        'NAME_FOR_GB',
        'the label did not come from Intl.DisplayNames. If the lookup has been removed, ' +
          'the select shows two-letter codes and nothing else in the suite notices.',
      )
    } finally {
      Object.defineProperty(globalThis, 'Intl', { value: realIntl, configurable: true })
    }
  })

  test('every code is offered exactly once, and none of them is unselectable', () => {
    const options = countryOptions()
    assert.equal(options.length, COUNTRY_CODES.length)
    assert.equal(new Set(options.map((option) => option.code)).size, COUNTRY_CODES.length)
    // A label the select cannot render is as bad as a missing option.
    for (const option of options) {
      assert.ok(option.label !== '', `${option.code} has an empty label`)
    }
    // And every offered code must be one the form will actually accept, or the select can
    // put the user into a state `validateSignup` refuses.
    for (const option of options) {
      assert.deepEqual(validateSignup({ ...VALID, country: option.code }), {})
    }
  })

  test('a missing or throwing Intl.DisplayNames degrades to codes rather than an empty select', () => {
    // The negative half. A select full of codes is worse than one full of names and far
    // better than a form that cannot be submitted.
    const realIntl = globalThis.Intl
    try {
      Object.defineProperty(globalThis, 'Intl', {
        value: {
          ...realIntl,
          DisplayNames: function ThrowingDisplayNames() {
            throw new Error('no DisplayNames here')
          },
        },
        configurable: true,
      })
      const options = countryOptions()
      assert.equal(options.length, COUNTRY_CODES.length)
      const gb = options.find((option) => option.code === 'GB')
      assert.ok(gb)
      assert.equal(gb.label, 'GB')
    } finally {
      Object.defineProperty(globalThis, 'Intl', { value: realIntl, configurable: true })
    }
  })
})

describe('timezone', () => {
  test('it reports the zone the environment names, not a constant', () => {
    // POSITIVE VALUES FIRST. This is the same lesson `guessCountry` has written above it,
    // about 150 lines up, under a comment with that exact heading — and it was not applied
    // to the function next door.
    //
    // Quinn deleted the ENTIRE Intl lookup, leaving a bare `return 'UTC'`, and `npm test`,
    // `npm run build` and `npm run test:states` all stayed green. The only assertion was
    // "returns something the column will hold", and 'UTC' holds. Every org created outside
    // Universal Time would have had its timers and schedules silently wrong from the first
    // login, which is the thing this function exists to prevent.
    withTimeZone('Africa/Lagos', () => assert.equal(detectTimezone(), 'Africa/Lagos'))
    withTimeZone('America/New_York', () => assert.equal(detectTimezone(), 'America/New_York'))
    // A zone that is NOT the fallback and not the first sample either, so "returns the
    // last thing it was told" and "returns UTC" are both excluded.
    withTimeZone('Pacific/Chatham', () => assert.equal(detectTimezone(), 'Pacific/Chatham'))
  })

  test('it falls back to UTC rather than failing the signup', () => {
    // The other half, and the reason the positive control above is needed: every one of
    // these paths returns 'UTC', so a function that ONLY ever returns 'UTC' passes all of
    // them. They are the negative control, never the whole test.
    withTimeZone(undefined, () => assert.equal(detectTimezone(), 'UTC'))
    withTimeZone('', () => assert.equal(detectTimezone(), 'UTC'))
    withTimeZone(42, () => assert.equal(detectTimezone(), 'UTC'))
    // Over `CustomerOrg.timezone`'s max_length — sending it would fail the signup on a
    // field the user cannot see.
    withTimeZone('A'.repeat(MAX_TIMEZONE_LENGTH + 1), () => assert.equal(detectTimezone(), 'UTC'))
    // Exactly at the limit is kept, so the bound is `>` and not `>=`.
    const atLimit = 'A'.repeat(MAX_TIMEZONE_LENGTH)
    withTimeZone(atLimit, () => assert.equal(detectTimezone(), atLimit))

    const realIntl = globalThis.Intl
    try {
      Object.defineProperty(globalThis, 'Intl', {
        value: {
          DateTimeFormat: () => {
            throw new Error('no Intl in this environment')
          },
        },
        configurable: true,
      })
      assert.equal(detectTimezone(), 'UTC')
    } finally {
      Object.defineProperty(globalThis, 'Intl', { value: realIntl, configurable: true })
    }
  })

  test('always returns something the column will hold', () => {
    const zone = detectTimezone()
    assert.equal(typeof zone, 'string')
    assert.notEqual(zone, '')
    assert.ok(zone.length <= 64, `"${zone}" is longer than CustomerOrg.timezone allows`)
  })
})
