<script setup lang="ts">
import { ref } from 'vue'
import AdminShell from '@/components/AdminShell.vue'
import DataTable from '@/components/DataTable.vue'
import UiBadge from '@/components/UiBadge.vue'

const kpis = [
  { label: 'Active Customers', value: '142', delta: '+12 this month', isGood: true },
  { label: 'Monthly Recurring Revenue', value: '$2,698', delta: '+18% ARR growth', isGood: true },
  { label: 'Active License Keys', value: '186', delta: '5 expiring soon', isGood: false },
  { label: 'Bible Entitlements Granted', value: '412', delta: 'NIV & ESV top', isGood: true }
]

const recentSignupsColumns = [
  { key: 'customer', label: 'Organization / Customer', sortable: true },
  { key: 'plan', label: 'Plan' },
  { key: 'keyPrefix', label: 'License Key Prefix' },
  { key: 'joined', label: 'Joined Date', sortable: true },
  { key: 'status', label: 'Status' }
]

const recentSignups = ref([
  { customer: 'Grace Community Church', plan: 'Pro Annual', keyPrefix: 'sc_live_9f82...', joined: 'Aug 8, 2026', status: 'Active' },
  { customer: 'Redeemer Worship Center', plan: 'Pro Monthly', keyPrefix: 'sc_live_3k91...', joined: 'Aug 7, 2026', status: 'Active' },
  { customer: 'St. John Lutheran', plan: 'Free Tier', keyPrefix: 'sc_free_1m20...', joined: 'Aug 6, 2026', status: 'Trial' },
  { customer: 'First Baptist Church', plan: 'Church Enterprise', keyPrefix: 'sc_live_88a2...', joined: 'Aug 4, 2026', status: 'Active' }
])
</script>

<template>
  <AdminShell>
    <template #title>Operational Overview</template>

    <!-- KPI Row -->
    <div class="kpi-grid">
      <div v-for="kpi in kpis" :key="kpi.label" class="kpi-card">
        <span class="kpi-label">{{ kpi.label }}</span>
        <span class="kpi-value">{{ kpi.value }}</span>
        <span :class="['kpi-delta', kpi.isGood ? 'positive' : 'warning']">{{ kpi.delta }}</span>
      </div>
    </div>

    <!-- Alert / System Status Banner -->
    <div class="alert-strip">
      <div class="alert-item">
        <span class="alert-icon">⚠️</span>
        <div>
          <strong>5 App Keys Expiring Soon:</strong>
          <span> 5 customer trial/pilot keys expire within the next 7 days. [View Keys]</span>
        </div>
      </div>
    </div>

    <!-- Table Section -->
    <div class="section-block">
      <div class="block-title">
        <h2>Recent Customer Signups</h2>
      </div>

      <DataTable :columns="recentSignupsColumns" :items="recentSignups" searchPlaceholder="Search recent customers...">
        <template #cell-customer="{ row }">
          <router-link to="/admin/customers/1" class="customer-link">{{ row.customer }}</router-link>
        </template>
        <template #cell-keyPrefix="{ row }">
          <code>{{ row.keyPrefix }}</code>
        </template>
        <template #cell-status="{ row }">
          <UiBadge :variant="row.status === 'Active' ? 'preview' : 'warn'">
            {{ row.status }}
          </UiBadge>
        </template>
      </DataTable>
    </div>
  </AdminShell>
</template>

<style scoped>
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 32px; }
.kpi-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 14px; padding: 24px; display: flex; flex-direction: column; gap: 6px; }
.kpi-label { font-size: 12px; font-weight: 600; color: var(--sc-text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-value { font-size: 32px; font-weight: 800; color: var(--sc-text); }
.kpi-delta { font-size: 13px; font-weight: 600; }
.kpi-delta.positive { color: var(--sc-preview); }
.kpi-delta.warning { color: var(--sc-warn); }

.alert-strip { background: var(--sc-warn-soft); border: 1px solid var(--sc-warn-border); border-radius: 12px; padding: 16px 20px; margin-bottom: 32px; }
.alert-item { display: flex; align-items: center; gap: 12px; font-size: 14px; color: var(--sc-text); }

.section-block h2 { font-size: 18px; font-weight: 700; color: var(--sc-text); margin: 0 0 16px 0; }
.customer-link { font-weight: 600; color: var(--sc-text); text-decoration: none; }
.customer-link:hover { color: var(--sc-primary); text-decoration: underline; }
code { font-family: monospace; color: var(--sc-gold); }

@media (max-width: 1100px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
