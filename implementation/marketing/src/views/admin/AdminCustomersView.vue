<script setup lang="ts">
import { ref } from 'vue'
import AdminShell from '@/components/AdminShell.vue'
import DataTable from '@/components/DataTable.vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'

const columns = [
  { key: 'orgName', label: 'Organization Name', sortable: true },
  { key: 'contact', label: 'Primary Contact', sortable: true },
  { key: 'plan', label: 'Plan Tier', sortable: true },
  { key: 'seats', label: 'Device Seats' },
  { key: 'bibles', label: 'Bible Entitlements' },
  { key: 'status', label: 'Status' },
  { key: 'actions', label: 'Action', align: 'right' as const }
]

const customers = ref([
  { id: '1', orgName: 'Grace Community Church', contact: 'Sarah Jenkins (sarah@grace.org)', plan: 'Pro Annual', seats: '2 / 5', bibles: 'NIV, ESV, NLT', status: 'Active' },
  { id: '2', orgName: 'Redeemer Worship Center', contact: 'Mark Davis (mark@redeemer.org)', plan: 'Pro Monthly', seats: '1 / 5', bibles: 'NIV, ESV', status: 'Active' },
  { id: '3', orgName: 'St. John Lutheran', contact: 'Paul Miller (paul@stjohn.org)', plan: 'Free Tier', seats: '1 / 1', bibles: 'WEB (Bundled)', status: 'Trial' },
  { id: '4', orgName: 'First Baptist Church', contact: 'David Wilson (david@fbc.org)', plan: 'Church Enterprise', seats: '8 / 15', bibles: 'NIV, ESV, NLT, CSB', status: 'Active' },
  { id: '5', orgName: 'Hope Chapel', contact: 'Rachel Adams (rachel@hope.org)', plan: 'Pro Monthly', seats: '0 / 5', bibles: 'None', status: 'Past Due' }
])
</script>

<template>
  <AdminShell>
    <template #title>Customer Organizations</template>

    <DataTable :columns="columns" :items="customers" searchPlaceholder="Search organization name, contact, status...">
      <template #table-actions>
        <UiButton variant="primary" size="sm">+ Add Customer</UiButton>
      </template>

      <template #cell-orgName="{ row }">
        <router-link :to="`/admin/customers/${row.id}`" class="org-link">{{ row.orgName }}</router-link>
      </template>

      <template #cell-status="{ row }">
        <UiBadge :variant="row.status === 'Active' ? 'preview' : row.status === 'Trial' ? 'warn' : 'live'">
          {{ row.status }}
        </UiBadge>
      </template>

      <template #cell-actions="{ row }">
        <router-link :to="`/admin/customers/${row.id}`" class="action-link">View Detail →</router-link>
      </template>
    </DataTable>
  </AdminShell>
</template>

<style scoped>
.org-link { font-weight: 600; color: var(--sc-text); text-decoration: none; }
.org-link:hover { color: var(--sc-primary); text-decoration: underline; }
.action-link { font-size: 13px; color: var(--sc-primary); text-decoration: none; font-weight: 500; }
.action-link:hover { text-decoration: underline; }
</style>
