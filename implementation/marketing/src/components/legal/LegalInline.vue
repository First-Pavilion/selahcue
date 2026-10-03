<script setup lang="ts">
/**
 * Renders a run of inline legal content as real elements.
 *
 * No raw-HTML rendering of any kind: every node goes through ordinary template
 * interpolation, so markup in the source is displayed as text, never run. A link is only
 * ever emitted when `classifyHref` approves its target (the generator already refused
 * anything else; this is the second, independent gate).
 *
 * A placeholder is rendered as a highlighted chip, always. Placeholders exist only while
 * the document is a draft, so the highlight disappears when the last one is filled in.
 */
import { useRouter } from 'vue-router'
import { goToAnchor } from '@/lib/legal/anchors.ts'
import { classifyHref } from '@/lib/legal/links.ts'
import type { Inline } from '@/lib/legal/types.ts'
import { inlineToText } from '@/lib/legal/document.ts'

defineProps<{
  nodes: readonly Inline[]
  /**
   * The text MENTIONS the placeholder convention rather than missing a fact (the
   * document's own draft banner says "fill every {{PLACEHOLDER}}"). Rendered as plain
   * code, not as a highlighted chip, so chips always equal the real missing facts.
   */
  mention?: boolean
}>()
const router = useRouter()

function token(name: string): string {
  return `{{${name}}}`
}
</script>

<template>
  <template v-for="(n, i) in nodes" :key="i">
    <template v-if="n.kind === 'text'">{{ n.text }}</template>
    <strong v-else-if="n.kind === 'strong'" class="li-strong"><LegalInline :nodes="n.children" :mention="mention" /></strong>
    <code v-else-if="n.kind === 'code'" class="li-code">{{ n.text }}</code>
    <code v-else-if="n.kind === 'placeholder' && mention" class="li-code">{{ token(n.name) }}</code>
    <mark v-else-if="n.kind === 'placeholder'" class="ph" data-placeholder
      ><span class="li-sr">Placeholder, to be completed: </span>{{ token(n.name) }}</mark
    >
    <a
      v-else-if="n.kind === 'ref'"
      class="li-link"
      :href="`#${n.anchor}`"
      @click.prevent="goToAnchor(router, n.anchor)"
      >{{ n.text }}</a
    >
    <template v-else-if="n.kind === 'link'">
      <a
        v-if="classifyHref(n.href) === 'external'"
        class="li-link"
        :href="n.href"
        target="_blank"
        rel="noopener noreferrer"
        ><LegalInline :nodes="n.children" /><span class="li-sr"> (opens in a new tab)</span></a
      >
      <router-link v-else-if="classifyHref(n.href) === 'internal'" class="li-link" :to="n.href"
        ><LegalInline :nodes="n.children"
      /></router-link>
      <a v-else-if="classifyHref(n.href) === 'mailto'" class="li-link" :href="n.href"
        ><LegalInline :nodes="n.children"
      /></a>
      <template v-else>{{ inlineToText(n.children) }}</template>
    </template>
  </template>
</template>

<style scoped>
.li-strong { color: var(--sc-text); font-weight: 600; }
.li-code {
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 6px;
  padding: 1px 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em;
  color: var(--sc-text);
  overflow-wrap: anywhere;
}
.ph {
  background: var(--sc-warn-soft);
  color: var(--sc-warn);
  border: 1px dashed var(--sc-warn);
  border-radius: 4px;
  padding: 0 5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.88em;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.li-link {
  color: var(--sc-primary-hover);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.li-link:hover { color: var(--sc-text); }
.li-link:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
  border-radius: 3px;
}
.li-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
