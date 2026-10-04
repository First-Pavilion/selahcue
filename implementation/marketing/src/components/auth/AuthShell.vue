<script setup lang="ts">
/**
 * The bare centred auth card used by /signin, /verify and /reset.
 *
 * Handoff §2.1: chrome is cloned from Sign in `505:124` — brand lockup, one card, no
 * nav and no footer. The routes set `meta.bare` so `App.vue` drops the site chrome;
 * someone who arrived from an email is mid-task, and a nav bar here is an invitation to
 * wander off before the account is verified.
 *
 * Geometry lives in `assets/styles/auth.css` (§2.3, "do not re-derive").
 *
 * `align="center"` is for V1 and V2 only (Figma 743:125, 743:139), where the status disc,
 * the title and the body are centred; every other state, Sign in and Reset included, is
 * left-aligned. It is a modifier class and nothing more: the CSS reaches those three
 * elements and leaves banners, buttons, notes and the footer where they were.
 */
import { computed } from 'vue'

const props = defineProps<{
  /** `center` centres the disc, title and body; `start` (the default) is the left-aligned card. */
  align?: 'start' | 'center'
}>()

const centred = computed(() => props.align === 'center')
</script>

<template>
  <div class="au-page">
    <div class="au-brand">
      <!-- Decorative: the adjacent word mark is the accessible name. -->
      <img src="/selahcue-logo.png" alt="" aria-hidden="true" class="au-brand-logo" />
      <span class="au-brand-name">SelahCue</span>
    </div>

    <div :class="['au-card', { 'au-card-center': centred }]">
      <slot />
    </div>

    <p v-if="$slots.footer" class="au-footer-link">
      <slot name="footer" />
    </p>
  </div>
</template>
