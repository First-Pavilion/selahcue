<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import PageHero from '@/components/core/PageHero.vue'
import CtaBand from '@/components/core/CtaBand.vue'

/*
 * Figma 496:124: a hero, a two-column "Why we built SelahCue" story, a band of four values, a closing
 * band. The words are Figma's except where the repo does not back them (audit about-03, about-08, and
 * the Copy rule on ClickUp 17tnw2b2cey):
 *
 *  - "the whole thing runs with no network at all" overreaches NFR-015 ("all core live functions
 *    operate with the network disabled"), so the story says every core live control;
 *  - the fourth value ships only the backed part (memory is bounded, NFR-002 and 003). "Fast cold start"
 *    is a target, not a measurement, and "no account or tracking required" is not evidenced anywhere
 *    (about-08, owner decision pending), so neither is claimed;
 *  - "AI assists, never gates" is FR-083.
 */
</script>

<template>
  <div class="about-page">
    <PageHero
      title="Built for the people running the service"
      :pad-top="96"
      :pad-bottom="48"
      :gap="20"
      :title-size="50"
      :title-line="56"
      :title-max="560"
    >
      <template #eyebrow>
        <UiBadge variant="featured">ABOUT</UiBadge>
      </template>
      SelahCue started with one conviction: the moment a congregation is worshipping is not the moment your software should fail. So we built a church presentation app that stays up, stays offline, and stays out of the way.
    </PageHero>

    <!-- Figma 496:144: pad 40/96/56, gap 56; two 596px columns. -->
    <section class="story-section">
      <div class="container story-layout">
        <h2>Why we built SelahCue</h2>
        <div class="story-text">
          <p>Too many services are one crashed slide away from a blank screen — and the tools meant to help often assume a fast, always-on internet connection that a lot of churches simply don't have.</p>
          <p>We wanted the opposite: a desktop-authoritative app where the compositor never blanks live output, every core live control works with no network at all, and helpful AI features assist the operator without ever gating the controls that matter.</p>
          <p>That's what SelahCue is — presentation, scripture, timers, stage display and streaming outputs in one console, with a phone in your hand as the remote, built to be dependable on the one morning you can't get a second take.</p>
        </div>
      </div>
    </section>

    <!-- Figma 496:151: a full-width band (fill #171b22 = --sc-surface), pad 40/96/56, gap 28. -->
    <section class="values-band">
      <div class="container">
        <h2>What we stand for</h2>
        <div class="values-grid">
          <div class="value-card">
            <span class="value-tile tile-ready" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v5c0 5-3.2 8.5-7 10-3.8-1.5-7-5-7-10V6z" /><path d="M9 12l2 2 4-4" /></svg>
            </span>
            <h3>Reliability comes first</h3>
            <p>The screen never blanks. Every decision serves the one moment you can't repeat.</p>
          </div>
          <div class="value-card">
            <span class="value-tile tile-brand" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 9a15 15 0 0 1 19 0M5.5 12.5a10 10 0 0 1 13 0M8.7 16a5 5 0 0 1 6.6 0M12 19.5h.01" /></svg>
            </span>
            <h3>Offline by default</h3>
            <p>Your Sunday can't depend on the internet, so SelahCue doesn't either.</p>
          </div>
          <div class="value-card">
            <span class="value-tile tile-warn" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /></svg>
            </span>
            <h3>AI assists, never gates</h3>
            <p>Transcript and detection help the operator but stay out of the core controls.</p>
          </div>
          <div class="value-card">
            <span class="value-tile tile-live" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 18a9 9 0 1 1 16 0" /><path d="M12 14l4-4" /></svg>
            </span>
            <h3>Bounded &amp; respectful</h3>
            <p>Memory use is capped, so SelahCue stays light on the machine it runs on.</p>
          </div>
        </div>
      </div>
    </section>

    <CtaBand />
  </div>
</template>

<style scoped>
.about-page {
  background: var(--sc-base);
}

/* ---- story ---- */
.story-section {
  padding-block: 16px 40px;
}

.story-layout {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.story-layout h2 {
  margin: 0;
  font: 700 26px/32px var(--font-family);
  color: var(--sc-text);
}

.story-text {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.story-text p {
  margin: 0;
  font-size: 16px;
  line-height: 26px;
  color: var(--sc-text-secondary);
}

/* ---- values ---- */
.values-band {
  padding-block: 40px;
  background: var(--sc-surface);
}

.values-band h2 {
  margin: 0 0 24px;
  text-align: center;
  font: 700 26px/32px var(--font-family);
  color: var(--sc-text);
}

.values-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

.value-card {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
  min-width: 0;
  /* Figma pads from the OUTER edge (stroke inside the frame): the 1px border comes off the padding. */
  padding: 23px;
  background: var(--sc-base);
  border: 1px solid var(--sc-border);
  border-radius: 18px;
}

/* The tile takes the value's colour; the glyph is white, as drawn, on the red and the brand fill (3.27:1
   and 4.72:1). On the gold and the green fill white is 2.0:1 and 2.3:1 (Figma draws it so), so those two
   take the page's dark ink (9.5:1 and 8.4:1). Decoration (aria-hidden, the title carries the meaning):
   this is legibility, not a requirement. */
.value-tile {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  color: #fff;
}
.tile-ready {
  background: var(--sc-preview);
  color: var(--sc-base);
}
.tile-brand {
  background: var(--sc-primary);
}
.tile-warn {
  background: var(--sc-warn);
  color: var(--sc-base);
}
.tile-live {
  background: var(--sc-live);
}

.value-card h3 {
  margin: 0;
  font: 600 18px/24px var(--font-family);
  color: var(--sc-text);
}

.value-card p {
  margin: 0;
  font-size: 14.5px;
  line-height: 22px;
  color: var(--sc-text-secondary);
}

@media (min-width: 768px) {
  .story-section {
    padding-block: 24px 48px;
  }
  .story-layout {
    flex-direction: row;
    gap: 40px;
  }
  .story-layout h2,
  .story-text {
    flex: 1 1 0;
    min-width: 0;
  }
  .story-layout h2 {
    font-size: 30px;
    line-height: 36px;
  }
  .story-text p {
    font-size: 17px;
    line-height: 27px;
  }
  .values-band {
    padding-block: 40px 56px;
  }
  .values-band h2 {
    margin-bottom: 28px;
    font-size: 32px;
    line-height: 39px;
  }
  .values-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 20px;
  }
}

@media (min-width: 1200px) {
  .story-section {
    padding-block: 40px 56px;
  }
  .story-layout {
    gap: 56px;
  }
  .values-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 24px;
  }
  .value-card {
    padding: 25px 23px;
  }
}
</style>
