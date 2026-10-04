<script setup lang="ts">
import { ref } from 'vue'
import { nextIndex } from './segmentedKeys.ts'

interface Option {
  value: string
  label: string
  disabled?: boolean
}

const props = defineProps<{
  modelValue: string
  options: Option[]
  /** The name of the group, read out with the first radio (WCAG 1.3.1, 4.1.2). */
  label: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const group = ref<HTMLElement | null>(null)

function choose(option: Option): void {
  if (!option.disabled) emit('update:modelValue', option.value)
}

/**
 * Arrow keys move the choice AND the focus (a radio group's roving tabindex: the checked radio is the
 * only one in the tab order, so focus must follow it or the keyboard user is stranded on a radio
 * that is no longer in the order).
 */
function onKeydown(event: KeyboardEvent, at: number): void {
  const to = nextIndex(
    event.key,
    at,
    props.options.map((o) => !o.disabled),
    // A chord is the browser's (Alt+Left is Back, Cmd+Left too, Ctrl+Home jumps): leave it unhandled.
    { alt: event.altKey, ctrl: event.ctrlKey, meta: event.metaKey, shift: event.shiftKey },
  )
  if (to === null) return
  event.preventDefault()
  const target = props.options[to]
  if (!target || to === at) return
  emit('update:modelValue', target.value)
  const radios = group.value?.querySelectorAll<HTMLElement>('[role="radio"]')
  radios?.[to]?.focus()
}
</script>

<template>
  <div ref="group" class="segmented" role="radiogroup" :aria-label="label">
    <button
      v-for="(option, i) in options"
      :key="option.value"
      type="button"
      role="radio"
      class="segment"
      :aria-checked="option.value === modelValue ? 'true' : 'false'"
      :tabindex="option.value === modelValue ? 0 : -1"
      :disabled="option.disabled"
      @click="choose(option)"
      @keydown="onKeydown($event, i)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<style scoped>
/*
 * Figma 483:143 / 483:145: a pill 42px tall (1px border, 3px inset, a 34px segment), elevated fill,
 * 999 radius; the chosen segment is filled with the brand colour under a white 13.5px/600 label, the
 * other is muted. White on --sc-primary is 4.72:1; the muted label is --sc-text-secondary on the
 * elevated fill, 7.4:1 (Figma's muted #9aa4b2 maps to it).
 */
.segmented {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  background: var(--sc-elevated);
  border: 1px solid var(--sc-border);
  border-radius: var(--pill-radius);
}

.segment {
  box-sizing: border-box;
  height: 34px;
  padding: 0 18px;
  border: 0;
  border-radius: var(--pill-radius);
  background: transparent;
  color: var(--sc-text-secondary);
  font: 600 13.5px/16px var(--font-family);
  cursor: pointer;
  transition:
    background-color var(--transition-fast),
    color var(--transition-fast);
}

.segment[aria-checked='true'] {
  background: var(--sc-primary);
  color: #fff;
}

.segment:not([aria-checked='true']):hover:not(:disabled) {
  color: var(--sc-text);
}

.segment:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* A 44px hit area on phones and on any coarse pointer (UiButton's rule); the pill is 42px tall only where
   a mouse is the pointer, as Figma draws it. */
@media (max-width: 767.98px), (pointer: coarse) {
  .segment {
    min-height: 44px;
  }
}

/* A forced-colors user sees the chosen segment by its outline, not its fill. */
@media (forced-colors: active) {
  .segment[aria-checked='true'] {
    outline: 2px solid currentColor;
    outline-offset: -2px;
  }
}
</style>
