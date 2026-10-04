<script setup lang="ts">
import { useId } from 'vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import ConsoleMockup from '@/components/ConsoleMockup.vue'
import OutputManagerMockup from '@/components/OutputManagerMockup.vue'
import FeatureCard from '@/components/FeatureCard.vue'
import ReliabilityPillar from '@/components/ReliabilityPillar.vue'
import PricingCard from '@/components/PricingCard.vue'
import TestimonialCard from '@/components/TestimonialCard.vue'
import FaqAccordion from '@/components/FaqAccordion.vue'
import HomeIcon from '@/components/home/HomeIcon.vue'

/*
 * COPY. Figma frame 468:125 is the wording wherever the repo backs it. Where Figma claims more than the
 * repo can show, the backed part is what ships (the ledger in docs/delivery/goals/17tnw2b2cex-figma-home.md
 * lists each line and why; tests/homeView.test.ts pins it). Sentences no finding replaces are left exactly
 * as they were: removing a claim the live page already makes is ClickUp 17tnw2b0x3h, not this change.
 */

/** Ties the disabled demo button to the sentence that says why (read after it in the page). */
const demoNoteId = `${useId()}-demo-note`

const features = [
  {
    icon: 'monitor',
    title: 'Live presentation & outputs',
    description: 'Stage scripture, songs, and slides in Preview, then Go Live to the audience — the output never blanks, even on a fault.'
  },
  {
    icon: 'book',
    title: 'Scripture at your fingertips',
    description: 'A bundled public-domain Bible with instant reference parsing and keyword search.'
  },
  {
    icon: 'list',
    title: 'Service plans & timers',
    description: 'Build the order of service, run countdowns, and keep every segment on time from the console or your phone.'
  },
  {
    icon: 'layout',
    title: 'Stage & confidence monitor',
    description: "A dedicated speaker view — current line, what's next, and the service timer — that the audience never sees."
  },
  {
    icon: 'radio',
    title: 'NDI & multi-output',
    description: 'Broadcast your program as an NDI source for OBS or vMix, with per-output orientation, scaling, mirror, and visible layers.'
  },
  {
    icon: 'mic',
    title: 'On-device transcript',
    description: 'AI that assists but never gates: a live transcript and spoken-scripture suggestions, on your machine by default.'
  }
]

const pillars = [
  {
    icon: 'shield-check',
    title: 'Never blanks the screen',
    description: 'No component failure — a bad slide, a lost GPU, a dropped controller — is ever allowed to black the live output.',
    variant: 'primary'
  },
  {
    icon: 'wifi-off',
    title: 'Works fully offline',
    description: 'Everything runs on-device — no internet and no cloud dependency during the service. It just works.',
    variant: 'preview'
  },
  {
    icon: 'zap',
    title: 'Fast & bounded',
    description: 'Starts fast and keeps memory bounded. No runaway caches, no creeping slowdown.',
    variant: 'warn'
  }
]

const outputChecks = [
  'Audience projector — the program the room sees',
  'Stage display — current, next & timer, for the speaker only',
  'NDI output — broadcast to OBS, vMix, or another machine'
]

const steps = [
  {
    title: 'Plan your service',
    description: 'Add songs, scripture, and sections to the order of service. Set countdowns and give any item its own theme.'
  },
  {
    title: 'Go live with one tap',
    description: 'Stage the next item in Preview, then Go Live. The audience, stage, and NDI outputs all update together.'
  },
  {
    title: 'Control from anywhere',
    description: 'Drive it from the console — or pair your phone over the local network. No internet, no lag, no surprises.'
  }
]

/*
 * `to` is only set where a real destination exists. Free goes to /download, which says honestly that
 * nothing downloads yet (the hero and navbar buttons already go there). Church goes to /contact.
 * Pro has none: no billing exists, so PricingCard shows its disabled "Not available yet" state.
 * The price, `/ month` and MOST POPULAR are as they were (audit home-33; removal is 17tnw2b0x3h).
 */
