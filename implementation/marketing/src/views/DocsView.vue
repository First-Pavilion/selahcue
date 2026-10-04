<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import CategoryIcon from '@/components/article/CategoryIcon.vue'
import { docsArticles, docsCategories, docsIn, docsPath } from '@/lib/content/docs.ts'
import { readMinutes } from '@/lib/content/text.ts'

// The topics and every article link below come from the local content source, so each
// entry resolves to a real article (GAP-08). Category sections carry the id the article
// breadcrumbs link to (`/docs#<category>`).

const route = useRoute()

/**
 * The sidebar groups (Figma 499:145: GETTING STARTED, GUIDES, REFERENCE). The frame names topics the
 * content layer does not have (Installation, Keyboard shortcuts: docs-06), so the groups are filled
 * with the REAL categories: the first goes under GETTING STARTED, Troubleshooting under REFERENCE and
 * everything else under GUIDES. A category added later lands in GUIDES without an edit here.
 */
const groups = computed(() => {
  const first = docsCategories[0]?.id
  const reference = 'troubleshooting'
  return [
    { label: 'GETTING STARTED', items: docsCategories.filter((c) => c.id === first) },
    { label: 'GUIDES', items: docsCategories.filter((c) => c.id !== first && c.id !== reference) },
    { label: 'REFERENCE', items: docsCategories.filter((c) => c.id === reference && c.id !== first) }
  ].filter((g) => g.items.length > 0)
})

/** The one current item: the category in the URL hash, else the first (the page opens on it). */
const activeId = computed(() => {
  const hash = route.hash.replace(/^#/, '')
  return docsCategories.some((c) => c.id === hash) ? hash : (docsCategories[0]?.id ?? '')
})

/** The tile fills, in the order the Support cards use: brand, preview, warn, brand, preview, live. */
const TONES = ['brand', 'preview', 'warn', 'brand', 'preview', 'live'] as const
const toneFor = (index: number) => TONES[index % TONES.length] ?? 'brand'

/** The callout's destination: the first article the content layer flags as a place to start. */
const startArticle = docsArticles.find((a) => a.startHere) ?? docsArticles[0]
</script>

<template>
  <div class="docs-page">
    <section class="docs-hero container">
      <UiBadge variant="featured">DOCS</UiBadge>
      <h1 class="hero-title">Documentation</h1>
      <p class="hero-sub">How-to guides for running SelahCue, written from what the app actually does.</p>
    </section>

    <div class="container docs-split">
      <div class="docs-layout">
        <!-- Left Sidebar Navigation -->
        <aside class="docs-sidebar">
          <nav class="sidebar-nav" aria-label="Documentation topics">
            <div v-for="g in groups" :key="g.label" class="nav-group">
              <p class="group-label">{{ g.label }}</p>
              <ul class="nav-list">
                <li v-for="c in g.items" :key="c.id">
                  <router-link
                    :class="['nav-item', { 'is-active': c.id === activeId }]"
                    :to="{ hash: '#' + c.id }"
                    :aria-current="c.id === activeId ? 'location' : undefined"
                  >
                    {{ c.title }}
                  </router-link>
                </li>
              </ul>
            </div>
          </nav>
        </aside>

        <!-- Right Content Area. The site shell already provides <main>. `docs-content` is the name the global anchor
             rule (`assets/styles/anchors.css`: `.docs-content .topic`) gives the sections their scroll margin by;
             it is a plain column now, not the card it used to be. -->
        <div class="docs-content">
          <section class="docs-intro">
            <h2 class="intro-title">Getting started</h2>
            <p class="intro-text">
              SelahCue is a desktop-authoritative, offline-first church presentation app. These guides cover live control,
              outputs and displays, scripture, timers and service plans, and mobile control.
            </p>

            <div v-if="startArticle" class="start-callout">
              <CategoryIcon name="getting-started" tone="brand" size="lg" class="callout-icon" />
              <div class="callout-body">
                <p class="callout-title">New here? Start with the basics</p>
                <p class="callout-sub">{{ startArticle.title }}</p>
              </div>
              <UiButton class="start-button" variant="primary" size="sm" :to="docsPath(startArticle)">Start guide</UiButton>
            </div>

            <div class="topic-grid">
              <router-link
                v-for="(c, index) in docsCategories"
                :key="c.id"
                class="topic-tile"
                :to="{ hash: '#' + c.id }"
                aria-current-value="false"
              >
                <CategoryIcon :name="c.id" :tone="toneFor(index)" size="md" />
                <div class="tile-body">
                  <h3 class="tile-title">{{ c.title }}</h3>
                  <p class="tile-desc">{{ c.desc }}</p>
                </div>
              </router-link>
            </div>
          </section>

          <section v-for="c in docsCategories" :id="c.id" :key="c.id" class="topic" :aria-labelledby="'topic-' + c.id">
            <h2 :id="'topic-' + c.id" class="topic-title">{{ c.title }}</h2>
            <p class="topic-desc">{{ c.desc }}</p>
            <ul class="topic-list">
              <li v-for="a in docsIn(c.id)" :key="a.slug">
                <router-link class="topic-link" :to="docsPath(a)">
                  <span class="topic-link-title">{{ a.title }}</span>
                  <span class="topic-link-sum">{{ a.summary }}</span>
                  <span class="topic-link-meta">{{ readMinutes(a.body) }} min read</span>
                </router-link>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.docs-page {
  background: var(--sc-base);
}

/* HERO (Figma 499:139): padding 88 top / 36 bottom, 18px between the pill, the headline and the lead,
   all centred. The headline takes the shared page-hero token and is set to the frame's 46/52 from the
   desktop breakpoint up. */
.docs-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  padding-top: 88px;
  padding-bottom: 36px;
  text-align: center;
}

