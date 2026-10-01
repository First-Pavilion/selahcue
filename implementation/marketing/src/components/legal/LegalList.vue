<script setup lang="ts">
import type { ListItem } from '@/lib/legal/types.ts'
import LegalInline from './LegalInline.vue'

defineProps<{ items: readonly ListItem[] }>()
</script>

<template>
  <ul class="ll">
    <li v-for="(it, i) in items" :key="i" class="ll-item">
      <LegalInline :nodes="it.inline" />
      <LegalList v-if="it.children.length > 0" :items="it.children" />
    </li>
  </ul>
</template>

<style scoped>
.ll { margin: 0 0 16px; }
.ll .ll { margin: 6px 0 0; }
.ll-item {
  position: relative;
  padding-left: 20px;
  margin-bottom: 6px;
  font-size: 15px;
  line-height: 1.7;
  color: var(--sc-text-secondary);
}
.ll-item::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 0.72em;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--sc-text-secondary);
}
</style>
