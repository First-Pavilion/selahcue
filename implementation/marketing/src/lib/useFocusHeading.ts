/**
 * Move focus to a page's <h1> when the page, or the article within it, changes.
 *
 * Same mechanism the auth pages use (`heading.value?.focus()` on an `<h1 tabindex="-1">`):
 * in a single-page app a route change does not reload anything, so without this a
 * keyboard or screen-reader user stays parked on the link they just activated, with the
 * new article somewhere above or below them. `preventScroll` because the router's
 * `scrollBehavior` already owns scrolling and the two must not fight.
 */
import { nextTick, onMounted, watch, type Ref } from 'vue'

export function useFocusHeading(heading: Ref<HTMLElement | null>, key: () => string): void {
  async function focusIt(): Promise<void> {
    await nextTick()
    heading.value?.focus({ preventScroll: true })
  }
  onMounted(focusIt)
  watch(key, focusIt)
}
