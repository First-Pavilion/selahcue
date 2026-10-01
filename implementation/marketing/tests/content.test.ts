/**
 * The local article content (GAP-08): inline renderer safety, text helpers, and the
 * invariants every collection must hold so a detail page can never be blank or dangling.
 *
 * The index pages are generated FROM these collections (BlogView / DocsView / SupportView
 * import them), so "every card on an index page resolves to a real article" is true by
 * construction; the tests below pin the parts that construction cannot cover — unique
 * slugs, URL-safe slugs, non-empty bodies, real citations — and that no index entry is
 * ever hand-written beside the data.
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { blogPath, blogPosts, blogNeighbours, featuredPost, findBlogPost, relatedPosts } from '../src/lib/content/blog.ts'
import { docs, docsArticles, docsCategories, docsPath, findDocsArticle, docsNeighbours } from '../src/lib/content/docs.ts'
import { classifyHref, inlineToText, parseInline } from '../src/lib/content/inline.ts'
import { articlePath, readingOrder, relatedIn } from '../src/lib/content/knowledge.ts'
import {
  HEADING_ID_PREFIX,
  SLUG_PATTERN,
  formatDate,
  headingIds,
  pageTitle,
  readMinutes,
  tableOfContents,
  wordCount,
} from '../src/lib/content/text.ts'
import { support, supportArticles, supportCategories, supportPath, findSupportArticle } from '../src/lib/content/support.ts'
import type { Block, BlogPost, KnowledgeArticle } from '../src/lib/content/types.ts'
import { SOURCES } from './fixtures/content-sources.ts'

const REPO_ROOT = fileURLToPath(new URL('../../../', import.meta.url))
const MARKETING_SRC = fileURLToPath(new URL('../src/', import.meta.url))

/**
 * Every git-tracked path with its file mode, from `git ls-files -s`. `existsSync` would have
 * been the easy check and is the wrong one: it passes directories, passes a wrong-case path
 * on macOS's case-insensitive filesystem, and passes a gitignored file that exists only on
 * this machine. A citation must name a TRACKED REGULAR FILE, spelled exactly as git has it.
 */
function trackedFiles(): Map<string, string> {
  const raw = execFileSync('git', ['ls-files', '-s', '-z'], { cwd: REPO_ROOT, maxBuffer: 256 * 1024 * 1024 }).toString('utf8')
  const out = new Map<string, string>()
  for (const entry of raw.split('\0')) {
    const m = /^(\d{6}) [0-9a-f]+ \d\t(.+)$/s.exec(entry)
    if (m) out.set(m[2] as string, m[1] as string)
  }
  return out
}
const TRACKED = trackedFiles()
const isTrackedRegularFile = (path: string): boolean => {
  const mode = TRACKED.get(path)
  return mode === '100644' || mode === '100755'
}

describe('inline markup parses to safe segments', () => {
  test('bold, code, key and link become their own segments', () => {
    assert.deepEqual(parseInline('Press [[Enter]] to **go live** with `Rom 8:28` or [read more](/docs).'), [
      { kind: 'text', text: 'Press ' },
      { kind: 'kbd', text: 'Enter' },
      { kind: 'text', text: ' to ' },
      { kind: 'strong', text: 'go live' },
      { kind: 'text', text: ' with ' },
      { kind: 'code', text: 'Rom 8:28' },
      { kind: 'text', text: ' or ' },
      { kind: 'link', text: 'read more', href: '/docs', external: false },
      { kind: 'text', text: '.' },
    ])
  })

  test('HTML in a string stays text: it is never interpreted', () => {
    const segs = parseInline('<img src=x onerror=alert(1)> and <script>alert(1)</script>')
    assert.equal(segs.length, 1)
    assert.equal(segs[0]?.kind, 'text')
  })

  test('only same-site paths and https URLs become links', () => {
    for (const bad of ['javascript:alert(1)', '//evil.example/x', 'http://insecure.example', 'data:text/html,x', '/\\evil']) {
      assert.equal(classifyHref(bad), null, bad)
      const [seg] = parseInline(`[click](${bad})`)
      assert.deepEqual(seg, { kind: 'text', text: 'click' }, `${bad} must degrade to plain text`)
    }
    assert.equal(classifyHref('/docs/x/y'), 'internal')
    assert.equal(classifyHref('https://ndi.video/'), 'external')
  })

  test('inlineToText strips markup', () => {
    assert.equal(inlineToText('a **b** `c` [[D]] [e](/f)'), 'a b c D e')
  })
})

