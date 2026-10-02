/**
 * Source tripwires for what the article renderer must never do. Same style as the index
 * tripwires in `content.test.ts`: lexical, exact and instant. They are the cheap first line,
 * not the boundary; the boundary is that article text is typed blocks rendered through Vue's
 * text interpolation (see `lib/content/inline.ts`), which `content.test.ts` pins behaviourally.
 */
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

const SRC = fileURLToPath(new URL('../src/', import.meta.url))
const ARTICLE_COMPONENTS = readdirSync(join(SRC, 'components/article')).filter((f) => f.endsWith('.vue')).map((f) => `components/article/${f}`)
const ARTICLE_VIEWS = ['BlogPostView', 'DocsArticleView', 'SupportArticleView'].map((n) => `views/${n}.vue`)
const FILES = [...ARTICLE_COMPONENTS, ...ARTICLE_VIEWS, 'lib/content/inline.ts']
const read = (rel: string): string => readFileSync(join(SRC, rel), 'utf8')

/** Everything outside comments, so a sentence ABOUT v-html is not mistaken for using it. */
function code(rel: string): string {
  return read(rel).replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

describe('article code never injects markup', () => {
  test('the scan covers real files (positive control)', () => {
    assert.ok(ARTICLE_COMPONENTS.length >= 4, 'components/article should hold the renderer parts')
    assert.ok(ARTICLE_COMPONENTS.includes('components/article/ArticleBody.vue'))
    for (const f of FILES) assert.ok(read(f).length > 100, `${f} is empty`)
  })

  test('no v-html, innerHTML, outerHTML, insertAdjacentHTML, document.write or eval', () => {
    for (const f of FILES) {
      assert.ok(
        !/\bv-html\b|\.innerHTML\b|\.outerHTML\b|insertAdjacentHTML|document\.write\b|\beval\s*\(|new Function\s*\(/.test(code(f)),
        `${f} can turn a string into markup`,
      )
    }
  })
})

describe('links that open a new tab cannot reach back into this one', () => {
  test('every element with target="_blank" also carries rel="noopener noreferrer"', () => {
    let blank = 0
    for (const f of FILES.filter((x) => x.endsWith('.vue'))) {
      for (const tag of code(f).matchAll(/<(?:a|router-link)\b[^>]*>/g)) {
        if (!/target="_blank"/.test(tag[0])) continue
        blank++
        assert.match(tag[0], /rel="noopener noreferrer"/, `${f}: ${tag[0].slice(0, 80)}`)
      }
    }
    assert.ok(blank >= 3, `only ${blank} new-tab links found; the scan is not seeing them`)
  })
})
