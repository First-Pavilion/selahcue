<script setup lang="ts">
/**
 * Blog post detail — handoff §9a. Route `/blog/:slug`.
 *
 * Single column, 720px measure. Desktop (>=1200px) adds a right rail with a sticky table
 * of contents and related posts; below that the rail drops under the article and the
 * table of contents is hidden (§9a: "Sidebar (desktop only)"). Breakpoints are §8a's.
 *
 * Not built, deliberately: the spec's 16:9 hero image. There is no real photography or
 * screenshot to put there, and a stock or generated picture presented as the product
 * would be the kind of fabrication this content pass forbids.
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'
import UiBadge from '@/components/UiBadge.vue'
import ArticleBody from '@/components/article/ArticleBody.vue'
import BreadcrumbTrail from '@/components/article/BreadcrumbTrail.vue'
import PrevNext from '@/components/article/PrevNext.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import { blogCrumbs } from '@/lib/content/breadcrumbs.ts'
import { blogNeighbours, blogPath, findBlogPost, relatedPosts } from '@/lib/content/blog.ts'
import { formatDate, readMinutes, tableOfContents } from '@/lib/content/text.ts'
import { useDocumentMeta } from '@/lib/useDocumentMeta.ts'
import { useFocusHeading } from '@/lib/useFocusHeading.ts'

const props = defineProps<{ slug: string }>()

const post = computed(() => findBlogPost(props.slug))
const toc = computed(() => (post.value ? tableOfContents(post.value.body) : []))
const related = computed(() => (post.value ? relatedPosts(post.value) : []))
const neighbours = computed(() => (post.value ? blogNeighbours(post.value) : { prev: null, next: null }))
const minutes = computed(() => (post.value ? readMinutes(post.value.body) : 0))

// An unknown slug owns no title: the site defaults show (and the not-found page renders).
useDocumentMeta(
  () => post.value?.title ?? '',
  () => post.value?.summary ?? '',
)

const heading = ref<HTMLElement | null>(null)
useFocusHeading(heading, () => props.slug)

const route = useRoute()

/** Absolute URL of this post, for sharing. Built from the live origin, never hard-coded. */
const shareUrl = computed(() => (typeof window === 'undefined' ? '' : new URL(route.path, window.location.origin).href))
const xShareHref = computed(() => {
  const q = new URLSearchParams({ text: post.value?.title ?? '', url: shareUrl.value })
  return `https://x.com/intent/post?${q.toString()}`
})

const copyStatus = ref('')
let copyTimer: ReturnType<typeof setTimeout> | undefined
async function copyLink(): Promise<void> {
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    copyStatus.value = 'Link copied'
  } catch {
    copyStatus.value = 'Copy is blocked in this browser. Copy the address from the address bar instead.'
  }
  clearTimeout(copyTimer)
  copyTimer = setTimeout(() => (copyStatus.value = ''), 2500)
}
// A pending timer must not outlive the page that scheduled it.
onBeforeUnmount(() => clearTimeout(copyTimer))
</script>

<template>
  <NotFoundView embedded v-if="!post" />
  <article v-else class="bp">
    <div class="bp-wrap">
      <header class="bp-header">
        <BreadcrumbTrail :items="blogCrumbs(post)" />
        <UiBadge variant="preview">{{ post.category }}</UiBadge>
        <h1 ref="heading" tabindex="-1" class="bp-title">{{ post.title }}</h1>
        <p class="bp-summary">{{ post.summary }}</p>
        <p class="bp-byline">
          SelahCue Team &middot; <time :datetime="post.published">{{ formatDate(post.published) }}</time> &middot;
          {{ minutes }} min read
        </p>
      </header>

      <div class="bp-main">
        <ArticleBody :blocks="post.body" />

        <aside class="bp-author" aria-label="About the author">
          <span class="bp-avatar" aria-hidden="true">S</span>
          <div>
            <p class="bp-author-name">SelahCue Team</p>
            <p class="bp-author-note">
              Written by the people building SelahCue. Questions or corrections?
              <router-link class="bp-link" to="/contact">Get in touch</router-link>.
            </p>
          </div>
        </aside>

        <section class="bp-share" aria-labelledby="bp-share-title">
          <h2 id="bp-share-title" class="bp-share-title">Share this article</h2>
          <div class="bp-share-actions">
            <button type="button" class="bp-btn" @click="copyLink">Copy link</button>
            <a class="bp-btn" :href="xShareHref" target="_blank" rel="noopener noreferrer"
              >Share on X<span class="bp-sr"> (opens in a new tab)</span></a
            >
          </div>
          <p class="bp-share-status" role="status" aria-live="polite">{{ copyStatus }}</p>
        </section>

        <PrevNext :prev="neighbours.prev" :next="neighbours.next" label="More blog posts" />
      </div>

      <aside class="bp-rail" aria-label="Article sidebar">
        <nav v-if="toc.length > 1" class="bp-toc" aria-labelledby="bp-toc-title">
          <h2 id="bp-toc-title" class="bp-rail-title">On this page</h2>
          <ol class="bp-toc-list">
            <li v-for="entry in toc" :key="entry.id">
              <router-link class="bp-toc-link" :to="{ hash: '#' + entry.id }" aria-current-value="false">{{ entry.text }}</router-link>
            </li>
          </ol>
        </nav>

        <section v-if="related.length" class="bp-related" aria-labelledby="bp-related-title">
          <h2 id="bp-related-title" class="bp-rail-title">Related articles</h2>
          <ul class="bp-related-list">
            <li v-for="r in related" :key="r.slug">
              <router-link class="bp-related-card" :to="blogPath(r.slug)">
                <span class="bp-related-cat">{{ r.category }}</span>
                <span class="bp-related-title">{{ r.title }}</span>
              </router-link>
            </li>
          </ul>
        </section>
      </aside>
    </div>
  </article>
