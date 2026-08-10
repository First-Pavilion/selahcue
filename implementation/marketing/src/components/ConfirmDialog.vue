<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import UiButton from './UiButton.vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  consequences: { type: Array as () => string[], default: () => [] },
  confirmLabel: { type: String, default: 'Confirm' },
  cancelLabel: { type: String, default: 'Cancel' },
  requireType: { type: String, default: '' }, // String user must type to confirm (e.g. "cancel")
  variant: { type: String, default: 'danger' } // 'danger' | 'warning'
})

const emit = defineEmits(['confirm', 'cancel', 'update:show'])

const typedValue = ref('')

const isConfirmDisabled = () => {
  if (props.requireType) {
    return typedValue.value.trim().toLowerCase() !== props.requireType.toLowerCase()
  }
  return false
}

const handleConfirm = () => {
  if (!isConfirmDisabled()) {
    emit('confirm')
    emit('update:show', false)
  }
}

const handleCancel = () => {
  emit('cancel')
  emit('update:show', false)
}

const handleKeydown = (e: KeyboardEvent) => {
  if (props.show && e.key === 'Escape') {
    handleCancel()
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    typedValue.value = ''
  }
})

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="show" class="dialog-scrim" @click.self="handleCancel">
        <div 
          class="dialog-card"
          role="alertdialog"
          aria-modal="true"
          :aria-label="title"
        >
          <div class="dialog-icon-wrapper" :class="variant">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="dialog-icon">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>

          <h3 class="dialog-title">{{ title }}</h3>
          <p v-if="description" class="dialog-desc">{{ description }}</p>

          <ul v-if="consequences.length > 0" class="consequence-list">
            <li v-for="(item, idx) in consequences" :key="idx" class="consequence-item">
              <span class="bullet">•</span> {{ item }}
            </li>
          </ul>

          <div v-if="requireType" class="type-confirm-wrapper">
            <label class="type-label">
              Type <strong>"{{ requireType }}"</strong> to confirm:
            </label>
            <input 
              v-model="typedValue"
              type="text"
              class="type-input"
              :placeholder="requireType"
              @keyup.enter="handleConfirm"
            />
          </div>

          <div class="dialog-actions">
            <UiButton variant="ghost" @click="handleCancel">
              {{ cancelLabel }}
            </UiButton>
            <UiButton 
              :variant="variant === 'danger' ? 'primary' : 'secondary'"
              :disabled="isConfirmDisabled()"
              class="confirm-btn"
              :class="variant"
              @click="handleConfirm"
            >
              {{ confirmLabel }}
            </UiButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.dialog-scrim {
  position: fixed;
  inset: 0;
  background: rgba(11, 13, 18, 0.75);
  backdrop-filter: blur(8px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.dialog-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  max-width: 440px;
  width: 100%;
  padding: 32px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  text-align: center;
  animation: slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.dialog-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  margin: 0 auto 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-icon-wrapper.danger {
  background: var(--sc-live-soft);
  color: var(--sc-live);
  border: 1px solid var(--sc-live-border);
}

.dialog-icon-wrapper.warning {
  background: var(--sc-warn-soft);
  color: var(--sc-warn);
  border: 1px solid var(--sc-warn-border);
}

.dialog-icon {
  width: 24px;
  height: 24px;
}

.dialog-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0 0 12px 0;
}

.dialog-desc {
  font-size: 15px;
  color: var(--sc-text-secondary);
  line-height: 1.5;
  margin: 0 0 20px 0;
}

.consequence-list {
  list-style: none;
  padding: 0;
  margin: 0 0 24px 0;
  text-align: left;
  background: var(--sc-elevated);
  border-radius: 10px;
  padding: 16px;
  border: 1px solid var(--sc-border);
}

.consequence-item {
  font-size: 14px;
  color: var(--sc-text-secondary);
  margin-bottom: 8px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.consequence-item:last-child {
  margin-bottom: 0;
}

.bullet {
  color: var(--sc-live);
  font-weight: bold;
}

.type-confirm-wrapper {
  margin-bottom: 24px;
  text-align: left;
}

.type-label {
  font-size: 13px;
  color: var(--sc-text-secondary);
  display: block;
  margin-bottom: 8px;
}

.type-input {
  width: 100%;
  background: var(--sc-inset);
  border: 1px solid var(--sc-border);
  border-radius: 8px;
  padding: 10px 14px;
  font-family: var(--font-family);
  font-size: 14px;
  color: var(--sc-text);
  box-sizing: border-box;
}

.type-input:focus {
  outline: none;
  border-color: var(--sc-primary);
}

.dialog-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.confirm-btn.danger {
  background: var(--sc-live) !important;
  color: white !important;
}

.confirm-btn.danger:hover {
  background: #ff3333 !important;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

@keyframes slideUp {
  from { transform: translateY(12px) scale(0.97); opacity: 0; }
  to { transform: translateY(0) scale(1); opacity: 1; }
}
</style>
