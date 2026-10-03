<script setup lang="ts">
/**
 * Every state of the five shared components on one page, for `scripts/shared_components_headless.py`
 * to measure in a real browser. NOT shipped: it is built by `tests/gallery/vite.config.ts` into
 * `node_modules/.tmp`, and none of its copy appears on the site.
 *
 * Each block carries `data-case` so a check addresses it by name. The "defaults" blocks use
 * only props the audit branch already had, so the same page renders against that branch's
 * components and the two computed-style dumps can be diffed (the "default look unchanged"
 * proof for FormField and ConfirmDialog).
 */
import { ref } from 'vue'
import UiBadge from '@/components/UiBadge.vue'
import FormField from '@/components/FormField.vue'
import FaqAccordion from '@/components/FaqAccordion.vue'
import PricingCard from '@/components/PricingCard.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const faq = [
  { question: 'First question?', answer: 'The first answer is long enough to take two lines when it is shown in the boxed card, which is the case the row height depends on, so it keeps going for a while.' },
  { question: 'Second question?', answer: 'The second answer.' },
  { question: 'Third question?', answer: 'The third answer.' },
  { question: 'Fourth question?', answer: 'The fourth answer.' },
  { question: 'Fifth question?', answer: 'The fifth answer.' },
]

const plans = [
  { name: 'Free', price: 0, period: 'forever', description: 'Everything to run a service on one machine.', features: ['Live audience output + stage display', 'Bundled public-domain scripture + search', 'Service plans, timers & themes', 'One physical output'], cta: 'Download free', to: '/download', popular: false },
  { name: 'Pro', price: 19, period: 'month', description: 'For multi-output and streaming churches. Billed monthly, or save 20% yearly.', features: ['Everything in Free', 'NDI + multiple simultaneous outputs', 'Mobile control over your local network', 'Theme Designer & saved templates', 'On-device transcript & scripture detection', 'Always on the latest version'], cta: 'Get Pro', to: undefined, popular: true },
  { name: 'Church', price: 'Custom', period: 'month', description: 'For multi-site teams and larger ministries.', features: ['Everything in Pro', 'Multi-campus / site licensing', 'Guided onboarding & training', 'Priority support'], cta: 'Talk to us', to: '/contact', popular: false },
]

const email = ref('')
const password = ref('hunter22')
const newPassword = ref('abc')
const confirmPassword = ref('abcdefghi')
const lastEvent = ref('')

const showCentered = ref(false)
const showType = ref(false)
const showLeft = ref(false)
</script>

