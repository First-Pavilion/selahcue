<script setup lang="ts">
import { ref } from 'vue'
import AffiliateShell from '@/components/AffiliateShell.vue'
import DataTable from '@/components/DataTable.vue'
import UiBadge from '@/components/UiBadge.vue'

const columns = [
  { key: 'payoutId', label: 'Payout ID', sortable: true },
  { key: 'date', label: 'Payout Date', sortable: true },
  { key: 'method', label: 'Method / Destination' },
  { key: 'amount', label: 'Amount', sortable: true },
  { key: 'status', label: 'Status' }
]

const payouts = ref([
  { payoutId: 'PAY-2026-007', date: 'Aug 1, 2026', method: 'PayPal (john@worship.org)', amount: '$184.20', status: 'Paid' },
  { payoutId: 'PAY-2026-006', date: 'Jul 1, 2026', method: 'PayPal (john@worship.org)', amount: '$162.00', status: 'Paid' },
  { payoutId: 'PAY-2026-005', date: 'Jun 1, 2026', method: 'PayPal (john@worship.org)', amount: '$145.80', status: 'Paid' },
  { payoutId: 'PAY-2026-004', date: 'May 1, 2026', method: 'PayPal (john@worship.org)', amount: '$192.00', status: 'Paid' }
])
</script>

<template>
  <AffiliateShell>
    <div class="container">
      <div class="page-header">
        <h1>Commission Payouts</h1>
        <p>View your lifetime earnings ledger and download payout receipts.</p>
      </div>

      <div class="payout-summary-cards">
        <div class="summary-card">
          <span class="card-label">Available Balance</span>
          <span class="card-value highlight">$142.50</span>
          <span class="card-sub">Next payout on Sep 1, 2026</span>
        </div>
        <div class="summary-card">
          <span class="card-label">Lifetime Paid Out</span>
          <span class="card-value">$684.00</span>
          <span class="card-sub">4 payouts completed</span>
        </div>
        <div class="summary-card">
          <span class="card-label">Payout Method</span>
          <span class="card-value sm">PayPal</span>
          <span class="card-sub">john@worship.org</span>
        </div>
      </div>

      <DataTable :columns="columns" :items="payouts" searchPlaceholder="Search payouts...">
        <template #cell-payoutId="{ row }">
          <code class="font-mono">{{ row.payoutId }}</code>
        </template>
        <template #cell-amount="{ row }">
          <span class="font-bold">{{ row.amount }}</span>
        </template>
        <template #cell-status="{ row }">
          <UiBadge variant="preview">{{ row.status }}</UiBadge>
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

.payout-summary-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 36px; }
.summary-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 24px; display: flex; flex-direction: column; gap: 6px; }
.card-label { font-size: 12px; font-weight: 600; color: var(--sc-text-muted); text-transform: uppercase; }
.card-value { font-size: 32px; font-weight: 800; color: var(--sc-text); }
.card-value.sm { font-size: 24px; }
.card-value.highlight { color: var(--sc-preview); }
.card-sub { font-size: 12px; color: var(--sc-text-muted); }

.font-mono { font-family: monospace; font-weight: 600; color: var(--sc-gold); }
.font-bold { font-weight: 700; color: var(--sc-text); }

@media (max-width: 768px) {
  .payout-summary-cards { grid-template-columns: 1fr; }
}
</style>
