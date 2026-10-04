<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import CategoryIcon from '@/components/article/CategoryIcon.vue'
import { blogPath, blogPosts, featuredPost } from '@/lib/content/blog.ts'
import { formatDate, readMinutes } from '@/lib/content/text.ts'

// Every card below is generated from the local content source, so each one resolves to a
// real article (GAP-08). The featured post is shown in its own panel, not repeated in the grid.
const posts = blogPosts.filter((p) => p !== featuredPost)

type Tone = 'brand' | 'preview' | 'warn' | 'live'

/**
 * How each real category looks: the thumbnail's icon and tile colour. The pill takes the matching UiBadge
 * variant in the template (the frame colours every pill by its category: green, brand, amber): a tile on the
 * green `preview` fill gets the `preview` pill, amber gets `warn`, and the brand look gets `accent`, whose ink
 * is the readable text colour until Uma chooses the accessible brand ink (class D). The content source names
 * five categories; a category with no entry here falls back to the brand look.
 */
const LOOK: Record<string, { icon: string; tone: Tone }> = {
  'Product Strategy': { icon: 'shield-check', tone: 'brand' },
  'Worship Tech': { icon: 'monitor', tone: 'preview' },
  Scripture: { icon: 'book-open', tone: 'warn' },
  Mobile: { icon: 'smartphone', tone: 'brand' },
  Livestreaming: { icon: 'radio', tone: 'preview' }
}
const look = (category: string) => LOOK[category] ?? { icon: 'shield-check', tone: 'brand' as Tone }
</script>

<template>
  <div class="blog-page">
    <section class="hero-section container">
      <UiBadge variant="featured">BLOG</UiBadge>
      <h1 class="hero-title">The SelahCue blog</h1>
      <p class="hero-sub">Practical notes on running a confident service — reliability, outputs, and the craft of church tech.</p>
    </section>

    <div class="blog-body container">
      <!-- Featured Post: the card is one link (the title's), stretched over the whole card. -->
      <article v-if="featuredPost" class="featured-card" aria-labelledby="featured-heading">
        <div class="featured-media">
          <CategoryIcon :name="look(featuredPost.category).icon" :tone="look(featuredPost.category).tone" size="xl" />
        </div>
        <div class="featured-body">
          <div class="featured-tags">
            <UiBadge class="featured-category" :variant="look(featuredPost.category).tone === 'preview' ? 'preview' : look(featuredPost.category).tone === 'warn' ? 'warn' : 'accent'" size="sm">{{ featuredPost.category }}</UiBadge>
            <span class="featured-label">Featured</span>
          </div>
          <h2 id="featured-heading" class="featured-title">
            <router-link class="featured-link" :to="blogPath(featuredPost.slug)">{{ featuredPost.title }}</router-link>
          </h2>
          <p class="featured-desc">{{ featuredPost.summary }}</p>
          <p class="featured-meta">SelahCue Team &middot; {{ formatDate(featuredPost.published) }} &middot; {{ readMinutes(featuredPost.body) }} min read</p>
        </div>
      </article>

      <!-- Grid -->
      <div class="blog-grid">
        <article v-for="post in posts" :key="post.slug" class="blog-card">
          <div class="card-media">
            <CategoryIcon :name="look(post.category).icon" :tone="look(post.category).tone" size="thumb" />
          </div>
          <div class="card-body">
            <UiBadge class="card-category" :variant="look(post.category).tone === 'preview' ? 'preview' : look(post.category).tone === 'warn' ? 'warn' : 'accent'" size="sm">{{ post.category }}</UiBadge>
            <h3 class="card-title">{{ post.title }}</h3>
            <p class="card-desc">{{ post.summary }}</p>
            <div class="card-footer">
              <span class="card-meta">SelahCue Team &middot; {{ formatDate(post.published) }} &middot; {{ readMinutes(post.body) }} min</span>
              <router-link class="read-link" :to="blogPath(post.slug)">Read<span class="sr-only">: {{ post.title }}</span> →</router-link>
            </div>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>

<style scoped>
.blog-page { background: var(--sc-base); padding-bottom: 64px; }

/* HERO (Figma 502:139): padding 96 top / 40 bottom, 18px between the pill, the headline and the subline,
   all centred. The headline takes the shared page-hero token and is set to the frame's 48/54 from the
   desktop breakpoint up. */
.hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  padding-top: 96px;
  padding-bottom: 40px;
  text-align: center;
}

