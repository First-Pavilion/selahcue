<script setup lang="ts">
import { ref } from 'vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'

const searchQuery = ref('')

const categories = [
  { icon: '🚀', title: 'Getting Started', desc: 'Installation, first-time setup, and quickstart guide', count: 8 },
  { icon: '🖥️', title: 'Display & Outputs', desc: 'Configuring audience screens, stage displays & NDI', count: 12 },
  { icon: '📖', title: 'Scripture & Bibles', desc: 'Using built-in Bibles, search, and entitlement downloads', count: 7 },
  { icon: '⏱️', title: 'Timers & Clocks', desc: 'Stage countdowns, service plans, and TIME UP state', count: 5 },
  { icon: '🔧', title: 'Troubleshooting', desc: 'Graphics drivers, NDI lags, audio routing, crash logs', count: 14 },
  { icon: '💳', title: 'Licensing & Billing', desc: 'Managing subscriptions, license keys, and device seats', count: 9 }
]

const popularArticles = [
  { title: 'How to setup NDI output for OBS and vMix', category: 'Display & Outputs', readTime: '3 min' },
  { title: 'Offline Bible entitlement download and licensing', category: 'Scripture & Bibles', readTime: '4 min' },
  { title: 'Configuring stage confidence monitors with custom timers', category: 'Timers & Clocks', readTime: '5 min' },
  { title: 'Deactivating and reassigning venue device seats', category: 'Licensing & Billing', readTime: '2 min' }
]
</script>

<template>
  <div class="support-page">
    <section class="support-hero">
      <div class="container">
        <UiBadge variant="featured">Support &amp; Help Center</UiBadge>
        <h1 class="hero-title">How can we help you today?</h1>
        
        <div class="search-box">
          <svg viewBox="0 0 20 20" fill="currentColor" class="search-icon">
            <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/>
          </svg>
          <input 
            v-model="searchQuery" 
            type="text" 
            class="search-input" 
            placeholder="Search help articles (e.g. NDI, Bible entitlement, stage monitor)..." 
          />
        </div>
      </div>
    </section>

    <!-- Categories Grid -->
    <section class="categories-section">
      <div class="container">
        <h2 class="section-title">Knowledge Base Categories</h2>
        <div class="categories-grid">
          <div v-for="cat in categories" :key="cat.title" class="category-card">
            <div class="cat-icon">{{ cat.icon }}</div>
            <h3 class="cat-title">{{ cat.title }}</h3>
            <p class="cat-desc">{{ cat.desc }}</p>
            <span class="cat-count">{{ cat.count }} articles</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Popular Articles -->
    <section class="articles-section">
      <div class="container">
        <h2 class="section-title">Popular Help Articles</h2>
        <div class="articles-list">
          <div v-for="art in popularArticles" :key="art.title" class="article-row">
            <div>
              <h4 class="article-title">{{ art.title }}</h4>
              <span class="article-meta">{{ art.category }} &middot; {{ art.readTime }} read</span>
            </div>
            <UiButton variant="ghost" size="sm">Read Article →</UiButton>
          </div>
        </div>
      </div>
    </section>

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
  padding: 0 24px;
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
  grid-template-columns: repeat(3, 1fr);
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
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 40px;
  text-align: center;
}

.cta-box h3 { font-size: 24px; color: var(--sc-text); margin: 0 0 8px 0; }
.cta-box p { font-size: 15px; color: var(--sc-text-secondary); margin: 0 0 24px 0; }

@media (max-width: 900px) {
  .categories-grid { grid-template-columns: 1fr; }
  .article-row { flex-direction: column; align-items: flex-start; gap: 12px; }
}
</style>
