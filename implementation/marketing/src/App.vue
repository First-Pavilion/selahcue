<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import Navbar from '@/components/Navbar.vue'
import Footer from '@/components/Footer.vue'

const route = useRoute()
const router = useRouter()
const initialRoutePending = ref(true)
// Router imports resolve before RouterView renders; Suspense alone never sees that
// initial wait. Observe readiness without changing navigation or loading the route twice.
const initialIsBare = router.resolve(router.options.history.location).meta.bare === true
const finishInitialRoute = () => { initialRoutePending.value = false }
// Rejection must also release the fallback so existing navbar navigation can recover.
void router.isReady().then(finishInitialRoute, finishInitialRoute)

/**
 * Routes that opt out of the site chrome via `meta.bare` — currently the /verify and
 * /reset token landings (design §2.1: "bare centred card, no nav/footer"). Someone who
 * arrived from an email is mid-task; a nav bar is an invitation to wander off before the
 * account is verified, and the footer's outbound links are extra places for a
 * token-bearing URL to leak a referrer from.
 */
const isBare = computed(() => route.matched.length === 0 ? initialIsBare : route.meta.bare === true)
</script>

<template>
  <div class="app-shell">
    <Navbar v-if="!isBare" />
    <main class="main-content">
      <div v-if="initialRoutePending" class="loading" role="status">Loading...</div>
      <Suspense v-else>
        <template #default>
          <RouterView />
        </template>
        <template #fallback>
          <div class="loading" role="status">Loading...</div>
        </template>
      </Suspense>
    </main>
    <Footer v-if="!isBare" :class="{ 'is-route-pending': initialRoutePending }" />
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

/* Uma 1400430000277444: reserve only while a loading fallback exists. The footer
   stays below the fold during a cold route import; resolved 404/short Changelog keep
   their original content-driven flex flow, without a permanent main minimum. */
/* A short Pricing page can bring the footer into view on resolution. Keep its
   layout while pending, but avoid counting that first visible placement as a shift. */
.is-route-pending {
  visibility: hidden;
}

.loading {
  min-height: calc(100vh - var(--nav-height));
  box-sizing: border-box;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-grow: 1;
  font-size: 1.2rem;
  /* The secondary ink, not --sc-text-muted: 4.08:1 at this size is below AA and it is not large text. */
  color: var(--sc-text-secondary);
}
</style>
