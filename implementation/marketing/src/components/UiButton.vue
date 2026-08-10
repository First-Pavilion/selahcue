<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (val: string) => ['primary', 'secondary', 'ghost', 'gradient', 'outline'].includes(val)
  },
  size: {
    type: String,
    default: 'md',
    validator: (val: string) => ['sm', 'md', 'lg'].includes(val)
  },
  to: {
    type: [String, Object],
    default: undefined
  },
  href: {
    type: String,
    default: undefined
  },
  disabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const component = computed(() => {
  if (props.to) return 'router-link'
  if (props.href) return 'a'
  return 'button'
})
</script>

<template>
  <component
    :is="component"
    :to="to"
    :href="href"
    :disabled="disabled || loading"
    :class="['ui-button', `variant-${variant}`, `size-${size}`, { 'is-loading': loading, 'is-disabled': disabled }]"
  >
    <div v-if="loading" class="spinner"></div>
    <span class="content" :class="{ 'hidden': loading }">
      <slot></slot>
    </span>
  </component>
</template>

<style scoped>
.ui-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--pill-radius);
  font-family: var(--font-family);
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  border: none;
  outline: none;
  transition: all var(--transition-fast);
  position: relative;
  overflow: hidden;
}

.ui-button:focus-visible {
  box-shadow: 0 0 0 2px var(--sc-base), 0 0 0 4px var(--sc-primary);
}

.ui-button:active:not(.is-disabled) {
  transform: scale(0.98);
}

.ui-button.is-disabled {
  opacity: 0.5;
  pointer-events: none;
}

/* Sizes */
.size-sm {
  padding: 12px 20px;
  font-size: 14px;
}
.size-md {
  padding: 14px 28px;
  font-size: 15px;
}
.size-lg {
  padding: 16px 32px;
  font-size: 16px;
}

/* Variants */
.variant-primary {
  background: var(--sc-primary);
  color: white;
}
.variant-primary:hover {
  background: var(--sc-primary-hover);
}

.variant-secondary {
  background: var(--sc-elevated);
  color: var(--sc-text);
}
.variant-secondary:hover {
  background: var(--sc-border);
}

.variant-ghost {
  background: transparent;
  color: var(--sc-text);
}
.variant-ghost:hover {
  background: var(--sc-elevated);
}

.variant-gradient {
  background: var(--gradient-cta);
  color: white;
}
.variant-gradient:hover {
  box-shadow: 0 0 20px rgba(91, 107, 214, 0.4);
}

.variant-outline {
  background: transparent;
  border: 1px solid var(--sc-border);
  color: var(--sc-text);
}
.variant-outline:hover {
  background: var(--sc-elevated);
}

.content {
  display: flex;
  align-items: center;
  gap: 8px;
  opacity: 1;
  transition: opacity 0.2s;
}

.content.hidden {
  opacity: 0;
}

.spinner {
  position: absolute;
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: currentColor;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
