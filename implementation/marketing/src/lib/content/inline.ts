/**
 * Inline markup for article text, parsed into SAFE segments.
 *
 * Why not Markdown + `v-html`: the content is trusted today, but `v-html` is a standing
 * XSS foot-gun the day anyone pastes from somewhere else. Segments render through
 * ordinary Vue text interpolation, so a `<script>` in a string is displayed as text.
 *
 *   **bold**        -> strong
 *   `code`          -> code
 *   [[Enter]]       -> kbd
 *   [label](/path)  -> link (internal path, or https:// external)
 *
 * A link whose target is neither a same-site path nor an https URL is NOT turned into a
 * link: it falls back to its label as plain text, so `[x](javascript:alert(1))` is inert.
 */

export type Segment =
  | { readonly kind: 'text'; readonly text: string }
  | { readonly kind: 'strong'; readonly text: string }
  | { readonly kind: 'code'; readonly text: string }
  | { readonly kind: 'kbd'; readonly text: string }
  | { readonly kind: 'link'; readonly text: string; readonly href: string; readonly external: boolean }

const TOKEN = /\*\*(.+?)\*\*|`([^`]+)`|\[\[(.+?)\]\]|\[([^\]]+)\]\(([^)\s]+)\)/g

/** `/path` (but not protocol-relative `//host`) is internal; `https://…` is external. */
export function classifyHref(href: string): 'internal' | 'external' | null {
  if (href.startsWith('/') && !href.startsWith('//') && !href.includes('\\')) return 'internal'
  if (/^https:\/\/[^\s/]+/i.test(href)) return 'external'
  return null
}

export function parseInline(input: string): Segment[] {
  const out: Segment[] = []
  let last = 0
  for (const m of input.matchAll(TOKEN)) {
    const at = m.index ?? 0
    if (at > last) out.push({ kind: 'text', text: input.slice(last, at) })
    if (m[1] !== undefined) out.push({ kind: 'strong', text: m[1] })
    else if (m[2] !== undefined) out.push({ kind: 'code', text: m[2] })
    else if (m[3] !== undefined) out.push({ kind: 'kbd', text: m[3] })
    else {
      const label = m[4] ?? ''
      const href = m[5] ?? ''
      const kind = classifyHref(href)
      if (kind === null) out.push({ kind: 'text', text: label })
      else out.push({ kind: 'link', text: label, href, external: kind === 'external' })
    }
    last = at + m[0].length
  }
  if (last < input.length) out.push({ kind: 'text', text: input.slice(last) })
  return out
}

/** Plain text of an inline string, markup removed. Used for word counts and headings. */
export function inlineToText(input: string): string {
  return parseInline(input)
    .map((s) => s.text)
    .join('')
}
