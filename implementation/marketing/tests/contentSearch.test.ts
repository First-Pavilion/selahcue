/**
 * The support index search: a pure filter (`lib/content/search.ts`).
 *
 * The placeholder in the search box PROMISES three example queries. The first version of the
 * filter matched title + summary only, and two of the three ("pairing", "crash recovery")
 * returned nothing, as did "blackout". The promise is now read straight out of the view's
 * source and tested, so changing either the placeholder or the corpus cannot break it silently.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test, { describe } from 'node:test'
import { fileURLToPath } from 'node:url'

import { MAX_QUERY_CHARS, MAX_TERMS, normalizeForSearch, queryTerms, searchArticles } from '../src/lib/content/search.ts'
import { searchSupport, supportArticles, supportCategories } from '../src/lib/content/support.ts'

const titles = (q: string): string[] => (searchSupport(q) ?? []).map((a) => a.title)

describe('what counts as a query', () => {
  test('nothing to search for is null, so the page shows its normal sections', () => {
    for (const q of ['', ' ', '   \t\n ']) assert.equal(searchSupport(q), null, JSON.stringify(q))
  })

  test('normalisation ignores case, accents and runs of whitespace', () => {
    assert.equal(normalizeForSearch('  Stage   DISPLAY '), 'stage display')
    assert.equal(normalizeForSearch('Café'), 'cafe')
    assert.deepEqual(queryTerms('  Phone   Pair '), ['phone', 'pair'])
  })
})

describe('every word must match', () => {
  test('two words narrow the result: "phone pair" finds the pairing article, "phone zzz" finds nothing', () => {
    assert.ok(titles('phone pair').includes('My phone will not pair'))
    assert.deepEqual(titles('phone zzzqqq'), [])
    assert.ok(titles('phone').length > titles('phone pair').length - 1)
  })

  test('word order does not matter', () => {
    assert.deepEqual(titles('pair phone'), titles('phone pair'))
  })

  test('matching is case-insensitive', () => {
    for (const q of ['NDI', 'ndi', 'Ndi']) assert.deepEqual(titles(q), titles('ndi'), q)
    assert.ok(titles('ndi').length >= 1)
    assert.deepEqual(titles('MY PHONE WILL NOT PAIR'), titles('my phone will not pair'))
  })

  test('it searches the topic name and the keywords, not just title and summary', () => {
    assert.ok(titles('Mobile Control').length >= 3, 'topic name should match')
    assert.ok(titles('revoke').includes('Remove a paired phone'), 'keyword-only word should match')
    assert.ok(titles('recovery').length >= 1, 'keyword-only word should match')
  })
})

describe('the promise in the search box placeholder', () => {
  const view = readFileSync(fileURLToPath(new URL('../src/views/SupportView.vue', import.meta.url)), 'utf8')
  const placeholder = /placeholder="Search help articles \(e\.g\. ([^)]*)\)/.exec(view)?.[1]
  const examples = (placeholder ?? '').split(',').map((s) => s.trim()).filter(Boolean)

  test('the placeholder offers examples at all (positive control)', () => {
    assert.ok(placeholder, 'could not find the placeholder in SupportView.vue')
    assert.ok(examples.length >= 3, `only ${examples.length} examples`)
  })

  test('every example in it returns at least one article', () => {
    for (const ex of examples) assert.ok((searchSupport(ex) ?? []).length >= 1, `"${ex}" returns nothing`)
  })

  test('so do the other words people reach for first', () => {
    for (const q of ['blackout', 'phone pair', 'pairing', 'crash recovery', 'stage display', 'timer', 'verse', 'ndi']) {
      assert.ok((searchSupport(q) ?? []).length >= 1, `"${q}" returns nothing`)
    }
  })
})

describe('self-retrieval: nothing is unfindable', () => {
  test('every article is found by its own title and by its topic name', () => {
    for (const a of supportArticles) {
      assert.ok(titles(a.title).includes(a.title), `"${a.title}" does not find itself`)
      const topic = supportCategories.find((c) => c.id === a.category)!.title
      assert.ok(titles(topic).includes(a.title), `"${topic}" does not list "${a.title}"`)
    }
  })
})

describe('the query is never a pattern, and work is bounded', () => {
  test('regex metacharacters are plain text: they neither throw nor match everything', () => {
    for (const q of ['(', ')', '[', '[a-z]*', '.*', '(a+)+$', '\\', '**', '??', '++', '^$', '(?:x)']) {
      assert.doesNotThrow(() => searchSupport(q), q)
      assert.deepEqual(searchSupport(q), [], `${q} must not behave like a pattern`)
    }
    // Control: the SAME letters as a plain word still match, so "no matches" above is not a dead filter.
    assert.ok((searchSupport('ndi') ?? []).length >= 1)
  })

  test('catastrophic-backtracking shaped and enormous input returns at once', () => {
    const started = performance.now()
    searchSupport('a'.repeat(100_000) + '!')
    searchSupport('(a+)+'.repeat(20_000))
    searchSupport(Array.from({ length: 50_000 }, () => 'ndi').join(' '))
    assert.ok(performance.now() - started < 500, 'the filter must not scale with the size of hostile input')
  })

  test('the query is clipped to MAX_QUERY_CHARS and MAX_TERMS words', () => {
    assert.equal(queryTerms('a '.repeat(500)).length, MAX_TERMS)
    assert.ok(queryTerms('x'.repeat(10_000)).join('').length <= MAX_QUERY_CHARS)
  })
})

describe('searchArticles on a small corpus (rules in isolation)', () => {
  const cats = [{ id: 'c', title: 'Alpha Topic', desc: 'd', icon: '*' }]
  const mk = (slug: string, title: string, summary: string, keywords?: string[]) => ({
    slug, title, summary, category: 'c', body: [], ...(keywords ? { keywords } : {}),
  })
  const corpus = [mk('a', 'One', 'red fish'), mk('b', 'Two', 'blue fish', ['secretword']), mk('c', 'Three', 'red bird')]

  test('substring, all-words, keyword, topic and order', () => {
    assert.deepEqual(searchArticles(corpus, cats, 'fish')!.map((a) => a.slug), ['a', 'b'])
    assert.deepEqual(searchArticles(corpus, cats, 'red fish')!.map((a) => a.slug), ['a'])
    assert.deepEqual(searchArticles(corpus, cats, 'secretword')!.map((a) => a.slug), ['b'])
    assert.deepEqual(searchArticles(corpus, cats, 'alpha')!.map((a) => a.slug), ['a', 'b', 'c'])
    assert.deepEqual(searchArticles(corpus, cats, 'fis')!.map((a) => a.slug), ['a', 'b'], 'a word matches as a substring')
  })
})
