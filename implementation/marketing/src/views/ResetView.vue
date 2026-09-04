<script setup lang="ts">
/**
 * `/reset?token=…` — where the password-reset email's button lands.
 *
 * Design: `docs/design/AUTH-LANDING-PAGES-HANDOFF.md` §5 + §8.2.
 * Figma: R1 `747:143` · R2 `747:173` · R3 `749:124` · R4 `749:150` · R6 `749:198` · R7 `749:217`.
 *
 * THE TRAP THIS VIEW EXISTS TO AVOID — AND WHAT CHANGED UNDER IT
 * -------------------------------------------------------------
 * `confirm_password_reset` USED TO call `_validate_password` before it looked up the
 * token, with BOTH raising the same `VALIDATION_FAILED`. So a page that submitted an
 * unvalidated password produced:
 *
 *   user types a 6-character password
 *     → server rejects the PASSWORD
 *     → client sees `VALIDATION_FAILED`, indistinguishable from a dead token
 *     → page shows R4, "this reset link didn't work"
 *     → user's link was fine. They request a new one, type the same short password,
 *       hit the same wall, and conclude the product is broken.
 *
 * FR-551 (PR #16) reversed that order at the source. The token is validated first
 * (`apps/accounts/services.py:1185`–`1206`: fingerprint, purpose, consumed, expiry — all
 * one collapsed `VALIDATION_FAILED`), and the password is checked afterwards at
 * `services.py:1245`, raising the DISTINCT `PASSWORD_INVALID` from behind a token already
 * found live. This file's comment claimed the old ordering as current fact until round 3;
 * it was false from the day #16 landed, which is why the claim now carries the line
 * numbers it was checked against.
 *
 * Two consequences for this view, and both are implemented below:
 *
 * 1. `PASSWORD_INVALID` gets its OWN state. It is not R4 (the link demonstrably works —
 *    the server had to find it live to reach the password check) and it is not R7 (nothing
 *    went wrong on our side; the request was answered correctly). Letting it fall into R7
 *    told the user to try again later about a failure that is permanent until they change
 *    what they typed.
 * 2. That state may not name a rule. `PASSWORD_INVALID` carries no policy detail on
 *    purpose (`graphql/errors.py:28`), and this client has already enforced 10–200
 *    characters before sending — so whatever the server refused, it is NOT something this
 *    page can identify. "That password wasn't accepted" is the whole of what is known.
 *
 * `validateNewPassword` still gates every submit, and no request outside 10–200
 * characters (or an all-whitespace one, which the server also rejects) is ever sent. It is
 * no longer the only thing standing between a short password and a false "your link is
 * dead" — the server's ordering is — but it is what keeps a rejectable password from
 * spending a round trip and a rate-limit slot, and it is the only place that can tell the
 * user which rule they broke.
 *
 * WHY R5 IS NOT BUILT
 * -------------------
 * Same reason V4 is not: the API collapses unknown / wrong-purpose / consumed / expired
 * into one code, on purpose, so "this link has expired" is a claim the client cannot
 * support. R4 names the 1-hour single-use rule without asserting which cause applied,
 * and always offers a fresh link. 86ak120fz owns whether that ever changes.
 *
 * The reset TTL in this copy is ONE HOUR (`ACCOUNT_PASSWORD_RESET_TTL_SECONDS = 3600`).
 * `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §5b says 15 minutes; it is wrong, and §11.3 of
 * the auth handoff records the correction.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import AuthShell from '@/components/auth/AuthShell.vue'
import AuthBanner from '@/components/auth/AuthBanner.vue'
import StatusDisc from '@/components/auth/StatusDisc.vue'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'
import { confirmPasswordReset, requestPasswordReset } from '@/lib/api/account.ts'
import { ApiError } from '@/lib/api/graphql.ts'
import { validateEmail } from '@/lib/auth/emailPolicy.ts'
import {
  MIN_PASSWORD_LENGTH,
  validateNewPassword,
  type NewPasswordErrors,
} from '@/lib/auth/passwordPolicy.ts'
import { takeLandingToken } from '@/lib/auth/useLandingToken.ts'
import {
  CHECK_SPAM_NOTE,
  NEWEST_LINK_BODY,
  NEWEST_LINK_TITLE,
  RESEND_FAILED
} from '@/lib/auth/messages.ts'

type ResetState =
  /** R1 / R2 — the form, with or without client-side errors. */
  | 'form'
  /** R3 — the mutation is in flight. */
  | 'submitting'
  /** R4 — merged failure: expired OR consumed OR unknown OR mistyped. */
  | 'invalid'
  /** R6 — the password is changed. */
  | 'updated'
  /** R7 — our side failed; the link is untouched. */
  | 'serverError'
  /**
   * `PASSWORD_INVALID` — the server refused the PASSWORD, from behind a token it had
   * already looked up and found live (`services.py:1245`). No Figma frame: the code did
   * not exist when the R-series was drawn, and DEC-017 sanctioned it afterwards.
   */
  | 'passwordRejected'
  /** Extrapolated from V6 — opened without `?token=`. Not an error. */
  | 'missing'
  /** Extrapolated from V5 — a fresh reset link has been requested. */
  | 'sent'

