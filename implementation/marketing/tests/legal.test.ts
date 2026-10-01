/**
 * The legal pages' content pipeline: markdown draft -> typed content -> page decisions.
 *
 * What is pinned here, and why each one matters:
 *
 *  1. DRIFT. The generated files are regenerated in memory from `docs/legal/*.md` and must
 *     equal what is committed. Edit a draft without running `npm run sync:legal` and this
 *     fails, so the site can never show something the drafts no longer say.
 *  2. COMPLETENESS. Every word of each draft appears in the typed content, in order. The
 *     parser is not trusted to be lossless; this proves it on the real documents.
 *  3. LOUD FAILURE. Every markdown construct the parser does not support makes it throw
 *     rather than drop or mangle content.
 *  4. THE DRAFT RULE. The banner, the highlight and `noindex` are derived from whether a
 *     `{{PLACEHOLDER}}` remains, in BOTH directions, on synthetic documents.
 *  5. HEAD HANDLING. `noindex` survives a Privacy -> Terms navigation (new page set up
 *     before the old one is torn down) and is removed when the last legal page leaves.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  LegalParseError,
  assertNoStrayBraces,
  parseInline,
  parseLegalMarkdown,
  parseVersionLine,
} from '../scripts/legal_markdown.ts'
import { GENERATED_DIR, REPO_ROOT, TARGETS, generateAll } from '../scripts/sync_legal.ts'
import {
  DRAFT_NOTICE,
  allAnchorIds,
  formatIsoDate,
  inlineToText,
  legalPageState,
  legalTitle,
  placeholderOccurrences,
  tableOfContents,
  versionLabel,
} from '../src/lib/legal/document.ts'
import { LegalHead, NOINDEX_SELECTOR, type HeadHost } from '../src/lib/legal/head.ts'
import { classifyHref } from '../src/lib/legal/links.ts'
import { privacyPolicy } from '../src/lib/legal/privacy.generated.ts'
import { termsOfService } from '../src/lib/legal/terms.generated.ts'
import type { Block, Inline, LegalDocument, ListItem, Section } from '../src/lib/legal/types.ts'

const DOCS_PRESENT = TARGETS.every((t) => existsSync(`${REPO_ROOT}/${t.source}`))
const SRC = `${fileURLToPath(new URL('../src/', import.meta.url))}`

/** A minimal valid document around `body` (sections), for synthetic cases. */
function md(body: string, header = ''): string {
  return `# Test Policy\n\n${header}\n## 1. First\n\n${body}\n`
}

// ---------------------------------------------------------------------------------------
// 1. Drift
// ---------------------------------------------------------------------------------------

describe('generated files match docs/legal', { skip: !DOCS_PRESENT && 'docs/legal is not present (build context without the repo)' }, () => {
  for (const g of DOCS_PRESENT ? generateAll() : []) {
    test(`${g.target.output} equals a fresh generation from ${g.target.source}`, () => {
      assert.ok(g.outPath.startsWith(GENERATED_DIR))
      assert.ok(existsSync(g.outPath), `${g.outPath} is missing; run: npm run sync:legal`)
      const committed = readFileSync(g.outPath, 'utf8')
      assert.equal(
        committed,
        g.content,
        `${g.target.output} is stale: ${g.target.source} changed without regenerating. Run: npm run sync:legal`,
      )
    })
  }

  test('regeneration is deterministic', () => {
    const a = generateAll().map((g) => g.content)
    const b = generateAll().map((g) => g.content)
    assert.deepEqual(a, b)
  })
})

// ---------------------------------------------------------------------------------------
// 2. Completeness: no word of the draft is lost, none is invented
// ---------------------------------------------------------------------------------------

function inlineWords(nodes: readonly Inline[]): string {
  return inlineToText(nodes)
}
function itemsText(items: readonly ListItem[], out: string[]): void {
  for (const it of items) {
    out.push(inlineWords(it.inline))
    itemsText(it.children, out)
  }
}
function blocksText(blocks: readonly Block[], out: string[]): void {
  for (const b of blocks) {
    if (b.kind === 'paragraph') out.push(`${b.clause ? `${b.clause} ` : ''}${inlineWords(b.inline)}`)
    else if (b.kind === 'list') itemsText(b.items, out)
    else {
      out.push(...b.header.map(inlineWords))
      for (const row of b.rows) out.push(...row.map(inlineWords))
    }
  }
}
function sectionText(s: Section, out: string[]): void {
  if (s.level === 2 && s.number && !s.number.includes('.')) out.push(`${s.number}. ${s.title}`)
  else if (s.level === 3 && s.number && !s.number.includes('.')) out.push(`${s.number}. ${s.title}`)
  else if (s.number) out.push(`${s.number} ${s.title}`)
  else out.push(s.title)
  blocksText(s.blocks, out)
  for (const c of s.children) sectionText(c, out)
}

/** The typed document flattened to text, in reading order. */
function documentText(doc: LegalDocument): string[] {
  const out: string[] = [doc.title]
  if (doc.banner) {
    out.push(inlineWords(doc.banner.headline))
    blocksText(doc.banner.notes, out)
  }
  if (doc.version.source === 'front-matter') out.push(doc.version.line)
  itemsText(doc.facts, out)
  if (doc.summary) sectionText(doc.summary, out)
  for (const p of doc.parts) {
    if (p.label && p.title) out.push(`${p.label} — ${p.title}`)
    for (const s of p.sections) sectionText(s, out)
  }
  return out.join(' ').split(/\s+/).filter(Boolean)
}

