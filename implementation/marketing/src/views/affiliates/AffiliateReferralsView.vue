<script setup lang="ts">
import { ref } from 'vue'
import AffiliateShell from '@/components/AffiliateShell.vue'
import DataTable from '@/components/DataTable.vue'
import UiBadge from '@/components/UiBadge.vue'

const columns = [
  { key: 'church', label: 'Referred Church', sortable: true },
  { key: 'plan', label: 'Plan', sortable: true },
  { key: 'joined', label: 'Joined Date', sortable: true },
  { key: 'mrr', label: 'Plan Value', sortable: true },
  { key: 'commission', label: 'Your Commission (20%)', sortable: true },
  { key: 'status', label: 'Status' }
]

const referrals = ref([
  { church: 'Grace Fellowship', plan: 'Pro Annual', joined: 'Aug 2, 2026', mrr: '$15.00/mo', commission: '$3.00/mo', status: 'Active' },
  { church: 'Hope Chapel', plan: 'Pro Monthly', joined: 'Jul 28, 2026', mrr: '$19.00/mo', commission: '$3.80/mo', status: 'Active' },
  { church: 'Calvary Worship Center', plan: 'Pro Monthly', joined: 'Jul 15, 2026', mrr: '$19.00/mo', commission: '$3.80/mo', status: 'Active' },
  { church: 'Trinity Assembly', plan: 'Pro Annual', joined: 'Jun 10, 2026', mrr: '$15.00/mo', commission: '$3.00/mo', status: 'Active' },
  { church: 'New Life Center', plan: 'Free Plan', joined: 'Jun 30, 2026', mrr: '$0.00', commission: '$0.00', status: 'Pending Upgrade' },
  { church: 'Cornerstone Church', plan: 'Pro Monthly', joined: 'May 12, 2026', mrr: '$19.00/mo', commission: '$3.80/mo', status: 'Active' }
])
</script>

<template>
  <AffiliateShell>
    <div class="container">
      <div class="page-header">
        <h1>Referred Churches</h1>
        <p>A complete list of churches that signed up through your referral link.</p>
      </div>

      <DataTable :columns="columns" :items="referrals" searchPlaceholder="Search referred churches...">
        <template #cell-church="{ row }">
          <span class="font-medium">{{ row.church }}</span>
        </template>
        <template #cell-commission="{ row }">
          <span class="font-bold highlight">{{ row.commission }}</span>
        </template>
        <template #cell-status="{ row }">
          <UiBadge :variant="row.status === 'Active' ? 'preview' : 'warn'">
            {{ row.status }}
          </UiBadge>
        </template>
      </DataTable>
    </div>
  </AffiliateShell>
</template>

<style scoped>
.container { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
.page-header { margin-bottom: 32px; }
.page-header h1 { font-size: 28px; font-weight: 700; color: var(--sc-text); margin: 0 0 8px 0; }
.page-header p { font-size: 15px; color: var(--sc-text-secondary); margin: 0; }
.font-medium { font-weight: 600; color: var(--sc-text); }
.font-bold { font-weight: 700; }
.highlight { color: var(--sc-preview); }
</style>
