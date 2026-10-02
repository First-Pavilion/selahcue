/**
 * Router resolution for the blog / docs / support detail pages, run through a REAL
 * vue-router (memory history) built from the same route records `router/index.ts` uses.
 *
 * What the router promises: every real article path resolves to its detail route with the
 * slugs as props, and ANY path under these prefixes (real or not) resolves to a matched
 * component with the address bar left exactly as typed. Deciding that a slug names nothing
 * is the view's job (it renders the not-found page, embedded); that decision runs on every
 * param change and is tested through the lookups here and in a real browser in
 * `scripts/article_pages_headless.py`. A category-only prefix has no route and falls to the
 * site catch-all.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'
import { createMemoryHistory, createRouter, type RouteRecordRaw, type Router } from 'vue-router'

import { blogPath, blogPosts, findBlogPost } from '../src/lib/content/blog.ts'
import { docsArticles, docsPath, findDocsArticle } from '../src/lib/content/docs.ts'
import { findSupportArticle, supportArticles, supportPath } from '../src/lib/content/support.ts'
import { articleRoutes } from '../src/router/articleRoutes.ts'

const stub = { render: () => null }
const CATCH_ALL = 'not-found'

/** The article routes plus a stand-in for index.ts's catch-all, which cannot load in node. */
function makeRouter(): Router {
  // vue-router CALLS a lazy `component: () => import('@/views/…vue')` while it navigates,
  // and node can resolve neither the `@` alias nor a .vue file. Swap in a stub for the
  // component only; `path`, `name` and `props` are the real records.
  const articles = articleRoutes.map((r) => ({ ...r, component: stub })) as RouteRecordRaw[]
  const routes: RouteRecordRaw[] = [
    { path: '/blog', name: 'blog', component: stub },
    { path: '/docs', name: 'docs', component: stub },
    { path: '/support', name: 'support', component: stub },
    ...articles,
    { path: '/:pathMatch(.*)*', name: CATCH_ALL, component: stub },
  ]
  return createRouter({ history: createMemoryHistory(), routes })
}

async function land(router: Router, path: string): Promise<{ name: unknown; fullPath: string; matched: number }> {
  await router.push(path)
  await router.isReady()
  const r = router.currentRoute.value
  return { name: r.name, fullPath: r.fullPath, matched: r.matched.length }
}

describe('the real route records', () => {
  test('each detail route lazy-loads its own view and passes its slugs as props', () => {
    assert.deepEqual(articleRoutes.map((r) => r.name), ['blog-post', 'docs-article', 'support-article'])
    for (const r of articleRoutes) {
      assert.equal(typeof r.component, 'function', `${String(r.name)} should lazy-load its view`)
      assert.equal(r.props, true)
      assert.equal(r.beforeEnter, undefined, `${String(r.name)} must not gate on a guard: guards miss param-only changes`)
    }
  })
})

describe('every real article resolves to its detail route', () => {
  test('there are articles to resolve (positive control)', () => {
    assert.ok(blogPosts.length > 0 && docsArticles.length > 0 && supportArticles.length > 0)
  })

  test('blog posts, docs articles and support articles', async () => {
    for (const p of blogPosts) {
      const got = await land(makeRouter(), blogPath(p.slug))
      assert.deepEqual([got.name, got.fullPath], ['blog-post', `/blog/${p.slug}`])
    }
    for (const a of docsArticles) {
      const got = await land(makeRouter(), docsPath(a))
      assert.deepEqual([got.name, got.fullPath], ['docs-article', docsPath(a)])
    }
    for (const a of supportArticles) {
      const got = await land(makeRouter(), supportPath(a))
      assert.deepEqual([got.name, got.fullPath], ['support-article', supportPath(a)])
    }
  })

  test('the slugs reach the view as props', async () => {
    const router = makeRouter()
    const a = docsArticles[0]!
    await router.push(docsPath(a))
    assert.equal(router.currentRoute.value.matched[0]!.props.default, true)
    assert.deepEqual(router.currentRoute.value.params, { category: a.category, slug: a.slug })
  })
})

