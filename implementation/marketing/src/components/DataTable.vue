<script setup lang="ts">
import { ref, computed } from 'vue'

export interface TableColumn {
  key: string
  label: string
  sortable?: boolean
  align?: 'left' | 'center' | 'right'
}

const props = defineProps({
  columns: { type: Array as () => TableColumn[], required: true },
  items: { type: Array as () => Record<string, any>[], required: true },
  searchPlaceholder: { type: String, default: 'Search records...' },
  filterable: { type: Boolean, default: true },
  pageSize: { type: Number, default: 10 }
})

const searchQuery = ref('')
const sortKey = ref('')
const sortOrder = ref<'asc' | 'desc'>('asc')
const currentPage = ref(1)

const toggleSort = (key: string) => {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'asc'
  }
}

const filteredItems = computed(() => {
  let res = [...props.items]

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    res = res.filter(item => 
      Object.values(item).some(val => 
        String(val || '').toLowerCase().includes(q)
      )
    )
  }

  if (sortKey.value) {
    res.sort((a, b) => {
      const valA = a[sortKey.value]
      const valB = b[sortKey.value]
      if (valA < valB) return sortOrder.value === 'asc' ? -1 : 1
      if (valA > valB) return sortOrder.value === 'asc' ? 1 : -1
      return 0
    })
  }

  return res
})

const totalPages = computed(() => {
  return Math.ceil(filteredItems.value.length / props.pageSize) || 1
})

const paginatedItems = computed(() => {
  const start = (currentPage.value - 1) * props.pageSize
  return filteredItems.value.slice(start, start + props.pageSize)
})
</script>

<template>
  <div class="data-table-container">
    <!-- Table Header Controls -->
    <div v-if="filterable" class="table-controls">
      <div class="search-input-wrapper">
        <svg viewBox="0 0 20 20" fill="currentColor" class="search-icon">
          <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/>
        </svg>
        <input 
          v-model="searchQuery" 
          type="text" 
          class="table-search" 
          :placeholder="searchPlaceholder"
          @input="currentPage = 1"
        />
      </div>

      <div class="table-actions">
        <slot name="table-actions"></slot>
      </div>
    </div>

    <!-- Data Table -->
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th 
              v-for="col in columns" 
              :key="col.key"
              :class="[{ sortable: col.sortable }, col.align || 'left']"
              @click="col.sortable ? toggleSort(col.key) : undefined"
            >
              <div class="th-content">
                <span>{{ col.label }}</span>
                <span v-if="col.sortable && sortKey === col.key" class="sort-arrow">
                  {{ sortOrder === 'asc' ? '▲' : '▼' }}
                </span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="paginatedItems.length === 0">
            <td :colspan="columns.length" class="empty-cell">
              No matching records found
            </td>
          </tr>
          <tr v-for="(row, idx) in paginatedItems" :key="idx" class="table-row">
            <td 
              v-for="col in columns" 
              :key="col.key"
              :class="col.align || 'left'"
            >
              <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
                {{ row[col.key] }}
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination Footer -->
    <div class="table-pagination">
      <span class="pagination-info">
        Showing {{ (currentPage - 1) * pageSize + 1 }} to {{ Math.min(currentPage * pageSize, filteredItems.length) }} of {{ filteredItems.length }} entries
      </span>

      <div class="pagination-btns">
        <button 
          type="button" 
          class="page-btn" 
          :disabled="currentPage === 1"
          @click="currentPage--"
        >
          Previous
        </button>
        <span class="page-current">{{ currentPage }} / {{ totalPages }}</span>
        <button 
          type="button" 
          class="page-btn" 
          :disabled="currentPage >= totalPages"
          @click="currentPage++"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.data-table-container {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  overflow: hidden;
}

.table-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--sc-border);
  gap: 16px;
}

.search-input-wrapper {
  position: relative;
  flex: 1;
  max-width: 320px;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--sc-text-muted);
}

.table-search {
  width: 100%;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  padding: 8px 12px 8px 36px;
  font-family: var(--font-family);
  font-size: 13px;
  color: var(--sc-text);
  box-sizing: border-box;
}

.table-search:focus {
  outline: none;
  border-color: var(--sc-primary);
}

.table-wrapper {
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
  user-select: none;
}

.data-table th.sortable {
  cursor: pointer;
}

.data-table th.sortable:hover {
  color: var(--sc-text);
}

.th-content {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sort-arrow {
  font-size: 10px;
  color: var(--sc-primary);
}

.data-table td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--sc-border);
  color: var(--sc-text-secondary);
}

.table-row:hover {
  background: rgba(255, 255, 255, 0.02);
}

.empty-cell {
  text-align: center;
  padding: 36px !important;
  color: var(--sc-text-muted);
}

.left { text-align: left; }
.center { text-align: center; }
.right { text-align: right; }

.table-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: var(--sc-inset);
  border-top: 1px solid var(--sc-border);
  font-size: 13px;
  color: var(--sc-text-muted);
}

.pagination-btns {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-btn {
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: 6px;
  padding: 4px 12px;
  font-family: var(--font-family);
  font-size: 12px;
  color: var(--sc-text);
  cursor: pointer;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-current {
  font-weight: 600;
  color: var(--sc-text);
}
</style>
