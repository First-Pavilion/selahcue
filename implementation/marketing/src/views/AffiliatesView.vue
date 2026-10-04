<script setup lang="ts">
import { ref, computed } from 'vue'
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import FaqAccordion from '@/components/FaqAccordion.vue'
import CategoryIcon from '@/components/article/CategoryIcon.vue'

const monthlyReferrals = ref(10)

const estimatedMonthlyEarnings = computed(() => {
  // 20% of $19/mo = $3.80 per referral / month
  return monthlyReferrals.value * 3.8
})

const estimatedAnnualEarnings = computed(() => {
  return estimatedMonthlyEarnings.value * 12
})

/**
 * Every figure on this page (the rate, the window, the threshold, the payout rails) is the build's own and is
 * unbacked: the programme is NOT-V1 and its terms are undecided (audit affiliates-12 to 14, ClickUp 17tnw2b0x3h
 * owns removing them). This ticket restyles what is already here and adds none: the sections the frame draws
 * that the build lacked carry copy without a figure, a rate, a price or a promise.
 */
const faqItems = [
  { question: 'What is the commission rate?', answer: 'You earn a 20% recurring commission for 12 months on every paid subscription that signs up using your referral link.' },
  { question: 'How long does the referral cookie last?', answer: 'Our referral tracking uses a 60-day last-click attribution window.' },
  { question: 'When are affiliate payouts made?', answer: 'Payouts are processed on the 1st of every month via PayPal or Direct Bank Transfer once you reach the $50 minimum threshold.' },
  { question: 'Who can join the affiliate program?', answer: 'Worship leaders, tech consultants, Christian bloggers, YouTubers, and church network leaders are welcome to apply!' }
]

/** The stat cards (Figma 541:150): four, the value in the frame's inks in turn. The first three are the build's own. */
const highlights = [
  { value: '20%', caption: 'Recurring Commission', tone: 'is-brand' },
  { value: '60 Days', caption: 'Cookie Attribution', tone: 'is-preview' },
  { value: '$50', caption: 'Low Payout Threshold', tone: 'is-warn' },
  { value: 'Offline', caption: 'Slides and timers run offline', tone: 'is-brand' }
]

/**
 * How it works (Figma 541:163): the frame's three steps, each saying what the VISITOR does. None says what happens
 * to money, how often or how much: the programme's terms are undecided, so a step that restated "earn" would be a
 * second copy of the claim the page already carries (ClickUp 17tnw2b0x3h owns removing that one).
 */
const steps = [
  { n: '01', title: 'Apply to join', body: "Tell us how you'll share SelahCue." },
  { n: '02', title: 'Share SelahCue', body: 'Recommend it anywhere your audience is.' },
  { n: '03', title: 'Refer a church', body: 'Introduce SelahCue to a church that could use it.' }
]

/** Made for people who talk to churches (Figma 542:124): audience descriptions, not product claims. */
const audiences = [
  { icon: 'video', tone: 'brand', title: 'Church tech creators', body: 'Bloggers, YouTubers and newsletter writers in the worship-tech space.' },
  { icon: 'package', tone: 'preview', title: 'AV & gear resellers', body: 'Sell projectors, mixers and stage gear? Add software your customers need.' },
  { icon: 'users', tone: 'warn', title: 'Ministry networks', body: 'Denominations and multi-site networks recommending tools to member churches.' },
  { icon: 'briefcase', tone: 'brand', title: 'Consultants & integrators', body: 'You set up church production rigs — bundle SelahCue into your builds.' }
] as const

/**
 * The checklist (Figma 542:154): the two lines the repo backs, in the repo's own terms. The live output is DESIGNED
 * never to blank on a fault (a requirement, not a guarantee), and the live core runs on the desktop with no network
 * (a new activation or a licensed download still needs one once, so "no internet" alone would say too much).
 */
const reasons = [
  'Designed so a fault never blanks the live screen',
  'Offline-first: slides, scripture and timers run on the desktop with no network'
]
</script>