const state = ref<ResetState>('form')
const heading = ref<HTMLElement | null>(null)

/**
 * The states that render the form, and the states that render a danger banner above it.
 * ONE definition each, consumed by the template rather than restated in it: the `v-if`
 * that mounts the form and the `v-if` that suppresses the info banner are two readings of
 * the same fact, and adding `passwordRejected` to one and not the other is exactly the
 * kind of half-edit this file has already shipped once.
 */
const FORM_STATES: readonly ResetState[] = ['form', 'submitting', 'serverError', 'passwordRejected']
const BANNERED_STATES: readonly ResetState[] = ['serverError', 'passwordRejected']

const showsForm = computed(() => FORM_STATES.includes(state.value))
const showsErrorBanner = computed(() => BANNERED_STATES.includes(state.value))

// Held outside reactive state — a single-use credential that grants account takeover.
// `takeLandingToken` has already removed it from the address bar.
let landingToken = ''

const controller = new AbortController()
let unmounted = false

const password = ref('')
const confirmPassword = ref('')
const errors = ref<NewPasswordErrors>({})

// Fresh-link sub-form, shared by R4 / missing.
const email = ref('')
const emailError = ref('')
const requestPending = ref(false)
const requestFailed = ref(false)
const sentToEmail = ref('')

const passwordHint = computed(() => `At least ${MIN_PASSWORD_LENGTH} characters.`)

async function focusHeading(): Promise<void> {
  await nextTick()
  heading.value?.focus()
}

async function submitNewPassword(): Promise<void> {
  // THE GUARD. Everything above in this file explains why it must run before the call
  // and why the call must not happen when it produces anything.
  errors.value = validateNewPassword(password.value, confirmPassword.value)
  if (Object.keys(errors.value).length > 0) {
    // R2. Stay on the form; the field-level messages carry the correction.
    state.value = 'form'
    return
  }

  state.value = 'submitting'

  try {
    const reset = await confirmPasswordReset(landingToken, password.value, {
      signal: controller.signal,
    })
    if (unmounted) return
    state.value = reset ? 'updated' : 'invalid'
    if (reset) {
      // The password has served its purpose; drop both copies rather than leaving
      // plaintext sitting in component state for as long as the tab is open.
      password.value = ''
      confirmPassword.value = ''
    }
  } catch (error) {
    if (unmounted || controller.signal.aborted) return
    if (error instanceof ApiError && error.code === 'PASSWORD_INVALID') {
      // The server got as far as the password, which means it had already found the token
      // live — and the raise happens inside the `transaction.atomic()` that wraps
      // `confirm_password_reset`, so `consumed_at` rolls back and the link is still
      // usable. Both halves of the copy below are therefore true, and neither is guessed.
      state.value = 'passwordRejected'
    } else if (error instanceof ApiError && error.code === 'VALIDATION_FAILED') {
      // Since FR-551 this is a TOKEN failure and nothing else: the password check runs
      // after the token lookup and raises `PASSWORD_INVALID`, handled above.
      state.value = 'invalid'
    } else {
      // Transport failure, rate limiting, INTERNAL — none of which say anything about
      // the link. R7's promise that "this link still works until it expires" is accurate:
      // `confirm_password_reset` is wrapped in `transaction.atomic()`, so a failure rolls
      // the token's `consumed_at` back.
      state.value = 'serverError'
    }
  }
  void focusHeading()
}

