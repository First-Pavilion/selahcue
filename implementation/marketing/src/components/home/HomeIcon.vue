<script lang="ts">
/**
 * The feather-style stroke icons the Home frame draws (Figma 468:125; handoff section 7: "Icons are
 * inline feather-style SVGs ... reuse the same set in the built site").
 *
 * The path data is Figma's own: read from the vector nodes (473:125 to 473:141 for the feature tiles,
 * 474:133 to 474:147 for the reliability tiles, 475:132 for the showcase tick) and put back on the
 * 24-unit grid the set is drawn on. They replace the emoji and text glyphs (`📊 ⚡ ✓ ✨ ▶ ●`) that
 * rendered differently on every OS and could not take a brand colour (audit home-09).
 */
interface IconDef {
  /** The square viewBox, in units. */
  readonly box: number
  readonly d: readonly string[]
  /** A filled shape (the play mark) rather than a stroke. */
  readonly solid?: boolean
}

export const ICONS: Readonly<Record<string, IconDef>> = {
  monitor: { box: 24, d: ['M2 4h20v13H2z', 'M8 21h8', 'M12 17v4'] },
  book: {
    box: 24,
    d: ['M4 19.5A2.5 2.5 0 0 1 6.5 17H20', 'M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'],
  },
  list: { box: 24, d: ['M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01'] },
  layout: { box: 24, d: ['M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z', 'M3 10h18', 'M9 20V10'] },
  radio: {
    box: 24,
    d: [
      'M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z',
      'M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14',
    ],
  },
  mic: { box: 24, d: ['M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z', 'M5 11a7 7 0 0 0 14 0', 'M12 18v3'] },
  'shield-check': { box: 24, d: ['M12 2 4 5v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V5z', 'm9 12 2 2 4-4'] },
  'wifi-off': {
    box: 24,
    d: [
      'M1 1l22 22',
      'M16.72 11.06A10.94 10.94 0 0 1 19 12.55',
      'M5 12.55a10.94 10.94 0 0 1 5.17-2.39',
      'M10.71 5.05A16 16 0 0 1 22.58 9',
      'M1.42 9a15.91 15.91 0 0 1 4.7-2.88',
      'M8.53 16.11a6 6 0 0 1 6.95 0',
      'M12 20h.01',
    ],
  },
  zap: { box: 24, d: ['M13 2 3 14h9l-1 8 10-12h-9l1-8z'] },
  /** The showcase tick (Figma 475:132): an 18-unit box, 1.8px stroke. */
  check: { box: 18, d: ['M3.75 9l3.75 3.75L15 4.5'] },
  /** The play mark before "Watch 2-min demo" (Figma 469:134, an 11px triangle). */
  play: { box: 24, d: ['M7 3.5v17l14-8.5z'], solid: true },
}

export const ICON_NAMES: readonly string[] = Object.keys(ICONS)
</script>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  /** One of `ICON_NAMES`. An unknown name draws nothing, rather than an empty box. */
  name: {
    type: String,
    required: true,
    validator: (value: string) => ICON_NAMES.includes(value),
  },
  /** Rendered size in px (Figma: 22 in the feature and reliability tiles, 18 for the tick, 11 for the play mark). */
  size: { type: Number, default: 22 },
  /** Stroke width in px as drawn (1.74 in the tiles, 1.8 for the tick). Converted to viewBox units. */
  stroke: { type: Number, default: 1.74 },
})

const icon = computed(() => ICONS[props.name])
const strokeUnits = computed(() => (props.stroke * (icon.value?.box ?? 24)) / props.size)
</script>

<template>
  <!-- Decorative: every icon sits beside text that says the same thing, so none is announced. -->
  <svg
    v-if="icon"
    class="home-icon"
    :data-icon="name"
    :width="size"
    :height="size"
    :viewBox="`0 0 ${icon.box} ${icon.box}`"
    :fill="icon.solid ? 'currentColor' : 'none'"
    :stroke="icon.solid ? 'none' : 'currentColor'"
    :stroke-width="strokeUnits"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="d in icon.d" :key="d" :d="d" />
  </svg>
</template>

<style scoped>
.home-icon {
  display: block;
  flex-shrink: 0;
}
</style>