const pricingPlans = [
  {
    name: 'Free',
    price: 0,
    period: 'forever',
    description: 'Everything to run a service on one machine.',
    features: [
      'Live audience output + stage display',
      'Bundled public-domain scripture + search',
      'Service plans, timers & themes'
    ],
    cta: 'Download free',
    popular: false,
    to: '/download'
  },
  {
    name: 'Pro',
    price: 19,
    period: 'month',
    description: 'For multi-output and streaming churches.',
    features: [
      'Everything in Free',
      'NDI + multiple simultaneous outputs',
      'Mobile control over your local network'
    ],
    cta: 'Get Pro',
    popular: true,
    to: undefined
  },
  {
    name: 'Church',
    price: 'Custom',
    period: '',
    description: 'For multi-site teams and larger ministries.',
    features: [
      'Everything in Pro',
      'Multi-campus / site licensing'
    ],
    cta: 'Talk to us',
    popular: false,
    to: '/contact'
  }
]

/* The quotes, names and churches are as they were (audit home-36: removal is 17tnw2b0x3h). */
const testimonials = [
  {
    quote: "SelahCue changed how our tech team operates on Sunday. The volunteer onboarding time dropped to zero, and the platform is rock-solid.",
    author: "Sarah Jenkins",
    role: "Worship Director · Grace Community",
    color: "blue"
  },
  {
    quote: "We finally have a presentation tool that works 100% offline. No more Sunday morning panic when the church internet backhaul fails.",
    author: "Mark Davis",
    role: "Technical Director · Redeemer Church",
    color: "green"
  },
  {
    quote: "The stage confidence monitor and built-in countdown timers keep our pastors and worship leaders synchronized throughout every service.",
    author: "Pastor Paul Miller",
    role: "Lead Pastor · Hope Chapel",
    color: "amber"
  }
]

/* The platforms answer is as it was until Uma redraws it (audit home-38, 40 and 45). */
const faqItems = [
  {
    question: 'Do I need an internet connection?',
    answer: 'No. SelahCue is offline-first — the whole service runs on-device, so a dropped internet connection never stops it.'
  },
  {
    question: 'Which platforms are supported?',
    answer: 'SelahCue supports Windows 10/11 (64-bit) and macOS 12+ (Apple Silicon & Intel). Additionally, you can pair any iOS or Android phone over your local Wi-Fi network to control slides remotely.'
  },
  {
    question: 'Can I use my own songs, slides, and designs?',
    answer: 'Yes. Build multi-slide song lyrics, stage any scripture, and design your own slide templates in the Theme Designer.'
  },
  {
    question: 'What is NDI, and do I need it?',
    answer: "NDI sends your program video over the local network to software like OBS or vMix — no capture card required. It's optional."
  },
  {
    question: 'How does billing work?',
    answer: 'SelahCue Pro is a simple monthly subscription; the Free plan is free forever. Cancel anytime — and the app keeps running fully offline during your service either way.'
  }
]
</script>

