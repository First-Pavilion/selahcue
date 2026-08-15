<script setup lang="ts">
/**
 * The reassurance banner that closes almost every auth card.
 *
 * These are not decoration. Every error, expiry and destructive frame in this design
 * carries one because of the product's hard invariant (handoff §1, NFR-015 / CON-2 /
 * NFR-024): account and licensing state must never block, blank, or IMPLY blocking of
 * live presentation. "You don't need an account to run SelahCue" on a failed
 * verification, and "Your devices keep presenting" on a password change, are the
 * statements that stop a stressed operator concluding that Sunday is at risk. §4.2 is
 * explicit that the banner "must not be dropped".
 *
 * Colour handling (§2.2): the glyph carries the status ink; the title and body never do.
 * That keeps every text pair well clear of AA and satisfies WCAG 1.4.1 — the words carry
 * the meaning, not the hue.
 */
const props = defineProps<{
  kind: 'info' | 'success' | 'warning' | 'danger'
  title: string
  /** Card-level banners that report a failure are announced (handoff §12: R7 is role="alert"). */
  alert?: boolean
}>()

const GLYPHS: Record<typeof props.kind, string> = {
  info: '◆',
  success: '✓',
  warning: '!',
  danger: '✕',
}
</script>

<template>
  <div :class="['au-banner', `au-banner-${kind}`]" :role="alert ? 'alert' : undefined">
    <span class="au-banner-glyph" aria-hidden="true">{{ GLYPHS[kind] }}</span>
    <div>
      <p class="au-banner-title">{{ title }}</p>
      <p class="au-banner-body"><slot /></p>
    </div>
  </div>
</template>
