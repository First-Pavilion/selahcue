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
  position: sticky;
  top: 0;
  z-index: 100;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
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
  transition: all var(--transition-fast);
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

@media (max-width: 900px) {
  .topbar-inner { flex-direction: column; height: auto; padding: 16px 0; gap: 16px; }
  .portal-nav { overflow-x: auto; width: 100%; justify-content: flex-start; }
}
</style>
