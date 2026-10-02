/**
 * The router's scroll behaviour: where a navigation lands, and how it gets there.
 *
 * Pure (`scrollFor`) plus a thin browser adapter (`siteScrollBehavior`), so node can test the
 * decisions. Two rules live here that the first version got wrong:
 *
 * 1. IN-PAGE ANCHORS CLEAR THE STICKY NAVBAR. vue-router's `{ el, behavior }` scroll ignores
 *    CSS `scroll-margin`/`scroll-padding`, so a table-of-contents or "link to this section"
 *    click scrolled the heading UNDER the 68px navbar. The offset is not a constant here: it
 *    is the navbar's rendered bottom edge plus `--sc-anchor-gap` (`assets/styles/anchors.css`,
 *    which uses the same gap for the CSS side), so the navbar itself is the source of the
 *    height. Only the blog/docs/support pages opt in; other pages' hash targets (the home
 *    page's `#how-it-works`) keep their previous behaviour.
 * 2. REDUCED MOTION IS HONOURED. `behavior: 'smooth'` written into the scroll position
 *    overrides the CSS `scroll-behavior` that `main.css` already switches off under
 *    `prefers-reduced-motion`, so people who asked for no animation still got one. With
 *    reduced motion the behaviour is `'auto'`, which defers to that CSS (instant).
 */

export interface ScrollEnv {
  /** `matchMedia('(prefers-reduced-motion: reduce)').matches` */
  readonly reducedMotion: boolean
  /** Pixels of sticky chrome to leave above an anchor target. */
  readonly stickyOffset: number
}

export type SiteScrollPosition =
  | { el: string; top: number; behavior: ScrollBehavior }
  | { top: number; behavior: ScrollBehavior }

/** Route names whose in-page anchors sit below the sticky navbar and need the offset. */
const ANCHORED_ROUTES: ReadonlySet<string> = new Set([
  'blog',
  'blog-post',
  'docs',
  'docs-article',
  'support',
  'support-article',
])

export function isAnchoredRoute(name: unknown): boolean {
  return typeof name === 'string' && ANCHORED_ROUTES.has(name)
}

export function scrollFor(to: { hash: string; name?: unknown }, env: ScrollEnv): SiteScrollPosition {
  const behavior: ScrollBehavior = env.reducedMotion ? 'auto' : 'smooth'
  if (to.hash) return { el: to.hash, top: isAnchoredRoute(to.name) ? env.stickyOffset : 0, behavior }
  return { top: 0, behavior }
}

/**
 * The clearance above an anchor target: the sticky navbar's rendered bottom edge plus the CSS
 * gap (`--sc-anchor-gap`, a px literal). 0 when the navbar cannot be measured, which is the
 * previous behaviour (no offset).
 */
export function stickyOffsetFrom(navBottom: number, gap: string): number {
  if (!Number.isFinite(navBottom) || navBottom <= 0) return 0
  const px = Number.parseFloat(gap)
  return navBottom + (Number.isFinite(px) && px > 0 ? px : 0)
}

/** The real browser, for `createRouter({ scrollBehavior })`. */
export function siteScrollBehavior(to: { hash: string; name?: unknown }): SiteScrollPosition {
  // The first <header> in the app is the site navbar (App.vue renders it before the page).
  const navBottom = document.querySelector('#app header')?.getBoundingClientRect().bottom ?? 0
  const gap = getComputedStyle(document.documentElement).getPropertyValue('--sc-anchor-gap')
  return scrollFor(to, {
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    stickyOffset: stickyOffsetFrom(navBottom, gap),
  })
}
