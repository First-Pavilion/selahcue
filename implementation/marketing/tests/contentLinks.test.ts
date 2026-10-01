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

import { blogPosts, findBlogPost } from '../src/lib/content/blog.ts'
import { docsArticles, docsCategories, findDocsArticle } from '../src/lib/content/docs.ts'
import { classifyHref, parseInline } from '../src/lib/content/inline.ts'
import { headingIds } from '../src/lib/content/text.ts'
import { findSupportArticle, supportArticles, supportCategories } from '../src/lib/content/support.ts'
import type { Block, KnowledgeArticle } from '../src/lib/content/types.ts'

const read = (rel: string): string => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')

/** Literal, parameter-free paths from router/index.ts: `path: '/pricing'` and friends. */
function staticPaths(): Set<string> {
  const src = read('../src/router/index.ts')
  const out = new Set<string>()
  for (const m of src.matchAll(/path:\s*'(\/[a-z0-9\-/]*)'/g)) out.add(m[1] as string)
  return out
}
const STATIC = staticPaths()

function articleHeadingIds(a: KnowledgeArticle | { body: readonly Block[] }): Set<string> {
  return new Set(headingIds(a.body).values())
}

/** `null` when the link resolves, otherwise a reason. Only same-site paths are resolved. */
export function whyUnresolvable(href: string): string | null {
  if (classifyHref(href) !== 'internal') return 'not a same-site path'
  const hashAt = href.indexOf('#')
  const hash = hashAt === -1 ? '' : href.slice(hashAt + 1)
  const base = (hashAt === -1 ? href : href.slice(0, hashAt)).split('?')[0] as string

  let m = /^\/blog\/([^/]+)$/.exec(base)
  if (m) {
    const post = findBlogPost(m[1])
    if (!post) return `no blog post "${m[1]}"`
    return hash && !articleHeadingIds(post).has(hash) ? `no heading #${hash} in that post` : null
  }
  m = /^\/docs\/([^/]+)\/([^/]+)$/.exec(base)
  if (m) {
    const a = findDocsArticle(m[1], m[2])
    if (!a) return `no docs article ${m[1]}/${m[2]}`
    return hash && !articleHeadingIds(a).has(hash) ? `no heading #${hash} in that article` : null
  }
  m = /^\/support\/([^/]+)\/([^/]+)$/.exec(base)
  if (m) {
    const a = findSupportArticle(m[1], m[2])
    if (!a) return `no support article ${m[1]}/${m[2]}`
    return hash && !articleHeadingIds(a).has(hash) ? `no heading #${hash} in that article` : null
  }
  if (!STATIC.has(base)) return `no such page ${base}`
  if (!hash) return null
  if (base === '/docs') return docsCategories.some((c) => c.id === hash) ? null : `no docs category #${hash}`
  if (base === '/support') return supportCategories.some((c) => c.id === hash) ? null : `no support category #${hash}`
  return `cannot verify an anchor on ${base}`
}

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
