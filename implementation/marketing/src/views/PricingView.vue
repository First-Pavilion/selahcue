<script setup lang="ts">
import { computed, ref } from 'vue'
import PricingCard from '@/components/PricingCard.vue'
import UiBadge from '@/components/UiBadge.vue'
import FaqAccordion from '@/components/FaqAccordion.vue'
import PageHero from '@/components/core/PageHero.vue'
import SegmentedToggle from '@/components/core/SegmentedToggle.vue'

/*
 * WORDING FOLLOWS THE REPO, NOT THE FIGMA FRAME (owner decision: honest content wins).
 *
 * Figma draws Free / Pro / Church at $0 / $19 / Custom. None of that is decided: DEC-008 fixes the
 * tiers (Free, Pro, Platinum) and their limits, and leaves prices, tier names and the final
 * speech-to-text hours open under D1. So each card says what DEC-008 backs (devices, outputs, NDI
 * outputs, the Free watermark) and nothing else: no price, no trial, no Church tier, no SLA, no
 * annual discount. Whatever D1 decides is a change to the data below, not to the layout.
 *
 * Audit: pricing-02, -05, -09, -12 (Copy rule on ClickUp 17tnw2b2cey); claims removal on the live
 * site is 17tnw2b0x3h.
 */
interface Plan {
  name: string
  price: string
  description: string
  features: string[]
  cta: string
  /** Where the button goes. Without one the card shows a disabled button and says why. */
  to?: string
  popular: boolean
}

const plans: Plan[] = [
  {
    name: 'Free',
    price: 'No charge',
    description: 'For running a service from one device. A SelahCue watermark appears on all output.',
    features: ['1 device', 'Up to 2 outputs', 'Speech-to-text with a monthly allowance'],
    cta: 'Download free',
    // The Download page says plainly that nothing downloads yet (PR 134); the wording of every
    // "Download free" button site-wide is 17tnw2b0x3h's. The nav says the same.
    to: '/download',
    popular: false,
  },
  {
    name: 'Pro',
    price: 'Price TBA',
    description: 'Price to be announced. For churches that need more outputs and NDI output.',
    features: [
      'Everything in Free, without the watermark',
      '3 devices',
      'Up to 5 outputs',
      'Up to 5 NDI outputs',
      'A larger monthly speech-to-text allowance',
    ],
    cta: 'Get Pro',
    // No `to`: no purchase flow exists (audit pricing-17), so the card shows "Not available yet".
    popular: true,
  },
  {
    name: 'Platinum',
    price: 'Price TBA',
    description: 'Price to be announced. For larger teams.',
    features: [
      'Everything in Pro',
      '7 devices',
      'Up to 10 outputs',
      'Up to 10 NDI outputs',
      'The largest monthly speech-to-text allowance',
    ],
    cta: 'Talk to us',
    to: '/contact',
    popular: false,
  },
]

/*
 * The billing toggle keeps Figma's shape and no arithmetic. There is no annual plan in the repo
 * (audit pricing-18), so choosing Annual computes no price and shows no discount; it says so.
 */
const billing = ref('monthly')
const billingOptions = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'annual', label: 'Annual' },
]
const billingNote = computed(() => (billing.value === 'annual' ? 'Annual billing is not available yet.' : ''))

type Cell = { kind: 'yes' } | { kind: 'no' } | { kind: 'value'; text: string }
const yes: Cell = { kind: 'yes' }
const no: Cell = { kind: 'no' }
const value = (text: string): Cell => ({ kind: 'value', text })

/*
 * Only rows the repo backs. The three base rows are in every plan (nothing in DEC-008 withholds them);
 * the rest are DEC-008's table. Figma's other rows ("Mobile control", "Theme Designer", "On-device
 * transcript" as a paid extra, "Multi-campus / site licensing", "Onboarding & priority support",
 * "Unlimited" outputs) have no decided plan assignment or no source: audit pricing-12, -16.
 */
const rows: { label: string; cells: [Cell, Cell, Cell] }[] = [
  { label: 'Live output + stage display', cells: [yes, yes, yes] },
  { label: 'Bundled scripture + keyword search', cells: [yes, yes, yes] },
  { label: 'Service plans, timers & themes', cells: [yes, yes, yes] },
  { label: 'Devices', cells: [value('1'), value('3'), value('7')] },
  { label: 'Simultaneous outputs', cells: [value('2'), value('5'), value('10')] },
  { label: 'NDI streaming output', cells: [no, value('5'), value('10')] },
  { label: 'Speech-to-text, monthly allowance', cells: [yes, yes, yes] },
  { label: 'No watermark on output', cells: [no, yes, yes] },
]

