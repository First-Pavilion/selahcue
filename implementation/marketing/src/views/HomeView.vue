<script setup lang="ts">
import { ref } from 'vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import ConsoleMockup from '@/components/ConsoleMockup.vue'
import OutputManagerMockup from '@/components/OutputManagerMockup.vue'
import FeatureCard from '@/components/FeatureCard.vue'
import ReliabilityPillar from '@/components/ReliabilityPillar.vue'
import PricingCard from '@/components/PricingCard.vue'
import TestimonialCard from '@/components/TestimonialCard.vue'
import FaqAccordion from '@/components/FaqAccordion.vue'

const isAnnual = ref(false)

const pricingPlans = [
  {
    name: 'Free',
    price: 0,
    period: 'month',
    description: 'Everything your church needs to start presenting',
    features: [
      '1 Venue Device seat',
      'Bundled Public Domain Bibles',
      'Basic service plan run-sheet',
      'Single display projector output'
    ],
    cta: 'Download free',
    popular: false
  },
  {
    name: 'Pro',
    price: 19,
    period: 'month',
    description: 'For churches requiring NDI, stage monitors, and multi-output',
    features: [
      'Up to 5 Venue Device seats',
      'Licensed Bible Entitlements',
      'NDI 5 direct broadcast streaming',
      'Stage confidence monitor & timers',
      'Mobile controller pairing over LAN'
    ],
    cta: 'Get Pro',
    popular: true
  },
  {
    name: 'Church',
    price: 'Custom',
    period: '',
    description: 'For multi-campus ministries and large enterprises',
    features: [
      'Unlimited Venue Device seats',
      'Multi-campus organization',
      'Custom Bible entitlement SLAs',
      'Dedicated Solutions Architect'
    ],
    cta: 'Talk to us',
    popular: false
  }
]

const testimonials = [
  {
    quote: "SelahCue changed how our tech team operates on Sunday. The volunteer onboarding time dropped to zero, and the platform is rock-solid.",
    author: "Sarah Jenkins",
    role: "Worship Director @ Grace Community",
    color: "blue"
  },
  {
    quote: "We finally have a presentation tool that works 100% offline. No more Sunday morning panic when the church internet backhaul fails.",
    author: "Mark Davis",
    role: "Technical Director @ Redeemer Church",
    color: "green"
  },
  {
    quote: "The stage confidence monitor and built-in countdown timers keep our pastors and worship leaders synchronized throughout every service.",
    author: "Pastor Paul Miller",
    role: "Lead Pastor @ Hope Chapel",
    color: "amber"
  }
]

const faqItems = [
  { 
    question: 'Does SelahCue work fully offline on Sunday morning?', 
    answer: 'Yes! SelahCue is built desktop-authoritative and offline-first. All core features—scripture search, song slides, service plans, stage monitors, and NDI outputs—run 100% locally on your venue hardware without requiring an internet connection.' 
  },
  { 
    question: 'What platforms and operating systems are supported?', 
    answer: 'SelahCue supports Windows 10/11 (64-bit) and macOS 12+ (Apple Silicon & Intel). Additionally, you can pair any iOS or Android phone over your local Wi-Fi network to control slides remotely.' 
  },
  { 
    question: 'How do copyrighted Bible translation entitlements work?', 
    answer: 'Public-domain Bibles (WEB, ASV, BSB) are bundled for unlimited use right out of the box. Copyrighted translations (NIV, ESV, NLT) are granted via post-activation entitlement and downloaded to an encrypted local store on your venue hardware.' 
  },
  { 
    question: 'Does SelahCue support NDI streaming to OBS and vMix?', 
    answer: 'Yes! SelahCue includes native NDI 5 broadcast output support, allowing you to stream transparent lower-third lyrics and sermon notes directly to OBS, vMix, Wirecast, or hardware video switchers.' 
  },
  { 
    question: 'How does billing work and can I cancel anytime?', 
    answer: 'Our Free tier is free forever. Pro subscriptions can be billed monthly or annually (save 20%). You can upgrade, downgrade, or cancel anytime from your account portal, and your software will continue running offline on Sunday.' 
  }
]
</script>

