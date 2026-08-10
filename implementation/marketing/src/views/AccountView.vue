<script setup lang="ts">
import { ref } from 'vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import Toast from '@/components/Toast.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

// Active Tab
const activeTab = ref('overview') // 'overview' | 'subscription' | 'license' | 'bibles' | 'invoices' | 'settings'

// Loading State
const isLoading = ref(false)

// Toast State
const toastShow = ref(false)
const toastMessage = ref('')
const toastVariant = ref('success')

const showToast = (msg: string, variant = 'success') => {
  toastMessage.value = msg
  toastVariant.value = variant
  toastShow.value = true
}

// Dialog States
const showCancelDialog = ref(false)
const showDeactivateDialog = ref(false)
const targetDevice = ref<any>(null)

// User Data Mock
const user = ref({
  orgName: 'Grace Community Church',
  primaryContact: 'Sarah Jenkins',
  email: 'sarah@gracechurch.org',
  role: 'Organization Owner',
  memberSince: 'March 2025'
})

// Subscription State Mock
const subscription = ref({
  plan: 'Pro',
  status: 'active', // 'active' | 'past_due' | 'cancelled'
  period: 'annual',
  amount: '$15',
  interval: 'month',
  nextBillingDate: '1 Sep 2026',
  seatsUsed: 2,
  seatsTotal: 5
})

// License Key & Devices Mock
const licenseKey = ref('sc_live_9f82k3m4n5p6q7r8s9t0')
const isKeyMasked = ref(true)

const copyLicenseKey = () => {
  navigator.clipboard.writeText(licenseKey.value)
  showToast('License key copied to clipboard!')
}

const devices = ref([
  { id: 'dev_1', name: 'Sanctuary Main PC', os: 'Windows 11 Pro', ip: '192.168.1.104', lastActive: 'Today at 10:45 AM', version: 'v1.2.0', isCurrent: true },
  { id: 'dev_2', name: 'Youth Room Mac Studio', os: 'macOS Sonoma 14.5', ip: '192.168.1.112', lastActive: 'Yesterday at 4:15 PM', version: 'v1.2.0', isCurrent: false }
])

const promptDeactivateDevice = (dev: any) => {
  targetDevice.value = dev
  showDeactivateDialog.value = true
}

const confirmDeactivateDevice = () => {
  if (targetDevice.value) {
    devices.value = devices.value.filter(d => d.id !== targetDevice.value.id)
    subscription.value.seatsUsed -= 1
    showToast(`Deactivated "${targetDevice.value.name}" successfully`)
    targetDevice.value = null
  }
}

const confirmCancelSubscription = () => {
  subscription.value.status = 'cancelled'
  showToast('Subscription cancelled. Pro access ends on 1 Sep 2026.', 'info')
}

// Bible Entitlements Data (CRITICAL GAP COVERED!)
const bibles = ref([
  { id: 'b_1', name: 'New International Version (NIV)', language: 'English', publisher: 'Biblica, Inc.', status: 'active', size: '42 MB', lastSynced: '2 Aug 2026', expires: '1 Sep 2027', isCopyrighted: true },
  { id: 'b_2', name: 'English Standard Version (ESV)', language: 'English', publisher: 'Crossway', status: 'active', size: '38 MB', lastSynced: '2 Aug 2026', expires: '1 Sep 2027', isCopyrighted: true },
  { id: 'b_3', name: 'New Living Translation (NLT)', language: 'English', publisher: 'Tyndale House', status: 'expiring', size: '40 MB', lastSynced: '15 Jul 2026', expires: '28 Aug 2026', isCopyrighted: true }
])

const bundledBibles = [
  { name: 'World English Bible (WEB)', language: 'English', status: 'installed' },
  { name: 'American Standard Version (ASV)', language: 'English', status: 'installed' },
  { name: 'Berean Standard Bible (BSB)', language: 'English', status: 'installed' },
  { name: 'Bible in Basic English (BBE)', language: 'English', status: 'installed' },
  { name: 'Darby Translation', language: 'English', status: 'installed' },
  { name: 'Webster Bible', language: 'English', status: 'installed' }
]

