/**
 * Support (help centre) articles, at `/support/<category>/<slug>`.
 * See `types.ts` for the honesty rules; every claim is backed by a file in `sources`.
 */
import { articlePath, articlesIn, articleNeighbours, findArticle, findCategory, relatedIn, type KnowledgeCollection } from './knowledge.ts'
import type { KnowledgeArticle, KnowledgeCategory } from './types.ts'

export const supportCategories: readonly KnowledgeCategory[] = []
export const supportArticles: readonly KnowledgeArticle[] = []

export const support: KnowledgeCollection = {
  root: '/support',
  categories: supportCategories,
  articles: supportArticles,
}

export const supportPath = (a: KnowledgeArticle): string => articlePath(support.root, a)
export const findSupportArticle = (category: unknown, slug: unknown) => findArticle(support, category, slug)
export const findSupportCategory = (id: unknown) => findCategory(support, id)
export const supportIn = (categoryId: string) => articlesIn(support, categoryId)
export const supportNeighbours = (a: KnowledgeArticle) => articleNeighbours(support, a)
export const supportRelated = (a: KnowledgeArticle) => relatedIn(support, a)
