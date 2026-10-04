<script setup lang="ts">
/**
 * The coloured icon tile the Support and Docs frames draw for a help category (Figma 498:151 and
 * 499:186): a rounded square on a brand, preview, warn or live fill holding a white feather-style
 * stroke icon (MARKETING-SITE-HANDOFF 7). The content source carries an emoji for each category; the
 * pages draw this instead, keyed by the category id, and an id with no entry falls back to the
 * first icon. Decorative: hidden from assistive technology (the category title next to it names it).
 *
 * `lg` is the Support card tile (48px, radius 13), `md` the Docs hub tile (40px, radius 11).
 */
import { computed } from 'vue'

type Shape = readonly [tag: string, attrs: Record<string, string>]

const ICONS: Record<string, readonly Shape[]> = {
  'getting-started': [['polygon', { points: '13 2 3 14 12 14 11 22 21 10 12 10 13 2' }]],
  'display-outputs': [
    ['rect', { x: '2', y: '3', width: '20', height: '14', rx: '2', ry: '2' }],
    ['line', { x1: '8', y1: '21', x2: '16', y2: '21' }],
    ['line', { x1: '12', y1: '17', x2: '12', y2: '21' }]
  ],
  'scripture-bibles': [
    ['path', { d: 'M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z' }],
    ['path', { d: 'M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z' }]
  ],
  'timers-clocks': [
    ['circle', { cx: '12', cy: '12', r: '10' }],
    ['polyline', { points: '12 6 12 12 16 14' }]
  ],
  'timers-plans': [
    ['circle', { cx: '12', cy: '12', r: '10' }],
    ['polyline', { points: '12 6 12 12 16 14' }]
  ],
  'mobile-control': [
    ['rect', { x: '5', y: '2', width: '14', height: '20', rx: '2', ry: '2' }],
    ['line', { x1: '12', y1: '18', x2: '12.01', y2: '18' }]
  ],
  troubleshooting: [
    ['circle', { cx: '12', cy: '12', r: '10' }],
    ['line', { x1: '12', y1: '8', x2: '12', y2: '12' }],
    ['line', { x1: '12', y1: '16', x2: '12.01', y2: '16' }]
  ]
}

const props = withDefaults(
  defineProps<{
    id: string
    tone?: 'brand' | 'preview' | 'warn' | 'live'
    size?: 'md' | 'lg'
  }>(),
  { tone: 'brand', size: 'lg' }
)

const shapes = computed<readonly Shape[]>(() => ICONS[props.id] ?? ICONS['getting-started'] ?? [])
</script>

<template>
  <div :class="['cat-icon', `is-${tone}`, `is-${size}`]" aria-hidden="true">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <component :is="shape[0]" v-for="(shape, index) in shapes" :key="index" v-bind="shape[1]" />
    </svg>
  </div>
</template>

<style scoped>
.cat-icon {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.cat-icon.is-lg {
  width: 48px;
  height: 48px;
  border-radius: 13px;
}

.cat-icon.is-md {
  width: 40px;
  height: 40px;
  border-radius: 11px;
}

/* The Figma stroke is 2px on the large tile and 1.75px on the small one, over icons that are 24 and
   about 20 units: a 24-unit icon at 24px and at 21px reproduces both. */
.cat-icon.is-lg svg {
  width: 24px;
  height: 24px;
}

.cat-icon.is-md svg {
  width: 21px;
  height: 21px;
}

.cat-icon.is-brand { background: var(--sc-primary); }
.cat-icon.is-preview { background: var(--sc-preview); }
.cat-icon.is-warn { background: var(--sc-warn); }
.cat-icon.is-live { background: var(--sc-live); }
</style>
