/**
 * The pure rules behind per-page title/description and focus. The Vue composables that use
 * them (`useDocumentMeta`, `useFocusHeading`) are thin adapters; the headless browser check
 * (`scripts/article_pages_headless.py`) proves the wiring.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { SITE_DEFAULT_DESCRIPTION, SITE_DEFAULT_TITLE } from '../src/lib/content/text.ts'
import { applyMeta, releaseMeta, type MetaDefaults, type MetaTarget } from '../src/lib/documentMeta.ts'
import { cameFromInsideTheApp } from '../src/lib/pageFocus.ts'

const DEFAULTS: MetaDefaults = { title: 'SelahCue — Church presentation, reengineered', description: 'The site description.' }
const fresh = (): MetaTarget => ({ title: DEFAULTS.title, description: DEFAULTS.description })

describe('applyMeta', () => {
  test('an article writes its own title (with the site suffix) and description', () => {
    const t = fresh()
    const w = applyMeta(t, DEFAULTS, { title: 'Pair a phone', description: 'Connect a phone.' })
    assert.equal(t.title, 'Pair a phone — SelahCue')
    assert.equal(t.description, 'Connect a phone.')
    assert.deepEqual(w, { title: 'Pair a phone — SelahCue', description: 'Connect a phone.' })
  })

  test('no title (an unknown slug) shows the site defaults, never an empty description', () => {
    for (const none of ['', '   ', null, undefined]) {
      const t = fresh()
      applyMeta(t, DEFAULTS, { title: 'Some article', description: 'Words.' })
      applyMeta(t, DEFAULTS, { title: none, description: 'stale words that must not stay' })
      assert.equal(t.title, DEFAULTS.title, JSON.stringify(none))
      assert.equal(t.description, DEFAULTS.description, JSON.stringify(none))
    }
  })

  test('an article with an empty summary falls back to the site description, not blank', () => {
    const t = fresh()
    applyMeta(t, DEFAULTS, { title: 'X', description: '' })
    assert.equal(t.description, DEFAULTS.description)
  })

  test('moving from one article to another replaces both fields', () => {
    const t = fresh()
    applyMeta(t, DEFAULTS, { title: 'A', description: 'a' })
    applyMeta(t, DEFAULTS, { title: 'B', description: 'b' })
    assert.deepEqual({ ...t }, { title: 'B — SelahCue', description: 'b' })
  })
})

describe('releaseMeta', () => {
  test('leaving the page gives the defaults back for BOTH fields', () => {
    const t = fresh()
    const w = applyMeta(t, DEFAULTS, { title: 'A', description: 'a' })
    releaseMeta(t, DEFAULTS, w)
    assert.deepEqual({ ...t }, { ...DEFAULTS })
  })

  test('it does not clobber a newer page: Suspense sets up the next article BEFORE the old one unmounts', () => {
    const t = fresh()
    const oldPage = applyMeta(t, DEFAULTS, { title: 'Old', description: 'old' })
    applyMeta(t, DEFAULTS, { title: 'New', description: 'new' })
    releaseMeta(t, DEFAULTS, oldPage)
    assert.equal(t.title, 'New — SelahCue')
    assert.equal(t.description, 'new')
  })

  test('each field is judged on its own', () => {
    const t = fresh()
    const w = applyMeta(t, DEFAULTS, { title: 'A', description: 'a' })
    t.description = 'someone else wrote this'
    releaseMeta(t, DEFAULTS, w)
    assert.equal(t.title, DEFAULTS.title)
    assert.equal(t.description, 'someone else wrote this')
  })
})

describe('cameFromInsideTheApp (where focus goes)', () => {
  test('a page reached from another in-app page is "from inside": focus moves to its h1', () => {
    assert.equal(cameFromInsideTheApp({ back: '/blog', current: '/blog/x', position: 3 }), true)
  })

  test('the first entry of a session (back is null) is a direct load: focus stays at the top', () => {
    assert.equal(cameFromInsideTheApp({ back: null, current: '/blog/x', position: 0 }), false)
  })

  test('absent or odd history state is treated as a direct load', () => {
    for (const s of [null, undefined, 0, 'x', {}, { back: undefined }]) assert.equal(cameFromInsideTheApp(s), false, JSON.stringify(s))
  })
})

describe('the site defaults are constants, not whatever the document showed first', () => {
  const read = (rel: string): string => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')

  test('they equal the title and description in index.html', () => {
    const html = read('../index.html')
    assert.equal(/<title>([^<]*)<\/title>/.exec(html)?.[1], SITE_DEFAULT_TITLE)
    assert.equal(/<meta name="description" content="([^"]*)"/.exec(html)?.[1], SITE_DEFAULT_DESCRIPTION)
  })

  test('leaving an article restores the constants, whichever page was showing on first load', () => {
    // Cold-load a page that sets its own title (what /privacy does once the legal pages land),
    // then visit an article, then leave it. The home page must not inherit the other page's title.
    const defaults: MetaDefaults = { title: SITE_DEFAULT_TITLE, description: SITE_DEFAULT_DESCRIPTION }
    for (const firstPage of ['SelahCue Privacy Policy', 'Terms of Service — SelahCue', '', 'x']) {
      const target: MetaTarget = { title: firstPage, description: 'that page’s own description' }
      const written = applyMeta(target, defaults, { title: 'Pair a phone', description: 'Connect a phone.' })
      releaseMeta(target, defaults, written)
      assert.equal(target.title, SITE_DEFAULT_TITLE, `first page was "${firstPage}"`)
      assert.equal(target.description, SITE_DEFAULT_DESCRIPTION)
    }
  })

  test('the composable does not derive its defaults from the document', () => {
    const src = read('../src/lib/useDocumentMeta.ts').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
    const defaultsDecl = /const DEFAULTS[\s\S]*?\n\n/.exec(src)?.[0] ?? ''
    assert.ok(defaultsDecl.includes('SITE_DEFAULT_TITLE') && defaultsDecl.includes('SITE_DEFAULT_DESCRIPTION'), 'DEFAULTS must be the constants')
    assert.ok(!/document\./.test(defaultsDecl), 'DEFAULTS must not read the document')
  })
})
