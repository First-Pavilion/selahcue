/**
 * Pure helpers shared by the three article kinds: slug rules, read-time, heading ids and
 * the document title. Kept free of Vue so `node --test` can load it.
 */
import { inlineToText } from './inline.ts'
import type { Block } from './types.ts'

/** Lowercase letters, digits and single hyphens; no leading/trailing hyphen. */
export const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

export function blockText(block: Block): string {
  switch (block.type) {
    case 'p':
    case 'h2':
    case 'h3':
      return inlineToText(block.text)
    case 'ul':
    case 'ol':
      return block.items.map(inlineToText).join(' ')
    case 'callout':
      return `${block.title} ${inlineToText(block.text)}`
    case 'code':
      return block.code
  }
}

export function wordCount(body: readonly Block[]): number {
  const text = body.map(blockText).join(' ').trim()
  return text === '' ? 0 : text.split(/\s+/).length
}

/** Whole minutes at 200 wpm, never below 1. Derived from the body, so it cannot drift. */
export function readMinutes(body: readonly Block[]): number {
  return Math.max(1, Math.ceil(wordCount(body) / 200))
}

/**
 * Every generated heading id starts with this. The views own a handful of fixed ids
 * (`docs-nav`, `docs-article`, `bp-share-title` …); an article whose h2 is "Docs nav" must
 * not be able to collide with one, and the prefix makes that impossible by construction
 * (`tests/content.test.ts` checks no fixed id uses it).
 */
export const HEADING_ID_PREFIX = 'sec-'

/** `sec-heading-text` id for an h2/h3. Collisions get `-2`, `-3` … in document order. */
export function headingIds(body: readonly Block[]): Map<Block, string> {
  const seen = new Map<string, number>()
  const ids = new Map<Block, string>()
  for (const b of body) {
    if (b.type !== 'h2' && b.type !== 'h3') continue
    const base =
      inlineToText(b.text)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '') || 'section'
    const n = (seen.get(base) ?? 0) + 1
    seen.set(base, n)
    ids.set(b, HEADING_ID_PREFIX + (n === 1 ? base : `${base}-${n}`))
  }
  return ids
}

export interface TocEntry {
  readonly id: string
  readonly text: string
}

export function tableOfContents(body: readonly Block[]): TocEntry[] {
  const ids = headingIds(body)
  const out: TocEntry[] = []
  for (const b of body) {
    if (b.type === 'h2') out.push({ id: ids.get(b) ?? '', text: inlineToText(b.text) })
  }
  return out
}

export const SITE_NAME = 'SelahCue'

/**
 * What the site shows when no article owns the title or description: the values in
 * `index.html`. They are CONSTANTS, not read from the document, because the document is the
 * wrong witness: another page may already have changed `document.title` by the time the lazy
 * article module first loads (cold-load /privacy, which sets its own title, then open an
 * article: the "default" captured would be "SelahCue Privacy Policy", and leaving the article
 * for the home page would show that). `tests/pageMeta.test.ts` checks these match `index.html`.
 */
export const SITE_DEFAULT_TITLE = 'SelahCue — Church presentation, reengineered'
export const SITE_DEFAULT_DESCRIPTION =
  'A reliable, modern church presentation software built for stability and ease of use.'

/** `Article title — SelahCue`, the shape every detail page uses for `document.title`. */
export function pageTitle(title: string): string {
  return `${title} — ${SITE_NAME}`
}

/** `1 Oct 2026` from an ISO date, locale-independent so tests and builds agree. */
export function formatDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!m) return iso
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${Number(m[3])} ${months[Number(m[2]) - 1]} ${m[1]}`
}

/**
 * Where a docs article's source lives, for the "Suggest an edit" link (handoff §9b "Edit on
 * GitHub"). Articles are typed data in one file per collection rather than Markdown files,
 * so the link goes to that file. The repository is public (`gh repo view` -> PUBLIC).
 */
export const CONTENT_SOURCE_URL =
  'https://github.com/First-Pavilion/selahcue/blob/main/implementation/marketing/src/lib/content/docs.ts'
