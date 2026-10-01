/**
 * Markdown -> typed legal content. The pure half of `sync_legal.ts` (no file access here, so
 * the drift test and the unit tests can drive it with synthetic input).
 *
 * THE RULE THIS FILE EXISTS TO ENFORCE: it never silently drops or reinterprets anything.
 * It understands exactly the subset of markdown the platform drafts use and THROWS, naming
 * the line, on every other construct. A policy page that quietly lost a sentence because
 * the parser did not know what a `*` bullet was would be worse than a build that stops.
 *
 * Supported:
 *   - one `# Title`, then `## ` and `### ` headings (`####` and deeper throw)
 *   - a leading `>` blockquote (the document's DRAFT banner), at most one
 *   - paragraphs; `- ` lists with `  - ` nesting and indented continuation lines
 *   - GFM pipe tables with a `|---|` delimiter row
 *   - `---` horizontal rules, ONLY as decoration between the header block / summary and
 *     the body (a rule anywhere else would mean something this page cannot show)
 *   - inline: `**bold**`, `` `code` ``, `[label](target)` with a safe target, and
 *     `{{PLACEHOLDER}}` (bare, or alone in a code span)
 *
 * Document structure is recognised from heading TEXT:
 *   `Summary in plain language`   the summary box
 *   `Part A — Title`              a group of sections (Terms)
 *   `3. Title`                    a numbered section (h2 in the Privacy Policy, h3 in Terms)
 *   `3.1 Title`                   a numbered subsection of section 3 (Privacy, h3)
 * and `3.8 Text...` at the start of a paragraph is a numbered clause with its own anchor.
 */
import { classifyHref } from '../src/lib/legal/links.ts'
import type { Block, DocumentVersion, Inline, LegalDocument, ListItem, Part, Section } from '../src/lib/legal/types.ts'

// ---------------------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------------------

export class LegalParseError extends Error {
  constructor(source: string, line: number | null, message: string) {
    super(`${source}${line === null ? '' : `:${line}`}: ${message}`)
    this.name = 'LegalParseError'
  }
}

// ---------------------------------------------------------------------------------------
// Block tokenizer
// ---------------------------------------------------------------------------------------

type Token =
  | { t: 'h'; level: number; text: string; line: number }
  | { t: 'hr'; line: number }
  | { t: 'quote'; lines: string[]; line: number }
  | { t: 'list'; lines: { text: string; line: number }[]; line: number }
  | { t: 'table'; lines: { text: string; line: number }[]; line: number }
  | { t: 'para'; text: string; line: number }

