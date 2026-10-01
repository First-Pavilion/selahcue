<script setup lang="ts">
import { useRoute } from 'vue-router'
import UiBadge from './UiBadge.vue'

const route = useRoute()

const portalNav = [
  { path: '/affiliates/dashboard', label: 'Dashboard' },
  { path: '/affiliates/referrals', label: 'Referrals' },
  { path: '/affiliates/payouts', label: 'Payouts' },
  { path: '/affiliates/resources', label: 'Resources' },
  { path: '/affiliates/settings', label: 'Settings' },
  { path: '/affiliates/help', label: 'Help & FAQ' }
]

const isActive = (path: string) => route.path === path
</script>

<template>
  <div class="affiliate-shell">
    <header class="affiliate-topbar">
      <div class="container topbar-inner">
        <div class="brand-lockup">
          <img src="/selahcue-logo.png" alt="SelahCue logo" class="brand-logo" />
          <span class="brand-text">SelahCue</span>
          <UiBadge variant="featured" size="sm">AFFILIATES</UiBadge>
        </div>

        <nav class="portal-nav">
          <router-link
            v-for="item in portalNav"
            :key="item.path"
            :to="item.path"
            :class="['nav-link', { active: isActive(item.path) }]"
          >
            {{ item.label }}
          </router-link>
        </nav>

        <div class="user-profile">
          <span class="balance-chip">$142.50 Pending</span>
          <div class="avatar">JD</div>
        </div>
      </div>
    </header>

    <main class="affiliate-content">
      <slot></slot>
    </main>
  </div>
</template>

<style scoped>
.affiliate-shell {
  min-height: 100vh;
  background: var(--sc-base);
}

.affiliate-topbar {
  background: var(--sc-surface);
  border-bottom: 1px solid var(--sc-border);
  /* Below the sticky site navbar (z-index 100), not stacked over it. */
  position: sticky;
  top: var(--nav-height);
  z-index: 90;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--page-gutter);
}

.topbar-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 72px;
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  height: 28px;
}

.brand-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--sc-text);
}

.portal-nav {
  display: flex;
  gap: 6px;
}

.nav-link {
  color: var(--sc-text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  padding: 8px 14px;
  border-radius: 8px;
  white-space: nowrap;
  transition: all var(--transition-fast);
}

/* 44px targets once the nav is a swipeable row (and on any coarse pointer). The desktop
   keeps the designed pill height. */
@media (max-width: 1099px), (pointer: coarse) {
  .nav-link {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    padding-block: 0;
  }
}

.nav-link:hover {
  color: var(--sc-text);
  background: var(--sc-elevated);
}

.nav-link.active {
  color: var(--sc-primary);
  background: var(--sc-accent-soft);
  font-weight: 600;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
}

.balance-chip {
  background: var(--sc-preview-soft);
  color: var(--sc-preview);
  border: 1px solid var(--sc-preview-border);
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--sc-primary);
  color: white;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.affiliate-content {
  padding: 40px 0 80px;
}

/* Below 1100 the brand, six portal links and the balance chip no longer fit one row:
   the nav drops to its own full-width, swipeable row. */
@media (max-width: 1099px) {
  /* padding-block, not `padding`: the shorthand would zero the container's side gutters. */
  .topbar-inner { flex-wrap: wrap; height: auto; padding-block: 12px 4px; gap: 8px 16px; }
  .brand-lockup { order: 1; }
  .user-profile { order: 2; margin-left: auto; }
  .portal-nav {
    order: 3;
    flex: 1 0 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    justify-content: flex-start;
    padding-bottom: 8px;
  }
  .portal-nav::-webkit-scrollbar { display: none; }
}

@media (max-width: 767px) {
  /* The profile row sits beside the brand on a phone, the nav strip underneath. */
  .affiliate-topbar { position: static; }
  .affiliate-content { padding: 24px 0 var(--section-pad-sm); }
}
</style>
