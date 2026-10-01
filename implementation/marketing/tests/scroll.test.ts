/**
 * Where a navigation scrolls to, and how. Tested through the pure `scrollFor` and
 * `readStickyOffset` (the router calls them through `siteScrollBehavior`); the real browser
 * behaviour (landing below the navbar, instant under reduced motion) is proved by
 * `scripts/article_pages_headless.py`.
 */
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { isAnchoredRoute, readStickyOffset, scrollFor } from '../src/router/scroll.ts'

const MOTION = { reducedMotion: false, stickyOffset: 84 }
const REDUCED = { reducedMotion: true, stickyOffset: 84 }

describe('anchors clear the sticky navbar', () => {
  test('on every blog, docs and support route a #hash target is offset by the navbar clearance', () => {
    for (const name of ['blog', 'blog-post', 'docs', 'docs-article', 'support', 'support-article']) {
      assert.deepEqual(scrollFor({ hash: '#sec-x', name }, MOTION), { el: '#sec-x', top: 84, behavior: 'smooth' }, name)
    }
  })

  test('the offset is whatever the document reports, not a constant in the router', () => {
    assert.equal((scrollFor({ hash: '#a', name: 'docs-article' }, { reducedMotion: false, stickyOffset: 120 }) as { top: number }).top, 120)
    assert.equal((scrollFor({ hash: '#a', name: 'docs-article' }, { reducedMotion: false, stickyOffset: 0 }) as { top: number }).top, 0)
  })

  test('other pages keep their previous behaviour: no offset', () => {
    for (const name of ['home', 'pricing', 'account', 'not-found', undefined, Symbol('x'), 42]) {
      assert.deepEqual(scrollFor({ hash: '#how-it-works', name }, MOTION), { el: '#how-it-works', top: 0, behavior: 'smooth' }, String(name))
    }
    assert.equal(isAnchoredRoute('home'), false)
    assert.equal(isAnchoredRoute('docs-article'), true)
  })

  test('with no hash a navigation goes to the top', () => {
    assert.deepEqual(scrollFor({ hash: '', name: 'blog-post' }, MOTION), { top: 0, behavior: 'smooth' })
  })
})

describe('reduced motion is honoured', () => {
  test('behaviour is "auto" (defer to CSS, which is instant under reduce), never "smooth"', () => {
    assert.deepEqual(scrollFor({ hash: '#a', name: 'docs-article' }, REDUCED), { el: '#a', top: 84, behavior: 'auto' })
    assert.deepEqual(scrollFor({ hash: '#a', name: 'home' }, REDUCED), { el: '#a', top: 0, behavior: 'auto' })
    assert.deepEqual(scrollFor({ hash: '', name: 'docs' }, REDUCED), { top: 0, behavior: 'auto' })
  })

  test('without the preference it still animates (control: the switch is not stuck)', () => {
    assert.equal(scrollFor({ hash: '', name: 'docs' }, MOTION).behavior, 'smooth')
  })
})

describe('the offset is read from the document', () => {
  test('it parses the computed px value and treats anything unusable as 0', () => {
    assert.equal(readStickyOffset({ scrollPaddingTop: '84px' }), 84)
    assert.equal(readStickyOffset({ scrollPaddingTop: '84.5px' }), 84.5)
    for (const bad of [undefined, '', 'auto', 'NaN', '-4px', '0px']) assert.equal(readStickyOffset({ scrollPaddingTop: bad }), 0, String(bad))
  })
})

describe('the CSS side of the same rule', () => {
  const src = fileURLToPath(new URL('../src/', import.meta.url))
  const walk = (d: string): string[] => readdirSync(d).flatMap((n) => (statSync(join(d, n)).isDirectory() ? walk(join(d, n)) : [join(d, n)]))

  test('anchors.css defines the root scroll-padding-top from the navbar token and main.ts loads it', () => {
    const css = readFileSync(join(src, 'assets/styles/anchors.css'), 'utf8')
    assert.match(css, /html\s*\{[^}]*scroll-padding-top:\s*calc\(var\(--nav-height,\s*68px\)\s*\+\s*var\(--sc-anchor-gap\)\)/)
    assert.match(readFileSync(join(src, 'main.ts'), 'utf8'), /assets\/styles\/anchors\.css/)
  })

  test('no per-element scroll-margin exists to double-count with the root padding', () => {
    const offenders = walk(src).filter((f) => /\.(vue|css)$/.test(f) && /^[^*\n]*\bscroll-margin(-top)?\s*:/m.test(readFileSync(f, 'utf8')))
    assert.deepEqual(offenders.map((f) => f.slice(src.length)), [])
  })
})
