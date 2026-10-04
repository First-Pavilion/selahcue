/**
 * Server-render one of the REAL page views, and read the markup it produces.
 *
 * Shared by `tests/secondaryPages.test.ts` (ClickUp 17tnw2b2cez). No browser and no jsdom: Vite
 * compiles the real single-file component (`ssrLoadModule`) and Vue renders it to a string, the
 * pattern `legalPage.test.ts` and `sharedComponents.test.ts` use. A real router is installed
 * (memory history), so `RouterLink` renders the anchor it would render in the browser, with the
 * href the router resolves.
 *
 * What this can see: structure, order, text, attributes, which component was used with which
 * props. What it cannot: computed colour, geometry, real focus movement. Those are asserted in a
 * browser by `tests/secondary_pages_headless.py` and measured by the visual-parity harness.
 */
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { createSSRApp, type Component } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createServer, type ViteDevServer } from 'vite'

export const ROOT = fileURLToPath(new URL('../../', import.meta.url))
export const SRC = path.join(ROOT, 'src')

export async function startViewServer(): Promise<ViteDevServer> {
  return createServer({
    root: ROOT,
    configFile: false,
    logLevel: 'silent',
    appType: 'custom',
    plugins: [vue()],
    resolve: { alias: { '@': SRC } },
    server: { middlewareMode: true, hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] },
  })
}

/** Render `src/views/<file>` at `route` (the route the router sits on while it renders). */
export async function renderView(server: ViteDevServer, file: string, route = '/'): Promise<string> {
  const mod = (await server.ssrLoadModule(`/src/views/${file}`)) as { default: Component }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:p(.*)*', component: { render: () => null } }],
  })
  await router.push(route)
  await router.isReady()
  const app = createSSRApp(mod.default)
  app.use(router)
  return renderToString(app)
}

// --------------------------------------------------------------------------- reading the markup

export interface Tag {
  name: string
  attrs: Record<string, string>
  /** Offset of the `<` in the HTML; lets a test assert DOM ORDER. */
  at: number
}

/** Opening tags of well-formed, double-quoted SSR output. Not a general HTML parser. */
export function tagsOf(html: string): Tag[] {
  const out: Tag[] = []
  for (const m of html.matchAll(/<([a-zA-Z][\w-]*)((?:\s+[^\s=>/]+(?:="[^"]*")?)*)\s*\/?>/g)) {
    const attrs: Record<string, string> = {}
    for (const a of (m[2] ?? '').matchAll(/([^\s=>/]+)(?:="([^"]*)")?/g)) attrs[a[1] as string] = a[2] ?? ''
    out.push({ name: m[1] as string, attrs, at: m.index ?? 0 })
  }
  return out
}

export const classesOf = (t: Tag): string[] => (t.attrs['class'] ?? '').split(/\s+/).filter(Boolean)

export const withClass = (html: string, cls: string): Tag[] => tagsOf(html).filter((t) => classesOf(t).includes(cls))

/** Visible-ish text: comments and tags removed, entities decoded for the few the markup uses. */
export function textOf(html: string): string {
  return html
    .replace(/<!--.*?-->/gs, '')
    .replace(/<style[\s\S]*?<\/style>/g, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Every text run in the markup: the text between tags, entities decoded, whitespace collapsed, empties dropped.
 * Comments and style blocks are not text. A visually hidden span is a run like any other (a screen reader reads it).
 */
export function textRunsOf(html: string): string[] {
  const cleaned = html.replace(/<!--[\s\S]*?-->/g, '').replace(/<style[\s\S]*?<\/style>/g, '')
  const out: string[] = []
  for (const chunk of cleaned.split(/<[^>]+>/)) {
    const t = chunk
      .replace(/&amp;/g, '&')
      .replace(/&#39;/g, "'")
      .replace(/&quot;/g, '"')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/\s+/g, ' ')
      .trim()
    if (t) out.push(t)
  }
  return out
}

export interface Heading {
  level: number
  text: string
  at: number
}

/** Every h1 to h6 in document order, with its text. */
export function headingsOf(html: string): Heading[] {
  const out: Heading[] = []
  for (const m of html.matchAll(/<h([1-6])(?:\s[^>]*)?>([\s\S]*?)<\/h\1>/g)) {
    out.push({ level: Number(m[1]), text: textOf(m[2] ?? ''), at: m.index ?? 0 })
  }
  return out
}

/**
 * Every way a heading sequence breaks the outline, as readable sentences. Empty when clean:
 * it starts at h1, there is exactly one h1, and no heading is more than one level deeper than
 * the one before it. (Going back up any number of levels is fine.)
 */
export function outlineProblems(headings: readonly Heading[]): string[] {
  const out: string[] = []
  if (headings.length === 0) return ['the page has no headings at all']
  if (headings[0]!.level !== 1) out.push(`the first heading is h${headings[0]!.level} "${headings[0]!.text}", not h1`)
  const h1s = headings.filter((h) => h.level === 1)
  if (h1s.length !== 1) out.push(`the page has ${h1s.length} h1 headings, not one`)
  for (let i = 1; i < headings.length; i++) {
    const prev = headings[i - 1]!
    const cur = headings[i]!
    if (cur.level > prev.level + 1) {
      out.push(`h${prev.level} "${prev.text}" is followed by h${cur.level} "${cur.text}": h${prev.level + 1} is skipped`)
    }
  }
  return out
}