<template>
  <div class="affiliates-page">
    <section class="hero-section container">
      <UiBadge variant="featured">AFFILIATE PROGRAM</UiBadge>
      <h1 class="hero-title">Recommend SelahCue. Earn 20% Recurring Commission.</h1>
      <p class="hero-sub">Help churches upgrade their live worship presentation. Earn passive recurring income on every paid referral for 12 months.</p>

      <!-- The affiliate Apply and Sign in screens have no route yet (audit affiliates-06, a missing screen). Apply goes
           to the contact page, as an interim, because a CTA to Apply already existed here. Sign in goes NOWHERE: the
           only affiliate pages are presentation shells full of sample figures that look like a live account, so the
           button is disabled and says so, as the Pro plan does on the pricing page. -->
      <div class="hero-actions">
        <div class="hero-ctas">
          <UiButton variant="primary" size="lg" to="/contact">Apply now</UiButton>
          <UiButton variant="outline" size="lg" disabled aria-describedby="signin-note">Affiliate sign in</UiButton>
        </div>
        <p id="signin-note" class="cta-note">Affiliate sign in: not available yet</p>
      </div>
    </section>

    <!-- Highlights: four stat cards -->
    <section class="highlights-section container">
      <div class="highlights-grid">
        <div v-for="h in highlights" :key="h.value" class="highlight-card">
          <div :class="['hl-value', h.tone]">{{ h.value }}</div>
          <p>{{ h.caption }}</p>
        </div>
      </div>
    </section>

    <!-- How it works -->
    <section class="steps-section" aria-labelledby="steps-heading">
      <div class="container steps-inner">
        <div class="section-head">
          <h2 id="steps-heading" class="section-title">How it works</h2>
          <p class="section-sub">Three steps to get started.</p>
        </div>
        <div class="steps-grid">
          <article v-for="s in steps" :key="s.n" class="step-card">
            <span class="step-chip" aria-hidden="true">{{ s.n }}</span>
            <h3 class="step-title">{{ s.title }}</h3>
            <p class="step-body">{{ s.body }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- Audiences -->
    <section class="audience-section container" aria-labelledby="audience-heading">
      <h2 id="audience-heading" class="audience-title">Made for people who talk to churches</h2>
      <div class="audience-grid">
        <article v-for="a in audiences" :key="a.title" class="audience-card">
          <CategoryIcon :name="a.icon" :tone="a.tone" size="audience" />
          <h3 class="audience-card-title">{{ a.title }}</h3>
          <p class="audience-card-body">{{ a.body }}</p>
        </article>
      </div>
    </section>

    <!-- Why it's easy to recommend, with the calculator beside it (the owner decides what stays: affiliates-10) -->
    <section class="why-section container" aria-labelledby="why-heading">
      <div class="why-main">
        <h2 id="why-heading" class="why-title">Why it's easy to recommend</h2>
        <ul class="check-list">
          <li v-for="r in reasons" :key="r" class="check-row">
            <svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <span>{{ r }}</span>
          </li>
        </ul>
      </div>

      <div id="calculator" class="calc-card">
        <h2 class="calc-title">Estimate Your Earnings</h2>
        <p class="calc-sub">Slide to see how much you could earn by recommending SelahCue to churches:</p>

        <div class="slider-wrapper">
          <div class="slider-label">
            <span id="calc-slider-label">Referred Active Churches:</span>
            <strong class="count-badge">{{ monthlyReferrals }} churches</strong>
          </div>
          <input
            v-model.number="monthlyReferrals"
            type="range"
            min="1"
            max="100"
            class="range-slider"
            aria-labelledby="calc-slider-label"
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
    </section>

    <!-- FAQ: the boxed card on a panel band -->
    <section class="faq-section" aria-labelledby="faq-heading">
      <div class="container faq-inner">
        <h2 id="faq-heading" class="faq-title">Affiliate FAQ</h2>
        <FaqAccordion boxed :items="faqItems" :defaultOpen="0" />
      </div>
    </section>

    <!-- Closing band -->
    <section class="cta-section container" aria-labelledby="cta-heading">
      <div class="cta-band">
        <h2 id="cta-heading" class="cta-title">Ready to get started?</h2>
        <p class="cta-sub">Apply to join the SelahCue affiliate program.</p>
        <div class="cta-actions">
          <!-- No destination: a button this page newly adds does not point at a form that sends nothing. It is
               disabled and says why, until the application exists. -->
          <UiButton variant="inverse" size="lg" disabled aria-describedby="apply-note">Apply now</UiButton>
          <p id="apply-note" class="cta-note on-band">Not available yet</p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.affiliates-page { background: var(--sc-base); }

/* HERO (Figma 541:139): padding 96 top / 56 bottom, 22px between the pill, the headline, the subline and the
   buttons, all centred. The headline takes the shared page-hero token, set to the frame's 54/60 from the desktop
   breakpoint up, and is held to two lines (the frame's own sentence is shorter, so its box is about 600 wide; the
   build's sentence needs 880). The two buttons are one flex row that stretches them
   to the same height, as the frame draws both at 49. */
.hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 22px;
  padding-top: 96px;
  padding-bottom: 56px;
  text-align: center;
}

