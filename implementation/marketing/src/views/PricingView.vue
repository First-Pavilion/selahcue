<script setup lang="ts">
import { ref } from 'vue'
import PricingCard from '@/components/PricingCard.vue'
import UiBadge from '@/components/UiBadge.vue'
import FaqAccordion from '@/components/FaqAccordion.vue'

const isAnnual = ref(false)

const pricingPlans = [
  {
    name: 'Free',
    price: 0,
    period: 'forever',
    description: 'Everything you need to get started',
    features: ['Basic presentation', 'Built-in Bible', 'Offline support'],
    cta: 'Download free',
    popular: false
  },
  {
    name: 'Pro',
    price: 19,
    period: 'month',
    description: 'For churches ready to go further',
    features: ['Multi-screen output', 'NDI support', 'Stage monitor', 'Priority support'],
    cta: 'Start free trial',
    popular: true
  },
  {
    name: 'Church',
    price: 0,
    period: 'month',
    description: 'For multi-campus and enterprise',
    features: ['Unlimited campuses', 'Enterprise deployment', 'Custom integrations', '24/7 SLA'],
    cta: 'Talk to us',
    popular: false
  }
]

const pricingFaqItems = [
  { question: 'Can I switch plans later?', answer: 'Yes, you can upgrade or downgrade your plan at any time. Prorated charges will apply.' },
  { question: 'Do you offer non-profit discounts?', answer: 'Our pricing is already optimized for churches and non-profits.' },
  { question: 'What payment methods are accepted?', answer: 'We accept all major credit cards, PayPal, and ACH transfers for annual plans.' }
]
</script>

<template>
  <div class="pricing-view">
    <section class="hero">
      <div class="container">
        <h1>Choose the plan that's right for your church</h1>
        <p>Transparent pricing with no hidden fees.</p>
        
        <div class="pricing-toggle">
          <span>Monthly</span>
          <label class="switch">
            <input type="checkbox" v-model="isAnnual" />
            <span class="slider"></span>
          </label>
          <span>Annual <UiBadge text="Save 20%" variant="accent" /></span>
        </div>
      </div>
    </section>

    <section class="cards-section">
      <div class="container">
        <div class="pricing-grid">
          <PricingCard 
            v-for="plan in pricingPlans" 
            :key="plan.name"
            :name="plan.name"
            :price="plan.price"
            :period="plan.period"
            :description="plan.description"
            :features="plan.features"
            :cta="plan.cta"
            :popular="plan.popular"
            :annual="isAnnual"
          />
        </div>
      </div>
    </section>

    <section class="comparison-section">
      <div class="container">
        <h2>Compare features</h2>
        <div class="table-container">
          <table class="comparison-table">
            <thead>
              <tr>
                <th>Feature</th>
                <th>Free</th>
                <th>Pro</th>
                <th>Church</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Audience Output</td>
                <td class="check">✓</td>
                <td class="check">✓</td>
                <td class="check">✓</td>
              </tr>
              <tr>
                <td>Offline Support</td>
                <td class="check">✓</td>
                <td class="check">✓</td>
                <td class="check">✓</td>
              </tr>
              <tr>
                <td>Built-in Scripture</td>
                <td class="check">✓</td>
                <td class="check">✓</td>
                <td class="check">✓</td>
              </tr>
              <tr>
                <td>Stage Monitor</td>
                <td class="dash">—</td>
                <td class="check">✓</td>
                <td class="check">✓</td>
              </tr>
              <tr>
                <td>NDI Output</td>
                <td class="dash">—</td>
                <td class="check">✓</td>
                <td class="check">✓</td>
              </tr>
              <tr>
                <td>Timers & Clocks</td>
                <td class="dash">—</td>
                <td class="check">✓</td>
                <td class="check">✓</td>
              </tr>
              <tr>
                <td>Priority Support</td>
                <td class="dash">—</td>
                <td class="check">✓</td>
                <td class="check">✓</td>
              </tr>
              <tr>
                <td>Custom SLA</td>
                <td class="dash">—</td>
                <td class="dash">—</td>
                <td class="check">✓</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="faq-section">
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
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

.hero {
  padding: 5rem 0 3rem;
  text-align: center;
}
.hero h1 {
  font-size: 3rem;
  margin-bottom: 1rem;
}
.hero p {
  font-size: 1.25rem;
  color: var(--sc-text-muted);
  margin-bottom: 3rem;
}

.pricing-toggle {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
}

/* Switch */
.switch {
  position: relative;
  display: inline-block;
  width: 50px;
  height: 24px;
}
.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--sc-surface);
  transition: .4s;
  border-radius: 24px;
  border: 1px solid var(--sc-border);
}
.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 4px;
  bottom: 3px;
  background-color: var(--sc-primary);
  transition: .4s;
  border-radius: 50%;
}
input:checked + .slider:before {
  transform: translateX(24px);
}

.cards-section {
  padding: 0 0 5rem;
}
.pricing-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2rem;
}

.comparison-section {
  padding: 5rem 0;
  background: var(--sc-surface);
}
.comparison-section h2 {
  text-align: center;
  margin-bottom: 3rem;
  font-size: 2.5rem;
}
.table-container {
  overflow-x: auto;
}
.comparison-table {
  width: 100%;
  border-collapse: collapse;
}
.comparison-table th, .comparison-table td {
  padding: 1.25rem;
  text-align: left;
  border-bottom: 1px solid var(--sc-border);
}
.comparison-table th {
  position: sticky;
  top: 0;
  background: var(--sc-surface);
  font-weight: 600;
  font-size: 1.1rem;
}
.comparison-table td.check {
  color: var(--sc-success);
  font-weight: bold;
}
.comparison-table td.dash {
  color: var(--sc-text-muted);
}
.comparison-table tbody tr:nth-child(even) {
  background: rgba(0,0,0,0.02);
}

.faq-section {
  padding: 5rem 0;
}
.faq-section h2 {
  text-align: center;
  margin-bottom: 3rem;
  font-size: 2.5rem;
}
.faq-list {
  max-width: 800px;
  margin: 0 auto;
}

@media (max-width: 768px) {
  .pricing-grid {
    grid-template-columns: 1fr;
  }
}
</style>
