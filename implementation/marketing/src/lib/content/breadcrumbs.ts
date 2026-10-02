/**
 * The breadcrumb trails of the three article pages, as functions, so the targets can be
 * resolved in a node test. They used to be object literals inside the view templates, where the
 * `to="..."` literal scan could not see a target built from an expression (`'/docs#' + id`).
 * The last crumb is the current page and has no link.
 *
 * Deliberately free of the article collections (it takes the already-found article), so it
 * adds nothing to the chunk that loads it.
 */
import type { BlogPost, Crumb, KnowledgeArticle, KnowledgeCategory } from './types.ts'

export function blogCrumbs(post: BlogPost): Crumb[] {
  return [{ label: 'Home', to: '/' }, { label: 'Blog', to: '/blog' }, { label: post.title }]
}

export function docsCrumbs(article: KnowledgeArticle, category: KnowledgeCategory): Crumb[] {
  return [{ label: 'Docs', to: '/docs' }, { label: category.title, to: `/docs#${category.id}` }, { label: article.title }]
}

export function supportCrumbs(article: KnowledgeArticle, category: KnowledgeCategory): Crumb[] {
  return [
    { label: 'Support', to: '/support' },
    { label: category.title, to: `/support#${category.id}` },
    { label: article.title },
  ]
}
