/**
 * Blog posts. See `types.ts` for the honesty rules; every claim is backed by a file listed
 * in that post's `sources`.
 */
import { asParam, neighbours } from './lookup.ts'
import type { BlogPost, Neighbour } from './types.ts'

export const blogPosts: readonly BlogPost[] = []

export function blogPath(slug: string): string {
  return `/blog/${slug}`
}

export function findBlogPost(slug: unknown): BlogPost | undefined {
  const wanted = asParam(slug)
  return blogPosts.find((p) => p.slug === wanted)
}

export const featuredPost: BlogPost | undefined = blogPosts.find((p) => p.featured)

export function blogNeighbours(post: BlogPost): { prev: Neighbour | null; next: Neighbour | null } {
  return neighbours(blogPosts, blogPosts.indexOf(post), (p) => ({ title: p.title, to: blogPath(p.slug) }))
}

/** Up to `limit` other posts, same category first, then the rest in index order. */
export function relatedPosts(post: BlogPost, limit = 3): BlogPost[] {
  const others = blogPosts.filter((p) => p !== post)
  const same = others.filter((p) => p.category === post.category)
  const rest = others.filter((p) => p.category !== post.category)
  return [...same, ...rest].slice(0, limit)
}