.hero-title { font: var(--font-h1-page); color: var(--sc-text); max-width: 880px; }

@media (min-width: 1200px) {
  .hero-title { font-size: 54px; line-height: 60px; }
}

.hero-sub { max-width: 760px; font-size: 19px; line-height: 30px; color: var(--sc-text-secondary); }
.hero-actions { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.hero-ctas { display: flex; justify-content: center; gap: 14px; padding-top: 6px; }

/* The note that explains a disabled button (the same line the pricing plans use). */
.cta-note { font-size: 13px; line-height: 19px; color: var(--sc-text-secondary); }
.cta-note.on-band { color: #fff; }

/* STAT CARDS (Figma 541:150): four 295.5 cards, 22px apart, radius 18, padding 26 / 24 from the edge, left aligned,
   a 34/700 value over a one-line caption. */
.highlights-section { padding-bottom: 64px; }
.highlights-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 22px; }

.highlight-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 18px;
  padding: 25px 23px;
}

.hl-value { font-size: 34px; font-weight: 700; line-height: 41px; color: var(--sc-primary); }
.hl-value.is-preview { color: var(--sc-preview); }
.hl-value.is-warn { color: var(--sc-warn); }
.highlight-card p { font-size: 14.5px; line-height: 21px; color: var(--sc-text-secondary); }

/* HOW IT WORKS (Figma 541:163): a full-bleed panel band, padding 64 / 64, 32px between the heading block and the
   steps; steps are 400 wide on the page fill, 24px apart, radius 18, padding 28 / 26 from the edge. */
.steps-section { background: var(--sc-surface-alt); }
.steps-inner { display: flex; flex-direction: column; gap: 32px; padding-top: 64px; padding-bottom: 64px; }
.section-head { display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; }
.section-title { font-size: 38px; font-weight: 700; line-height: 46px; color: var(--sc-text); }
.section-sub { font-size: 18px; line-height: 22px; color: var(--sc-text-secondary); }

.steps-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; align-items: start; }

.step-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
  background: var(--sc-base);
  border: 1px solid var(--sc-border);
  border-radius: 18px;
  padding: 27px 25px;
}

/* The brand ink of the frame's number is 3.4:1 on the chip; the chip takes the text colour until Uma chooses an
   accessible brand ink (class D). */
.step-chip {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 12px;
  background: var(--sc-elevated);
  font-size: 18px;
  font-weight: 700;
  color: var(--sc-text);
}

.step-title { font-size: 20px; font-weight: 600; line-height: 24px; color: var(--sc-text); }
.step-body { font-size: 15.5px; line-height: 24px; color: var(--sc-text-secondary); }

/* AUDIENCES (Figma 542:124): padding 64 / 56, 32px between the centred heading and four 295.5 cards 22px apart. */
.audience-section { display: flex; flex-direction: column; gap: 32px; padding-top: 64px; padding-bottom: 56px; }
.audience-title { font-size: 34px; font-weight: 700; line-height: 41px; text-align: center; color: var(--sc-text); }
.audience-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 22px; align-items: start; }

.audience-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 13px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 18px;
  padding: 25px 23px;
}

.audience-card-title { font-size: 17.5px; font-weight: 600; line-height: 21px; color: var(--sc-text); }
.audience-card-body { font-size: 14.5px; line-height: 22px; color: var(--sc-text-secondary); }

/* WHY IT'S EASY TO RECOMMEND (Figma 542:154): padding 56 top / 64 bottom, two columns 56px apart: the heading and
   the checklist on the left, a 420px card on the right. */
.why-section {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 56px;
  align-items: start;
  padding-top: 56px;
  padding-bottom: 64px;
}

.why-main { display: flex; flex-direction: column; gap: 18px; }
.why-title { font-size: 30px; font-weight: 700; line-height: 36px; color: var(--sc-text); }
.check-list { display: flex; flex-direction: column; gap: 14px; }
.check-row { display: flex; align-items: flex-start; gap: 12px; font-size: 16.5px; line-height: 24px; color: var(--sc-text); }
.check-icon { flex-shrink: 0; width: 18px; height: 20px; margin-top: 2px; color: var(--sc-preview); }

