<script setup lang="ts">
import UiBadge from '@/components/UiBadge.vue'
import UiButton from '@/components/UiButton.vue'
import CategoryIcon from '@/components/article/CategoryIcon.vue'

/**
 * NO PROGRAMME TERMS ON THIS PAGE (ClickUp 17tnw2b0x3h). The programme is NOT-V1 and its terms are undecided, so the page states
 * no rate, no cookie window, no payout threshold, no payout rail, no length of commission and has no earnings calculator. The
 * stat cards, the calculator, the FAQ (every answer restated those terms or invited people to apply) and the closing "Apply"
 * band are gone; so is the "Apply" button, because no application exists. What is left says what the visitor would DO and who
 * the programme is for, in words that carry no figure and no promise.
 */

/**
 * How it works (Figma 541:163): the visitor's steps. There is no "apply" step, because nothing can be applied to, and none says
 * what happens to money, how often or how much.
 */
const steps = [
  { n: '01', title: 'Share SelahCue', body: 'Recommend it anywhere your audience is.' },
  { n: '02', title: 'Refer a church', body: 'Introduce SelahCue to a church that could use it.' }
]

/** Made for people who talk to churches (Figma 542:124): audience descriptions, not product claims. */
const audiences = [
  { icon: 'video', tone: 'brand', title: 'Church tech creators', body: 'Bloggers, YouTubers and newsletter writers in the worship-tech space.' },
  { icon: 'package', tone: 'preview', title: 'AV & gear resellers', body: 'Sell projectors, mixers and stage gear? Tell your customers about SelahCue.' },
  { icon: 'users', tone: 'warn', title: 'Ministry networks', body: 'Denominations and multi-site networks recommending tools to member churches.' },
  { icon: 'briefcase', tone: 'brand', title: 'Consultants & integrators', body: 'You set up church production rigs — recommend SelahCue to the churches you work with.' }
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
      <h1 class="hero-title">Recommend SelahCue to churches.</h1>
      <p class="hero-sub">Help churches upgrade their live worship presentation. The affiliate program is not open yet.</p>

      <!-- The affiliate Apply and Sign in screens have no route (audit affiliates-06, a missing screen), so there is NO Apply
           button: the page used to send people to a contact form that sends nothing. Sign in goes nowhere either: the only
           affiliate pages are presentation shells full of sample figures that look like a live account, so the button is
           disabled and says so, as the Pro plan did on the pricing page. -->
      <div class="hero-actions">
        <div class="hero-ctas">
          <UiButton variant="outline" size="lg" disabled aria-describedby="signin-note">Affiliate sign in</UiButton>
        </div>
        <p id="signin-note" class="cta-note">Affiliate sign in: not available yet</p>
      </div>
    </section>

    <!-- How it works -->
    <section class="steps-section" aria-labelledby="steps-heading">
      <div class="container steps-inner">
        <div class="section-head">
          <h2 id="steps-heading" class="section-title">How it works</h2>
          <p class="section-sub">Two steps to get started.</p>
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

    <!-- Why it's easy to recommend: the two lines the repo backs -->
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

/* HOW IT WORKS (Figma 541:163): a full-bleed panel band, padding 64 / 64, 32px between the heading block and the
   steps; steps are 400 wide on the page fill, 24px apart, radius 18, padding 28 / 26 from the edge. */
.steps-section { background: var(--sc-surface-alt); }
.steps-inner { display: flex; flex-direction: column; gap: 32px; padding-top: 64px; padding-bottom: 64px; }
.section-head { display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; }
.section-title { font-size: 38px; font-weight: 700; line-height: 46px; color: var(--sc-text); }
.section-sub { font-size: 18px; line-height: 22px; color: var(--sc-text-secondary); }

.steps-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; align-items: start; max-width: 840px; margin-inline: auto; width: 100%; }

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

/* WHY IT'S EASY TO RECOMMEND (Figma 542:154): padding 56 top / 64 bottom. The frame puts a calculator card beside the
   checklist; the calculator is gone (it stated earnings nobody backs), so the heading and checklist stand alone, centred. */
.why-section {
  padding-top: 56px;
  padding-bottom: 64px;
}

.why-main { display: flex; flex-direction: column; gap: 18px; max-width: 720px; margin-inline: auto; }
.why-title { font-size: 30px; font-weight: 700; line-height: 36px; color: var(--sc-text); }
.check-list { display: flex; flex-direction: column; gap: 14px; }
.check-row { display: flex; align-items: flex-start; gap: 12px; font-size: 16.5px; line-height: 24px; color: var(--sc-text); }
.check-icon { flex-shrink: 0; width: 18px; height: 20px; margin-top: 2px; color: var(--sc-preview); }

@media (max-width: 1199.98px) {
  .audience-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .steps-grid { grid-template-columns: minmax(0, 1fr); }
}

@media (max-width: 767.98px) {
  .hero-section { padding-top: 56px; padding-bottom: 36px; gap: 18px; }
  .hero-sub { font-size: 16px; line-height: 26px; }
  .hero-actions { align-self: stretch; }
  .hero-ctas { flex-direction: column; align-self: stretch; }
  .hero-ctas > * { width: 100%; }
  .audience-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .steps-inner { padding-top: 44px; padding-bottom: 44px; }
  .section-title { font-size: 30px; line-height: 38px; }
  .audience-section { padding-top: 44px; padding-bottom: 40px; }
  .audience-title { font-size: 28px; line-height: 34px; }
  .why-section { padding-top: 36px; padding-bottom: 44px; }
  .why-title { font-size: 26px; line-height: 32px; }
}
</style>