const redownloadBible = (bible: any) => {
  showToast(`Initiated re-download of ${bible.name} (${bible.size})`)
}

// Invoices Mock
const invoices = ref([
  { id: 'INV-2026-008', date: '1 Sep 2025', amount: '$180.00', status: 'Paid', period: 'Annual Pro Plan' },
  { id: 'INV-2024-008', date: '1 Sep 2024', amount: '$180.00', status: 'Paid', period: 'Annual Pro Plan' }
])
</script>

<template>
  <div class="account-portal">
    <div class="container">
      <!-- Portal Top Header -->
      <header class="portal-header">
        <div class="user-lockup">
          <div class="avatar">{{ user.orgName.charAt(0) }}</div>
          <div>
            <h1 class="org-title">{{ user.orgName }}</h1>
            <p class="user-sub">{{ user.primaryContact }} ({{ user.email }}) &middot; <span class="role-tag">{{ user.role }}</span></p>
          </div>
        </div>
        <div class="header-actions">
          <UiButton variant="outline" size="sm" to="/signin">Sign Out</UiButton>
        </div>
      </header>

      <!-- Past-Due Warning Banner -->
      <div v-if="subscription.status === 'past_due'" class="alert-banner past-due" role="alert">
        <svg viewBox="0 0 20 20" fill="currentColor" class="alert-icon">
          <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>
        <span>Your last payment failed. Please update your payment method to avoid Pro feature interruption.</span>
        <UiButton variant="gradient" size="sm">Update Payment</UiButton>
      </div>

      <!-- Navigation Tabs -->
      <nav class="portal-tabs" aria-label="Account sections">
        <button 
          v-for="tab in ['overview', 'subscription', 'license', 'bibles', 'invoices', 'settings']" 
          :key="tab"
          :class="['tab-btn', { active: activeTab === tab }]"
          @click="activeTab = tab"
        >
          {{ tab.charAt(0).toUpperCase() + tab.slice(1) }}
          <UiBadge v-if="tab === 'bibles'" variant="preview" size="sm">3 Entitled</UiBadge>
        </button>
      </nav>

      <!-- Skeleton Loading State -->
      <div v-if="isLoading" class="portal-grid">
        <div class="portal-card">
          <SkeletonLoader :lines="4" :widths="[30, 80, 100, 50]" />
        </div>
      </div>

      <!-- Tab Content Grid -->
      <div v-else class="portal-content">
        <!-- OVERVIEW / SUBSCRIPTION CARD -->
        <section v-if="activeTab === 'overview' || activeTab === 'subscription'" class="portal-card">
          <div class="card-header">
            <div>
              <h2>Subscription & Plan</h2>
              <p class="card-subtitle">Manage your tier and billing terms</p>
            </div>
            <UiBadge :variant="subscription.status === 'active' ? 'preview' : 'live'">
              {{ subscription.status.toUpperCase() }}
            </UiBadge>
          </div>

          <div class="plan-summary-box">
            <div class="summary-col">
              <span class="label">Current Plan</span>
              <span class="value-highlight">{{ subscription.plan }} Tier</span>
            </div>
            <div class="summary-col">
              <span class="label">Billing Rate</span>
              <span class="value">{{ subscription.amount }} / {{ subscription.interval }} (billed {{ subscription.period }})</span>
            </div>
            <div class="summary-col">
              <span class="label">Renewal Date</span>
              <span class="value">{{ subscription.nextBillingDate }}</span>
            </div>
          </div>

          <div class="card-actions">
            <UiButton variant="primary" size="md">Change Plan</UiButton>
            <UiButton variant="outline" size="md">Update Payment Method</UiButton>
            <UiButton 
              v-if="subscription.status === 'active'" 
              variant="ghost" 
              size="md" 
              class="danger-text"
              @click="showCancelDialog = true"
            >
              Cancel Subscription
            </UiButton>
          </div>
        </section>

        <!-- LICENSE & DEVICES CARD -->
        <section v-if="activeTab === 'overview' || activeTab === 'license'" class="portal-card">
          <div class="card-header">
            <div>
              <h2>App License & Devices</h2>
              <p class="card-subtitle">Manage your activation key and authorized venue devices</p>
            </div>
            <UiBadge variant="ndi">{{ subscription.seatsUsed }} / {{ subscription.seatsTotal }} Seats Active</UiBadge>
          </div>

          <div class="license-key-box">
            <div class="key-info">
              <span class="label">App License Key</span>
              <code class="key-code">
                {{ isKeyMasked ? licenseKey.substring(0, 10) + '••••••••••••' : licenseKey }}
              </code>
            </div>
            <div class="key-btn-group">
              <UiButton variant="ghost" size="sm" @click="isKeyMasked = !isKeyMasked">
                {{ isKeyMasked ? 'Reveal' : 'Mask' }}
              </UiButton>
              <UiButton variant="secondary" size="sm" @click="copyLicenseKey">
                Copy Key
              </UiButton>
            </div>
          </div>

          <div class="devices-section">
            <h3>Registered Venue Devices</h3>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Device Name</th>
                    <th>OS / Platform</th>
                    <th>IP Address</th>
                    <th>Last Active</th>
                    <th>App Version</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="dev in devices" :key="dev.id">
                    <td class="font-medium">
                      {{ dev.name }}
                      <span v-if="dev.isCurrent" class="current-tag">(This device)</span>
                    </td>
                    <td>{{ dev.os }}</td>
                    <td><code>{{ dev.ip }}</code></td>
                    <td>{{ dev.lastActive }}</td>
                    <td><UiBadge variant="preview" size="sm">{{ dev.version }}</UiBadge></td>
                    <td>
                      <button type="button" class="btn-text-danger" @click="promptDeactivateDevice(dev)">
                        Deactivate
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <!-- BIBLE ENTITLEMENTS CARD (CRITICAL GAP IMPLEMENTED!) -->
        <section v-if="activeTab === 'overview' || activeTab === 'bibles'" class="portal-card">
          <div class="card-header">
            <div>
              <h2>Bible Translation Entitlements</h2>
              <p class="card-subtitle">Licensed Bibles authorized for encrypted download on your venue hardware</p>
            </div>
            <UiBadge variant="ready">3 Entitlements Granted</UiBadge>
          </div>

          <div class="entitlements-list">
            <div v-for="b in bibles" :key="b.id" class="entitlement-row">
              <div class="ent-icon">📖</div>
              <div class="ent-details">
                <div class="ent-title-line">
                  <h4 class="ent-name">{{ b.name }}</h4>
                  <UiBadge :variant="b.status === 'active' ? 'preview' : 'warn'">
                    {{ b.status.toUpperCase() }}
                  </UiBadge>
                </div>
                <p class="ent-sub">{{ b.language }} &middot; Rights Holder: {{ b.publisher }}</p>
                <div class="ent-meta">
                  <span>Downloaded ({{ b.size }})</span> &middot;
                  <span>Last synced: {{ b.lastSynced }}</span> &middot;
                  <span :class="{ 'expiring-text': b.status === 'expiring' }">Expires: {{ b.expires }}</span>
                </div>
              </div>
              <div class="ent-action">
                <UiButton variant="outline" size="sm" @click="redownloadBible(b)">
                  Re-download
                </UiButton>
              </div>
            </div>
          </div>

          <div class="bundled-bibles-section">
            <h3>Bundled Public-Domain Bibles (Always Included)</h3>
            <div class="bundled-grid">
              <div v-for="bb in bundledBibles" :key="bb.name" class="bundled-chip">
                <span>📖 {{ bb.name }}</span>
                <UiBadge variant="preview" size="sm">INSTALLED</UiBadge>
              </div>
            </div>
          </div>
        </section>

        <!-- INVOICES CARD -->
        <section v-if="activeTab === 'overview' || activeTab === 'invoices'" class="portal-card">
          <div class="card-header">
            <div>
              <h2>Billing History & Invoices</h2>
              <p class="card-subtitle">Download PDF receipts and view payment ledger</p>
            </div>
          </div>

          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Invoice ID</th>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Receipt</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="inv in invoices" :key="inv.id">
                  <td class="font-mono">{{ inv.id }}</td>
                  <td>{{ inv.date }}</td>
                  <td>{{ inv.period }}</td>
                  <td class="font-bold">{{ inv.amount }}</td>
                  <td><UiBadge variant="preview">{{ inv.status }}</UiBadge></td>
                  <td>
                    <button type="button" class="btn-link" @click="showToast('Downloading PDF invoice...')">
                      Download PDF
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- SETTINGS CARD -->
        <section v-if="activeTab === 'settings'" class="portal-card">
          <div class="card-header">
            <div>
              <h2>Account Settings</h2>
              <p class="card-subtitle">Update organization details and primary contact email</p>
            </div>
          </div>

          <form class="settings-form" @submit.prevent="showToast('Settings saved successfully!')">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Organization Name</label>
                <input v-model="user.orgName" type="text" class="form-input" />
              </div>
              <div class="form-group">
                <label class="form-label">Primary Contact</label>
                <input v-model="user.primaryContact" type="text" class="form-input" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Email Address</label>
              <input v-model="user.email" type="email" class="form-input" />
            </div>

            <div class="form-actions">
              <UiButton variant="gradient" size="md">Save Changes</UiButton>
            </div>
          </form>
        </section>
      </div>
    </div>

    <!-- Confirmation Dialogs -->
    <ConfirmDialog
      v-model:show="showCancelDialog"
      title="Cancel your Pro subscription?"
      description="Your Pro features will remain active until 1 Sep 2026. After that date, multi-output, NDI streaming, and stage monitor features will be disabled."
      :consequences="[
        'Multi-output presentation disabled',
        'NDI streaming to OBS/vMix disabled',
        'Stage confidence monitor disabled',
        'Your account reverts to Free tier'
      ]"
      confirmLabel="Cancel subscription"
      cancelLabel="Keep my plan"
      requireType="cancel"
      variant="danger"
      @confirm="confirmCancelSubscription"
    />

    <ConfirmDialog
      v-model:show="showDeactivateDialog"
      title="Deactivate this device?"
      :description="`Are you sure you want to deactivate &quot;${targetDevice?.name || 'this device'}&quot;? It will lose access to Pro features.`"
      confirmLabel="Deactivate"
      cancelLabel="Keep active"
      variant="warning"
      @confirm="confirmDeactivateDevice"
    />

    <!-- Toast Notification -->
    <Toast 
      v-model:show="toastShow" 
      :message="toastMessage" 
      :variant="toastVariant" 
    />
  </div>
