<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import AdminShell from '@/components/AdminShell.vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const route = useRoute()
const activeTab = ref('summary')
const showRevokeDialog = ref(false)

const customer = ref({
  id: route.params.id || '1',
  orgName: 'Grace Community Church',
  status: 'Active',
  plan: 'Pro Annual ($180/yr)',
  contact: 'Sarah Jenkins',
  email: 'sarah@grace.org',
  country: 'United States',
  joined: 'March 15, 2025',
  keyPrefix: 'sc_live_9f82k3m4n5p6q7r8s9t0',
  seatsUsed: 2,
  seatsTotal: 5
})

const devices = ref([
  { name: 'Sanctuary Main PC', os: 'Windows 11 Pro', ip: '192.168.1.104', lastActive: 'Today at 10:45 AM' },
  { name: 'Youth Room Mac Studio', os: 'macOS Sonoma', ip: '192.168.1.112', lastActive: 'Yesterday at 4:15 PM' }
])

const bibles = ref([
  { name: 'New International Version (NIV)', publisher: 'Biblica, Inc.', status: 'Active', expires: '1 Sep 2027' },
  { name: 'English Standard Version (ESV)', publisher: 'Crossway', status: 'Active', expires: '1 Sep 2027' },
  { name: 'New Living Translation (NLT)', publisher: 'Tyndale', status: 'Expiring Soon', expires: '28 Aug 2026' }
])
</script>