.hero-title { font: var(--font-h1-page); color: var(--sc-text); }

@media (min-width: 1200px) {
  .hero-title { font-size: 48px; line-height: 54px; }
}

.hero-sub { max-width: 640px; font-size: 18px; line-height: 28px; color: var(--sc-text-secondary); }

/* THE BODY (Figma 502:144): padding 24 top, 40px between the featured card and the grid. */
.blog-body { display: flex; flex-direction: column; gap: 40px; padding-top: 24px; }

/* FEATURED (Figma 502:145): 1248 x 348, the panel surface, a hairline border, radius 22, padding 24 from
   the edge (the stroke is drawn inside), a 584 x 300 media panel and the text column 32px apart. */
.featured-card {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 584px) minmax(0, 1fr);
  align-items: center;
  gap: 32px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 22px;
  padding: 23px;
}

.featured-media {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
  background: var(--sc-elevated);
  border-radius: 14px;
}

.featured-body { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.featured-tags { display: flex; align-items: center; gap: 8px; }
.featured-category { padding-block: 4px; }
.featured-label { font-size: 12px; font-weight: 500; line-height: 15px; color: var(--sc-text-secondary); }
.featured-title { font-size: 28px; font-weight: 700; line-height: 34px; color: var(--sc-text); }
.featured-link { color: inherit; text-decoration: none; }
/* One link for the whole card, so the title is the only tab stop and the ring is drawn round the card. */
.featured-link::after { content: ''; position: absolute; inset: 0; border-radius: 22px; }
.featured-link:focus-visible { outline: none; }
.featured-link:focus-visible::after { outline: 2px solid var(--sc-primary); outline-offset: 2px; }
.featured-desc { font-size: 16px; line-height: 25px; color: var(--sc-text-secondary); }
.featured-meta { font-size: 13.5px; line-height: 16px; color: var(--sc-text-secondary); }

/* THE GRID (Figma 502:159): three 400px columns, 24px apart; a card is radius 18 with padding 14 / 14 / 20 / 14
   from the edge, a 150px thumbnail panel, then the text 14px below it, inset 6px. */
.blog-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; align-items: start; }

.blog-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 18px;
  padding: 13px 13px 19px;
}

.card-media {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 150px;
  background: var(--sc-elevated);
  border-radius: 14px;
}

.card-body { display: flex; flex-direction: column; align-items: flex-start; gap: 9px; padding-inline: 6px; }
.card-category { padding-block: 4px; }
.card-title { font-size: 17px; font-weight: 600; line-height: 23px; color: var(--sc-text); }
.card-desc { font-size: 14px; line-height: 1.6; color: var(--sc-text-secondary); }
.card-footer { align-self: stretch; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.card-meta { font-size: 12.5px; line-height: 15px; color: var(--sc-text-secondary); }
.read-link { background: none; border: none; font-size: 13px; color: var(--sc-primary); font-weight: 600; cursor: pointer; }

@media (max-width: 1199.98px) {
  .blog-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .featured-card { grid-template-columns: minmax(0, 1fr); gap: 24px; }
  .featured-media { height: 240px; }
}

@media (max-width: 767.98px) {
  .blog-page { padding-bottom: var(--section-pad-sm); }
  .hero-section { padding-top: 56px; padding-bottom: 28px; gap: 14px; }
  .hero-sub { font-size: 16px; line-height: 24px; }
  .blog-body { gap: 28px; padding-top: 8px; }
  .blog-grid { grid-template-columns: minmax(0, 1fr); gap: 20px; }
  .featured-card { padding: 15px; border-radius: 18px; }
  .featured-media { height: 180px; }
  .featured-title { font-size: 24px; line-height: 30px; }
  .card-footer { flex-wrap: wrap; gap: 8px; }
  /* 44px tap target for the card's action without changing how it looks at rest. */
  .read-link { min-height: 44px; padding: 0 0 0 12px; display: inline-flex; align-items: center; }
}

/* GAP-08: the cards link to real articles now. */
.read-link { text-decoration: none; }
.read-link:hover { text-decoration: underline; text-underline-offset: 3px; }
.read-link:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 3px; border-radius: 4px; }
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
