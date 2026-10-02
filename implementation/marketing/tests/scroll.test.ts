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

/**
 * Components that declare per-element `scroll-margin` ON PURPOSE because they switch the root
 * `scroll-padding-top` off while mounted, so the two cannot add. Keyed by path under `src/`; the
 * value is what must still be in the file for the exemption to hold.
 *
 * `components/legal/LegalPage.vue` (the legal pages, a separate PR) zeroes the root padding with
 * `html:has(.legal-page) { scroll-padding-top: 0 }` in an unscoped style block and carries its
 * own anchor offsets. An entry for a file that is not in this tree is skipped silently, so this
 * branch stands alone and the entry only bites once that file arrives.
 */
const NEUTRALISERS: Readonly<Record<string, RegExp>> = {
  'components/legal/LegalPage.vue': /html:has\(\.legal-page\)\s*\{[^}]*\bscroll-padding-top:\s*0(?:px)?\s*[;}]/,
}

/** Strip comments so a margin or a neutraliser that is only mentioned in one does not count. */
const withoutComments = (text: string): string => text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '')

export function scrollMarginProblems(files: Readonly<Record<string, string>>, neutralisers: Readonly<Record<string, RegExp>>): string[] {
  const problems: string[] = []
  for (const [path, text] of Object.entries(files)) {
    if (!/^[^*\n]*\bscroll-margin(-top)?\s*:/m.test(withoutComments(text).replace(/^\s*\*.*$/gm, ''))) continue
    const exempt = neutralisers[path]
    if (!exempt) problems.push(`${path}: declares scroll-margin`)
    else if (!exempt.test(withoutComments(text))) problems.push(`${path}: declares scroll-margin but no longer neutralises the root scroll-padding-top`)
  }
  return problems
}

describe('the CSS side of the same rule', () => {
  const src = fileURLToPath(new URL('../src/', import.meta.url))
  const walk = (d: string): string[] => readdirSync(d).flatMap((n) => (statSync(join(d, n)).isDirectory() ? walk(join(d, n)) : [join(d, n)]))

  test('anchors.css defines the root scroll-padding-top from the navbar token and main.ts loads it', () => {
    const css = readFileSync(join(src, 'assets/styles/anchors.css'), 'utf8')
    assert.match(css, /html\s*\{[^}]*scroll-padding-top:\s*calc\(var\(--nav-height,\s*68px\)\s*\+\s*var\(--sc-anchor-gap\)\)/)
    assert.match(readFileSync(join(src, 'main.ts'), 'utf8'), /assets\/styles\/anchors\.css/)
  })

  test('no per-element scroll-margin exists to double-count with the root padding (bar the allowlist)', () => {
    const files: Record<string, string> = {}
    for (const f of walk(src).filter((x) => /\.(vue|css)$/.test(x))) files[f.slice(src.length)] = readFileSync(f, 'utf8')
    assert.deepEqual(scrollMarginProblems(files, NEUTRALISERS), [])
  })

  describe('the rule itself (checked on in-memory files, so it needs no other PR)', () => {
    const LEGAL = 'components/legal/LegalPage.vue'
    const withMargin = '.x { scroll-margin-top: 10px; }'
    const neutraliser = 'html:has(.legal-page) {\n  scroll-padding-top: 0;\n}'

    test('an ordinary file with a scroll-margin is reported', () => {
      assert.deepEqual(scrollMarginProblems({ 'views/A.vue': withMargin }, NEUTRALISERS), ['views/A.vue: declares scroll-margin'])
    })

    test('an allowlisted file is accepted only while it still neutralises the root padding', () => {
      assert.deepEqual(scrollMarginProblems({ [LEGAL]: `${withMargin}\n${neutraliser}` }, NEUTRALISERS), [])
      assert.deepEqual(scrollMarginProblems({ [LEGAL]: withMargin }, NEUTRALISERS), [`${LEGAL}: declares scroll-margin but no longer neutralises the root scroll-padding-top`])
      assert.equal(scrollMarginProblems({ [LEGAL]: `${withMargin}\nhtml:has(.legal-page) { scroll-padding-top: 8px; }` }, NEUTRALISERS).length, 1, 'a non-zero padding is not a neutraliser')
      assert.equal(scrollMarginProblems({ [LEGAL]: `${withMargin}\n/* html:has(.legal-page) { scroll-padding-top: 0; } */` }, NEUTRALISERS).length, 1, 'a commented-out neutraliser does not count')
    })

    test('an allowlisted file that does not exist is skipped silently (this PR stands alone)', () => {
      assert.deepEqual(scrollMarginProblems({}, NEUTRALISERS), [])
      assert.deepEqual(scrollMarginProblems({ 'views/A.vue': '.x { color: red; }' }, NEUTRALISERS), [])
    })

    test('an allowlisted file with no scroll-margin at all is fine, and so is a margin only in a comment', () => {
      assert.deepEqual(scrollMarginProblems({ [LEGAL]: '.x { color: red; }' }, NEUTRALISERS), [])
      assert.deepEqual(scrollMarginProblems({ 'views/A.vue': ' * scroll-margin: do not use' }, NEUTRALISERS), [])
    })

    test('the allowlist is path-based: the same text under another path is not exempt', () => {
      assert.equal(scrollMarginProblems({ 'components/other/LegalPage.vue': `${withMargin}\n${neutraliser}` }, NEUTRALISERS).length, 1)
    })
  })
})
