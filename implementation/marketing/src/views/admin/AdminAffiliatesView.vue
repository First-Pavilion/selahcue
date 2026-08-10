<script setup lang="ts">
import { ref } from 'vue'
import AdminShell from '@/components/AdminShell.vue'
import DataTable from '@/components/DataTable.vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'

const columns = [
  { key: 'name', label: 'Affiliate Name / Email', sortable: true },
  { key: 'code', label: 'Referral Code' },
  { key: 'clicks', label: 'Clicks', sortable: true },
  { key: 'signups', label: 'Paid Signups', sortable: true },
  { key: 'earned', label: 'Total Earned', sortable: true },
  { key: 'owed', label: 'Pending Balance', sortable: true },
  { key: 'status', label: 'Status' }
]

const affiliates = ref([
  { name: 'John Worship (john@worship.org)', code: 'john-worship', clicks: 342, signups: 12, earned: '$684.00', owed: '$142.50', status: 'Active' },
  { name: 'Church Tech Today (info@churchtech.com)', code: 'churchtech', clicks: 1240, signups: 48, earned: '$2,410.00', owed: '$380.00', status: 'Active' },
  { name: 'David Miller (david@worshipmedia.io)', code: 'dmiller', clicks: 88, signups: 2, earned: '$94.00', owed: '$38.00', status: 'Active' }
])
</script>

<template>
  <AdminShell>
    <template #title>Affiliate Partners</template>

    <DataTable :columns="columns" :items="affiliates" searchPlaceholder="Search affiliates...">
      <template #table-actions>
        <UiButton variant="primary" size="sm">+ Add Affiliate</UiButton>
        <UiButton variant="outline" size="sm" to="/admin/payouts">Run Payout Cycle</UiButton>
      </template>

      <template #cell-name="{ row }">
        <span class="font-medium">{{ row.name }}</span>
      </template>

      <template #cell-code="{ row }">
        <code>{{ row.code }}</code>
      </template>

      <template #cell-owed="{ row }">
        <span class="font-bold highlight">{{ row.owed }}</span>
      </template>

      <template #cell-status="{ row }">
        <UiBadge variant="preview">{{ row.status }}</UiBadge>
      </template>
    </DataTable>
  </AdminShell>
</template>

<style scoped>
.font-medium { font-weight: 600; color: var(--sc-text); }
.font-bold { font-weight: 700; color: var(--sc-text); }
.highlight { color: var(--sc-preview); }
code { font-family: monospace; color: var(--sc-gold); font-weight: 600; }
</style>
