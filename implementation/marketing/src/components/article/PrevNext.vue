<script setup lang="ts">
/** Previous / next article links at the foot of an article. Either side may be absent. */
import type { Neighbour } from '@/lib/content/types.ts'

defineProps<{ prev: Neighbour | null; next: Neighbour | null; label?: string }>()
</script>

<template>
  <nav v-if="prev || next" class="pn" :aria-label="label ?? 'More articles'">
    <router-link v-if="prev" class="pn-link is-prev" :to="prev.to" rel="prev">
      <span class="pn-dir">Previous</span>
      <span class="pn-title">{{ prev.title }}</span>
    </router-link>
    <span v-else class="pn-gap" aria-hidden="true"></span>
    <router-link v-if="next" class="pn-link is-next" :to="next.to" rel="next">
      <span class="pn-dir">Next</span>
      <span class="pn-title">{{ next.title }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.pn { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 40px; }
.pn-link {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 20px;
  min-height: 44px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  transition: border-color var(--transition-base);
}
.pn-link:hover { border-color: var(--sc-primary); }
.pn-link:focus-visible { outline: 2px solid var(--sc-primary); outline-offset: 2px; }
.pn-link.is-next { text-align: right; grid-column: 2; }
.pn-dir { font-size: 13px; color: var(--sc-text-secondary); }
.pn-title { font-size: 16px; font-weight: 600; color: var(--sc-text); line-height: 1.35; }
@media (max-width: 767.98px) {
  .pn { grid-template-columns: 1fr; }
  .pn-link.is-next { grid-column: auto; text-align: left; }
  .pn-gap { display: none; }
}
</style>
