/**
 * The email mirror, checked against the SERVER's verdict rather than against itself.
 *
 * `tests/fixtures/email-mirror.json` is the single definition. It carries one row per
 * address with a `serverAccepts` column, and it has exactly two consumers:
 *
 *   - this file, which asserts `emailPolicy` agrees with that column on every row;
 *   - `scripts/service_text_reference.py`, which RE-DERIVES the column from Django's own
 *     `validate_email` and fails if the file has drifted from it.
 *
 * That shape is the point. The previous mirror test asserted the client against a second
 * copy of the client's own rule, so it passed while the rule was wrong — four ordinary
 * typos (`a@b.c`, `a@b..com`, `a@-b.com`, `a@b-.com`) passed the client and were rejected
 * by the server, surfacing on `/forgot-password` as a transient "try again in a moment"
 * for an error that is permanent. Neither of the two consumers here can silently agree
 * with a wrong answer, because neither owns the answer.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'
import { readFileSync } from 'node:fs'
import {
  EMAIL_INVALID,
  EMAIL_REQUIRED,
  normalizeEmail,
  serverWouldAcceptEmail,
  validateEmail,
} from '../src/lib/auth/emailPolicy.ts'

interface MirrorCase {
  address: string
  serverAccepts: boolean
  note: string
}

const CASES: MirrorCase[] = JSON.parse(
  readFileSync(new URL('./fixtures/email-mirror.json', import.meta.url), 'utf8'),
).cases

describe('the client agrees with the server on every fixture', () => {
  test('the fixture set is real and covers both verdicts', () => {
    // The premise, pinned so the sweep below cannot go vacuous by the file emptying or
    // by every row landing on one verdict — a sweep of thirty accepts would pass just as
    // well for `return true`.
    const accepted = CASES.filter((row) => row.serverAccepts)
    const rejected = CASES.filter((row) => !row.serverAccepts)
    assert.ok(accepted.length >= 10, `only ${accepted.length} accepted fixtures`)
    assert.ok(rejected.length >= 10, `only ${rejected.length} rejected fixtures`)

    // And the four Cody measured against real Django are present BY VALUE, so deleting
    // them to make this file pass is a visible edit rather than a quiet one.
    for (const address of ['a@b.c', 'a@b..com', 'a@-b.com', 'a@b-.com']) {
      const row = CASES.find((candidate) => candidate.address === address)
      assert.ok(row, `${address} is missing from the fixture set`)
      assert.equal(row.serverAccepts, false, `${address} must be recorded as server-rejected`)
    }
  })

  test('serverWouldAcceptEmail matches serverAccepts on every row', () => {
    const disagreements: string[] = []
    for (const row of CASES) {
      if (serverWouldAcceptEmail(row.address) !== row.serverAccepts) {
        disagreements.push(
          `${JSON.stringify(row.address)} — server ${row.serverAccepts ? 'accepts' : 'rejects'}, ` +
            `client ${row.serverAccepts ? 'rejects' : 'accepts'} (${row.note})`,
        )
      }
    }
    assert.deepEqual(disagreements, [], `the mirror has drifted:\n  ${disagreements.join('\n  ')}`)
  })

  test('validateEmail reports the same verdict, with a message the user can act on', () => {
    for (const row of CASES) {
      const message = validateEmail(row.address)
      if (row.serverAccepts) {
        assert.equal(message, '', `${JSON.stringify(row.address)} must be submittable`)
      } else {
        assert.ok(message !== '', `${JSON.stringify(row.address)} must not be submittable`)
        assert.ok(
          message === EMAIL_REQUIRED || message === EMAIL_INVALID,
          `unexpected message for ${JSON.stringify(row.address)}: ${message}`,
        )
      }
    }
  })

  test('an empty or whitespace-only address asks for one rather than calling it invalid', () => {
    assert.equal(validateEmail(''), EMAIL_REQUIRED)
    assert.equal(validateEmail('   '), EMAIL_REQUIRED)
    // The service-strip set, not the JS one: the server sees these as empty too.
    assert.equal(validateEmail('\u001c\u001c'), EMAIL_REQUIRED)
  })
})

describe('normalisation matches `_normalize_email`', () => {
  test('the address is stripped and lowercased the way the server does it', () => {
    assert.equal(normalizeEmail('  Pastor@YourChurch.ORG  '), 'pastor@yourchurch.org')
    // U+001C is whitespace to Python and not to JavaScript. Stripping it here is what
    // stops the client validating a different string than the server stores.
    assert.equal(normalizeEmail('\u001cpastor@yourchurch.org\u001c'), 'pastor@yourchurch.org')
    // U+FEFF runs the other way and must survive, which makes this address invalid on
    // BOTH sides rather than valid on one.
    assert.equal(normalizeEmail('\ufeffpastor@yourchurch.org'), '\ufeffpastor@yourchurch.org')
    assert.equal(serverWouldAcceptEmail('\ufeffpastor@yourchurch.org'), false)
  })
})

describe('the rule the module must never acquire', () => {
  test('nothing here can tell a registered address from an unregistered one', () => {
    // Two addresses of identical shape, one of which is the fixture used throughout the
    // suite as "registered". The verdict must depend on shape alone.
    assert.equal(validateEmail('pastor@yourchurch.org'), '')
    assert.equal(validateEmail('nobody-has-this-address@nowhere.test'), '')
  })
})