describe('text helpers', () => {
  const body: Block[] = [
    { type: 'h2', text: 'First `step`' },
    { type: 'p', text: 'one two three' },
    { type: 'h2', text: 'First step' },
    { type: 'h3', text: 'Detail' },
  ]

  test('heading ids are slugs and collisions are disambiguated in order', () => {
    const ids = headingIds(body)
    assert.deepEqual([...ids.values()], ['sec-first-step', 'sec-first-step-2', 'sec-detail'])
  })

  test('generated ids can never collide with an id a view owns: a heading called "Docs nav" is still sec-docs-nav', () => {
    const ids = headingIds([{ type: 'h2', text: 'Docs nav' }, { type: 'h2', text: 'Docs article' }])
    assert.deepEqual([...ids.values()], ['sec-docs-nav', 'sec-docs-article'])
    // Every id the article views and index views declare by hand must stay OUTSIDE the prefix.
    const read = (n: string): string => readFileSync(MARKETING_SRC + `views/${n}.vue`, 'utf8')
    const fixed: string[] = []
    for (const n of ['BlogPostView', 'DocsArticleView', 'SupportArticleView', 'DocsView', 'SupportView', 'BlogView']) {
      for (const m of read(n).matchAll(/\bid="([^"]+)"/g)) fixed.push(m[1] as string)
    }
    assert.ok(fixed.includes('docs-nav') && fixed.includes('docs-article'), 'positive control: the walker finds the fixed ids')
    for (const id of fixed) assert.ok(!id.startsWith(HEADING_ID_PREFIX), `fixed id ${id} is inside the generated-id prefix`)
  })

  test('every real article uses prefixed, unique ids', () => {
    for (const a of [...blogPosts, ...docsArticles, ...supportArticles]) {
      const ids = [...headingIds(a.body).values()]
      assert.equal(new Set(ids).size, ids.length, `${a.slug}: duplicate heading ids`)
      for (const id of ids) assert.ok(id.startsWith(HEADING_ID_PREFIX), `${a.slug}: ${id}`)
    }
  })

  test('the table of contents lists h2s only', () => {
    assert.deepEqual(tableOfContents(body), [
      { id: 'sec-first-step', text: 'First step' },
      { id: 'sec-first-step-2', text: 'First step' },
    ])
  })

  test('read time is derived from the body, never below one minute', () => {
    assert.equal(readMinutes([{ type: 'p', text: 'short' }]), 1)
    const long: Block = { type: 'p', text: Array.from({ length: 401 }, () => 'word').join(' ') }
    assert.equal(wordCount([long]), 401)
    assert.equal(readMinutes([long]), 3)
  })

  test('title and date formats are stable', () => {
    assert.equal(pageTitle('Hello'), 'Hello — SelahCue')
    assert.equal(formatDate('2026-10-01'), '1 Oct 2026')
  })
})

function bodyWords(a: { body: readonly Block[] }): number {
  return wordCount(a.body)
}

function assertCollection(
  label: string,
  items: readonly (BlogPost | KnowledgeArticle)[],
  keyOf: (a: BlogPost | KnowledgeArticle) => string,
): void {
  describe(`${label}: article invariants`, () => {
    test('there are articles at all (positive control for every check below)', () => {
      assert.ok(items.length >= 3, `${label} should have several articles, has ${items.length}`)
    })

    test('slugs are URL-safe and unique', () => {
      const seen = new Set<string>()
      for (const a of items) {
        assert.match(a.slug, SLUG_PATTERN, `${keyOf(a)} is not URL-safe`)
        assert.ok(!seen.has(keyOf(a)), `duplicate key ${keyOf(a)}`)
        seen.add(keyOf(a))
      }
    })

    test('every article has a title, a summary and a body with real text', () => {
      for (const a of items) {
        assert.ok(a.title.trim().length > 0, `${keyOf(a)}: empty title`)
        assert.ok(a.summary.trim().length > 0, `${keyOf(a)}: empty summary`)
        assert.ok(a.body.length > 0, `${keyOf(a)}: empty body`)
        assert.ok(bodyWords(a) >= 80, `${keyOf(a)}: body is a stub (${bodyWords(a)} words)`)
        for (const b of a.body) {
          if (b.type === 'ul' || b.type === 'ol') assert.ok(b.items.length > 0, `${keyOf(a)}: empty list`)
          if (b.type === 'code') assert.ok(b.code.trim().length > 0, `${keyOf(a)}: empty code block`)
        }
      }
    })

    test('titles are unique so every document.title and breadcrumb is distinct', () => {
      const titles = items.map((a) => a.title)
      assert.equal(new Set(titles).size, titles.length)
    })

    test('no fabricated attribution: bodies never name a person, quote someone, or invent a figure', () => {
      for (const a of items) {
        const text = a.body.map((b) => JSON.stringify(b)).join(' ')
        assert.ok(!/[“”]/.test(text), `${keyOf(a)}: contains a typographic quotation (would read as a quote)`)
        assert.ok(!/\b\d+(?:\.\d+)?\s?%/.test(text), `${keyOf(a)}: contains a percentage statistic`)
        assert.ok(!/\b(?:testimonial|customers say|pastor [A-Z][a-z]+)\b/i.test(text), `${keyOf(a)}: reads like a testimonial`)
      }
    })
  })
}

