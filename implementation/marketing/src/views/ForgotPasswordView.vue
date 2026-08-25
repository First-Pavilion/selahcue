<script setup lang="ts">
/**
 * `/forgot-password` — the entry point to the reset flow (86ak11r67).
 *
 * The other half — `/reset?token=…`, where the emailed link lands — already ships in
 * `ResetView.vue` (86ak10b1t). `requestPasswordReset` already ships in `account.ts`,
 * because that view offers it from its failure states. What was missing was the page a
 * person reaches when they simply cannot remember their password and have no link at
 * all: sign-in's "Forgot your password?" pointed nowhere.
 *
 * Design: `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §5, with two of its specs refused.
 *
 * §5c "Email not found → We couldn't find an account with this email. [Create one]"
 * IS NOT BUILT, and cannot be. `request_password_reset` returns `accepted: true` for
 * every well-formed address and pads the miss branch with a dummy PBKDF2 specifically so
 * the two take the same time. There is no signal to render. This is the same class of
 * defect as the §4c "email already exists" error that 86ak120kw calls out — the ticket
 * lists three corrections and this is a fourth of the same kind, found in §5c.
 *
 * §5b "It expires in 15 minutes" IS NOT USED. The real TTL is one hour
 * (`ACCOUNT_PASSWORD_RESET_TTL_SECONDS = 3600`). Fifteen minutes is not a harmless
 * rounding error in copy: it tells people their working link died 45 minutes early, so
 * they request another, which invalidates the one they were about to use. 86ak120kw's
 * third correction. The wording here is `ResetView.vue`'s, so the two pages agree
 * word for word.
 */
import { nextTick, onBeforeUnmount, ref } from 'vue'
import AuthShell from '@/components/auth/AuthShell.vue'
import AuthBanner from '@/components/auth/AuthBanner.vue'
import StatusDisc from '@/components/auth/StatusDisc.vue'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'
import { requestPasswordReset } from '@/lib/api/account.ts'
import { ApiError } from '@/lib/api/graphql.ts'
import { validateEmail } from '@/lib/auth/emailPolicy.ts'

type ForgotState = 'form' | 'submitting' | 'sent'

const state = ref<ForgotState>('form')
const heading = ref<HTMLElement | null>(null)

const email = ref('')
const emailError = ref('')
const requestError = ref('')
/** Frozen at submit, so later typing cannot rewrite the address the sent card names. */
const sentToEmail = ref('')

const controller = new AbortController()
let unmounted = false

const REQUEST_FAILED = "We couldn't send a link just now. Please try again in a moment."
/**
 * Says nothing about the address, deliberately.
 *
 * A limiter that spent its budget before looking the account up cannot be evidence the
 * account is real — and copy like "too many requests for this account" would say it is.
 * "Too many requests" describes what the caller did, not what the server knows.
 */
const REQUEST_RATE_LIMITED =
  'Too many requests for a new link. Wait a few minutes, then try again.'

async function focusHeading(): Promise<void> {
  await nextTick()
  heading.value?.focus()
}

async function submit(): Promise<void> {
  if (state.value === 'submitting') return
  requestError.value = ''
  emailError.value = validateEmail(email.value)
  if (emailError.value) return

  const address = email.value.trim()
  state.value = 'submitting'

  try {
    await requestPasswordReset(address, { signal: controller.signal })
    if (unmounted) return
    sentToEmail.value = address
    state.value = 'sent'
    void focusHeading()
  } catch (error) {
    if (unmounted || controller.signal.aborted) return
    // Never show the sent state for a failure. `requestPasswordReset` returns
    // `accepted: true` for every valid address — registered or not — so an error means
    // the request genuinely did not happen, and "check your inbox" would send someone to
    // wait for an email that is not coming.
    state.value = 'form'
    requestError.value =
      error instanceof ApiError && error.code === 'RATE_LIMITED'
        ? REQUEST_RATE_LIMITED
        : REQUEST_FAILED
  }
}

onBeforeUnmount(() => {
  unmounted = true
  controller.abort()
})
</script>

<template>
  <AuthShell>
    <!-- ============================================================ request a link -->
    <template v-if="state === 'form' || state === 'submitting'">
      <h1 ref="heading" tabindex="-1" class="au-title au-title-form">Reset your password</h1>
      <p class="au-body">
        Enter your email address and we'll send you a link to set a new one. Reset links last
        1 hour and work once.
      </p>

      <form
        novalidate
        aria-label="Reset your password"
        :aria-busy="state === 'submitting'"
        :class="{ 'is-submitting': state === 'submitting' }"
        @submit.prevent="submit"
      >
        <FormField
          v-model="email"
          type="email"
          label="Email"
          placeholder="you@yourchurch.org"
          autocomplete="email"
          required
          :error="emailError"
          :disabled="state === 'submitting'"
        />
        <div class="au-actions">
          <UiButton
            variant="primary"
            size="lg"
            class="au-btn au-btn-primary"
            :loading="state === 'submitting'"
          >
            <template v-if="state === 'submitting'">Sending…</template>
            <template v-else>Send reset link</template>
          </UiButton>
        </div>
      </form>

      <p v-if="requestError" class="au-note" role="alert">{{ requestError }}</p>

      <AuthBanner kind="info" title="This does not affect your devices">
        Requesting a link changes nothing yet. Your current password keeps working until you
        set a new one, and activated devices keep presenting offline throughout.
      </AuthBanner>
    </template>

    <!-- ================================================================ link sent -->
    <!-- CONDITIONAL BY CONSTRUCTION, and identical for a registered and an unregistered
         address because the API's answer is identical for both. "If … has a SelahCue
         account" is load-bearing and must not be "improved" into a direct claim: the
         direct version would be a lie half the time and an existence oracle all of it.
         Word for word the same as ResetView's sent state, so the two agree. -->
    <template v-else>
      <StatusDisc tone="brand" glyph="✉" />
      <h1 ref="heading" tabindex="-1" class="au-title">Check your inbox</h1>
      <p class="au-body">
        If {{ sentToEmail }} has a SelahCue account, a reset link is on its way. It expires in
        1 hour.
      </p>
      <div class="au-actions">
        <UiButton to="/signin" variant="secondary" size="lg" class="au-btn au-btn-secondary">
          Back to sign in
        </UiButton>
      </div>
      <p class="au-note">Didn't arrive? Check your spam folder, then request another link.</p>
      <AuthBanner kind="info" title="Only the newest link works">
        Sending a new link cancels the previous one. Use the most recent email you received.
      </AuthBanner>
    </template>

    <!-- ==================================================================== footer -->
    <template #footer>
      <template v-if="state === 'sent'">
        <span>Need a hand?</span><router-link to="/support">Contact support</router-link>
      </template>
      <template v-else>
        <span>Remembered it?</span><router-link to="/signin">Back to sign in</router-link>
      </template>
    </template>
  </AuthShell>
</template>

<style scoped>
.au-title:focus {
  outline: none;
}

.au-title:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 4px;
}

.is-submitting :deep(.form-field) {
  opacity: 0.5;
}
</style>
