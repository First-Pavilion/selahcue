<script setup lang="ts">
import { docsCategories, docsIn, docsPath } from '@/lib/content/docs.ts'
import { readMinutes } from '@/lib/content/text.ts'

// The topics and every article link below come from the local content source, so each
// entry resolves to a real article (GAP-08). Category sections carry the id the article
// breadcrumbs link to (`/docs#<category>`).
</script>

<template>
  <div class="docs-page">
    <div class="container">
      <div class="docs-layout">
        <!-- Left Sidebar Navigation -->
        <aside class="docs-sidebar">
          <div class="sidebar-header">
            <span class="sidebar-title">Documentation</span>
          </div>
          <nav class="sidebar-nav" aria-label="Documentation topics">
            <router-link
              v-for="c in docsCategories"
              :key="c.id"
              class="nav-item"
              :to="{ hash: '#' + c.id }"
            >
              {{ c.title }}
            </router-link>
          </nav>
        </aside>

        <!-- Right Content Area. The site shell already provides <main>. -->
        <div class="docs-content">
          <div class="breadcrumb">Docs</div>

          <h1 class="doc-title">Documentation</h1>
          <p class="doc-lead">How-to guides for running SelahCue, written from what the app actually does.</p>

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
  padding: 60px 0;
  background: var(--sc-base);
  min-height: calc(100vh - 160px);
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
}

.docs-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 48px;
  align-items: start;
}

/* Sidebar */
.docs-sidebar {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 20px;
  position: sticky;
  top: 100px;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--sc-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  display: block;
  margin-bottom: 16px;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  background: none;
  border: none;
  text-align: left;
  padding: 10px 14px;
  font-family: var(--font-family);
  font-size: 14px;
  color: var(--sc-text-secondary);
  border-radius: 8px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.nav-item:hover {
  background: var(--sc-elevated);
  color: var(--sc-text);
}

.nav-item.active {
  background: var(--sc-accent-soft);
  color: var(--sc-primary);
  font-weight: 600;
}

/* Content */
.docs-content {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 48px;
}

.breadcrumb {
  font-size: 13px;
  color: var(--sc-text-muted);
  margin-bottom: 16px;
}

.doc-title {
  font-size: 36px;
  font-weight: 800;
  color: var(--sc-text);
  margin: 0 0 12px 0;
}

.doc-lead {
  font-size: 18px;
  color: var(--sc-text-secondary);
  margin: 0 0 32px 0;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--sc-border);
}

.doc-body h2 {
  font-size: 22px;
  color: var(--sc-text);
  margin: 32px 0 16px 0;
}

.doc-body p {
  font-size: 16px;
  color: var(--sc-text-secondary);
  line-height: 1.7;
  margin-bottom: 20px;
}

.doc-body ul {
  padding-left: 20px;
  margin-bottom: 24px;
}

.doc-body li {
  font-size: 15px;
  color: var(--sc-text-secondary);
  line-height: 1.6;
  margin-bottom: 8px;
}

/* Callouts */
.callout {
  display: flex;
  gap: 16px;
  padding: 18px 20px;
  border-radius: 12px;
  margin: 24px 0;
  font-size: 14px;
  line-height: 1.6;
}

.callout.tip {
  background: var(--sc-preview-soft);
  border: 1px solid var(--sc-preview-border);
  color: var(--sc-text);
}

.callout.warning {
  background: var(--sc-warn-soft);
  border: 1px solid var(--sc-warn-border);
  color: var(--sc-text);
}

.callout-icon { font-size: 20px; }

kbd {
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 4px;
  padding: 2px 6px;
  font-family: monospace;
  font-size: 12px;
}

.code-block {
  background: var(--sc-inset);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  padding: 20px;
  overflow-x: auto;
  font-family: monospace;
  font-size: 14px;
  color: var(--sc-gold);
}

.doc-feedback {
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid var(--sc-border);
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 14px;
  color: var(--sc-text-muted);
}

.feedback-btn {
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  padding: 6px 14px;
  color: var(--sc-text);
  font-size: 13px;
  cursor: pointer;
}

.feedback-btn:hover {
  background: var(--sc-border);
}

@media (max-width: 900px) {
  .docs-layout { grid-template-columns: 1fr; }
  .docs-sidebar { position: static; }
}
</style>

<style scoped>
/* GAP-08: the index lists real articles. Appended as its own block so it does not sit
   inside the rules the responsive pass is editing above. */
.nav-item { display: block; text-decoration: none; }
.nav-item:focus-visible, .topic-link:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; }
.topic { margin-top: 40px; scroll-margin-top: 96px; }
.topic-title { font-size: 22px; font-weight: 700; color: var(--sc-text); margin: 0 0 6px; }
.topic-desc { font-size: 15px; color: var(--sc-text-secondary); margin: 0 0 16px; }
.topic-list { display: flex; flex-direction: column; gap: 10px; }
.topic-link {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 18px;
  min-height: 44px;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  transition: border-color var(--transition-base);
}
.topic-link:hover { border-color: var(--sc-primary); }
.topic-link-title { font-size: 16px; font-weight: 600; color: var(--sc-text); }
.topic-link-sum { font-size: 14px; line-height: 1.55; color: var(--sc-text-secondary); }
.topic-link-meta { font-size: 13px; color: var(--sc-text-secondary); }
</style>