<template>
  <div class="home">
    <!-- Section 1: Hero -->
    <section class="hero-section">
      <div class="hero-bg-glow" aria-hidden="true"></div>
      <div class="container hero-content">
        <div class="hero-eyebrow">
          <span class="brand-mark" :style="{ '--mark-size': '18px' }"><img src="/selahcue-logo.png" alt="" aria-hidden="true" /></span>
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
          <UiButton variant="primary" size="lg" to="/download">
            Download free
          </UiButton>
          <!-- The demo video does not exist yet (audit home-18, class C: remove or relabel is Uma's and
               the owner's call; removing the claim is 17tnw2b0x3h). It was a link to #demo, which did
               nothing. Disabled with a spoken reason, like the plan button below, until that is decided. -->
          <UiButton variant="secondary" size="lg" disabled :aria-describedby="demoNoteId">
            <HomeIcon class="demo-play" name="play" :size="11" />
            Watch 2-min demo
          </UiButton>
          <span :id="demoNoteId" class="visually-hidden">The demo video is not available yet.</span>
        </div>

        <p class="hero-trust">Free to start&nbsp;&nbsp;&middot;&nbsp;&nbsp;Works fully offline&nbsp;&nbsp;&middot;&nbsp;&nbsp;Windows, macOS &amp; mobile control</p>

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
          <UiBadge variant="eyebrow">FEATURES</UiBadge>
          <h2 class="section-title">Everything you need to run the service</h2>
          <p class="section-subtitle">One app for the whole ministry moment — from planning the order of service to the last slide, on stage and online.</p>
        </div>

        <div class="features-grid">
          <FeatureCard
            v-for="feature in features"
            :key="feature.title"
            :icon="feature.icon"
            :title="feature.title"
            :description="feature.description"
          />
        </div>
      </div>
    </section>

    <!-- Section 3: Reliability Invariants Band -->
    <section class="reliability-section">
      <div class="container">
        <div class="section-header">
          <UiBadge variant="eyebrow">WHY SELAHCUE</UiBadge>
          <!-- Figma draws the break after "moment" (two lines of 760px); phones let it wrap. -->
          <h2 class="section-title is-reliability">Built for the one moment<br />you can't repeat</h2>
          <p class="section-subtitle">Sunday morning doesn't wait for a spinning cursor. SelahCue is engineered so the audience output is always up — reliable, offline, and fast.</p>
        </div>

        <div class="reliability-grid">
          <ReliabilityPillar
            v-for="pillar in pillars"
            :key="pillar.title"
            :icon="pillar.icon"
            :title="pillar.title"
            :description="pillar.description"
            :variant="pillar.variant"
          />
        </div>
      </div>
    </section>

    <!-- Section 4: Screens & Outputs Showcase -->
    <section class="outputs-section">
      <div class="container">
        <div class="outputs-layout">
          <div class="outputs-content">
            <UiBadge variant="eyebrow">SCREENS &amp; OUTPUTS</UiBadge>
            <h2 class="outputs-title">One live moment, every output</h2>
            <p class="outputs-body">
              Send the same live content to your projector, a stage confidence monitor, and an NDI stream — each with its own theme, orientation, scaling, and visible layers.
            </p>

            <ul class="outputs-checklist">
              <li v-for="check in outputChecks" :key="check" class="checklist-item">
                <HomeIcon class="check-icon" name="check" :size="18" :stroke="1.8" />
                <span>{{ check }}</span>
              </li>
            </ul>
          </div>

          <div class="outputs-visual">
            <OutputManagerMockup />
          </div>
        </div>
      </div>
    </section>

    <!-- Section 5: How It Works (3 Steps). The id is the target of the navbar's "How it works" link
         (/#how-it-works) from every page; main.css gives it its scroll offset under the sticky bar. -->
    <section id="how-it-works" class="steps-section">
      <div class="container">
        <div class="section-header">
          <UiBadge variant="eyebrow">HOW IT WORKS</UiBadge>
          <h2 class="section-title">Live in three steps</h2>
          <p class="section-subtitle">From an empty plan to a running service in minutes — no manual, no setup weekend.</p>
        </div>

        <ol class="steps-grid" role="list">
          <li v-for="(step, index) in steps" :key="step.title" class="step-card">
            <span class="step-marker" aria-hidden="true">{{ index + 1 }}</span>
            <h3 class="step-title">{{ step.title }}</h3>
            <p class="step-body">{{ step.description }}</p>
          </li>
        </ol>
      </div>
    </section>

    <!-- Section 6: Pricing Section -->
    <section class="pricing-section">
      <div class="container">
        <div class="section-header">
          <UiBadge variant="eyebrow">PRICING</UiBadge>
          <h2 class="section-title">Simple pricing. Cancel anytime.</h2>
          <p class="section-subtitle">Start free, upgrade when you're ready, and cancel anytime — it still runs fully offline on Sunday.</p>
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
            :to="plan.to"
          />
        </div>
      </div>
    </section>

    <!-- Section 7: Community Testimonials -->
    <section class="testimonials-section">
      <div class="container">
        <div class="section-header">
          <UiBadge variant="eyebrow">TESTIMONIALS</UiBadge>
          <h2 class="section-title is-compact">Run by volunteers. Trusted on Sunday.</h2>
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
          <h2 class="section-title is-compact">Questions, answered</h2>
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
            <UiButton variant="inverse" size="lg" to="/download">Download free</UiButton>
            <UiButton variant="inverse-outline" size="lg" to="/pricing">See pricing</UiButton>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/*
 * The page ground is the body's (--sc-base); each section sits on it, and Reliability and Testimonials
 * are full-width panel bands. The content column is the shared `.container` (main.css: 1248 of content
 * at 96px gutters, stepping to 48 and 20), not a local rule: the local one was 1092 wide and overrode it.
 *
 * No `overflow-x: hidden` here: it would hide real clipping bugs from the responsive sweep. The glow is
 * contained by the hero itself, and every grid track is `minmax(0, 1fr)` so content can never widen a
 * column.
 */
.home {
  color: var(--sc-text);
  /* The accessible light indigo for small brand text on a dark pill: Figma's #5b6bd6 is 3.7:1 there
     (audit home-15, class B; home-44, class D: Uma picks the final tint). 9.6:1 on the hero pill. */
  --home-brand-ink: #a5b4fc;
}

/* Spoken, not seen: the reason the demo button is disabled. */
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}

/*
 * Section headers (Figma 472:125 and its siblings): eyebrow, title and subtitle, centred, 14px apart
 * (15 on Reliability, 13 on Testimonials), then a gap to the content that is different in every
 * section (48 / 52 / 50 / 48 / 46 / 40). Each section declares its own numbers in custom properties.
 */
.section-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--header-gap-inner, 14px);
  max-width: 760px;
  margin: 0 auto var(--header-gap, 48px);
  text-align: center;
}

