<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
</script>

<template>
  <div class="legal-page">
    <div class="container">
      <div class="legal-header">
        <UiBadge variant="preview">Legal Terms</UiBadge>
        <h1 class="legal-title">Terms of Service</h1>
        <p class="legal-date">Last Updated: August 8, 2026</p>
      </div>

      <div class="legal-content">
        <h2>1. Agreement to Terms</h2>
        <p>
          By downloading, installing, or subscribing to SelahCue, your organization agrees to be bound by these Terms of Service. If you do not agree, do not use the application.
        </p>

        <h2>2. Software License &amp; Device Seat Limits</h2>
        <p>
          SelahCue grants your organization a non-exclusive, non-transferable license to run the SelahCue presentation software on venue devices up to the seat count specified in your Pro or Church subscription plan.
        </p>

        <h2>3. Bible Translation Entitlements</h2>
        <p>
          Public-domain Bibles (e.g. WEB, ASV, BSB) are bundled for unlimited use. Copyrighted translations (e.g. NIV, ESV, NLT) are downloaded post-activation under specific publisher entitlement agreements. You agree not to extract, reverse engineer, or redistribute encrypted Bible databases.
        </p>

        <h2>4. Subscriptions &amp; Cancellations</h2>
        <p>
          Pro plans are billed on a monthly or annual recurring basis. You may cancel your subscription at any time via your account portal. Paid features remain active until the end of your current billing period.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.legal-page { background: var(--sc-base); padding: 60px 0 80px; }
.container { max-width: 800px; margin: 0 auto; padding: 0 24px; }
.legal-header { text-align: center; margin-bottom: 48px; border-bottom: 1px solid var(--sc-border); padding-bottom: 32px; }
.legal-title { font-size: 36px; font-weight: 800; color: var(--sc-text); margin: 16px 0 8px 0; }
.legal-date { font-size: 14px; color: var(--sc-text-muted); }

.legal-content h2 { font-size: 22px; font-weight: 700; color: var(--sc-text); margin: 32px 0 12px 0; }
.legal-content p { font-size: 15px; color: var(--sc-text-secondary); line-height: 1.7; margin-bottom: 16px; }
</style>