describe('an unknown slug keeps its URL byte for byte and still has a component to render', () => {
  // Real and made-up paths alike. The encoded ones are the regression: the old redirect fed
  // the ENCODED path back through `pathMatch`, so %20 became %2520 in the address bar.
  const UNKNOWN = [
    '/blog/no-such-post',
    '/blog/NO-SUCH-POST',
    '/docs/getting-started/no-such-article',
    '/docs/no-such-category/no-such-article',
    '/support/troubleshooting/no-such-article',
    '/support/no-such-category/x',
    '/blog/a%20b',
    '/blog/%C3%A9',
    '/blog/caf%C3%A9-au-lait',
    '/docs/x%2Fy/z',
    '/docs/getting-started/a%2Fb',
    '/blog/100%25',
    '/blog/%ZZ',
    '/docs/%ZZ/%E0%A4%A',
    '/blog/no-such-post?ref=email#top',
  ]

  for (const path of UNKNOWN) {
    test(path, async () => {
      const got = await land(makeRouter(), path)
      assert.ok(got.matched > 0, 'a route with no matched component is a blank page')
      assert.equal(got.fullPath, path, "the visitor's address must not be rewritten")
    })
  }

  test('these slugs all fail the lookup, so the view will render the not-found page', () => {
    for (const bad of ['no-such-post', 'a b', 'é', 'NO-SUCH-POST', '%ZZ', '', 'a/b']) {
      assert.equal(findBlogPost(bad), undefined, bad)
    }
    assert.equal(findDocsArticle('x/y', 'z'), undefined)
    assert.equal(findSupportArticle('troubleshooting', 'no-such-article'), undefined)
  })

  test('a malformed escape (%ZZ) never throws out of the router', async () => {
    await assert.doesNotReject(land(makeRouter(), '/blog/%ZZ'))
    await assert.doesNotReject(land(makeRouter(), '/docs/%E0%A4%A/%ZZ'))
  })

  test('same-route PARAM change (article to an unknown slug) is a navigation the view must handle', async () => {
    // A `beforeEnter` guard never fires here, which is why the check lives in the view.
    const router = makeRouter()
    await router.push(blogPath(blogPosts[0]!.slug))
    assert.equal(router.currentRoute.value.name, 'blog-post')
    await router.push('/blog/no-such-post')
    const r = router.currentRoute.value
    assert.equal(r.name, 'blog-post', 'same record, new params: the component is reused, not re-created')
    assert.equal(r.params.slug, 'no-such-post')
    assert.equal(r.fullPath, '/blog/no-such-post')
    assert.equal(findBlogPost(r.params.slug), undefined)
    // And back to a real one, to prove the view's lookup is reactive to params alone.
    await router.push(blogPath(blogPosts[1]!.slug))
    assert.equal(findBlogPost(router.currentRoute.value.params.slug), blogPosts[1])
  })

  test('a real slug under the WRONG category does not resolve (no cross-category aliasing)', () => {
    const a = docsArticles[0]!
    const other = docsArticles.find((x) => x.category !== a.category)!
    assert.equal(findDocsArticle(other.category, a.slug), undefined)
  })

  test('a docs slug is not an article under /support and vice versa', () => {
    const d = docsArticles[0]!
    const s = supportArticles[0]!
    assert.equal(findSupportArticle(d.category, d.slug), undefined)
    assert.equal(findDocsArticle(s.category, s.slug), undefined)
  })

  test('a category-only prefix has no route of its own and falls to the catch-all', async () => {
    const c = docsArticles[0]!.category
    assert.equal((await land(makeRouter(), `/docs/${c}`)).name, CATCH_ALL)
    assert.equal((await land(makeRouter(), `/blog/a/b`)).name, CATCH_ALL)
  })

  test('the existing index routes are untouched', async () => {
    for (const name of ['blog', 'docs', 'support']) {
      assert.equal((await land(makeRouter(), `/${name}`)).name, name)
    }
  })
})
