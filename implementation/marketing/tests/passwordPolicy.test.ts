/**
 * The correctness trap, tested.
 *
 * Run with `npm test` (Node's built-in `node:test` runner — see package.json).
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'

import {
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
  PASSWORDS_DO_NOT_MATCH,
  PASSWORD_ONLY_SPACES,
  PASSWORD_TOO_LONG,
  PASSWORD_TOO_SHORT,
  isSubmittableNewPassword,
  codePointLength,
  validateNewPassword,
} from '../src/lib/auth/passwordPolicy.ts'

describe('the 6-character case', () => {
  /**
   * The specific case called out in ClickUp 86ak10b1t's implementation note.
   *
   * `confirm_password_reset` validates the password BEFORE the token and returns the same
   * `VALIDATION_FAILED` for both. If this password ever reached the API, the user would
   * be told their reset link is dead when it is perfectly good — and would go and request
   * another one, and hit the same wall.
   */
  test('a 6-character password is rejected client-side and never submitted', () => {
    const errors = validateNewPassword('abc123', 'abc123')

    assert.equal(errors.password, PASSWORD_TOO_SHORT)
    assert.equal(errors.confirmPassword, undefined, 'the passwords match; only length is wrong')
    assert.equal(
      isSubmittableNewPassword('abc123', 'abc123'),
      false,
      'this is the gate ResetView.submitNewPassword checks before calling the mutation',
    )
  })

  test('the message tells the user the actual rule, so the second attempt succeeds', () => {
    // A message that just said "invalid password" would send them round the same loop.
    assert.match(PASSWORD_TOO_SHORT, /at least 10 characters/)
  })
})

describe('boundaries agree with _validate_password (services.py:273-279)', () => {
  const cases: Array<[string, number, boolean]> = [
    ['empty', 0, false],
    ['one below the floor', MIN_PASSWORD_LENGTH - 1, false],
    ['exactly the floor', MIN_PASSWORD_LENGTH, true],
    ['one above the floor', MIN_PASSWORD_LENGTH + 1, true],
    ['exactly the ceiling', MAX_PASSWORD_LENGTH, true],
    ['one above the ceiling', MAX_PASSWORD_LENGTH + 1, false],
  ]

  for (const [label, length, expected] of cases) {
    test(`${label} (${length} chars) → ${expected ? 'accepted' : 'rejected'}`, () => {
      const password = 'a'.repeat(length)
      assert.equal(isSubmittableNewPassword(password, password), expected)
    })
  }

  test('the floor is 10, matching ACCOUNT_MIN_PASSWORD_LENGTH', () => {
    // MARKETING-PORTAL-GAP-FILL-HANDOFF §3c/§4d says 8 + complexity. It is wrong on both
    // counts; the shipped API is length-only, 10..200. Pinned so nobody "fixes" this back.
    assert.equal(MIN_PASSWORD_LENGTH, 10)
    assert.equal(MAX_PASSWORD_LENGTH, 200)
  })

  test('there is no complexity rule — a long lowercase password is accepted', () => {
    assert.equal(isSubmittableNewPassword('correcthorsebattery', 'correcthorsebattery'), true)
  })
})

describe('the all-whitespace case', () => {
  /**
   * The second way to be wrongly told your link is dead. `_validate_password` starts with
   * `not password.strip()`, so a password of twelve spaces is long enough but still
   * rejected — with the same `VALIDATION_FAILED`.
   */
  test('twelve spaces is long enough but still rejected, matching the server', () => {
    const spaces = ' '.repeat(12)
    assert.equal(codePointLength(spaces), 12, 'long enough on length alone')
    assert.equal(validateNewPassword(spaces, spaces).password, PASSWORD_ONLY_SPACES)
    assert.equal(isSubmittableNewPassword(spaces, spaces), false)
  })

  test('a short all-space entry still gets the primary length message', () => {
    // Length is the more useful correction when both rules are broken.
    assert.equal(validateNewPassword('   ', '   ').password, PASSWORD_TOO_SHORT)
  })

  test('internal and trailing spaces are preserved, not trimmed away', () => {
    // The API does NOT strip before measuring — "spaces can be intentional" — so a
    // passphrase with spaces must be accepted exactly as typed.
    assert.equal(isSubmittableNewPassword('two words ok', 'two words ok'), true)
  })
})

describe('length is counted in code points, like Python len()', () => {
  /**
   * JavaScript's `.length` counts surrogate pairs twice. Five emoji measure 10 in JS and
   * 5 in Python — so a naive `.length` check would pass them to an API that rejects them,
   * reopening the exact mis-attribution this module exists to close.
   */
  test('five astral characters measure 5, not 10', () => {
    const fiveEmoji = '\u{1F600}\u{1F601}\u{1F602}\u{1F603}\u{1F604}'
    assert.equal(fiveEmoji.length, 10, 'JS string length double-counts surrogate pairs')
    assert.equal(codePointLength(fiveEmoji), 5, 'code-point count matches Python len()')
    assert.equal(
      isSubmittableNewPassword(fiveEmoji, fiveEmoji),
      false,
      'must be rejected here rather than by the server, which cannot say why',
    )
  })

  test('ten astral characters are accepted', () => {
    const tenEmoji = '\u{1F600}'.repeat(10)
    assert.equal(isSubmittableNewPassword(tenEmoji, tenEmoji), true)
  })
})

describe('confirmation field', () => {
  test('mismatched passwords are reported on the confirm field', () => {
    const errors = validateNewPassword('correcthorsebattery', 'correcthorsebatteries')
    assert.equal(errors.password, undefined)
    assert.equal(errors.confirmPassword, PASSWORDS_DO_NOT_MATCH)
  })

  test('both errors surface together — R2 shows both fields in error at once', () => {
    const errors = validateNewPassword('short', 'different')
    assert.equal(errors.password, PASSWORD_TOO_SHORT)
    assert.equal(errors.confirmPassword, PASSWORDS_DO_NOT_MATCH)
  })

  test('a valid matching pair produces no errors at all', () => {
    assert.deepEqual(validateNewPassword('a-good-passphrase', 'a-good-passphrase'), {})
  })

  test('the too-long message names the ceiling', () => {
    assert.match(PASSWORD_TOO_LONG, /200/)
  })
})
