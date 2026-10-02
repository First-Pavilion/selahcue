<script setup lang="ts">
/**
 * Renders one inline-markup string (see `lib/content/inline.ts`) as real elements.
 * No `v-html`: every segment goes through text interpolation, so content cannot inject
 * markup, and a link is only ever a same-site path or an https URL.
 */
import { computed } from 'vue'
import { parseInline } from '@/lib/content/inline.ts'

const props = defineProps<{ text: string }>()
const segments = computed(() => parseInline(props.text))
</script>

<template>
  <template v-for="(s, i) in segments" :key="i">
    <strong v-if="s.kind === 'strong'" class="it-strong">{{ s.text }}</strong>
    <code v-else-if="s.kind === 'code'" class="it-code">{{ s.text }}</code>
    <kbd v-else-if="s.kind === 'kbd'" class="it-kbd">{{ s.text }}</kbd>
    <a
      v-else-if="s.kind === 'link' && s.external"
      class="it-link"
      :href="s.href"
      target="_blank"
      rel="noopener noreferrer"
      >{{ s.text }}<span class="it-sr"> (opens in a new tab)</span></a
    >
    <router-link v-else-if="s.kind === 'link'" class="it-link" :to="s.href">{{ s.text }}</router-link>
    <template v-else>{{ s.text }}</template>
  </template>
</template>

<style scoped>
.it-strong { color: var(--sc-text); font-weight: 600; }
.it-code {
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 6px;
  padding: 1px 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em;
  color: var(--sc-text);
  overflow-wrap: anywhere;
}
.it-kbd {
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border-strong);
  border-bottom-width: 2px;
  border-radius: 6px;
  padding: 1px 7px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.85em;
  color: var(--sc-text);
  white-space: nowrap;
}
.it-link {
  color: var(--sc-primary-hover);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.it-link:hover { color: var(--sc-text); }
.it-link:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
  border-radius: 3px;
}
.it-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
