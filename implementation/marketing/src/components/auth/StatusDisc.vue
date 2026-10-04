<script setup lang="ts">
/**
 * The 56x56 status disc at the top of an auth card (handoff §2.3).
 *
 * Always `aria-hidden`. Handoff §12: colour is never the only cue — every status pairs a
 * glyph AND a word, and the word is the card title right beneath this. A screen reader
 * gets the meaning from the title, so announcing "✓" as well would only be noise.
 *
 * The cross and the envelope are DRAWN, not typeset (review of PR 179: Cody 3, Quinn Q4; verify-v5-02). Neither is in
 * Inter, so each browser fell back to whatever symbol font the machine had: the envelope was 13px wide on macOS where Figma
 * draws 22px, and the cross was a different weight on Chromium and on WebKit. An inline SVG is the same size and weight
 * in every engine and on every OS, takes its colour from the tone (`currentColor`), and cannot turn into a colour emoji.
 * The other glyphs (↻ ✓ !) are left as text: they are in the fonts the page ships or fall back narrower than the disc.
 */
import { computed } from 'vue'

const props = defineProps<{
  /** Status ink for the glyph. `neutral` is for states that are not errors (V6). */
  tone: 'brand' | 'success' | 'danger' | 'warning' | 'neutral'
  glyph: string
}>()

/** The text-presentation selector (U+FE0E) and the emoji one (U+FE0F) mean nothing once the mark is drawn. */
const mark = computed(() => props.glyph.replace(/[︎️]/g, ''))
</script>

<template>
  <div :class="['au-disc', `au-disc-${tone}`]" aria-hidden="true">
    <svg
      v-if="mark === '✕'"
      class="au-icon"
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      focusable="false"
    >
      <path d="M2 2 14 14M14 2 2 14" />
    </svg>
    <svg
      v-else-if="mark === '✉'"
      class="au-icon"
      width="22"
      height="16"
      viewBox="0 0 22 16"
      fill="none"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linejoin="round"
      stroke-linecap="round"
      focusable="false"
    >
      <rect x="1" y="1" width="20" height="14" rx="2.5" />
      <path d="M1.8 2.6 11 9.6 20.2 2.6" />
    </svg>
    <template v-else>{{ glyph }}</template>
  </div>
</template>
