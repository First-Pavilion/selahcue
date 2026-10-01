/**
 * Router resolution for the blog / docs / support detail pages, run through a REAL
 * vue-router (memory history) built from the same route records `router/index.ts` uses.
 *
 * The important property is the negative one: an unknown slug must land on the existing
 * `not-found` route with the visitor's URL intact — never a blank page (no matched
 * component), which is the dead end the catch-all was added to close.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'
import { createMemoryHistory, createRouter, type RouteRecordRaw, type Router } from 'vue-router'

import { blogPath, blogPosts } from '../src/lib/content/blog.ts'
import { docsArticles, docsPath } from '../src/lib/content/docs.ts'
import { supportArticles, supportPath } from '../src/lib/content/support.ts'
import { NOT_FOUND_ROUTE, articleRoutes } from '../src/router/articleRoutes.ts'

const stub = { render: () => null }

/** The article routes plus a stand-in for index.ts's catch-all, which cannot load in node. */
function makeRouter(): Router {
  // vue-router CALLS a lazy `component: () => import('@/views/…vue')` while it navigates,
  // and node can resolve neither the `@` alias nor a .vue file. Swap in a stub for the
  // component only; `path`, `name`, `props` and `beforeEnter` — everything under test — are
  // the real records.
  const articles = articleRoutes.map((r) => ({ ...r, component: stub })) as RouteRecordRaw[]
  const routes: RouteRecordRaw[] = [
    { path: '/blog', name: 'blog', component: stub },
    { path: '/docs', name: 'docs', component: stub },
    { path: '/support', name: 'support', component: stub },
    ...articles,
    { path: '/:pathMatch(.*)*', name: NOT_FOUND_ROUTE, component: stub },
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
  test('each detail route lazy-loads its own view, takes props, and guards with beforeEnter', () => {
    assert.deepEqual(
      articleRoutes.map((r) => r.name),
      ['blog-post', 'docs-article', 'support-article'],
    )
    for (const r of articleRoutes) {
      assert.equal(typeof r.component, 'function', `${String(r.name)} should lazy-load its view`)
      assert.equal(r.props, true)
      assert.equal(typeof r.beforeEnter, 'function', `${String(r.name)} must guard unknown slugs`)
    }
  })
})

describe('every real article resolves to its detail route', () => {
  test('there are articles to resolve (positive control)', () => {
    assert.ok(blogPosts.length > 0 && docsArticles.length > 0 && supportArticles.length > 0)
  })

  test('blog posts', async () => {
    for (const p of blogPosts) {
      const got = await land(makeRouter(), blogPath(p.slug))
      assert.equal(got.name, 'blog-post', p.slug)
      assert.equal(got.fullPath, `/blog/${p.slug}`)
      assert.ok(got.matched > 0)
    }
  })

  test('docs articles', async () => {
    for (const a of docsArticles) {
      const got = await land(makeRouter(), docsPath(a))
      assert.equal(got.name, 'docs-article', `${a.category}/${a.slug}`)
      assert.equal(got.fullPath, docsPath(a))
    }
  })

  test('support articles', async () => {
    for (const a of supportArticles) {
      const got = await land(makeRouter(), supportPath(a))
      assert.equal(got.name, 'support-article', `${a.category}/${a.slug}`)
      assert.equal(got.fullPath, supportPath(a))
    }
  })

  test('the slugs reach the view as props', async () => {
    const router = makeRouter()
    const a = docsArticles[0]!
    await router.push(docsPath(a))
    const record = router.currentRoute.value.matched[0]!
    assert.equal(record.props.default, true)
    assert.deepEqual(router.currentRoute.value.params, { category: a.category, slug: a.slug })
  })
})

describe('an unknown slug lands on not-found, not on a blank page', () => {
  const MISSES = [
    '/blog/no-such-post',
    '/blog/NO-SUCH-POST',
    '/docs/getting-started/no-such-article',
    '/docs/no-such-category/no-such-article',
    '/support/troubleshooting/no-such-article',
    '/support/no-such-category/x',
  ]

  for (const path of MISSES) {
    test(path, async () => {
      const got = await land(makeRouter(), path)
      assert.equal(got.name, NOT_FOUND_ROUTE)
      assert.ok(got.matched > 0, 'a route with no matched component is a blank page')
      assert.equal(got.fullPath, path, 'the visitor\'s URL must survive the redirect')
    })
  }

  test('a real slug under the WRONG category is not found (no cross-category aliasing)', async () => {
    const [a, b] = [docsArticles[0]!, docsArticles.find((x) => x.category !== docsArticles[0]!.category)!]
    const got = await land(makeRouter(), `/docs/${b.category}/${a.slug}`)
    assert.equal(got.name, NOT_FOUND_ROUTE)
  })

  test('a docs slug is not reachable under /support and vice versa', async () => {
    const d = docsArticles[0]!
    const s = supportArticles[0]!
    assert.equal((await land(makeRouter(), `/support/${d.category}/${d.slug}`)).name, NOT_FOUND_ROUTE)
    assert.equal((await land(makeRouter(), `/docs/${s.category}/${s.slug}`)).name, NOT_FOUND_ROUTE)
  })

  test('query string and hash survive the not-found redirect', async () => {
    const got = await land(makeRouter(), '/blog/nope?ref=email#top')
    assert.equal(got.name, NOT_FOUND_ROUTE)
    assert.equal(got.fullPath, '/blog/nope?ref=email#top')
  })

  test('a category-only prefix has no route of its own and falls to the catch-all', async () => {
    const c = docsArticles[0]!.category
    assert.equal((await land(makeRouter(), `/docs/${c}`)).name, NOT_FOUND_ROUTE)
  })

  test('the existing index routes are untouched', async () => {
    for (const name of ['blog', 'docs', 'support']) {
      assert.equal((await land(makeRouter(), `/${name}`)).name, name)
    }
  })
})

describe('index.ts wires the article routes ahead of the catch-all', () => {
  // index.ts cannot be imported under node (it pulls in .vue files), so this reads it. It is
  // a tripwire for the one edit that would silently bring back blank pages: dropping the
  // spread, or defining a second hand-written copy of these routes that skips the guard.
  const src = readFileSync(fileURLToPath(new URL('../src/router/index.ts', import.meta.url)), 'utf8')

  test('spreads articleRoutes, and before the not-found catch-all', () => {
    const spread = src.indexOf('...articleRoutes')
    const catchAll = src.indexOf("name: 'not-found'")
    assert.ok(spread > -1, 'router/index.ts must spread articleRoutes')
    assert.ok(catchAll > -1)
    assert.ok(spread < catchAll)
  })

  test('uses the catch-all name articleRoutes redirects to', () => {
    assert.ok(src.includes(`name: '${NOT_FOUND_ROUTE}'`))
  })

  test('does not declare its own /blog/:slug, /docs/:category/:slug or /support/:category/:slug', () => {
    for (const p of ["'/blog/:slug'", "'/docs/:category/:slug'", "'/support/:category/:slug'"]) {
      assert.ok(!src.includes(`path: ${p}`), `${p} is declared in index.ts, bypassing the unknown-slug guard`)
    }
  })
})
