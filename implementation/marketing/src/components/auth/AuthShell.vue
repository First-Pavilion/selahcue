<script setup lang="ts">
/**
 * The bare centred auth card used by /verify and /reset.
 *
 * Handoff §2.1: chrome is cloned from Sign in `505:124` — brand lockup, one card, no
 * nav and no footer. The routes set `meta.bare` so `App.vue` drops the site chrome;
 * someone who arrived from an email is mid-task, and a nav bar here is an invitation to
 * wander off before the account is verified.
 *
 * Geometry lives in `assets/styles/auth.css` (§2.3, "do not re-derive").
 */
</script>

<template>
  <div class="au-page">
    <div class="au-brand">
      <!-- Decorative: the adjacent word mark is the accessible name. -->
      <img src="/selahcue-logo.png" alt="" aria-hidden="true" class="au-brand-logo" />
      <span class="au-brand-name">SelahCue</span>
    </div>

    <div class="au-card">
      <slot />
    </div>

    <p v-if="$slots.footer" class="au-footer-link">
      <slot name="footer" />
    </p>
  </div>
</template>
