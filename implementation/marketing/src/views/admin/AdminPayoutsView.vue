<script setup lang="ts">
import { ref } from 'vue'
import AdminShell from '@/components/AdminShell.vue'
import DataTable from '@/components/DataTable.vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import Toast from '@/components/Toast.vue'

const toastShow = ref(false)
const toastMessage = ref('')

const columns = [
  { key: 'affiliate', label: 'Affiliate', sortable: true },
  { key: 'method', label: 'Destination' },
  { key: 'amount', label: 'Amount Owed', sortable: true },
  { key: 'cycle', label: 'Cycle' },
  { key: 'status', label: 'Status' },
  { key: 'action', label: 'Action', align: 'right' as const }
]

const payouts = ref([
  { id: '1', affiliate: 'John Worship (john-worship)', method: 'PayPal (john@worship.org)', amount: '$142.50', cycle: 'August 2026', status: 'Pending Approval' },
  { id: '2', affiliate: 'Church Tech Today (churchtech)', method: 'PayPal (info@churchtech.com)', amount: '$380.00', cycle: 'August 2026', status: 'Pending Approval' }
])

const releasePayout = (row: any) => {
  payouts.value = payouts.value.filter(p => p.id !== row.id)
  toastMessage.value = `Released payout of ${row.amount} to ${row.affiliate}`
  toastShow.value = true
}
</script>

<template>
  <AdminShell>
    <template #title>Affiliate Payout Runs</template>

    <div class="payout-header-box">
      <div>
        <h3>Pending Payout Cycle: August 1, 2026</h3>
        <p>Review and release pending affiliate commissions for the current month.</p>
      </div>
      <UiButton variant="gradient" size="md" @click="toastMessage = 'Released all approved payouts!'; toastShow = true">
        Release All Approved Payouts ($522.50)
      </UiButton>
    </div>

    <DataTable :columns="columns" :items="payouts" searchPlaceholder="Search affiliate payouts...">
      <template #cell-affiliate="{ row }">
        <span class="font-medium">{{ row.affiliate }}</span>
      </template>
      <template #cell-amount="{ row }">
        <span class="font-bold highlight">{{ row.amount }}</span>
      </template>
      <template #cell-status="{ row }">
        <UiBadge variant="warn">{{ row.status }}</UiBadge>
      </template>
      <template #cell-action="{ row }">
        <UiButton variant="primary" size="sm" @click="releasePayout(row)">Release Payout</UiButton>
      </template>
    </DataTable>

    <Toast v-model:show="toastShow" :message="toastMessage" />
  </AdminShell>
</template>

<style scoped>
.payout-header-box { display: flex; justify-content: space-between; align-items: center; background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 24px 28px; margin-bottom: 28px; }
.payout-header-box h3 { font-size: 18px; color: var(--sc-text); margin: 0 0 4px 0; }
.payout-header-box p { font-size: 14px; color: var(--sc-text-secondary); margin: 0; }

.font-medium { font-weight: 600; color: var(--sc-text); }
.font-bold { font-weight: 700; color: var(--sc-text); }
.highlight { color: var(--sc-preview); }
</style>
