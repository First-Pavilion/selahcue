<script setup lang="ts">
import { ref, computed } from 'vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import FaqAccordion from '@/components/FaqAccordion.vue'

const monthlyReferrals = ref(10)

const estimatedMonthlyEarnings = computed(() => {
  // 20% of $19/mo = $3.80 per referral / month
  return monthlyReferrals.value * 3.8
})

const estimatedAnnualEarnings = computed(() => {
  return estimatedMonthlyEarnings.value * 12
})

const faqItems = [
  { question: 'What is the commission rate?', answer: 'You earn a 20% recurring commission for 12 months on every paid subscription that signs up using your referral link.' },
  { question: 'How long does the referral cookie last?', answer: 'Our referral tracking uses a 60-day last-click attribution window.' },
  { question: 'When are affiliate payouts made?', answer: 'Payouts are processed on the 1st of every month via PayPal or Direct Bank Transfer once you reach the $50 minimum threshold.' },
  { question: 'Who can join the affiliate program?', answer: 'Worship leaders, tech consultants, Christian bloggers, YouTubers, and church network leaders are welcome to apply!' }
]
</script>

<template>
  <div class="affiliates-page">
    <section class="hero-section">
      <div class="container">
        <UiBadge variant="featured">SelahCue Partner Program</UiBadge>
        <h1 class="hero-title">Recommend SelahCue. Earn 20% Recurring Commission.</h1>
        <p class="hero-sub">Help churches upgrade their live worship presentation. Earn passive recurring income on every paid referral for 12 months.</p>
        
        <div class="hero-ctas">
          <UiButton variant="gradient" size="lg" to="/signin">Apply to Join Program</UiButton>
          <UiButton variant="outline" size="lg" href="#calculator">Calculate Earnings</UiButton>
        </div>
      </div>
    </section>

    <!-- Highlights Grid -->
    <section class="highlights-section">
      <div class="container">
        <div class="highlights-grid">
          <div class="highlight-card">
            <div class="hl-value">20%</div>
            <h3>Recurring Commission</h3>
            <p>Earn monthly recurring commission for up to 12 months per referred church.</p>
          </div>
          <div class="highlight-card">
            <div class="hl-value">60 Days</div>
            <h3>Cookie Attribution</h3>
            <p>Generous 60-day tracking window so you get credited even if they try free first.</p>
          </div>
          <div class="highlight-card">
            <div class="hl-value">$50</div>
            <h3>Low Payout Threshold</h3>
            <p>Monthly payouts direct to your PayPal or bank account with clear real-time reporting.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Earnings Calculator -->
    <section id="calculator" class="calc-section">
      <div class="container">
        <div class="calc-card">
          <h2>Estimate Your Earnings</h2>
          <p class="calc-sub">Slide to see how much you could earn by recommending SelahCue to churches:</p>

          <div class="slider-wrapper">
            <div class="slider-label">
              <span>Referred Active Churches:</span>
              <strong class="count-badge">{{ monthlyReferrals }} churches</strong>
            </div>
            <input 
              v-model.number="monthlyReferrals" 
              type="range" 
              min="1" 
              max="100" 
              class="range-slider"
            />
          </div>

          <div class="results-grid">
            <div class="result-box">
              <span class="res-label">Monthly Recurring Income</span>
              <span class="res-amount">${{ Math.round(estimatedMonthlyEarnings) }}/mo</span>
            </div>
            <div class="result-box highlight">
              <span class="res-label">Estimated Annual Payout</span>
              <span class="res-amount">${{ Math.round(estimatedAnnualEarnings) }}/yr</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- FAQ -->
    <section class="faq-section">
      <div class="container">
        <h2 class="section-title">Affiliate Program FAQ</h2>
        <div class="faq-wrapper">
          <FaqAccordion :items="faqItems" :defaultOpen="0" />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.affiliates-page { background: var(--sc-base); padding-bottom: 80px; }
.container { max-width: 1140px; margin: 0 auto; padding: 0 24px; }
.hero-section { padding: 80px 0 60px; text-align: center; }
.hero-title { font-size: 42px; font-weight: 800; color: var(--sc-text); margin: 20px 0; line-height: 1.25; }
.hero-sub { font-size: 18px; color: var(--sc-text-secondary); max-width: 720px; margin: 0 auto 36px; line-height: 1.6; }
.hero-ctas { display: flex; justify-content: center; gap: 16px; }

.highlights-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin-bottom: 60px; }
.highlight-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 32px; text-align: center; }
.hl-value { font-size: 36px; font-weight: 800; color: var(--sc-primary); margin-bottom: 8px; }
.highlight-card h3 { font-size: 18px; color: var(--sc-text); margin: 0 0 8px 0; }
.highlight-card p { font-size: 14px; color: var(--sc-text-secondary); margin: 0; }

.calc-section { padding: 40px 0; }
.calc-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 24px; padding: 48px; max-width: 700px; margin: 0 auto; }
.calc-card h2 { font-size: 28px; font-weight: 700; color: var(--sc-text); text-align: center; margin: 0 0 8px 0; }
.calc-sub { font-size: 15px; color: var(--sc-text-secondary); text-align: center; margin: 0 0 32px 0; }

.slider-wrapper { margin-bottom: 36px; }
.slider-label { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 15px; color: var(--sc-text); }
.count-badge { font-size: 18px; color: var(--sc-primary); }

.range-slider { width: 100%; height: 8px; border-radius: 4px; background: var(--sc-elevated); accent-color: var(--sc-primary); cursor: pointer; }

.results-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.result-box { background: var(--sc-elevated); border: 1px solid var(--sc-border); border-radius: 12px; padding: 20px; text-align: center; }
.result-box.highlight { background: var(--sc-accent-soft); border-color: var(--sc-primary); }
.res-label { font-size: 12px; text-transform: uppercase; color: var(--sc-text-muted); display: block; margin-bottom: 6px; }
.res-amount { font-size: 28px; font-weight: 800; color: var(--sc-text); }

.faq-section { padding: 60px 0; }
.section-title { text-align: center; font-size: 28px; font-weight: 700; color: var(--sc-text); margin-bottom: 32px; }
.faq-wrapper { max-width: 800px; margin: 0 auto; }

@media (max-width: 768px) {
  .highlights-grid { grid-template-columns: 1fr; }
  .results-grid { grid-template-columns: 1fr; }
  .hero-ctas { flex-direction: column; }
}
</style>
