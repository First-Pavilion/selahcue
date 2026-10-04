<script setup lang="ts">
import { ref } from 'vue'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'
import UiBadge from '@/components/UiBadge.vue'
import CategoryIcon from '@/components/article/CategoryIcon.vue'

const name = ref('')
const email = ref('')
const org = ref('')
const message = ref('')

const errors = ref<Record<string, string>>({})
const isSubmitting = ref(false)
const isSubmitted = ref(false)

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
    return /\S+@\S+\.\S+/.test(email.value) ? '' : 'Please enter a valid email address'
  },
  org: () => (org.value.length > NAME_LIMIT ? `Church / organization must be ${NAME_LIMIT} characters or fewer` : ''),
  message: () => (message.value ? '' : 'Message is required')
}

/** Validation on blur (MARKETING-PORTAL-GAP-FILL-HANDOFF 6b): show or clear that one field's error. */
const checkField = (field: string) => {
  const problem = rules[field]?.() ?? ''
  const next = { ...errors.value }
  if (problem) next[field] = problem
  else delete next[field]
  errors.value = next
}

const handleSubmit = () => {
  errors.value = {}
  for (const field of Object.keys(rules)) {
    const problem = rules[field]?.() ?? ''
    if (problem) errors.value[field] = problem
  }

  if (Object.keys(errors.value).length === 0) {
    isSubmitting.value = true
    setTimeout(() => {
      isSubmitting.value = false
      isSubmitted.value = true
    }, 800)
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
          <div v-if="isSubmitted" class="success-state">
            <div class="success-icon">✓</div>
            <h2>Message Received!</h2>
            <p>Thank you for reaching out, {{ name }}. A SelahCue specialist will respond within 24 hours.</p>
            <UiButton variant="outline" @click="isSubmitted = false; name=''; email=''; org=''; message=''">
              Send Another Message
            </UiButton>
          </div>

          <form v-else class="contact-form" aria-label="Contact us" @submit.prevent="handleSubmit">
            <h2 class="form-title">Send us a message</h2>

            <FormField
              v-model="name"
              label="Full name"
              placeholder="Jane Pastor"
              required
              :error="errors.name"
              :disabled="isSubmitting"
              @blur="checkField('name')"
            />

            <FormField
              v-model="email"
              type="email"
              label="Email"
              placeholder="jane@yourchurch.org"
              required
              :error="errors.email"
              :disabled="isSubmitting"
              @blur="checkField('email')"
            />

            <FormField
              v-model="org"
              label="Church / organization"
              placeholder="Grace Community Church"
              :error="errors.org"
              :disabled="isSubmitting"
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
              :disabled="isSubmitting"
              @blur="checkField('message')"
            />

            <UiButton
              variant="primary"
              size="lg"
              block
              :loading="isSubmitting"
            >
              Send message
            </UiButton>
          </form>
        </div>

        <!-- Right: the other ways to get in touch. -->
        <div class="method-cards">
          <div class="method-card">
            <CategoryIcon class="method-icon" name="mail" tone="brand" size="method" />
            <div class="method-body">
              <h2>Support & Sales Email</h2>
              <p>Email our dedicated support team directly.</p>
              <a href="mailto:support@selahcue.app" class="method-link">support@selahcue.app</a>
            </div>
          </div>

          <div class="method-card">
            <CategoryIcon class="method-icon" name="users" tone="warn" size="method" />
            <div class="method-body">
              <h2>Community & Discord</h2>
              <p>Join 1,200+ worship tech leaders on Discord for instant help.</p>
              <a href="#" class="method-link">Join Discord Community</a>
            </div>
          </div>

          <div class="method-card">
            <CategoryIcon class="method-icon" name="briefcase" tone="preview" size="method" />
            <div class="method-body">
              <h2>Enterprise & Multi-Campus</h2>
              <p>Talk to our church solutions architect for enterprise SLAs.</p>
              <a href="#" class="method-link">Schedule a Demo Call</a>
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

.success-state {
  text-align: center;
  padding: 40px 20px;
}

.success-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: var(--sc-preview-soft);
  color: var(--sc-preview);
  font-size: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}

.success-state h2 {
  font-size: 24px;
  color: var(--sc-text);
  margin-bottom: 12px;
}

.success-state p {
  font-size: 15px;
  color: var(--sc-text-secondary);
  margin-bottom: 28px;
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
  .success-state { padding: 24px 0; }
}
</style>