<template>
  <main class="gallery">
    <section data-case="badges" class="row">
      <UiBadge data-badge="featured" variant="featured">Join Our Team</UiBadge>
      <UiBadge data-badge="eyebrow" variant="eyebrow">Features</UiBadge>
      <UiBadge data-badge="accent" variant="accent">Most popular</UiBadge>
      <UiBadge data-badge="warn" variant="warn">Fixed</UiBadge>
      <UiBadge data-badge="preview-sm" variant="preview">Paid</UiBadge>
      <UiBadge data-badge="preview-md" variant="preview" size="md">Active</UiBadge>
      <UiBadge data-badge="live" variant="live">Live</UiBadge>
      <UiBadge data-badge="ready" variant="ready">Ready</UiBadge>
      <UiBadge data-badge="ndi" variant="ndi">NDI</UiBadge>
      <UiBadge data-badge="new" variant="new">New</UiBadge>
    </section>

    <!-- One line in a stylesheet, or on any ancestor, re-inks every brand badge at once. -->
    <section data-case="badges-ink" class="row" style="--ui-badge-ink: #a5b4fc">
      <UiBadge data-badge="featured" variant="featured">Join Our Team</UiBadge>
      <UiBadge data-badge="eyebrow" variant="eyebrow">Features</UiBadge>
      <UiBadge data-badge="accent" variant="accent">Most popular</UiBadge>
    </section>

    <section data-case="faq-plain" class="wrap-800">
      <FaqAccordion :items="faq" :default-open="0" />
    </section>

    <section data-case="faq-boxed" class="wrap-1040">
      <FaqAccordion :items="faq" :default-open="0" boxed />
    </section>

    <section data-case="pricing" class="pricing-grid">
      <PricingCard
        v-for="plan in plans"
        :key="plan.name"
        :name="plan.name"
        :price="plan.price"
        :period="plan.period"
        :description="plan.description"
        :features="plan.features"
        :cta="plan.cta"
        :to="plan.to"
        :popular="plan.popular"
      />
    </section>

    <!-- Props the audit branch already had: rendered against both, then diffed. -->
    <section data-case="defaults" class="card">
      <FormField id="d-plain" v-model="email" label="Email" placeholder="you@yourchurch.org" />
      <FormField id="d-required" model-value="Ada" label="Name" required />
      <FormField id="d-error" model-value="x" type="email" label="Email" error="Enter a valid email address." />
      <FormField id="d-hint" model-value="" label="Church" hint="Optional." />
      <FormField id="d-area" model-value="hello" type="textarea" label="Message" :max-length="2000" />
      <FormField id="d-password" v-model="password" type="password" label="Password" />
      <FormField id="d-password-error" model-value="" type="password" label="Password" error="Enter your password." />
    </section>

    <section data-case="signin-fields" class="card">
      <FormField id="s-email" v-model="email" label="Email" type="email" placeholder="you@yourchurch.org" />
      <FormField id="s-password" v-model="password" label="Password" type="password">
        <template #label-action>
          <a href="/forgot-password" aria-label="Forgot your password?" data-probe="forgot">Forgot?</a>
        </template>
      </FormField>
      <button class="primary" data-probe="submit" type="button">Sign in</button>
    </section>

    <section data-case="reset-fields" class="card">
      <FormField id="r-new" v-model="newPassword" label="New password" type="password" reveal-style="text" error-style="glyph" error="Password must be at least 10 characters." />
      <FormField id="r-confirm" v-model="confirmPassword" label="Confirm new password" type="password" reveal-style="text" error-style="glyph" error="Both passwords must match." />
      <button class="primary" data-probe="submit" type="button">Update password</button>
    </section>

    <section data-case="dialogs" class="row">
      <button id="open-centered" type="button" @click="showCentered = true">Open default dialog</button>
      <button id="open-type" type="button" @click="showType = true">Open type-to-confirm</button>
      <button id="open-left" type="button" @click="showLeft = true">Open devices confirm</button>
      <output id="last-event">{{ lastEvent }}</output>
    </section>

    <ConfirmDialog
      v-model:show="showCentered"
      title="Deactivate this device?"
      description="Are you sure you want to deactivate this device?"
      confirm-label="Deactivate"
      cancel-label="Keep active"
      variant="warning"
      @confirm="lastEvent = 'confirm'"
      @cancel="lastEvent = 'cancel'"
    />

    <ConfirmDialog
      v-model:show="showType"
      title="Cancel your plan?"
      description="Your features stay until the end of the period."
      :consequences="['One thing stops', 'Another thing stops']"
      confirm-label="Cancel subscription"
      cancel-label="Keep my plan"
      require-type="cancel"
      variant="danger"
      @confirm="lastEvent = 'confirm'"
      @cancel="lastEvent = 'cancel'"
    />

    <ConfirmDialog
      v-model:show="showLeft"
      layout="left"
      title="Deactivate Youth Hall PC?"
      description="This frees one of your 5 device slots straight away. Youth Hall PC keeps presenting offline until its cached entitlement expires, then it must be activated again."
      confirm-label="Deactivate"
      cancel-label="Keep active"
      variant="warning"
      hint="Esc keeps the device active."
      @confirm="lastEvent = 'confirm'"
      @cancel="lastEvent = 'cancel'"
    >
      <template #banner>
        <div class="fake-banner" data-probe="banner">
          <span class="fake-banner-glyph" aria-hidden="true">✓</span>
          <div>
            <p class="fake-banner-title">Nothing goes dark</p>
            <p class="fake-banner-body">Deactivating never blanks or stops a live service — it only removes the device from your plan.</p>
          </div>
        </div>
      </template>
    </ConfirmDialog>
  </main>
</template>

<style>
/* Measure at rest: main.css turns on smooth scrolling, and a click or focus mid-run would
   otherwise move the page between two measurements. */
html, html:focus-within { scroll-behavior: auto !important; }
.gallery { display: flex; flex-direction: column; gap: 48px; padding: 32px 96px 400px; }
.gallery .row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.gallery .wrap-800 { width: 800px; }
.gallery .wrap-1040 { width: 1040px; }
.gallery .card { width: 480px; padding: 28px; background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 16px; }
.gallery .pricing-grid { display: grid; grid-template-columns: repeat(3, 400px); gap: 24px; align-items: stretch; width: 1248px; }
.gallery button.primary { width: 100%; height: 44px; border: 0; border-radius: 11px; background: var(--sc-primary); color: #fff; font-weight: 600; font-family: inherit; }
.gallery [data-case='dialogs'] button { height: 44px; padding: 0 16px; font-family: inherit; }
.fake-banner { display: flex; gap: 12px; padding: 14px 16px; border-radius: 12px; background: var(--sc-preview-soft); }
.fake-banner-glyph { color: var(--sc-preview); font-weight: 700; font-size: 15px; }
.fake-banner-title { margin: 0 0 3px; font-size: 13.5px; font-weight: 600; color: var(--sc-text); }
.fake-banner-body { margin: 0; font-size: 13px; line-height: 19px; color: var(--sc-text-secondary); }
</style>