.section-title {
  margin: 0;
  font-size: 40px;
  font-weight: 700;
  /* Figma's titles are 46px tall, except How it works and Pricing, which have no fixed line height and
     measure 48 (the section sets --title-lh). */
  line-height: var(--title-lh, 46px);
  letter-spacing: 0;
  color: var(--sc-text);
}

/* Reliability's title is the handoff's H2 token (42/48). */
.section-title.is-reliability {
  font: var(--font-h2);
}

/* Testimonials and FAQ draw a 38px title. */
.section-title.is-compact {
  font-size: 38px;
}

.section-subtitle {
  margin: 0;
  max-width: var(--sub-width, 640px);
  font-size: 18px;
  line-height: 27px;
  color: var(--sc-text-secondary);
}

/* Section 1: Hero (Figma 469:124: padding 96 / 72, 26px between the blocks) */
.hero-section {
  position: relative;
  padding: 96px 0 72px;
  text-align: center;
  /* Clip the glow at the top edge of the page (as the old page-wide overflow did) without
     creating a scroll container, and without clipping the mockup's drop shadow below. */
  clip-path: inset(0 0 -120px 0);
}

/* Not drawn in Figma (audit home-19, class D: Uma decides whether it stays). Kept as it was. */
.hero-bg-glow {
  position: absolute;
  top: -100px;
  left: 50%;
  transform: translateX(-50%);
  /* `min()` so the glow can never be wider than the page -- it is the only element that
     ever overflowed here, and clipping it with overflow:hidden would hide real bugs too. */
  width: min(900px, 100%);
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
  gap: 26px;
}

/* Figma 469:125: a 32px pill (darkened ground, darkened edge) with the 18px logo mark and 12.5/600 words.
   Figma measures padding from the OUTER edge, so the 1px border comes off it (7/16/7/14 becomes 6/15/6/13). */
.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 15px 6px 13px;
  line-height: 15px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(0, 0, 0, 0.4);
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--home-brand-ink);
}

.hero-title {
  max-width: 920px;
  margin: 0;
  font: var(--font-h1);
  letter-spacing: 0;
  color: var(--sc-text);
}

.hero-subtitle {
  max-width: 720px;
  margin: 0;
  font-size: 19px;
  line-height: 29px;
  color: var(--sc-text-secondary);
}

/* Centred, so the quiet 47px button is not stretched to the 49px solid one beside it (PR 172 review). */
.hero-actions {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding-top: 8px;
}

.demo-play {
  /* The frame's gap between the glyph and the label is 9, the button's own is 8. */
  margin-right: 1px;
}

.hero-trust {
  margin: 0;
  font-size: 13.5px;
  line-height: 16px;
  letter-spacing: 0.005em;
  color: var(--sc-text-secondary);
}