/*
 * The Pricing FAQ is not in the Figma frame (audit pricing-20, class D: Uma decides whether it stays).
 * Its answers still carry claims the repo does not back (proration, payment methods, a non-profit
 * line); removing them belongs to ClickUp 17tnw2b0x3h, and this ticket neither decides the section nor
 * duplicates that removal. `tests/corePages.test.ts` names this region as its one exception.
 */
const pricingFaqItems = [
  { question: 'Can I switch plans later?', answer: 'Yes, you can upgrade or downgrade your plan at any time. Prorated charges will apply.' },
  { question: 'Do you offer non-profit discounts?', answer: 'Our pricing is already optimized for churches and non-profits.' },
  { question: 'What payment methods are accepted?', answer: 'We accept all major credit cards, PayPal, and ACH transfers for annual plans.' }
]
</script>

<template>
  <div class="pricing-view">
    <!-- Figma 483:139: pad 80/96/8, gap 16; the toggle's frame adds 10 above the pill. -->
    <PageHero
      title="Pricing that grows with your church"
      :pad-top="80"
      :pad-bottom="8"
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
      Start with the Free plan; Pro and Platinum add outputs, NDI and devices. Prices are not announced yet.
      <template #after>
        <div class="billing">
          <SegmentedToggle v-model="billing" :options="billingOptions" label="Billing period" />
          <p class="billing-note" role="status" aria-live="polite">{{ billingNote }}</p>
        </div>
      </template>
    </PageHero>

    <section class="plans-section" aria-labelledby="plans-heading">
      <!-- The plan names are h3 (PricingCard). This h2 keeps the outline from jumping h1 to h3 (audit
           pricing-bug-01); Figma draws no heading levels. -->
      <h2 id="plans-heading" class="sr-only">Choose a plan</h2>
      <div class="container">
        <div class="pricing-grid">
          <PricingCard
            v-for="plan in plans"
            :key="plan.name"
            :name="plan.name"
            :price="plan.price"
            :description="plan.description"
            :features="plan.features"
            :cta="plan.cta"
            :to="plan.to"
            :popular="plan.popular"
          />
        </div>
      </div>
    </section>

    <section class="compare-section">
      <div class="container">
        <h2>Compare every plan</h2>
        <div class="comparison-card">
          <div class="table-scroll" tabindex="0" role="region" aria-label="Plan comparison, scrolls sideways when wide">
            <table class="comparison-table">
              <thead>
                <tr>
                  <th scope="col" class="plans-label">PLANS</th>
                  <th scope="col">Free</th>
                  <th scope="col">Pro</th>
                  <th scope="col">Platinum</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="row.label">
                  <th scope="row">{{ row.label }}</th>
                  <td v-for="(cell, i) in row.cells" :key="i">
                    <template v-if="cell.kind === 'yes'">
                      <svg class="mark yes" viewBox="0 0 16 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path d="M2 6.4l3.8 3.8L14 2" />
                      </svg>
                      <span class="sr-only">Included</span>
                    </template>
                    <template v-else-if="cell.kind === 'no'">
                      <svg class="mark no" viewBox="0 0 16 12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">
                        <path d="M3 6h10" />
                      </svg>
                      <span class="sr-only">Not included</span>
                    </template>
                    <span v-else class="figure">{{ cell.text }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <section class="faq-section" data-region="pricing-faq">
      <div class="container">
        <h2>Pricing FAQ</h2>
        <div class="faq-list">
          <FaqAccordion :items="pricingFaqItems" :defaultOpen="0" />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* The toggle frame (Figma 483:144): 10px above the 42px pill. The note under it is positioned out of the
   flow on desktop, in the 48px gap above the cards, so choosing Annual moves nothing. */
.billing {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 10px;
}

.billing-note {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 18px;
  color: var(--sc-text-secondary);
}
.billing-note:empty {
  display: none;
}

/* Figma 483:240: pad 40/96/80 around the cards; 24px between them. */
.plans-section {
  position: relative;
  padding-block: 24px 48px;
}

.pricing-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 24px;
  max-width: 520px;
  margin-inline: auto;
}
/* Tablet and mobile: one card per row, Pro first so the recommended plan leads (design 8d). */
.pricing-grid > .popular {
  order: -1;
}

