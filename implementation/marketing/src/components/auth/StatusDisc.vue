<script setup lang="ts">
/**
 * The 56x56 status disc at the top of an auth card (handoff §2.3).
 *
 * Always `aria-hidden`. Handoff §12: colour is never the only cue — every status pairs a
 * glyph AND a word, and the word is the card title right beneath this. A screen reader
 * gets the meaning from the title, so announcing "✓" as well would only be noise.
 */
defineProps<{
  /** Status ink for the glyph. `neutral` is for states that are not errors (V6). */
  tone: 'brand' | 'success' | 'danger' | 'warning' | 'neutral'
  glyph: string
}>()
</script>

<template>
  <div :class="['au-disc', `au-disc-${tone}`]" aria-hidden="true">{{ glyph }}</div>
</template>
