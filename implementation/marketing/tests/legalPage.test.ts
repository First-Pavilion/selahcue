/**
 * The REAL `LegalPage.vue`, server-rendered with synthetic documents.
 *
 * `legal.test.ts` proves the decision (`legalPageState`); this proves the page obeys it,
 * in BOTH directions, and that rendering is inert: markup in a document is shown as text,
 * and a link the generator would have refused is not emitted even if it is handed to the
 * renderer directly. No browser, no jsdom: Vite compiles the real single-file components
 * (`ssrLoadModule`), Vue renders them to a string.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { after, before, describe } from 'node:test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import vue from '@vitejs/plugin-vue'
import { createSSRApp, type Component } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createServer, type ViteDevServer } from 'vite'

import { DRAFT_NOTICE, legalPageState } from '../src/lib/legal/document.ts'
import { privacyPolicy } from '../src/lib/legal/privacy.generated.ts'
import { termsOfService } from '../src/lib/legal/terms.generated.ts'
import type { Inline, LegalDocument } from '../src/lib/legal/types.ts'
import { parseLegalMarkdown } from '../scripts/legal_markdown.ts'
import { fakeHost } from './fixtures/fakeHead.ts'

const ROOT = fileURLToPath(new URL('../', import.meta.url))

let server: ViteDevServer
let LegalPage: Component
/** From the SAME vite module graph as LegalPage: a direct import would be a different instance. */
let resetLegalHead: () => void

before(async () => {
  server = await createServer({
    root: ROOT,
    configFile: false,
    logLevel: 'silent',
    appType: 'custom',
    plugins: [vue()],
    resolve: { alias: { '@': path.resolve(ROOT, 'src') } },
    server: { middlewareMode: true, hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] },
  })
  const mod = (await server.ssrLoadModule('/src/components/legal/LegalPage.vue')) as { default: Component }
  LegalPage = mod.default
  resetLegalHead = ((await server.ssrLoadModule('/src/lib/legal/useLegalHead.ts')) as { resetLegalHead: () => void }).resetLegalHead
})

after(async () => {
  await server?.close()
})

async function render(doc: LegalDocument): Promise<string> {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { render: () => null } }] })
  await router.push('/privacy')
  await router.isReady()
  const app = createSSRApp(LegalPage, { doc, badge: 'Legal Notice' })
  app.use(router)
  return renderToString(app)
}

const BANNER = '> **DRAFT: NOT FINAL**\n>\n> Version 0.1 (draft, 2026-01-02). Fill every `{{PLACEHOLDER}}` first.\n\n'

function docFrom(body: string, withBanner = true): LegalDocument {
  // Without the banner the version is a front-matter paragraph (the publish-path shape).
  const front = withBanner ? BANNER : 'Version 1.0 (final, 2026-01-02).\n\n'
  return parseLegalMarkdown(`# Synthetic Policy\n\n${front}## 1. One\n\n${body}\n`, 'synthetic.md')
}

const count = (html: string, needle: string): number => html.split(needle).length - 1
const legalPageStateCount = (doc: LegalDocument): number => legalPageState(doc).placeholderCount