/** The markdown with its syntax removed, as words. Independent of the parser under test. */
function markdownWords(source: string): string[] {
  return source
    .replace(/\r\n/g, '\n')
    .split('\n')
    .filter((l) => !/^-{3,}\s*$/.test(l) && !/^\|[\s:|-]+\|\s*$/.test(l))
    .map((l) =>
      l
        .replace(/^#{1,3} +/, '')
        .replace(/^>\s?/, '')
        .replace(/^ *- +/, '')
        .replace(/\*\*/g, '')
        .replace(/`/g, '')
        .replace(/\|/g, ' '),
    )
    .join(' ')
    .split(/\s+/)
    .filter(Boolean)
}

describe('the completeness check itself works on the publish-path shape (banner removed)', () => {
  test('a synthetic final document: every word survives, including the front-matter version line', () => {
    const src =
      '# Final Policy\n\nVersion 1.0 (final, 2026-11-05).\n\n- **Who:** Example Ltd\n\n---\n\n## Summary in plain language\n\n- one plain point\n\n---\n\n## 1. Scope\n\n1.1 This applies to everyone. See section 2.\n\n## 2. Data\n\n| A | B |\n|---|---|\n| x | `y` |\n'
    const doc = parseLegalMarkdown(src, 'final.md')
    assert.deepEqual(documentText(doc), markdownWords(src))
  })
})

describe('the typed content holds every word of the draft, in order', { skip: !DOCS_PRESENT && 'docs/legal is not present' }, () => {
  for (const [target, doc] of [
    [TARGETS[0], privacyPolicy],
    [TARGETS[1], termsOfService],
  ] as const) {
    test(`${target?.source}`, () => {
      const source = readFileSync(`${REPO_ROOT}/${target?.source}`, 'utf8')
      const want = markdownWords(source)
      const got = documentText(doc)
      assert.ok(want.length > 2000, 'the premise: a real document has thousands of words')
      assert.equal(got.length, want.length, `word count: markdown ${want.length}, typed content ${got.length}`)
      const at = want.findIndex((w, i) => w !== got[i])
      assert.equal(at, -1, `first divergence at word ${at}: markdown "${want[at]}" vs content "${got[at]}"`)
    })
  }
})

// ---------------------------------------------------------------------------------------
// Real-document invariants
// ---------------------------------------------------------------------------------------

describe('the real documents are internally consistent', () => {
  for (const [name, doc] of [
    ['privacy', privacyPolicy],
    ['terms', termsOfService],
  ] as const) {
    test(`${name}: anchors are unique and every cross-reference resolves`, () => {
      const ids = allAnchorIds(doc)
      assert.equal(new Set(ids).size, ids.length, 'duplicate anchor id')
      for (const id of ids) assert.match(id, /^(summary|s-\d+(-\d+)?)$/)
      const idSet = new Set(ids)
      let refs = 0
      const visit = (nodes: readonly Inline[]): void => {
        for (const n of nodes) {
          if (n.kind === 'ref') {
            refs++
            assert.ok(idSet.has(n.anchor), `ref to missing anchor ${n.anchor}`)
          } else if (n.kind === 'strong' || n.kind === 'link') visit(n.children)
        }
      }
      const walkBlocks = (blocks: readonly Block[]): void => {
        for (const b of blocks) {
          if (b.kind === 'paragraph') visit(b.inline)
          else if (b.kind === 'list') {
            const w = (items: readonly ListItem[]): void => {
              for (const it of items) {
                visit(it.inline)
                w(it.children)
              }
            }
            w(b.items)
          } else {
            b.header.forEach(visit)
            b.rows.forEach((r) => r.forEach(visit))
          }
        }
      }
      const walk = (s: Section): void => {
        walkBlocks(s.blocks)
        s.children.forEach(walk)
      }
      if (doc.summary) walk(doc.summary)
      doc.parts.forEach((p) => p.sections.forEach(walk))
      assert.ok(refs > 5, 'the premise: these documents cross-reference sections')
    })

    test(`${name}: every top-level section is in the contents and the headings are plain`, () => {
      const toc = tableOfContents(doc).flatMap((g) => g.entries)
      const sections = [...(doc.summary ? [doc.summary] : []), ...doc.parts.flatMap((p) => p.sections)]
      assert.deepEqual(
        toc.map((e) => e.id),
        sections.map((s) => s.id),
      )
      assert.ok(toc.length >= 10)
    })

    test(`${name}: no raw braces survive in rendered text (every placeholder is a node)`, () => {
      const texts: string[] = []
      const visit = (nodes: readonly Inline[]): void => {
        for (const n of nodes) {
          if (n.kind === 'text' || n.kind === 'code') texts.push(n.text)
          else if (n.kind === 'strong' || n.kind === 'link') visit(n.children)
        }
      }
      const walkBlocks = (blocks: readonly Block[]): void => {
        for (const b of blocks) {
          if (b.kind === 'paragraph') visit(b.inline)
          else if (b.kind === 'list') {
            const w = (items: readonly ListItem[]): void => {
              for (const it of items) {
                visit(it.inline)
                w(it.children)
              }
            }
            w(b.items)
          } else {
            b.header.forEach(visit)
            b.rows.forEach((r) => r.forEach(visit))
          }
        }
      }
      const walk = (s: Section): void => {
        walkBlocks(s.blocks)
        s.children.forEach(walk)
      }
      if (doc.summary) walk(doc.summary)
      doc.parts.forEach((p) => p.sections.forEach(walk))
      for (const t of texts) assert.ok(!t.includes('{{') && !t.includes('}}'), `raw braces in: ${t}`)
    })

    test(`${name}: the version comes from the draft's own line`, () => {
      assert.ok(doc.banner, 'the committed drafts carry their DRAFT banner')
      assert.ok(doc.version, 'the version line parsed')
      assert.match(doc.version.date, /^\d{4}-\d{2}-\d{2}$/)
      assert.ok(versionLabel(doc.version)?.text.startsWith(`Version ${doc.version.number}`))
    })

    test(`${name}: tables are rectangular`, () => {
      let tables = 0
      const check = (blocks: readonly Block[]): void => {
        for (const b of blocks) {
          if (b.kind !== 'table') continue
          tables++
          for (const r of b.rows) assert.equal(r.length, b.header.length)
        }
      }
      const walk = (s: Section): void => {
        check(s.blocks)
        s.children.forEach(walk)
      }
      doc.parts.forEach((p) => p.sections.forEach(walk))
      assert.ok(name === 'terms' || tables >= 2, 'the Privacy Policy has its data and cookie tables')
    })
  }

  test('the Privacy Policy keeps the sections the notes file and the Terms point at', () => {
    const ids = new Set(allAnchorIds(privacyPolicy))
    for (const id of ['summary', 's-3', 's-3-4', 's-3-8', 's-4-1', 's-11-2', 's-13']) assert.ok(ids.has(id), id)
  })

  test('the Terms are grouped into Parts A to G', () => {
    assert.deepEqual(
      termsOfService.parts.map((p) => p.label),
      ['Part A', 'Part B', 'Part C', 'Part D', 'Part E', 'Part F', 'Part G'],
    )
  })
})