async function submitFreshLink(): Promise<void> {
  emailError.value = validateEmail(email.value)
  if (emailError.value) return

  requestPending.value = true
  requestFailed.value = false
  const address = email.value.trim()

  try {
    // Unlike /verify's resend, this mutation EXISTS and is shipped, so this path is
    // fully wired today.
    await requestPasswordReset(address, { signal: controller.signal })
    if (unmounted) return
    sentToEmail.value = address
    state.value = 'sent'
    void focusHeading()
  } catch {
    if (unmounted) return
    // `requestPasswordReset` returns `accepted: true` for every address, so an error
    // means the request genuinely did not happen. Never show the sent state for it.
    requestFailed.value = true
  } finally {
    if (!unmounted) requestPending.value = false
  }
}

onMounted(() => {
  landingToken = takeLandingToken()
  // Nothing is validated on arrival: the reset token is opaque and there is no query
  // that would tell us whether it is live, so the form is shown optimistically and R4
  // is reached only after a submit. That also means this page can never display whose
  // account it is for — §5.1 is explicit that no "resetting the password for …" line
  // may be added, because nothing here knows the address.
  state.value = landingToken ? 'form' : 'missing'
})

onBeforeUnmount(() => {
  unmounted = true
  controller.abort()
})
</script>

<template>
  <AuthShell>
    <!-- ================ R1 / R2 / R3 / R7 + PASSWORD_INVALID — the form and its states -->
    <template v-if="showsForm">
      <!-- R7: a danger banner ABOVE the title, per §5.7. -->
      <AuthBanner
        v-if="state === 'serverError'"
        kind="danger"
        title="We couldn't update your password"
        alert
      >
        Something went wrong on our side. Your password has not been changed and this link
        still works until it expires.
      </AuthBanner>

      <!-- PASSWORD_INVALID. Same shape as R7, opposite meaning: the request was answered
           correctly and the answer was no. It names the password and does NOT name a rule,
           because the server sends none and this page has already checked the rules it
           knows — see the header. -->
      <AuthBanner
        v-else-if="state === 'passwordRejected'"
        kind="danger"
        title="That password wasn't accepted"
        alert
      >
        Your password has not been changed and this reset link still works. Choose a
        different password and try again.
      </AuthBanner>

      <h1 ref="heading" tabindex="-1" class="au-title au-title-form">Choose a new password</h1>
      <p class="au-body">
        Pick a password you don't use anywhere else. You'll be signed in again with the
        new one.
      </p>

      <form
        novalidate
        :aria-busy="state === 'submitting'"
        :class="{ 'is-submitting': state === 'submitting' }"
        @submit.prevent="submitNewPassword"
      >
        <FormField
          v-model="password"
          type="password"
          label="New password"
          autocomplete="new-password"
          :hint="passwordHint"
          :error="errors.password"
          :disabled="state === 'submitting'"
        />
        <FormField
          v-model="confirmPassword"
          type="password"
          label="Confirm new password"
          autocomplete="new-password"
          :error="errors.confirmPassword"
          :disabled="state === 'submitting'"
        />
        <div class="au-actions">
          <UiButton
            variant="primary"
            size="lg"
            class="au-btn au-btn-primary"
            :loading="state === 'submitting'"
          >
            <template v-if="state === 'submitting'">Updating password…</template>
            <template v-else-if="state === 'serverError'">Try again</template>
            <template v-else>Update password</template>
          </UiButton>
        </div>
      </form>

      <!-- R3 -->
      <p v-if="state === 'submitting'" class="au-note" role="status" aria-live="polite">
        Don't close this tab.
      </p>

      <!-- Factual, and the reason it is worth saying: the mutation revokes every ACTIVE
           CustomerSession but deliberately NOT any DeviceToken, so an activated machine
           in the building keeps presenting. That is the never-blank guarantee, stated
           where it matters most. -->
      <AuthBanner v-if="!showsErrorBanner" kind="info" title="This signs you out everywhere">
        Updating your password ends every active SelahCue session on this account. Devices
        you have already activated keep presenting offline — live output is never
        interrupted.
      </AuthBanner>
    </template>

    <!-- ===================================== R4 merged failure (the state that ships) -->
    <template v-else-if="state === 'invalid'">
      <StatusDisc tone="danger" glyph="✕" />
      <h1 ref="heading" tabindex="-1" class="au-title">This reset link didn't work</h1>
      <p class="au-body">
        The link may have expired, already been used, or been copied incompletely. Reset
        links last 1 hour and work once. Enter your email address to start again.
      </p>
      <form novalidate @submit.prevent="submitFreshLink">
        <FormField
          v-model="email"
          type="email"
          label="Email"
          placeholder="you@yourchurch.org"
          autocomplete="email"
          :error="emailError"
          :disabled="requestPending"
        />
        <div class="au-actions">
          <UiButton
            variant="primary"
            size="lg"
            class="au-btn au-btn-primary"
            :loading="requestPending"
          >
            Send a new reset link
          </UiButton>
        </div>
      </form>
      <p v-if="requestFailed" class="au-note" role="alert">
        We couldn't send a new link just now. Please try again in a moment.
      </p>
      <AuthBanner kind="info" title="Your password has not changed">
        A link that fails changes nothing on your account. Your old password still works
        until you set a new one.
      </AuthBanner>
    </template>

    <!-- =============================================================== R6 updated -->
    <template v-else-if="state === 'updated'">
      <StatusDisc tone="success" glyph="✓" />
      <h1 ref="heading" tabindex="-1" class="au-title">Password updated</h1>
      <p class="au-body">
        Sign in with your new password. For your security, every other session on this
        account has been signed out.
      </p>
      <div class="au-actions">
        <UiButton to="/signin" variant="primary" size="lg" class="au-btn au-btn-primary">
          Continue to sign in
        </UiButton>
      </div>
      <AuthBanner kind="success" title="Your devices keep presenting">
        Activated SelahCue devices are not signed out and keep working offline. Changing
        your password never interrupts live output.
      </AuthBanner>
    </template>

    <!-- ================================================ no token (V6, extrapolated) -->
    <!-- The R-series has no designed no-token frame, but the condition is identical to
         /verify's V6 — a bookmark, a stripped query, a hand-typed URL — and V6's
         reasoning transfers exactly: this is not an error, so it is not red. -->
    <template v-else-if="state === 'missing'">
      <StatusDisc tone="neutral" glyph="!" />
      <h1 ref="heading" tabindex="-1" class="au-title">This page needs a reset link</h1>
      <p class="au-body">
        Open the link in the email we sent you. If you no longer have it, enter your
        address and we'll send a new one. Reset links last 1 hour and work once.
      </p>
      <form novalidate @submit.prevent="submitFreshLink">
        <FormField
          v-model="email"
          type="email"
          label="Email"
          placeholder="you@yourchurch.org"
          autocomplete="email"
          :error="emailError"
          :disabled="requestPending"
        />
        <div class="au-actions">
          <UiButton
            variant="primary"
            size="lg"
            class="au-btn au-btn-primary"
            :loading="requestPending"
          >
            Send a reset link
          </UiButton>
        </div>
      </form>
      <p v-if="requestFailed" class="au-note" role="alert">{{ RESEND_FAILED }}</p>
    </template>

    <!-- ============================================= fresh link sent (V5 analogue) -->
    <template v-else>
      <StatusDisc tone="brand" glyph="✉" />
      <h1 ref="heading" tabindex="-1" class="au-title">Check your inbox</h1>
      <!-- Conditional by construction, exactly as V5. `request_password_reset` returns
           accepted:true for an address with no account, so any direct claim would be an
           existence oracle. The TTL here is 1 hour, not verification's 24. -->
      <p class="au-body">
        If {{ sentToEmail }} has a SelahCue account, a new reset link is on its way. It
        expires in 1 hour.
      </p>
      <div class="au-actions">
        <UiButton to="/signin" variant="secondary" size="lg" class="au-btn au-btn-secondary">
          Back to Sign in
        </UiButton>
      </div>
      <p class="au-note">
        {{ CHECK_SPAM_NOTE }}
      </p>
      <AuthBanner kind="info" :title="NEWEST_LINK_TITLE">
        {{ NEWEST_LINK_BODY }}
      </AuthBanner>
    </template>

    <!-- ==================================================================== footer -->
    <template #footer>
      <template v-if="state === 'updated'">
        <span>Didn't do this?</span><router-link to="/support">Contact support</router-link>
      </template>
      <template v-else-if="state === 'serverError'">
        <span>Still stuck?</span><router-link to="/signin">Back to Sign in</router-link>
      </template>
      <template v-else-if="state === 'sent'">
        <span>Need a hand?</span><router-link to="/support">Contact support</router-link>
      </template>
      <template v-else>
        <span>Remembered it?</span><router-link to="/signin">Back to Sign in</router-link>
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

/* R3: fields at 50% opacity while the mutation is in flight (§5.3). They are also
   genuinely disabled — dimming alone would leave them editable. */
.is-submitting :deep(.form-field) {
  opacity: 0.5;
}
</style>
