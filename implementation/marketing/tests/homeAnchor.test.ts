/**
 * The cold-load anchor correction on Home (`lib/reanchor.ts`), driven through the REAL
 * `reanchorForBrowser` with a stand-in browser (ClickUp 17tnw2b2cex; hand-over from the chrome review,
 * PR 172, Shadow's finding).
 *
 * Home became an anchored route in PR 172, so `reanchorForBrowser` now runs on a cold load of
 * `/#anything`. It used to look the fragment up with `document.querySelector(rawHash)`. A fragment is
 * not a selector: `#1abc` and `#%` are valid fragments and INVALID selectors, so `querySelector`
 * throws, and the correction ended as `reapply-failed` on a URL a visitor can type or follow from
 * anywhere. vue-router looks the element up with `getElementById` on the decoded fragment; this makes
 * the correction do the same.
 *
 * The stand-in `document` is faithful where it matters: its `querySelector` THROWS on a selector a
 * real browser rejects (the CONTROL test below proves that), so the faulty code reads `reapply-failed`
 * here for the same reason it does in a browser.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test, { afterEach, describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { parse } from 'vue/compiler-sfc'

import { anchorScrollTop, fragmentId, reanchorForBrowser } from '../src/lib/reanchor.ts'

const ROOT = fileURLToPath(new URL('../', import.meta.url))

interface FakeTarget {
  getBoundingClientRect(): { top: number }
}

/** `#ident` as a CSS selector: what a browser accepts (an identifier cannot start with a digit; `%` is not an identifier character). */
const VALID_ID_SELECTOR = /^#-?[A-Za-z_\u00A0-\uFFFF][\w\u00A0-\uFFFF-]*$/

interface Installed {
  scrolls: Array<{ top: number; behavior: string }>
  lookups: { byId: string[]; bySelector: string[] }
  restore(): void
}

const saved: Array<() => void> = []

function installBrowser(opts: { hash: string; ids: Record<string, number>; navBottom?: number }): Installed {
  const scrolls: Installed['scrolls'] = []
  const lookups: Installed['lookups'] = { byId: [], bySelector: [] }
  const target = (top: number): FakeTarget => ({ getBoundingClientRect: () => ({ top }) })
  const fakeDocument = {
    fonts: { status: 'loading', ready: Promise.resolve() },
    documentElement: {},
    querySelector(selector: string) {
      lookups.bySelector.push(selector)
      if (selector === '#app header') return { getBoundingClientRect: () => ({ bottom: opts.navBottom ?? 79 }) }
      if (!VALID_ID_SELECTOR.test(selector)) throw new SyntaxError(`'${selector}' is not a valid selector`)
      const id = selector.slice(1)
      return id in opts.ids ? target(opts.ids[id] as number) : null
    },
    getElementById(id: string) {
      lookups.byId.push(id)
      return id in opts.ids ? target(opts.ids[id] as number) : null
    },
  }
  const fakeWindow = {
    location: { hash: opts.hash },
    scrollY: 0,
    matchMedia: () => ({ matches: false }),
    addEventListener() {},
    removeEventListener() {},
    scrollTo(o: { top: number; behavior: string }) {
      scrolls.push({ top: o.top, behavior: o.behavior })
    },
  }
  const g = globalThis as Record<string, unknown>
  const before = { window: g['window'], document: g['document'], getComputedStyle: g['getComputedStyle'] }
  g['window'] = fakeWindow
  g['document'] = fakeDocument
  g['getComputedStyle'] = () => ({ getPropertyValue: () => '16px' })
  const restore = (): void => {
    for (const [k, v] of Object.entries(before)) {
      if (v === undefined) delete g[k]
      else g[k] = v
    }
  }
  saved.push(restore)
  return { scrolls, lookups, restore }
}

afterEach(() => {
  while (saved.length) saved.pop()?.()
})

