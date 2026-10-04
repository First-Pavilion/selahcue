<script setup lang="ts">
/**
 * A picture of the Screens & Outputs window (Figma 475:142). The rows say only what the frame says: a
 * name, a tag and a status. The old sub-lines ("1920x1080 · 60fps", "NDI 5 Stream · Alpha Channel")
 * carried claims the repo cannot back (audit home-42) and are gone.
 */
const rows = [
  { name: 'Audience — Main', tag: 'MAIN', tagTone: 'brand', status: 'LIVE', statusTone: 'live', canvas: 'main' },
  { name: 'Stage Display', tag: 'STAGE', tagTone: 'preview', status: 'READY', statusTone: 'warn', canvas: 'stage' },
  { name: 'Livestream Program', tag: 'NDI', tagTone: 'preview', status: 'BROADCASTING', statusTone: 'preview', canvas: 'ndi' },
]
</script>

<template>
  <!-- One image for assistive technology: the name says what it shows; the words inside it are a drawing
       of the product. The "+ Add output" is a picture of a button, so it is not one. -->
  <div
    class="output-window"
    role="img"
    aria-label="Screens & Outputs window listing three outputs: the audience projector, the stage display and an NDI stream"
  >
    <!-- Hidden too, not only presentational: not every browser and reader prunes the children of an
         image, and none of these words is page content. -->
    <div aria-hidden="true">
      <div class="window-bar">
        <span class="window-title">Screens &amp; Outputs</span>
        <span class="add-output">+ Add output</span>
      </div>

      <div class="output-rows">
        <div v-for="row in rows" :key="row.name" class="output-row">
          <span :class="['thumb', row.canvas]"></span>
          <div class="row-main">
            <div class="row-name">
              <span class="output-name">{{ row.name }}</span>
              <span :class="['pill', 'tag', row.tagTone]">{{ row.tag }}</span>
            </div>
            <span :class="['pill', 'status', row.statusTone]"><span class="dot"></span>{{ row.status }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/*
 * Figma 475:142: 706 wide at 1440, radius 16, 1px border, shadow (0 24 56 -14). A 52px bar with the title
 * (14/600) and a brand "+ Add output" button (11.5/600, radius 8), then three 68px rows (radius 11) each
 * with a 78x46 slide thumbnail, the output name (14/600) and a tag chip, and a status chip on the right.
 */
.output-window {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 24px 56px -14px rgba(5, 8, 15, 0.6);
  text-align: left;
  /* The accessible light indigo for small brand text on a dark pill (the same ink as the hero pill in
     HomeView): Figma's #5b6bd6 is 3.4:1 on this one (audit home-44, class D: Uma picks the final tint).
     Declared here too because a custom property declared in another component does not reach this one. */
  --mock-brand-ink: #a5b4fc;
}

.window-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  /* Figma measures padding from the outer edge of the window, so its 1px border comes off the
     paddings that touch it (13/16 becomes 12/15 above and at the sides). */
  padding: 12px 15px 13px;
  background: var(--sc-elevated);
}

.window-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 17px;
  color: var(--sc-text);
}

.add-output {
  padding: 6px 11px;
  border-radius: 8px;
  background: var(--sc-primary);
  /* Pure white on the brand fill: 4.7:1. */
  color: #fff;
  font-size: 11.5px;
  font-weight: 600;
  line-height: 14px;
  white-space: nowrap;
}

.output-rows {
  display: flex;
  flex-direction: column;
  gap: 11px;
  padding: 14px 13px 13px;
  background: var(--sc-base);
}

.output-row {
  display: flex;
  align-items: center;
  gap: 13px;
  /* 11 from the outer edge: the row's own 1px border comes off it. */
  padding: 10px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 11px;
}

/* The thumbnails are the slide canvases each output shows (content, not site chrome). */
.thumb {
  width: 78px;
  height: 46px;
  flex-shrink: 0;
  border-radius: 7px;
}
.thumb.main { background: #241c4a; }
.thumb.stage { background: #0f121a; }
.thumb.ndi { background: #0d1221; }

.row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px 8px;
}

.row-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.output-name {
  font-size: 14px;
  font-weight: 600;
  line-height: 17px;
  color: var(--sc-text);
}

/* A tag or status chip: an elevated pill and a bold 9.5px word in a status ink that clears 4.5:1 there. */
.pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px 3px 8px;
  border-radius: 999px;
  background: var(--sc-elevated);
  font-size: 9.5px;
  font-weight: 700;
  line-height: 11px;
  letter-spacing: 0.005em;
  white-space: nowrap;
}

/* The MAIN tag: brand ink, in the accessible tint above. */
.pill.brand { color: var(--mock-brand-ink); }
.pill.preview { color: var(--sc-preview); }
.pill.live { color: var(--sc-live); }
.pill.warn { color: var(--sc-warn); }

.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

@media (max-width: 767.98px) {
  .output-row { padding: 10px; gap: 10px; }
  .thumb { width: 56px; height: 36px; }
}
</style>