/* The calculator is the build's own (affiliates-10: whether it stays is the owner's and Uma's decision). It
   takes the frame's card geometry (420 wide, radius 20, padding 28 from the edge) and its labels and count the
   readable inks; the slider now has a name. */
.calc-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 27px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.calc-title { font-size: 17px; font-weight: 600; line-height: 21px; color: var(--sc-text); }
.calc-sub { font-size: 14.5px; line-height: 21px; color: var(--sc-text-secondary); }

.slider-label { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 14.5px; color: var(--sc-text); }
.count-badge { font-size: 18px; color: var(--sc-text); }

.range-slider { width: 100%; height: 8px; border-radius: 4px; background: var(--sc-elevated); accent-color: var(--sc-primary); cursor: pointer; }

.results-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.result-box { background: var(--sc-elevated); border: 1px solid var(--sc-border); border-radius: 12px; padding: 16px 12px; text-align: center; }
.result-box.highlight { background: var(--sc-accent-soft); border-color: var(--sc-primary); }
.res-label { font-size: 12px; text-transform: uppercase; color: var(--sc-text-secondary); display: block; margin-bottom: 6px; }
.res-amount { font-size: 24px; font-weight: 800; color: var(--sc-text); }

/* FAQ (Figma 542:197): a full-bleed panel band, padding 56 / 64, 28px between the centred heading and the boxed
   card (the boxed look is FaqAccordion's own option). */
.faq-section { background: var(--sc-surface-alt); }
.faq-inner { display: flex; flex-direction: column; gap: 28px; padding-top: 56px; padding-bottom: 64px; }
.faq-title { font-size: 34px; font-weight: 700; line-height: 41px; text-align: center; color: var(--sc-text); }

/* CLOSING BAND (Figma 542:227): a 1248 gradient card, radius 24, padding 48 / 64, 20px between its parts, all
   centred, on the page fill with 64px above and below. The subline is solid white (the frame draws it at 90%,
   which is 4.3:1 on the lighter end of the gradient). */
.cta-section { padding-top: 64px; padding-bottom: 64px; }

.cta-band {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  background: var(--gradient-cta);
  border-radius: 24px;
  padding: 48px 64px;
  text-align: center;
}

.cta-title { font-size: 40px; font-weight: 700; line-height: 48px; color: #fff; }
.cta-sub { max-width: 640px; font-size: 18px; line-height: 27px; color: #fff; }
.cta-actions { display: flex; flex-direction: column; align-items: center; gap: 10px; padding-top: 6px; }

@media (max-width: 1199.98px) {
  .highlights-grid, .audience-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .steps-grid { grid-template-columns: minmax(0, 1fr); }
  .why-section { grid-template-columns: minmax(0, 1fr); gap: 32px; }
  .calc-card { max-width: 560px; }
}

@media (max-width: 767.98px) {
  .hero-section { padding-top: 56px; padding-bottom: 36px; gap: 18px; }
  .hero-sub { font-size: 16px; line-height: 26px; }
  .hero-actions { align-self: stretch; }
  .hero-ctas { flex-direction: column; align-self: stretch; }
  .hero-ctas > * { width: 100%; }
  .highlights-section { padding-bottom: 40px; }
  .highlights-grid, .audience-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .steps-inner { padding-top: 44px; padding-bottom: 44px; }
  .section-title { font-size: 30px; line-height: 38px; }
  .audience-section { padding-top: 44px; padding-bottom: 40px; }
  .audience-title, .faq-title { font-size: 28px; line-height: 34px; }
  .why-section { padding-top: 36px; padding-bottom: 44px; }
  .why-title { font-size: 26px; line-height: 32px; }
  .results-grid { grid-template-columns: minmax(0, 1fr); }
  /* The native range input's box IS its hit area; 8px is untappable. Make the box 44px
     and let the thumb + accent-color carry the look instead of a painted 8px bar. */
  .range-slider { height: 44px; background: transparent; }
  .faq-inner { padding-top: 40px; padding-bottom: 44px; }
  .cta-section { padding-top: 40px; padding-bottom: 40px; }
  .cta-band { padding: 32px 20px; border-radius: 20px; }
  .cta-title { font-size: 30px; line-height: 38px; }
  .cta-sub { font-size: 16px; line-height: 24px; }
  .cta-actions { align-self: stretch; }
  .cta-actions .ui-button { width: 100%; }
}
</style>
