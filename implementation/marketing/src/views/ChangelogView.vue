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


type ChangeType = 'new' | 'improved' | 'fixed'

/**
 * The change-type labels (Figma 501:154): one pill per GROUP of changes, in this order. The variants are
 * the ones UiBadge defines, chosen in the template as a plain choice between literals (the shared tree test
 * can only check a variant it can read): New is the green `preview` tone, Improved is the brand `accent` tone
 * and Fixed is the amber `warn` tone. The dot beside each change takes the same colour.
 */
const TYPES: Array<{ type: ChangeType; label: string }> = [
  { type: 'new', label: 'New' },
  { type: 'improved', label: 'Improved' },
  { type: 'fixed', label: 'Fixed' }
]

/** A release's changes grouped by type, in the frame's order, leaving out a type it has no changes of. */
const groupsOf = (rel: (typeof releases)[number]) =>
  TYPES.map((t) => ({ ...t, items: rel.highlights.filter((h) => h.type === t.type) })).filter((g) => g.items.length > 0)
</script>

<template>
  <div class="changelog-page">
    <section class="hero-section container">
      <UiBadge variant="featured">CHANGELOG</UiBadge>
      <h1 class="hero-title">What's new</h1>
      <p class="hero-sub">Stay up to date with new features, performance improvements, and bug fixes in SelahCue.</p>
    </section>

    <section class="release-section container">
      <div class="release-list">
        <article v-for="(rel, index) in releases" :key="rel.version" class="release-card">
          <header class="release-head">
            <h2 class="version-code">{{ rel.version }}</h2>
            <span class="release-date">{{ rel.date }}</span>
            <UiBadge v-if="index === 0" class="release-tag" variant="preview" size="sm">{{ rel.tag }}</UiBadge>
          </header>

          <div class="release-rule" aria-hidden="true"></div>

          <div v-for="group in groupsOf(rel)" :key="group.type" :class="['change-group', 'is-' + group.type]">
            <UiBadge
              class="change-label"
              :variant="group.type === 'new' ? 'preview' : group.type === 'improved' ? 'accent' : 'warn'"
              size="sm"
              >{{ group.label }}</UiBadge
            >
            <ul class="change-list">
              <li v-for="(item, idx) in group.items" :key="idx" class="change-entry">
                <span class="change-dot" aria-hidden="true"></span>
                <div class="entry-body">
                  <h3 class="entry-title">{{ item.title }}</h3>
                  <p class="entry-desc">{{ item.desc }}</p>
                </div>
              </li>
            </ul>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.changelog-page {
  background: var(--sc-base);
  padding-bottom: 64px;
}

/* HERO (Figma 501:139): padding 96 top / 40 bottom, 18px between the pill, the headline and the subline,
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

/* THE RELEASES (Figma 501:144): padding 24 top, one card per release, 900 wide and centred, 24px apart. */
.release-section {
  padding-top: 24px;
}

.release-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 900px;
  margin-inline: auto;
}

/* A release card (Figma 501:145): the panel surface, a 1px border, radius 20, padding 28 / 30 from the edge
   (the stroke is drawn inside), 18px between the header, the rule and each group of changes. */
.release-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 27px 29px;
}

.release-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.version-code {
  font-size: 22px;
  font-weight: 700;
  line-height: 27px;
  color: var(--sc-text);
}

.release-date {
  font-size: 14px;
  line-height: 17px;
  color: var(--sc-text-secondary);
}

.release-rule {
  height: 1px;
  background: var(--sc-border);
}

/* A group: its label pill, then the list 16px to the right of it (the frame does not align the lists, so
   neither does this). The pill is sentence case in the frame; UiBadge uppercases, so this turns that off. */
.change-group {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.change-label {
  flex-shrink: 0;
  text-transform: none;
}

.change-list {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.change-entry {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

/* The 6px dot in the type's colour, centred on the first line (23px tall). */
.change-dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  margin-top: 9px;
  border-radius: 50%;
  background: var(--sc-preview);
}

.is-improved .change-dot { background: var(--sc-primary); }
.is-fixed .change-dot { background: var(--sc-warn); }

.entry-body {
  min-width: 0;
}

.entry-title {
  font-size: 15px;
  font-weight: 400;
  line-height: 23px;
  color: var(--sc-text);
}

.entry-desc {
  margin-top: 1px;
  font-size: 14px;
  line-height: 21px;
  color: var(--sc-text-secondary);
}

@media (max-width: 767.98px) {
  .changelog-page { padding-bottom: var(--section-pad-sm); }
  .hero-section { padding-top: 56px; padding-bottom: 28px; gap: 14px; }
  .hero-sub { font-size: 16px; line-height: 24px; }
  .release-section { padding-top: 8px; }
  .release-card { padding: 21px 19px; border-radius: 16px; }
  .change-group { flex-direction: column; gap: 10px; }
}
</style>
