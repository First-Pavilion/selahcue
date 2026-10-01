<script setup lang="ts">
/**
 * Documentation article detail — handoff §9b. Route `/docs/:category/:slug`.
 *
 * Two columns: a sticky 280px category tree (left) and the article. Below 1200px the tree
 * folds behind a "Documentation menu" button (aria-expanded) so the article is the first
 * thing on a phone. Breakpoints are §8a's.
 *
 * "Was this helpful?" records nothing — there is no feedback backend yet — so the buttons
 * only acknowledge, and "No" routes to the contact form, which is the one path that
 * actually reaches a person. The thumbs are a placeholder for a real collector, tracked as
 * a follow-up in the PR.
 */
import { computed, nextTick, ref, watch } from 'vue'
import ArticleBody from '@/components/article/ArticleBody.vue'
import BreadcrumbTrail from '@/components/article/BreadcrumbTrail.vue'
import PrevNext from '@/components/article/PrevNext.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import {
  docsCategories,
  docsIn,
  docsNeighbours,
  docsPath,
  findDocsArticle,
  findDocsCategory,
} from '@/lib/content/docs.ts'
import { CONTENT_SOURCE_URL, readMinutes } from '@/lib/content/text.ts'
import { useDocumentMeta } from '@/lib/useDocumentMeta.ts'
import { useFocusHeading } from '@/lib/useFocusHeading.ts'

const props = defineProps<{ category: string; slug: string }>()

const article = computed(() => findDocsArticle(props.category, props.slug))
const category = computed(() => findDocsCategory(props.category))
const neighbours = computed(() => (article.value ? docsNeighbours(article.value) : { prev: null, next: null }))
const minutes = computed(() => (article.value ? readMinutes(article.value.body) : 0))

// An unknown slug owns no title: the site defaults show (and the not-found page renders).
useDocumentMeta(
  () => (article.value && category.value ? `${article.value.title} — Documentation` : ''),
  () => article.value?.summary ?? '',
)

const heading = ref<HTMLElement | null>(null)
useFocusHeading(heading, () => `${props.category}/${props.slug}`)

const content = ref<HTMLElement | null>(null)
function skipToArticle(): void {
  content.value?.focus()
  content.value?.scrollIntoView({ block: 'start' })
}

const menuOpen = ref(false)
const feedback = ref<'' | 'yes'>('')
const thanks = ref<HTMLElement | null>(null)
async function answerYes(): Promise<void> {
  feedback.value = 'yes'
  await nextTick()
  thanks.value?.focus()
}
// A new article is a new question: forget the previous answer and fold the menu.
watch(
  () => `${props.category}/${props.slug}`,
  () => {
    feedback.value = ''
    menuOpen.value = false
  },
)
</script>

<template>
  <NotFoundView embedded v-if="!article || !category" />
  <div v-else class="da">
    <a class="da-skip" href="#docs-article" @click.prevent="skipToArticle">Skip to article</a>
    <div class="da-wrap">
      <aside class="da-side" aria-label="Documentation sidebar">
        <button
          type="button"
          class="da-menu-btn"
          :aria-expanded="menuOpen"
          aria-controls="docs-nav"
          @click="menuOpen = !menuOpen"
        >
          Documentation menu
          <span class="da-chevron" :class="{ 'is-open': menuOpen }" aria-hidden="true"></span>
        </button>
        <nav id="docs-nav" :class="['da-nav', { 'is-open': menuOpen }]" aria-label="Documentation">
          <router-link class="da-all" to="/docs">All documentation</router-link>
          <details
            v-for="c in docsCategories"
            :key="c.id"
            class="da-cat"
            :open="c.id === article.category"
          >
            <summary class="da-cat-title">{{ c.title }}</summary>
            <ul class="da-cat-list">
              <li v-for="a in docsIn(c.id)" :key="a.slug">
                <router-link
                  class="da-link"
                  :to="docsPath(a)"
                  :aria-current="a === article ? 'page' : undefined"
                  >{{ a.title }}</router-link
                >
              </li>
            </ul>
          </details>
        </nav>
      </aside>

      <article id="docs-article" ref="content" tabindex="-1" class="da-content">
        <BreadcrumbTrail
          :items="[
            { label: 'Docs', to: '/docs' },
            { label: category.title, to: '/docs#' + category.id },
            { label: article.title },
          ]"
        />
        <h1 ref="heading" tabindex="-1" class="da-title">{{ article.title }}</h1>
        <p class="da-lead">{{ article.summary }}</p>
        <p class="da-meta">{{ minutes }} min read</p>

        <ArticleBody :blocks="article.body" anchors copyable-code />

        <section class="da-feedback" aria-labelledby="da-feedback-title">
          <h2 id="da-feedback-title" class="da-feedback-title">Was this helpful?</h2>
          <!-- A live region that exists BEFORE its text does (inserting the region together with
               its message is often not announced); focus also moves here after "Yes" so the
               press has a visible and audible result, and the button that was pressed is gone. -->
          <div ref="thanks" class="da-feedback-result" role="status" aria-live="polite" tabindex="-1">
            <template v-if="feedback === 'yes'">Glad it helped.</template>
          </div>
          <div v-if="feedback === ''" class="da-feedback-actions">
            <button type="button" class="da-btn" @click="answerYes">Yes</button>
            <router-link class="da-btn" to="/contact">No, I need help</router-link>
          </div>
          <a class="da-edit" :href="CONTENT_SOURCE_URL" target="_blank" rel="noopener noreferrer"
            >Suggest an edit on GitHub<span class="da-sr"> (opens in a new tab)</span></a
          >
        </section>

        <PrevNext :prev="neighbours.prev" :next="neighbours.next" label="More documentation" />
      </article>
    </div>
  </div>
