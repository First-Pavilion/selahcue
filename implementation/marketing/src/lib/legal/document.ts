/**
 * Pure helpers over a `LegalDocument`: everything the legal pages DECIDE lives here, so
 * the decisions can be tested without a browser.
 *
 * The draft treatment is derived, never configured. There is no `isDraft` flag anywhere:
 * the page is a draft exactly while the document text still contains a `{{PLACEHOLDER}}`.
 * Fill the last one in the markdown, run `npm run sync:legal`, and the banner, the
 * highlighting and the `noindex` all go away with no code change.
 */
import type { Block, DocumentVersion, Inline, LegalDocument, ListItem, Section } from './types.ts'

/**
 * Said on the page while the document is a draft. The document's own banner headline is
 * shown with it; this is the plain-English half a visitor needs.
 */
export const DRAFT_NOTICE = 'Draft, pending legal review. This page is not our final policy.'

function inlinePlaceholders(nodes: readonly Inline[], out: string[]): void {
  for (const n of nodes) {
    if (n.kind === 'placeholder') out.push(n.name)
    else if (n.kind === 'strong' || n.kind === 'link') inlinePlaceholders(n.children, out)
  }
}

function itemPlaceholders(items: readonly ListItem[], out: string[]): void {
  for (const it of items) {
    inlinePlaceholders(it.inline, out)
    itemPlaceholders(it.children, out)
  }
}

function blockPlaceholders(blocks: readonly Block[], out: string[]): void {
  for (const b of blocks) {
    if (b.kind === 'paragraph') inlinePlaceholders(b.inline, out)
    else if (b.kind === 'list') itemPlaceholders(b.items, out)
    else {
      for (const cell of b.header) inlinePlaceholders(cell, out)
      for (const row of b.rows) for (const cell of row) inlinePlaceholders(cell, out)
    }
  }
}

function sectionPlaceholders(s: Section, out: string[]): void {
  blockPlaceholders(s.blocks, out)
  for (const c of s.children) sectionPlaceholders(c, out)
}

/**
 * Every placeholder occurrence in the text a visitor reads, in document order.
 *
 * The draft banner is deliberately NOT scanned: it may name the `{{PLACEHOLDER}}`
 * convention in its own instructions ("every {{PLACEHOLDER}} must be filled"), which is
 * a mention, not a missing fact, and would otherwise keep the page in draft forever.
 */
export function placeholderOccurrences(doc: LegalDocument): string[] {
  const out: string[] = []
  itemPlaceholders(doc.facts, out)
  if (doc.summary) sectionPlaceholders(doc.summary, out)
  for (const p of doc.parts) for (const s of p.sections) sectionPlaceholders(s, out)
  return out
}

export function inlineToText(nodes: readonly Inline[]): string {
  return nodes
    .map((n) => {
      switch (n.kind) {
        case 'text':
        case 'code':
          return n.text
        case 'placeholder':
          return `{{${n.name}}}`
        case 'ref':
          return n.text
        case 'strong':
        case 'link':
          return inlineToText(n.children)
      }
    })
    .join('')
}

export interface LegalPageState {
  /** True while at least one placeholder remains. Drives banner, highlight and noindex. */
  readonly draft: boolean
  /** Distinct placeholder names, in order of first appearance. */
  readonly placeholders: readonly string[]
  /** Total occurrences (a name used five times counts five). */
  readonly placeholderCount: number
  /** `noindex` is sent exactly while the document is a draft. */
  readonly noindex: boolean
  /** The document's own banner headline as plain text, or null if it has none. */
  readonly bannerHeadline: string | null
}

export function legalPageState(doc: LegalDocument): LegalPageState {
  const all = placeholderOccurrences(doc)
  const draft = all.length > 0
  return {
    draft,
    placeholders: [...new Set(all)],
    placeholderCount: all.length,
    noindex: draft,
    bannerHeadline: doc.banner ? inlineToText(doc.banner.headline) : null,
  }
}

// ---------------------------------------------------------------------------------------
// Contents
// ---------------------------------------------------------------------------------------

export interface TocEntry {
  readonly id: string
  readonly label: string
}
export interface TocGroup {
  /** "Part A — The agreement", or null for a document without parts. */
  readonly heading: string | null
  readonly entries: readonly TocEntry[]
}

/** One entry per top-level section (and the summary). Subsections stay reachable by deep link. */
export function tableOfContents(doc: LegalDocument): TocGroup[] {
  const groups: TocGroup[] = []
  if (doc.summary) groups.push({ heading: null, entries: [{ id: doc.summary.id, label: doc.summary.title }] })
  for (const p of doc.parts) {
    groups.push({
      heading: p.label && p.title ? `${p.label} — ${p.title}` : null,
      entries: p.sections.map((s) => ({ id: s.id, label: s.number ? `${s.number}. ${s.title}` : s.title })),
    })
  }
  return groups
}

/** Every anchor id a visitor can deep-link to, for tests and the scroll-spy. */
export function allAnchorIds(doc: LegalDocument): string[] {
  const ids: string[] = []
  const walkBlocks = (blocks: readonly Block[]): void => {
    for (const b of blocks) if (b.kind === 'paragraph' && b.anchor) ids.push(b.anchor)
  }
  const walk = (s: Section): void => {
    ids.push(s.id)
    walkBlocks(s.blocks)
    s.children.forEach(walk)
  }
  if (doc.summary) walk(doc.summary)
  for (const p of doc.parts) p.sections.forEach(walk)
  return ids
}

// ---------------------------------------------------------------------------------------
// Dates
// ---------------------------------------------------------------------------------------

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

/** "2026-10-01" -> "1 October 2026". Locale- and timezone-independent; null if not a real date. */
export function formatIsoDate(iso: string): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!m) return null
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const probe = new Date(Date.UTC(y, mo - 1, d))
  if (probe.getUTCFullYear() !== y || probe.getUTCMonth() !== mo - 1 || probe.getUTCDate() !== d) return null
  return `${d} ${MONTHS[mo - 1]} ${y}`
}

/**
 * "Version 0.3 (draft) · Last updated 1 October 2026" from the document's own version
 * line, or null. Nothing here is invented: no version line, or a date that is not a real
 * calendar date, shows nothing at all.
 */
export function versionLabel(version: DocumentVersion | null): { text: string; iso: string } | null {
  if (!version) return null
  const date = formatIsoDate(version.date)
  if (!date) return null
  const status = version.status === 'draft' ? ' (draft)' : version.status ? ` (${version.status})` : ''
  return { text: `Version ${version.number}${status} · Last updated ${date}`, iso: version.date }
}

/** `document.title` for a legal page. */
export function legalTitle(doc: LegalDocument): string {
  return /selahcue/i.test(doc.title) ? doc.title : `${doc.title} — SelahCue`
}
