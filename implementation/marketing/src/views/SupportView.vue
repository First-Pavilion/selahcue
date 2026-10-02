<script setup lang="ts">
import { computed, ref } from 'vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import { searchSupport, supportArticles, supportCategories, supportIn, supportPath } from '@/lib/content/support.ts'
import { readMinutes } from '@/lib/content/text.ts'

const searchQuery = ref('')

// Categories, their article counts and every link come from the local content source, so
// each card and row resolves to a real article (GAP-08). The old hand-typed counts claimed
// articles that did not exist.
const startHere = supportArticles.filter((a) => a.startHere)
const categoryTitle = (id: string): string => supportCategories.find((c) => c.id === id)?.title ?? id

/**
 * Client-side filter over the local articles (`lib/content/search.ts`, tested in node):
 * every word typed must appear in an article's title, summary, topic or keywords. Not a
 * search backend, which is out of scope.
 */
const results = computed(() => searchSupport(searchQuery.value))

/**
 * Read out by screen readers. The element is rendered from the first paint and only its TEXT
 * changes; a live region that is inserted together with its message is often not announced.
 */
const statusText = computed(() => {
  const r = results.value
  if (r === null) return ''
  if (r.length === 0) return 'No help articles match that search.'
  return `${r.length} help ${r.length === 1 ? 'article matches' : 'articles match'} your search.`
})
</script>

<template>
  <div class="support-page">
    <section class="support-hero">
      <div class="container">
        <UiBadge variant="featured">Support &amp; Help Center</UiBadge>
        <h1 class="hero-title">How can we help you today?</h1>
        
        <div class="search-box" role="search">
          <svg viewBox="0 0 20 20" fill="currentColor" class="search-icon" aria-hidden="true">
            <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/>
          </svg>
          <input 
            v-model="searchQuery" 
            type="search" 
            class="search-input" 
            aria-label="Search help articles"
            placeholder="Search help articles (e.g. stage display, pairing, crash recovery)..." 
          />
          <p class="sr-only" role="status" aria-live="polite">{{ statusText }}</p>
        </div>
      </div>
    </section>

    <!-- Search results replace the browse sections while a query is typed. -->
    <section v-if="results" class="articles-section" aria-labelledby="results-heading">
      <div class="container">
        <h2 id="results-heading" class="section-title">Search results</h2>
        <p class="results-status" aria-hidden="true">{{ statusText }}</p>
        <div class="articles-list">
          <div v-for="art in results" :key="art.category + '/' + art.slug" class="article-row">
            <div>
              <h3 class="article-title"><router-link class="article-link" :to="supportPath(art)">{{ art.title }}</router-link></h3>
              <span class="article-meta">{{ categoryTitle(art.category) }} &middot; {{ readMinutes(art.body) }} min read</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <template v-else>
      <!-- Categories Grid -->
      <section class="categories-section">
        <div class="container">
          <h2 class="section-title">Knowledge Base Categories</h2>
          <div class="categories-grid">
            <div v-for="cat in supportCategories" :id="cat.id" :key="cat.id" class="category-card">
              <div class="cat-icon" aria-hidden="true">{{ cat.icon }}</div>
              <h3 class="cat-title">{{ cat.title }}</h3>
              <p class="cat-desc">{{ cat.desc }}</p>
              <ul class="cat-articles">
                <li v-for="a in supportIn(cat.id)" :key="a.slug">
                  <router-link class="cat-article-link" :to="supportPath(a)">{{ a.title }}</router-link>
                </li>
              </ul>
              <span class="cat-count">{{ supportIn(cat.id).length }} {{ supportIn(cat.id).length === 1 ? 'article' : 'articles' }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Start here -->
      <section v-if="startHere.length" class="articles-section" aria-labelledby="start-heading">
        <div class="container">
          <h2 id="start-heading" class="section-title">Start here</h2>
          <div class="articles-list">
            <div v-for="art in startHere" :key="art.category + '/' + art.slug" class="article-row">
              <div>
                <h3 class="article-title">{{ art.title }}</h3>
                <span class="article-meta">{{ categoryTitle(art.category) }} &middot; {{ readMinutes(art.body) }} min read</span>
              </div>
              <UiButton variant="ghost" size="sm" :to="supportPath(art)">Read article<span class="sr-only">: {{ art.title }}</span> →</UiButton>
            </div>
          </div>
        </div>
      </section>
    </template>

    <!-- Contact Support CTA -->
    <section class="help-cta">
      <div class="container cta-box">
        <h3>Still need help?</h3>
        <p>Our support team is available to assist your church with technical questions.</p>
        <UiButton variant="gradient" size="md" to="/contact">Contact Support Team</UiButton>
      </div>
    </section>
  </div>
</template>

<style scoped>
.support-page {
  background: var(--sc-base);
  padding-bottom: 80px;
}

.container {
  max-width: 1140px;
  margin: 0 auto;
  padding: 0 var(--page-gutter);
}

.support-hero {
  padding: 80px 0 60px;
  text-align: center;
  background: radial-gradient(circle at center, rgba(110, 92, 240, 0.12) 0%, transparent 60%);
}

.hero-title {
  font-size: 40px;
  font-weight: 800;
  color: var(--sc-text);
  margin: 16px 0 32px 0;
}

.search-box {
  position: relative;
  max-width: 640px;
  margin: 0 auto;
}

.search-icon {
  position: absolute;
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  color: var(--sc-text-muted);
}

.search-input {
  width: 100%;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 999px;
  padding: 16px 24px 16px 54px;
  font-family: var(--font-family);
  font-size: 16px;
  color: var(--sc-text);
  box-shadow: 0 10px 30px rgba(0,0,0,0.3);
  box-sizing: border-box;
}

.search-input:focus {
  outline: none;
  border-color: var(--sc-primary);
}

.categories-section, .articles-section {
  padding: 50px 0;
}

.section-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--sc-text);
  margin-bottom: 32px;
}

