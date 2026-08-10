<script setup lang="ts">
import { ref } from 'vue'
import AffiliateShell from '@/components/AffiliateShell.vue'
import UiButton from '@/components/UiButton.vue'
import UiBadge from '@/components/UiBadge.vue'
import DataTable from '@/components/DataTable.vue'
import Toast from '@/components/Toast.vue'

const referralLink = 'https://selahcue.app/?via=john-worship'
const toastShow = ref(false)
const toastMessage = ref('')

const copyLink = () => {
  navigator.clipboard.writeText(referralLink)
  toastMessage.value = 'Referral link copied to clipboard!'
  toastShow.value = true
}

const columns = [
  { key: 'church', label: 'Referred Church', sortable: true },
  { key: 'plan', label: 'Plan', sortable: true },
  { key: 'joined', label: 'Joined Date', sortable: true },
  { key: 'commission', label: 'Monthly Commission', sortable: true },
  { key: 'status', label: 'Status' }
]

const recentReferrals = ref([
  { church: 'Grace Fellowship', plan: 'Pro Annual ($180/yr)', joined: 'Aug 2, 2026', commission: '$3.00/mo', status: 'Active' },
  { church: 'Hope Chapel', plan: 'Pro Monthly ($19/mo)', joined: 'Jul 28, 2026', commission: '$3.80/mo', status: 'Active' },
  { church: 'Calvary Worship', plan: 'Pro Monthly ($19/mo)', joined: 'Jul 15, 2026', commission: '$3.80/mo', status: 'Active' },
  { church: 'New Life Center', plan: 'Free Plan', joined: 'Jun 30, 2026', commission: '$0.00', status: 'Pending Upgrade' }
])
</script>

<template>
  <AffiliateShell>
    <div class="container">
      <div class="dashboard-header">
        <h1>Affiliate Dashboard</h1>
        <p>Track your referral performance, commissions, and upcoming payouts.</p>
      </div>

      <!-- Referral Link Box -->
      <div class="link-banner">
        <div class="banner-text">
          <h3>Your Unique Referral Link</h3>
          <p>Share this link on your website, social media, or directly with church tech teams.</p>
        </div>
        <div class="link-input-group">
          <input type="text" readonly :value="referralLink" class="link-input" />
          <UiButton variant="primary" size="md" @click="copyLink">Copy Link</UiButton>
        </div>
      </div>

      <!-- KPI Grid -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <span class="kpi-title">Total Clicks</span>
          <span class="kpi-value">342</span>
          <span class="kpi-delta positive">↑ 14% vs last month</span>
        </div>

        <div class="kpi-card">
          <span class="kpi-title">Paid Signups</span>
          <span class="kpi-value">12</span>
          <span class="kpi-delta positive">↑ 3 new this month</span>
        </div>

        <div class="kpi-card">
          <span class="kpi-title">Pending Commission</span>
          <span class="kpi-value highlight">$142.50</span>
          <span class="kpi-sub">Payout on Sep 1, 2026</span>
        </div>

        <div class="kpi-card">
          <span class="kpi-title">Lifetime Earnings</span>
          <span class="kpi-value">$684.00</span>
          <span class="kpi-sub">Paid via PayPal</span>
        </div>
      </div>

      <!-- Recent Referrals -->
      <div class="section-block">
        <div class="block-header">
          <h2>Recent Referrals</h2>
          <router-link to="/affiliates/referrals" class="view-all">View All Referrals →</router-link>
        </div>

        <DataTable :columns="columns" :items="recentReferrals" :filterable="false">
          <template #cell-church="{ row }">
            <span class="font-medium">{{ row.church }}</span>
          </template>
          <template #cell-status="{ row }">
            <UiBadge :variant="row.status === 'Active' ? 'preview' : 'warn'">
              {{ row.status }}
            </UiBadge>
          </template>
        </DataTable>
      </div>
    </div>

    <Toast v-model:show="toastShow" :message="toastMessage" />
  </AffiliateShell>
</template>

<style scoped>
.container { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
.dashboard-header { margin-bottom: 32px; }
.dashboard-header h1 { font-size: 28px; font-weight: 700; color: var(--sc-text); margin: 0 0 8px 0; }
.dashboard-header p { font-size: 15px; color: var(--sc-text-secondary); margin: 0; }

.link-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, var(--sc-surface), #1b1938);
  border: 1px solid var(--sc-primary);
  border-radius: 16px;
  padding: 24px 32px;
  margin-bottom: 32px;
}

.banner-text h3 { font-size: 18px; color: var(--sc-text); margin: 0 0 4px 0; }
.banner-text p { font-size: 14px; color: var(--sc-text-secondary); margin: 0; }

.link-input-group { display: flex; gap: 12px; width: 440px; }
.link-input { flex: 1; background: var(--sc-inset); border: 1px solid var(--sc-border); border-radius: 8px; padding: 10px 14px; font-family: monospace; font-size: 13px; color: var(--sc-gold); }

.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 40px; }
.kpi-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 24px; display: flex; flex-direction: column; gap: 6px; }
.kpi-title { font-size: 12px; font-weight: 600; color: var(--sc-text-muted); text-transform: uppercase; }
.kpi-value { font-size: 32px; font-weight: 800; color: var(--sc-text); }
.kpi-value.highlight { color: var(--sc-preview); }
.kpi-delta { font-size: 12px; font-weight: 600; }
.kpi-delta.positive { color: var(--sc-preview); }
.kpi-sub { font-size: 12px; color: var(--sc-text-muted); }

.section-block { margin-bottom: 40px; }
.block-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.block-header h2 { font-size: 20px; font-weight: 700; color: var(--sc-text); margin: 0; }
.view-all { font-size: 14px; color: var(--sc-primary); text-decoration: none; font-weight: 500; }
.view-all:hover { text-decoration: underline; }
.font-medium { font-weight: 600; color: var(--sc-text); }

@media (max-width: 900px) {
  .link-banner { flex-direction: column; align-items: flex-start; gap: 16px; }
  .link-input-group { width: 100%; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
