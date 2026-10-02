/**
 * The decisions behind per-page `document.title` and meta description, as pure functions
 * over a tiny target object, so `node --test` can exercise them without a DOM. The Vue
 * wrapper (`useDocumentMeta.ts`) adapts the real `document` to `MetaTarget`.
 */
import { pageTitle } from './content/text.ts'

/** Where the title and description live. The browser adapter maps these to `document`. */
export interface MetaTarget {
  title: string
  description: string
}

/** What the page shows when no article owns the title (the `index.html` values). */
export interface MetaDefaults {
  readonly title: string
  readonly description: string
}

/** What THIS page last wrote, remembered so it only ever undoes its own work. */
export interface Written {
  title: string
  description: string
}

/**
 * Write a page's title and description. An empty or missing `title` means "this page owns
 * neither": the site defaults are shown instead (an unknown article slug lands here; it
 * used to blank the description).
 */
export function applyMeta(
  target: MetaTarget,
  defaults: MetaDefaults,
  next: { title: string | null | undefined; description: string | null | undefined },
): Written {
  const owns = typeof next.title === 'string' && next.title.trim() !== ''
  const written: Written = {
    title: owns ? pageTitle(next.title as string) : defaults.title,
    description: owns && next.description ? next.description : defaults.description,
  }
  target.title = written.title
  target.description = written.description
  return written
}

/**
 * Give the defaults back when the page goes away, but ONLY for a field that still holds what
 * this page wrote. App.vue renders the router view inside <Suspense>, which sets up the NEW
 * page before it unmounts the OLD one; an unconditional "restore" would run after the next
 * article had written its own title and overwrite it with a stale one.
 */
export function releaseMeta(target: MetaTarget, defaults: MetaDefaults, written: Written): void {
  if (target.title === written.title) target.title = defaults.title
  if (target.description === written.description) target.description = defaults.description
}