describe('draft treatment in the rendered page', () => {
  test('placeholders remain: banner, highlighted chips and the draft text are rendered', async () => {
    const html = await render(docFrom('1.1 Contact `{{CONTACT_EMAIL}}`.\n\n1.2 And `{{OTHER_DETAIL}}` and `{{CONTACT_EMAIL}}`.'))
    assert.equal(count(html, 'data-draft-banner'), 1)
    assert.ok(html.includes(DRAFT_NOTICE))
    assert.ok(html.includes('DRAFT: NOT FINAL'), "the document's own banner headline is shown")
    assert.equal(count(html, 'data-placeholder'), 3, 'one chip per occurrence')
    assert.ok(html.includes('{{CONTACT_EMAIL}}') && html.includes('{{OTHER_DETAIL}}'))
    assert.ok(html.includes('Placeholder, to be completed'), 'each chip has an accessible label')
    assert.ok(html.includes('2 details are still to be filled in (3 places)'))
  })

  test('banner removed and no placeholders remain: no banner, no chips, no draft text, from the same component', async () => {
    const html = await render(docFrom('1.1 Contact privacy@example.com. Nothing is missing.', false))
    assert.equal(count(html, 'data-draft-banner'), 0)
    assert.equal(count(html, 'data-placeholder'), 0)
    assert.ok(!html.includes(DRAFT_NOTICE))
    assert.ok(!html.includes('DRAFT: NOT FINAL'))
    assert.ok(html.includes('Contact privacy@example.com. Nothing is missing.'), 'the text itself still renders')
  })

  test('FAILS CLOSED: every placeholder filled but the document banner still present renders the draft banner', async () => {
    const html = await render(docFrom('1.1 Contact legal@example.com.'))
    assert.equal(count(html, 'data-draft-banner'), 1)
    assert.equal(count(html, 'data-placeholder'), 0)
    assert.ok(html.includes(DRAFT_NOTICE))
    assert.ok(html.includes('DRAFT: NOT FINAL'))
    assert.ok(!html.includes('still to be filled in'), 'no placeholder count when none remain')
  })

  test('a single placeholder reads "1 detail is ... (1 place)", not "1 details ... (1 places)"', async () => {
    const html = await render(docFrom('1.1 Contact `{{ONLY_ONE}}`.', false))
    assert.ok(html.includes('1 detail is still to be filled in (1 place).'))
    assert.ok(!html.includes('1 details'))
    assert.ok(!html.includes('1 places'))
  })

  test('the draft banner goes only when the banner is removed and the last placeholder is filled', async () => {
    const draft = await render(docFrom('1.1 Contact `{{CONTACT_EMAIL}}`.', false))
    const final = await render(docFrom('1.1 Contact legal@example.com.', false))
    assert.equal(count(draft, 'data-draft-banner'), 1)
    assert.equal(count(final, 'data-draft-banner'), 0)
  })

  test('a document with no banner of its own still shows the page-level draft notice while placeholders remain', async () => {
    const html = await render(docFrom('1.1 Contact `{{CONTACT_EMAIL}}`.', false))
    assert.equal(count(html, 'data-draft-banner'), 1)
    assert.ok(html.includes(DRAFT_NOTICE))
  })
})

/**
 * Render with a fake `document` on globalThis, so the REAL path from LegalPage to the robots
 * tag runs (state -> useLegalHead -> LegalHead -> <meta>): `noindex` wired to the wrong
 * signal (say, the placeholder count alone) is only visible here, not in `legalPageState`.
 */
async function renderWithHead(doc: LegalDocument): Promise<{ html: string; robots: string[]; title: string }> {
  const { host, metas, raw } = fakeHost('SelahCue (default)')
  const g = globalThis as { document?: unknown }
  const before = g.document
  g.document = host
  resetLegalHead()
  try {
    const html = await render(doc)
    const robots = metas.filter((m) => m.attrs.get('name') === 'robots').map((m) => m.attrs.get('content') ?? '')
    return { html, robots, title: raw.title }
  } finally {
    resetLegalHead()
    if (before === undefined) delete g.document
    else g.document = before
  }
}

describe('the robots noindex tag follows EVERY draft signal (real wiring, not just the decision function)', () => {
  const finalBanner = '> **DRAFT: NOT FINAL**\n>\n> Version 1.0 (final, 2026-01-02). Banner left in by mistake.\n\n'
  const parse = (front: string, body: string): LegalDocument =>
    parseLegalMarkdown(`# Synthetic Policy\n\n${front}## 1. One\n\n${body}\n`, 'synthetic.md')

  test('BANNER ONLY: every placeholder filled, DRAFT banner kept (status final) => noindex is sent', async () => {
    const r = await renderWithHead(parse(finalBanner, '1.1 Contact legal@example.com. Nothing is missing.'))
    assert.deepEqual(r.robots, ['noindex'])
    assert.equal(count(r.html, 'data-draft-banner'), 1)
  })

  test('STATUS ONLY: no banner, no placeholders, status "pending review" => noindex is sent', async () => {
    const r = await renderWithHead(parse('Version 1.0 (pending review, 2026-01-02).\n\n', '1.1 Nothing is missing.'))
    assert.deepEqual(r.robots, ['noindex'])
  })

  test('PLACEHOLDER ONLY: status final, no banner, one placeholder => noindex is sent', async () => {
    const r = await renderWithHead(parse('Version 1.0 (final, 2026-01-02).\n\n', '1.1 Contact `{{CONTACT_EMAIL}}`.'))
    assert.deepEqual(r.robots, ['noindex'])
  })

  test('PUBLISHED: no banner, status final, no placeholders => no robots tag at all, and the title is set', async () => {
    const r = await renderWithHead(parse('Version 1.0 (final, 2026-01-02).\n\n', '1.1 Nothing is missing.'))
    assert.deepEqual(r.robots, [])
    assert.equal(r.title, 'Synthetic Policy — SelahCue')
  })

  test('the real committed drafts are sent noindex', async () => {
    assert.deepEqual((await renderWithHead(privacyPolicy)).robots, ['noindex'])
    assert.deepEqual((await renderWithHead(termsOfService)).robots, ['noindex'])
  })
})