const HEADING = /^(#{1,6})( +)(.+?) *$/
const HR = /^-{3,} *$/
const BULLET = /^- +\S/
const TABLE_ROW = /^\|/

function isBlockStart(line: string): boolean {
  return HEADING.test(line) || HR.test(line) || line.startsWith('>') || BULLET.test(line) || TABLE_ROW.test(line)
}

function tokenize(lines: string[], source: string, lineOffset = 0): Token[] {
  const fail = (i: number, msg: string): never => {
    throw new LegalParseError(source, i + 1 + lineOffset, msg)
  }
  const tokens: Token[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i] ?? ''
    if (line.trim() === '') {
      i++
      continue
    }
    if (line !== line.trimEnd() && / {2}$/.test(line)) {
      fail(i, 'trailing double space (a markdown hard line break) is not supported')
    }
    if (/^#{1,6}[^# ]/.test(line)) fail(i, `"${line}" looks like a heading with no space after the #`)
    const h = HEADING.exec(line)
    if (h) {
      const level = (h[1] ?? '').length
      if (level > 3) fail(i, `heading level ${level} is not supported (use ## or ###)`)
      tokens.push({ t: 'h', level, text: h[3] ?? '', line: i + 1 + lineOffset })
      i++
      continue
    }
    if (HR.test(line)) {
      if (line.trim() !== '---') fail(i, 'only a three-dash "---" rule is supported')
      tokens.push({ t: 'hr', line: i + 1 + lineOffset })
      i++
      continue
    }
    if (/^(\*{3,}|_{3,})\s*$/.test(line)) fail(i, 'only a three-dash "---" rule is supported')
    if (line.startsWith('```') || line.startsWith('~~~')) fail(i, 'fenced code blocks are not supported')
    if (/^ {4,}\S/.test(line) || /^ +\S/.test(line)) fail(i, 'an indented line that is not part of a list is not supported')
    if (line.startsWith('<')) fail(i, 'HTML is not supported')
    if (/^[*+] /.test(line)) fail(i, 'only "-" bullets are supported')
    if (/^\d+[.)] /.test(line)) fail(i, 'markdown ordered lists are not supported (numbered clauses are plain paragraphs)')
    if (/^\[[^\]]*\]:/.test(line)) fail(i, 'link reference definitions are not supported')

    if (line.startsWith('>')) {
      const start = i
      const body: string[] = []
      while (i < lines.length && (lines[i] ?? '').startsWith('>')) {
        const raw = lines[i] ?? ''
        body.push(raw.startsWith('> ') ? raw.slice(2) : raw.slice(1))
        i++
      }
      const next = lines[i]
      if (next !== undefined && next.trim() !== '' && !isBlockStart(next)) {
        fail(i, 'text directly after a blockquote (lazy continuation) is not supported; add a blank line')
      }
      tokens.push({ t: 'quote', lines: body, line: start + 1 + lineOffset })
      continue
    }

    if (BULLET.test(line)) {
      const start = i
      const items: { text: string; line: number }[] = []
      while (i < lines.length) {
        const cur = lines[i] ?? ''
        if (cur.trim() === '') {
          const after = lines[i + 1]
          if (after !== undefined && (BULLET.test(after) || /^ +\S/.test(after))) {
            fail(i + 1, 'a blank line inside a list (a "loose" list) is not supported')
          }
          break
        }
        if (BULLET.test(cur) || /^ +\S/.test(cur)) {
          items.push({ text: cur, line: i + 1 + lineOffset })
          i++
          continue
        }
        if (isBlockStart(cur)) break
        fail(i, 'text directly after a list item (lazy continuation) is not supported; indent it or add a blank line')
      }
      tokens.push({ t: 'list', lines: items, line: start + 1 + lineOffset })
      continue
    }

    if (TABLE_ROW.test(line)) {
      const start = i
      const rows: { text: string; line: number }[] = []
      while (i < lines.length && TABLE_ROW.test(lines[i] ?? '')) {
        rows.push({ text: lines[i] ?? '', line: i + 1 + lineOffset })
        i++
      }
      tokens.push({ t: 'table', lines: rows, line: start + 1 + lineOffset })
      continue
    }

    const start = i
    const parts: string[] = []
    while (i < lines.length) {
      const cur = lines[i] ?? ''
      if (cur.trim() === '' || isBlockStart(cur)) break
      if (/ {2}$/.test(cur)) fail(i, 'trailing double space (a markdown hard line break) is not supported')
      if (/^ +\S/.test(cur)) fail(i, 'an indented line inside a paragraph is not supported')
      parts.push(cur.trim())
      i++
    }
    tokens.push({ t: 'para', text: parts.join(' '), line: start + 1 + lineOffset })
  }
  return tokens
}

// ---------------------------------------------------------------------------------------
// Inline parser
// ---------------------------------------------------------------------------------------

const PLACEHOLDER_ONLY = /^\{\{[A-Z][A-Z0-9_]*\}\}$/
const PLACEHOLDER_AT = /^\{\{([A-Z][A-Z0-9_]*)\}\}/

/** Phrases like "section 3.8" / "Sections 9.1, 9.5 and 10", for cross-reference linking. */
const REF_RUN = /\b([Ss]ections?) (\d+(?:\.\d+)?(?:(?:, | and |, and | or )\d+(?:\.\d+)?)*)/g

