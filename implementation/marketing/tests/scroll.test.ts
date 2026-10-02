/**
 * Where a navigation scrolls to, and how. Tested through the pure `scrollFor` and
 * `stickyOffsetFrom` (the router calls them through `siteScrollBehavior`); the real browser
 * behaviour (landing below the navbar, instant under reduced motion) is proved by
 * `scripts/article_pages_headless.py`.
 */
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { isAnchoredRoute, scrollFor, stickyOffsetFrom } from '../src/router/scroll.ts'

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

describe('the offset is the navbar plus the gap', () => {
  test('it adds the measured navbar bottom to the px gap', () => {
    assert.equal(stickyOffsetFrom(68, '16px'), 84)
    assert.equal(stickyOffsetFrom(68.5, ' 16px'), 84.5, 'custom property values keep leading whitespace')
    assert.equal(stickyOffsetFrom(92, '16px'), 108, 'a taller navbar moves the clearance with it: the navbar is the height, not a constant')
  })

  test('an unmeasurable navbar means no offset (the previous behaviour); a bad gap means no gap', () => {
    for (const nav of [0, -4, Number.NaN, Number.POSITIVE_INFINITY]) assert.equal(stickyOffsetFrom(nav, '16px'), 0, String(nav))
    for (const gap of ['', 'auto', 'NaN', '-4px', '0px']) assert.equal(stickyOffsetFrom(68, gap), 68, JSON.stringify(gap))
  })
})

/** `scroll-padding` declarations on html/:root/body that are not zero, per file. */
export function rootPaddingProblems(files: Readonly<Record<string, string>>): string[] {
  const problems: string[] = []
  for (const [path, raw] of Object.entries(files)) {
    const text = raw.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '')
    for (const rule of text.matchAll(/([^{}]*)\{([^{}]*)\}/g)) {
      const selector = (rule[1] ?? '').trim()
      if (!/(^|[\s,>+~])(html|:root|body)\b(?![-\w])/.test(selector) && !/^(html|:root|body)\b/.test(selector)) continue
      for (const decl of (rule[2] ?? '').matchAll(/\bscroll-padding(?:-[a-z]+)?\s*:\s*([^;}]+)/g)) {
        const value = (decl[1] ?? '').trim()
        if (!/^0(px)?$/.test(value)) problems.push(`${path}: \`${selector}\` sets scroll-padding: ${value}`)
      }
    }
  }
  return problems
}

describe('the CSS side of the same rule', () => {
  const src = fileURLToPath(new URL('../src/', import.meta.url))
  const walk = (d: string): string[] => readdirSync(d).flatMap((n) => (statSync(join(d, n)).isDirectory() ? walk(join(d, n)) : [join(d, n)]))

  test('anchors.css defines the gap and the offset, applies per-element scroll-margin, and main.ts loads it', () => {
    const css = readFileSync(join(src, 'assets/styles/anchors.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
    assert.match(css, /--sc-anchor-gap:\s*16px/)
    assert.match(css, /--sc-anchor-offset:\s*calc\(var\(--nav-height,\s*68px\)\s*\+\s*var\(--sc-anchor-gap\)\)/)
    assert.match(css, /\.ab-hwrap > :is\(h2, h3\)/, 'heading anchors')
    assert.match(css, /#docs-article/, 'the skip-link target')
    assert.match(css, /:is\(\.bp, \.da, \.sa\) :is\(a\[href\], button/, 'focusable elements on the article pages')
    assert.match(css, /:not\(\.da-skip\)/, 'the fixed skip link is excluded (margin would make focusing it scroll the page)')
    assert.match(css, /scroll-margin-top:\s*var\(--sc-anchor-offset\)/)
    assert.match(readFileSync(join(src, 'main.ts'), 'utf8'), /assets\/styles\/anchors\.css/)
  })

  test('NOTHING sets a non-zero scroll-padding on the root: it scrolls the page to the top when a fixed element is focused', () => {
    const files: Record<string, string> = {}
    for (const f of walk(src).filter((x) => /\.(vue|css)$/.test(x))) files[f.slice(src.length)] = readFileSync(f, 'utf8')
    assert.deepEqual(rootPaddingProblems(files), [])
  })

  describe('the rule itself (checked on in-memory files)', () => {
    test('a non-zero root padding is reported, however it is spelled', () => {
      assert.equal(rootPaddingProblems({ 'a.css': 'html { scroll-padding-top: 84px; }' }).length, 1)
      assert.equal(rootPaddingProblems({ 'a.css': ':root { scroll-padding: 10px 0 0; }' }).length, 1)
      assert.equal(rootPaddingProblems({ 'a.vue': '<style>\nhtml:has(.x), body { scroll-padding-top: var(--n); }\n</style>' }).length, 1)
      assert.equal(rootPaddingProblems({ 'a.css': 'html{scroll-padding-top:calc(1px + 2px)}' }).length, 1)
    })

    test('zero is allowed (it only switches the padding off), and so are other selectors, margins and comments', () => {
      assert.deepEqual(rootPaddingProblems({ 'a.css': 'html:has(.legal-page) {\n  scroll-padding-top: 0;\n}' }), [])
      assert.deepEqual(rootPaddingProblems({ 'a.css': 'html { scroll-padding-top: 0px; }' }), [])
      assert.deepEqual(rootPaddingProblems({ 'a.css': '.panel { scroll-padding-top: 40px; }' }), [], 'a scroll container of its own is fine')
      assert.deepEqual(rootPaddingProblems({ 'a.css': 'h2 { scroll-margin-top: 84px; }' }), [])
      assert.deepEqual(rootPaddingProblems({ 'a.css': '/* html { scroll-padding-top: 84px; } */' }), [])
    })
  })
})