<template>
  <div class="home">
    <!-- Section 1: Hero -->
    <section class="hero-section">
      <div class="hero-bg-glow"></div>
      <div class="container hero-content">
        <div class="hero-eyebrow">
          <span class="sparkle">✨</span>
          <span>Church presentation, reengineered</span>
        </div>

        <h1 class="hero-title">
          Run your service with<br />
          total confidence.
        </h1>

        <p class="hero-subtitle">
          SelahCue is the offline-first presentation &amp; ministry-assistance app that never blanks the screen — scripture, songs, timers, stage display, and NDI outputs, controlled from anywhere.
        </p>

        <div class="hero-actions">
          <UiButton variant="gradient" size="lg" to="/download">
            Download free
          </UiButton>
          <UiButton variant="outline" size="lg" href="#demo">
            Watch 2-min demo
          </UiButton>
        </div>

        <p class="hero-trust">
          <span>Free to start</span>
          <span class="dot">&middot;</span>
          <span>Works fully offline</span>
          <span class="dot">&middot;</span>
          <span>Windows, macOS &amp; mobile control</span>
        </p>

        <!-- Product Window Mockup -->
        <div class="hero-mockup-frame">
          <ConsoleMockup />
        </div>
      </div>
    </section>

    <!-- Section 2: Features Grid -->
    <section class="features-section">
      <div class="container">
        <div class="section-header">
          <UiBadge variant="accent" size="sm">FEATURES</UiBadge>
          <h2 class="section-title">Everything you need to run the service</h2>
          <p class="section-subtitle">All the tools you need to run a seamless service, built into one reliable application.</p>
        </div>

        <div class="features-grid">
          <FeatureCard 
            icon="📊" 
            title="Live presentation & outputs" 
            description="Real-time multi-screen output with a zero-blank hardware buffer guarantee." 
          />
          <FeatureCard 
            icon="📖" 
            title="Scripture at your fingertips" 
            description="Built-in WEB Bible with instant verse-by-verse reference lookup and quick search." 
          />
          <FeatureCard 
            icon="📋" 
            title="Service plans & timers" 
            description="Bounded run-sheet planning with automated stage countdown timers and TIME UP alerts." 
          />
          <FeatureCard 
            icon="🖥️" 
            title="Stage & confidence monitor" 
            description="Dedicated stage display showing current lyrics, next slide, presenter notes, and service clocks." 
          />
          <FeatureCard 
            icon="📡" 
            title="NDI & multi-output" 
            description="Direct NDI 5 broadcast streams to OBS, vMix, and Wirecast with transparent lower thirds." 
          />
          <FeatureCard 
            icon="🎤" 
            title="On-device transcript" 
            description="100% offline speech-to-text powered by local Whisper AI without relying on cloud services." 
          />
        </div>
      </div>
    </section>

    <!-- Section 3: Reliability Invariants Band -->
    <section class="reliability-section">
      <div class="container">
        <div class="section-header">
          <UiBadge variant="accent" size="sm">RELIABILITY</UiBadge>
          <h2 class="section-title">Built for the one moment you can't repeat</h2>
          <p class="section-subtitle">Core engineering guarantees designed for live Sunday worship environments.</p>
        </div>

        <div class="reliability-grid">
          <ReliabilityPillar 
            icon="⚡" 
            title="Never blanks the screen" 
            description="Hardware frame buffer holds the last-good image if any output glitches (NFR-024)." 
            metric="0 Blanks" 
            variant="primary"
          />
          <ReliabilityPillar 
            icon="📶" 
            title="Works fully offline" 
            description="100% local presentation engine. Internet backhaul drops will never stop your service (NFR-015)." 
            metric="100% Offline" 
            variant="preview"
          />
          <ReliabilityPillar 
            icon="⚡" 
            title="Fast & bounded" 
            description="≤3s cold start, capped GPU memory usage, and zero lag when triggering live slides." 
            metric="≤3s Start" 
            variant="warn"
          />
        </div>
      </div>
    </section>

    <!-- Section 4: Screens & Outputs Showcase -->
    <section class="outputs-section">
      <div class="container">
        <div class="outputs-layout">
          <div class="outputs-content">
            <UiBadge variant="accent" size="sm">SCREENS &amp; OUTPUTS</UiBadge>
            <h2 class="outputs-title">One live moment, every output</h2>
            <p class="outputs-body">
              Send clean lyrics to your main venue projectors, custom current/next slides to stage monitors, and transparent lower thirds to your livestream switcher — all simultaneously from one seat.
            </p>

            <ul class="outputs-checklist">
              <li class="checklist-item">
                <span class="check-icon">✓</span>
                <span><strong>Audience projector</strong> &middot; Full 4K resolution, clean typography, motion backgrounds</span>
              </li>
              <li class="checklist-item">
                <span class="check-icon">✓</span>
                <span><strong>Stage display (current/next/timer)</strong> &middot; Current slide, next item preview, countdown clock</span>
              </li>
              <li class="checklist-item">
                <span class="check-icon">✓</span>
                <span><strong>NDI output to OBS / vMix / Wirecast</strong> &middot; Direct IP feed with alpha channel transparency</span>
              </li>
            </ul>
          </div>

          <div class="outputs-visual">
            <OutputManagerMockup />
          </div>
        </div>
      </div>
    </section>

    <!-- Section 5: How It Works (3 Steps) -->
    <section class="steps-section">
      <div class="container">
        <div class="section-header">
          <UiBadge variant="accent" size="sm">HOW IT WORKS</UiBadge>
          <h2 class="section-title">Live in three steps</h2>
          <p class="section-subtitle">Designed for volunteer simplicity without sacrificing professional control.</p>
        </div>

        <div class="steps-grid">
          <div class="step-card">
            <div class="step-icon-box">01</div>
            <h3>Plan your service</h3>
            <p>Import songs, search scripture, add media, and set countdown timer thresholds in minutes.</p>
          </div>
          <div class="step-card">
            <div class="step-icon-box green">02</div>
            <h3>Go live with one tap</h3>
            <p>Stage content safely in Preview before sending to Live with a single click or keyboard shortcut.</p>
          </div>
          <div class="step-card">
            <div class="step-icon-box">03</div>
            <h3>Control from anywhere</h3>
            <p>Drive slides from the desktop operator console or pair any mobile phone over local Wi-Fi.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 6: Pricing Section -->
    <section class="pricing-section">
      <div class="container">
        <div class="section-header">
          <UiBadge variant="accent" size="sm">PRICING</UiBadge>
          <h2 class="section-title">Simple pricing. Cancel anytime.</h2>
          <p class="section-subtitle">Start free, upgrade when your church is ready, cancel anytime. Billed monthly or save 20% annually.</p>
        </div>

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

    <!-- Section 7: Community Testimonials -->
    <section class="testimonials-section">
      <div class="container">
        <div class="section-header">
          <UiBadge variant="accent" size="sm">TESTIMONIALS</UiBadge>
          <h2 class="section-title">Run by volunteers. Trusted on Sunday.</h2>
        </div>

        <div class="testimonials-grid">
          <TestimonialCard 
            v-for="t in testimonials" 
            :key="t.author"
            :quote="t.quote" 
            :author="t.author" 
            :role="t.role" 
            :avatarColor="t.color"
          />
        </div>
      </div>
    </section>

    <!-- Section 8: FAQ Accordion -->
    <section class="faq-section">
      <div class="container">
        <div class="section-header">
          <h2 class="section-title">Questions, answered</h2>
        </div>

        <div class="faq-wrapper">
          <FaqAccordion :items="faqItems" :defaultOpen="0" />
        </div>
      </div>
    </section>

    <!-- Section 9: Final CTA Band -->
    <section class="final-cta-section">
      <div class="container">
        <div class="final-cta-card">
          <h2 class="cta-title">Ready to run your best service yet?</h2>
          <p class="cta-subtitle">
            Start free and go live this Sunday. Cancel anytime — and it runs fully offline when it matters most.
          </p>
          <div class="cta-btn-group">
            <UiButton variant="ghost" size="lg" class="cta-btn-white" to="/download">Download free</UiButton>
            <UiButton variant="outline" size="lg" to="/pricing">View pricing</UiButton>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home {
  background: #090a0f;
  color: #ffffff;
  overflow-x: hidden;
}