</template>

<style scoped>
.bp { background: var(--sc-base); padding: 56px 0 96px; }
.bp-wrap {
  max-width: 1280px;
  margin: 0 auto;
  padding-inline: var(--gutter);
  display: grid;
  grid-template-columns: minmax(0, 720px);
  justify-content: center;
  column-gap: 64px;
}
.bp-header { grid-column: 1; margin-bottom: 40px; }
.bp-main { grid-column: 1; min-width: 0; }
.bp-rail { grid-column: 1; margin-top: 56px; display: flex; flex-direction: column; gap: 32px; }
.bp-toc { display: none; }

.bp-title {
  font: var(--font-h1);
  color: var(--sc-text);
  margin: 16px 0 16px;
  overflow-wrap: break-word;
}
.bp-title:focus { outline: none; }
.bp-summary { font-size: 19px; line-height: 1.6; color: var(--sc-text-secondary); margin: 0 0 20px; }
.bp-byline { font-size: 14px; color: var(--sc-text-secondary); margin: 0; }

.bp-link { color: var(--sc-primary-hover); text-decoration: underline; text-underline-offset: 3px; }
.bp-link:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; border-radius: 3px; }

.bp-author {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  margin-top: 56px;
  padding: 20px 24px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
}
.bp-avatar {
  flex: none;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--sc-accent-soft);
  color: var(--sc-primary-hover);
  font-weight: 700;
}
.bp-author-name { margin: 0 0 4px; font-weight: 600; color: var(--sc-text); }
.bp-author-note { margin: 0; font-size: 14px; line-height: 1.6; color: var(--sc-text-secondary); }

.bp-share { margin-top: 24px; }
.bp-share-title { font-size: 16px; font-weight: 600; color: var(--sc-text); margin: 0 0 12px; }
.bp-share-actions { display: flex; flex-wrap: wrap; gap: 12px; }
.bp-btn {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  padding: 0 18px;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: var(--pill-radius);
  color: var(--sc-text);
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.bp-btn:hover { background: var(--sc-border); }
.bp-btn:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; }
.bp-share-status { margin: 8px 0 0; min-height: 22px; font-size: 13px; color: var(--sc-preview); }
.bp-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.bp-rail-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--sc-text-secondary);
  margin: 0 0 12px;
}
.bp-toc-list { display: flex; flex-direction: column; gap: 2px; }
.bp-toc-link {
  display: block;
  padding: 8px 12px;
  border-left: 2px solid var(--sc-border);
  font-size: 14px;
  line-height: 1.4;
  color: var(--sc-text-secondary);
}
.bp-toc-link:hover { color: var(--sc-text); border-left-color: var(--sc-primary); }
.bp-toc-link:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; }

.bp-related-list { display: grid; gap: 12px; grid-template-columns: 1fr; }
.bp-related-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  min-height: 44px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  transition: border-color var(--transition-base);
}
.bp-related-card:hover { border-color: var(--sc-primary); }
.bp-related-card:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; }
.bp-related-cat { font-size: 12px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--sc-preview); }
.bp-related-title { font-size: 15px; font-weight: 600; line-height: 1.4; color: var(--sc-text); }

/* Tablet: 768 - 1199px (handoff §8a). Related posts go 2-up under the article. */
@media (max-width: 1199.98px) {
  .bp { padding-top: 40px; }
  .bp-related-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

/* Mobile: < 768px. Everything single-column; h1 follows the 36/44 token. */
@media (max-width: 767.98px) {
  .bp { padding: 28px 0 64px; }
  .bp-header { margin-bottom: 28px; }
  .bp-summary { font-size: 17px; }
  .bp-related-list { grid-template-columns: 1fr; }
  .bp-author { margin-top: 40px; padding: 16px; }
}

/* Desktop: >= 1200px. Right rail with a sticky table of contents. */
@media (min-width: 1200px) {
  .bp-wrap { grid-template-columns: minmax(0, 720px) 280px; }
  .bp-rail { grid-column: 2; grid-row: 1 / span 2; margin-top: 0; position: sticky; top: 92px; align-self: start; }
  .bp-toc { display: block; }
  .bp-related-list { grid-template-columns: 1fr; }
}
</style>
