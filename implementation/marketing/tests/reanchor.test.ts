/**
 * The one-shot re-scroll after web fonts load (`lib/reanchor.ts`). Driven with fakes, so the
 * promise ordering is explicit: fonts are released by hand, time is a number, input is a
 * function call. The real-browser wiring is proved in `scripts/article_pages_headless.py`.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { REANCHOR_DEADLINE_MS, anchorScrollTop, reanchorAfterFonts, type ReanchorDeps } from '../src/lib/reanchor.ts'

function harness(over: Partial<ReanchorDeps> & { hash?: string; fontsMissing?: boolean; status?: string } = {}) {
  let release!: () => void
  let reject!: (e: Error) => void
  const ready = new Promise<void>((res, rej) => {
    release = res
    reject = rej
  })
  if (over.status === 'loaded') release() // fonts that are already loaded have an already-resolved ready promise
  const state = { hash: over.hash ?? '#sec-x', now: 0, reapplied: 0, added: 0, removed: 0, handlers: new Set<() => void>() }
  const deps: ReanchorDeps = {
    hash: () => state.hash,
    fontsStatus: () => over.status ?? 'loading',
    fontsReady: () => (over.fontsMissing ? undefined : ready),
    now: () => state.now,
    onUserInput: (h) => {
      state.added++
      state.handlers.add(h)
      return () => {
        state.removed++
        state.handlers.delete(h)
      }
    },
    reapply: over.reapply ?? (() => void state.reapplied++),
    ...(over.deadlineMs === undefined ? {} : { deadlineMs: over.deadlineMs }),
  }
  return { deps, state, release, reject, input: () => state.handlers.forEach((h) => h()) }
}

/** Let the pending `await ready` continuation run. */
const settle = (): Promise<void> => new Promise((r) => setImmediate(r))

describe('the happy path', () => {
  test('after the fonts load it re-applies the anchor exactly once, and leaves no listener behind', async () => {
    const h = harness()
    const outcome = reanchorAfterFonts(h.deps)
    await settle()
    assert.equal(h.state.reapplied, 0, 'it must wait for the fonts')
    assert.equal(h.state.handlers.size, 1, 'it listens for the reader while it waits')
    h.release()
    assert.equal(await outcome, 'reapplied')
    assert.equal(h.state.reapplied, 1)
    assert.deepEqual([h.state.added, h.state.removed, h.state.handlers.size], [1, 1, 0])
    h.input()
    assert.equal(h.state.reapplied, 1, 'input after the shot must not trigger anything')
  })

  test('it is one shot: releasing the fonts twice, or the promise resolving late, never re-applies again', async () => {
    const h = harness()
    const outcome = reanchorAfterFonts(h.deps)
    h.release()
    h.release()
    await outcome
    await settle()
    assert.equal(h.state.reapplied, 1)
  })
})

