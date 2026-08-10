<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'

const releases = [
  {
    version: 'v1.2.0',
    date: 'August 8, 2026',
    tag: 'Latest Release',
    highlights: [
      { type: 'new', title: 'Native NDI 5 Output Engine', desc: 'Direct broadcast-quality NDI streaming to OBS, vMix, and Wirecast without extra plugins.' },
      { type: 'new', title: 'Licensed Bible Entitlement Sync', desc: 'Encrypted post-activation downloads for NIV, ESV, and NLT translations.' },
      { type: 'improved', title: 'Hardware Decode Optimization', desc: 'Reduced GPU VRAM usage by 35% on 4K motion backgrounds.' },
      { type: 'fixed', title: 'Stage Monitor Timer Overrun', desc: 'Fixed edge case where stage countdown timer held at 00:00 instead of triggering TIME UP state.' }
    ]
  },
  {
    version: 'v1.1.0',
    date: 'June 15, 2026',
    tag: 'Feature Update',
    highlights: [
      { type: 'new', title: 'Flutter Mobile Companion App', desc: 'Pair iOS and Android devices over local Wi-Fi to control slides and stage timers.' },
      { type: 'improved', title: 'Scripture Verse-by-Verse Paging', desc: 'Faster keyboard navigation using Arrow keys and spacebar.' },
      { type: 'fixed', title: 'Display Reconnect Recovery', desc: 'Restored automatic venue display matching upon HDMI reconnect.' }
    ]
  },
  {
    version: 'v1.0.0',
    date: 'March 1, 2026',
    tag: 'Major Release',
    highlights: [
      { type: 'new', title: 'SelahCue Initial Launch', desc: 'Cross-platform offline presentation software for churches.' }
    ]
  }
]
</script>

<template>
  <div class="changelog-page">
    <section class="hero-section">
      <div class="container">
        <UiBadge variant="featured">Product Updates</UiBadge>
        <h1 class="hero-title">Changelog &amp; Release Notes</h1>
        <p class="hero-sub">Stay up to date with new features, performance improvements, and bug fixes in SelahCue.</p>
      </div>
    </section>

    <section class="timeline-section">
      <div class="container">
        <div class="timeline">
          <div v-for="rel in releases" :key="rel.version" class="timeline-item">
            <div class="timeline-meta">
              <span class="version-code">{{ rel.version }}</span>
              <span class="release-date">{{ rel.date }}</span>
              <UiBadge variant="preview" size="sm">{{ rel.tag }}</UiBadge>
            </div>

            <div class="timeline-content">
              <div v-for="(item, idx) in rel.highlights" :key="idx" class="change-entry">
                <UiBadge 
                  :variant="item.type === 'new' ? 'preview' : item.type === 'improved' ? 'ndi' : 'warn'"
                  size="sm"
                >
                  {{ item.type.toUpperCase() }}
                </UiBadge>
                <div class="entry-body">
                  <h3 class="entry-title">{{ item.title }}</h3>
                  <p class="entry-desc">{{ item.desc }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.changelog-page {
  background: var(--sc-base);
  padding-bottom: 80px;
}

.container {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 24px;
}

.hero-section {
  padding: 80px 0 50px;
  text-align: center;
}

.hero-title {
  font-size: 40px;
  font-weight: 800;
  color: var(--sc-text);
  margin: 16px 0;
}

.hero-sub {
  font-size: 16px;
  color: var(--sc-text-secondary);
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 48px;
  position: relative;
}

.timeline-item {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 36px;
  align-items: start;
}

.timeline-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
  position: sticky;
  top: 100px;
}

.version-code {
  font-size: 24px;
  font-weight: 800;
  color: var(--sc-text);
}

.release-date {
  font-size: 13px;
  color: var(--sc-text-muted);
}

.timeline-content {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.change-entry {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--sc-border);
}

.change-entry:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.entry-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--sc-text);
  margin: 0 0 4px 0;
}

.entry-desc {
  font-size: 14px;
  color: var(--sc-text-secondary);
  line-height: 1.5;
  margin: 0;
}

@media (max-width: 768px) {
  .timeline-item { grid-template-columns: 1fr; gap: 16px; }
  .timeline-meta { position: static; flex-direction: row; align-items: center; }
}
</style>