assertCollection('blog', blogPosts, (a) => a.slug)
assertCollection('docs', docsArticles, (a) => `${(a as KnowledgeArticle).category}/${a.slug}`)
assertCollection('support', supportArticles, (a) => `${(a as KnowledgeArticle).category}/${a.slug}`)

describe('blog collection', () => {
  test('every post has a real category and an ISO date', () => {
    for (const p of blogPosts) {
      assert.ok(p.category.trim().length > 0)
      assert.match(p.published, /^\d{4}-\d{2}-\d{2}$/)
      assert.ok(!Number.isNaN(Date.parse(p.published)), `${p.slug}: unparseable date`)
    }
  })

  test('the author is always the fixed string "SelahCue Team": the data cannot name anyone else', () => {
    // The post type has no author field, so a post cannot carry a name in data...
    for (const p of blogPosts) assert.ok(!('author' in p) && !('authors' in p) && !('byline' in p), `${p.slug} carries an author field`)
    // ...and the one place an author is rendered is hard-wired to the team, byline and card.
    const view = readFileSync(MARKETING_SRC + 'views/BlogPostView.vue', 'utf8')
    assert.match(view, /<p class="bp-byline">\s*SelahCue Team\b/)
    assert.match(view, /<p class="bp-author-name">SelahCue Team<\/p>/)
    assert.equal((view.match(/class="bp-byline"/g) ?? []).length, 1)
  })

  test('at most one post is featured, and the featured post exists', () => {
    assert.ok(blogPosts.filter((p) => p.featured).length <= 1)
    assert.equal(featuredPost, blogPosts.find((p) => p.featured))
  })

  test('lookup, prev/next and related never point at the post itself or at nothing', () => {
    for (const p of blogPosts) {
      assert.equal(findBlogPost(p.slug), p)
      const rel = relatedPosts(p)
      assert.ok(rel.length >= 1 && rel.length <= 3)
      assert.ok(!rel.includes(p))
      const { prev, next } = blogNeighbours(p)
      for (const n of [prev, next]) if (n) assert.ok(blogPosts.some((q) => blogPath(q.slug) === n.to))
    }
    assert.equal(blogNeighbours(blogPosts[0] as BlogPost).prev, null)
    assert.equal(blogNeighbours(blogPosts[blogPosts.length - 1] as BlogPost).next, null)
  })

  test('lookup is exact: unknown, empty, array and non-string slugs find nothing', () => {
    for (const bad of ['', 'nope', 'Offline-First', ' ', ['a'], undefined, null, 42]) {
      assert.equal(findBlogPost(bad), undefined, String(bad))
    }
  })
})

