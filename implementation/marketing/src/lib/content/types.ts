/**
 * The shape of the local article content that backs the blog, docs and support detail
 * pages (GAP-08, handoff §9). There is no CMS and no API: articles are typed data that
 * ships in the bundle, so a typo in a slug or an empty body is a compile or test error,
 * not a blank page in production.
 *
 * HONESTY RULES (ClickUp 17tnw2b0q9h). Every article:
 *   - is authored by "SelahCue Team" — never a named person;
 *   - carries no invented quotes, statistics, customers, benchmarks or dates;
 *   - lists, in `sources`, the repository file that backs each product claim it makes.
 *     `tests/content.test.ts` checks every listed path exists, so a citation cannot rot
 *     quietly when a file moves.
 */

/** A repo file that supports a claim in the article. Paths are relative to the repo root. */
export interface ArticleSource {
  readonly path: string
  /** The claim(s) in the article that this file backs, in one line. Audit trail only. */
  readonly supports: string
}

export type CalloutVariant = 'tip' | 'warning' | 'info'

/**
 * A block of article body. Deliberately small: the renderer (`ArticleBody.vue`) maps each
 * one to a semantic element and never uses `v-html`, so content can never inject markup.
 *
 * Inline markup inside any `text`/`items` string is parsed by `inline.ts`:
 * `**bold**`, `` `code` ``, `[[Key]]` for a keyboard key, and `[label](/path)` for links.
 */
export type Block =
  | { readonly type: 'p'; readonly text: string }
  | { readonly type: 'h2'; readonly text: string }
  | { readonly type: 'h3'; readonly text: string }
  | { readonly type: 'ul'; readonly items: readonly string[] }
  | { readonly type: 'ol'; readonly items: readonly string[] }
  | {
      readonly type: 'callout'
      readonly variant: CalloutVariant
      readonly title: string
      readonly text: string
    }
  | { readonly type: 'code'; readonly label: string; readonly code: string }

interface ArticleBase {
  /** URL-safe, lowercase, hyphenated. Unique within its collection (and category). */
  readonly slug: string
  readonly title: string
  /** One or two sentences, shown on index cards and used as the page's meta description. */
  readonly summary: string
  readonly body: readonly Block[]
  readonly sources: readonly ArticleSource[]
}

export interface BlogPost extends ArticleBase {
  /** Category badge text, e.g. "Product Strategy". */
  readonly category: string
  /** ISO date (YYYY-MM-DD): the day the article was written, not a marketing date. */
  readonly published: string
  /** At most one post is featured on the blog index. */
  readonly featured?: boolean
}

export interface KnowledgeCategory {
  readonly id: string
  readonly title: string
  readonly desc: string
  readonly icon: string
}

export interface KnowledgeArticle extends ArticleBase {
  /** Matches a `KnowledgeCategory.id` in the same collection. */
  readonly category: string
}

/** One step in a breadcrumb trail. The last step is the current page and has no link. */
export interface Crumb {
  readonly label: string
  readonly to?: string
}

/** A previous/next link target. */
export interface Neighbour {
  readonly title: string
  readonly to: string
}
