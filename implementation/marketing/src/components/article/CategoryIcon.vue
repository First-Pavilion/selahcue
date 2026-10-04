<script setup lang="ts">
/**
 * The coloured icon tile the Support, Docs and Blog frames draw (Figma 498:151, 499:186, 502:162 and
 * 502:147): a rounded square on a brand, preview, warn or live fill holding a white feather-style stroke
 * icon (MARKETING-SITE-HANDOFF 7). The content source carries an emoji for each help category; the pages
 * draw this instead, keyed by the category id or by an icon name, and a name with no entry falls back to
 * the first icon. Decorative: hidden from assistive technology (the title next to it names it).
 *
 * Sizes: `md` the Docs hub tile (40px, radius 11), `lg` the Support card tile (48px, radius 13), `tile` the
 * Careers culture tile (50px, radius 13), `thumb` the Blog card thumbnail tile (51px, radius 14), `xl` the
 * Blog featured tile (102px, radius 14).
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
  ],
  'shield-check': [
    ['path', { d: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' }],
    ['polyline', { points: '9 12 11 14 15 10' }]
  ],
  monitor: [
    ['rect', { x: '2', y: '3', width: '20', height: '14', rx: '2', ry: '2' }],
    ['line', { x1: '8', y1: '21', x2: '16', y2: '21' }],
    ['line', { x1: '12', y1: '17', x2: '12', y2: '21' }]
  ],
  smartphone: [
    ['rect', { x: '5', y: '2', width: '14', height: '20', rx: '2', ry: '2' }],
    ['line', { x1: '12', y1: '18', x2: '12.01', y2: '18' }]
  ],
  radio: [
    ['circle', { cx: '12', cy: '12', r: '2' }],
    ['path', { d: 'M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14' }]
  ],
  'book-open': [
    ['path', { d: 'M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z' }],
    ['path', { d: 'M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z' }]
  ],
  globe: [
    ['circle', { cx: '12', cy: '12', r: '10' }],
    ['line', { x1: '2', y1: '12', x2: '22', y2: '12' }],
    ['path', { d: 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z' }]
  ],
  'check-circle': [
    ['path', { d: 'M22 11.08V12a10 10 0 1 1-5.93-9.14' }],
    ['polyline', { points: '22 4 12 14.01 9 11.01' }]
  ],
  heart: [
    ['path', { d: 'M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z' }]
  ],
  'wifi-off': [
    ['line', { x1: '1', y1: '1', x2: '23', y2: '23' }],
    ['path', { d: 'M16.72 11.06A10.94 10.94 0 0 1 19 12.55' }],
    ['path', { d: 'M5 12.55a10.94 10.94 0 0 1 5.17-2.39' }],
    ['path', { d: 'M10.71 5.05A16 16 0 0 1 22.58 9' }],
    ['path', { d: 'M1.42 9a15.91 15.91 0 0 1 4.7-2.88' }],
    ['path', { d: 'M8.53 16.11a6 6 0 0 1 6.95 0' }],
    ['line', { x1: '12', y1: '20', x2: '12.01', y2: '20' }]
  ]
}

const props = withDefaults(
  defineProps<{
    name: string
    tone?: 'brand' | 'preview' | 'warn' | 'live'
    size?: 'md' | 'lg' | 'tile' | 'thumb' | 'xl'
  }>(),
  { tone: 'brand', size: 'lg' }
)

const shapes = computed<readonly Shape[]>(() => ICONS[props.name] ?? ICONS['getting-started'] ?? [])
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

.cat-icon.is-tile {
  width: 50px;
  height: 50px;
  border-radius: 13px;
}

.cat-icon.is-thumb {
  width: 51px;
  height: 51px;
  border-radius: 14px;
}

.cat-icon.is-xl {
  width: 102px;
  height: 102px;
  border-radius: 14px;
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

.cat-icon.is-tile svg {
  width: 23px;
  height: 23px;
}

.cat-icon.is-thumb svg {
  width: 27px;
  height: 27px;
}

.cat-icon.is-xl svg {
  width: 53px;
  height: 53px;
}

.cat-icon.is-brand { background: var(--sc-primary); }
.cat-icon.is-preview { background: var(--sc-preview); }
.cat-icon.is-warn { background: var(--sc-warn); }
.cat-icon.is-live { background: var(--sc-live); }
</style>
