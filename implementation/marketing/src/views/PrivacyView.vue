<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
</script>

<template>
  <div class="legal-page">
    <div class="container">
      <div class="legal-header">
        <UiBadge variant="preview">Legal Notice</UiBadge>
        <h1 class="legal-title">Privacy Policy</h1>
        <p class="legal-date">Last Updated: August 8, 2026</p>
      </div>

      <div class="legal-content">
        <h2>1. Executive Commitment to Privacy</h2>
        <p>
          At SelahCue, we believe church ministry data—including sermon transcripts, internal service plans, member media, and audio recordings—is strictly private. Our core presentation application is designed as an <strong>offline-first local application</strong> that stores presentation data directly on your venue hardware.
        </p>

        <h2>2. Information We Collect</h2>
        <h3>A. Account &amp; Subscription Information</h3>
        <p>
          When you register for a SelahCue account or upgrade to a Pro tier, we collect your organization name, primary contact name, email address, and billing information through our payment processor (Stripe).
        </p>

        <h3>B. App License &amp; Device Activation Data</h3>
        <p>
          To enforce seat limits on paid plans, the SelahCue desktop software transmits an anonymized hardware fingerprint, platform OS version, and app version during activation. We do NOT collect venue network logs, presentation slide text, or audio feeds during activation checks.
        </p>

        <h2>3. Local Data Privacy (Speech &amp; Transcripts)</h2>
        <p>
          On-device speech-to-text (Whisper AI) runs <strong>100% locally</strong> on your hardware using native GPU acceleration. Sermon audio streams and generated transcripts never leave your local venue machine unless you explicitly enable an opt-in cloud AI integration.
        </p>

        <h2>4. Data Protection Rights (GDPR &amp; NDPA 2023)</h2>
        <p>
          You have the right to access, rectify, or request deletion of your account and billing data at any time by contacting <code>privacy@selahcue.app</code>.
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
.legal-content h3 { font-size: 17px; font-weight: 600; color: var(--sc-text); margin: 20px 0 8px 0; }
.legal-content p { font-size: 15px; color: var(--sc-text-secondary); line-height: 1.7; margin-bottom: 16px; }
.legal-content code { background: var(--sc-elevated); padding: 2px 6px; border-radius: 4px; color: var(--sc-primary); }
</style>
