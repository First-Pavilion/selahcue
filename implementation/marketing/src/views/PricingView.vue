<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import PageHero from '@/components/core/PageHero.vue'

/*
 * NO PLAN, PRICE OR BILLING TERM IS SHOWN (ClickUp 17tnw2b0x3h).
 *
 * The page used to draw three plan cards (Free, Pro, Platinum), a comparison table of device, output and NDI limits, a
 * Monthly / Annual toggle and a Pricing FAQ. All of it read from DEC-008's lineup, which the owner superseded on 2026-09-27
 * (Free, Core and Pro, with weekly allowances and no price set), and the FAQ answered with proration, a non-profit rule and
 * PayPal / ACH payment methods that nothing backs. The Core and Pro device, output and NDI limits are still undecided.
 *
 * Plan names, prices and limits are data in the API's catalogue, so they will be shown HERE from the API and never typed into
 * this file again (the follow-up tickets "public plan catalogue endpoint" and "Home and Pricing plan cards render from the
 * API"). Until the API serves them the page says so and draws nothing else. `PricingCard` and `SegmentedToggle` stay in the
 * component library for that work.
 */
</script>

<template>
  <div class="pricing-view">
    <PageHero
      title="Pricing that grows with your church"
      :pad-top="80"
      :pad-bottom="40"
      :gap="16"
      :title-size="52"
      :title-line="56"
      :title-max="520"
    >
      <template #eyebrow>
        <UiBadge variant="eyebrow">PRICING</UiBadge>
      </template>
    </PageHero>

    <!-- The h2 keeps the outline from jumping from the h1 to the footer's h3 headings (audit pricing-bug-01). -->
    <section class="plans-section" aria-labelledby="plans-heading">
      <div class="container">
        <h2 id="plans-heading" class="plans-heading">Plans and pricing</h2>
        <div class="plans-empty">
          <p>Plans and prices have not been published yet.</p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.plans-section {
  padding-block: 24px var(--section-pad);
}

.plans-heading {
  margin: 0 0 24px;
  text-align: center;
  font: 700 26px/32px var(--font-family);
  color: var(--sc-text);
}

/* The empty state takes the card the Changelog and Careers empty states use. */
.plans-empty {
  max-width: 900px;
  margin-inline: auto;
  padding: 47px 29px;
  text-align: center;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
}

.plans-empty p {
  margin: 0;
  font-size: 17px;
  line-height: 26px;
  color: var(--sc-text-secondary);
}

@media (max-width: 767.98px) {
  .plans-empty {
    padding: 31px 19px;
    border-radius: 16px;
  }
}
</style>