describe('a cold load of Home with a #fragment', () => {
  test('#how-it-works finds the steps section and lands it clear of the 79px bar (offset 95)', async () => {
    const b = installBrowser({ hash: '#how-it-works', ids: { 'how-it-works': 300 } })
    assert.equal(await reanchorForBrowser({ name: 'home' }), 'reapplied')
    assert.deepEqual(b.scrolls, [{ top: anchorScrollTop(300, 0, 95), behavior: 'instant' }])
    assert.equal(anchorScrollTop(300, 0, 95), 205)
  })

  test('#1abc is a valid fragment and an invalid selector: it reaches "reapplied", not "reapply-failed"', async () => {
    const b = installBrowser({ hash: '#1abc', ids: {} })
    assert.equal(await reanchorForBrowser({ name: 'home' }), 'reapplied')
    assert.deepEqual(b.scrolls, [], 'there is no such element, so there is nothing to scroll to')
  })

  test('#% (a bare percent sign, which cannot be decoded) reaches "reapplied" and does not throw', async () => {
    const b = installBrowser({ hash: '#%', ids: {} })
    assert.equal(await reanchorForBrowser({ name: 'home' }), 'reapplied')
    assert.deepEqual(b.scrolls, [])
  })

  test('an id that starts with a digit is found when it exists (#1abc as a real section id)', async () => {
    const b = installBrowser({ hash: '#1abc', ids: { '1abc': 480 } })
    assert.equal(await reanchorForBrowser({ name: 'home' }), 'reapplied')
    assert.deepEqual(b.scrolls, [{ top: 385, behavior: 'instant' }])
  })

  test('a percent-encoded fragment is decoded before the lookup, as vue-router does', async () => {
    const b = installBrowser({ hash: '#%C3%BCber-uns', ids: { 'über-uns': 120 } })
    assert.equal(await reanchorForBrowser({ name: 'home' }), 'reapplied')
    assert.deepEqual(b.scrolls, [{ top: 25, behavior: 'instant' }])
    assert.deepEqual(b.lookups.byId, ['über-uns'])
  })

  test('the lookup is by id, never by selector (the fragment is not a selector)', async () => {
    const b = installBrowser({ hash: '#how-it-works', ids: { 'how-it-works': 300 } })
    await reanchorForBrowser({ name: 'home' })
    assert.deepEqual(b.lookups.byId, ['how-it-works'])
    assert.deepEqual(b.lookups.bySelector.filter((s) => s !== '#app header'), [], 'document.querySelector was called with the fragment')
  })

  test('other routes keep exactly the scroll the router gave them (the correction is for anchored routes only)', async () => {
    const b = installBrowser({ hash: '#how-it-works', ids: { 'how-it-works': 300 } })
    assert.equal(await reanchorForBrowser({ name: 'pricing' }), 'not-anchored')
    assert.deepEqual(b.scrolls, [])
  })

  test('CONTROL: the stand-in document rejects the selectors a browser rejects, so the old lookup would have thrown here too', () => {
    const b = installBrowser({ hash: '#x', ids: {} })
    const doc = (globalThis as unknown as { document: { querySelector(s: string): unknown } }).document
    assert.throws(() => doc.querySelector('#1abc'), SyntaxError)
    assert.throws(() => doc.querySelector('#%'), SyntaxError)
    assert.throws(() => doc.querySelector('#%C3%BCber'), SyntaxError)
    assert.equal(doc.querySelector('#how-it-works'), null)
    assert.ok(b)
  })
})

describe('fragmentId', () => {
  test('strips the hash, decodes percent escapes and falls back to the text as written when it cannot decode', () => {
    assert.equal(fragmentId('#how-it-works'), 'how-it-works')
    assert.equal(fragmentId('how-it-works'), 'how-it-works')
    assert.equal(fragmentId('#%C3%BCber'), 'über')
    assert.equal(fragmentId('#%'), '%')
    assert.equal(fragmentId('#%E0%A4%A'), '%E0%A4%A')
    assert.equal(fragmentId('#'), '')
    assert.equal(fragmentId(''), '')
  })
})

describe('Home stays a synchronous route, so the anchor offset is measured against a page that exists (chrome review, PR 172)', () => {
  test('the router imports HomeView statically and routes "/" straight to it; HomeView has no async setup', () => {
    const router = readFileSync(path.join(ROOT, 'src/router/index.ts'), 'utf8')
    assert.match(router, /^import HomeView from '@\/views\/HomeView\.vue'$/m)
    assert.match(router, /\{ path: '\/', name: 'home', component: HomeView \}/)
    const sfc = parse(readFileSync(path.join(ROOT, 'src/views/HomeView.vue'), 'utf8')).descriptor
    const script = sfc.scriptSetup?.content ?? ''
    assert.doesNotMatch(script, /\bawait\b/, 'a top-level await makes <script setup> async: the router scroll would run before the target exists')
    assert.doesNotMatch(script, /defineAsyncComponent|import\(/, 'a lazily loaded part of Home can arrive after the anchor scroll')
  })
})
