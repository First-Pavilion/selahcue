/**
 * Resolves a same-site link the way the router and the content lookups would. Shared by
 * `contentLinks.test.ts` (body links, view literals) and the breadcrumb test.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { findBlogPost } from '../../src/lib/content/blog.ts'
import { docsCategories, findDocsArticle } from '../../src/lib/content/docs.ts'
import { classifyHref } from '../../src/lib/content/inline.ts'
import { findSupportArticle, supportCategories } from '../../src/lib/content/support.ts'
import { headingIds } from '../../src/lib/content/text.ts'
import type { Block, KnowledgeArticle } from '../../src/lib/content/types.ts'

const read = (rel: string): string => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')

/** Literal, parameter-free paths from router/index.ts: `path: '/pricing'` and friends. */
function staticPaths(): Set<string> {
  const src = read('../../src/router/index.ts')
  const out = new Set<string>()
  for (const m of src.matchAll(/path:\s*'(\/[a-z0-9\-/]*)'/g)) out.add(m[1] as string)
  return out
}
export const STATIC = staticPaths()

function articleHeadingIds(a: KnowledgeArticle | { body: readonly Block[] }): Set<string> {
  return new Set(headingIds(a.body).values())
}

/** `null` when the link resolves, otherwise a reason. Only same-site paths are resolved. */
export function whyUnresolvable(href: string): string | null {
  if (classifyHref(href) !== 'internal') return 'not a same-site path'
  const hashAt = href.indexOf('#')
  const hash = hashAt === -1 ? '' : href.slice(hashAt + 1)
  const base = (hashAt === -1 ? href : href.slice(0, hashAt)).split('?')[0] as string

  let m = /^\/blog\/([^/]+)$/.exec(base)
  if (m) {
    const post = findBlogPost(m[1])
    if (!post) return `no blog post "${m[1]}"`
    return hash && !articleHeadingIds(post).has(hash) ? `no heading #${hash} in that post` : null
  }
  m = /^\/docs\/([^/]+)\/([^/]+)$/.exec(base)
  if (m) {
    const a = findDocsArticle(m[1], m[2])
    if (!a) return `no docs article ${m[1]}/${m[2]}`
    return hash && !articleHeadingIds(a).has(hash) ? `no heading #${hash} in that article` : null
  }
  m = /^\/support\/([^/]+)\/([^/]+)$/.exec(base)
  if (m) {
    const a = findSupportArticle(m[1], m[2])
    if (!a) return `no support article ${m[1]}/${m[2]}`
    return hash && !articleHeadingIds(a).has(hash) ? `no heading #${hash} in that article` : null
  }
  if (!STATIC.has(base)) return `no such page ${base}`
  if (!hash) return null
  if (base === '/docs') return docsCategories.some((c) => c.id === hash) ? null : `no docs category #${hash}`
  if (base === '/support') return supportCategories.some((c) => c.id === hash) ? null : `no support category #${hash}`
  return `cannot verify an anchor on ${base}`
}

