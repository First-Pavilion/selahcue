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
import test, { after, before, describe } from 'node:test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import vue from '@vitejs/plugin-vue'
import { createSSRApp, type Component } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createServer, type ViteDevServer } from 'vite'

import { DRAFT_NOTICE } from '../src/lib/legal/document.ts'
import type { Inline, LegalDocument } from '../src/lib/legal/types.ts'
import { parseLegalMarkdown } from '../scripts/legal_markdown.ts'

const ROOT = fileURLToPath(new URL('../', import.meta.url))

let server: ViteDevServer
let LegalPage: Component

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
  return parseLegalMarkdown(`# Synthetic Policy\n\n${withBanner ? BANNER : ''}## 1. One\n\n${body}\n`, 'synthetic.md')
}

const count = (html: string, needle: string): number => html.split(needle).length - 1

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

describe('structure and accessibility of the rendered page', () => {
  test('one h1, a skip link, a labelled Contents nav, numbered anchored sections, version as <time>', async () => {
    const html = await render(
      docFrom('1.1 First clause, see section 2.\n\n## 2. Two\n\n2.1 Second.\n\n| A | B |\n|---|---|\n| x | y |\n'),
    )
    assert.equal(count(html, '<h1'), 1)
    assert.ok(html.includes('href="#legal-text"'), 'skip link')
    assert.ok(html.includes('aria-label="Contents"'))
    assert.ok(html.includes('id="s-1"') && html.includes('id="s-1-1"') && html.includes('id="s-2"'))
    assert.ok(html.includes('id="s-1-title"') && html.includes('aria-labelledby="s-1-title"'))
    assert.ok(html.includes('data-spy="s-1"') && html.includes('data-spy="s-2"'))
    assert.ok(html.includes('href="#s-2"'), 'the in-text reference and the Contents both link to the section')
    assert.match(html, /<time datetime="2026-01-02"[^>]*>\s*Version 0\.1 \(draft\) · Last updated 2 January 2026\s*<\/time>/)
    assert.ok(html.includes('role="region"') && html.includes('aria-label="Two: table"') && html.includes('scope="col"') && html.includes('scope="row"'))
  })

  test('no version line: nothing is shown in its place', async () => {
    const doc = parseLegalMarkdown('# T\n\n> **DRAFT**\n>\n> No version here.\n\n## 1. One\n\nBody.\n', 't.md')
    const html = await render(doc)
    assert.ok(!html.includes('Last updated'))
    assert.ok(!html.includes('<time'))
  })
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