.hero-title {
  font: var(--font-h1-page);
  color: var(--sc-text);
}

@media (min-width: 1200px) {
  .hero-title {
    font-size: 46px;
    line-height: 52px;
  }
}

.hero-sub {
  max-width: 600px;
  font-size: 18px;
  line-height: 28px;
  color: var(--sc-text-secondary);
}

/* THE SPLIT (Figma 499:144): padding 24 top / 64 bottom; a 248px sidebar, a 40px gap, then the content
   column (960 at 1440) on the shared 1248 container. `minmax(0, 1fr)`, not `1fr`: a `1fr` track has an
   automatic minimum of its content's min-content, so an unbroken run inside the article column (a long
   word, a code line) would make the whole track as wide as it and push the page sideways. */
.docs-split {
  padding-top: 24px;
  padding-bottom: 64px;
}

.docs-layout {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  gap: 40px;
  align-items: start;
}

/* SIDEBAR (Figma 499:145): 248 wide, padding 22 / 18 from the edge (the stroke is drawn inside), 18px
   between groups; a group is an 11px/700 label with 0.9px tracking, then 32px rows 9px apart. */
.docs-sidebar {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 21px 17px;
  position: sticky;
  top: calc(var(--nav-height) + 24px);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.nav-group {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.group-label {
  font-size: 11px;
  font-weight: 700;
  line-height: 13px;
  letter-spacing: 0.9px;
  color: var(--sc-text-secondary);
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.nav-item {
  display: block;
  padding: 7px 10px;
  font-family: var(--font-family);
  font-size: 14.5px;
  line-height: 18px;
  color: var(--sc-text);
  text-decoration: none;
  border-radius: 8px;
  transition: background-color var(--transition-fast), color var(--transition-fast);
}

.nav-item:hover {
  background: var(--sc-elevated);
}

/* The current item: the elevated fill, 600, and a brand bar down its edge. The frame inks the label in
   brand blue, which is 3.4:1 on that fill and fails AA at this size; which accessible brand ink replaces
   it is Uma's decision (class D), so the label keeps the primary text colour and the bar carries the
   brand. The bar is a shadow, not a border, so no row moves. */
.nav-item.is-active {
  background: var(--sc-elevated);
  color: var(--sc-text);
  font-weight: 600;
  box-shadow: inset 3px 0 0 var(--sc-primary);
}

.nav-item:focus-visible,
.topic-tile:focus-visible,
.topic-link:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
}

/* CONTENT (Figma 499:172): an h2 of 28/700, the intro, the callout and the topic grid, 22px apart. */
.docs-intro {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.intro-title {
  font-size: 28px;
  font-weight: 700;
  line-height: 34px;
  color: var(--sc-text);
}

.intro-text {
  font-size: 16.5px;
  line-height: 26px;
  color: var(--sc-text-secondary);
}

/* The callout (Figma 499:175): 84 high, the elevated fill, a 1px border, radius 16, padding 20 / 22
   from the edge, a 44px brand tile, the text, and a 41px button at the right. */
.start-callout {
  display: flex;
  align-items: center;
  gap: 18px;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 19px 21px;
}

.start-callout :deep(.cat-icon) {
  width: 44px;
  height: 44px;
  border-radius: 11px;
}

.callout-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.callout-title {
  font-size: 16.5px;
  font-weight: 600;
  line-height: 20px;
  color: var(--sc-text);
}

.callout-sub {
  font-size: 14px;
  line-height: 17px;
  color: var(--sc-text-secondary);
}

.start-button {
  flex-shrink: 0;
}

/* The topic grid (Figma 499:184): two columns, 18px apart, tiles 83 high with a 40px tile, 14px gap,
   padding 20 from the edge. */
.topic-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.topic-tile {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 83px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 19px;
  text-decoration: none;
  transition: border-color var(--transition-base);
}

.topic-tile:hover { border-color: var(--sc-primary); }

.tile-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.tile-title {
  font-size: 16px;
  font-weight: 600;
  line-height: 19px;
  color: var(--sc-text);
}

.tile-desc {
  font-size: 13.5px;
  line-height: 20px;
  color: var(--sc-text-secondary);
}

/* GAP-08: the index lists real articles (the content layer, docs-05: not in the frame, so it follows
   the hub). The sections the sidebar and the tiles link to. */
.topic { margin-top: 48px; }
.topic-title { font-size: 22px; font-weight: 700; color: var(--sc-text); margin: 0 0 6px; }
.topic-desc { font-size: 15px; color: var(--sc-text-secondary); margin: 0 0 16px; }
.topic-list { display: flex; flex-direction: column; gap: 10px; }
.topic-link {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 18px;
  min-height: 44px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  text-decoration: none;
  transition: border-color var(--transition-base);
}
.topic-link:hover { border-color: var(--sc-primary); }
.topic-link-title { font-size: 16px; font-weight: 600; color: var(--sc-text); }
.topic-link-sum { font-size: 14px; line-height: 1.55; color: var(--sc-text-secondary); }
.topic-link-meta { font-size: 13px; color: var(--sc-text-secondary); }

/* Below 1024 the sidebar no longer fits beside the article: it becomes a swipeable row of topic chips
   above it (still the same links, so keyboard and AT behaviour is unchanged). The group labels go; the
   chips keep their order. */
@media (max-width: 1023.98px) {
  .docs-layout { grid-template-columns: minmax(0, 1fr); gap: 24px; }
  .docs-sidebar { position: static; padding: 14px 16px; border-radius: 14px; }
  .sidebar-nav {
    flex-direction: row;
    gap: 6px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    margin: 0 -4px;
    padding: 0 4px 2px;
  }
  .sidebar-nav::-webkit-scrollbar { display: none; }
  .nav-group { flex-direction: row; gap: 6px; }
  .group-label { display: none; }
  .nav-list { flex-direction: row; gap: 6px; }
  .nav-item { flex: 0 0 auto; white-space: nowrap; min-height: 44px; display: inline-flex; align-items: center; }
}

@media (max-width: 767.98px) {
  .docs-hero { padding-top: 56px; padding-bottom: 24px; gap: 14px; }
  .hero-sub { font-size: 16px; line-height: 24px; }
  .docs-split { padding-top: 16px; padding-bottom: var(--section-pad-sm); }
  .intro-title { font-size: 24px; line-height: 30px; }
  .start-callout { flex-wrap: wrap; }
  .callout-body { flex-basis: calc(100% - 62px); }
  .start-button { width: 100%; }
  .topic-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
