<script setup lang="ts">
/**
 * Support article detail — handoff §9c. Route `/support/:category/:slug`.
 *
 * Single column, 720px, prose styled like docs (shared `ArticleBody`), ending in a
 * "Still stuck?" call to action that goes to the contact form.
 */
import { computed, ref } from 'vue'
import UiButton from '@/components/UiButton.vue'
import ArticleBody from '@/components/article/ArticleBody.vue'
import BreadcrumbTrail from '@/components/article/BreadcrumbTrail.vue'
import PrevNext from '@/components/article/PrevNext.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import {
  findSupportArticle,
  findSupportCategory,
  supportNeighbours,
  supportPath,
  supportRelated,
} from '@/lib/content/support.ts'
import { readMinutes } from '@/lib/content/text.ts'
import { useDocumentMeta } from '@/lib/useDocumentMeta.ts'
import { useFocusHeading } from '@/lib/useFocusHeading.ts'

const props = defineProps<{ category: string; slug: string }>()

const article = computed(() => findSupportArticle(props.category, props.slug))
const category = computed(() => findSupportCategory(props.category))
const neighbours = computed(() => (article.value ? supportNeighbours(article.value) : { prev: null, next: null }))
const related = computed(() => (article.value ? supportRelated(article.value) : []))
const minutes = computed(() => (article.value ? readMinutes(article.value.body) : 0))

// An unknown slug owns no title: the site defaults show (and the not-found page renders).
useDocumentMeta(
  () => (article.value && category.value ? `${article.value.title} — Support` : ''),
  () => article.value?.summary ?? '',
)

const heading = ref<HTMLElement | null>(null)
useFocusHeading(heading, () => `${props.category}/${props.slug}`)
</script>

<template>
  <NotFoundView embedded v-if="!article || !category" />
  <article v-else class="sa">
    <div class="sa-wrap">
      <BreadcrumbTrail
        :items="[
          { label: 'Support', to: '/support' },
          { label: category.title, to: '/support#' + category.id },
          { label: article.title },
        ]"
      />
      <header class="sa-header">
        <h1 ref="heading" tabindex="-1" class="sa-title">{{ article.title }}</h1>
        <p class="sa-lead">{{ article.summary }}</p>
        <p class="sa-meta">{{ category.title }} &middot; {{ minutes }} min read</p>
      </header>

      <ArticleBody :blocks="article.body" copyable-code />

      <section v-if="related.length" class="sa-related" aria-labelledby="sa-related-title">
        <h2 id="sa-related-title" class="sa-h2">More in {{ category.title }}</h2>
        <ul class="sa-related-list">
          <li v-for="r in related" :key="r.slug">
            <router-link class="sa-related-link" :to="supportPath(r)">{{ r.title }}</router-link>
          </li>
        </ul>
      </section>

      <section class="sa-stuck" aria-labelledby="sa-stuck-title">
        <h2 id="sa-stuck-title" class="sa-stuck-title">Still stuck?</h2>
        <p class="sa-stuck-text">
          Tell us what you were doing and what you saw, and our team will help.
        </p>
        <UiButton variant="gradient" size="md" to="/contact">Contact support</UiButton>
      </section>

      <PrevNext :prev="neighbours.prev" :next="neighbours.next" label="More support articles" />
    </div>
  </article>
</template>

<style scoped>
.sa { background: var(--sc-base); padding: 48px 0 96px; }
.sa-wrap { max-width: 720px; margin: 0 auto; padding-inline: var(--gutter); box-sizing: content-box; }
.sa-header { margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid var(--sc-border); }
.sa-title { font-size: 44px; line-height: 1.15; font-weight: 800; color: var(--sc-text); margin: 0 0 14px; overflow-wrap: break-word; }
.sa-title:focus { outline: none; }
.sa-lead { font-size: 19px; line-height: 1.6; color: var(--sc-text-secondary); margin: 0 0 12px; }
.sa-meta { font-size: 14px; color: var(--sc-text-secondary); margin: 0; }

.sa-h2 { font-size: 20px; font-weight: 700; color: var(--sc-text); margin: 0 0 12px; }
.sa-related { margin-top: 48px; }
.sa-related-list { display: flex; flex-direction: column; gap: 8px; }
.sa-related-link {
  display: block;
  padding: 14px 16px;
  min-height: 44px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  color: var(--sc-text);
  font-weight: 600;
  transition: border-color var(--transition-base);
}
.sa-related-link:hover { border-color: var(--sc-primary); }
.sa-related-link:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; }

.sa-stuck {
  margin-top: 48px;
  padding: 32px;
  text-align: center;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
}
.sa-stuck-title { font-size: 24px; font-weight: 700; color: var(--sc-text); margin: 0 0 8px; }
.sa-stuck-text { font-size: 15px; color: var(--sc-text-secondary); margin: 0 0 20px; }

@media (max-width: 1199px) {
  .sa-title { font-size: 40px; }
}
@media (max-width: 767px) {
  .sa { padding: 24px 0 64px; }
  .sa-title { font-size: 30px; }
  .sa-lead { font-size: 17px; }
  .sa-stuck { padding: 24px 20px; }
}
</style>
