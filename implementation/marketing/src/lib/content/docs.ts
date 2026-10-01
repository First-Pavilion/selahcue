/**
 * Documentation articles, at `/docs/<category>/<slug>`.
 * See `types.ts` for the honesty rules; every claim is backed by a file in `sources`.
 */
import { articlePath, articlesIn, articleNeighbours, findArticle, findCategory, relatedIn, type KnowledgeCollection } from './knowledge.ts'
import type { KnowledgeArticle, KnowledgeCategory } from './types.ts'

export const docsCategories: readonly KnowledgeCategory[] = []
export const docsArticles: readonly KnowledgeArticle[] = []

export const docs: KnowledgeCollection = { root: '/docs', categories: docsCategories, articles: docsArticles }

export const docsPath = (a: KnowledgeArticle): string => articlePath(docs.root, a)
export const findDocsArticle = (category: unknown, slug: unknown) => findArticle(docs, category, slug)
export const findDocsCategory = (id: unknown) => findCategory(docs, id)
export const docsIn = (categoryId: string) => articlesIn(docs, categoryId)
export const docsNeighbours = (a: KnowledgeArticle) => articleNeighbours(docs, a)
export const docsRelated = (a: KnowledgeArticle) => relatedIn(docs, a)
