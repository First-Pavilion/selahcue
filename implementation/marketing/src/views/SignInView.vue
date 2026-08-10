<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'

const router = useRouter()

// Mode: 'signin' | 'signup' | 'forgot'
const mode = ref<'signin' | 'signup' | 'forgot'>('signin')

// Form Fields
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const orgName = ref('')
const agreeTerms = ref(false)

// Errors & States
const errors = ref<Record<string, string>>({})
const serverError = ref('')
const isSubmitting = ref(false)

const validate = () => {
  errors.value = {}
  serverError.value = ''

  if (!email.value) {
    errors.value.email = 'Email address is required'
  } else if (!/\S+@\S+\.\S+/.test(email.value)) {
    errors.value.email = 'Please enter a valid email address'
  }

  if (mode.value !== 'forgot') {
    if (!password.value) {
      errors.value.password = 'Password is required'
    } else if (password.value.length < 8) {
      errors.value.password = 'Password must be at least 8 characters'
    }
  }

  if (mode.value === 'signup') {
    if (!orgName.value) {
      errors.value.orgName = 'Organization name is required'
    }
    if (password.value !== confirmPassword.value) {
      errors.value.confirmPassword = 'Passwords do not match'
    }
  }

  return Object.keys(errors.value).length === 0
}

const handleSubmit = () => {
  if (!validate()) return

  isSubmitting.value = true
  serverError.value = ''

  setTimeout(() => {
    isSubmitting.value = false

    // Simulate invalid login test
    if (mode.value === 'signin' && email.value === 'error@test.com') {
      serverError.value = 'Invalid email or password. Please try again.'
      return
    }

    if (mode.value === 'forgot') {
      serverError.value = 'Reset link sent! Please check your email inbox.'
      return
    }

    // Success redirect
    router.push('/account')
  }, 1000)
}

const handleGoogleOAuth = () => {
  isSubmitting.value = true
  setTimeout(() => {
    isSubmitting.value = false
    router.push('/account')
  }, 800)
}

const switchMode = (newMode: 'signin' | 'signup' | 'forgot') => {
  mode.value = newMode
  errors.value = {}
  serverError.value = ''
}
</script>

