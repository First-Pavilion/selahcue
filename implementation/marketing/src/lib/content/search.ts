/**
 * Client-side filter behind the support index's search box. Pure: no Vue, no DOM.
 *
 * Matching rules, kept deliberately simple so they can be stated in one sentence in the UI:
 * every word you type must appear, as plain text and ignoring case and accents, somewhere
 * in an article's title, summary, topic name or search keywords. There is no ranking.
 *
 * NO REGULAR EXPRESSION IS EVER BUILT FROM THE QUERY. The query is split into words and
 * each word is tested with `String.prototype.includes`, so `(`, `[a-z]*` or `.*` are just
 * characters (and cannot hang the page, which a user-supplied pattern can). Work is also
 * bounded: the query is clipped to MAX_QUERY_CHARS and to MAX_TERMS words.
 */
import type { KnowledgeArticle, KnowledgeCategory } from './types.ts'

export const MAX_QUERY_CHARS = 200
export const MAX_TERMS = 8

/** Lower-case, accent-free, single-spaced. */
export function normalizeForSearch(input: string): string {
  return input
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
}

/** The words of a query, normalised and bounded. Empty array = nothing to search for. */
export function queryTerms(query: string): string[] {
  const clipped = normalizeForSearch(query.slice(0, MAX_QUERY_CHARS))
  return clipped === '' ? [] : clipped.split(' ').slice(0, MAX_TERMS)
}

/**
 * Articles matching every word of `query`, in their listed order, or `null` when the query
 * has no words (so the caller can show its normal, unfiltered page).
 */
export function searchArticles<T extends KnowledgeArticle>(
  articles: readonly T[],
  categories: readonly KnowledgeCategory[],
  query: string,
): T[] | null {
  const terms = queryTerms(query)
  if (terms.length === 0) return null
  return articles.filter((a) => {
    const topic = categories.find((c) => c.id === a.category)?.title ?? ''
    const haystack = normalizeForSearch(`${a.title} ${a.summary} ${topic} ${(a.keywords ?? []).join(' ')}`)
    return terms.every((t) => haystack.includes(t))
  })
}