.hero-mockup-frame {
  width: 100%;
  max-width: 1140px;
  margin: 0 auto;
}

/* Section 2: Features (Figma 472:124: 88px, header gap 48, cards 20 apart) */
.features-section {
  padding-block: var(--section-pad);
  --header-gap: 48px;
  --sub-width: 640px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

/* Section 3: Reliability (Figma 474:124: a full-width panel band, 90px, header gap 52, cards 28 apart) */
/* The band's 1px edge rules count towards Figma's 90: Figma draws the stroke inside the frame. */
.reliability-section {
  padding-block: calc(var(--section-pad) + 1px);
  background: var(--sc-surface);
  border-block: 1px solid var(--sc-border);
  --header-gap: 52px;
  --header-gap-inner: 15px;
  --sub-width: 660px;
}

.reliability-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 28px;
}

/* Section 4: Outputs Showcase (Figma 475:124: 90px, text 470 | window 706, 72 apart, centred) */
.outputs-section {
  padding-block: calc(var(--section-pad) + 2px);
}

.outputs-layout {
  display: grid;
  grid-template-columns: 470px minmax(0, 1fr);
  gap: 72px;
  align-items: center;
}

.outputs-content {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 22px;
  min-width: 0;
}

.outputs-title {
  margin: 0;
  font-size: 40px;
  font-weight: 700;
  line-height: 46px;
  letter-spacing: 0;
  color: var(--sc-text);
}

.outputs-body {
  margin: 0;
  font-size: 17px;
  line-height: 26px;
  color: var(--sc-text-secondary);
}

.outputs-checklist {
  display: flex;
  flex-direction: column;
  gap: 13px;
  width: 100%;
  padding-top: 4px;
  list-style: none;
  margin: 0;
}

.checklist-item {
  display: flex;
  align-items: center;
  gap: 11px;
  font-size: 15px;
  line-height: 18px;
  color: var(--sc-text);
}

.check-icon {
  color: var(--sc-preview);
}

.outputs-visual {
  min-width: 0;
}

/* Section 5: Steps (Figma 476:124: 88px, header gap 50, cards 28 apart) */
.steps-section {
  padding-block: var(--section-pad);
  --title-lh: 48px;
  --header-gap: 50px;
  --sub-width: 600px;
}

.steps-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 28px;
}

.step-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
  /* Figma's 30/28 is measured from the outer edge: the 1px border comes off it. */
  padding: 29px 27px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
}

/* Figma 476:131: a 46px brand circle holding a white 21/700 numeral, the same on all three. */
.step-marker {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 999px;
  background: var(--sc-primary);
  /* Pure white on the brand fill (4.7:1). */
  color: #fff;
  font-size: 21px;
  font-weight: 700;
  line-height: 25px;
}

.step-title {
  margin: 0;
  font: var(--font-h3);
  line-height: 25px;
  color: var(--sc-text);
}

.step-body {
  margin: 0;
  font-size: 15px;
  line-height: 23px;
  color: var(--sc-text-secondary);
}

/* Section 6: Pricing (Figma 477:124: 90px, header gap 48, cards 24 apart) */
.pricing-section {
  padding-block: calc(var(--section-pad) + 2px);
  --title-lh: 48px;
  --header-gap: 48px;
  --sub-width: 620px;
}

.pricing-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
  align-items: start;
}

/* Section 7: Testimonials (Figma 478:124: a full-width panel band, 90px, header gap 46, cards 24 apart) */
.testimonials-section {
  padding-block: calc(var(--section-pad) + 1px);
  background: var(--sc-surface);
  border-block: 1px solid var(--sc-border);
  --header-gap: 46px;
  --header-gap-inner: 13px;
}

.testimonials-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

/* Section 8: FAQ (Figma 478:153: 90px, header gap 40, a 780px list) */
.faq-section {
  padding-block: calc(var(--section-pad) + 2px);
  --header-gap: 40px;
}

.faq-wrapper {
  max-width: 780px;
  margin: 0 auto;
}