// ---------------------------------------------------------------------------------------
// 3. The parser on synthetic input
// ---------------------------------------------------------------------------------------

describe('the markdown parser', () => {
  test('numbers clauses, anchors them and resolves "section N" references', () => {
    const doc = parseLegalMarkdown(
      '# T\n\nVersion 1.0 (final, 2026-01-02).\n\n## 1. One\n\n1.1 First clause, see section 2.\n\n## 2. Two\n\n2.1 Second, with **bold** and `code`.\n',
      't.md',
    )
    const one = doc.parts[0]?.sections[0]
    assert.equal(one?.id, 's-1')
    const clause = one?.blocks[0]
    assert.ok(clause && clause.kind === 'paragraph')
    assert.equal(clause.clause, '1.1')
    assert.equal(clause.anchor, 's-1-1')
    assert.deepEqual(clause.inline, [
      { kind: 'text', text: 'First clause, see section ' },
      { kind: 'ref', anchor: 's-2', text: '2' },
      { kind: 'text', text: '.' },
    ])
  })

  test('a list of references links every number and keeps the separators as text', () => {
    const doc = parseLegalMarkdown(
      '# T\n\nVersion 1.0 (final, 2026-01-02).\n\n## 1. One\n\n1.1 A.\n\n1.2 Sections 1.1, 1.2 and 2, and more.\n\n## 2. Two\n\nBody.\n',
      't.md',
    )
    const p = doc.parts[0]?.sections[0]?.blocks[1]
    assert.ok(p && p.kind === 'paragraph')
    assert.equal(inlineToText(p.inline), 'Sections 1.1, 1.2 and 2, and more.')
    assert.deepEqual(
      p.inline.filter((n) => n.kind === 'ref').map((n) => (n.kind === 'ref' ? n.anchor : '')),
      ['s-1-1', 's-1-2', 's-2'],
    )
  })

  test('a reference to a section that does not exist throws', () => {
    assert.throws(() => parseLegalMarkdown(md('1.1 See section 9.'), 't.md'), /refers to a section or clause that does not exist/)
  })

  test('a placeholder is a node, bare or in a code span, anywhere inline', () => {
    assert.deepEqual(parseInline('a `{{X_1}}` b {{Y}} **`{{Z}}`**', 't', 1), [
      { kind: 'text', text: 'a ' },
      { kind: 'placeholder', name: 'X_1' },
      { kind: 'text', text: ' b ' },
      { kind: 'placeholder', name: 'Y' },
      { kind: 'text', text: ' ' },
      { kind: 'strong', children: [{ kind: 'placeholder', name: 'Z' }] },
    ])
  })

  test('the banner is parsed, its version extracted, and its own {{PLACEHOLDER}} mention does not count', () => {
    const doc = parseLegalMarkdown(
      '# T\n\n> **DRAFT: REVIEW ME**\n>\n> Version 1.2 (draft, 2026-02-03). Fill every `{{PLACEHOLDER}}`.\n\n## 1. One\n\nNo placeholders here.\n',
      't.md',
    )
    assert.deepEqual(doc.version, {
      number: '1.2',
      status: 'draft',
      date: '2026-02-03',
      line: 'Version 1.2 (draft, 2026-02-03)',
      source: 'banner',
    })
    assert.equal(doc.banner?.headline.length, 1)
    assert.equal(placeholderOccurrences(doc).length, 0, 'the banner mention is not a missing fact')
    const state = legalPageState(doc)
    assert.equal(state.reasons.placeholders, false)
    assert.equal(state.reasons.banner, true, 'but the banner itself keeps the page a draft')
    assert.equal(state.draft, true)
  })

  test('the version is never guessed: a malformed or impossible line is null', () => {
    assert.equal(parseVersionLine('Version 0.3 (draft, 2026-10-01). Status.')?.date, '2026-10-01')
    for (const bad of [
      'Version 0.3 (draft, 2026-02-30).',
      'Version 0.3 (draft, 1 October 2026).',
      'Draft version 0.3 of 2026-10-01',
      'Version (draft, 2026-10-01)',
      '',
    ]) {
      assert.equal(parseVersionLine(bad), null, bad)
    }
  })

  test('the version is REQUIRED and generation fails loudly without one (it can never silently vanish)', () => {
    assert.throws(
      () => parseLegalMarkdown('# T\n\n> **DRAFT**\n>\n> No version line here.\n\n## 1. One\n\nBody.\n', 't.md'),
      /no version line/,
    )
    assert.throws(() => parseLegalMarkdown('# T\n\n## 1. One\n\nBody.\n', 't.md'), /no version line/)
  })

  test('an unreadable version line throws rather than being skipped', () => {
    for (const bad of ['Version 0.3 (draft, 2026-02-30).', 'Version 0.3 (draft, 1 October 2026).', 'Version three.']) {
      assert.throws(() => parseLegalMarkdown(`# T\n\n${bad}\n\n## 1. One\n\nBody.\n`, 't.md'), /unreadable version line/, bad)
      assert.throws(() => parseLegalMarkdown(`# T\n\n> **DRAFT**\n>\n> ${bad}\n\n## 1. One\n\nBody.\n`, 't.md'), /unreadable version line/, bad)
    }
  })

  test('PUBLISH PATH: with the banner removed, the version is read from its own front-matter paragraph', () => {
    const doc = parseLegalMarkdown('# T\n\nVersion 1.0 (final, 2026-11-05).\n\n- **Who:** us\n\n## 1. One\n\n1.1 Body.\n', 't.md')
    assert.equal(doc.banner, null)
    assert.deepEqual(doc.version, {
      number: '1.0',
      status: 'final',
      date: '2026-11-05',
      line: 'Version 1.0 (final, 2026-11-05).',
      source: 'front-matter',
    })
    assert.equal(versionLabel(doc.version)?.text, 'Version 1.0 (final) · Last updated 5 November 2026')
    assert.equal(legalPageState(doc).draft, false)
  })

  test('the version may not be given twice, nor carry unrendered extra text, nor sit out of order', () => {
    assert.throws(
      () =>
        parseLegalMarkdown('# T\n\n> **DRAFT**\n>\n> Version 1.0 (draft, 2026-01-02).\n\nVersion 1.0 (final, 2026-01-02).\n\n## 1. One\n\nB.\n', 't.md'),
      /given twice/,
    )
    assert.throws(
      () => parseLegalMarkdown('# T\n\nVersion 1.0 (final, 2026-01-02). Effective from launch.\n\n## 1. One\n\nB.\n', 't.md'),
      /only the version statement/,
    )
    assert.throws(
      () => parseLegalMarkdown('# T\n\n- **Who:** us\n\nVersion 1.0 (final, 2026-01-02).\n\n## 1. One\n\nB.\n', 't.md'),
      /unexpected para/,
    )
  })

  test('Parts, sections, subsections, tables and nested lists parse to the typed shape', () => {
    const doc = parseLegalMarkdown(
      [
        '# T',
        '',
        'Version 1.0 (final, 2026-01-02).',
        '',
        '- **Key:** value',
        '',
        '---',
        '',
        '## Summary in plain language',
        '',
        '- one',
        '',
        '---',
        '',
        '## Part A — Alpha',
        '',
        '### 1. First',
        '',
        '1.1 Clause.',
        '',
        '- item',
        '  - child',
        '    continued',
        '- second',
        '',
        '| A | B |',
        '|---|---|',
        '| `x` | y |',
        '',
        '### 2. Second',
        '',
        'Plain.',
        '',
      ].join('\n'),
      't.md',
    )
    assert.equal(doc.facts.length, 1)
    assert.equal(doc.summary?.id, 'summary')
    assert.equal(doc.parts[0]?.label, 'Part A')
    const first = doc.parts[0]?.sections[0]
    assert.equal(first?.level, 3)
    const list = first?.blocks[1]
    assert.ok(list && list.kind === 'list')
    assert.equal(list.items[0]?.children.length, 1)
    assert.equal(inlineToText(list.items[0]?.children[0]?.inline ?? []), 'child continued')
    const table = first?.blocks[2]
    assert.ok(table && table.kind === 'table')
    assert.deepEqual(table.rows[0]?.[0], [{ kind: 'code', text: 'x' }])
  })

  test('a Windows (CRLF) checkout parses to the same content', () => {
    const src = '# T\n\nVersion 1.0 (final, 2026-01-02).\n\n## 1. One\n\n1.1 A clause.\n\n- a\n- b\n'
    assert.deepEqual(parseLegalMarkdown(src.replace(/\n/g, '\r\n'), 't.md'), parseLegalMarkdown(src, 't.md'))
  })
})

