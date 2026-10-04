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
 * The frame's icon tile for each category: a feather-style stroke icon (MARKETING-SITE-HANDOFF 7) on
 * a brand, preview, warn or live fill, in the frame's order. The content source carries an emoji;
 * the page draws its own icon instead, and an id with no entry here falls back to the first.
 */
type Shape = readonly [tag: string, attrs: Record<string, string>]
const ICONS: Record<string, readonly Shape[]> = {
  'getting-started': [['polygon', { points: '13 2 3 14 12 14 11 22 21 10 12 10 13 2' }]],
  'display-outputs': [
    ['rect', { x: '2', y: '3', width: '20', height: '14', rx: '2', ry: '2' }],
    ['line', { x1: '8', y1: '21', x2: '16', y2: '21' }],
    ['line', { x1: '12', y1: '17', x2: '12', y2: '21' }]
  ],
  'scripture-bibles': [
    ['path', { d: 'M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z' }],
    ['path', { d: 'M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z' }]
  ],
  'timers-clocks': [
    ['circle', { cx: '12', cy: '12', r: '10' }],
    ['polyline', { points: '12 6 12 12 16 14' }]
  ],
  'mobile-control': [
    ['rect', { x: '5', y: '2', width: '14', height: '20', rx: '2', ry: '2' }],
    ['line', { x1: '12', y1: '18', x2: '12.01', y2: '18' }]
  ],
  troubleshooting: [
    ['circle', { cx: '12', cy: '12', r: '10' }],
    ['line', { x1: '12', y1: '8', x2: '12', y2: '12' }],
    ['line', { x1: '12', y1: '16', x2: '12.01', y2: '16' }]
  ]
}
const TONES = ['is-brand', 'is-preview', 'is-warn', 'is-brand', 'is-preview', 'is-live']
const iconFor = (id: string): readonly Shape[] => ICONS[id] ?? ICONS['getting-started'] ?? []
const toneFor = (index: number): string => TONES[index % TONES.length] ?? 'is-brand'

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
    <section class="support-hero container">
      <UiBadge variant="featured">HELP CENTER</UiBadge>
      <h1 class="hero-title">How can we help?</h1>
      <p class="hero-sub">Guides, answers and troubleshooting for running SelahCue on Sunday.</p>

      <div class="search-box" role="search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="search-icon" aria-hidden="true">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          v-model="searchQuery"
          type="search"
          class="search-input"
          aria-label="Search help articles"
          placeholder="Search help articles…"
        />
        <p class="sr-only" role="status" aria-live="polite">{{ statusText }}</p>
      </div>
    </section>

    <!-- Search results replace the browse sections while a query is typed. -->
    <section v-if="results" class="articles-band" aria-labelledby="results-heading">
      <div class="container band-inner">
        <h2 id="results-heading" class="band-title">Search results</h2>
        <p class="results-status" aria-hidden="true">{{ statusText }}</p>
        <ul v-if="results.length" class="articles-panel">
          <li v-for="art in results" :key="art.category + '/' + art.slug">
            <router-link class="article-row" :to="supportPath(art)">
              <span class="row-title">{{ art.title }}</span>
              <span class="row-meta">{{ categoryTitle(art.category) }} &middot; {{ readMinutes(art.body) }} min read</span>
              <svg class="row-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6" /></svg>
            </router-link>
          </li>
        </ul>
      </div>
    </section>

    <template v-else>
      <!-- Categories Grid -->
      <section class="categories-section container">
        <div class="categories-grid">
          <div v-for="(cat, index) in supportCategories" :id="cat.id" :key="cat.id" class="category-card">
            <div :class="['cat-icon', toneFor(index)]" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <component :is="shape[0]" v-for="(shape, si) in iconFor(cat.id)" :key="si" v-bind="shape[1]" />
              </svg>
            </div>
            <h2 class="cat-title">{{ cat.title }}</h2>
            <p class="cat-desc">{{ cat.desc }}</p>
            <ul class="cat-articles">
              <li v-for="a in supportIn(cat.id)" :key="a.slug">
                <router-link class="cat-article-link" :to="supportPath(a)">{{ a.title }}</router-link>
              </li>
            </ul>
            <span class="cat-count">{{ supportIn(cat.id).length }} {{ supportIn(cat.id).length === 1 ? 'article' : 'articles' }}</span>
          </div>
        </div>
      </section>

      <!-- Start here: the frame's "Popular articles" band. The heading says what it is (a curated
           list, not a popularity claim: support-06 is the owner's call). -->
      <section v-if="startHere.length" class="articles-band" aria-labelledby="start-heading">
        <div class="container band-inner">
          <h2 id="start-heading" class="band-title">Start here</h2>
          <ul class="articles-panel">
            <li v-for="art in startHere" :key="art.category + '/' + art.slug">
              <router-link class="article-row" :to="supportPath(art)">
                <span class="row-title">{{ art.title }}</span>
                <span class="row-meta">{{ categoryTitle(art.category) }} &middot; {{ readMinutes(art.body) }} min read</span>
                <svg class="row-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6" /></svg>
              </router-link>
            </li>
          </ul>
        </div>
      </section>
    </template>

    <!-- Contact Support CTA -->
    <section class="help-cta">
      <div class="container">
        <div class="cta-box">
          <h2>Still need help?</h2>
          <p>Our support team is available to assist your church with technical questions.</p>
          <UiButton variant="primary" size="md" to="/contact">Contact Support Team</UiButton>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.support-page {
  background: var(--sc-base);
  padding-bottom: 40px;
}