describe('when it must do nothing', () => {
  test('no hash: nothing to correct, and no listener is even added', async () => {
    for (const hash of ['', '#']) {
      const h = harness({ hash })
      assert.equal(await reanchorAfterFonts(h.deps), 'no-hash')
      assert.deepEqual([h.state.reapplied, h.state.added], [0, 0])
    }
  })

  test('no font loading API, or fonts already loaded: nothing will shift', async () => {
    const none = harness({ fontsMissing: true })
    assert.equal(await reanchorAfterFonts(none.deps), 'no-fonts')
    const loaded = harness({ status: 'loaded' })
    assert.equal(await reanchorAfterFonts(loaded.deps), 'fonts-already-loaded')
    assert.deepEqual([none.state.reapplied, loaded.state.reapplied, none.state.added, loaded.state.added], [0, 0, 0, 0])
  })

  test('the reader scrolled, touched, typed or pointed while the fonts loaded: it leaves them alone', async () => {
    const h = harness()
    const outcome = reanchorAfterFonts(h.deps)
    await settle()
    h.input()
    h.release()
    assert.equal(await outcome, 'user-moved')
    assert.equal(h.state.reapplied, 0)
    assert.deepEqual([h.state.added, h.state.removed], [1, 1])
  })

  test('the hash changed meanwhile (they followed another link): it leaves them alone', async () => {
    const h = harness()
    const outcome = reanchorAfterFonts(h.deps)
    await settle()
    h.state.hash = '#sec-other'
    h.release()
    assert.equal(await outcome, 'hash-changed')
    assert.equal(h.state.reapplied, 0)
  })

  test('the fonts took longer than the deadline: a late jump is worse than a slightly low anchor', async () => {
    const h = harness()
    const outcome = reanchorAfterFonts(h.deps)
    await settle()
    h.state.now = REANCHOR_DEADLINE_MS + 1
    h.release()
    assert.equal(await outcome, 'too-late')
    assert.equal(h.state.reapplied, 0)
    // And right at the deadline it still goes ahead (the bound is inclusive).
    const edge = harness()
    const o2 = reanchorAfterFonts(edge.deps)
    await settle()
    edge.state.now = REANCHOR_DEADLINE_MS
    edge.release()
    assert.equal(await o2, 'reapplied')
  })

  test('a custom deadline is honoured', async () => {
    const h = harness({ deadlineMs: 100 })
    const outcome = reanchorAfterFonts(h.deps)
    await settle()
    h.state.now = 101
    h.release()
    assert.equal(await outcome, 'too-late')
  })
})

describe('failure never escapes and never leaks', () => {
  test('a font load that rejects: no throw, no re-scroll, listeners removed', async () => {
    const h = harness()
    const outcome = reanchorAfterFonts(h.deps)
    await settle()
    h.reject(new Error('network'))
    assert.equal(await outcome, 'fonts-failed')
    assert.deepEqual([h.state.reapplied, h.state.added, h.state.removed], [0, 1, 1])
  })

  test('a re-scroll that throws is swallowed and the listeners are still removed', async () => {
    const h = harness({ reapply: () => { throw new Error('boom') } })
    const outcome = reanchorAfterFonts(h.deps)
    h.release()
    assert.equal(await outcome, 'reapply-failed')
    assert.deepEqual([h.state.added, h.state.removed, h.state.handlers.size], [1, 1, 0])
  })
})

describe('the scroll arithmetic and the wiring', () => {
  test('anchorScrollTop puts the element the clearance below the top, never above zero', () => {
    assert.equal(anchorScrollTop(300, 1000, 84), 1216)
    assert.equal(anchorScrollTop(-40, 0, 84), 0)
    assert.equal(anchorScrollTop(84, 500, 84), 500, 'already in place: no movement')
  })

  const src = (rel: string): string => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')

  test('main.ts starts it once, after the router is ready', () => {
    const main = src('../src/main.ts')
    assert.match(main, /import \{ reanchorForBrowser \} from '\.\/lib\/reanchor\.ts'/)
    assert.match(main, /router\.isReady\(\)\.then\(\(\) => reanchorForBrowser\(router\.currentRoute\.value\)\)/)
    assert.equal((main.match(/reanchorForBrowser\(/g) ?? []).length, 1, 'started exactly once')
  })

  test('the browser binding only touches the pages whose anchors need the clearance, and corrects instantly', () => {
    const code = src('../src/lib/reanchor.ts')
    assert.match(code, /if \(!isAnchoredRoute\(route\.name\)\) return Promise\.resolve\('not-anchored'\)/)
    assert.match(code, /behavior: 'instant'/)
    assert.ok(!/setTimeout|setInterval|requestAnimationFrame/.test(code.replace(/\/\*[\s\S]*?\*\//g, '')), 'no timers: one shot only')
  })

  test('every listener it adds it removes, for the same events with the same capture flag', () => {
    const code = src('../src/lib/reanchor.ts')
    assert.match(code, /addEventListener\(type, handler, \{ passive: true, capture: true \}\)/)
    assert.match(code, /removeEventListener\(type, handler, \{ capture: true \}\)/)
  })
})
