<script setup lang="ts">
defineProps({
  variant: {
    type: String,
    default: 'preview',
    validator: (val: string) => ['live', 'preview', 'ready', 'ndi', 'featured', 'new'].includes(val)
  },
  size: {
    type: String,
    default: 'sm',
    validator: (val: string) => ['sm', 'md'].includes(val)
  },
  dot: {
    type: Boolean,
    default: false
  }
})
</script>

<template>
  <span :class="['ui-badge', `variant-${variant}`, `size-${size}`]">
    <span v-if="dot" class="dot"></span>
    <slot></slot>
  </span>
</template>

<style scoped>
.ui-badge {
  display: inline-flex;
  align-items: center;
  border-radius: var(--pill-radius);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 11px;
  border: 1px solid transparent;
}

.size-sm {
  padding: 4px 8px;
}
.size-md {
  padding: 6px 12px;
  font-size: 12px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 6px;
  background-color: currentColor;
}

.variant-live .dot {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(255, 77, 77, 0.7); }
  70% { box-shadow: 0 0 0 6px rgba(255, 77, 77, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 77, 77, 0); }
}

.variant-live {
  background: var(--sc-live-soft);
  color: var(--sc-live);
  border-color: var(--sc-live-border);
}

.variant-preview {
  background: var(--sc-preview-soft);
  color: var(--sc-preview);
  border-color: var(--sc-preview-border);
}

.variant-ready {
  background: var(--sc-warn-soft);
  color: var(--sc-warn);
  border-color: var(--sc-warn-border);
}

.variant-ndi {
  background: var(--sc-info-soft);
  color: var(--sc-info);
  border-color: transparent;
}

.variant-featured {
  background: var(--sc-accent-soft);
  color: var(--sc-primary);
  border-color: transparent;
}

.variant-new {
  background: var(--sc-primary);
  color: white;
  border-color: transparent;
}
</style>