describe('structure and accessibility of the rendered page', () => {
  test('one h1, a skip link, a labelled Contents nav, numbered anchored sections, version as <time>', async () => {
    const html = await render(
      docFrom('1.1 First clause, see section 2.\n\n## 2. Two\n\n2.1 Second.\n\n| A | B |\n|---|---|\n| x | y |\n'),
    )
    assert.equal(count(html, '<h1'), 1)
    assert.ok(html.includes('href="#legal-text"'), 'skip link')
    assert.ok(html.includes('aria-label="Contents"'))
    assert.ok(html.includes('id="s-1"') && html.includes('id="s-1-1"') && html.includes('id="s-2"'))
    assert.ok(html.includes('id="s-1-title"'))
    assert.ok(html.includes('data-spy="s-1"') && html.includes('data-spy="s-2"'))
    assert.ok(!html.includes('<aside'), 'no unnamed aside: the nav carries the name')
    assert.ok(html.includes('href="#s-2"'), 'the in-text reference and the Contents both link to the section')
    assert.match(html, /<time datetime="2026-01-02"[^>]*>\s*Version 0\.1 \(draft\) · Last updated 2 January 2026\s*<\/time>/)
    assert.ok(html.includes('<table') && html.includes('aria-label="Two"') && html.includes('scope="col"') && html.includes('scope="row"'), 'the table is named and has headers')
    assert.ok(!html.includes('role="region"') && !html.includes('tabindex="0"'), 'no region or tab stop until the table actually overflows (decided in the browser)')
  })

  test('PUBLISH PATH: with the banner removed, "Last updated" is still shown from the front-matter version line', async () => {
    const html = await render(docFrom('1.1 Body.', false))
    assert.match(html, /<time datetime="2026-01-02"[^>]*>\s*Version 1\.0 \(final\) · Last updated 2 January 2026\s*<\/time>/)
    assert.equal(count(html, 'data-draft-banner'), 0)
  })
})

/** Text of every h1-h3 in rendered HTML, tags stripped, entities decoded, whitespace collapsed. */
function renderedHeadings(html: string): string[] {
  const decode = (t: string): string =>
    t.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
  return [...html.matchAll(/<h([1-3])\b[^>]*>([\s\S]*?)<\/h\1>/g)].map((m) =>
    decode((m[2] ?? '').replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]+>/g, ''))
      .replace(/\s+/g, ' ')
      .trim(),
  )
}

/** The headings the typed content says should exist, in reading order. */
function expectedHeadings(doc: LegalDocument): string[] {
  const out = [doc.title]
  if (doc.summary) out.push(doc.summary.title)
  for (const p of doc.parts) {
    if (p.label && p.title) out.push(`${p.label} — ${p.title}`)
    for (const s of p.sections) {
      out.push(`${s.number}. ${s.title}`) // top-level numbers have no dot of their own
      for (const c of s.children) out.push(`${c.number} ${c.title}`)
    }
  }
  return out
}

