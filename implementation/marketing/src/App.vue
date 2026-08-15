<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import Navbar from '@/components/Navbar.vue'
import Footer from '@/components/Footer.vue'

const route = useRoute()

/**
 * Routes that opt out of the site chrome via `meta.bare` — currently the /verify and
 * /reset token landings (design §2.1: "bare centred card, no nav/footer"). Someone who
 * arrived from an email is mid-task; a nav bar is an invitation to wander off before the
 * account is verified, and the footer's outbound links are extra places for a
 * token-bearing URL to leak a referrer from.
 */
const isBare = computed(() => route.meta.bare === true)
</script>

<template>
  <div class="app-shell">
    <Navbar v-if="!isBare" />
    <main class="main-content">
      <Suspense>
        <template #default>
          <RouterView />
        </template>
        <template #fallback>
          <div class="loading">Loading...</div>
        </template>
      </Suspense>
    </main>
    <Footer v-if="!isBare" />
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-grow: 1;
  font-size: 1.2rem;
  color: var(--sc-text-muted);
}
</style>