export function parseInline(src: string, source: string, line: number): Inline[] {
  const fail = (msg: string): never => {
    throw new LegalParseError(source, line, `${msg} (in: "${src.length > 80 ? `${src.slice(0, 80)}…` : src}")`)
  }
  const out: Inline[] = []
  let buf = ''
  const flush = (): void => {
    if (buf !== '') out.push({ kind: 'text', text: buf })
    buf = ''
  }
  let i = 0
  while (i < src.length) {
    const ch = src[i] ?? ''
    if (src.startsWith('**', i)) {
      const j = src.indexOf('**', i + 2)
      if (j === -1) fail('unclosed "**"')
      const inner = src.slice(i + 2, j)
      if (inner === '' || /^\s|\s$/.test(inner)) fail('"**" with empty or space-padded content is not valid bold')
      flush()
      out.push({ kind: 'strong', children: parseInline(inner, source, line) })
      i = j + 2
    } else if (ch === '`') {
      if (src[i + 1] === '`') fail('double-backtick code spans are not supported')
      const j = src.indexOf('`', i + 1)
      if (j === -1) fail('unclosed backtick')
      const code = src.slice(i + 1, j)
      if (code === '') fail('empty code span')
      flush()
      if (PLACEHOLDER_ONLY.test(code)) {
        out.push({ kind: 'placeholder', name: code.slice(2, -2) })
      } else if (code.includes('{{') || code.includes('}}')) {
        fail(`code span "${code}" contains a malformed placeholder (expected exactly {{UPPER_SNAKE_NAME}})`)
      } else {
        out.push({ kind: 'code', text: code })
      }
      i = j + 1
    } else if (ch === '!' && src[i + 1] === '[') {
      fail('images are not supported')
    } else if (ch === '[') {
      const m = /^\[([^[\]]+)\]\(([^)\s]+)\)/.exec(src.slice(i))
      if (!m) fail('"[" that is not a complete [label](target) link')
      const label = m?.[1] ?? ''
      const href = m?.[2] ?? ''
      if (href.includes('{{') || href.includes('}}')) {
        fail(`a placeholder inside the link target "${href}" would hide a missing fact behind a working-looking link`)
      }
      if (classifyHref(href) === null) fail(`link target "${href}" is not allowed (same-site path, https:// or mailto: only)`)
      if (href.includes('(')) fail('parentheses inside a link target are not supported (the link would end at the first ")")')
      // The label is parsed like any other inline run, so a placeholder in it is a real
      // placeholder node: counted, and shown as a chip. Anything else is refused.
      const children = parseInline(label, source, line)
      if (children.some((c) => c.kind !== 'text' && c.kind !== 'placeholder')) {
        fail('links whose label contains markup are not supported')
      }
      flush()
      out.push({ kind: 'link', href, children })
      i += (m?.[0] ?? '').length
    } else if (ch === '{' && src[i + 1] === '{') {
      const m = PLACEHOLDER_AT.exec(src.slice(i))
      if (!m) fail('"{{" that is not a well-formed {{UPPER_SNAKE_NAME}} placeholder')
      flush()
      out.push({ kind: 'placeholder', name: m?.[1] ?? '' })
      i += (m?.[0] ?? '').length
    } else if (ch === '}' && src[i + 1] === '}') {
      fail('stray "}}"')
    } else if (ch === '*') {
      fail('single "*" (italic or bullet) is not supported')
    } else if (ch === '_' && (i === 0 || /[\s(]/.test(src[i - 1] ?? '')) && /\S/.test(src[i + 1] ?? '')) {
      fail('"_italic_" is not supported')
    } else if (ch === '~' && src[i + 1] === '~') {
      fail('strikethrough is not supported')
    } else if (ch === '<') {
      fail('"<" (HTML or an autolink) is not supported')
    } else if (ch === '\\') {
      fail('backslash escapes are not supported')
    } else if (ch === ']') {
      fail('stray "]"')
    } else if (ch === '&' && /^&(#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);/.test(src.slice(i))) {
      fail('HTML entities are not supported; write the character itself')
    } else if (ch === ':' && src.startsWith('://', i)) {
      fail('a bare URL in running text is not supported; use [label](https://...) or put it in a `code` span')
    } else {
      buf += ch
      i++
    }
  }
  flush()
  return out
}

/** Turn "section 3.8" in text nodes into `ref` nodes, throwing on a number with no target. */
function linkRefs(nodes: readonly Inline[], anchors: ReadonlySet<string>, source: string, line: number): Inline[] {
  const out: Inline[] = []
  for (const node of nodes) {
    if (node.kind === 'strong') {
      out.push({ kind: 'strong', children: linkRefs(node.children, anchors, source, line) })
      continue
    }
    if (node.kind !== 'text') {
      out.push(node)
      continue
    }
    let last = 0
    const text = node.text
    for (const m of text.matchAll(REF_RUN)) {
      const word = m[1] ?? ''
      const list = m[2] ?? ''
      const listStart = (m.index ?? 0) + word.length + 1
      if (listStart > last) out.push({ kind: 'text', text: text.slice(last, listStart) })
      let pos = 0
      for (const num of list.matchAll(/\d+(?:\.\d+)?/g)) {
        const at = num.index ?? 0
        if (at > pos) out.push({ kind: 'text', text: list.slice(pos, at) })
        const anchor = `s-${num[0].replace('.', '-')}`
        if (!anchors.has(anchor)) {
          throw new LegalParseError(source, line, `"${word} ${num[0]}" refers to a section or clause that does not exist`)
        }
        out.push({ kind: 'ref', anchor, text: num[0] })
        pos = at + num[0].length
      }
      last = listStart + pos
    }
    if (last < text.length) out.push({ kind: 'text', text: text.slice(last) })
  }
  return out
}

// ---------------------------------------------------------------------------------------
// Structure
// ---------------------------------------------------------------------------------------

interface RawItem {
  raw: string
  line: number
  children: RawItem[]
}
type RawBlock =
  | { kind: 'paragraph'; raw: string; line: number; clause?: string; anchor?: string }
  | { kind: 'list'; items: RawItem[]; line: number }
  | { kind: 'table'; header: string[]; rows: string[][]; line: number }

interface RawSection {
  id: string
  number: string | null
  title: string
  level: 2 | 3
  line: number
  blocks: RawBlock[]
  children: RawSection[]
}
interface RawPart {
  label: string | null
  title: string | null
  sections: RawSection[]
}

function parseList(tok: Extract<Token, { t: 'list' }>, source: string): RawItem[] {
  const root: RawItem[] = []
  // stack of [indent, item]; the sibling list a new marker at `indent` belongs to
  const stack: { indent: number; item: RawItem }[] = []
  for (const { text, line } of tok.lines) {
    const m = /^( *)- +(\S.*)$/.exec(text)
    if (m) {
      const indent = (m[1] ?? '').length
      if (indent % 2 !== 0) throw new LegalParseError(source, line, 'list indentation must be a multiple of two spaces')
      while (stack.length > 0 && (stack[stack.length - 1]?.indent ?? 0) >= indent) stack.pop()
      const parent = stack[stack.length - 1]
      if (parent && indent !== parent.indent + 2) {
        throw new LegalParseError(source, line, 'a nested list item must be indented exactly two spaces deeper than its parent')
      }
      if (!parent && indent !== 0) throw new LegalParseError(source, line, 'a list cannot start indented')
      const item: RawItem = { raw: (m[2] ?? '').trimEnd(), line, children: [] }
      ;(parent ? parent.item.children : root).push(item)
      stack.push({ indent, item })
      continue
    }
    // continuation line
    const cur = stack[stack.length - 1]
    const indent = (/^ */.exec(text)?.[0] ?? '').length
    if (!cur || indent < cur.indent + 2) {
      throw new LegalParseError(source, line, 'a list continuation line must be indented under its item')
    }
    if (/ {2}$/.test(text)) throw new LegalParseError(source, line, 'trailing double space is not supported')
    cur.item.raw += ` ${text.trim()}`
  }
  return root
}

function splitRow(text: string, source: string, line: number): string[] {
  const t = text.trim()
  if (!t.startsWith('|') || !t.endsWith('|')) {
    throw new LegalParseError(source, line, 'a table row must start and end with "|"')
  }
  const inner = t.slice(1, -1)
  if (inner.includes('\\|')) throw new LegalParseError(source, line, 'escaped pipes in table cells are not supported')
  // A pipe inside a code span would split the cell wrongly; none of the drafts needs one,
  // so refuse rather than guess.
  for (const seg of inner.split('`').filter((_, k) => k % 2 === 1)) {
    if (seg.includes('|')) throw new LegalParseError(source, line, 'a "|" inside a code span in a table cell is not supported')
  }
  return inner.split('|').map((c) => c.trim())
}

function parseTable(tok: Extract<Token, { t: 'table' }>, source: string): RawBlock {
  const [head, delim, ...body] = tok.lines
  if (!head || !delim) throw new LegalParseError(source, tok.line, 'a table needs a header row and a |---| delimiter row')
  const header = splitRow(head.text, source, head.line)
  const delimCells = splitRow(delim.text, source, delim.line)
  if (delimCells.length !== header.length || !delimCells.every((c) => /^:?-{3,}:?$/.test(c))) {
    throw new LegalParseError(source, delim.line, 'the second table row must be a |---|---| delimiter row with one cell per column')
  }
  if (delimCells.some((c) => c.includes(':'))) {
    throw new LegalParseError(source, delim.line, 'column alignment (:---:) is not supported')
  }
  const rows = body.map((r) => {
    const cells = splitRow(r.text, source, r.line)
    if (cells.length !== header.length) {
      throw new LegalParseError(source, r.line, `table row has ${cells.length} cells, the header has ${header.length}`)
    }
    return cells
  })
  if (rows.length === 0) throw new LegalParseError(source, tok.line, 'a table needs at least one body row')
  return { kind: 'table', header, rows, line: tok.line }
}

const PART_HEADING = /^(Part [A-Z]) — (.+)$/
const SECTION_HEADING = /^(\d+)\. (.+)$/
const SUBSECTION_HEADING = /^(\d+)\.(\d+) (.+)$/
const SUMMARY_HEADING = /^Summary in plain language$/
const CLAUSE = /^(\d+)\.(\d+) (\S.*)$/s

function plainHeading(text: string, source: string, line: number): void {
  if (/[`*[\]{}<>_]/.test(text)) {
    throw new LegalParseError(source, line, `heading "${text}" contains markup or a placeholder; headings must be plain text`)
  }
}

function validDate(iso: string): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!m) return false
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const dt = new Date(Date.UTC(y, mo - 1, d))
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d
}

/** "Version 0.3 (draft, 2026-10-01)." -> structured, or null. Never guesses. */
export function parseVersionLine(text: string): DocumentVersion | null {
  const m = /^Version (\d+(?:\.\d+)*) \(([A-Za-z][A-Za-z -]*), (\d{4}-\d{2}-\d{2})\)/.exec(text)
  if (!m) return null
  const date = m[3] ?? ''
  if (!validDate(date)) return null
  return { number: m[1] ?? '', status: (m[2] ?? '').toLowerCase(), date }
}

export function parseLegalMarkdown(markdown: string, source: string): LegalDocument {
  if (markdown.includes('\t')) throw new LegalParseError(source, null, 'tab characters are not supported')
  if (markdown.includes('\0')) throw new LegalParseError(source, null, 'NUL byte in source')
  const lines = markdown.replace(/\r\n/g, '\n').replace(/\n+$/, '').split('\n')
  const tokens = tokenize(lines, source)

  // ---- header block ------------------------------------------------------------------
  const first = tokens[0]
  if (!first || first.t !== 'h' || first.level !== 1) {
    throw new LegalParseError(source, first && 'line' in first ? first.line : 1, 'the document must start with a single "# Title"')
  }
  plainHeading(first.text, source, first.line)
  const title = first.text

  let k = 1
  let bannerTok: Extract<Token, { t: 'quote' }> | null = null
  let factsTok: Extract<Token, { t: 'list' }> | null = null
  for (; k < tokens.length; k++) {
    const tok = tokens[k]
    if (!tok || tok.t === 'h') break
    if (tok.t === 'quote' && !bannerTok && !factsTok) bannerTok = tok
    else if (tok.t === 'list' && !factsTok) factsTok = tok
    else if (tok.t === 'hr') continue
    else throw new LegalParseError(source, tok.line, `unexpected ${tok.t} before the first "##" heading`)
  }

  // ---- sections ----------------------------------------------------------------------
  const anchors = new Set<string>()
  const addAnchor = (id: string, line: number): void => {
    if (anchors.has(id)) throw new LegalParseError(source, line, `duplicate anchor "${id}" (a number is used twice)`)
    anchors.add(id)
  }

  let summary: RawSection | null = null
  const rawParts: RawPart[] = []
  let part: RawPart | null = null
  let section: RawSection | null = null // the currently open numbered section
  let subsection: RawSection | null = null // the currently open numbered subsection
  let target: RawSection | null = null // where blocks go right now
  let sawFlatSection = false
  let sawPart = false
  // A `---` is decoration only when it sits at the very end of a section (the rule that
  // closes the summary, say). `pendingRule` remembers one so that any block arriving after
  // it, inside the same section, is an error rather than a silently swallowed divider.
  let pendingRule: number | null = null

  const pushBlock = (b: RawBlock, line: number): void => {
    if (!target) throw new LegalParseError(source, line, 'content before the first heading')
    if (pendingRule !== null) {
      throw new LegalParseError(source, pendingRule, 'a "---" rule in the middle of a section is not supported')
    }
    target.blocks.push(b)
  }

  for (; k < tokens.length; k++) {
    const tok = tokens[k]
    if (!tok) break
    if (tok.t === 'h') {
      pendingRule = null
      if (tok.level === 1) throw new LegalParseError(source, tok.line, 'only one "#" title is allowed')
      plainHeading(tok.text, source, tok.line)
      const text = tok.text
      const pm = PART_HEADING.exec(text)
      const sm = SECTION_HEADING.exec(text)
      const ssm = SUBSECTION_HEADING.exec(text)
      if (SUMMARY_HEADING.test(text)) {
        if (tok.level !== 2 || summary) throw new LegalParseError(source, tok.line, 'the summary must be a single "##" section')
        if (sawFlatSection || sawPart) throw new LegalParseError(source, tok.line, 'the summary must come before the numbered sections')
        addAnchor('summary', tok.line)
        summary = { id: 'summary', number: null, title: text, level: 2, line: tok.line, blocks: [], children: [] }
        target = summary
        section = null
        subsection = null
      } else if (pm) {
        if (tok.level !== 2) throw new LegalParseError(source, tok.line, '"Part X —" must be a "##" heading')
        if (sawFlatSection) throw new LegalParseError(source, tok.line, 'a document cannot mix numbered "##" sections with Parts')
        sawPart = true
        part = { label: pm[1] ?? null, title: pm[2] ?? null, sections: [] }
        rawParts.push(part)
        section = null
        subsection = null
        target = null
      } else if (sm) {
        const num = sm[1] ?? ''
        const id = `s-${num}`
        if (tok.level === 2) {
          if (sawPart) throw new LegalParseError(source, tok.line, 'a numbered "##" section after a Part is ambiguous; use "###" inside Parts')
          if (!part) {
            part = { label: null, title: null, sections: [] }
            rawParts.push(part)
          }
          sawFlatSection = true
        } else if (!part || !sawPart) {
          throw new LegalParseError(source, tok.line, 'a numbered "###" section must sit inside a "## Part X —" group')
        }
        addAnchor(id, tok.line)
        section = { id, number: num, title: sm[2] ?? '', level: tok.level as 2 | 3, line: tok.line, blocks: [], children: [] }
        part.sections.push(section)
        subsection = null
        target = section
      } else if (ssm) {
        if (tok.level !== 3 || !section || section.level !== 2) {
          throw new LegalParseError(source, tok.line, `subsection "${text}" must be a "###" heading under a "## ${ssm[1]}." section`)
        }
        if (ssm[1] !== section.number) {
          throw new LegalParseError(source, tok.line, `subsection "${ssm[1]}.${ssm[2]}" is under section ${section.number}`)
        }
        const num = `${ssm[1]}.${ssm[2]}`
        const id = `s-${ssm[1]}-${ssm[2]}`
        addAnchor(id, tok.line)
        subsection = { id, number: num, title: ssm[3] ?? '', level: 3, line: tok.line, blocks: [], children: [] }
        section.children.push(subsection)
        target = subsection
      } else {
        throw new LegalParseError(
          source,
          tok.line,
          `heading "${text}" is not one of: "Summary in plain language", "Part X — Title", "N. Title", "N.M Title"`,
        )
      }
      continue
    }
    if (tok.t === 'hr') {
      pendingRule = tok.line
      continue
    }
    if (tok.t === 'quote') throw new LegalParseError(source, tok.line, 'a blockquote is only supported as the leading draft banner')
    if (tok.t === 'list') {
      pushBlock({ kind: 'list', items: parseList(tok, source), line: tok.line }, tok.line)
      continue
    }
    if (tok.t === 'table') {
      pushBlock(parseTable(tok, source), tok.line)
      continue
    }
    // paragraph: possibly a numbered clause
    const cm = CLAUSE.exec(tok.text)
    if (cm) {
      if (!section || subsection || target !== section) {
        throw new LegalParseError(source, tok.line, `numbered clause "${cm[1]}.${cm[2]}" is not directly inside a numbered section`)
      }
      if (cm[1] !== section.number) {
        throw new LegalParseError(source, tok.line, `clause "${cm[1]}.${cm[2]}" is inside section ${section.number}`)
      }
      const id = `s-${cm[1]}-${cm[2]}`
      addAnchor(id, tok.line)
      pushBlock({ kind: 'paragraph', raw: cm[3] ?? '', line: tok.line, clause: `${cm[1]}.${cm[2]}`, anchor: id }, tok.line)
    } else {
      pushBlock({ kind: 'paragraph', raw: tok.text, line: tok.line }, tok.line)
    }
  }
  if (rawParts.length === 0 && !summary) {
    throw new LegalParseError(source, null, 'the document has no sections')
  }
  for (const p of rawParts) {
    if (p.sections.length === 0) throw new LegalParseError(source, null, `${p.label ?? 'a part'} has no sections`)
  }

  // ---- inline pass (needs the full anchor set for cross-references) ------------------
  const inl = (raw: string, line: number): Inline[] => linkRefs(parseInline(raw, source, line), anchors, source, line)
  const convItems = (items: RawItem[]): ListItem[] =>
    items.map((it) => ({ inline: inl(it.raw, it.line), children: convItems(it.children) }))
  const convBlock = (b: RawBlock): Block => {
    if (b.kind === 'paragraph') {
      const base = { kind: 'paragraph' as const, inline: inl(b.raw, b.line) }
      return b.clause && b.anchor ? { ...base, clause: b.clause, anchor: b.anchor } : base
    }
    if (b.kind === 'list') return { kind: 'list', items: convItems(b.items) }
    return {
      kind: 'table',
      header: b.header.map((c) => inl(c, b.line)),
      rows: b.rows.map((r) => r.map((c) => inl(c, b.line))),
    }
  }
  const convSection = (s: RawSection): Section => ({
    id: s.id,
    number: s.number,
    title: s.title,
    level: s.level,
    blocks: s.blocks.map(convBlock),
    children: s.children.map(convSection),
  })

  // ---- banner, version, facts ----------------------------------------------------------
  let banner: LegalDocument['banner'] = null
  let version: DocumentVersion | null = null
  if (bannerTok) {
    const inner = tokenize(bannerTok.lines, source, bannerTok.line - 1)
    const paras = inner.filter((t): t is Extract<Token, { t: 'para' }> => t.t === 'para')
    if (paras.length !== inner.length || paras.length === 0) {
      throw new LegalParseError(source, bannerTok.line, 'the draft banner may contain paragraphs only')
    }
    const [head, ...rest] = paras
    if (!head) throw new LegalParseError(source, bannerTok.line, 'empty draft banner')
    banner = {
      headline: parseInline(head.text, source, head.line),
      notes: rest.map((p): Block => ({ kind: 'paragraph', inline: parseInline(p.text, source, p.line) })),
    }
    for (const p of rest) {
      version = parseVersionLine(p.text)
      if (version) break
    }
  }
  const facts = factsTok ? convItems(parseList(factsTok, source)) : []

  const parts: Part[] = rawParts.map((p) => ({
    label: p.label,
    title: p.title,
    sections: p.sections.map(convSection),
  }))

  const doc: LegalDocument = {
    source,
    title,
    banner,
    version,
    facts,
    summary: summary ? convSection(summary) : null,
    parts,
  }
  assertNoStrayBraces(doc)
  return doc
}

/**
 * Generator-level backstop for the draft rule. A `{{` or `}}` anywhere outside a
 * placeholder NODE (and outside the document's own banner) is a missing fact the page
 * would neither count nor highlight, which could let a draft look final. Every path that
 * should produce a placeholder node already does; this fails the build if one ever
 * leaks through some other field (a link target, a heading, a future node kind).
 */
export function assertNoStrayBraces(doc: LegalDocument): void {
  const walk = (value: unknown, path: string): void => {
    if (typeof value === 'string') {
      if (value.includes('{{') || value.includes('}}')) {
        throw new LegalParseError(doc.source, null, `stray "{{" or "}}" in generated content at ${path}: "${value.slice(0, 80)}"`)
      }
    } else if (Array.isArray(value)) {
      value.forEach((v, i) => walk(v, `${path}[${i}]`))
    } else if (value !== null && typeof value === 'object') {
      for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
        if (k === 'banner' && path === '$') continue // the banner may mention the convention
        walk(v, `${path}.${k}`)
      }
    }
  }
  walk(doc, '$')
}

// ---------------------------------------------------------------------------------------
// Serialiser: deterministic TypeScript source for the generated file
// ---------------------------------------------------------------------------------------

/**
 * JSON, laid out for diffs: an object whose values are all primitives (every text, code,
 * placeholder and ref node) is one line however long its text is, and any other value that
 * fits in `width` columns stays on one line too. Everything else is expanded.
 */
function stringify(value: unknown, indent: string, width = 100): string {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.every(([, v]) => v === null || typeof v !== 'object')) {
      return `{ ${entries.map(([k, v]) => `${JSON.stringify(k)}: ${JSON.stringify(v)}`).join(', ')} }`
    }
  }
  const flat = flatten(value)
  if (flat.length + indent.length <= width) return flat
  const next = `${indent}  `
  if (Array.isArray(value)) {
    return `[\n${value.map((v) => `${next}${stringify(v, next, width)}`).join(',\n')}\n${indent}]`
  }
  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    return `{\n${entries.map(([k, v]) => `${next}${JSON.stringify(k)}: ${stringify(v, next, width)}`).join(',\n')}\n${indent}}`
  }
  return flat
}

/** The one-line form of a value, spaced like `stringify`'s leaf objects. */
function flatten(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(flatten).join(', ')}]`
  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    return `{ ${entries.map(([k, v]) => `${JSON.stringify(k)}: ${flatten(v)}`).join(', ')} }`
  }
  return JSON.stringify(value)
}

export function renderGeneratedModule(doc: LegalDocument, exportName: string, regenerateHint: string): string {
  return [
    '/**',
    ' * GENERATED FILE. DO NOT EDIT BY HAND.',
    ` * Source of truth: ${doc.source}`,
    ` * Regenerate:      ${regenerateHint}`,
    ' *',
    ' * `tests/legal.test.ts` regenerates this in memory and fails if it differs from the',
    ' * committed text, so the page can never drift from the markdown drafts.',
    ' */',
    "import type { LegalDocument } from './types.ts'",
    '',
    `export const ${exportName}: LegalDocument = ${stringify(doc, '')}`,
    '',
  ].join('\n')
}