/* HERO (Figma 498:139): padding 96 top / 48 bottom, 22px between the pill, the headline, the subline
   and the search field, all centred, on a flat background (no glow). The headline takes the shared
   page-hero token and is set to the frame's 48/54 from the desktop breakpoint up. */
.support-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 22px;
  padding-top: 96px;
  padding-bottom: 48px;
  text-align: center;
}

.hero-title {
  font: var(--font-h1-page);
  color: var(--sc-text);
}

@media (min-width: 1200px) {
  .hero-title {
    font-size: 48px;
    line-height: 54px;
  }
}

.hero-sub {
  max-width: 620px;
  font-size: 18px;
  line-height: 28px;
  color: var(--sc-text-secondary);
}

/* SEARCH (Figma 498:144): 620 x 52, radius 14, a 1px border, no shadow; a 20px magnifier 18px from the
   edge (a 13px circle at the 2px stroke the frame draws), the text 50px in. */
.search-box {
  position: relative;
  width: 100%;
  max-width: 620px;
}

.search-icon {
  position: absolute;
  left: 18px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  color: var(--sc-text-secondary);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 52px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 14px;
  padding: 0 17px 0 49px;
  font-family: var(--font-family);
  font-size: 15.5px;
  color: var(--sc-text);
  box-sizing: border-box;
}

/* The browser's default grey was 3.9:1; the frame's own placeholder ink is the secondary one. */
.search-input::placeholder {
  color: var(--sc-text-secondary);
  opacity: 1;
}

.search-input:focus {
  border-color: var(--sc-primary);
}

/* A ring, not only a border change: the global focus ring leaves form fields out on purpose. An
   outline, so forced colors keeps it. */
.search-input:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
}

/* CATEGORY CARDS (Figma 498:150): 3 x 2 cards of 400 x 170 on the 1248 container, 24px apart, no heading
   above them. The build's own content layer (a list of the real articles and a count, support-05)
   sits under the description, so a card is taller than the frame's 170. */
.categories-section {
  padding-top: 8px;
  padding-bottom: 48px;
}

.categories-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

.category-card {
  display: flex;
  flex-direction: column;
  gap: 13px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 18px;
  /* Figma pads 26 / 24 from the edge and draws the stroke inside, so one pixel less each side. */
  padding: 25px 23px;
  cursor: default;
}