<template>
  <AdminShell>
    <template #title>
      <div class="header-with-back">
        <router-link to="/admin/customers" class="back-link">← Customers</router-link>
        <span>{{ customer.orgName }}</span>
        <UiBadge variant="preview">{{ customer.status }}</UiBadge>
      </div>
    </template>

    <div class="detail-layout">
      <!-- Left Main Column -->
      <div class="main-col">
        <!-- Detail Header Box -->
        <div class="detail-header-card">
          <div class="info-grid">
            <div>
              <span class="label">Primary Contact</span>
              <span class="val">{{ customer.contact }} ({{ customer.email }})</span>
            </div>
            <div>
              <span class="label">Current Plan</span>
              <span class="val highlight">{{ customer.plan }}</span>
            </div>
            <div>
              <span class="label">Country / Region</span>
              <span class="val">{{ customer.country }}</span>
            </div>
            <div>
              <span class="label">Member Since</span>
              <span class="val">{{ customer.joined }}</span>
            </div>
          </div>
        </div>

        <!-- Section Tabs -->
        <div class="section-tabs">
          <button 
            v-for="tab in ['summary', 'keys', 'devices', 'bibles', 'notes']" 
            :key="tab"
            :class="['tab-btn', { active: activeTab === tab }]"
            @click="activeTab = tab"
          >
            {{ tab.toUpperCase() }}
          </button>
        </div>

        <!-- Devices Section -->
        <div v-if="activeTab === 'summary' || activeTab === 'devices'" class="panel-card">
          <div class="panel-header">
            <h3>Registered Venue Devices ({{ customer.seatsUsed }} / {{ customer.seatsTotal }})</h3>
          </div>
          <table class="detail-table">
            <thead>
              <tr>
                <th>Device Name</th>
                <th>OS</th>
                <th>IP Address</th>
                <th>Last Active</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in devices" :key="d.name">
                <td class="font-medium">{{ d.name }}</td>
                <td>{{ d.os }}</td>
                <td><code>{{ d.ip }}</code></td>
                <td>{{ d.lastActive }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Bible Entitlements Section -->
        <div v-if="activeTab === 'summary' || activeTab === 'bibles'" class="panel-card">
          <div class="panel-header">
            <h3>Granted Bible Entitlements</h3>
            <UiButton variant="outline" size="sm">+ Grant Entitlement</UiButton>
          </div>
          <table class="detail-table">
            <thead>
              <tr>
                <th>Translation</th>
                <th>Publisher / Rights Holder</th>
                <th>Status</th>
                <th>Expiration Date</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in bibles" :key="b.name">
                <td class="font-medium">📖 {{ b.name }}</td>
                <td>{{ b.publisher }}</td>
                <td><UiBadge :variant="b.status === 'Active' ? 'preview' : 'warn'">{{ b.status }}</UiBadge></td>
                <td>{{ b.expires }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Right Action Sidebar -->
      <aside class="action-sidebar">
        <div class="sidebar-card">
          <h3>Staff Actions</h3>
          <div class="btn-stack">
            <UiButton variant="outline" size="md">Issue App Key</UiButton>
            <UiButton variant="outline" size="md">Grant Bible Entitlement</UiButton>
            <UiButton variant="outline" size="md">Impersonate Customer</UiButton>
            <UiButton variant="ghost" size="md" class="danger-text" @click="showRevokeDialog = true">
              Revoke License Key
            </UiButton>
          </div>
        </div>

        <div class="sidebar-card">
          <h3>App License Key</h3>
          <code class="key-display">{{ customer.keyPrefix }}</code>
          <span class="key-sub">{{ customer.seatsUsed }} of {{ customer.seatsTotal }} seats active</span>
        </div>
      </aside>
    </div>

    <ConfirmDialog
      v-model:show="showRevokeDialog"
      title="Revoke Customer License Key?"
      description="Revoking this key will immediately block future activations for Grace Community Church."
      :consequences="['Active venue devices will lose Pro access on next sync', 'New activations will be rejected']"
      confirmLabel="Revoke Key"
      requireType="cancel"
      variant="danger"
    />
  </AdminShell>
</template>

<style scoped>
.header-with-back { display: flex; align-items: center; gap: 12px; }
.back-link { font-size: 14px; color: var(--sc-primary); text-decoration: none; font-weight: 500; }

.detail-layout { display: grid; grid-template-columns: 1fr 300px; gap: 28px; align-items: start; }
.main-col { display: flex; flex-direction: column; gap: 24px; }

.detail-header-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 28px; }
.info-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.info-grid .label { font-size: 12px; color: var(--sc-text-muted); text-transform: uppercase; display: block; margin-bottom: 4px; }
.info-grid .val { font-size: 15px; color: var(--sc-text); font-weight: 500; }
.val.highlight { color: var(--sc-primary); font-weight: 700; }

.section-tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--sc-border); padding-bottom: 8px; }
.tab-btn { background: none; border: none; padding: 8px 16px; font-family: var(--font-family); font-size: 13px; font-weight: 600; color: var(--sc-text-muted); border-radius: 6px; cursor: pointer; }
.tab-btn.active { background: var(--sc-elevated); color: var(--sc-text); }

.panel-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 24px; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.panel-header h3 { font-size: 16px; font-weight: 700; color: var(--sc-text); margin: 0; }

.detail-table { width: 100%; border-collapse: collapse; font-size: 14px; text-align: left; }
.detail-table th { background: var(--sc-elevated); color: var(--sc-text-muted); font-size: 12px; padding: 10px 14px; }
.detail-table td { padding: 12px 14px; border-bottom: 1px solid var(--sc-border); color: var(--sc-text-secondary); }

.action-sidebar { display: flex; flex-direction: column; gap: 20px; }
.sidebar-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 20px; }
.sidebar-card h3 { font-size: 14px; font-weight: 700; color: var(--sc-text); margin: 0 0 16px 0; text-transform: uppercase; letter-spacing: 0.05em; }

.btn-stack { display: flex; flex-direction: column; gap: 10px; }
.btn-stack button { width: 100%; text-align: center; }
.danger-text { color: var(--sc-live) !important; }
.key-display { font-family: monospace; font-size: 13px; color: var(--sc-gold); display: block; margin-bottom: 6px; }
.key-sub { font-size: 12px; color: var(--sc-text-muted); }

@media (max-width: 1024px) {
  .detail-layout { grid-template-columns: 1fr; }
}
</style>
