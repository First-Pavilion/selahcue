<script setup lang="ts">
import { useRoute } from 'vue-router'
import UiBadge from './UiBadge.vue'

const route = useRoute()

const adminNav = [
  { path: '/admin', label: 'Overview', icon: '📊' },
  { path: '/admin/customers', label: 'Customers', icon: '🏢' },
  { path: '/admin/users', label: 'Users', icon: '👤' },
  { path: '/admin/subscriptions', label: 'Subscriptions', icon: '💳' },
  { path: '/admin/licenses', label: 'Licenses', icon: '🔑' },
  { path: '/admin/affiliates', label: 'Affiliates', icon: '🤝' },
  { path: '/admin/payouts', label: 'Payouts', icon: '💰' },
  { path: '/admin/settings', label: 'Settings', icon: '⚙️' }
]

const isActive = (path: string) => {
  if (path === '/admin') return route.path === '/admin'
  return route.path.startsWith(path)
}
</script>

<template>
  <div class="admin-shell">
    <!-- Admin Sidebar -->
    <aside class="admin-sidebar">
      <div class="sidebar-brand">
        <img src="/selahcue-logo.png" alt="SelahCue logo" class="brand-img" />
        <span class="brand-name">SelahCue</span>
        <UiBadge variant="live" size="sm">ADMIN</UiBadge>
      </div>

      <nav class="sidebar-menu">
        <router-link
          v-for="item in adminNav"
          :key="item.path"
          :to="item.path"
          :class="['menu-item', { active: isActive(item.path) }]"
        >
          <span class="menu-icon">{{ item.icon }}</span>
          <span class="menu-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-user">
        <div class="user-avatar">SA</div>
        <div class="user-info">
          <span class="user-name">Staff Admin</span>
          <span class="user-email">admin@selahcue.app</span>
        </div>
      </div>
    </aside>

    <!-- Admin Main Body -->
    <div class="admin-body">
      <header class="admin-topbar">
        <div class="topbar-left">
          <h1 class="page-title"><slot name="title">Admin Console</slot></h1>
        </div>

        <div class="topbar-right">
          <div class="search-box">
            <svg viewBox="0 0 20 20" fill="currentColor" class="search-icon">
              <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/>
            </svg>
            <input type="text" class="topbar-search" placeholder="Search customers, keys, licenses..." />
          </div>

          <button type="button" class="icon-btn" aria-label="Notifications">
            🔔
          </button>
        </div>
      </header>

      <main class="admin-content">
        <slot></slot>
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-shell {
  display: flex;
  min-height: 100vh;
  background: var(--sc-base);
}

/* Sidebar */
.admin-sidebar {
  width: 248px;
  background: var(--sc-surface);
  border-right: 1px solid var(--sc-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  height: 100vh;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px;
  border-bottom: 1px solid var(--sc-border);
}

.brand-img {
  height: 28px;
}

.brand-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--sc-text);
}

.sidebar-menu {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 12px;
  flex-grow: 1;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 10px;
  color: var(--sc-text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.menu-item:hover {
  background: var(--sc-elevated);
  color: var(--sc-text);
}

.menu-item.active {
  background: var(--sc-accent-soft);
  color: var(--sc-primary);
  font-weight: 600;
}

.menu-icon {
  font-size: 16px;
}

.sidebar-user {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--sc-border);
  background: var(--sc-inset);
}

.user-avatar {
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

.user-info {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--sc-text);
}

.user-email {
  font-size: 11px;
  color: var(--sc-text-muted);
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}

/* Main Body */
.admin-body {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.admin-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: var(--sc-surface);
  border-bottom: 1px solid var(--sc-border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.search-box {
  position: relative;
  width: 280px;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--sc-text-muted);
}

.topbar-search {
  width: 100%;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  padding: 8px 12px 8px 36px;
  font-family: var(--font-family);
  font-size: 13px;
  color: var(--sc-text);
  box-sizing: border-box;
}

.topbar-search:focus {
  outline: none;
  border-color: var(--sc-primary);
}

.icon-btn {
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  font-size: 16px;
}

.admin-content {
  padding: 32px;
  flex-grow: 1;
}

@media (max-width: 1024px) {
  .admin-sidebar { width: 72px; }
  .brand-name, .menu-label, .user-info, .sidebar-brand .badge { display: none; }
  .sidebar-user { justify-content: center; padding: 16px 0; }
}
</style>