describe('the parser fails loudly on anything it does not support', () => {
  const cases: [name: string, body: string, expected: RegExp][] = [
    ['an italic with *', md('Some *emphasis* here.'), /single "\*"/],
    ['an italic with _', md('Some _emphasis_ here.'), /_italic_/],
    ['a "*" bullet', md('* item\n'), /only "-" bullets/],
    ['a "+" bullet', md('+ item\n'), /only "-" bullets/],
    ['a markdown ordered list', md('1. item\n2. item\n'), /ordered lists/],
    ['a fenced code block', md('```\ncode\n```\n'), /fenced code/],
    ['an indented code block', md('    code\n'), /indented line/],
    ['raw HTML', md('<div>hi</div>'), /HTML is not supported/],
    ['inline HTML', md('text <b>bold</b> text'), /"<"/],
    ['an HTML entity', md('fish &amp; chips'), /entities/],
    ['an image', md('![alt](/x.png)'), /images/],
    ['a bare URL in text', md('see https://example.com now'), /bare URL/],
    ['a backslash escape', md('a \\* b'), /backslash/],
    ['strikethrough', md('a ~~b~~ c'), /strikethrough/],
    ['an h4 heading', md('#### Deep\n'), /heading level 4/],
    ['a heading with no space', md('#Tag\n'), /no space/],
    ['an unknown heading', '# T\n\n## Whatever\n', /not one of/],
    ['a second h1', '# T\n\n# U\n', /only one "#"/],
    ['a document without an h1', '## 1. One\n\nBody\n', /must start with a single/],
    ['an unclosed bold', md('**oops'), /unclosed/],
    ['an unclosed backtick', md('`oops'), /unclosed backtick/],
    ['a malformed placeholder in a code span', md('`{{lower_case}}`'), /malformed placeholder/],
    ['a malformed bare placeholder', md('{{ spaced }}'), /well-formed/],
    ['a stray closing braces', md('oops }} here'), /stray "}}"/],
    ['a javascript: link', md('[x](javascript:alert(1))'), /not allowed/],
    ['an http: link', md('[x](http://example.com)'), /not allowed/],
    ['a protocol-relative link', md('[x](//evil.example)'), /not allowed/],
    ['a link with markup in its label', md('[**x**](/y)'), /markup/],
    ['a "[" that is not a link', md('see [1] here'), /not a complete/],
    ['a tab character', md('a\tb'), /tab/],
    ['a hard line break', md('line one  \nline two'), /hard line break/],
    ['an escaped table pipe', md('| a | b |\n|---|---|\n| x \\| y | z |\n'), /escaped pipes/],
    ['a ragged table', md('| a | b |\n|---|---|\n| x |\n'), /1 cells, the header has 2/],
    ['a table with no delimiter row', md('| a | b |\n| x | y |\n'), /delimiter/],
    ['an aligned table column', md('| a | b |\n|:---|---|\n| x | y |\n'), /alignment/],
    ['a "---" rule in the middle of a section', md('Before.\n\n---\n\nAfter.\n'), /rule in the middle/],
    ['a loose list', md('- a\n\n- b\n'), /loose/],
    ['a lazy list continuation', md('- a\nlazy\n'), /lazy continuation/],
    ['a lazy blockquote continuation', '# T\n\n> banner\nlazy\n\n## 1. One\n\nBody\n', /lazy continuation/],
    ['a blockquote in the body', md('> quoted\n'), /leading draft banner/],
    ['a list inside the banner', '# T\n\n> - a\n\n## 1. One\n\nBody\n', /paragraphs only/],
    ['a duplicate section number', '# T\n\n## 1. One\n\nA\n\n## 1. Again\n\nB\n', /duplicate anchor/],
    ['a clause in the wrong section', '# T\n\n## 1. One\n\n2.1 Wrong.\n\n## 2. Two\n\nB\n', /inside section 1/],
    ['a subsection under the wrong section', '# T\n\n## 1. One\n\n### 2.1 Wrong\n\nB\n', /under section 1/],
    ['mixing Parts with ## sections', '# T\n\n## Part A — X\n\n### 1. One\n\nA\n\n## 2. Two\n\nB\n', /ambiguous/],
    ['a "###" section outside any Part', '# T\n\n### 1. One\n\nA\n', /inside a "## Part/],
    ['a placeholder in a heading', '# T\n\n## 1. About {{X}}\n\nBody\n', /plain text/],
    ['markup in a heading', '# T\n\n## 1. About `x`\n\nBody\n', /plain text/],
  ]
  for (const [name, source, expected] of cases) {
    test(name, () => {
      assert.throws(() => parseLegalMarkdown(source, 't.md'), (e: unknown) => {
        assert.ok(e instanceof LegalParseError, `not a LegalParseError: ${String(e)}`)
        assert.match(e.message, expected)
        assert.match(e.message, /^t\.md/, 'the message names the source file')
        return true
      })
    })
  }

  test('an error names the line it is on', () => {
    assert.throws(() => parseLegalMarkdown('# T\n\n## 1. One\n\nfine\n\nbad *star*\n', 't.md'), /^LegalParseError: t\.md:7:|t\.md:7:/)
  })
})

describe('link targets', () => {
  test('only same-site paths, https URLs and plain mailto: addresses are links', () => {
    assert.equal(classifyHref('/privacy'), 'internal')
    assert.equal(classifyHref('https://example.com/a?b=c#d'), 'external')
    assert.equal(classifyHref('mailto:privacy@example.com'), 'mailto')
    for (const bad of [
      'javascript:alert(1)',
      'JaVaScRiPt:alert(1)',
      'data:text/html,x',
      'http://insecure.example',
      '//evil.example/x',
      '/\\evil.example',
      'https://',
      'https:///nohost',
      'ftp://x.example',
      'mailto:a@b.c?subject=x&body=y',
      'mailto:',
      'vbscript:x',
      '',
    ]) {
      assert.equal(classifyHref(bad), null, bad)
    }
  })
})

// ---------------------------------------------------------------------------------------
// 4. The draft rule
// ---------------------------------------------------------------------------------------

function docWith(body: string, bannerMentionsPlaceholder = true): LegalDocument {
  // With the banner: the version rides in the banner (status draft). Without it: the
  // version is its own front-matter paragraph (status final), the publish-path shape.
  const banner = bannerMentionsPlaceholder
    ? '> **DRAFT: NOT FINAL**\n>\n> Version 0.1 (draft, 2026-01-02). Fill every `{{PLACEHOLDER}}` first.\n\n'
    : 'Version 1.0 (final, 2026-01-02).\n\n'
  return parseLegalMarkdown(`# Synthetic Policy\n\n${banner}## 1. One\n\n${body}\n`, 'synthetic.md')
}

describe('draft treatment is derived from the remaining placeholders', () => {
  test('while a placeholder remains: draft, noindex, banner text, and it is counted', () => {
    const state = legalPageState(docWith('1.1 Contact `{{CONTACT_EMAIL}}` or {{CONTACT_EMAIL}}.\n\n1.2 Also `{{OTHER}}`.'))
    assert.equal(state.draft, true)
    assert.equal(state.noindex, true)
    assert.deepEqual(state.placeholders, ['CONTACT_EMAIL', 'OTHER'])
    assert.equal(state.placeholderCount, 3)
    assert.equal(state.bannerHeadline, 'DRAFT: NOT FINAL')
    assert.equal(DRAFT_NOTICE, 'Draft, pending legal review. This page is not our final policy.')
  })

  test('when no signal remains (no placeholders, no banner, status not draft): final, no noindex', () => {
    const state = legalPageState(docWith('1.1 Contact privacy@example.com. Nothing is missing.', false))
    assert.equal(state.draft, false)
    assert.equal(state.noindex, false)
    assert.deepEqual(state.reasons, { placeholders: false, banner: false, versionDraft: false })
    assert.deepEqual(state.placeholders, [])
    assert.equal(state.placeholderCount, 0)
  })

  test('FAILS CLOSED: every placeholder filled but the DRAFT banner still present is still a draft', () => {
    const state = legalPageState(docWith('1.1 Contact legal@example.com.', true))
    assert.equal(state.placeholderCount, 0)
    assert.equal(state.draft, true, 'filling the blanks is not publishing')
    assert.equal(state.noindex, true)
    assert.equal(state.reasons.banner, true)
  })

  test('FAILS CLOSED: a version status of "draft" keeps the page a draft even with the banner removed', () => {
    const doc = parseLegalMarkdown('# T\n\nVersion 1.0 (final, 2026-01-02).\n\n## 1. One\n\n1.1 Body.\n', 't.md')
    const draftStatus: LegalDocument = { ...doc, version: { number: '0.9', status: 'draft', date: '2026-01-02' } }
    const finalStatus: LegalDocument = { ...doc, version: { number: '1.0', status: 'final', date: '2026-01-02' } }
    assert.equal(legalPageState(draftStatus).draft, true)
    assert.equal(legalPageState(draftStatus).reasons.versionDraft, true)
    assert.equal(legalPageState(finalStatus).draft, false)
  })

  test('FAILS CLOSED: the banner alone keeps the page a draft even when the version status says final', () => {
    const doc = parseLegalMarkdown(
      '# T\n\n> **DRAFT: REVIEW ME**\n>\n> Version 1.0 (final, 2026-01-02). Banner left in by mistake.\n\n## 1. One\n\n1.1 Body.\n',
      't.md',
    )
    const state = legalPageState(doc)
    assert.deepEqual(state.reasons, { placeholders: false, banner: true, versionDraft: false })
    assert.equal(state.draft, true)
    assert.equal(state.noindex, true)
  })

  test('a placeholder alone keeps a bannerless, non-draft-status document a draft', () => {
    const state = legalPageState(docWith('1.1 Contact `{{CONTACT_EMAIL}}`.', false))
    assert.equal(state.draft, true)
    assert.equal(state.noindex, true)
    assert.deepEqual(state.reasons, { placeholders: true, banner: false, versionDraft: false })
  })

  test('publishing is explicit: the same text flips to final only when the banner is removed AND no placeholder remains', () => {
    const body = '1.1 Contact legal@example.com.'
    assert.equal(legalPageState(docWith(body, true)).noindex, true, 'banner present')
    assert.equal(legalPageState(docWith('1.1 Contact `{{CONTACT_EMAIL}}`.', false)).noindex, true, 'placeholder present')
    assert.equal(legalPageState(docWith(body, false)).noindex, false, 'banner removed and none left')
  })

  test('a placeholder is found wherever content can hold one', () => {
    const where: [string, string][] = [
      ['a paragraph', '1.1 `{{P}}`'],
      ['a list item', '- item `{{P}}`'],
      ['a nested list item', '- item\n  - nested `{{P}}`'],
      ['a table cell', '| A | B |\n|---|---|\n| x | `{{P}}` |'],
      ['a table header', '| `{{P}}` | B |\n|---|---|\n| x | y |'],
      ['bold text', '1.1 **`{{P}}`**'],
      ['a link label', '1.1 see [`{{P}}`](/privacy) now'],
      ['a bare placeholder in a link label', '1.1 see [{{P}} policy](/privacy) now'],
    ]
    for (const [name, body] of where) {
      assert.deepEqual(placeholderOccurrences(docWith(body)), ['P'], name)
    }
  })

  test('a placeholder in a link target is refused, not silently ignored', () => {
    for (const target of ['https://{{HOST}}.com/', '/{{PATH}}', 'https://example.com/{{X}}', 'mailto:{{ADDR}}@example.com']) {
      assert.throws(() => parseLegalMarkdown(md(`1.1 see [policy](${target}) now`), 't.md'), /placeholder inside the link target/, target)
    }
  })

  test('a placeholder in a link label is a counted placeholder node inside the link', () => {
    const doc = docWith('1.1 See [`{{PRIVACY_POLICY_URL}}`](/privacy).')
    assert.deepEqual(placeholderOccurrences(doc), ['PRIVACY_POLICY_URL'])
    assert.equal(legalPageState(doc).draft, true)
    const p = doc.parts[0]?.sections[0]?.blocks[0]
    assert.ok(p && p.kind === 'paragraph')
    const link = p.inline.find((n) => n.kind === 'link')
    assert.deepEqual(link, { kind: 'link', href: '/privacy', children: [{ kind: 'placeholder', name: 'PRIVACY_POLICY_URL' }] })
  })

  test('backstop: braces outside a placeholder node fail generation, whatever field they hide in', () => {
    const clean = docWith('1.1 Contact `{{X}}`.')
    assert.doesNotThrow(() => assertNoStrayBraces(clean))
    const section = clean.parts[0]?.sections[0]
    assert.ok(section)
    const withText = (inline: Inline[]): LegalDocument => ({
      ...clean,
      parts: [{ ...clean.parts[0]!, sections: [{ ...section, blocks: [{ kind: 'paragraph', inline }] }] }],
    })
    assert.throws(() => assertNoStrayBraces(withText([{ kind: 'text', text: 'oops {{X}} here' }])), /stray/)
    assert.throws(() => assertNoStrayBraces(withText([{ kind: 'link', href: 'https://{{H}}.com/', children: [{ kind: 'text', text: 'x' }] }])), /stray/)
    assert.throws(() => assertNoStrayBraces(withText([{ kind: 'code', text: '}}' }])), /stray/)
    assert.throws(() => assertNoStrayBraces({ ...clean, title: 'About {{X}}' }), /stray/)
    // ...but the banner may name the convention.
    assert.doesNotThrow(() => assertNoStrayBraces({ ...clean, banner: { headline: [{ kind: 'text', text: 'fill every {{PLACEHOLDER}}' }], notes: [] } }))
  })

  test('a placeholder in the facts list or the summary counts too', () => {
    const doc = parseLegalMarkdown(
      '# T\n\nVersion 1.0 (final, 2026-01-02).\n\n- **Who:** `{{WHO}}`\n\n---\n\n## Summary in plain language\n\n- we use `{{SUMMARY_FACT}}`\n\n---\n\n## 1. One\n\nBody.\n',
      't.md',
    )
    assert.deepEqual(placeholderOccurrences(doc), ['WHO', 'SUMMARY_FACT'])
  })

  test('the real drafts are drafts today (placeholders remain) and say so', () => {
    for (const doc of [privacyPolicy, termsOfService]) {
      const s = legalPageState(doc)
      assert.equal(s.draft, true)
      assert.equal(s.noindex, true)
      assert.ok(s.placeholders.includes('LEGAL_ENTITY_NAME'))
      assert.ok(s.bannerHeadline?.startsWith('DRAFT'))
    }
  })

  test('the page title never doubles the brand', () => {
    assert.equal(legalTitle(privacyPolicy), 'SelahCue Privacy Policy')
    assert.equal(legalTitle({ ...privacyPolicy, title: 'Privacy Policy' }), 'Privacy Policy — SelahCue')
  })
})

describe('"Last updated" is shown only when the document gives a real date', () => {
  test('formats ISO dates without locale or timezone', () => {
    assert.equal(formatIsoDate('2026-10-01'), '1 October 2026')
    assert.equal(formatIsoDate('2024-02-29'), '29 February 2024')
    assert.equal(formatIsoDate('2026-02-29'), null)
    assert.equal(formatIsoDate('01/10/2026'), null)
  })
  test('label text', () => {
    assert.deepEqual(versionLabel({ number: '0.3', status: 'draft', date: '2026-10-01' }), {
      text: 'Version 0.3 (draft) · Last updated 1 October 2026',
      iso: '2026-10-01',
    })
    assert.equal(versionLabel({ number: '1.0', status: 'final', date: '2027-01-05' })?.text, 'Version 1.0 (final) · Last updated 5 January 2027')
    assert.equal(versionLabel({ number: '1', status: 'draft', date: '2026-13-40' }), null)
    assert.equal(versionLabel(null), null)
  })
})

// ---------------------------------------------------------------------------------------
// 5. Head handling
// ---------------------------------------------------------------------------------------

/** Just enough DOM for LegalHead: a head that holds meta elements, and a title. */
function fakeHost(initialTitle = 'SelahCue') {
  interface FakeMeta {
    attrs: Map<string, string>
    parent: FakeMeta[] | null
    setAttribute(k: string, v: string): void
    remove(): void
  }
  const metas: FakeMeta[] = []
  const host = {
    title: initialTitle,
    head: {
      appendChild(node: FakeMeta) {
        node.parent = metas
        metas.push(node)
        return node
      },
    },
    createElement(): FakeMeta {
      const node: FakeMeta = {
        attrs: new Map(),
        parent: null,
        setAttribute(k, v) {
          this.attrs.set(k, v)
        },
        remove() {
          const at = metas.indexOf(this)
          if (at !== -1) metas.splice(at, 1)
        },
      }
      return node
    },
    querySelector(selector: string): FakeMeta | null {
      assert.equal(selector, NOINDEX_SELECTOR)
      return metas.find((m) => m.attrs.get('name') === 'robots' && m.attrs.has('data-legal-noindex')) ?? null
    },
  }
  return { host: host as unknown as HeadHost, metas, raw: host }
}

describe('noindex and title follow the page, and cannot leak or be lost', () => {
  test('a draft page adds noindex and its title; leaving removes the tag and restores the title', () => {
    const { host, metas, raw } = fakeHost('SelahCue — home')
    const head = new LegalHead(host)
    const claim = head.claim({ title: 'SelahCue Privacy Policy', noindex: true })
    assert.equal(metas.length, 1)
    assert.equal(metas[0]?.attrs.get('content'), 'noindex')
    assert.equal(raw.title, 'SelahCue Privacy Policy')
    claim.release()
    assert.equal(metas.length, 0)
    assert.equal(raw.title, 'SelahCue — home')
    assert.equal(head.activeClaims, 0)
  })

  test('a page with no placeholders adds no noindex at all', () => {
    const { host, metas } = fakeHost()
    const claim = new LegalHead(host).claim({ title: 'SelahCue Terms of Service', noindex: false })
    assert.equal(metas.length, 0)
    claim.release()
  })

  test('the tag follows the flag while the page stays mounted', () => {
    const { host, metas } = fakeHost()
    const claim = new LegalHead(host).claim({ title: 'T', noindex: true })
    assert.equal(metas.length, 1)
    claim.update({ title: 'T', noindex: false })
    assert.equal(metas.length, 0, 'removed when the last placeholder is gone')
    claim.update({ title: 'T', noindex: true })
    assert.equal(metas.length, 1)
    claim.release()
    assert.equal(metas.length, 0)
  })

  test('Privacy -> Terms (new page set up BEFORE the old one is torn down) keeps noindex and the new title', () => {
    const { host, metas, raw } = fakeHost('SelahCue — home')
    const head = new LegalHead(host)
    const privacy = head.claim({ title: 'SelahCue Privacy Policy', noindex: true })
    const terms = head.claim({ title: 'SelahCue Terms of Service', noindex: true }) // Suspense: new page first
    privacy.release() // ...then the old page unmounts
    assert.equal(metas.length, 1, 'the tag must survive the old page leaving')
    assert.equal(raw.title, 'SelahCue Terms of Service', 'and the new page keeps its own title')
    terms.release()
    assert.equal(metas.length, 0)
    assert.equal(raw.title, 'SelahCue — home')
    assert.equal(head.activeClaims, 0)
  })

  test('a title someone else wrote after us is not overwritten on leave', () => {
    const { host, raw } = fakeHost('SelahCue — home')
    const claim = new LegalHead(host).claim({ title: 'SelahCue Privacy Policy', noindex: true })
    raw.title = 'Some Other Page'
    claim.release()
    assert.equal(raw.title, 'Some Other Page')
  })

  test('release is idempotent and many mount/unmount cycles leave nothing behind', () => {
    const { host, metas } = fakeHost()
    const head = new LegalHead(host)
    for (let i = 0; i < 500; i++) {
      const c = head.claim({ title: `T${i}`, noindex: true })
      c.release()
      c.release()
    }
    assert.equal(head.activeClaims, 0)
    assert.equal(metas.length, 0)
  })

  test('only a tag this module created is ever touched', () => {
    const { host, metas } = fakeHost()
    const foreign = host.createElement('meta')
    foreign.setAttribute('name', 'robots')
    foreign.setAttribute('content', 'index,follow')
    host.head.appendChild(foreign)
    const claim = new LegalHead(host).claim({ title: 'T', noindex: true })
    assert.equal(metas.length, 2)
    claim.release()
    assert.equal(metas.length, 1)
    assert.equal(metas[0]?.attrs.get('content'), 'index,follow')
  })
})

// ---------------------------------------------------------------------------------------
// No raw-HTML sinks in the legal rendering path
// ---------------------------------------------------------------------------------------

describe('the legal rendering path has no raw-HTML sink', () => {
  const files = [
    'components/legal/LegalPage.vue',
    'components/legal/LegalBlocks.vue',
    'components/legal/LegalInline.vue',
    'components/legal/LegalList.vue',
    'views/PrivacyView.vue',
    'views/TermsView.vue',
    'lib/legal/anchors.ts',
    'lib/legal/document.ts',
    'lib/legal/head.ts',
    'lib/legal/useLegalHead.ts',
    'lib/legal/useScrollSpy.ts',
  ]
  for (const f of files) {
    test(f, () => {
      const text = readFileSync(`${SRC}${f}`, 'utf8')
      for (const sink of ['v-html', 'innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write', 'createContextualFragment']) {
        assert.ok(!text.includes(sink), `${f} contains ${sink}`)
      }
    })
  }
})
