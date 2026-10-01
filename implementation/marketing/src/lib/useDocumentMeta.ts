/**
 * Per-page `document.title` and meta description for the article detail pages.
 *
 * The site had no title management at all (every route showed the `index.html` title), so
 * this is new, and it is deliberately small: set on setup, follow the reactive getters,
 * and give the title back on unmount.
 *
 * GIVE-BACK IS CONDITIONAL, and that is the point. App.vue wraps the router view in
 * <Suspense>, which sets up the NEW page before it unmounts the OLD one. A naive
 * "restore the title I saw at setup on unmount" would therefore run AFTER the next page
 * had set its own title and overwrite it with a stale one. Restoring only when the title
 * is still the one THIS instance wrote keeps article -> article correct.
 */
import { onBeforeUnmount, watchEffect } from 'vue'
import { pageTitle } from './content/text.ts'

/** Captured when this module first loads — before any article has written a title. */
const DEFAULT_TITLE = typeof document === 'undefined' ? '' : document.title
const DEFAULT_DESCRIPTION =
  typeof document === 'undefined'
    ? ''
    : (document.querySelector('meta[name="description"]')?.getAttribute('content') ?? '')

function descriptionTag(): HTMLMetaElement {
  let tag = document.querySelector<HTMLMetaElement>('meta[name="description"]')
  if (!tag) {
    tag = document.createElement('meta')
    tag.name = 'description'
    document.head.appendChild(tag)
  }
  return tag
}

export function useDocumentMeta(title: () => string, description: () => string): void {
  let writtenTitle = ''
  let writtenDescription = ''

  watchEffect(() => {
    writtenTitle = pageTitle(title())
    document.title = writtenTitle
    writtenDescription = description()
    descriptionTag().setAttribute('content', writtenDescription)
  })

  onBeforeUnmount(() => {
    if (document.title === writtenTitle) document.title = DEFAULT_TITLE
    const tag = descriptionTag()
    if (tag.getAttribute('content') === writtenDescription) {
      tag.setAttribute('content', DEFAULT_DESCRIPTION)
    }
  })
}
