/**
 * Move focus to a page's <h1> when the visitor navigates to a page, or to another article
 * within it.
 *
 * Same mechanism the auth pages use (`heading.value?.focus()` on an `<h1 tabindex="-1">`):
 * in a single-page app a route change does not reload anything, so without this a
 * keyboard or screen-reader user stays parked on the link they just activated, with the
 * new article somewhere above or below them. `preventScroll` because the router's
 * `scrollBehavior` already owns scrolling and the two must not fight.
 *
 * NOT ON A DIRECT LOAD. When the page is the first thing the visitor opened (a link, a
 * bookmark, a refresh of the very first entry) the browser has already announced it and
 * focus belongs at the top of the document: moving it to the h1 would put it PAST the
 * navigation and the "Skip to article" link, so the first Tab would skip them
 * (`cameFromInsideTheApp` decides).
 */
import { nextTick, onMounted, watch, type Ref } from 'vue'
import { cameFromInsideTheApp } from './pageFocus.ts'

export function useFocusHeading(heading: Ref<HTMLElement | null>, key: () => string): void {
  async function focusIt(): Promise<void> {
    await nextTick()
    heading.value?.focus({ preventScroll: true })
  }
  onMounted(() => {
    if (cameFromInsideTheApp(window.history.state)) void focusIt()
  })
  watch(key, focusIt)
}