/*
 * The shared accordion draws 17/600 questions, 15/1.6 answers and a 24px gap between an open question
 * and its answer; Figma 478:155 draws 18/600, 15.5/24 and 10px. Pricing draws the same rows, so the
 * proper home for this is FaqAccordion's defaults (a shared file, reported rather than edited here);
 * until then the page skins it.
 */
.faq-wrapper :deep(.faq-question) {
  font-size: 18px;
}

.faq-wrapper :deep(.faq-item.open .faq-question) {
  padding-bottom: 10px;
}

.faq-wrapper :deep(.faq-answer p) {
  font-size: 15.5px;
  line-height: 24px;
}

/* Section 9: Final CTA Band (Figma 479:124: 90px; the card 1248 wide, radius 24, gradient, no shadow) */
.final-cta-section {
  padding-block: calc(var(--section-pad) + 2px);
}

.final-cta-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 22px;
  padding: 64px 48px;
  border-radius: 24px;
  background: var(--gradient-cta);
  text-align: center;
}

/* Pure white on the gradient: the handoff's second non-token colour (section 3). */
.cta-title {
  max-width: 760px;
  margin: 0;
  font-size: 44px;
  font-weight: 700;
  line-height: 50px;
  letter-spacing: 0;
  color: #fff;
}

/* White, not Figma's #dbe0fa: that is 3.6:1 on the lightest end of the gradient and 4.2:1 where the copy
   sits on a phone; white is 4.7:1 or better everywhere (class B, flagged to Uma). */
.cta-subtitle {
  max-width: 600px;
  margin: 0;
  font-size: 19px;
  line-height: 28px;
  color: #fff;
}

.cta-btn-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding-top: 10px;
}

/* Tablet (768-1199): grids go 2-up (a third card wraps), pricing goes 1-up with the Pro
   card first, the outputs image drops below its text, and the H1 steps down (design 8a/8d). */
@media (max-width: 1199.98px) {
  .section-title,
  .section-title.is-reliability,
  .section-title.is-compact,
  .outputs-title {
    font-size: 34px;
    line-height: 40px;
  }
  .features-grid, .reliability-grid, .steps-grid, .testimonials-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .pricing-grid {
    grid-template-columns: minmax(0, 1fr);
    max-width: 520px;
    margin-inline: auto;
  }
  .pricing-grid > .popular { order: -1; }
  .outputs-layout {
    grid-template-columns: minmax(0, 1fr);
    gap: 40px;
  }
  .hero-section { padding: 72px 0 64px; }
  .final-cta-card { padding: 56px 40px; }
  .cta-title { font-size: 38px; line-height: 44px; }
}

/* Mobile (<768): everything 1-up, 20px gutters, H1 36/40, CTAs stack full-width. */
@media (max-width: 767.98px) {
  .hero-section { padding: 48px 0 48px; }
  .hero-content { gap: 20px; }
  /* The designed line break leaves an orphaned "with" on its own line at phone widths. */
  .hero-title br,
  .section-title br { display: none; }
  .hero-subtitle { font-size: 16px; line-height: 26px; }
  .hero-actions { flex-direction: column; align-self: stretch; padding-top: 0; }
  .hero-actions > .ui-button { width: 100%; }
  .hero-trust { font-size: 13px; line-height: 18px; text-wrap: balance; }
  .section-header { margin-bottom: 32px; }
  .section-title,
  .section-title.is-reliability,
  .section-title.is-compact,
  .outputs-title {
    font-size: 28px;
    line-height: 34px;
  }
  .section-subtitle { font-size: 15px; line-height: 24px; }
  .features-grid, .reliability-grid, .steps-grid, .testimonials-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
  }
  .pricing-grid { gap: 20px; }
  .outputs-layout { gap: 32px; }
  .step-card { padding: 23px 19px; }
  .final-cta-card { padding: 40px 24px; border-radius: 20px; }
  .cta-title { font-size: 28px; line-height: 34px; }
  .cta-subtitle { font-size: 16px; line-height: 24px; }
  .cta-btn-group { flex-direction: column; align-self: stretch; padding-top: 0; }
  .cta-btn-group > .ui-button { width: 100%; }
}
</style>
