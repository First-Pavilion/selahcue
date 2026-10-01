<script setup lang="ts">
/** Breadcrumb trail. The last item is the current page: text, not a link. */
import type { Crumb } from '@/lib/content/types.ts'

defineProps<{ items: readonly Crumb[] }>()
</script>

<template>
  <nav class="bc" aria-label="Breadcrumb">
    <ol class="bc-list">
      <li v-for="(item, i) in items" :key="i" class="bc-item">
        <router-link v-if="item.to && i < items.length - 1" class="bc-link" :to="item.to">{{ item.label }}</router-link>
        <span v-else class="bc-current" :aria-current="i === items.length - 1 ? 'page' : undefined">{{ item.label }}</span>
        <span v-if="i < items.length - 1" class="bc-sep" aria-hidden="true">/</span>
      </li>
    </ol>
  </nav>
</template>

<style scoped>
.bc { font-size: 14px; margin-bottom: 20px; }
.bc-list { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
.bc-item { display: inline-flex; align-items: center; gap: 8px; min-width: 0; }
.bc-link { color: var(--sc-text-secondary); text-decoration: underline; text-underline-offset: 3px; padding: 4px 0; }
.bc-link:hover { color: var(--sc-text); }
.bc-link:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; border-radius: 3px; }
.bc-current { color: var(--sc-text); overflow-wrap: anywhere; }
.bc-sep { color: var(--sc-text-secondary); opacity: 0.6; }
</style>
