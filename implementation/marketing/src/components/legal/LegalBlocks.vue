<script setup lang="ts">
import type { Block } from '@/lib/legal/types.ts'
import LegalInline from './LegalInline.vue'
import LegalList from './LegalList.vue'

/**
 * `tableLabel` names every table in this run of blocks for assistive technology. The
 * drafts' tables have no captions of their own, so the section's heading is the honest
 * name for them ("Cookies and similar technologies: table").
 */
defineProps<{ blocks: readonly Block[]; tableLabel: string }>()
</script>

<template>
  <template v-for="(b, i) in blocks" :key="i">
    <template v-if="b.kind === 'paragraph'">
      <span v-if="b.anchor" :id="b.anchor" class="legal-anchor" aria-hidden="true"></span>
      <p :class="['lb-p', { 'lb-clause': b.clause }]">
        <span v-if="b.clause" class="lb-num">{{ b.clause }}</span
        >{{ b.clause ? ' ' : '' }}<LegalInline :nodes="b.inline" />
      </p>
    </template>
    <LegalList v-else-if="b.kind === 'list'" :items="b.items" />
    <template v-else>
      <div class="lb-table-wrap" role="region" :aria-label="`${tableLabel}: table`" tabindex="0">
        <table class="lb-table">
          <thead>
            <tr>
              <th v-for="(h, c) in b.header" :key="c" scope="col"><LegalInline :nodes="h" /></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, r) in b.rows" :key="r">
              <template v-for="(cell, c) in row" :key="c">
                <th v-if="c === 0" scope="row" class="lb-rowhead"><LegalInline :nodes="cell" /></th>
                <td v-else><LegalInline :nodes="cell" /></td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="lb-hint" aria-hidden="true">Scroll sideways to see every column.</p>
    </template>
  </template>
</template>

<style scoped>
.lb-p {
  font-size: 15px;
  color: var(--sc-text-secondary);
  line-height: 1.7;
  margin: 0 0 16px;
}
.lb-clause {
  padding-left: var(--clause-indent, 0);
  text-indent: calc(-1 * var(--clause-indent, 0px));
}
.lb-num {
  display: inline-block;
  min-width: calc(var(--clause-indent, 0px) - var(--clause-gap, 8px));
  /* The real space after the number (so copy/paste and text extraction read "1.1 This...",
     not "1.1This...") is about 0.28em wide; take it out of the margin so the hanging indent
     still lines up. */
  margin-right: calc(var(--clause-gap, 8px) - 0.28em);
  text-indent: 0;
  color: var(--sc-text);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.lb-table-wrap {
  max-width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  margin: 4px 0 16px;
  background: var(--sc-surface);
}
.lb-table-wrap:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
}
.lb-table {
  width: 100%;
  min-width: 560px;
  border-collapse: collapse;
  font-size: 14px;
  line-height: 1.55;
}
.lb-table th,
.lb-table td {
  text-align: left;
  vertical-align: top;
  padding: 10px 14px;
  border-bottom: 1px solid var(--sc-border);
  color: var(--sc-text-secondary);
}
.lb-table thead th {
  background: var(--sc-elevated);
  color: var(--sc-text);
  font-weight: 600;
  white-space: nowrap;
}
.lb-table .lb-rowhead { color: var(--sc-text); font-weight: 500; }
.lb-table tbody tr:last-child th,
.lb-table tbody tr:last-child td { border-bottom: 0; }
.lb-hint {
  display: none;
  margin: -8px 0 16px;
  font-size: 13px;
  color: var(--sc-text-secondary);
}
@media (max-width: 819px) {
  .lb-hint { display: block; }
}
</style>
