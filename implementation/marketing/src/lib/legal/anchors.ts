/**
 * Moving to a section of a legal page.
 *
 * ANCHORS CARRY THEIR OWN OFFSET. The site's navbar is sticky (68px) and the router's
 * `scrollBehavior` scrolls to an element's raw top, ignoring CSS `scroll-margin-top`, so
 * a deep link such as `/privacy#s-3-8` would land with its heading hidden under the bar.
 * Each section therefore starts with a zero-height `<span class="anchor">` shifted up by
 * the bar's height (see LegalPage.vue); the id lives on that span, so ANY way of arriving
 * (router, native fragment navigation, a pasted URL) ends with the heading visible. The
 * element that follows the anchor is the heading or paragraph itself.
 */
import { nextTick } from 'vue'
import type { Router } from 'vue-router'

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
}

/** The visible thing an anchor stands for: the element right after the zero-height span. */
function anchorTarget(id: string): HTMLElement | null {
  const anchor = document.getElementById(id)
  const next = anchor?.nextElementSibling
  return next instanceof HTMLElement ? next : null
}

/** Move keyboard focus to the section so the next Tab continues from there. */
export async function focusAnchor(id: string): Promise<void> {
  await nextTick()
  const target = anchorTarget(id)
  if (!target) return
  if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1')
  target.focus({ preventScroll: true })
}

/**
 * Navigate to `#id`: update the URL (so the section is shareable and Back works), scroll,
 * and focus. Navigating to the hash the URL already has is a no-op for the router, so that
 * case scrolls by hand — otherwise a second click on the same Contents entry, after the
 * reader has scrolled away, would do nothing.
 */
export async function goToAnchor(router: Router, id: string): Promise<void> {
  const hash = `#${id}`
  if (router.currentRoute.value.hash === hash) {
    document.getElementById(id)?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' })
  } else {
    await router.push({ hash })
  }
  await focusAnchor(id)
}
