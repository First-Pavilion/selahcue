<script setup lang="ts">
// A picture of the operator console, not the console: static markup, nothing to load, nothing to run.
</script>

<template>
  <!-- One image for assistive technology (handoff section 6): its name says what it shows, and the
       words inside it are a drawing of the product, not page content. Its box has a fixed height at
       desktop width, so it cannot shift the layout while the page loads. -->
  <div
    class="console-mockup"
    role="img"
    aria-label="SelahCue operator console showing a Preview and a Live scripture slide"
  >
    <!-- Hidden too, not only presentational: not every browser and reader prunes the children of an
         image, and none of these words is page content. -->
    <div aria-hidden="true">
      <div class="window-header">
        <span class="traffic-lights">
          <span class="light close"></span>
          <span class="light minimize"></span>
          <span class="light maximize"></span>
        </span>
        <span class="window-title">SelahCue — Live Console</span>
        <span class="chip live"><span class="dot"></span>LIVE</span>
      </div>

      <div class="interface-grid">
        <div class="pane">
          <div class="pane-head">
            <span class="chip preview"><span class="dot"></span>PREVIEW</span>
            <span class="resolution">1920 × 1080</span>
          </div>
          <div class="slide">
            <span class="slide-ref">PSALM 46:10</span>
            <span class="slide-text">Be still, and know that I am God.</span>
          </div>
        </div>

        <div class="pane">
          <div class="pane-head">
            <span class="chip live"><span class="dot"></span>LIVE</span>
            <span class="resolution">1920 × 1080</span>
          </div>
          <div class="slide">
            <span class="slide-ref">JOHN 3:16</span>
            <span class="slide-text">For God so loved the world…</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/*
 * Figma 470:124, the hero product window: 1140 wide at 1440, radius 16, 1px border, soft shadow
 * (0 34 70 -16). A 45px title bar (traffic lights, "SelahCue — Live Console", a LIVE chip), then two
 * 544px panes side by side, PREVIEW on the left and LIVE on the right, each a 1920 × 1080 label over
 * a 236px slide. The slide canvas is the audience screen (content), so it keeps its own dark ground.
 */
.console-mockup {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 34px 70px -16px rgba(5, 8, 15, 0.7);
  text-align: left;
}

.window-header {
  display: flex;
  align-items: center;
  gap: 7px;
  /* Figma measures padding from the outer edge of the window, so its 1px border comes off the
     paddings that touch it (12/16 becomes 11/15 above and at the sides). */
  padding: 11px 15px 12px;
  background: var(--sc-elevated);
}

.traffic-lights {
  display: flex;
  gap: 7px;
}

.light {
  width: 11px;
  height: 11px;
  border-radius: 50%;
}

.light.close { background: var(--accent-live); }
.light.minimize { background: var(--accent-warn); }
.light.maximize { background: var(--accent-preview); }

.window-title {
  font-size: 12px;
  font-weight: 500;
  line-height: 15px;
  color: var(--sc-text-secondary);
}

/* The status chip: an elevated pill, a dot and a bold 10.5px word in the status ink. */
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px 4px 9px;
  border-radius: 999px;
  background: var(--sc-elevated);
  font-size: 10.5px;
  font-weight: 700;
  line-height: 13px;
  letter-spacing: 0.005em;
}

.chip.live { color: var(--sc-live); }
.chip.preview { color: var(--sc-preview); }

.window-header .chip { margin-left: auto; }

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.interface-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  padding: 18px 17px 17px;
  background: var(--sc-base);
}

.pane {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.pane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.resolution {
  font-size: 11px;
  line-height: 13px;
  color: var(--sc-text-secondary);
}

.slide {
  height: 236px;
  padding: 40px 28px;
  border-radius: 10px;
  /* The projected slide's own canvas (Figma 470:141). */
  background: #080a17;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  text-align: center;
}

.slide-ref {
  font-size: 15px;
  font-weight: 700;
  line-height: 18px;
  letter-spacing: 0.01em;
  color: var(--sc-gold);
}

.slide-text {
  max-width: 360px;
  font-size: 22px;
  font-weight: 600;
  line-height: 30px;
  /* Pure white: the slide's text is a light-on-dark projection, not a site ink. */
  color: #fff;
}

@media (max-width: 767.98px) {
  .interface-grid {
    grid-template-columns: minmax(0, 1fr);
    padding: 14px;
    gap: 14px;
  }

  /* The title would collide with the lights and the chip at phone widths: it truncates instead. */
  .window-title {
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .window-header .chip { flex-shrink: 0; }

  .slide {
    height: auto;
    min-height: 150px;
    padding: 28px 18px;
  }

  .slide-text { font-size: 19px; line-height: 26px; }
}
</style>
