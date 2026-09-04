<script setup lang="ts">
/**
 * The page for a path with no route.
 *
 * MEDIUM-4 from the PR #17 review. Before this existed the router had no catch-all, so an
 * unmatched path resolved with zero matched components and rendered a BLANK PAGE — no
 * heading, no message, no way onward. That is a dead end, and it was reachable from a
 * link: `/signin?next=/anything` signed the visitor in and left them looking at nothing.
 *
 * The whole point is therefore the way FORWARD, not the apology. FR-552 asks every failure
 * state to offer the next step, and a 404 is a failure state like any other.
 *
 * NO `AuthShell` here on purpose. This route is not part of the auth flow, so it keeps the
 * site's own nav and footer — a visitor who mistyped a marketing URL should be able to
 * carry on browsing rather than be dropped into a bare card.
 */
import UiButton from '@/components/UiButton.vue'
</script>

<template>
  <main class="nf-page">
    <h1 class="nf-title">We couldn't find that page</h1>
    <p class="nf-body">
      The link may be out of date, or the address may have a typo in it. Nothing is wrong
      with your account, and any devices you have activated are still presenting.
    </p>
    <div class="nf-actions">
      <UiButton to="/" variant="primary" size="lg">Go to the home page</UiButton>
      <UiButton to="/support" variant="secondary" size="lg">Contact support</UiButton>
    </div>
  </main>
</template>

<style scoped>
.nf-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 96px 24px 120px;
  text-align: center;
}

.nf-title {
  font-family: var(--font-family);
  font-size: 2rem;
  line-height: 1.25;
  color: var(--sc-text);
  margin: 0 0 16px;
}

.nf-body {
  font-family: var(--font-family);
  color: var(--sc-text-muted);
  margin: 0 0 32px;
}

.nf-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
}
</style>
