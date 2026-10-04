/**
 * Render a real `.vue` file to HTML the way the server renderer would, and read the result as a tree.
 *
 * Vite compiles the real single-file components (`ssrLoadModule`), Vue renders them to a string, and
 * `parseHtml` turns that string into a small element tree so a test can ask structural questions
 * (what is a heading, what is hidden from assistive technology, which control is disabled) instead of
 * pattern-matching markup. Used by `homeView.test.ts`.
 *
 * Vue's server output is well formed and double-quoted, so the parser is small on purpose; it is
 * NOT a general HTML parser. Its own behaviour is pinned at the top of `homeView.test.ts`.
 */
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { createSSRApp, h, type Component } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createServer, type ViteDevServer } from 'vite'

const ROOT = fileURLToPath(new URL('../../', import.meta.url))
const SRC = path.join(ROOT, 'src')

export interface RenderServer {
  /** Render a component file under `src/` (for example `views/HomeView.vue`) to an HTML string. */
  render(file: string, props?: Record<string, unknown>): Promise<string>
  close(): Promise<void>
}

export async function startRenderServer(): Promise<RenderServer> {
  const server: ViteDevServer = await createServer({
    root: ROOT,
    configFile: false,
    logLevel: 'silent',
    appType: 'custom',
    plugins: [vue()],
    resolve: { alias: { '@': SRC } },
    server: { middlewareMode: true, hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] },
  })
  return {
    async render(file, props = {}) {
      const mod = (await server.ssrLoadModule(`/src/${file}`)) as { default: Component }
      const app = createSSRApp({ render: () => h(mod.default, props) })
      // vue-router's link, as an anchor carrying the destination: all these tests need to see.
      app.component('RouterLink', {
        props: { to: { type: [String, Object], required: true } },
        setup(p: { to: unknown }, { slots }: { slots: Record<string, () => unknown> }) {
          return () => h('a', { href: String(p.to) }, slots.default?.() as never)
        },
      })
      return renderToString(app)
    },
    close: () => server.close(),
  }
}

// --------------------------------------------------------------------------- the tree

export interface El {
  tag: string
  attrs: Record<string, string>
  children: Array<El | string>
  parent: El | null
}

const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'])

const ENTITIES: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' }

export function decodeEntities(s: string): string {
  return s.replace(/&(#x[0-9a-fA-F]+|#[0-9]+|[a-zA-Z]+);/g, (whole, name: string) => {
    if (name.startsWith('#x')) return String.fromCodePoint(parseInt(name.slice(2), 16))
    if (name.startsWith('#')) return String.fromCodePoint(parseInt(name.slice(1), 10))
    return ENTITIES[name] ?? whole
  })
}

/** Parse Vue server output into a tree under a synthetic `#root` element. */
export function parseHtml(html: string): El {
  const root: El = { tag: '#root', attrs: {}, children: [], parent: null }
  let cur = root
  const token = /<!--[\s\S]*?-->|<\/([a-zA-Z][\w-]*)\s*>|<([a-zA-Z][\w-]*)((?:\s+[^\s=>/]+(?:="[^"]*")?)*)\s*(\/?)>|([^<]+)/g
  for (const m of html.matchAll(token)) {
    if (m[0].startsWith('<!--')) continue
    if (m[1] !== undefined) {
      // A closing tag closes the nearest open element of that name (tolerates an implied close).
      let el: El | null = cur
      while (el && el.tag !== m[1].toLowerCase()) el = el.parent
      if (el?.parent) cur = el.parent
      continue
    }
    if (m[2] !== undefined) {
      const attrs: Record<string, string> = {}
      for (const a of (m[3] ?? '').matchAll(/([^\s=>/]+)(?:="([^"]*)")?/g)) attrs[a[1] as string] = decodeEntities(a[2] ?? '')
      const el: El = { tag: m[2].toLowerCase(), attrs, children: [], parent: cur }
      cur.children.push(el)
      if (!VOID.has(el.tag) && m[4] !== '/') cur = el
      continue
    }
    if (m[5] !== undefined) cur.children.push(decodeEntities(m[5]))
  }
  return root
}

export function walk(el: El, visit: (e: El) => void): void {
  visit(el)
  for (const c of el.children) if (typeof c !== 'string') walk(c, visit)
}

export function findAll(el: El, pred: (e: El) => boolean): El[] {
  const out: El[] = []
  walk(el, (e) => {
    if (pred(e)) out.push(e)
  })
  return out
}

export const hasClass = (e: El, cls: string): boolean => (e.attrs['class'] ?? '').split(/\s+/).includes(cls)

export function ancestors(e: El): El[] {
  const out: El[] = []
  for (let p = e.parent; p; p = p.parent) out.push(p)
  return out
}

const collapse = (s: string): string => s.replace(/\s+/g, ' ').trim()

/**
 * The text of an element. With `exposed`, what assistive technology would read: nothing under
 * `aria-hidden="true"`, and an element with `role="img"` is only its `aria-label`.
 */
export function textOf(el: El, opts: { exposed?: boolean } = {}): string {
  const parts: string[] = []
  const go = (e: El): void => {
    for (const c of e.children) {
      if (typeof c === 'string') {
        parts.push(c)
        continue
      }
      if (c.tag === 'br') {
        parts.push(' ')
        continue
      }
      if (opts.exposed) {
        if (c.attrs['aria-hidden'] === 'true') continue
        if (c.attrs['role'] === 'img') {
          parts.push(' ', c.attrs['aria-label'] ?? '', ' ')
          continue
        }
      }
      // Block-level boundaries must not glue two words together.
      parts.push(' ')
      go(c)
      parts.push(' ')
    }
  }
  go(el)
  return collapse(parts.join(''))
}
