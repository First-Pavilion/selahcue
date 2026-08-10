<script setup lang="ts">
import { ref } from 'vue'
import AffiliateShell from '@/components/AffiliateShell.vue'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'
import Toast from '@/components/Toast.vue'

const name = ref('John Doe')
const email = ref('john@worship.org')
const paypalEmail = ref('john@worship.org')
const toastShow = ref(false)

const saveSettings = () => {
  toastShow.value = true
}
</script>

<template>
  <AffiliateShell>
    <div class="container">
      <div class="page-header">
        <h1>Affiliate Account Settings</h1>
        <p>Manage your profile, payout destinations, and email preferences.</p>
      </div>

      <div class="settings-card">
        <form @submit.prevent="saveSettings">
          <h2>Personal Profile</h2>
          <FormField v-model="name" label="Full Name" required />
          <FormField v-model="email" type="email" label="Email Address" required />

          <h2 class="section-divider">Payout Method</h2>
          <FormField v-model="paypalEmail" type="email" label="PayPal Account Email" hint="Payouts are sent to this address on the 1st of every month." required />

          <div class="form-actions">
            <UiButton variant="gradient" size="md">Save Settings</UiButton>
          </div>
        </form>
      </div>
    </div>
    <Toast v-model:show="toastShow" message="Affiliate settings saved successfully!" />
  </AffiliateShell>
</template>

<style scoped>
.container { max-width: 800px; margin: 0 auto; padding: 0 24px; }
.page-header { margin-bottom: 32px; }
.page-header h1 { font-size: 28px; font-weight: 700; color: var(--sc-text); margin: 0 0 8px 0; }
.page-header p { font-size: 15px; color: var(--sc-text-secondary); margin: 0; }

.settings-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 36px; }
.settings-card h2 { font-size: 18px; font-weight: 700; color: var(--sc-text); margin: 0 0 20px 0; }
.section-divider { margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--sc-border); }
.form-actions { margin-top: 28px; }
</style>