describe('rendered headings equal the typed content (nothing dropped between data and page)', () => {
  for (const [name, doc] of [
    ['privacy', privacyPolicy],
    ['terms', termsOfService],
  ] as const) {
    test(name, async () => {
      const got = renderedHeadings(await render(doc))
      const want = expectedHeadings(doc)
      assert.ok(want.length > 15, 'the premise: these documents have many headings')
      assert.deepEqual(got, want)
    })
  }

  test('Terms Part headings keep the dash the markdown has: "Part A — The agreement"', async () => {
    const got = renderedHeadings(await render(termsOfService))
    assert.ok(got.includes('Part A — The agreement'))
    assert.ok(got.includes('Part G — General terms'))
    assert.ok(!got.some((h) => /^Part [A-G] [^—]/.test(h)), 'no Part heading lost its dash')
  })
})

describe("the document's own banner text is rendered while it is a draft", () => {
  test('real drafts: status line, launch caveat and the Controller-policy pointer are all on the page', async () => {
    const html = await render(privacyPolicy)
    assert.ok(html.includes('Status: Draft'))
    assert.ok(html.includes('describes SelahCue as it operates at launch'))
    assert.ok(html.includes('also has its own policy'))
    assert.equal(count(html, 'data-placeholder'), legalPageStateCount(privacyPolicy), 'the banner mention is code, not a highlighted chip')
  })

  test('a banner note mentioning {{PLACEHOLDER}} shows as plain code and is not counted as a missing fact', async () => {
    const html = await render(docFrom('1.1 Contact legal@example.com.'))
    assert.ok(html.includes('Fill every'))
    assert.ok(html.includes('{{PLACEHOLDER}}'))
    assert.equal(count(html, 'data-placeholder'), 0)
  })
})

/** Visible text of an HTML fragment, the way copy/paste or a text extractor would see it. */
function textOf(html: string): string {
  return html
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
}

describe('landmarks stay few: only the summary and the draft banner are named regions', () => {
  for (const [name, doc] of [
    ['privacy', privacyPolicy],
    ['terms', termsOfService],
  ] as const) {
    test(name, async () => {
      const html = await render(doc)
      const named = count(html, 'aria-labelledby=')
      assert.ok(named <= 3, `${named} aria-labelledby regions (was 15 and 27 section landmarks)`)
      assert.ok(count(html, '<section') >= 14, 'the sections are still sections')
      assert.equal(count(html, '<nav '), 1)
      assert.equal(count(html, '<aside'), 0)
    })
  }
})

describe('clause numbers are separated from their text by a real space', () => {
  test('"1.1 This policy..." not "1.1This policy..." in the text a copy or extractor reads', async () => {
    const html = await render(privacyPolicy)
    const clauses = [...html.matchAll(/<p class="lb-p lb-clause"[^>]*>([\s\S]*?)<\/p>/g)].map((m) => textOf(m[1] ?? ''))
    assert.ok(clauses.length >= 32, `the premise: many numbered clauses (${clauses.length})`)
    for (const c of clauses) assert.match(c, /^\d+\.\d+ \S/, `no space after the clause number in: ${c.slice(0, 40)}`)
    assert.ok(clauses.some((c) => c.startsWith('1.1 This policy explains')))
  })
})

describe('the skip link is hidden by clipping, not by parking it off-screen', () => {
  const source = readFileSync(fileURLToPath(new URL('../src/components/legal/LegalPage.vue', import.meta.url)), 'utf8')
  const rule = /\.skip-link\s*\{([^}]*)\}/.exec(source)?.[1] ?? ''

  test('the resting rule clips and does not use a large negative offset', () => {
    assert.ok(rule.length > 0, 'found the .skip-link rule')
    assert.match(rule, /clip-path:\s*inset\(50%\)/)
    assert.doesNotMatch(rule, /(left|right|top|inset-inline-start)\s*:\s*-\d{3,}/, 'no huge negative offset (it breaks responsive audits)')
  })

  test('it becomes visible on focus, in the near-black-on-near-white pairing (not white on a brand colour)', () => {
    assert.match(source, /\.skip-link:focus[\s\S]*?clip-path:\s*none/)
    assert.doesNotMatch(rule, /color:\s*#fff\b/)
    assert.match(rule, /background:\s*var\(--sc-text\)/)
    assert.match(rule, /color:\s*var\(--sc-base\)/)
  })
})