</template>

<style scoped>
.account-portal {
  padding: 40px 0 80px;
  background: var(--sc-base);
  min-height: calc(100vh - 80px);
}

.container {
  max-width: 1140px;
  margin: 0 auto;
  padding: 0 24px;
}

/* Header */
.portal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--sc-border);
}

.user-lockup {
  display: flex;
  align-items: center;
  gap: 16px;
}

.avatar {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--sc-primary), #2b2a6b);
  color: white;
  font-weight: 700;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.org-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0 0 4px 0;
}

.user-sub {
  font-size: 14px;
  color: var(--sc-text-secondary);
  margin: 0;
}

.role-tag {
  color: var(--sc-primary);
  font-weight: 500;
}

/* Past-due alert */
.alert-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-radius: 12px;
  margin-bottom: 32px;
  font-size: 14px;
  font-weight: 500;
}

.alert-banner.past-due {
  background: var(--sc-live-soft);
  border: 1px solid var(--sc-live-border);
  color: var(--sc-text);
}

.alert-icon {
  width: 20px;
  height: 20px;
  color: var(--sc-live);
  flex-shrink: 0;
}

/* Tabs */
.portal-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 32px;
  border-bottom: 1px solid var(--sc-border);
  padding-bottom: 12px;
  overflow-x: auto;
}

