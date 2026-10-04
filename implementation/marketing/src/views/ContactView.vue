<script setup lang="ts">
import { ref } from 'vue'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'
import UiBadge from '@/components/UiBadge.vue'
import CategoryIcon from '@/components/article/CategoryIcon.vue'
import { looksLikeEmail } from '@/lib/contactForm.ts'

const name = ref('')
const email = ref('')
const org = ref('')
const message = ref('')

const errors = ref<Record<string, string>>({})

/**
 * One rule per field, so a field can be checked when it loses focus and again on submit. The 100
 * character limits on name and church (MARKETING-PORTAL-GAP-FILL-HANDOFF 6a) are rules here, not a
 * `maxlength`: FormField puts `maxlength` on a textarea only, so an input would ignore it.
 */
const NAME_LIMIT = 100

const rules: Record<string, () => string> = {
  name: () => {
    if (!name.value) return 'Name is required'
    return name.value.length > NAME_LIMIT ? `Name must be ${NAME_LIMIT} characters or fewer` : ''
  },
  email: () => {
    if (!email.value) return 'Email is required'
    return looksLikeEmail(email.value) ? '' : 'Please enter a valid email address'
  },
  org: () => (org.value.length > NAME_LIMIT ? `Church / organization must be ${NAME_LIMIT} characters or fewer` : ''),
  message: () => (message.value ? '' : 'Message is required')
}

/**
 * Validation on blur (MARKETING-PORTAL-GAP-FILL-HANDOFF 6b): show or clear that one field's error.
 *
 * A blur must never move the Send button out from under the pointer (review round 2, Quinn Q1): pressing the
 * mouse on a button blurs the focused field FIRST, and an error line that appears or goes away at that moment
 * moves the button before the mouse is released, so the browser sees no click and the first press is lost.
 * Two rules keep the layout still at that moment. An error is taken away when the value CHANGES (`clearError`,
 * on every keystroke), never on blur; and while the pointer is down on Send the blur does not check at all
 * (`pressingSend`): the click that follows validates every field anyway.
 */
const pressingSend = ref(false)

const checkField = (field: string) => {
  if (pressingSend.value) return
  const problem = rules[field]?.() ?? ''
  const next = { ...errors.value }
  if (problem) next[field] = problem
  else delete next[field]
  errors.value = next
}

/** Typing in a field takes that field's error away at once. */
const clearError = (field: string) => {
  if (!errors.value[field]) return
  const next = { ...errors.value }
  delete next[field]
  errors.value = next
}

/** The pointer went down inside the form: remember whether it is on the Send button. A focus moving into any field ends it. */
const notePointer = (event: PointerEvent) => {
  pressingSend.value = event.target instanceof Element && event.target.closest('button') !== null
}

/**
 * NOTHING IS SENT. There is no contact endpoint yet (the contact-send ticket is separate, ClickUp 17tnw2b0x3h), so the Send
 * button is disabled and the page says so. This is only the validation seam that ticket extends: it checks every field and
 * never reports a send, a receipt or a reply. It also stops a stray submit from navigating the page.
 */
const handleSubmit = () => {
  pressingSend.value = false
  errors.value = {}
  for (const field of Object.keys(rules)) {
    const problem = rules[field]?.() ?? ''
    if (problem) errors.value[field] = problem
  }
}
</script>

<template>
  <div class="contact-page">
    <section class="page-hero container">
      <UiBadge variant="featured">CONTACT</UiBadge>
      <h1 class="hero-title">Let's talk</h1>
      <p class="hero-sub">Questions about SelahCue, help with getting set up, or partnering with us. Here is how to get in touch.</p>
    </section>

    <div class="container contact-split">
      <div class="contact-layout">
        <!-- Left: the form. First in the DOM so Tab order is the form, then the cards (Figma column order). -->
        <div class="contact-form-card">
          <form
            class="contact-form"
            aria-label="Contact us"
            @submit.prevent="handleSubmit"
            @pointerdown="notePointer"
            @focusin="pressingSend = false"
          >
            <h2 class="form-title">Send us a message</h2>
            <!-- Said BEFORE the visitor types, and tied to the disabled button below. Nothing here sends, replies or confirms. -->
            <p id="send-note" class="form-note">The contact form is not available yet. Please email us instead.</p>

            <FormField
              v-model="name"
              label="Full name"
              placeholder="Jane Pastor"
              required
              :error="errors.name"
              @update:model-value="clearError('name')"
              @blur="checkField('name')"
            />

            <FormField
              v-model="email"
              type="email"
              label="Email"
              placeholder="jane@yourchurch.org"
              required
              :error="errors.email"
              @update:model-value="clearError('email')"
              @blur="checkField('email')"
            />

            <FormField
              v-model="org"
              label="Church / organization"
              placeholder="Grace Community Church"
              :error="errors.org"
              @update:model-value="clearError('org')"
              @blur="checkField('org')"
            />

            <FormField
              v-model="message"
              type="textarea"
              label="How can we help?"
              placeholder="Tell us a little about what you need…"
              required
              :maxLength="2000"
              :error="errors.message"
              @update:model-value="clearError('message')"
              @blur="checkField('message')"
            />

            <UiButton
              variant="primary"
              size="lg"
              block
              disabled
              aria-describedby="send-note"
            >
              Send message
            </UiButton>
          </form>
        </div>

        <!-- Right: the one way to get in touch that works today. -->
        <div class="method-cards">
          <div class="method-card">
            <CategoryIcon class="method-icon" name="mail" tone="brand" size="method" />
            <div class="method-body">
              <h2>Email us</h2>
              <p>Write to us at this address.</p>
              <a href="mailto:support@selahcueapp.com" class="method-link">support@selahcueapp.com</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.contact-page {
  background: var(--sc-base);
  padding-bottom: 64px;
}

