<script setup lang="ts">
import { ref } from 'vue'
import AdminShell from '@/components/AdminShell.vue'
import DataTable from '@/components/DataTable.vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'

const columns = [
  { key: 'user', label: 'User Name / Email', sortable: true },
  { key: 'org', label: 'Organization', sortable: true },
  { key: 'role', label: 'Role' },
  { key: 'lastActive', label: 'Last Active', sortable: true },
  { key: 'status', label: 'Status' },
  { key: 'actions', label: 'Action', align: 'right' as const }
]

const users = ref([
  { user: 'Sarah Jenkins (sarah@grace.org)', org: 'Grace Community Church', role: 'Org Owner', lastActive: 'Today at 10:45 AM', status: 'Active' },
  { user: 'Mark Davis (mark@redeemer.org)', org: 'Redeemer Worship Center', role: 'Org Owner', lastActive: 'Yesterday', status: 'Active' },
  { user: 'John Operator (john@grace.org)', org: 'Grace Community Church', role: 'Operator', lastActive: '3 days ago', status: 'Active' },
  { user: 'Rachel Adams (rachel@hope.org)', org: 'Hope Chapel', role: 'Org Owner', lastActive: '1 week ago', status: 'Suspended' }
])
</script>

<template>
  <AdminShell>
    <template #title>End-User Accounts</template>

    <DataTable :columns="columns" :items="users" searchPlaceholder="Search users, email, organization...">
      <template #table-actions>
        <UiButton variant="primary" size="sm">+ Invite User</UiButton>
      </template>

      <template #cell-user="{ row }">
        <span class="font-medium">{{ row.user }}</span>
      </template>

      <template #cell-status="{ row }">
        <UiBadge :variant="row.status === 'Active' ? 'preview' : 'live'">
          {{ row.status }}
        </UiBadge>
      </template>

      <template #cell-actions>
        <button type="button" class="btn-text">Impersonate</button>
      </template>
    </DataTable>
  </AdminShell>
</template>

<style scoped>
.font-medium { font-weight: 600; color: var(--sc-text); }
.btn-text { background: none; border: none; color: var(--sc-primary); font-size: 13px; font-weight: 500; cursor: pointer; }
.btn-text:hover { text-decoration: underline; }
</style>
