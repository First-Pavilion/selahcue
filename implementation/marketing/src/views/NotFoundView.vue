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

/**
 * The root is ALWAYS a <div>: the site shell (App.vue) already provides the page's <main>, and this view is shown both by the
 * catch-all route and, inside the blog / docs / support detail views, when an article slug names nothing. A <main> here
 * nested a second one in the shell's (audit shared-chrome-32, ClickUp 17tnw2b0x3h).
 */
</script>

<template>
  <div class="nf-page">
    <h1 class="nf-title">We couldn't find that page</h1>
    <!-- Says nothing about the visitor's account or devices: this page cannot know anything about either. -->
    <p class="nf-body">The link may be out of date, or the address may have a typo in it.</p>
    <div class="nf-actions">
      <UiButton to="/" variant="primary" size="lg">Go to the home page</UiButton>
      <UiButton to="/support" variant="secondary" size="lg">Contact support</UiButton>
    </div>
  </div>
</template>

<style scoped>
.nf-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 96px var(--page-gutter) 120px;
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

@media (max-width: 767.98px) {
  .nf-page { padding-top: 56px; padding-bottom: 72px; }
  .nf-title { font-size: 1.75rem; }
  .nf-actions { flex-direction: column; }
  .nf-actions > * { width: 100%; }
}
</style>