/* Figma's column order puts the form before the cards, so Tab from "Send message" jumps UP the page to the first
   card link. `anchors.css` gives focus a scroll margin on the article pages only, and without one a short window
   leaves that link under the sticky navbar (WCAG 2.2 SC 2.4.11, focus not obscured): its top was 69px at 700 high
   and 33px at 800, the navbar ends at 79 (review round 2, Quinn Q2). The same shared offset the article pages use,
   on every focusable control of the page, FormField's inner input and textarea and UiButton's button included. */
.contact-page :deep(:is(a[href], button, input, select, textarea)) {
  scroll-margin-top: var(--sc-anchor-offset);
}

/* HERO (Figma 497:139): padding 96 top / 32 bottom, 20px between the pill, the headline and the
   subline, all centred. The headline takes the shared page-hero token and is set to the frame's 50/56
   from the desktop breakpoint up; below it the token's own steps (44, 36) apply. */
.page-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding-top: 96px;
  padding-bottom: 32px;
  text-align: center;
}

.hero-title {
  font: var(--font-h1-page);
  color: var(--sc-text);
}

@media (min-width: 1200px) {
  .hero-title {
    font-size: 50px;
    line-height: 56px;
  }
}

.hero-sub {
  max-width: 680px;
  font-size: 19px;
  line-height: 30px;
  color: var(--sc-text-secondary);
}

/* THE SPLIT (Figma 497:144): two 604px columns at 1440 (1248 content, 40px gap), form left, cards
   right, both starting at the top. */
.contact-split {
  padding-top: 40px;
}

.contact-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 40px;
  align-items: start;
}

.method-cards {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.method-card {
  display: flex;
  gap: 16px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 16px;
  /* Figma pads 20 / 22 from the frame's edge and draws the stroke inside it, so the CSS padding is
     one pixel less each side to put the icon and the text where the frame does. */
  padding: 19px 21px;
}

.method-body {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  min-width: 0;
}

.method-card h2 {
  font-size: 16.5px;
  font-weight: 600;
  line-height: 20px;
  color: var(--sc-text);
}

.method-card p {
  font-size: 13.5px;
  line-height: 16px;
  color: var(--sc-text-secondary);
}

.method-link {
  font-size: 14px;
  font-weight: 500;
  line-height: 17px;
  color: var(--sc-primary);
  text-decoration: none;
}

.method-link:hover {
  text-decoration: underline;
}

/* THE FORM CARD (Figma 497:145): 604 wide, padding 32 from the edge (31 plus the 1px border), 18px
   between the title, the fields and the button, and no shadow. */
.contact-form-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 31px;
}

.contact-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 24px;
  color: var(--sc-text);
}

/* FormField is shared and owns its look (label and well styling are a pending decision between two
   handoffs, contact-19). Only the GEOMETRY the frame fixes is set here: a field row is 16 + 7 + 44 =
   67px, the input 44 high, the textarea 120, no spare line under a field that has nothing to say.
   The placeholder and the counter take the secondary ink (the frame's own, 7.4:1 on the well);
   the muted ink was the wrong role for them (contact-13). */
.contact-form :deep(.form-field) {
  margin-bottom: 0;
  gap: 7px;
}

.contact-form :deep(.field-label) {
  line-height: 16px;
}

.contact-form :deep(.field-input) {
  padding: 12px 13px;
  line-height: 18px;
}

/* An input is 44 high whatever the engine's own minimum is: WebKit draws a 15px field as 45 with a line box alone. */
.contact-form :deep(input.field-input) {
  height: 44px;
}

.contact-form :deep(.field-textarea) {
  min-height: 120px;
  padding: 13px;
}

.contact-form :deep(.field-input::placeholder) {
  color: var(--sc-text-secondary);
}

.contact-form :deep(.field-meta:empty) {
  display: none;
}

.contact-form :deep(.char-count) {
  color: var(--sc-text-secondary);
}

.contact-form :deep(.char-count.at-limit) {
  color: var(--sc-live);
}

.form-note {
  font-size: 14px;
  line-height: 20px;
  color: var(--sc-text-secondary);
}

@media (max-width: 1023.98px) {
  .contact-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 767.98px) {
  .contact-page { padding-bottom: var(--section-pad-sm); }
  .page-hero { padding-top: 56px; padding-bottom: 24px; gap: 16px; }
  .hero-sub { font-size: 17px; line-height: 26px; }
  .contact-split { padding-top: 24px; }
  .method-card { padding: 16px; }
  .method-link { display: inline-flex; align-items: center; min-height: 44px; }
  .contact-form-card { padding: 24px 20px; border-radius: 16px; }
}
</style>
