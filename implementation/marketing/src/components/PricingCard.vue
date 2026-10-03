<script setup lang="ts">
import { useId } from 'vue'
import UiButton from './UiButton.vue'
import UiBadge from './UiBadge.vue'

defineProps({
  name: { type: String, required: true },
  price: { type: [Number, String], required: true },
  period: { type: String, default: 'month' },
  description: { type: String, required: true },
  features: { type: Array as () => string[], required: true },
  cta: { type: String, required: true },
  popular: { type: Boolean, default: false },
  annual: { type: Boolean, default: false },
  /**
   * Where the plan's call to action goes: a router destination (`'/download'`, `{ name: ... }`).
   * The card never renders a button that does nothing. With a destination the call to action
   * is a link; without one it is a DISABLED button that says why (`unavailableNote`), which is
   * the honest state for a plan whose checkout does not exist yet.
   */
  to: { type: [String, Object], default: undefined },
  unavailableNote: { type: String, default: 'Not available yet' }
})

/** Ties the disabled button to the note that explains it. */
const noteId = `${useId()}-cta-note`
</script>

<template>
  <div :class="['pricing-card', { popular }]">
    <div class="plan-header">
      <h3 class="plan-name">{{ name }}</h3>
      <UiBadge v-if="popular" class="plan-chip" variant="accent">MOST POPULAR</UiBadge>
    </div>

    <div class="plan-price-box">
      <template v-if="typeof price === 'number'">
        <span class="price-val">${{ annual && price > 0 ? Math.round(price * 0.8) : price }}</span>
        <span class="price-period">/ {{ period }}</span>
      </template>
      <template v-else>
        <span class="price-val custom">{{ price }}</span>
      </template>
    </div>

    <p class="plan-desc">{{ description }}</p>

    <div class="cta-wrapper">
      <UiButton
        :to="to"
        :disabled="!to"
        :aria-describedby="to ? undefined : noteId"
        :variant="popular ? 'primary' : 'outline'"
        size="md"
      >
        {{ cta }}
      </UiButton>
      <p v-if="!to" :id="noteId" class="cta-note">{{ unavailableNote }}</p>
    </div>

    <div class="features-divider"></div>

    <ul class="features-list">
      <li v-for="feature in features" :key="feature">
        <svg class="check-icon" viewBox="0 0 17 20" fill="none" stroke="currentColor" stroke-width="1.84" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M4 8.6l3 3 6.6-6.7" />
        </svg>
        <span>{{ feature }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
/*
 * Figma 483:150 / 483:177 (Pricing) and 477:130 / 477:157 (Home). The card is top-aligned
 * (`align-self: start`, which wins over a grid's `align-items: stretch`, so the popular
 * plan is taller than its neighbours as drawn). Figma measures its padding from the OUTER
 * edge, so the border width is taken off the padding: 32/30, and 34/30/32/30 with the 2px
 * border of the popular plan. Gap 18 between every block.
 */
.pricing-card {
  --card-border: 1px;
  --card-pad-top: 32px;
  box-sizing: border-box;
  width: 100%;
  align-self: start;
  display: flex;
  flex-direction: column;
  gap: 18px;
  position: relative;
  background: var(--sc-surface);
  border: var(--card-border) solid var(--sc-border);
  border-radius: 18px;
  padding:
    calc(var(--card-pad-top) - var(--card-border))
    calc(30px - var(--card-border))
    calc(32px - var(--card-border));
  transition: border-color 0.2s ease;
}

.pricing-card.popular {
  --card-border: 2px;
  --card-pad-top: 34px;
  border-color: var(--sc-primary);
}

/* The plan name and, on the popular plan, the chip: one row, name left, chip right. */
.plan-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 21px;
}

.plan-name {
  font-size: 17px;
  font-weight: 600;
  line-height: 21px;
  color: var(--sc-text);
  margin: 0;
}

/* Figma 483:180: 103x22, 10px/700, +0.1px tracking, padding 5/11/5/10. The selector is
   deliberately longer than UiBadge's own size rule so the chip does not depend on the order
   the two stylesheets load in. */
.pricing-card .plan-chip {
  padding: 4px 10px 4px 9px;
  font-size: 10px;
  line-height: 12px;
  letter-spacing: 0.1px;
  flex-shrink: 0;
}

.plan-price-box {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.price-val {
  font-size: 44px;
  font-weight: 700;
  color: var(--sc-text);
  line-height: 1.2;
}

.price-period {
  font-size: 15px;
  color: var(--sc-text-secondary);
}

.plan-desc {
  font-size: 15px;
  color: var(--sc-text-secondary);
  line-height: 22px;
  margin: 0;
}

/* Full card width and 44px tall (Figma 483:157 / 483:186), above the divider. UiButton has no
   `block` prop, so the width is set here; the selector outranks UiButton's size rules. */
.cta-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cta-wrapper .ui-button {
  box-sizing: border-box;
  width: 100%;
  height: 44px;
  min-height: 44px;
  padding-top: 0;
  padding-bottom: 0;
  border-radius: 11px;
  font-size: 15px;
  font-weight: 600;
}

/* The honest reason a plan button is disabled; read with the button (aria-describedby). */
.cta-note {
  margin: 0;
  font-size: 13px;
  line-height: 18px;
  text-align: center;
  color: var(--sc-text-secondary);
}

.features-divider {
  height: 1px;
  background: var(--sc-border);
}

.features-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.features-list li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 14px;
  color: var(--sc-text-secondary);
  line-height: 20px;
}

.check-icon {
  width: 17px;
  height: 20px;
  color: var(--sc-preview);
  flex-shrink: 0;
}

/* On a phone the card is full width, so its call to action is too (it already is: the width
   above is 100% at every size). Only the padding steps down. */
@media (max-width: 767.98px) {
  .pricing-card {
    padding:
      calc(var(--card-pad-top) - var(--card-border) - 4px)
      calc(22px - var(--card-border))
      calc(28px - var(--card-border));
  }
}
</style>
