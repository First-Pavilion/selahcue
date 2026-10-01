<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import { blogPath, blogPosts, featuredPost } from '@/lib/content/blog.ts'
import { formatDate, readMinutes } from '@/lib/content/text.ts'

// Every card below is generated from the local content source, so each one resolves to a
// real article (GAP-08). The featured post is shown in its own panel, not repeated in the grid.
const posts = blogPosts.filter((p) => p !== featuredPost)
</script>

<template>
  <div class="blog-page">
    <section class="hero-section">
      <div class="container">
        <UiBadge variant="featured">SelahCue Journal</UiBadge>
        <h1 class="hero-title">Insights for Modern Worship &amp; Tech Ministry</h1>
        <p class="hero-sub">Articles, technical guides, and best practices for church presentation teams.</p>
      </div>
    </section>

    <!-- Featured Post -->
    <section v-if="featuredPost" class="featured-section" aria-labelledby="featured-heading">
      <div class="container">
        <div class="featured-card">
          <div class="featured-badge"><UiBadge variant="live">Featured Article</UiBadge></div>
          <h2 id="featured-heading" class="featured-title">{{ featuredPost.title }}</h2>
          <p class="featured-desc">{{ featuredPost.summary }}</p>
          <div class="featured-meta">
            <span>SelahCue Team &middot; {{ formatDate(featuredPost.published) }} &middot; {{ readMinutes(featuredPost.body) }} min read</span>
            <UiButton variant="gradient" size="sm" :to="blogPath(featuredPost.slug)">Read story<span class="sr-only">: {{ featuredPost.title }}</span> →</UiButton>
          </div>
        </div>
      </div>
    </section>

    <!-- Grid -->
    <section class="grid-section">
      <div class="container">
        <div class="blog-grid">
          <article v-for="post in posts" :key="post.slug" class="blog-card">
            <UiBadge variant="preview" size="sm">{{ post.category }}</UiBadge>
            <h3 class="card-title">{{ post.title }}</h3>
            <p class="card-desc">{{ post.summary }}</p>
            <div class="card-footer">
              <span class="meta-text">{{ formatDate(post.published) }} &middot; {{ readMinutes(post.body) }} min read</span>
              <router-link class="read-link" :to="blogPath(post.slug)">Read<span class="sr-only">: {{ post.title }}</span> →</router-link>
            </div>
          </article>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.blog-page { background: var(--sc-base); padding-bottom: 80px; }
.container { max-width: 1140px; margin: 0 auto; padding: 0 24px; }
.hero-section { padding: 80px 0 40px; text-align: center; }
.hero-title { font-size: 40px; font-weight: 800; color: var(--sc-text); margin: 16px 0; }
.hero-sub { font-size: 16px; color: var(--sc-text-secondary); }

.featured-card {
  background: linear-gradient(135deg, var(--sc-surface), #1b1938);
  border: 1px solid var(--sc-primary);
  border-radius: 20px;
  padding: 40px;
  margin-bottom: 48px;
}
.featured-title { font-size: 28px; font-weight: 700; color: var(--sc-text); margin: 16px 0 12px 0; }
.featured-desc { font-size: 16px; color: var(--sc-text-secondary); line-height: 1.6; margin-bottom: 24px; }
.featured-meta { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: var(--sc-text-muted); }

.blog-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 28px; }
.blog-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 28px;
  display: flex;
  flex-direction: column;
}
.card-title { font-size: 20px; font-weight: 700; color: var(--sc-text); margin: 14px 0 10px 0; line-height: 1.3; }
.card-desc { font-size: 14px; color: var(--sc-text-secondary); line-height: 1.6; margin-bottom: 24px; flex-grow: 1; }
.card-footer { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: var(--sc-text-muted); }
.read-link { background: none; border: none; color: var(--sc-primary); font-weight: 600; cursor: pointer; }

@media (max-width: 768px) {
  .blog-grid { grid-template-columns: 1fr; }
  .featured-meta { flex-direction: column; align-items: flex-start; gap: 16px; }
}
</style>

<style scoped>
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
