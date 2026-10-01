/**
 * The typed shape of a legal document (Privacy Policy, Terms of Service).
 *
 * These documents are NOT written here. `docs/legal/*-PLATFORM-DRAFT.md` is the source of
 * truth; `scripts/sync_legal.ts` parses it into this shape and commits the result as
 * `*.generated.ts`. A test fails when the committed output and the markdown disagree, so
 * the page can never quietly show something the drafts no longer say.
 *
 * Everything below is plain data. There is no markup in it, no HTML string anywhere: the
 * view renders each node through ordinary template interpolation (no `v-html`), so a
 * `<script>` in a draft would be displayed as text rather than run.
 */

/** Inline content: what can appear inside a paragraph, list item or table cell. */
export type Inline =
  | { readonly kind: 'text'; readonly text: string }
  | { readonly kind: 'strong'; readonly children: readonly Inline[] }
  | { readonly kind: 'code'; readonly text: string }
  /**
   * A `{{NAME}}` token: a fact the owner or counsel has not supplied yet. Kept as its own
   * node (never flattened into text) so the page can both highlight it and COUNT it —
   * the draft banner and the `noindex` header are driven by that count.
   */
  | { readonly kind: 'placeholder'; readonly name: string }
  /** A markdown link. `href` is validated by `classifyHref` at render time as well. */
  | { readonly kind: 'link'; readonly href: string; readonly children: readonly Inline[] }
  /** "section 3.8" in the prose, resolved to the anchor of that clause or section. */
  | { readonly kind: 'ref'; readonly anchor: string; readonly text: string }

export interface ListItem {
  readonly inline: readonly Inline[]
  /** A nested list directly under this item. */
  readonly children: readonly ListItem[]
}

export type Block =
  /** `clause` is the "3.8" a numbered paragraph opens with; `anchor` is its stable id. */
  | { readonly kind: 'paragraph'; readonly inline: readonly Inline[]; readonly clause?: string; readonly anchor?: string }
  | { readonly kind: 'list'; readonly items: readonly ListItem[] }
  | { readonly kind: 'table'; readonly header: readonly (readonly Inline[])[]; readonly rows: readonly (readonly (readonly Inline[])[])[] }

export interface Section {
  /** Stable id used for deep links, e.g. `s-3`, `s-3-8`. The summary is `summary`. */
  readonly id: string
  /** "3" for a section, "3.8" for a subsection, null for the unnumbered summary. */
  readonly number: string | null
  readonly title: string
  /** The heading level it is rendered at (2 or 3). */
  readonly level: 2 | 3
  readonly blocks: readonly Block[]
  /** Numbered subsections (`### 3.1 ...` under `## 3. ...`). */
  readonly children: readonly Section[]
}

/** A `Part A — The agreement` group in the Terms; the Privacy Policy has one unnamed part. */
export interface Part {
  /** "Part A", or null for the single implicit part of a document without parts. */
  readonly label: string | null
  readonly title: string | null
  readonly sections: readonly Section[]
}

export interface DocumentVersion {
  /** "0.3" */
  readonly number: string
  /** "draft" */
  readonly status: string
  /** ISO calendar date, "2026-10-01". */
  readonly date: string
}

export interface LegalDocument {
  /** The repo-relative markdown file this was generated from. */
  readonly source: string
  readonly title: string
  /**
   * The document's own DRAFT notice (the leading blockquote), or null once it has been
   * removed from the markdown. Its text may legitimately MENTION the `{{PLACEHOLDER}}`
   * convention, so it is deliberately excluded when placeholders are counted.
   */
  readonly banner: {
    readonly headline: readonly Inline[]
    readonly notes: readonly Block[]
  } | null
  /** Parsed from the banner's own "Version X (draft, date)" line; null if absent or unparseable. */
  readonly version: DocumentVersion | null
  /** The key-facts list under the title ("Who we are", "Registered address", ...). */
  readonly facts: readonly ListItem[]
  readonly summary: Section | null
  readonly parts: readonly Part[]
}
