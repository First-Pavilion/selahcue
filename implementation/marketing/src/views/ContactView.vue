<script setup lang="ts">
import { ref } from 'vue'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'
import UiBadge from '@/components/UiBadge.vue'

const name = ref('')
const email = ref('')
const org = ref('')
const message = ref('')

const errors = ref<Record<string, string>>({})
const isSubmitting = ref(false)
const isSubmitted = ref(false)

const handleSubmit = () => {
  errors.value = {}
  if (!name.value) errors.value.name = 'Name is required'
  if (!email.value) {
    errors.value.email = 'Email is required'
  } else if (!/\S+@\S+\.\S+/.test(email.value)) {
    errors.value.email = 'Please enter a valid email address'
  }
  if (!message.value) errors.value.message = 'Message is required'

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
    <div class="container">
      <div class="contact-layout">
        <!-- Left: Contact Info Cards -->
        <div class="contact-info">
          <UiBadge variant="featured">Get in Touch</UiBadge>
          <h1 class="info-title">We're here to help your church succeed</h1>
          <p class="info-sub">Have a question about SelahCue, pricing, licensing, or custom deployment? Reach out to our team.</p>

          <div class="method-cards">
            <div class="method-card">
              <div class="method-icon">💬</div>
              <div>
                <h4>Community & Discord</h4>
                <p>Join 1,200+ worship tech leaders on Discord for instant help.</p>
                <a href="#" class="method-link">Join Discord Community →</a>
              </div>
            </div>

            <div class="method-card">
              <div class="method-icon">📧</div>
              <div>
                <h4>Support & Sales Email</h4>
                <p>Email our dedicated support team directly.</p>
                <a href="mailto:support@selahcue.app" class="method-link">support@selahcue.app →</a>
              </div>
            </div>

            <div class="method-card">
              <div class="method-icon">🏢</div>
              <div>
                <h4>Enterprise & Multi-Campus</h4>
                <p>Talk to our church solutions architect for enterprise SLAs.</p>
                <a href="#" class="method-link">Schedule a Demo Call →</a>
              </div>
            </div>
          </div>
        </div>

        <!-- Right: Contact Form -->
        <div class="contact-form-card">
          <div v-if="isSubmitted" class="success-state">
            <div class="success-icon">✓</div>
            <h2>Message Received!</h2>
            <p>Thank you for reaching out, {{ name }}. A SelahCue specialist will respond within 24 hours.</p>
            <UiButton variant="outline" @click="isSubmitted = false; name=''; email=''; org=''; message=''">
              Send Another Message
            </UiButton>
          </div>

          <form v-else @submit.prevent="handleSubmit">
            <h2 class="form-title">Send us a message</h2>
            
            <FormField
              v-model="name"
              label="Your Name"
              placeholder="Sarah Jenkins"
              required
              :error="errors.name"
              :disabled="isSubmitting"
            />

            <FormField
              v-model="email"
              type="email"
              label="Email Address"
              placeholder="sarah@gracechurch.org"
              required
              :error="errors.email"
              :disabled="isSubmitting"
            />

            <FormField
              v-model="org"
              label="Church / Organization (Optional)"
              placeholder="Grace Community Church"
              :disabled="isSubmitting"
            />

            <FormField
              v-model="message"
              type="textarea"
              label="Your Message"
              placeholder="Tell us how we can help..."
              required
              :maxLength="2000"
              :error="errors.message"
              :disabled="isSubmitting"
            />

            <UiButton 
              variant="gradient" 
              size="lg" 
              class="full-btn"
              :loading="isSubmitting"
            >
              Send Message
            </UiButton>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.contact-page {
  padding: 80px 0;
  background: var(--sc-base);
  min-height: calc(100vh - 160px);
}

.container {
  max-width: 1140px;
  margin: 0 auto;
  padding: 0 24px;
}

.contact-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 60px;
  align-items: start;
}

.info-title {
  font-size: 38px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 16px 0;
  line-height: 1.2;
}

.info-sub {
  font-size: 16px;
  color: var(--sc-text-secondary);
  line-height: 1.6;
  margin-bottom: 40px;
}

.method-cards {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.method-card {
  display: flex;
  gap: 16px;
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 14px;
  padding: 20px;
}

.method-icon {
  font-size: 24px;
}

.method-card h4 {
  font-size: 16px;
  font-weight: 600;
  color: var(--sc-text);
  margin: 0 0 4px 0;
}

.method-card p {
  font-size: 13px;
  color: var(--sc-text-secondary);
  margin: 0 0 8px 0;
}

.method-link {
  font-size: 13px;
  font-weight: 600;
  color: var(--sc-primary);
  text-decoration: none;
}

.method-link:hover {
  text-decoration: underline;
}

.contact-form-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 40px;
  box-shadow: 0 20px 50px rgba(0,0,0,0.4);
}

.form-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0 0 24px 0;
}

.full-btn {
  width: 100%;
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

@media (max-width: 900px) {
  .contact-layout {
    grid-template-columns: 1fr;
  }
}
</style>