describe('breakpoints and gutters agree with the rest of the site (and with PR #140 once it lands)', () => {
  const dir = fileURLToPath(new URL('../src/components/legal/', import.meta.url))
  const css = ['LegalPage.vue', 'LegalBlocks.vue', 'LegalInline.vue', 'LegalList.vue', 'LegalTable.vue'].map((f) => [f, readFileSync(`${dir}${f}`, 'utf8')] as const)
  const page = css[0]?.[1] ?? ''

  test('NO max-width media query ends at a whole pixel: every range end is the .98 form (same rule as PR #140)', () => {
    // At a fractional viewport (browser zoom gives 767.5px) `max-width: 767px` and the next
    // range's `min-width: 768px` both miss. #140's tripwire bans every whole-pixel max-width
    // in @media, so this does too; the legal components have no exception to list.
    const offenders: string[] = []
    for (const [file, text] of css) {
      for (const line of text.split('\n')) {
        if (!line.includes('@media')) continue
        for (const m of line.matchAll(/max-width:\s*(\d+)px/g)) offenders.push(`${file}: ${line.trim()} (${m[1]}px)`)
      }
    }
    assert.deepEqual(offenders, [])
  })

  test('the stacking and phone breakpoints are the .98 forms', () => {
    assert.match(page, /@media \(max-width: 819\.98px\)/)
    assert.match(page, /@media \(max-width: 519\.98px\)/)
  })

  test('the mobile and tablet range ends are the site\'s complementary .98 forms', () => {
    assert.match(page, /@media \(max-width: 767\.98px\)/)
    assert.match(page, /@media \(max-width: 1199\.98px\)/)
  })

  test('the shell takes the site token when it exists and falls back to the same 24/48/20 steps otherwise', () => {
    assert.match(page, /\.legal-shell\s*\{[^}]*padding-inline:\s*var\(--page-gutter,\s*var\(--legal-gutter\)\)/)
    assert.match(page, /--legal-gutter:\s*24px/)
    assert.match(page, /@media \(max-width: 1199\.98px\)\s*\{\s*\.legal-page \{ --legal-gutter: 48px; \}/)
    assert.match(page, /@media \(max-width: 767\.98px\)\s*\{\s*\.legal-page \{ --legal-gutter: 20px; \}/)
    assert.equal(page.split('--legal-gutter:').length - 1, 3, 'defined once per breakpoint, nowhere else')
  })
})

describe('one offset mechanism for anchors (no double offset next to a page-wide scroll-padding)', () => {
  const page = readFileSync(fileURLToPath(new URL('../src/components/legal/LegalPage.vue', import.meta.url)), 'utf8')
  const anchors = readFileSync(fileURLToPath(new URL('../src/lib/legal/anchors.ts', import.meta.url)), 'utf8')

  test('the lift, the skip target and the page share ONE variable, defined once from the navbar height', () => {
    assert.equal(page.split('--legal-anchor-offset:').length - 1, 1, 'defined exactly once')
    assert.match(page, /--legal-anchor-offset:\s*calc\(var\(--nav-height, 68px\) \+ 20px\)/)
    assert.match(page, /\.legal-anchor\s*\{[^}]*top:\s*calc\(-1 \* var\(--legal-anchor-offset/)
    assert.match(page, /#legal-text\s*\{[^}]*scroll-margin-top:\s*var\(--legal-anchor-offset\)/)
  })

  test('a page-wide scroll-padding-top is neutralised while a legal page is mounted', () => {
    assert.match(page, /html:has\(\.legal-page\)\s*\{\s*scroll-padding-top:\s*0/)
  })

  test('the neutraliser is scoped to the mounted page: `html:has(.legal-page)`, and the page root carries that class', async () => {
    // Zero while mounted, restored on unmount, even next to a page-wide `html { scroll-padding-top }`
    // (PR #135): the rule matches only while a `.legal-page` is in the document, and it beats a bare
    // `html` rule on specificity. The browser check proves the restore on unmount for real.
    assert.match(page, /html:has\(\.legal-page\)\s*\{\s*scroll-padding-top:\s*0;?\s*\}/)
    assert.equal((page.match(/scroll-padding-top\s*:/g) ?? []).length, 1, 'exactly one declaration: the neutraliser, scoped by :has(.legal-page)')
    // specificity: html:has(.legal-page) is (0,1,1), a bare `html` is (0,0,1)
    const spec = (sel: string): [number, number, number] => [
      (sel.match(/#[\w-]+/g) ?? []).length,
      (sel.match(/\.[\w-]+/g) ?? []).length,
      sel.replace(/:has\([^)]*\)/g, '').match(/(^|[\s>+~])[a-z][a-z0-9]*/gi)?.length ?? 0,
    ]
    assert.deepEqual(spec('html:has(.legal-page)'), [0, 1, 1])
    assert.deepEqual(spec('html'), [0, 0, 1])
    const html = await render(privacyPolicy)
    assert.match(html, /<div class="legal-page"/, 'the root element the rule keys on')
  })

  test('manual scrolling reads only the element\'s own scroll-margin, never scrollIntoView (which adds the page padding)', () => {
    assert.ok(!anchors.includes('scrollIntoView'), 'anchors.ts must not use scrollIntoView')
    assert.ok(!page.includes('scrollIntoView'), 'LegalPage.vue must not use scrollIntoView')
    assert.match(anchors, /scrollMarginTop/)
  })
})

describe('a placeholder inside an external or mailto link label is counted and highlighted', () => {
  for (const target of ['https://example.com/policy', 'mailto:privacy@example.com', '/privacy']) {
    test(`label of [${target}]`, async () => {
      const doc = parseLegalMarkdown(
        `# T\n\nVersion 1.0 (final, 2026-01-02).\n\n## 1. One\n\n1.1 Write to [\`{{CONTACT_LABEL}}\`](${target}) or [plain {{SECOND_LABEL}} words](${target}).\n`,
        't.md',
      )
      const state = legalPageState(doc)
      assert.equal(state.placeholderCount, 2)
      assert.deepEqual(state.placeholders, ['CONTACT_LABEL', 'SECOND_LABEL'])
      assert.equal(state.draft, true, 'a placeholder in a link label keeps the page a draft')
      const html = await render(doc)
      assert.equal(count(html, 'data-placeholder'), 2, 'both labels render as highlighted chips')
      const anchors = [...html.matchAll(/<a [^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/g)].filter((m) => (m[1] ?? '') === target || (m[1] ?? '') === target)
      assert.ok(anchors.length >= 2 && anchors.every((m) => (m[2] ?? '').includes('data-placeholder')), 'the chips sit inside the links')
    })
  }
})

describe('rendering is inert', () => {
  function docWithInline(inline: Inline[]): LegalDocument {
    const base = docFrom('1.1 placeholder.')
    const part = base.parts[0]
    const section = part?.sections[0]
    assert.ok(part && section)
    return {
      ...base,
      parts: [{ ...part, sections: [{ ...section, blocks: [{ kind: 'paragraph', inline }] }] }],
    }
  }

  test('markup in a text node is displayed as text, never emitted', async () => {
    const html = await render(docWithInline([{ kind: 'text', text: '<script>alert(1)</script><img src=x onerror=alert(2)>' }]))
    assert.ok(!html.includes('<script>alert(1)'))
    assert.ok(!html.includes('<img src=x'))
    assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'))
  })

  test('a link target the generator would refuse is not emitted even if handed to the renderer', async () => {
    for (const href of ['javascript:alert(1)', 'data:text/html,x', '//evil.example', 'http://insecure.example', '/\\evil']) {
      const html = await render(docWithInline([{ kind: 'link', href, children: [{ kind: 'text', text: 'click me' }] }]))
      assert.ok(html.includes('click me'), 'the label is kept as text')
      assert.ok(!html.includes(`href="${href}"`), `${href} must not become a link`)
      assert.ok(!/href="(javascript|data):/i.test(html))
    }
  })

  test('safe links are emitted, and external ones open safely', async () => {
    const html = await render(
      docWithInline([
        { kind: 'link', href: 'https://example.com/x', children: [{ kind: 'text', text: 'ext' }] },
        { kind: 'link', href: 'mailto:a@example.com', children: [{ kind: 'text', text: 'mail' }] },
      ]),
    )
    assert.ok(html.includes('href="https://example.com/x"') && html.includes('rel="noopener noreferrer"') && html.includes('target="_blank"'))
    assert.ok(html.includes('href="mailto:a@example.com"'))
    assert.ok(html.includes('(opens in a new tab)'))
  })
})
