<script setup lang="ts">
import { watch, onUnmounted } from 'vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  message: { type: String, required: true },
  variant: { type: String, default: 'success' }, // 'success' | 'error' | 'info'
  duration: { type: Number, default: 3000 } // 0 = persistent
})

const emit = defineEmits(['update:show'])

let timer: ReturnType<typeof setTimeout> | null = null

const startTimer = () => {
  if (props.duration > 0) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      emit('update:show', false)
    }, props.duration)
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    startTimer()
  }
})

onUnmounted(() => {
  if (timer) clearTimeout(timer)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="toast">
      <div 
        v-if="show" 
        :class="['toast-notification', variant]"
        role="status"
        aria-live="polite"
      >
        <span class="toast-icon">
          <svg v-if="variant === 'success'" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
          </svg>
          <svg v-else-if="variant === 'error'" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
          </svg>
          <svg v-else viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zm-1 9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
        </span>
        <span class="toast-message">{{ message }}</span>
        <button type="button" class="toast-close" @click="emit('update:show', false)">×</button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.toast-notification {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10000;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 999px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.4);
  color: var(--sc-text);
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}

.toast-icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
}

.toast-icon svg {
  width: 18px;
  height: 18px;
}

.success .toast-icon { color: var(--sc-preview); }
.error .toast-icon { color: var(--sc-live); }
.info .toast-icon { color: var(--sc-info); }

.toast-close {
  background: none;
  border: none;
  color: var(--sc-text-muted);
  font-size: 18px;
  cursor: pointer;
  padding: 0 0 0 8px;
  line-height: 1;
}

.toast-close:hover {
  color: var(--sc-text);
}

.toast-enter-active, .toast-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-enter-from {
  opacity: 0;
  transform: translate(-50%, 20px);
}
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 10px);
}
</style>
