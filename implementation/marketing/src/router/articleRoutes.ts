/**
 * Routes for the blog / docs / support detail pages (GAP-08, handoff §9).
 *
 * Kept in their own module, not inlined in `index.ts`, so `tests/articleRoutes.test.ts`
 * can build a real vue-router from them under `node --test`. `index.ts` imports
 * `HomeView.vue` and the session store, neither of which node can load.
 *
 * UNKNOWN SLUGS ARE THE VIEW'S JOB, NOT THE ROUTER'S. The first version redirected an
 * unknown slug to the `not-found` route from a `beforeEnter` guard. That had three faults:
 *   - `beforeEnter` does not run when only the params change, so going from one article to
 *     an unknown slug skipped it (stale title, empty description, a blank-looking page);
 *   - the redirect fed the already-encoded `to.path` back through `pathMatch`, so
 *     `/blog/a%20b` became `/blog/a%2520b` in the address bar;
 *   - the guard had to load the whole article corpus into the entry chunk to check a slug.
 * Each view now looks its own article up (it has to, to render it) and shows the not-found
 * page, embedded, when there is none. That runs on EVERY param change, never rewrites the
 * address bar, and needs no guard. A path that is only a PREFIX (`/docs/getting-started`)
 * matches none of these records and falls through to the site's catch-all as before.
 */
import type { RouteRecordRaw } from 'vue-router'

export const articleRoutes: RouteRecordRaw[] = [
  { path: '/blog/:slug', name: 'blog-post', component: () => import('@/views/BlogPostView.vue'), props: true },
  {
    path: '/docs/:category/:slug',
    name: 'docs-article',
    component: () => import('@/views/DocsArticleView.vue'),
    props: true,
  },
  {
    path: '/support/:category/:slug',
    name: 'support-article',
    component: () => import('@/views/SupportArticleView.vue'),
    props: true,
  },
]
