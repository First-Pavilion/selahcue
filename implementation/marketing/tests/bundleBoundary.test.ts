/**
 * The article corpus must stay OUT of the entry bundle, and the citation trail must stay
 * out of the browser entirely.
 *
 * Two things went wrong the first time, and both were invisible to every existing gate:
 *   1. `router/articleRoutes.ts` statically imported `lib/content/*`, and `router/index.ts`
 *      imports that module, so every article body landed in the ENTRY chunk (80.8 -> 161.5 kB,
 *      +82%) and the home, pricing and sign-in pages paid for blog text.
 *   2. Each article carried a `sources` array of internal repo paths, which shipped to
 *      every visitor.
 *
 * This walks the STATIC import graph from `src/main.ts` (dynamic `import()` is a chunk
 * boundary and is deliberately not followed) and fails if it can reach the corpus. A
 * positive control proves the walker finds edges at all: starting at a lazy view it MUST
 * reach the corpus, otherwise "unreachable from main" would be satisfied by a walker that
 * resolves nothing.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

const SRC = fileURLToPath(new URL('../src/', import.meta.url))
const CORPUS = ['lib/content/blog.ts', 'lib/content/docs.ts', 'lib/content/support.ts'].map((p) => join(SRC, p))

/** Source text that can contain imports: a `.ts` file, or the `<script>` blocks of a `.vue`. */
function scriptText(file: string): string {
  const text = readFileSync(file, 'utf8')
  if (!file.endsWith('.vue')) return text
  return [...text.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join('\n')
}

/** Static specifiers only: `import … from 'x'`, `export … from 'x'`, `import 'x'`. */
function staticSpecifiers(file: string): string[] {
  const text = scriptText(file)
  const out: string[] = []
  for (const m of text.matchAll(/(?:^|[\s;])(?:import|export)\s+(?:type\s+)?(?:[\w*{}\s,$]+?\s+from\s+)?['"]([^'"]+)['"]/gm)) {
    out.push(m[1] as string)
  }
  return out
}

function resolveSpecifier(from: string, spec: string): string | null {
  const target = spec.startsWith('@/') ? join(SRC, spec.slice(2)) : spec.startsWith('.') ? resolve(dirname(from), spec) : null
  return target !== null && existsSync(target) && statSync(target).isFile() ? target : null
}

function reachable(entry: string): Set<string> {
  const seen = new Set<string>()
  const queue = [entry]
  while (queue.length > 0) {
    const file = queue.pop() as string
    if (seen.has(file)) continue
    seen.add(file)
    for (const spec of staticSpecifiers(file)) {
      const next = resolveSpecifier(file, spec)
      if (next !== null && /\.(ts|vue)$/.test(next)) queue.push(next)
    }
  }
  return seen
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name)
    return statSync(full).isDirectory() ? walk(full) : [full]
  })
}

describe('the article corpus is not in the entry bundle', () => {
  const fromMain = reachable(join(SRC, 'main.ts'))

  test('the walker is not vacuous: from main it reaches the router and the app shell', () => {
    for (const must of ['router/index.ts', 'router/articleRoutes.ts', 'App.vue', 'components/Navbar.vue']) {
      assert.ok(fromMain.has(join(SRC, must)), `walker never reached ${must}`)
    }
    assert.ok(fromMain.size > 8)
  })

  test('positive control: a lazy article view DOES statically reach the corpus', () => {
    assert.ok(reachable(join(SRC, 'views/BlogPostView.vue')).has(join(SRC, 'lib/content/blog.ts')))
    assert.ok(reachable(join(SRC, 'views/DocsArticleView.vue')).has(join(SRC, 'lib/content/docs.ts')))
    assert.ok(reachable(join(SRC, 'views/SupportArticleView.vue')).has(join(SRC, 'lib/content/support.ts')))
  })

  test('nothing reachable statically from main.ts imports an article collection', () => {
    for (const file of CORPUS) {
      assert.ok(!fromMain.has(file), `the entry bundle can statically reach ${file.slice(SRC.length)}`)
    }
  })

  test('the route table reaches the corpus only through dynamic import()', () => {
    const src = readFileSync(join(SRC, 'router/articleRoutes.ts'), 'utf8')
    assert.ok(!/from\s+['"][^'"]*lib\/content\/(blog|docs|support)/.test(src))
  })
})

describe('the citation trail never ships', () => {
  const files = walk(SRC).filter((f) => /\.(ts|vue)$/.test(f))

  test('no source file under src/ carries an article `sources` list or a `supports:` note', () => {
    assert.ok(files.length > 20)
    for (const f of files) {
      const text = readFileSync(f, 'utf8')
      assert.ok(!/\bsupports\s*:/.test(text), `${f.slice(SRC.length)} carries a citation note`)
      assert.ok(!/implementation\/desktop\/crates/.test(text), `${f.slice(SRC.length)} embeds an internal repo path`)
    }
  })

  test('no source file imports from tests/', () => {
    for (const f of files) {
      for (const spec of staticSpecifiers(f)) {
        assert.ok(!/(^|\/)tests\//.test(spec), `${f.slice(SRC.length)} imports ${spec}`)
      }
    }
  })

  test('article objects have no `sources` property', async () => {
    const [{ blogPosts }, { docsArticles }, { supportArticles }] = await Promise.all([
      import('../src/lib/content/blog.ts'),
      import('../src/lib/content/docs.ts'),
      import('../src/lib/content/support.ts'),
    ])
    for (const a of [...blogPosts, ...docsArticles, ...supportArticles]) {
      assert.ok(!('sources' in a), `${a.slug} still carries sources at runtime`)
    }
  })
})
