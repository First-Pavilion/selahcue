/**
 * Generic helpers for a categorised article collection (docs and support share the same
 * shape: categories, each owning articles at `/<root>/<category>/<slug>`).
 */
import { asParam, neighbours } from './lookup.ts'
import type { KnowledgeArticle, KnowledgeCategory, Neighbour } from './types.ts'

export interface KnowledgeCollection {
  readonly root: string
  readonly categories: readonly KnowledgeCategory[]
  readonly articles: readonly KnowledgeArticle[]
}

export function articlePath(root: string, article: KnowledgeArticle): string {
  return `${root}/${article.category}/${article.slug}`
}

export function findArticle(
  collection: KnowledgeCollection,
  category: unknown,
  slug: unknown,
): KnowledgeArticle | undefined {
  const c = asParam(category)
  const s = asParam(slug)
  return collection.articles.find((a) => a.category === c && a.slug === s)
}

export function findCategory(collection: KnowledgeCollection, id: unknown): KnowledgeCategory | undefined {
  const wanted = asParam(id)
  return collection.categories.find((c) => c.id === wanted)
}

export function articlesIn(collection: KnowledgeCollection, categoryId: string): KnowledgeArticle[] {
  return collection.articles.filter((a) => a.category === categoryId)
}

/**
 * Reading order: category order first, then the order articles are listed within it.
 * Prev/next follow this, so "Next" at the end of a category runs into the next one.
 */
export function readingOrder(collection: KnowledgeCollection): KnowledgeArticle[] {
  return collection.categories.flatMap((c) => articlesIn(collection, c.id))
}

export function articleNeighbours(
  collection: KnowledgeCollection,
  article: KnowledgeArticle,
): { prev: Neighbour | null; next: Neighbour | null } {
  const order = readingOrder(collection)
  return neighbours(order, order.indexOf(article), (a) => ({
    title: a.title,
    to: articlePath(collection.root, a),
  }))
}

/** Other articles in the same category (for support's "related" links). */
export function relatedIn(collection: KnowledgeCollection, article: KnowledgeArticle, limit = 3): KnowledgeArticle[] {
  return articlesIn(collection, article.category)
    .filter((a) => a !== article)
    .slice(0, limit)
}
