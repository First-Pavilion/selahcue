/**
 * Media queries in the files this feature owns must use the COMPLEMENTARY form of the
 * design's breakpoints (handoff section 8a: tablet starts at 768, desktop at 1200).
 *
 * A range that ends at `max-width: 767px` leaves a gap above it: at a fractional viewport
 * width (browser zoom produces 767.5px) neither `max-width: 767px` nor `min-width: 768px`
 * matches, and the page gets half of each layout. The complementary end is `767.98px`.
 *
 * The responsive pass (a separate PR) enforces the same rule site-wide. This is the same rule
 * scoped to what this feature added (the article components, the three article views and
 * `anchors.css`), so it holds even when that PR has not landed: the rest of `src/` still has
 * whole-pixel queries from before and is that PR's to convert.
 */
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

/** The design's range ends and starts. Anything else in an owned file is a typo or a drift. */
const MAX_ENDS = [767.98, 1199.98]
const MIN_STARTS = [768, 1200]

/** `@media` lines in `text` whose width conditions are not the complementary design values. */
export function mediaProblems(text: string): string[] {
  const problems: string[] = []
  for (const line of text.split('\n')) {
    if (!line.includes('@media')) continue
    for (const m of line.matchAll(/\((max|min)-width:\s*([0-9.]+)px\)/g)) {
      const value = Number(m[2])
      const allowed = m[1] === 'max' ? MAX_ENDS : MIN_STARTS
      if (!allowed.includes(value)) problems.push(`${line.trim()}  (${m[1]}-width ${value}px is not one of ${allowed.join(', ')})`)
    }
  }
  return problems
}

const SRC = fileURLToPath(new URL('../src/', import.meta.url))
const dir = (rel: string): string[] => readdirSync(join(SRC, rel)).filter((f) => /\.(vue|css)$/.test(f)).map((f) => `${rel}/${f}`)
const OWNED = [
  ...dir('components/article'),
  'views/BlogPostView.vue',
  'views/DocsArticleView.vue',
  'views/SupportArticleView.vue',
  'assets/styles/anchors.css',
]

describe('the rule', () => {
  test('whole-pixel range ends are reported, complementary ones are not', () => {
    assert.equal(mediaProblems('@media (max-width: 767px) {').length, 1)
    assert.equal(mediaProblems('@media (max-width: 1199px) {').length, 1)
    assert.equal(mediaProblems('@media (max-width: 768px) {').length, 1)
    assert.equal(mediaProblems('@media (max-width: 900px) {').length, 1)
    assert.equal(mediaProblems('@media (min-width: 767px) {').length, 1, 'a min that starts below 768 overlaps the mobile range')
    assert.equal(mediaProblems('@media (min-width: 1199px) {').length, 1)
    assert.deepEqual(mediaProblems('@media (max-width: 767.98px) {\n@media (max-width: 1199.98px) {\n@media (min-width: 768px) {\n@media (min-width: 1200px) {'), [])
  })

  test('a compound query is checked condition by condition, and non-width queries are ignored', () => {
    assert.equal(mediaProblems('@media (min-width: 768px) and (max-width: 1199px) {').length, 1)
    assert.deepEqual(mediaProblems('@media (min-width: 768px) and (max-width: 1199.98px) {'), [])
    assert.deepEqual(mediaProblems('@media (hover: none) { .a { opacity: 0.7; } }\n@media (prefers-reduced-motion: reduce) {'), [])
    assert.deepEqual(mediaProblems('.a { max-width: 767px; }'), [], 'a max-width PROPERTY is not a media query')
  })
})

describe('the files this feature owns', () => {
  test('the scan covers real files with real queries (positive control)', () => {
    assert.ok(OWNED.length >= 8, `only ${OWNED.length} owned files found`)
    const queries = OWNED.flatMap((f) => readFileSync(join(SRC, f), 'utf8').split('\n')).filter((l) => /@media[^{]*(max|min)-width/.test(l))
    assert.ok(queries.length >= 8, `only ${queries.length} width queries found; the scan is not seeing them`)
    assert.ok(queries.some((l) => l.includes('767.98px')) && queries.some((l) => l.includes('1199.98px')))
  })

  for (const file of OWNED) {
    test(file, () => assert.deepEqual(mediaProblems(readFileSync(join(SRC, file), 'utf8')), []))
  }
})
