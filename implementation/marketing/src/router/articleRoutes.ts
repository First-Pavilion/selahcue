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
    // The guards load the corpus on demand. A STATIC import here would pull every article
    // body into the entry chunk, because this module is imported by `router/index.ts`
    // (measured: entry 80.8 -> 161.5 kB), and the home page would ship article text.
    beforeEnter: async (to) => {
      const { findBlogPost } = await import('../lib/content/blog.ts')
      return findBlogPost(to.params.slug) ? true : notFoundFor(to)
    },
  },
  {
    path: '/docs/:category/:slug',
    name: 'docs-article',
    component: () => import('@/views/DocsArticleView.vue'),
    props: true,
    beforeEnter: async (to) => {
      const { findDocsArticle } = await import('../lib/content/docs.ts')
      return findDocsArticle(to.params.category, to.params.slug) ? true : notFoundFor(to)
    },
  },
  {
    path: '/support/:category/:slug',
    name: 'support-article',
    component: () => import('@/views/SupportArticleView.vue'),
    props: true,
    beforeEnter: async (to) => {
      const { findSupportArticle } = await import('../lib/content/support.ts')
      return findSupportArticle(to.params.category, to.params.slug) ? true : notFoundFor(to)
    },
  },
]

/**
 * Pixels to leave above an in-page anchor target so it is not hidden by the sticky navbar
 * (68px tall, `Navbar.vue`) with some breathing room.
 *
 * vue-router's `{ el, behavior }` scroll ignores CSS `scroll-margin-top`, so without an
 * explicit `top` a table-of-contents or "link to this section" click scrolls the heading
 * UNDER the navbar. Only these routes opt in: other pages' hash targets (the home page's
 * `#how-it-works`) keep their existing behaviour.
 */
export const STICKY_NAV_OFFSET = 84

const ANCHORED_ROUTES: ReadonlySet<string> = new Set([
  'blog',
  'blog-post',
  'docs',
  'docs-article',
  'support',
  'support-article',
])

export function hashScrollOffset(to: Pick<RouteLocationNormalized, 'name'>): number {
  return typeof to.name === 'string' && ANCHORED_ROUTES.has(to.name) ? STICKY_NAV_OFFSET : 0
}
