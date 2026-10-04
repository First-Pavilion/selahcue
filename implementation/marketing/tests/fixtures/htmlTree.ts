/**
 * A very small HTML tree for reading what Vue's server renderer produced.
 *
 * It is NOT a general HTML parser. It reads well-formed, double-quoted output (which is all
 * `renderToString` writes), keeps the void elements void, drops comments, and gives a test the
 * three things it needs: the tags with their attributes, the nesting, and the text a visitor
 * (or a screen reader) would get. Used by `corePages.test.ts`.
 */

export interface HtmlNode {
  /** Lower-case tag name; the root is `#root`, text is `#text`. */
  tag: string
  attrs: Record<string, string>
  children: HtmlNode[]
  /** Only on `#text`. */
  text?: string
  /** Offset of the opening tag in the source: lets a test assert document order. */
  at: number
}

const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'])

export function parseHtml(source: string): HtmlNode {
  const root: HtmlNode = { tag: '#root', attrs: {}, children: [], at: 0 }
  const stack: HtmlNode[] = [root]
  const token = /<!--[\s\S]*?-->|<\/([a-zA-Z][\w-]*)\s*>|<([a-zA-Z][\w-]*)((?:\s+[^\s=>/]+(?:="[^"]*")?)*)\s*(\/?)>|([^<]+)/g
  for (const m of source.matchAll(token)) {
    const top = stack[stack.length - 1] as HtmlNode
    if (m[0].startsWith('<!--')) continue
    if (m[1]) {
      const name = m[1].toLowerCase()
      // Close up to the nearest matching open tag; a stray close tag is ignored.
      const at = stack.map((n) => n.tag).lastIndexOf(name)
      if (at > 0) stack.length = at
      continue
    }
    if (m[2]) {
      const attrs: Record<string, string> = {}
      for (const a of (m[3] ?? '').matchAll(/([^\s=>/]+)(?:="([^"]*)")?/g)) attrs[a[1] as string] = decode(a[2] ?? '')
      const node: HtmlNode = { tag: m[2].toLowerCase(), attrs, children: [], at: m.index ?? 0 }
      top.children.push(node)
      if (!VOID.has(node.tag) && !m[4]) stack.push(node)
      continue
    }
    if (m[5] !== undefined) top.children.push({ tag: '#text', attrs: {}, children: [], text: decode(m[5]), at: m.index ?? 0 })
  }
  return root
}

function decode(s: string): string {
  return s
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&')
}

export function walk(node: HtmlNode, visit: (n: HtmlNode) => void): void {
  visit(node)
  for (const c of node.children) walk(c, visit)
}

export function all(node: HtmlNode, test: (n: HtmlNode) => boolean): HtmlNode[] {
  const out: HtmlNode[] = []
  walk(node, (n) => {
    if (n !== node && test(n)) out.push(n)
  })
  return out
}

export const byTag = (node: HtmlNode, ...tags: string[]): HtmlNode[] => all(node, (n) => tags.includes(n.tag))

export const hasClass = (n: HtmlNode, cls: string): boolean => (n.attrs['class'] ?? '').split(/\s+/).includes(cls)

export const byClass = (node: HtmlNode, cls: string): HtmlNode[] => all(node, (n) => hasClass(n, cls))

/** The text a reader gets, with whitespace collapsed. Elements hidden from assistive technology are skipped when asked. */
export function textOf(node: HtmlNode, options: { skipAriaHidden?: boolean } = {}): string {
  const parts: string[] = []
  const visit = (n: HtmlNode): void => {
    if (options.skipAriaHidden && n.attrs['aria-hidden'] === 'true') return
    if (n.tag === '#text') parts.push(n.text ?? '')
    for (const c of n.children) visit(c)
  }
  visit(node)
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}

/** Heading levels in document order. */
export function headingLevels(node: HtmlNode): number[] {
  return byTag(node, 'h1', 'h2', 'h3', 'h4', 'h5', 'h6').map((n) => Number(n.tag.slice(1)))
}

/**
 * Every way a heading outline breaks: no h1, more than one h1, a first heading that is not the
 * h1, or a heading more than one level deeper than the one before it (h1 then h3). Going back up
 * by any amount is fine. Empty when the outline is sound.
 */
export function outlineProblems(levels: readonly number[]): string[] {
  const out: string[] = []
  const h1s = levels.filter((l) => l === 1).length
  if (h1s !== 1) out.push(`expected exactly one h1, found ${h1s}`)
  if (levels.length > 0 && levels[0] !== 1) out.push(`the first heading is an h${levels[0]}, not the h1`)
  for (let i = 1; i < levels.length; i++) {
    const prev = levels[i - 1] as number
    const cur = levels[i] as number
    if (cur > prev + 1) out.push(`heading ${i + 1} is an h${cur} straight after an h${prev}: the outline skips a level`)
  }
  return out
}