.container {
  max-width: 1140px;
  margin: 0 auto;
  padding: 0 24px;
}

.section-header {
  text-align: center;
  max-width: 720px;
  margin: 0 auto 56px auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.section-title {
  font-size: 38px;
  font-weight: 800;
  color: #ffffff;
  line-height: 1.2;
  margin: 0;
  letter-spacing: -0.01em;
}

.section-subtitle {
  font-size: 16px;
  color: #8c97a8;
  line-height: 1.6;
  margin: 0;
}

/* Section 1: Hero */
.hero-section {
  position: relative;
  padding: 90px 0 80px 0;
  text-align: center;
}

.hero-bg-glow {
  position: absolute;
  top: -100px;
  left: 50%;
  transform: translateX(-50%);
  width: 900px;
  height: 600px;
  background: radial-gradient(circle at center, rgba(110, 92, 240, 0.15) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #141722;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 6px 16px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  color: #a5b4fc;
  margin-bottom: 24px;
}

.sparkle {
  font-size: 12px;
}

.hero-title {
  font-size: 58px;
  font-weight: 800;
  color: #ffffff;
  line-height: 1.12;
  letter-spacing: -0.02em;
  max-width: 900px;
  margin: 0 0 24px 0;
}

.hero-subtitle {
  font-size: 18px;
  color: #8c97a8;
  max-width: 780px;
  line-height: 1.6;
  margin: 0 0 36px 0;
}

.hero-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 20px;
}

.hero-trust {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #717d93;
  margin-bottom: 60px;
}

.dot {
  opacity: 0.5;
}

.hero-mockup-frame {
  width: 100%;
  max-width: 1040px;
  margin: 0 auto;
}

/* Section 2: Features */
.features-section {
  padding: 100px 0;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

/* Section 3: Reliability */
.reliability-section {
  padding: 100px 0;
}

.reliability-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

/* Section 4: Outputs Showcase */
.outputs-section {
  padding: 100px 0;
}

.outputs-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 60px;
  align-items: center;
}

.outputs-title {
  font-size: 38px;
  font-weight: 800;
  color: #ffffff;
  margin: 16px 0;
  line-height: 1.2;
}

.outputs-body {
  font-size: 16px;
  color: #8c97a8;
  line-height: 1.6;
  margin-bottom: 32px;
}

.outputs-checklist {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.checklist-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  font-size: 15px;
  color: #8c97a8;
  line-height: 1.5;
}

.checklist-item strong {
  color: #ffffff;
}

.check-icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(43, 182, 115, 0.15);
  color: #2bb673;
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

/* Section 5: Steps */
.steps-section {
  padding: 100px 0;
}

.steps-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.step-card {
  background: #12151e;
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 16px;
  padding: 32px 28px;
}

.step-icon-box {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: rgba(110, 92, 240, 0.15);
  border: 1px solid rgba(110, 92, 240, 0.3);
  color: #a5b4fc;
  font-weight: 800;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.step-icon-box.green {
  background: rgba(43, 182, 115, 0.15);
  border: 1px solid rgba(43, 182, 115, 0.3);
  color: #2bb673;
}

.step-card h3 {
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 10px 0;
}

.step-card p {
  font-size: 14px;
  color: #8c97a8;
  line-height: 1.6;
  margin: 0;
}

/* Section 6: Pricing */
.pricing-section {
  padding: 100px 0;
}

.pricing-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  align-items: stretch;
}

/* Section 7: Testimonials */
.testimonials-section {
  padding: 100px 0;
}

.testimonials-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

/* Section 8: FAQ */
.faq-section {
  padding: 100px 0;
}

.faq-wrapper {
  max-width: 800px;
  margin: 0 auto;
}

/* Section 9: Final CTA Band */
.final-cta-section {
  padding: 40px 0 100px 0;
}

.final-cta-card {
  background: linear-gradient(135deg, #4f46e5 0%, #312e81 100%);
  border-radius: 24px;
  padding: 64px 48px;
  text-align: center;
  box-shadow: 0 25px 60px rgba(79, 70, 229, 0.3);
}

.cta-title {
  font-size: 40px;
  font-weight: 800;
  color: #ffffff;
  margin: 0 0 16px 0;
}

.cta-subtitle {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.85);
  max-width: 680px;
  margin: 0 auto 36px auto;
  line-height: 1.6;
}

.cta-btn-group {
  display: flex;
  gap: 16px;
  justify-content: center;
}

.cta-btn-white {
  background: #ffffff !important;
  color: #312e81 !important;
  font-weight: 700;
}

@media (max-width: 1024px) {
  .hero-title { font-size: 44px; }
  .features-grid, .reliability-grid, .steps-grid, .pricing-grid, .testimonials-grid {
    grid-template-columns: 1fr;
  }
  .outputs-layout {
    grid-template-columns: 1fr;
  }
}
</style>
