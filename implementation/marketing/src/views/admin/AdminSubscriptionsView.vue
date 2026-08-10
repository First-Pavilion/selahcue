<script setup lang="ts">
import { ref } from 'vue'
import AdminShell from '@/components/AdminShell.vue'
import DataTable from '@/components/DataTable.vue'
import UiBadge from '@/components/UiBadge.vue'

const columns = [
  { key: 'customer', label: 'Organization', sortable: true },
  { key: 'plan', label: 'Plan', sortable: true },
  { key: 'mrr', label: 'MRR Value', sortable: true },
  { key: 'billingCycle', label: 'Cycle' },
  { key: 'nextRenewal', label: 'Renewal Date', sortable: true },
  { key: 'status', label: 'Status' }
]

const subscriptions = ref([
  { customer: 'Grace Community Church', plan: 'Pro Tier', mrr: '$15.00/mo', billingCycle: 'Annual ($180/yr)', nextRenewal: 'Sep 1, 2026', status: 'Active' },
  { customer: 'Redeemer Worship Center', plan: 'Pro Tier', mrr: '$19.00/mo', billingCycle: 'Monthly', nextRenewal: 'Aug 28, 2026', status: 'Active' },
  { customer: 'First Baptist Church', plan: 'Church Enterprise', mrr: '$99.00/mo', billingCycle: 'Annual ($1,188/yr)', nextRenewal: 'Jan 15, 2027', status: 'Active' },
  { customer: 'Hope Chapel', plan: 'Pro Tier', mrr: '$19.00/mo', billingCycle: 'Monthly', nextRenewal: 'Aug 1, 2026', status: 'Past Due' }
])
</script>

<template>
  <AdminShell>
    <template #title>Subscriptions &amp; Revenue</template>

    <div class="sub-kpis">
      <div class="kpi-box">
        <span class="label">Total MRR</span>
        <span class="val">$2,698.00</span>
      </div>
      <div class="kpi-box">
        <span class="label">Annual Run Rate (ARR)</span>
        <span class="val">$32,376.00</span>
      </div>
      <div class="kpi-box">
        <span class="label">Active Paid Subscribers</span>
        <span class="val">142</span>
      </div>
    </div>

    <DataTable :columns="columns" :items="subscriptions" searchPlaceholder="Search subscriptions...">
      <template #cell-customer="{ row }">
        <span class="font-medium">{{ row.customer }}</span>
      </template>
      <template #cell-mrr="{ row }">
        <span class="font-bold">{{ row.mrr }}</span>
      </template>
      <template #cell-status="{ row }">
        <UiBadge :variant="row.status === 'Active' ? 'preview' : 'live'">
          {{ row.status }}
        </UiBadge>
      </template>
    </DataTable>
  </AdminShell>
</template>

<style scoped>
.sub-kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 32px; }
.kpi-box { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 14px; padding: 20px; display: flex; flex-direction: column; gap: 4px; }
.kpi-box .label { font-size: 12px; font-weight: 600; color: var(--sc-text-muted); text-transform: uppercase; }
.kpi-box .val { font-size: 28px; font-weight: 800; color: var(--sc-text); }
.font-medium { font-weight: 600; color: var(--sc-text); }
.font-bold { font-weight: 700; color: var(--sc-text); }
</style>