.tab-btn {
  background: none;
  border: none;
  padding: 10px 18px;
  font-family: var(--font-family);
  font-size: 15px;
  font-weight: 500;
  color: var(--sc-text-secondary);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.tab-btn:hover {
  color: var(--sc-text);
  background: var(--sc-surface);
}

.tab-btn.active {
  color: var(--sc-text);
  background: var(--sc-elevated);
  font-weight: 600;
}

/* Content & Cards */
.portal-content {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.portal-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  padding: 32px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.card-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0 0 4px 0;
}

.card-subtitle {
  font-size: 14px;
  color: var(--sc-text-secondary);
  margin: 0;
}

/* Summary Box */
.plan-summary-box {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
}

.summary-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-col .label {
  font-size: 12px;
  color: var(--sc-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.value-highlight {
  font-size: 22px;
  font-weight: 700;
  color: var(--sc-primary);
}

.summary-col .value {
  font-size: 15px;
  color: var(--sc-text);
  font-weight: 500;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.danger-text {
  color: var(--sc-live) !important;
  margin-left: auto;
}

/* License Box */
.license-key-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--sc-inset);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 28px;
}

.key-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.key-info .label {
  font-size: 12px;
  color: var(--sc-text-muted);
}

.key-code {
  font-family: monospace;
  font-size: 16px;
  color: var(--sc-gold);
  font-weight: 600;
}

.key-btn-group {
  display: flex;
  gap: 8px;
}

/* Data Table */
.devices-section h3, .bundled-bibles-section h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--sc-text);
  margin: 0 0 16px 0;
}

