<script setup lang="ts">
import AffiliateShell from '@/components/AffiliateShell.vue'
import FaqAccordion from '@/components/FaqAccordion.vue'
import UiButton from '@/components/UiButton.vue'

const faqItems = [
  { question: 'How is referral attribution tracked?', answer: 'We use a 60-day last-click cookie. When someone clicks your referral link, a tracking cookie is stored in their browser.' },
  { question: 'What happens when a referred church upgrades?', answer: 'You automatically receive a 20% commission on their subscription amount every month for up to 12 months.' },
  { question: 'Is self-referral allowed?', answer: 'Self-referrals for your own church organization are not permitted under our affiliate terms.' },
  { question: 'When and how do payouts occur?', answer: 'Payouts occur automatically on the 1st of every month via PayPal once your pending balance reaches at least $50.' }
]
</script>

<template>
  <AffiliateShell>
    <div class="container">
      <div class="page-header">
        <h1>Affiliate Program Help &amp; FAQ</h1>
        <p>Everything you need to know about promoting SelahCue and earning commissions.</p>
      </div>

      <div class="faq-card">
        <FaqAccordion :items="faqItems" :defaultOpen="0" />
      </div>

      <div class="contact-box">
        <h3>Have a question about your affiliate account?</h3>
        <p>Contact our affiliate manager directly for custom commission tiers or partnership questions.</p>
        <UiButton variant="outline" size="md" href="mailto:affiliates@selahcue.app">Email Affiliate Manager</UiButton>
      </div>
    </div>
  </AffiliateShell>
</template>

<style scoped>
.container { max-width: 900px; margin: 0 auto; padding: 0 24px; }
.page-header { margin-bottom: 32px; text-align: center; }
.page-header h1 { font-size: 28px; font-weight: 700; color: var(--sc-text); margin: 0 0 8px 0; }
.page-header p { font-size: 15px; color: var(--sc-text-secondary); margin: 0; }

.faq-card { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 32px; margin-bottom: 40px; }

.contact-box { background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; padding: 32px; text-align: center; }
.contact-box h3 { font-size: 20px; color: var(--sc-text); margin: 0 0 8px 0; }
.contact-box p { font-size: 14px; color: var(--sc-text-secondary); margin: 0 0 20px 0; }
</style>
