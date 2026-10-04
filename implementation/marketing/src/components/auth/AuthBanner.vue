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
type BannerKind = 'info' | 'success' | 'warning' | 'danger'

defineProps<{
  kind: BannerKind
  title: string
  /** Card-level banners that report a failure are announced (handoff §12: R7 is role="alert"). */
  alert?: boolean
}>()

const GLYPHS: Record<BannerKind, string> = {
  info: '◆',
  success: '✓',
  warning: '!',
  danger: '✕',
}
</script>

<!--
  The diamond and the cross are DRAWN, not typeset (review of PR 179: Cody 3, Quinn Q4). Neither is in Inter, so each engine fell
  back to its own symbol font: the diamond was about 7px wide on macOS Chromium and 14px on WebKit, with the same CSS. A fixed-size
  SVG is the same everywhere. The tick and the exclamation mark stay text: the tick falls back to the Figma width and `!` is Inter's.
-->
<template>
  <div :class="['au-banner', `au-banner-${kind}`]" :role="alert ? 'alert' : undefined">
    <span class="au-banner-glyph" aria-hidden="true">
      <svg
        v-if="kind === 'info'"
        class="au-icon"
        width="14"
        height="14"
        viewBox="0 0 14 14"
        fill="currentColor"
        focusable="false"
      >
        <path d="M7 .5 13.5 7 7 13.5.5 7z" />
      </svg>
      <svg
        v-else-if="kind === 'danger'"
        class="au-icon"
        width="10"
        height="10"
        viewBox="0 0 10 10"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        focusable="false"
      >
        <path d="M1 1 9 9M9 1 1 9" />
      </svg>
      <template v-else>{{ GLYPHS[kind] }}</template>
    </span>
    <div>
      <p class="au-banner-title">{{ title }}</p>
      <p class="au-banner-body"><slot /></p>
    </div>
  </div>
</template>
