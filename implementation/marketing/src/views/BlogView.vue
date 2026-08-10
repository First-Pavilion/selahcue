<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'

const posts = [
  { id: 1, title: 'Why Offline-First Presentation Matters for Sunday Morning', tag: 'Product Strategy', date: 'August 5, 2026', readTime: '5 min read', desc: 'When church Wi-Fi fails, your presentation software shouldn’t blank. Here is how SelahCue’s desktop-authoritative architecture protects your service.' },
  { id: 2, title: 'Setting Up Multi-Screen Confidence Monitors and Timers', tag: 'Worship Tech', date: 'July 28, 2026', readTime: '4 min read', desc: 'A step-by-step guide to routing current slides, next items, and countdown clocks to your stage team.' },
  { id: 3, title: 'Understanding Bible Translation Copyright & Licensing', tag: 'Legal & Entitlements', date: 'July 14, 2026', readTime: '6 min read', desc: 'Why public domain translations are bundled offline, and how post-activation entitlement grants work for copyrighted versions like NIV and ESV.' },
  { id: 4, title: 'Integrating NDI 5 with OBS and vMix for Broadcast Quality', tag: 'Livestreaming', date: 'June 30, 2026', readTime: '4 min read', desc: 'Stream transparent lower thirds and worship lyrics directly to your stream switcher with zero capture card latency.' }
]
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
    <section class="featured-section">
      <div class="container">
        <div class="featured-card">
          <div class="featured-badge"><UiBadge variant="live">Featured Article</UiBadge></div>
          <h2 class="featured-title">Introducing SelahCue 1.2: Native NDI &amp; Multi-Screen Precision</h2>
          <p class="featured-desc">
            Explore our latest release featuring direct NDI streaming, encrypted Bible translation downloads, and zero-latency hardware buffer outputs.
          </p>
          <div class="featured-meta">
            <span>SelahCue Engineering Team &middot; August 8, 2026 &middot; 7 min read</span>
            <UiButton variant="gradient" size="sm">Read Story →</UiButton>
          </div>
        </div>
      </div>
    </section>

    <!-- Grid -->
    <section class="grid-section">
      <div class="container">
        <div class="blog-grid">
          <div v-for="post in posts" :key="post.id" class="blog-card">
            <UiBadge variant="preview" size="sm">{{ post.tag }}</UiBadge>
            <h3 class="card-title">{{ post.title }}</h3>
            <p class="card-desc">{{ post.desc }}</p>
            <div class="card-footer">
              <span class="meta-text">{{ post.date }} &middot; {{ post.readTime }}</span>
              <button type="button" class="read-link">Read →</button>
            </div>
          </div>
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