for (const [label, c, articles, categories, pathOf, find] of [
  ['docs', docs, docsArticles, docsCategories, docsPath, findDocsArticle],
  ['support', support, supportArticles, supportCategories, supportPath, findSupportArticle],
] as const) {
  describe(`${label} collection`, () => {
    test('category ids are URL-safe and unique, and each has a title, description and articles', () => {
      const ids = categories.map((x) => x.id)
      assert.equal(new Set(ids).size, ids.length)
      for (const cat of categories) {
        assert.match(cat.id, SLUG_PATTERN)
        assert.ok(cat.title.trim() && cat.desc.trim() && cat.icon.trim())
        assert.ok(articles.some((a) => a.category === cat.id), `${label}: category ${cat.id} has no articles`)
      }
    })

    test('every article belongs to a declared category (none is orphaned from the index)', () => {
      for (const a of articles) assert.ok(categories.some((x) => x.id === a.category), `${a.slug}: unknown category ${a.category}`)
    })

    test('slugs are unique within a category and resolve at /<root>/<category>/<slug>', () => {
      for (const a of articles) {
        assert.equal(find(a.category, a.slug), a)
        assert.equal(pathOf(a), `${c.root}/${a.category}/${a.slug}`)
        assert.equal(pathOf(a), articlePath(c.root, a))
      }
    })

    test('lookup needs BOTH category and slug to match', () => {
      const a = articles[0] as KnowledgeArticle
      assert.equal(find('not-a-category', a.slug), undefined)
      assert.equal(find(a.category, 'not-a-slug'), undefined)
      assert.equal(find(a.category, ''), undefined)
      assert.equal(find(['x'], undefined), undefined)
    })

    test('reading order covers every article exactly once', () => {
      const order = readingOrder(c)
      assert.equal(order.length, articles.length)
      assert.equal(new Set(order).size, articles.length)
    })
  })
}

describe('docs prev/next', () => {
  test('first has no previous, last has no next, and the chain is symmetric', () => {
    const order = readingOrder(docs)
    assert.equal(docsNeighbours(order[0] as KnowledgeArticle).prev, null)
    assert.equal(docsNeighbours(order[order.length - 1] as KnowledgeArticle).next, null)
    for (let i = 0; i < order.length - 1; i++) {
      const a = order[i] as KnowledgeArticle
      const b = order[i + 1] as KnowledgeArticle
      assert.equal(docsNeighbours(a).next?.to, docsPath(b))
      assert.equal(docsNeighbours(b).prev?.to, docsPath(a))
    }
  })
})

