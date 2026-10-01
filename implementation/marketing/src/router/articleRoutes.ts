/**
 * Routes for the blog / docs / support detail pages (GAP-08, handoff §9).
 *
 * Kept in their own module, not inlined in `index.ts`, so `tests/articleRoutes.test.ts`
 * can build a real vue-router from them under `node --test`. `index.ts` imports
 * `HomeView.vue` and the session store, neither of which node can load.
 *
 * UNKNOWN SLUGS. A path under these prefixes that names no article must not render a
 * blank page — the same dead end MEDIUM-4 closed with the catch-all. `beforeEnter`
 * checks the content source and, on a miss, sends the visitor to the existing
 * `not-found` route WITH THE URL PRESERVED (the `pathMatch` pattern from the vue-router
 * docs), so the address bar still shows what they typed, the status of the page is
 * honest, and they get NotFoundView's way forward. A path that is only a PREFIX
 * (`/docs/getting-started`) matches no route here at all and falls through to the same
 * catch-all.
 */
import type { RouteLocationNormalized, RouteLocationRaw, RouteRecordRaw } from 'vue-router'
import { findBlogPost } from '../lib/content/blog.ts'
import { findDocsArticle } from '../lib/content/docs.ts'
import { findSupportArticle } from '../lib/content/support.ts'

/** The existing catch-all's route name — see `index.ts`. */
export const NOT_FOUND_ROUTE = 'not-found'

export function notFoundFor(to: RouteLocationNormalized): RouteLocationRaw {
  return {
    name: NOT_FOUND_ROUTE,
    // Same shape the catch-all `/:pathMatch(.*)*` produces for this path.
    params: { pathMatch: to.path.substring(1).split('/') },
    query: to.query,
    hash: to.hash,
  }
}

export const articleRoutes: RouteRecordRaw[] = [
  {
    path: '/blog/:slug',
    name: 'blog-post',
    component: () => import('@/views/BlogPostView.vue'),
    props: true,
    beforeEnter: (to) => (findBlogPost(to.params.slug) ? true : notFoundFor(to)),
  },
  {
    path: '/docs/:category/:slug',
    name: 'docs-article',
    component: () => import('@/views/DocsArticleView.vue'),
    props: true,
    beforeEnter: (to) => (findDocsArticle(to.params.category, to.params.slug) ? true : notFoundFor(to)),
  },
  {
    path: '/support/:category/:slug',
    name: 'support-article',
    component: () => import('@/views/SupportArticleView.vue'),
    props: true,
    beforeEnter: (to) => (findSupportArticle(to.params.category, to.params.slug) ? true : notFoundFor(to)),
  },
]
