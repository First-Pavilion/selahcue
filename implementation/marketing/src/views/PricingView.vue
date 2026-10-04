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
      :pad-bottom="96"
      :gap="16"
      :title-size="52"
      :title-line="56"
      :title-max="520"
      :lead-size="18"
      :lead-line="27"
      :lead-max="660"
    >
      <template #eyebrow>
        <UiBadge variant="eyebrow">PRICING</UiBadge>
      </template>
      Plans and prices have not been published yet.
    </PageHero>
  </div>
</template>