.table-responsive {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 14px;
}

.data-table th {
  background: var(--sc-elevated);
  color: var(--sc-text-muted);
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 12px 16px;
  border-bottom: 1px solid var(--sc-border);
}

.data-table td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--sc-border);
  color: var(--sc-text-secondary);
}

.data-table tr:last-child td {
  border-bottom: none;
}

.font-medium { font-weight: 500; color: var(--sc-text); }
.font-mono { font-family: monospace; }
.font-bold { font-weight: 600; color: var(--sc-text); }
.current-tag { color: var(--sc-preview); font-size: 12px; margin-left: 6px; }

.btn-text-danger {
  background: none;
  border: none;
  color: var(--sc-live);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.btn-text-danger:hover { text-decoration: underline; }

.btn-link {
  background: none;
  border: none;
  color: var(--sc-primary);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.btn-link:hover { text-decoration: underline; }

/* Entitlements List */
.entitlements-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 28px;
}

.entitlement-row {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 12px;
  padding: 18px 20px;
}

.ent-icon {
  font-size: 28px;
}

.ent-details {
  flex: 1;
}

.ent-title-line {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}

.ent-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--sc-text);
  margin: 0;
}

.ent-sub {
  font-size: 13px;
  color: var(--sc-text-secondary);
  margin: 0 0 6px 0;
}

.ent-meta {
  font-size: 12px;
  color: var(--sc-text-muted);
}

.expiring-text {
  color: var(--sc-warn);
  font-weight: 600;
}

/* Bundled Bibles */
.bundled-bibles-section {
  padding-top: 24px;
  border-top: 1px solid var(--sc-border);
}

.bundled-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.bundled-chip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--sc-inset);
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--sc-text-secondary);
}

/* Settings Form */
.settings-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 600px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--sc-text);
}

.form-input {
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  padding: 10px 14px;
  font-family: var(--font-family);
  font-size: 14px;
  color: var(--sc-text);
}

.form-input:focus {
  outline: none;
  border-color: var(--sc-primary);
}

@media (max-width: 768px) {
  .portal-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  .plan-summary-box {
    grid-template-columns: 1fr;
  }
  .license-key-box {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .entitlement-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
