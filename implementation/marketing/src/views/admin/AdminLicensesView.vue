<script setup lang="ts">
import { ref } from 'vue'
import AdminShell from '@/components/AdminShell.vue'
import DataTable from '@/components/DataTable.vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'

const activeSubTab = ref('keys')

// App Keys
const keyColumns = [
  { key: 'keyPrefix', label: 'License Key Prefix', sortable: true },
  { key: 'customer', label: 'Customer Organization', sortable: true },
  { key: 'type', label: 'Key Type' },
  { key: 'seats', label: 'Seats' },
  { key: 'expires', label: 'Expiry Date', sortable: true },
  { key: 'status', label: 'Status' }
]

const keys = ref([
  { keyPrefix: 'sc_live_9f82...', customer: 'Grace Community Church', type: 'Paid Annual', seats: '2 / 5', expires: 'Sep 1, 2026', status: 'Active' },
  { keyPrefix: 'sc_live_3k91...', customer: 'Redeemer Worship Center', type: 'Paid Monthly', seats: '1 / 5', expires: 'Aug 28, 2026', status: 'Active' },
  { keyPrefix: 'sc_demo_77a1...', customer: 'St. John Lutheran', type: '14-Day Trial', seats: '1 / 1', expires: 'Aug 15, 2026', status: 'Expiring Soon' }
])

// Bible Catalogue
const catalogueColumns = [
  { key: 'code', label: 'Code', sortable: true },
  { key: 'name', label: 'Translation Name', sortable: true },
  { key: 'language', label: 'Language' },
  { key: 'publisher', label: 'Rights Holder' },
  { key: 'legalStatus', label: 'Legal Class' },
  { key: 'availability', label: 'Availability' }
]

const catalogue = ref([
  { code: 'NIV', name: 'New International Version', language: 'English', publisher: 'Biblica, Inc.', legalStatus: 'Copyrighted (Entitled)', availability: 'Published' },
  { code: 'ESV', name: 'English Standard Version', language: 'English', publisher: 'Crossway', legalStatus: 'Copyrighted (Entitled)', availability: 'Published' },
  { code: 'NLT', name: 'New Living Translation', language: 'English', publisher: 'Tyndale', legalStatus: 'Copyrighted (Entitled)', availability: 'Published' },
  { code: 'WEB', name: 'World English Bible', language: 'English', publisher: 'Public Domain', legalStatus: 'Bundled Offline', availability: 'Bundled' }
])
</script>

<template>
  <AdminShell>
    <template #title>Licenses &amp; Entitlements Management</template>

    <div class="sub-nav">
      <button :class="['sub-btn', { active: activeSubTab === 'keys' }]" @click="activeSubTab = 'keys'">
        App License Keys
      </button>
      <button :class="['sub-btn', { active: activeSubTab === 'catalogue' }]" @click="activeSubTab = 'catalogue'">
        Bible Translation Catalogue
      </button>
    </div>

    <div v-if="activeSubTab === 'keys'">
      <DataTable :columns="keyColumns" :items="keys" searchPlaceholder="Search license keys or customers...">
        <template #table-actions>
          <UiButton variant="primary" size="sm">+ Generate Key</UiButton>
        </template>
        <template #cell-keyPrefix="{ row }">
          <code>{{ row.keyPrefix }}</code>
        </template>
        <template #cell-status="{ row }">
          <UiBadge :variant="row.status === 'Active' ? 'preview' : 'warn'">
            {{ row.status }}
          </UiBadge>
        </template>
      </DataTable>
    </div>

    <div v-else-if="activeSubTab === 'catalogue'">
      <DataTable :columns="catalogueColumns" :items="catalogue" searchPlaceholder="Search Bible catalogue...">
        <template #table-actions>
          <UiButton variant="primary" size="sm">+ Add Translation</UiButton>
        </template>
        <template #cell-code="{ row }">
          <UiBadge variant="ndi">{{ row.code }}</UiBadge>
        </template>
        <template #cell-name="{ row }">
          <span class="font-medium">📖 {{ row.name }}</span>
        </template>
        <template #cell-availability="{ row }">
          <UiBadge variant="preview">{{ row.availability }}</UiBadge>
        </template>
      </DataTable>
    </div>
  </AdminShell>
</template>

<style scoped>
.sub-nav { display: flex; gap: 8px; margin-bottom: 24px; border-bottom: 1px solid var(--sc-border); padding-bottom: 8px; }
.sub-btn { background: none; border: none; padding: 8px 16px; font-family: var(--font-family); font-size: 14px; font-weight: 600; color: var(--sc-text-muted); border-radius: 8px; cursor: pointer; }
.sub-btn.active { background: var(--sc-elevated); color: var(--sc-text); }
code { font-family: monospace; color: var(--sc-gold); font-weight: 600; }
.font-medium { font-weight: 600; color: var(--sc-text); }
</style>