.categories-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

.category-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 28px;
  transition: transform var(--transition-base), border-color var(--transition-base);
  cursor: pointer;
}

.category-card:hover {
  transform: translateY(-4px);
  border-color: var(--sc-primary);
}

.cat-icon { font-size: 32px; margin-bottom: 12px; }

.cat-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--sc-text);
  margin: 0 0 8px 0;
}

.cat-desc {
  font-size: 14px;
  color: var(--sc-text-secondary);
  line-height: 1.5;
  margin: 0 0 16px 0;
}

.cat-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--sc-primary);
}

.articles-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.article-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  padding: 20px 24px;
}

.article-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--sc-text);
  margin: 0 0 4px 0;
}

.article-meta {
  font-size: 13px;
  color: var(--sc-text-muted);
}

.help-cta {
  padding: 40px 0;
}

.cta-box {
  /* Also `.container`; this element's own padding replaces the container gutter, so the
     gutter is taken as margin (a no-op once the viewport is wider than the max-width). */
  width: min(1140px, 100% - 2 * var(--page-gutter));
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 40px;
  text-align: center;
}

.cta-box h3 { font-size: 24px; color: var(--sc-text); margin: 0 0 8px 0; }
.cta-box p { font-size: 15px; color: var(--sc-text-secondary); margin: 0 0 24px 0; }

@media (max-width: 1199.98px) {
  .categories-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 767.98px) {
  .support-page { padding-bottom: var(--section-pad-sm); }
  .support-hero { padding: 48px 0 36px; }
  .hero-title { font-size: 36px; line-height: 40px; margin-bottom: 24px; }
  .search-input { padding: 14px 16px 14px 48px; font-size: 16px; text-overflow: ellipsis; }
  .search-icon { left: 16px; }
  .categories-section, .articles-section { padding: 32px 0; }
  .categories-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .category-card { padding: 22px; }
  .article-row { flex-direction: column; align-items: flex-start; gap: 12px; padding: 18px 20px; }
  .cta-box { padding: 32px 20px; border-radius: 16px; }
}
</style>

<style scoped>
/* GAP-08: category cards list their articles; rows are real links. Own block so it does
   not sit inside the rules the responsive pass is editing above. */
.category-card { cursor: default; }
.category-card:hover { transform: none; }
.cat-articles { display: flex; flex-direction: column; gap: 2px; margin: 0 0 16px; }
.cat-article-link {
  display: block;
  padding: 8px 0;
  min-height: 44px;
  font-size: 14px;
  line-height: 1.4;
  color: var(--sc-text);
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-color: var(--sc-border-strong);
}
.cat-article-link:hover { color: var(--sc-primary-hover); text-decoration-color: currentColor; }
.cat-article-link:focus-visible, .article-link:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; border-radius: 3px; }
.article-link { color: inherit; }
.article-link:hover { color: var(--sc-primary-hover); text-decoration: underline; }
.results-status { font-size: 15px; color: var(--sc-text-secondary); margin: -16px 0 20px; }
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
