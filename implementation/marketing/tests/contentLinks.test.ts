/**
 * Every internal link in the article content, and in the article views' own templates,
 * must RESOLVE: to a real blog post, a real docs or support article, a real category anchor,
 * or a static page the router actually serves.
 *
 * The old test only checked a link's SHAPE (`/` prefix, no `//`), so `/docs/display-outputs/
 * ndi-typo` passed. Resolution runs against the same lookups the router guards use, and the
 * static page list is read out of `router/index.ts` rather than restated, so a page that is
 * removed from the router turns every link to it red.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { blogPosts } from '../src/lib/content/blog.ts'
import { blogCrumbs, docsCrumbs, supportCrumbs } from '../src/lib/content/breadcrumbs.ts'
import { docsArticles, findDocsArticle, findDocsCategory } from '../src/lib/content/docs.ts'
import { parseInline } from '../src/lib/content/inline.ts'
import { findSupportCategory, supportArticles } from '../src/lib/content/support.ts'
import { headingIds } from '../src/lib/content/text.ts'
import type { Block, KnowledgeArticle } from '../src/lib/content/types.ts'
import { STATIC, whyUnresolvable } from './fixtures/resolveLink.ts'

const read = (rel: string): string => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')

function bodyStrings(body: readonly Block[]): string[] {
  return body.flatMap((b) =>
    b.type === 'ul' || b.type === 'ol' ? [...b.items] : b.type === 'p' || b.type === 'callout' ? [b.text] : [],
  )
}

describe('the resolver is not vacuous', () => {
  test('it reads a real static page list out of the router', () => {
    for (const p of ['/', '/contact', '/pricing', '/blog', '/docs', '/support']) assert.ok(STATIC.has(p), p)
    assert.ok(!STATIC.has('/blog/:slug'))
  })

  test('good links resolve', () => {
    const realHeading = [...headingIds(findDocsArticle('display-outputs', 'ndi-output')!.body).values()][0] as string
    for (const ok of [
      '/contact',
      '/docs/display-outputs/ndi-output',
      '/support/mobile-control/phone-wont-pair',
      '/blog/which-bible-translations-ship-with-selahcue',
      '/docs#display-outputs',
      '/support#mobile-control',
      `/docs/display-outputs/ndi-output#${realHeading}`,
    ]) {
      assert.equal(whyUnresolvable(ok), null, `${ok}: ${whyUnresolvable(ok)}`)
    }
  })

  test('dead links are caught, one per way a link can die', () => {
    for (const dead of [
      '/docs/display-outputs/ndi-typo',
      '/docs/no-such-category/ndi-output',
      '/support/mobile-control/nope',
      '/blog/nope',
      '/nope',
      '/docs#no-such-category',
      '/support#no-such-category',
      '/docs/display-outputs/ndi-output#no-such-heading',
      '/contact#anything',
      '//evil.example/x',
      'javascript:alert(1)',
    ]) {
      assert.notEqual(whyUnresolvable(dead), null, `${dead} should not resolve`)
    }
  })
})

describe('every internal link in the article bodies resolves', () => {
  const all: [string, KnowledgeArticle | { body: readonly Block[] }][] = [
    ...blogPosts.map((a) => [`blog/${a.slug}`, a] as [string, { body: readonly Block[] }]),
    ...docsArticles.map((a) => [`docs/${a.category}/${a.slug}`, a] as [string, KnowledgeArticle]),
    ...supportArticles.map((a) => [`support/${a.category}/${a.slug}`, a] as [string, KnowledgeArticle]),
  ]

  test('there are links to check at all (positive control)', () => {
    const n = all.flatMap(([, a]) => bodyStrings(a.body)).flatMap((s) => parseInline(s)).filter((s) => s.kind === 'link').length
    assert.ok(n >= 15, `only ${n} links in the whole corpus`)
  })

  test('internal links resolve; external ones are https', () => {
    for (const [key, a] of all) {
      for (const s of bodyStrings(a.body)) {
        for (const seg of parseInline(s)) {
          if (seg.kind !== 'link') continue
          if (seg.external) {
            assert.match(seg.href, /^https:\/\//, `${key}: external link must be https`)
          } else {
            assert.equal(whyUnresolvable(seg.href), null, `${key}: dead link ${seg.href} (${whyUnresolvable(seg.href)})`)
          }
        }
        // A written `[label](target)` that did not become a link was rejected as unsafe.
        assert.equal(
          parseInline(s).filter((x) => x.kind === 'link').length,
          (s.match(/\]\(/g) ?? []).length,
          `${key}: a link was written but rejected as unsafe in "${s}"`,
        )
      }
    }
  })
})

describe('literal links in the article views and index views resolve', () => {
  const VIEWS = [
    'BlogPostView', 'DocsArticleView', 'SupportArticleView', 'BlogView', 'DocsView', 'SupportView',
  ].map((n) => [n, read(`../src/views/${n}.vue`)] as const)

  test('every `to="/..."` / `href="/..."` literal resolves', () => {
    let seen = 0
    for (const [name, src] of VIEWS) {
      for (const m of src.matchAll(/(?:\bto|\bhref)="(\/[^"]*)"/g)) {
        seen++
        assert.equal(whyUnresolvable(m[1] as string), null, `${name}: ${m[1]} (${whyUnresolvable(m[1] as string)})`)
      }
    }
    assert.ok(seen >= 3, `only ${seen} literal links found in the views`)
  })
})

describe('every breadcrumb target resolves, for every article', () => {
  // The breadcrumb trails are built in script (`lib/content/breadcrumbs.ts`), where the
  // `to="..."` literal scan above cannot see them; a dead one used to survive the whole suite.
  test('blog posts: Home, Blog, then the post (no link on the current page)', () => {
    assert.ok(blogPosts.length > 0)
    for (const p of blogPosts) {
      const crumbs = blogCrumbs(p)
      assert.deepEqual(crumbs.map((c) => c.to), ['/', '/blog', undefined], p.slug)
      for (const c of crumbs) if (c.to) assert.equal(whyUnresolvable(c.to), null, `${p.slug}: ${c.label} -> ${c.to} (${whyUnresolvable(c.to)})`)
      assert.equal(crumbs[2]!.label, p.title)
    }
  })

  for (const [label, articles, find, crumbsOf, root] of [
    ['docs', docsArticles, findDocsCategory, docsCrumbs, '/docs'],
    ['support', supportArticles, findSupportCategory, supportCrumbs, '/support'],
  ] as const) {
    test(`${label} articles: ${root}, the category anchor, then the article`, () => {
      assert.ok(articles.length > 0)
      for (const a of articles) {
        const category = find(a.category)
        assert.ok(category, `${a.slug}: its category does not exist`)
        const crumbs = crumbsOf(a, category!)
        assert.equal(crumbs.length, 3)
        assert.equal(crumbs[0]!.to, root)
        assert.equal(crumbs[1]!.to, `${root}#${a.category}`)
        assert.equal(crumbs[2]!.to, undefined, 'the current page is not a link')
        for (const c of crumbs) if (c.to) assert.equal(whyUnresolvable(c.to), null, `${a.category}/${a.slug}: ${c.label} -> ${c.to} (${whyUnresolvable(c.to)})`)
        assert.equal(crumbs[2]!.label, a.title)
      }
    })
  }

  test('the views build their trail from these functions, not from a private copy', () => {
    for (const [view, fn] of [['BlogPostView', 'blogCrumbs'], ['DocsArticleView', 'docsCrumbs'], ['SupportArticleView', 'supportCrumbs']] as const) {
      const src = read(`../src/views/${view}.vue`)
      assert.match(src, new RegExp(`<BreadcrumbTrail :items="${fn}\\(`), `${view} should call ${fn}`)
      assert.ok(!/:items="\[/.test(src), `${view} still builds an inline breadcrumb array`)
    }
  })
})
