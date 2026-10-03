<script setup lang="ts">
import type { Block } from '@/lib/legal/types.ts'
import LegalInline from './LegalInline.vue'
import LegalList from './LegalList.vue'
import LegalTable from './LegalTable.vue'

/**
 * `tableLabel` names every table in this run of blocks for assistive technology. The
 * drafts' tables have no captions of their own, so the section's heading is the honest
 * name for them ("Cookies and similar technologies").
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
    <LegalTable v-else :header="b.header" :rows="b.rows" :label="tableLabel" />
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
</style>
