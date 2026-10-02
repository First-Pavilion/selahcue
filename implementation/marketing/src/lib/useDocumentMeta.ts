/**
 * Per-page `document.title` and meta description for the article detail pages. The rules
 * live in `documentMeta.ts` (pure, tested in node); this is the thin Vue + DOM adapter.
 *
 * The site had no title management at all (every route showed the `index.html` title), so
 * this is new, and deliberately small: set on setup, follow the reactive getters, and give
 * the defaults back on unmount (see `releaseMeta` for why that is conditional).
 */
import { onBeforeUnmount, watchEffect } from 'vue'
import { SITE_DEFAULT_DESCRIPTION, SITE_DEFAULT_TITLE } from './content/text.ts'
import { applyMeta, releaseMeta, type MetaDefaults, type MetaTarget, type Written } from './documentMeta.ts'

function descriptionTag(): HTMLMetaElement {
  let tag = document.querySelector<HTMLMetaElement>('meta[name="description"]')
  if (!tag) {
    tag = document.createElement('meta')
    tag.name = 'description'
    document.head.appendChild(tag)
  }
  return tag
}

/** The real document, as a `MetaTarget`. */
const browserTarget: MetaTarget = {
  get title() {
    return document.title
  },
  set title(value: string) {
    document.title = value
  },
  get description() {
    return descriptionTag().getAttribute('content') ?? ''
  },
  set description(value: string) {
    descriptionTag().setAttribute('content', value)
  },
}

/**
 * The site defaults are constants (`SITE_DEFAULT_*`), never read back from the document: by the
 * time this lazy module loads, another page may already have set its own title, and that would
 * be remembered as "the default".
 */
const DEFAULTS: MetaDefaults = { title: SITE_DEFAULT_TITLE, description: SITE_DEFAULT_DESCRIPTION }

/**
 * `title` empty means "not an article": the site defaults are shown (an unknown slug).
 */
export function useDocumentMeta(title: () => string, description: () => string): void {
  let written: Written = { title: '', description: '' }

  watchEffect(() => {
    written = applyMeta(browserTarget, DEFAULTS, { title: title(), description: description() })
  })

  onBeforeUnmount(() => releaseMeta(browserTarget, DEFAULTS, written))
}