.cat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 13px;
  color: #fff;
}

.cat-icon svg {
  width: 24px;
  height: 24px;
}

.cat-icon.is-brand { background: var(--sc-primary); }
.cat-icon.is-preview { background: var(--sc-preview); }
.cat-icon.is-warn { background: var(--sc-warn); }
.cat-icon.is-live { background: var(--sc-live); }

.cat-title {
  font-size: 18px;
  font-weight: 600;
  line-height: 22px;
  color: var(--sc-text);
}

.cat-desc {
  font-size: 14.5px;
  line-height: 22px;
  color: var(--sc-text-secondary);
}

/* The article lists and the count are the content layer's; the count takes the secondary ink (the
   brand ink was 3.83:1 on the card, support-10). */
.cat-articles { display: flex; flex-direction: column; gap: 2px; }
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
.cat-article-link:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; border-radius: 3px; }

.cat-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--sc-text-secondary);
}

/* THE ARTICLE BAND (Figma 498:193): full width on the panel surface, padding 40 / 48, 20px between the
   centred heading and the grouped list. The list is ONE panel, 880 wide, the inset fill, a 1px edge
   drawn as an outline (it takes no room, so the panel is five 53px rows, 265 high, as drawn), rows
   separated by hairlines, the whole row one link with a chevron. */
.articles-band {
  background: var(--sc-surface-alt);
}

.band-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding-top: 40px;
  padding-bottom: 48px;
}

.band-title {
  font-size: 26px;
  font-weight: 700;
  line-height: 31px;
  text-align: center;
  color: var(--sc-text);
}

.articles-panel {
  width: 100%;
  max-width: 880px;
  background: var(--sc-inset);
  border-radius: 16px;
  outline: 1px solid var(--sc-border);
  outline-offset: -1px;
  overflow: hidden;
}

.articles-panel li + li .article-row {
  border-top: 1px solid var(--sc-border);
}

.article-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 53px;
  padding: 17px 22px;
  color: var(--sc-text);
  text-decoration: none;
}

.article-row:hover { background: var(--sc-elevated); }
.article-row:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: -2px; }

.row-title {
  flex: 1;
  font-size: 15.5px;
  font-weight: 500;
  line-height: 19px;
}

.row-meta {
  font-size: 13px;
  line-height: 19px;
  color: var(--sc-text-secondary);
}

.row-chevron {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  color: var(--sc-text-secondary);
}

.results-status { font-size: 15px; color: var(--sc-text-secondary); margin: -8px 0 0; }

.help-cta {
  padding: 40px 0;
}

.cta-box {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 40px;
  text-align: center;
}

.cta-box h2 { font-size: 24px; color: var(--sc-text); margin: 0 0 8px 0; }
.cta-box p { font-size: 15px; color: var(--sc-text-secondary); margin: 0 0 24px 0; }

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

@media (max-width: 1199.98px) {
  .categories-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 767.98px) {
  .support-page { padding-bottom: var(--section-pad-sm); }
  .support-hero { padding-top: 56px; padding-bottom: 32px; gap: 16px; }
  .hero-sub { font-size: 16px; line-height: 24px; }
  /* 16px so iOS Safari does not zoom the page on focus. */
  .search-input { font-size: 16px; text-overflow: ellipsis; }
  .categories-section { padding-bottom: 32px; }
  .categories-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .category-card { padding: 21px; }
  .band-inner { padding-top: 32px; padding-bottom: 32px; }
  .article-row { flex-wrap: wrap; padding: 14px 18px; row-gap: 2px; }
  .row-title { flex-basis: calc(100% - 30px); }
  .row-meta { order: 3; flex-basis: 100%; }
  .row-chevron { order: 2; }
  .cta-box { padding: 32px 20px; border-radius: 16px; }
}
</style>
