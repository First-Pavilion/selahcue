<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  /*
   * Figma draws the four hero frames with their own measurements (Pricing 483:139, Features 485:139,
   * Download 487:139, About 496:139): padding, the gap between the lines, the headline's size and
   * line height and its wrapping width, and the subline's width. They are props rather than four
   * copies of the layout. They apply from 1200px up, where the frames are drawn; below that the type
   * tokens and the step-down padding in this file take over, so a phone never gets a 52px headline.
   */
  padTop: { type: Number, default: 96 },
  padBottom: { type: Number, default: 64 },
  gap: { type: Number, default: 22 },
  titleSize: { type: Number, default: 52 },
  titleLine: { type: Number, default: 58 },
  /** Where the headline wraps (Figma lets each frame's text hug a different width). */
  titleMax: { type: Number, default: 720 },
  leadSize: { type: Number, default: 19 },
  leadLine: { type: Number, default: 30 },
  leadMax: { type: Number, default: 760 },
})

const vars = computed(() => ({
  '--hero-top': `${props.padTop}px`,
  '--hero-bottom': `${props.padBottom}px`,
  '--hero-gap': `${props.gap}px`,
  '--hero-title-size': `${props.titleSize}px`,
  '--hero-title-line': `${props.titleLine}px`,
  '--hero-title-max': `${props.titleMax}px`,
  '--hero-lead-size': `${props.leadSize}px`,
  '--hero-lead-line': `${props.leadLine}px`,
  '--hero-lead-max': `${props.leadMax}px`,
}))
</script>

<template>
  <section class="page-hero" :style="vars">
    <div class="container">
      <div class="hero-stack">
        <div v-if="$slots.eyebrow" class="hero-eyebrow"><slot name="eyebrow" /></div>
        <h1 class="hero-title">{{ title }}</h1>
        <p v-if="$slots.default" class="hero-lead"><slot /></p>
        <slot name="after" />
      </div>
    </div>
  </section>
</template>

<style scoped>
/* Phone and tablet first: the type tokens step the headline down (44/50, then 36/42). */
.page-hero {
  padding-block: 48px 32px;
}

.hero-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.hero-eyebrow {
  display: flex;
  justify-content: center;
}

.hero-title {
  margin: 0;
  max-width: 100%;
  font: var(--font-h1-page);
  color: var(--sc-text);
  text-wrap: balance;
}

.hero-lead {
  margin: 0;
  max-width: 100%;
  font-size: 16px;
  line-height: 26px;
  color: var(--sc-text-secondary);
}

@media (min-width: 768px) {
  .page-hero {
    padding-block: 72px 48px;
  }
  .hero-stack {
    gap: 20px;
  }
  .hero-lead {
    font-size: 18px;
    line-height: 28px;
  }
}

/* The frame's own measurements. */
@media (min-width: 1200px) {
  .page-hero {
    padding-block: var(--hero-top) var(--hero-bottom);
  }
  .hero-stack {
    gap: var(--hero-gap);
  }
  .hero-title {
    max-width: var(--hero-title-max);
    font-size: var(--hero-title-size);
    line-height: var(--hero-title-line);
  }
  .hero-lead {
    max-width: var(--hero-lead-max);
    font-size: var(--hero-lead-size);
    line-height: var(--hero-lead-line);
  }
}
</style>
