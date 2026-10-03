<script setup lang="ts">
import { computed } from 'vue'
import { buttonElement } from '@/lib/ui/buttonElement.ts'

const props = defineProps({
  /**
   * `gradient` is a LEGACY alias of `primary`: Figma draws no gradient-filled button (the gradient
   * is the CTA card behind the buttons), so it renders the same solid fill. It stays accepted only
   * so the pages that still pass it keep working until their own tickets migrate to `primary`;
   * `inverse` / `inverse-outline` are the white / outlined pair for buttons that sit ON a gradient band.
   */
  variant: {
    type: String,
    default: 'primary',
    validator: (val: string) => ['primary', 'secondary', 'ghost', 'gradient', 'outline', 'inverse', 'inverse-outline'].includes(val)
  },
  /** `compact` is the 39px navbar button; sm / md / lg are the 41 / 44 / 49px content buttons. */
  size: {
    type: String,
    default: 'md',
    validator: (val: string) => ['compact', 'sm', 'md', 'lg'].includes(val)
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
  },
  /** Fill the container's width (the pricing cards pass this). */
  block: {
    type: Boolean,
    default: false
  }
})

/**
 * Which element to render and with which attributes: see `lib/ui/buttonElement.ts` for why a
 * router link must keep its own href, and why a disabled or loading link is rendered without
 * one (so it cannot be tabbed to or followed).
 */
const element = computed(() => buttonElement(props))
</script>

<template>
  <component
    :is="element.tag"
    v-bind="element.attrs"
    :class="['ui-button', `variant-${variant}`, `size-${size}`, { 'is-loading': loading, 'is-disabled': disabled, 'is-block': block }]"
  >
    <div v-if="loading" class="spinner"></div>
    <span class="content" :class="{ 'hidden': loading }">
      <slot></slot>
    </span>
  </component>
</template>

<style scoped>
/*
 * GEOMETRY (Figma, measured over every button frame on 15 page frames; audit shared-chrome-27/28).
 *
 * Every size is height = padding + a line box that is a PX LENGTH + a 1px border, on every variant
 * (a transparent border for the solid ones). A bare line-height here would be inherited, and the same
 * button then measured 41-47px, 47-50.5px and 51-58px depending on the section it sat in.
 *
 *   compact  39  (the navbar's Download free)      10px radius, 14/700
 *   sm       41                                    10px radius, 14/600
 *   md       44                                    11px radius, 15/600
 *   lg       49  solid (primary, inverse)          11px radius, 15.5/700
 *   lg       47  quiet (secondary, outline, ghost, inverse-outline), 15.5/600
 *
 * A pill is for toggles and badges; no button is one. `min-height` is NOT used for the design height:
 * the 44px floor below is a hit-area rule for phones and coarse pointers only.
 */
.ui-button {
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-family);
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--transition-fast);
  position: relative;
  overflow: hidden;
}

/* An OUTLINE, not a box-shadow: forced-colors (Windows High Contrast) deletes shadows and keeps
   outlines, so a shadow-only ring left keyboard users there with no indicator at all. */
.ui-button:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 2px;
}

/* On a gradient band the brand-coloured ring would disappear into the card. */
.variant-inverse:focus-visible,
.variant-inverse-outline:focus-visible {
  outline-color: #fff;
}

.ui-button:active:not(.is-disabled) {
  transform: scale(0.98);
}

.ui-button.is-disabled {
  opacity: 0.5;
  pointer-events: none;
}

.is-block {
  width: 100%;
}

/* Sizes */
.size-compact {
  padding: 10px 18px;
  font-size: 14px;
  line-height: 17px;
  font-weight: 700;
  border-radius: 10px;
}
.size-sm {
  padding: 11px 18px;
  font-size: 14px;
  line-height: 17px;
  border-radius: 10px;
}
.size-md {
  padding: 12px 24px;
  font-size: 15px;
  line-height: 18px;
  border-radius: 11px;
}
.size-lg {
  padding: 14px 26px;
  font-size: 15.5px;
  line-height: 19px;
  font-weight: 700;
  border-radius: 11px;
}
.size-lg.variant-secondary,
.size-lg.variant-outline,
.size-lg.variant-ghost,
.size-lg.variant-inverse-outline {
  padding: 13px 24px;
  font-weight: 600;
}

/* Variants */
.variant-primary,
.variant-gradient {
  background: var(--sc-primary);
  color: #fff;
}
.variant-primary:hover {
  background: var(--sc-primary-hover);
}
/* The old gradient's hover was a glow, which leaves the label contrast where it is. Kept for the
   call sites that still pass `gradient`; the primary hover colour is a decision for Uma. */
.variant-gradient:hover {
  box-shadow: 0 0 20px rgba(110, 92, 240, 0.4);
}

.variant-secondary {
  background: var(--sc-elevated);
  color: var(--sc-text);
  border-color: var(--sc-border);
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

.variant-outline {
  background: transparent;
  border-color: var(--sc-border);
  color: var(--sc-text);
}
.variant-outline:hover {
  background: var(--sc-elevated);
}

/* For buttons that sit ON a gradient CTA band (Figma 479:129 and its outlined sibling). */
.variant-inverse {
  background: #fff;
  color: var(--sc-primary);
}
/* A lift, not a colour change: a darker fill would drop the brand-ink label below 4.5:1. */
.variant-inverse:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}

.variant-inverse-outline {
  background: transparent;
  border-color: rgba(255, 255, 255, 0.5);
  color: #fff;
}
/* Darken, never lighten: white on the lighter end of the band is already 4.65:1. */
.variant-inverse-outline:hover {
  background: rgba(0, 0, 0, 0.2);
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

/* 44px minimum touch target on phones and on any coarse pointer (tablets). A fine
   pointer keeps the designed heights, so the desktop is visually unchanged. */
@media (max-width: 767.98px), (pointer: coarse) {
  .ui-button {
    min-height: 44px;
  }
}
</style>
