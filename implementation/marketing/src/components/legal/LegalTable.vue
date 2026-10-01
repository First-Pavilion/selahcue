<script setup lang="ts">
/**
 * A table from the legal text. The table itself is always named and has column and row
 * headers. Its scroll container becomes a focusable, named region only while the table
 * actually overflows (a phone), so keyboard users can scroll it, and screen-reader users
 * are not given a landmark and a tab stop for a table that fits.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { isOverflowing } from '@/lib/legal/overflow.ts'
import type { Inline } from '@/lib/legal/types.ts'
import LegalInline from './LegalInline.vue'

defineProps<{
  header: readonly (readonly Inline[])[]
  rows: readonly (readonly (readonly Inline[])[])[]
  /** What the table is about: the heading of the section it sits in. */
  label: string
}>()

const wrap = ref<HTMLElement | null>(null)
const scrollable = ref(false)
let observer: ResizeObserver | null = null

function measure(): void {
  if (wrap.value) scrollable.value = isOverflowing(wrap.value)
}

onMounted(() => {
  measure()
  if (typeof ResizeObserver === 'undefined' || !wrap.value) return
  observer = new ResizeObserver(measure)
  observer.observe(wrap.value)
  const table = wrap.value.querySelector('table')
  if (table) observer.observe(table)
})
onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})
</script>

<template>
  <div
    ref="wrap"
    class="lt-wrap"
    :role="scrollable ? 'region' : undefined"
    :aria-label="scrollable ? `${label} (table, scrolls sideways)` : undefined"
    :tabindex="scrollable ? 0 : undefined"
  >
    <table class="lt-table" :aria-label="label">
      <thead>
        <tr>
          <th v-for="(h, c) in header" :key="c" scope="col"><LegalInline :nodes="h" /></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, r) in rows" :key="r">
          <template v-for="(cell, c) in row" :key="c">
            <th v-if="c === 0" scope="row" class="lt-rowhead"><LegalInline :nodes="cell" /></th>
            <td v-else><LegalInline :nodes="cell" /></td>
          </template>
        </tr>
      </tbody>
    </table>
  </div>
  <p v-if="scrollable" class="lt-hint" aria-hidden="true">Scroll sideways to see every column.</p>
</template>

<style scoped>
.lt-wrap {
  max-width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  margin: 4px 0 16px;
  background: var(--sc-surface);
}
.lt-wrap:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
}
.lt-table {
  width: 100%;
  min-width: 560px;
  border-collapse: collapse;
  font-size: 14px;
  line-height: 1.55;
}
.lt-table th,
.lt-table td {
  text-align: left;
  vertical-align: top;
  padding: 10px 14px;
  border-bottom: 1px solid var(--sc-border);
  color: var(--sc-text-secondary);
}
.lt-table thead th {
  background: var(--sc-elevated);
  color: var(--sc-text);
  font-weight: 600;
  white-space: nowrap;
}
.lt-table .lt-rowhead { color: var(--sc-text); font-weight: 500; }
.lt-table tbody tr:last-child th,
.lt-table tbody tr:last-child td { border-bottom: 0; }
.lt-hint {
  margin: -8px 0 16px;
  font-size: 13px;
  color: var(--sc-text-secondary);
}
</style>