describe('index pages are generated from the content source', () => {
  // A card typed by hand beside the data is exactly how the old index drifted from reality
  // (counts of articles that did not exist, "popular" links that went nowhere). The index
  // views must read the collections, and must not carry their own copy of article titles.
  const read = (rel: string): string => readFileSync(MARKETING_SRC + rel, 'utf8')

  test('BlogView reads blogPosts and links each card to its post', () => {
    const src = read('views/BlogView.vue')
    assert.match(src, /lib\/content\/blog\.ts/)
    assert.match(src, /blogPath\(/)
    for (const p of blogPosts) assert.ok(!src.includes(p.title), `BlogView hard-codes the title of ${p.slug}`)
  })

  test('DocsView reads the docs collection and links each entry to its article', () => {
    const src = read('views/DocsView.vue')
    assert.match(src, /lib\/content\/docs\.ts/)
    assert.match(src, /docsPath\(/)
    for (const a of docsArticles) assert.ok(!src.includes(a.title), `DocsView hard-codes the title of ${a.slug}`)
  })

  test('SupportView reads the support collection and links each entry to its article', () => {
    const src = read('views/SupportView.vue')
    assert.match(src, /lib\/content\/support\.ts/)
    assert.match(src, /supportPath\(/)
    for (const a of supportArticles) assert.ok(!src.includes(a.title), `SupportView hard-codes the title of ${a.slug}`)
  })
})

describe('the citation trail (test-only data, never in src/)', () => {
  const allKeys = [
    ...blogPosts.map((a) => `blog/${a.slug}`),
    ...docsArticles.map((a) => `docs/${a.category}/${a.slug}`),
    ...supportArticles.map((a) => `support/${a.category}/${a.slug}`),
  ]

  test('the tracked-file check is not vacuous: it rejects what existsSync would accept', () => {
    assert.ok(isTrackedRegularFile('implementation/marketing/package.json'), 'a real tracked file must pass')
    assert.ok(!isTrackedRegularFile('implementation/marketing/src'), 'a directory is not a citation')
    assert.ok(existsSync(REPO_ROOT + 'implementation/marketing/src'), 'control: the directory does exist on disk')
    assert.ok(!isTrackedRegularFile('Implementation/marketing/package.json'), 'wrong case must fail even where the filesystem forgives it')
    assert.ok(!isTrackedRegularFile('implementation/marketing/node_modules/vue/package.json'), 'an untracked/ignored file must fail')
    assert.ok(!isTrackedRegularFile('implementation/marketing/nope.txt'))
  })

  test('every article has an entry, and no entry names a non-article', () => {
    assert.deepEqual([...Object.keys(SOURCES)].sort(), [...allKeys].sort())
  })

  test('every article cites at least one file, says what it backs, and the file is a tracked regular file', () => {
    for (const key of allKeys) {
      const list = SOURCES[key]
      assert.ok(list && list.length > 0, `${key}: no sources — every claim needs a repo citation`)
      for (const s of list as NonNullable<typeof list>) {
        assert.ok(s.supports.trim().length > 0, `${key}: ${s.path} says nothing about what it supports`)
        assert.ok(isTrackedRegularFile(s.path), `${key}: cited source is not a git-tracked regular file: ${s.path}`)
      }
    }
  })
})

describe('the live-control article tells the whole truth about the emergency controls', () => {
  const live = findDocsArticle('getting-started', 'preview-live-and-go-live')
  const text = (live?.body ?? []).map((b) => JSON.stringify(b)).join(' ')
  const op = readFileSync(REPO_ROOT + 'implementation/desktop/crates/selahcue-operator/dist/app.js', 'utf8')

  test('the article exists (positive control)', () => {
    assert.ok(live)
  })

  test('its "Emergency controls" section lists both chords and the footer buttons', () => {
    const body = live?.body ?? []
    const at = body.findIndex((b) => b.type === 'h3' && /Emergency controls/.test(b.text))
    assert.ok(at >= 0, 'the Emergency controls heading is missing')
    const list = body[at + 1]
    assert.equal(list?.type, 'ul', 'the heading must be followed by the list')
    const items = list && list.type === 'ul' ? list.items.join('\n') : ''
    assert.match(items, /Ctrl\]\]\+\[\[Shift\]\]\+\[\[B\]\]/, 'blackout chord missing')
    assert.match(items, /Ctrl\]\]\+\[\[Shift\]\]\+\[\[\.\]\]/, 'clear-all chord missing')
    assert.match(items, /\*\*Blackout\*\* and \*\*Clear Output\*\* buttons/, 'footer buttons missing')
  })

  test('it never says the single keys cannot blackout the show', () => {
    assert.ok(!/can never[^"]*blackout the show|cannot[^"]*blackout the show/i.test(text))
  })

  test('the claim is true: the chords are handled BEFORE the Live-Console-only guard in app.js', () => {
    const chordB = op.indexOf('e.code === "KeyB"')
    const chordDot = op.indexOf('e.code === "Period"')
    assert.ok(chordB > 0 && chordDot > 0, 'could not find the chord handlers in app.js')
    // From the start of THAT keydown handler to the chord, nothing may gate on the active surface.
    const handlerStart = op.lastIndexOf('"keydown",', chordB)
    const before = op.slice(handlerStart, Math.max(chordB, chordDot))
    assert.ok(handlerStart > 0)
    assert.ok(!/surface-console|classList\.contains\("active"\)/.test(before), 'a surface guard now runs before the chords; the article is wrong')
    const guard = op.indexOf('getElementById("surface-console").classList.contains("active")', chordB)
    assert.ok(guard > Math.max(chordB, chordDot), 'the single-key guard must come AFTER the chords')
    const footer = readFileSync(REPO_ROOT + 'implementation/desktop/crates/selahcue-operator/dist/index.html', 'utf8')
    assert.ok(footer.indexOf('<footer id="emergency"') > footer.indexOf('</main>'), 'the emergency footer is no longer outside the per-surface <main>')
  })
})

describe('related links', () => {
  test('relatedIn never offers the article itself, stays in its category, and respects the limit', () => {
    for (const a of supportArticles) {
      const rel = relatedIn(support, a)
      assert.ok(!rel.includes(a), `${a.slug} lists itself as related`)
      assert.ok(rel.every((r) => r.category === a.category))
      assert.ok(rel.length <= 3)
    }
    // Control: a category with company has related links at all.
    assert.ok(relatedIn(support, supportArticles.find((a) => a.category === 'mobile-control')!).length >= 2)
    assert.equal(relatedIn(support, supportArticles[0]!, 0).length, 0)
  })
})
