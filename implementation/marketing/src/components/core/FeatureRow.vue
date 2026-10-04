<script setup lang="ts">
import ToneChip from './ToneChip.vue'

/*
 * One capability row of the Features page (Figma 486:124 and its five siblings): a text column and an
 * abstract skeleton panel, alternating sides. The panel is deliberately NOT a product mockup (audit
 * features-03): a window title chip, an icon tile in the capability's colour, two skeleton bars and a
 * status chip. It is decoration, so it is hidden from assistive technology and carries no claim.
 *
 * Text first in the DOM on every row; the even rows only swap the visual order (`reverse`).
 */
defineProps({
  tone: {
    type: String,
    required: true,
    validator: (v: string) => ['live', 'brand', 'warn', 'ready'].includes(v),
  },
  eyebrow: { type: String, required: true },
  title: { type: String, required: true },
  text: { type: String, required: true },
  bullets: { type: Array as () => string[], required: true },
  /** The window title chip and the status chip inside the panel. */
  panelTitle: { type: String, required: true },
  panelChip: { type: String, required: true },
  reverse: { type: Boolean, default: false },
})
</script>

<template>
  <section :class="['feature-row', `tone-${tone}`, { reverse }]">
    <div class="container">
      <div class="row-layout">
        <div class="row-copy">
          <ToneChip class="row-eyebrow" kind="row" :tone="tone">{{ eyebrow }}</ToneChip>
          <h2>{{ title }}</h2>
          <p class="row-text">{{ text }}</p>
          <ul class="row-bullets">
            <li v-for="bullet in bullets" :key="bullet">
              <svg class="tick" viewBox="0 0 16 19" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3.3 9.6l3.1 3.2 6.9-7.3" />
              </svg>
              <span>{{ bullet }}</span>
            </li>
          </ul>
        </div>

        <div class="feature-panel" aria-hidden="true">
          <div class="panel-chrome">
            <span class="dot dot-red"></span><span class="dot dot-gold"></span><span class="dot dot-green"></span>
            <ToneChip class="panel-title" kind="title" tone="muted">{{ panelTitle }}</ToneChip>
          </div>
          <div class="panel-tile"><slot name="icon" /></div>
          <div class="skeleton-bar long"></div>
          <div class="skeleton-bar short"></div>
          <div class="panel-chips">
            <ToneChip kind="status" :tone="tone">{{ panelChip }}</ToneChip>
            <span class="skeleton-pill"></span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* Figma: a row is 336px (40px above and below a 256px panel), text 644 and panel 548 with a 56px gap. */
.feature-row {
  padding-block: 28px;
}

.row-layout {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.row-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
  min-width: 0;
}

.row-copy h2 {
  margin: 0;
  font: 700 26px/32px var(--font-family);
  color: var(--sc-text);
}

.row-text {
  margin: 0;
  font-size: 16px;
  line-height: 26px;
  color: var(--sc-text-secondary);
}

.row-bullets {
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.row-bullets li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 15.5px;
  line-height: 19px;
  color: var(--sc-text);
}

.tick {
  flex-shrink: 0;
  width: 16px;
  height: 19px;
  color: var(--sc-preview);
}

/* The skeleton panel (Figma 486:131): 548x256, radius 20, padding 24, an 18px gap between blocks. */
.feature-panel {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
  /* Figma measures padding from the OUTER edge (stroke inside the frame), so the 1px border comes off it. */
  padding: 23px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
}

.panel-chrome {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 22px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.dot-red {
  background: var(--sc-live);
}
.dot-gold {
  background: var(--sc-warn);
}
.dot-green {
  background: var(--sc-preview);
}

.panel-title {
  margin-left: 17px;
}

/* The tile takes the capability's colour; the glyph is white, as drawn. It is decoration (the panel is
   aria-hidden and the row's heading carries the meaning), so the glyph is not held to a 3:1 ratio
   against the gold and green fills. */
.panel-tile {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 60px;
  height: 60px;
  border-radius: 16px;
  color: #fff;
}
.tone-live .panel-tile {
  background: var(--sc-live);
}
.tone-brand .panel-tile {
  background: var(--sc-primary);
}
.tone-warn .panel-tile {
  background: var(--sc-warn);
}
.tone-ready .panel-tile {
  background: var(--sc-preview);
}

.skeleton-bar {
  height: 14px;
  border-radius: 7px;
  background: var(--sc-elevated);
}
.skeleton-bar.long {
  width: 100%;
}
.skeleton-bar.short {
  width: 64%;
}

.panel-chips {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 26px;
}

.skeleton-pill {
  width: 90px;
  height: 26px;
  border-radius: 13px;
  background: var(--sc-elevated);
}

@media (min-width: 768px) {
  .feature-row {
    padding-block: 36px;
  }
  .row-copy h2 {
    font-size: 30px;
    line-height: 36px;
  }
  .row-text {
    font-size: 17px;
    line-height: 27px;
  }
}

@media (min-width: 1200px) {
  .feature-row {
    padding-block: 40px;
  }
  .row-layout {
    flex-direction: row;
    align-items: center;
    gap: 56px;
  }
  .feature-row.reverse .row-layout {
    flex-direction: row-reverse;
  }
  .row-copy {
    flex: 1 1 644px;
  }
  .feature-panel {
    flex: 0 0 548px;
    width: 548px;
  }
}
</style>
