/**
 * What the browser is allowed to remember about being signed in.
 *
 * The controls under test are all of the "must not" kind, so each one is paired with a
 * positive control: a test that only shows a value being REFUSED cannot tell a working
 * guard from a function that returns null unconditionally.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'

import {
  SESSION_HINT_KEY,
  clearSessionHint,
  readSessionHint,
  writeSessionHint,
  type HintStorage,
} from '../src/lib/auth/session.ts'

/** An in-memory `Storage`, so these tests need no DOM and no browser. */
function memoryStorage(seed: Record<string, string> = {}): HintStorage & { dump(): Record<string, string> } {
  const data = new Map(Object.entries(seed))
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
    dump: () => Object.fromEntries(data),
  }
}

/** A storage that throws on every operation — Safari private mode, cookies disabled. */
const hostileStorage: HintStorage = {
  getItem() {
    throw new DOMException('The operation is insecure.', 'SecurityError')
  },
  setItem() {
    throw new DOMException('QuotaExceededError')
  },
  removeItem() {
    throw new DOMException('The operation is insecure.', 'SecurityError')
  },
}

const HOUR = 3_600_000
const NOW = Date.parse('2026-08-25T12:00:00Z')
const LATER = new Date(NOW + 24 * HOUR).toISOString()
const EARLIER = new Date(NOW - HOUR).toISOString()

const LIVE_HINT = { role: 'ADMIN', orgId: 'org-1', expiresAt: LATER }

describe('a session token is never written to storage', () => {
  test('writeSessionHint drops a sessionToken it is handed', () => {
    // THE control. `login`'s payload type is one field away from carrying the raw
    // credential, and `writeSessionHint(payload)` is the natural thing to write. Because
    // the stored object is rebuilt from a fixed field list, that mistake stores the three
    // safe fields and drops the token on the floor.
    const storage = memoryStorage()
    writeSessionHint(
      { ...LIVE_HINT, sessionToken: 'SC-SESSION-do-not-persist-me' } as never,
      storage,
    )

    const raw = storage.dump()[SESSION_HINT_KEY]
    assert.ok(raw, 'the hint was not written at all — the rest of this test proves nothing')
    assert.ok(
      !raw.includes('SC-SESSION-do-not-persist-me'),
      `the session token reached localStorage: ${raw}`,
    )
    assert.ok(!raw.includes('sessionToken'), `the token key reached localStorage: ${raw}`)
    // Positive control: the three fields it IS meant to keep are all there, so "no token"
    // is not passing because nothing was stored.
    assert.deepEqual(JSON.parse(raw), LIVE_HINT)
  })

  test('readSessionHint never returns a token, even from a blob that contains one', () => {
    // Covers a value this build did not write: an older build, another tab, or someone
    // editing localStorage by hand. The hint is rebuilt field by field on the way out
    // too, so extra keys cannot ride into the running application.
    const storage = memoryStorage({
      [SESSION_HINT_KEY]: JSON.stringify({
        ...LIVE_HINT,
        sessionToken: 'SC-SESSION-planted',
      }),
    })

    const hint = readSessionHint(NOW, storage)
    assert.deepEqual(hint, LIVE_HINT)
    assert.ok(!Object.hasOwn(hint as object, 'sessionToken'))
  })
})

describe('an unusable hint is no hint', () => {
  test('a live hint round-trips', () => {
    // The positive control for every refusal below.
    const storage = memoryStorage()
    writeSessionHint(LIVE_HINT as never, storage)
    assert.deepEqual(readSessionHint(NOW, storage), LIVE_HINT)
  })

  test('an expired hint is refused', () => {
    const storage = memoryStorage({
      [SESSION_HINT_KEY]: JSON.stringify({ ...LIVE_HINT, expiresAt: EARLIER }),
    })
    assert.equal(readSessionHint(NOW, storage), null)
  })

  test('a hint expiring exactly now is refused', () => {
    const storage = memoryStorage({
      [SESSION_HINT_KEY]: JSON.stringify({
        ...LIVE_HINT,
        expiresAt: new Date(NOW).toISOString(),
      }),
    })
    assert.equal(readSessionHint(NOW, storage), null)
  })

  test('an unparseable expiry is treated as dead, not as "no expiry"', () => {
    // Failing the other way would turn one corrupted timestamp into an immortal hint.
    const storage = memoryStorage({
      [SESSION_HINT_KEY]: JSON.stringify({ ...LIVE_HINT, expiresAt: 'soon-ish' }),
    })
    assert.equal(readSessionHint(NOW, storage), null)
  })

  test('malformed JSON, wrong types and missing fields are all refused', () => {
    for (const stored of [
      'not json at all',
      'null',
      '"a bare string"',
      '[]',
      JSON.stringify({ role: 'ADMIN', orgId: 'org-1' }),
      JSON.stringify({ role: 'ADMIN', orgId: 'org-1', expiresAt: '' }),
      JSON.stringify({ role: 'ADMIN', orgId: 42, expiresAt: LATER }),
    ]) {
      const storage = memoryStorage({ [SESSION_HINT_KEY]: stored })
      assert.equal(readSessionHint(NOW, storage), null, `should have refused: ${stored}`)
    }
  })

  test('an absent key is refused', () => {
    assert.equal(readSessionHint(NOW, memoryStorage()), null)
  })
})

describe('storage that is missing or hostile', () => {
  test('no storage at all degrades to "no hint" rather than throwing', () => {
    assert.equal(readSessionHint(NOW, null), null)
    assert.doesNotThrow(() => writeSessionHint(LIVE_HINT as never, null))
    assert.doesNotThrow(() => clearSessionHint(null))
  })

  test('a storage that throws on every call degrades the same way', () => {
    // Reading `localStorage` throws outright in a Firefox profile with cookies disabled,
    // and `setItem` throws in Safari private mode. A sign-in flow must not become
    // unusable because a browser preference makes a convenience cache unavailable.
    assert.equal(readSessionHint(NOW, hostileStorage), null)
    assert.doesNotThrow(() => writeSessionHint(LIVE_HINT as never, hostileStorage))
    assert.doesNotThrow(() => clearSessionHint(hostileStorage))
  })
})

describe('clearing', () => {
  test('clearSessionHint removes the key, and a later read finds nothing', () => {
    const storage = memoryStorage()
    writeSessionHint(LIVE_HINT as never, storage)
    assert.notEqual(readSessionHint(NOW, storage), null, 'nothing was stored to clear')

    clearSessionHint(storage)
    assert.equal(storage.dump()[SESSION_HINT_KEY], undefined)
    assert.equal(readSessionHint(NOW, storage), null)
  })
})