/* Figma 484:124: pad 20/96/88, gap 36; the card is 1040 wide. */
.compare-section {
  padding-block: 24px var(--section-pad);
}
.compare-section h2,
.faq-section h2 {
  margin: 0 0 24px;
  text-align: center;
  font: 700 26px/32px var(--font-family);
  color: var(--sc-text);
}

.comparison-card {
  max-width: 1040px;
  margin-inline: auto;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  overflow: hidden;
}

/* The table scrolls sideways INSIDE its card (never the page) when it is wide; it is a focus stop so a
   keyboard user can scroll it. */
.table-scroll {
  /* Positioned, so the visually hidden "Included" / "Not included" spans (absolute) are contained and
     clipped HERE. Without it they escape this scroller and widen the page on a phone. */
  position: relative;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-x: contain;
}

.comparison-table {
  width: 100%;
  min-width: 520px;
  table-layout: fixed;
  border-collapse: collapse;
}

.comparison-table th,
.comparison-table td {
  box-sizing: border-box;
  height: 48px;
  padding: 0 12px;
  font-size: 14.5px;
  line-height: 18px;
  text-align: center;
  vertical-align: middle;
}

.comparison-table thead tr {
  background: var(--sc-elevated);
}
.comparison-table thead th {
  height: 45px;
  font-size: 15px;
  font-weight: 600;
  color: var(--sc-text);
}
.comparison-table thead th.plans-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.1px;
  color: var(--sc-text-secondary);
}

.comparison-table th:first-child,
.comparison-table td:first-child {
  width: auto;
  padding-left: 16px;
  text-align: left;
}
.comparison-table th:not(:first-child),
.comparison-table td {
  width: 96px;
}
.comparison-table th:last-child,
.comparison-table td:last-child {
  padding-right: 16px;
}

.comparison-table tbody th {
  font-weight: 500;
  color: var(--sc-text);
}
.comparison-table tbody tr + tr {
  border-top: 1px solid var(--sc-border);
}

.mark {
  display: inline-block;
  width: 16px;
  height: 12px;
  vertical-align: middle;
}
.mark.yes {
  color: var(--sc-preview);
}
.mark.no {
  color: var(--sc-text-secondary);
}

/* The accent numerals (Figma 13.5/600 brand ink, 3.7:1 on the card: below AA). They read the single
   brand-ink property UiBadge reads, and fall back to the readable text colour: Uma's one-line change. */
.figure {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ui-badge-ink, var(--sc-text));
}

.faq-section {
  padding-block: 0 var(--section-pad);
}
.faq-list {
  max-width: 800px;
  margin: 0 auto;
}

@media (min-width: 768px) {
  .plans-section {
    padding-block: 32px 64px;
  }
  .compare-section {
    padding-top: 16px;
  }
  .compare-section h2,
  .faq-section h2 {
    margin-bottom: 32px;
    font-size: 32px;
    line-height: 39px;
  }
  .comparison-table th,
  .comparison-table td {
    padding-inline: 20px;
  }
  .comparison-table th:first-child,
  .comparison-table td:first-child {
    padding-left: 26px;
  }
  .comparison-table th:last-child,
  .comparison-table td:last-child {
    padding-right: 26px;
  }
  .comparison-table th:not(:first-child),
  .comparison-table td {
    width: 150px;
  }
  .comparison-table th:last-child,
  .comparison-table td:last-child {
    width: 176px;
  }
}

/* Three across from 1200 (the sweep reads these columns). */
@media (min-width: 1200px) {
  .billing-note {
    position: absolute;
    top: 100%;
    left: 50%;
    margin: 8px 0 0;
    transform: translateX(-50%);
    white-space: nowrap;
  }
  .plans-section {
    padding-block: 40px 80px;
  }
  .pricing-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    max-width: none;
    margin-inline: 0;
  }
  .pricing-grid > .popular {
    order: 0;
  }
  .compare-section {
    padding-top: 20px;
    padding-bottom: 88px;
  }
  .compare-section h2 {
    margin-bottom: 36px;
  }
}

/* A phone: the feature column stays pinned so a row is still readable at the far right. */
@media (max-width: 767.98px) {
  .comparison-table tbody th {
    position: sticky;
    left: 0;
    z-index: 1;
    background: var(--sc-surface);
    box-shadow: 1px 0 0 var(--sc-border);
  }
}
</style>
