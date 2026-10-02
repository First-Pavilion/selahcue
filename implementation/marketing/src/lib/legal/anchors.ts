/**
 * Moving to a section of a legal page.
 *
 * ONE MECHANISM FOR "BELOW THE STICKY NAVBAR": each section starts with a zero-height
 * `<span class="legal-anchor">` lifted by `--legal-anchor-offset` (navbar height plus
 * air, see LegalPage.vue), and the id lives on that span. The router's `scrollBehavior`
 * scrolls to an element's raw top and ignores CSS `scroll-margin`/`scroll-padding`, so the
 * lift is what makes a router-driven deep link (`/privacy#s-3-8`) land with its heading
 * visible. Everything else here lands in the same place because it ALSO scrolls to the
 * anchor's raw top (`scrollToElement` reads only the element's own `scroll-margin-top`,
 * never the page's `scroll-padding-top`), and LegalPage.vue zeroes the page's
 * `scroll-padding-top` while it is mounted. No stylesheet sets one on `html` today (PR #135
 * uses per-element `scroll-margin-top` instead, and a test pins that); this is a guard, so
 * that one added later is not stacked on top of the lift by the browser's own fragment
 * scrolling: a double offset.
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

/**
 * Scroll `el`'s top edge to the top of the viewport, minus the element's OWN
 * `scroll-margin-top`. Deliberately not the built-in scroll-into-view call: that also honours the page's
 * `scroll-padding-top`, which would stack with the anchor lift (see the header).
 */
export function scrollToElement(el: HTMLElement): void {
  const margin = Number.parseFloat(getComputedStyle(el).scrollMarginTop)
  const top = window.scrollY + el.getBoundingClientRect().top - (Number.isFinite(margin) ? margin : 0)
  window.scrollTo({ top: Math.max(0, top), behavior: prefersReducedMotion() ? 'auto' : 'smooth' })
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
    // After the DOM has settled: the caller may have just collapsed the phone Contents
    // list, which sits ABOVE the text, and measuring before that shift scrolls to where the
    // section used to be.
    await nextTick()
    const anchor = document.getElementById(id)
    if (anchor) scrollToElement(anchor)
  } else {
    await router.push({ hash })
  }
  await focusAnchor(id)
}