</template>

<style scoped>
.da { background: var(--sc-base); padding: 40px 0 96px; position: relative; }
.da-wrap {
  max-width: 1280px;
  margin: 0 auto;
  padding-inline: var(--gutter);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* Off-screen until it receives keyboard focus, then pinned under the sticky navbar. */
.da-skip {
  position: fixed;
  left: -9999px;
  top: calc(var(--nav-height, 68px) + 12px);
  z-index: 120;
  padding: 12px 18px;
  background: var(--sc-primary);
  color: #fff;
  border-radius: 8px;
  font-weight: 600;
}
.da-skip:focus { left: 16px; }

/* Sidebar */
.da-side { min-width: 0; }
.da-menu-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 48px;
  padding: 0 16px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  color: var(--sc-text);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.da-menu-btn:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; }
.da-chevron {
  width: 8px;
  height: 8px;
  margin-right: 4px;
  border-right: 2px solid var(--sc-text-secondary);
  border-bottom: 2px solid var(--sc-text-secondary);
  transform: rotate(45deg);
  transition: transform var(--transition-fast);
}
.da-chevron.is-open { transform: rotate(225deg); }
.da-nav {
  display: none;
  margin-top: 8px;
  padding: 16px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
}
.da-nav.is-open { display: block; }
.da-all { display: block; padding: 10px 12px; margin-bottom: 8px; font-size: 14px; font-weight: 600; color: var(--sc-primary-hover); border-radius: 8px; }
.da-all:hover { background: var(--sc-elevated); }
.da-cat { border-top: 1px solid var(--sc-border); padding: 4px 0; }
.da-cat-title {
  cursor: pointer;
  padding: 10px 12px;
  min-height: 44px;
  display: flex;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--sc-text-secondary);
  border-radius: 8px;
}
.da-cat-title:focus-visible, .da-link:focus-visible, .da-all:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; }
.da-cat-list { padding-bottom: 8px; }
.da-link {
  display: block;
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.4;
  color: var(--sc-text-secondary);
  border-radius: 8px;
}
.da-link:hover { background: var(--sc-elevated); color: var(--sc-text); }
.da-link[aria-current='page'] {
  background: var(--sc-accent-soft);
  /* primary-hover on accent-soft is 4.2:1; the body text colour is 14.7:1 */
  color: var(--sc-text);
  font-weight: 600;
  box-shadow: inset 3px 0 0 var(--sc-primary);
}

/* Content */
.da-content {
  min-width: 0;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 40px 48px 48px;
}
.da-content:focus { outline: none; }
.da-title { font-size: 40px; line-height: 1.2; font-weight: 800; color: var(--sc-text); margin: 0 0 12px; overflow-wrap: break-word; }
.da-title:focus { outline: none; }
.da-lead { font-size: 19px; line-height: 1.6; color: var(--sc-text-secondary); margin: 0 0 12px; }
.da-meta { font-size: 14px; color: var(--sc-text-secondary); margin: 0 0 28px; padding-bottom: 24px; border-bottom: 1px solid var(--sc-border); }

/* Feedback */
.da-feedback { margin-top: 56px; padding-top: 24px; border-top: 1px solid var(--sc-border); }
.da-feedback-title { font-size: 16px; font-weight: 600; color: var(--sc-text); margin: 0 0 12px; }
.da-feedback-actions { display: flex; flex-wrap: wrap; gap: 12px; }
.da-feedback-result { color: var(--sc-preview); font-size: 15px; }
.da-feedback-result:focus { outline: none; }
.da-feedback-result:not(:empty) { min-height: 44px; display: flex; align-items: center; }
.da-btn {
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
.da-btn:hover { background: var(--sc-border); }
.da-btn:focus-visible, .da-edit:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; }
.da-edit { display: inline-block; margin-top: 16px; padding: 10px 0; font-size: 14px; color: var(--sc-primary-hover); text-decoration: underline; text-underline-offset: 3px; }
.da-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

/* Tablet: 768 - 1199px — sidebar is the collapsed menu above the article. */
@media (max-width: 1199px) {
  .da-content { padding: 32px 32px 40px; }
  .da-title { font-size: 36px; }
}

/* Mobile: < 768px */
@media (max-width: 767px) {
  .da { padding: 20px 0 64px; }
  .da-content { padding: 24px 20px 32px; border-radius: 16px; }
  .da-title { font-size: 30px; }
  .da-lead { font-size: 17px; }
}

/* Desktop: >= 1200px — permanent two-column layout, sticky tree. */
@media (min-width: 1200px) {
  .da-wrap { grid-template-columns: 280px minmax(0, 1fr); gap: 48px; }
  .da-side { position: sticky; top: 92px; max-height: calc(100vh - 116px); overflow-y: auto; }
  .da-menu-btn { display: none; }
  .da-nav { display: block; margin-top: 0; }
}
</style>