<template>
  <div class="auth-page">
    <div class="container">
      <div class="auth-card">
        <!-- Brand Lockup -->
        <div class="brand-header">
          <img src="/selahcue-logo.png" alt="SelahCue logo" class="brand-logo" />
          <h1 class="auth-title">
            <template v-if="mode === 'signin'">Sign in to SelahCue</template>
            <template v-else-if="mode === 'signup'">Create your account</template>
            <template v-else>Reset your password</template>
          </h1>
          <p class="auth-subtitle">
            <template v-if="mode === 'signin'">Manage your church presentation plan &amp; devices</template>
            <template v-else-if="mode === 'signup'">Start managing your SelahCue license &amp; entitlements</template>
            <template v-else>Enter your email to receive a password reset link</template>
          </p>
        </div>

        <!-- Global Alert / Server Error -->
        <div v-if="serverError" class="alert-box" :class="{ 'is-success': mode === 'forgot' }" role="alert">
          <svg viewBox="0 0 20 20" fill="currentColor" class="alert-icon">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          <span>{{ serverError }}</span>
        </div>

        <!-- Form -->
        <form class="auth-form" @submit.prevent="handleSubmit" novalidate>
          <FormField
            v-if="mode === 'signup'"
            v-model="orgName"
            label="Church / Organization Name"
            placeholder="Grace Community Church"
            required
            :error="errors.orgName"
            :disabled="isSubmitting"
          />

          <FormField
            v-model="email"
            type="email"
            label="Email Address"
            placeholder="pastor@church.org"
            required
            :error="errors.email"
            :disabled="isSubmitting"
          />

          <FormField
            v-if="mode !== 'forgot'"
            v-model="password"
            type="password"
            label="Password"
            placeholder="••••••••"
            required
            :error="errors.password"
            :disabled="isSubmitting"
          />

          <FormField
            v-if="mode === 'signup'"
            v-model="confirmPassword"
            type="password"
            label="Confirm Password"
            placeholder="••••••••"
            required
            :error="errors.confirmPassword"
            :disabled="isSubmitting"
          />

          <div v-if="mode === 'signin'" class="forgot-link-wrapper">
            <button type="button" class="text-link" @click="switchMode('forgot')">
              Forgot password?
            </button>
          </div>

          <div v-if="mode === 'signup'" class="terms-checkbox">
            <label class="checkbox-label">
              <input v-model="agreeTerms" type="checkbox" required />
              <span>I agree to the <router-link to="/terms">Terms of Service</router-link> and <router-link to="/privacy">Privacy Policy</router-link></span>
            </label>
          </div>

          <UiButton 
            variant="gradient" 
            size="lg" 
            class="submit-btn" 
            :loading="isSubmitting"
            :disabled="mode === 'signup' && !agreeTerms"
          >
            <template v-if="mode === 'signin'">Sign In</template>
            <template v-else-if="mode === 'signup'">Create Account</template>
            <template v-else>Send Reset Link</template>
          </UiButton>
        </form>

        <div v-if="mode !== 'forgot'" class="divider">
          <span>or</span>
        </div>

        <UiButton 
          v-if="mode !== 'forgot'"
          variant="outline" 
          size="lg" 
          class="google-btn"
          :disabled="isSubmitting"
          @click="handleGoogleOAuth"
        >
          <svg class="google-icon" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"/>
            <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.27v3.15C3.25 21.3 7.31 24 12 24z"/>
            <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.27C.46 8.2.01 10.04.01 12c0 1.96.45 3.8 1.26 5.42l4.01-3.15z"/>
            <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.25 2.7 1.27 6.58l4.01 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/>
          </svg>
          Continue with Google
        </UiButton>

        <!-- Toggle Switcher -->
        <div class="auth-footer-link">
          <template v-if="mode === 'signin'">
            Don't have an account? 
            <button type="button" class="link-btn" @click="switchMode('signup')">Create an account</button>
          </template>
          <template v-else-if="mode === 'signup'">
            Already have an account? 
            <button type="button" class="link-btn" @click="switchMode('signin')">Sign in</button>
          </template>
          <template v-else>
            Remember your password? 
            <button type="button" class="link-btn" @click="switchMode('signin')">Back to sign in</button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  padding: 80px 0;
  background: var(--sc-base);
  min-height: calc(100vh - 160px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.container {
  width: 100%;
  max-width: 460px;
  padding: 0 20px;
}

.auth-card {
  background: var(--sc-surface);
  border: 1px solid var(--sc-border);
  border-radius: 20px;
  padding: 40px 36px;
  box-shadow: 0 20px 50px rgba(0,0,0,0.4);
}

.brand-header {
  text-align: center;
  margin-bottom: 28px;
}

.brand-logo {
  height: 48px;
  width: auto;
  margin-bottom: 16px;
}

.auth-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--sc-text);
  margin: 0 0 8px 0;
}

.auth-subtitle {
  font-size: 14px;
  color: var(--sc-text-secondary);
  margin: 0;
  line-height: 1.5;
}

/* Alert Box */
.alert-box {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--sc-live-soft);
  border: 1px solid var(--sc-live-border);
  color: var(--sc-live);
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 24px;
}

.alert-box.is-success {
  background: var(--sc-preview-soft);
  border-color: var(--sc-preview-border);
  color: var(--sc-preview);
}

.alert-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.forgot-link-wrapper {
  text-align: right;
  margin-top: -8px;
  margin-bottom: 20px;
}

.text-link {
  background: none;
  border: none;
  color: var(--sc-primary);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.text-link:hover {
  text-decoration: underline;
}

.terms-checkbox {
  margin-bottom: 20px;
  font-size: 13px;
  color: var(--sc-text-secondary);
}

.checkbox-label {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  cursor: pointer;
}

.checkbox-label input {
  margin-top: 2px;
}

.checkbox-label a {
  color: var(--sc-primary);
  text-decoration: none;
}

.checkbox-label a:hover {
  text-decoration: underline;
}

.submit-btn {
  width: 100%;
}

.divider {
  display: flex;
  align-items: center;
  margin: 24px 0;
}

.divider::before, .divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid var(--sc-border);
}

.divider span {
  padding: 0 12px;
  font-size: 12px;
  color: var(--sc-text-muted);
  text-transform: uppercase;
}

.google-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.google-icon {
  width: 18px;
  height: 18px;
}

.auth-footer-link {
  text-align: center;
  margin-top: 28px;
  font-size: 14px;
  color: var(--sc-text-secondary);
}

.link-btn {
  background: none;
  border: none;
  color: var(--sc-primary);
  font-weight: 600;
  cursor: pointer;
  padding: 0 0 0 4px;
  font-size: 14px;
}

.link-btn:hover {
  text-decoration: underline;
}
</style>
