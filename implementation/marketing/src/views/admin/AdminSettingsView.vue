<script setup lang="ts">
import { ref } from 'vue'
import AdminShell from '@/components/AdminShell.vue'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'
import Toast from '@/components/Toast.vue'

const commissionRate = ref('20')
const cookieDays = ref('60')
const minPayout = ref('50')
const toastShow = ref(false)

const saveSettings = () => {
  toastShow.value = true
}
</script>

<template>
  <AdminShell>
    <template #title>Admin System Settings</template>

    <div class="settings-grid">
      <div class="settings-card">
        <h2>Affiliate Program Configuration</h2>
        <form @submit.prevent="saveSettings">
          <FormField v-model="commissionRate" label="Recurring Commission Rate (%)" hint="Percentage of paid subscription credited to affiliate for 12 months." required />
          <FormField v-model="cookieDays" label="Cookie Attribution Window (Days)" hint="Last-click cookie duration for referral tracking." required />
          <FormField v-model="minPayout" label="Minimum Payout Threshold ($)" hint="Minimum balance before an affiliate is eligible for automatic monthly payout." required />

          <div class="form-actions">
            <UiButton variant="gradient" size="md">Save Program Settings</UiButton>
          </div>
        </form>
      </div>

      <div class="settings-card">
        <h2>Licensing &amp; Security Defaults</h2>
        <div class="setting-item">
          <div>
            <strong>Offline Grace Period:</strong>
            <p>Number of days a venue app retains offline access after entitlement expiry.</p>
          </div>
          <span class="setting-val">30 Days</span>
        </div>
        <div class="setting-item">
          <div>
            <strong>Hardware Fingerprint Guard:</strong>
            <p>Maximum device finger-print changes allowed per year per seat.</p>
          </div>
          <span class="setting-val">3 Changes</span>
        </div>
      </div>
    </div>

    <Toast v-model:show="toastShow" message="Admin settings updated successfully!" />
  </AdminShell>
</template>

<style scoped>
.settings-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 28px; }
.settings-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 32px; }
.settings-card h2 { font-size: 18px; font-weight: 700; color: var(--sc-text); margin: 0 0 24px 0; }

.setting-item { display: flex; justify-content: space-between; align-items: center; padding: 16px 0; border-bottom: 1px solid var(--sc-border); }
.setting-item strong { font-size: 14px; color: var(--sc-text); display: block; margin-bottom: 2px; }
.setting-item p { font-size: 13px; color: var(--sc-text-secondary); margin: 0; }
.setting-val { font-size: 14px; font-weight: 700; color: var(--sc-primary); }

.form-actions { margin-top: 24px; }

@media (max-width: 900px) {
  .settings-grid { grid-template-columns: 1fr; }
}
</style>
