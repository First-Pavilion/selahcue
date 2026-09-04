<script setup lang="ts">
/**
 * `/signup` — self-serve account creation against `registerCustomerUser` (86ak11r67).
 *
 * Design: `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §4, corrected by
 * `AUTH-LANDING-PAGES-HANDOFF.md` §8.3/§10.1/§11 and 86ak120kw. Copy is A11's, adapted
 * from the desktop frame to the web card; geometry and a11y are the shared auth
 * conventions (§2.3, §12) via `AuthShell` and `auth.css`.
 *
 * THREE THINGS THE HANDOFF ASKS FOR THAT ARE NOT BUILT, AND WHY
 * ------------------------------------------------------------
 * 1. §4c "Email taken → An account with this email already exists. [Sign in instead]" —
 *    NOT BUILT, and it must never be. `register_customer_user` returns `accepted: true`
 *    whether the address is new or already registered; it does not raise for a taken
 *    address at all, so there is no signal to render even if we wanted one. Building it
 *    would mean inventing the oracle from a guess. The real owner is told instead, out of
 *    band, by the "someone tried to sign up with your address" email
 *    (`TRANSACTIONAL-EMAIL-spec.md` §3) — tell the owner, tell the submitter nothing.
 *    This is 86ak120kw's first correction and the one it calls a security issue.
 *
 * 2. §3c/§4d "8 characters + one uppercase + one number" — NOT BUILT. The API is
 *    10-200 characters, LENGTH ONLY (`_validate_password`). `passwordPolicy.ts` mirrors
 *    the real rule. 86ak120kw's second correction.
 *
 * 3. §4b's four-segment password strength meter — NOT BUILT. A meter is a picture of a
 *    complexity policy, and there is no complexity policy: the server accepts any ten
 *    characters. Drawing "Weak" over a password the server will accept, or "Strong" over
 *    one it will not, teaches the user a rule that does not exist. A11's hint —
 *    "At least 10 characters" — is the rule, stated. Raised in the handoff notes.
 *
 * AND ONE FIELD THE HANDOFF FORGETS
 * ---------------------------------
 * §4a lists four fields; `RegisterCustomerUserInput` requires `country`, and
 * `len(country) != 2` is a hard reject. A form built from §4a alone fails EVERY signup
 * with a `VALIDATION_FAILED` that looks exactly like a bad password. §9 of the auth
 * handoff has the real field set.
 */
import { nextTick, onBeforeUnmount, ref } from 'vue'
import AuthShell from '@/components/auth/AuthShell.vue'
import AuthBanner from '@/components/auth/AuthBanner.vue'
import StatusDisc from '@/components/auth/StatusDisc.vue'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'
import { registerAccount, resendVerification } from '@/lib/api/account.ts'
import { ApiError } from '@/lib/api/graphql.ts'
import { countryOptions, guessCountry } from '@/lib/auth/countries.ts'
import { MIN_PASSWORD_LENGTH } from '@/lib/auth/passwordPolicy.ts'
import {
  CHECK_SPAM_NOTE,
  NEWEST_LINK_BODY,
  NEWEST_LINK_TITLE,
  RATE_LIMITED_BODY,
  RATE_LIMITED_TITLE,
  RESEND_FAILED,
  RESEND_RATE_LIMITED
} from '@/lib/auth/messages.ts'
import {
  collapseWhitespace,
  detectTimezone,
  newIdempotencyKey,
  validateSignup,
  type SignupErrors,
} from '@/lib/auth/signupPolicy.ts'

type SignUpState =
  /** The form, with or without field-level errors. */
  | 'form'
  /** The mutation is in flight. */
  | 'submitting'
  /** Accepted. Rendered IDENTICALLY whether or not the address was already registered. */
  | 'sent'
  /** A fresh verification link has been requested from the sent state. */
  | 'resent'

const state = ref<SignUpState>('form')
const heading = ref<HTMLElement | null>(null)

const orgName = ref('')
const displayName = ref('')
const email = ref('')
const country = ref(guessCountry())
const password = ref('')
const confirmPassword = ref('')
const agreeTerms = ref(false)

const errors = ref<SignupErrors>({})
const bannerTitle = ref('')
const bannerBody = ref('')

/** The address the accepted request was for. Frozen at submit so later typing cannot alter it. */
const submittedEmail = ref('')

const resendPending = ref(false)
const resendError = ref('')

const countries = countryOptions()
const passwordHint = `At least ${MIN_PASSWORD_LENGTH} characters. Use something you don't use anywhere else.`

const controller = new AbortController()
let unmounted = false

/**
 * ONE key per signup ATTEMPT, minted lazily and REUSED across retries.
 *
 * This is the whole point of the idempotency key. After a timeout the client cannot know
 * whether the first request landed; `register_customer_user` namespaces its guard per
 * email fingerprint, so a retry carrying the same key converges on the row that already
 * exists instead of racing a second org into being. Minting a fresh key on retry — the
 * obvious implementation — throws that guarantee away at the exact moment it is needed.
 *
 * Cleared only after an accepted submit, so a second signup from the same page is
 * correctly a new attempt.
 */
let idempotencyKey = ''

const UNREACHABLE_TITLE = "We couldn't create your account just now"
const UNREACHABLE_BODY =
  "We couldn't reach SelahCue. Check your connection and try again — nothing has been created."
/**
 * Deliberately says NOTHING about the email address.
 *
 * Every field is validated before this request is sent, so a `VALIDATION_FAILED` that
 * still arrives is a client/server disagreement — a country code we accept and the API
 * does not, a timezone the column will not hold. It is emphatically not evidence that the
 * address is taken, because a taken address does not raise at all. Guessing otherwise
 * here is how the oracle gets rebuilt by accident.
 */
const REJECTED_TITLE = "We couldn't create your account"
const REJECTED_BODY = 'Please check the details above and try again.'


async function focusHeading(): Promise<void> {
  await nextTick()
  heading.value?.focus()
}

async function submit(): Promise<void> {
  if (state.value === 'submitting') return
  bannerTitle.value = ''
  bannerBody.value = ''

  errors.value = validateSignup({
    orgName: orgName.value,
    displayName: displayName.value,
    email: email.value,
    password: password.value,
    confirmPassword: confirmPassword.value,
    country: country.value,
    agreeTerms: agreeTerms.value,
  })
  if (Object.keys(errors.value).length > 0) {
    // Stay on the form; the field-level messages carry the correction. No request is
    // sent, so the server's single collapsed VALIDATION_FAILED never has to be guessed at.
    state.value = 'form'
    return
  }

  if (idempotencyKey === '') {
    try {
      idempotencyKey = newIdempotencyKey()
    } catch {
      // No secure random source. Honest, and not a dead end — the message names the
      // cause and the form is still there.
      bannerTitle.value = "We couldn't start a secure signup"
      bannerBody.value =
        'This browser could not generate a secure signup key. Try a different browser, or contact support.'
      return
    }
  }

  state.value = 'submitting'
  const address = email.value.trim()

  try {
    await registerAccount(
      {
        idempotencyKey,
        email: address,
        password: password.value,
        orgName: collapseWhitespace(orgName.value),
        country: country.value.trim().toUpperCase(),
        displayName: collapseWhitespace(displayName.value),
        timezone: detectTimezone(),
      },
      { signal: controller.signal },
    )
    if (unmounted) return

    // ACCEPTED. There is exactly one success path and it does not branch, because the
    // response does not: `accepted: true` arrives for a brand-new address and for one
    // that already has an account, and the client cannot tell which — by design.
    submittedEmail.value = address
    // The passwords have served their purpose; drop both rather than leave plaintext in
    // component state for as long as the tab is open.
    password.value = ''
    confirmPassword.value = ''
    idempotencyKey = ''
    state.value = 'sent'
    void focusHeading()
  } catch (error) {
    if (unmounted || controller.signal.aborted) return
    state.value = 'form'
    if (error instanceof ApiError && error.code === 'NETWORK') {
      bannerTitle.value = UNREACHABLE_TITLE
      bannerBody.value = UNREACHABLE_BODY
    } else if (error instanceof ApiError && error.code === 'RATE_LIMITED') {
      bannerTitle.value = RATE_LIMITED_TITLE
      bannerBody.value = RATE_LIMITED_BODY
    } else {
      bannerTitle.value = REJECTED_TITLE
      bannerBody.value = REJECTED_BODY
    }
  }
}

async function submitResend(): Promise<void> {
  resendPending.value = true
  resendError.value = ''
  try {
    await resendVerification(submittedEmail.value, { signal: controller.signal })
    if (unmounted) return
    state.value = 'resent'
    void focusHeading()
  } catch (error) {
    if (unmounted) return
    // Never fall through to the sent state on failure — `resendVerificationEmail` returns
    // `accepted: true` for every valid address, so an error means it genuinely did not
    // happen, and "check your inbox" would be a lie told to someone already stuck.
    resendError.value =
      error instanceof ApiError && error.code === 'RATE_LIMITED'
        ? RESEND_RATE_LIMITED
        : RESEND_FAILED
  } finally {
    if (!unmounted) resendPending.value = false
  }
}

onBeforeUnmount(() => {
  unmounted = true
  controller.abort()
})
</script>

<template>
  <AuthShell>
    <!-- ============================================================ the form + errors -->
    <template v-if="state === 'form' || state === 'submitting'">
      <AuthBanner v-if="bannerTitle" kind="danger" :title="bannerTitle" alert>
        {{ bannerBody }}
      </AuthBanner>

      <h1 ref="heading" tabindex="-1" class="au-title au-title-form">
        Create your SelahCue account
      </h1>
      <p class="au-body">
        One account per church. It manages your plan, license and the devices you activate —
        it is not needed to run a service.
      </p>

      <form
        novalidate
        aria-label="Create account"
        :aria-busy="state === 'submitting'"
        :class="{ 'is-submitting': state === 'submitting' }"
        @submit.prevent="submit"
      >
        <FormField
          v-model="orgName"
          label="Church or organisation"
          placeholder="Grace Community Church"
          autocomplete="organization"
          required
          :error="errors.orgName"
          :disabled="state === 'submitting'"
        />
        <FormField
          v-model="displayName"
          label="Your name"
          placeholder="Alex Morgan"
          autocomplete="name"
          :error="errors.displayName"
          :disabled="state === 'submitting'"
        />
        <FormField
          v-model="email"
          type="email"
          label="Email"
          placeholder="you@yourchurch.org"
          autocomplete="email"
          required
          :error="errors.email"
          :disabled="state === 'submitting'"
        />

        <!-- Required by the API and absent from the handoff's field list. Not a FormField
             because that component renders inputs and textareas only; the markup below
             carries the same label / aria-invalid / aria-describedby contract by hand. -->
        <div class="form-field" :class="{ 'has-error': !!errors.country }">
          <label for="signup-country" class="field-label">
            Country
            <span class="required-star" aria-hidden="true">*</span>
          </label>
          <select
            id="signup-country"
            v-model="country"
            class="au-select"
            autocomplete="country"
            :disabled="state === 'submitting'"
            :aria-invalid="!!errors.country"
            :aria-describedby="errors.country ? 'signup-country-error' : undefined"
          >
            <option value="">Select a country</option>
            <option v-for="option in countries" :key="option.code" :value="option.code">
              {{ option.label }}
            </option>
          </select>
          <p v-if="errors.country" id="signup-country-error" class="au-field-error" role="alert">
            {{ errors.country }}
          </p>
        </div>

        <FormField
          v-model="password"
          type="password"
          label="Password"
          autocomplete="new-password"
          required
          :hint="passwordHint"
          :error="errors.password"
          :disabled="state === 'submitting'"
        />
        <FormField
          v-model="confirmPassword"
          type="password"
          label="Confirm password"
          autocomplete="new-password"
          required
          :error="errors.confirmPassword"
          :disabled="state === 'submitting'"
        />

        <!-- Validated on submit rather than by disabling the button. A disabled primary
             action gives a keyboard user a dead control and no reason for it; A12
             specifies the message for exactly that reason. -->
        <label class="au-check">
          <input
            v-model="agreeTerms"
            type="checkbox"
            :disabled="state === 'submitting'"
            :aria-invalid="!!errors.terms"
            :aria-describedby="errors.terms ? 'signup-terms-error' : undefined"
          />
          <span>
            I agree to the SelahCue
            <router-link to="/terms">Terms of Service</router-link> and
            <router-link to="/privacy">Privacy Policy</router-link>.
          </span>
        </label>
        <p v-if="errors.terms" id="signup-terms-error" class="au-field-error" role="alert">
          {{ errors.terms }}
        </p>

        <div class="au-actions">
          <UiButton
            variant="primary"
            size="lg"
            class="au-btn au-btn-primary"
            :loading="state === 'submitting'"
          >
            <template v-if="state === 'submitting'">Creating account…</template>
            <template v-else>Create account</template>
          </UiButton>
        </div>
      </form>

      <p v-if="state === 'submitting'" class="au-note" role="status" aria-live="polite">
        Creating your account…
      </p>

      <AuthBanner kind="info" title="You can skip this entirely">
        SelahCue works offline. Slides, scripture, media, blackout/clear and timers all run
        without an account — signing up only unlocks cloud features, licensing and device
        management.
      </AuthBanner>
    </template>

    <!-- ================================================== accepted (A13 equivalent) -->
    <!-- THE STATE THAT MUST NOT BRANCH. It is reached for a brand-new address and for one
         that already has an account, and it renders identically for both, because the
         response is identical for both. The copy is chosen to be TRUE of both: an email
         genuinely goes out either way — the verification link, or the "someone tried to
         sign up with your address" notice to the real owner — so "an email is on its way"
         is accurate without naming which, where "we've sent your verification link" would
         be false in one branch and "if this address is not already registered" would hand
         back the oracle in the shape of a hint. -->
    <template v-else-if="state === 'sent'">
      <StatusDisc tone="brand" glyph="✉" />
      <h1 ref="heading" tabindex="-1" class="au-title">Check your email to finish setting up</h1>
      <p class="au-body">
        An email is on its way to {{ submittedEmail }}. Open it to finish setting up your
        account — verification links expire 24 hours after they are sent.
      </p>
      <div class="au-actions">
        <UiButton
          variant="primary"
          size="lg"
          class="au-btn au-btn-primary"
          :loading="resendPending"
          @click="submitResend"
        >
          Resend verification email
        </UiButton>
        <UiButton to="/signin" variant="secondary" size="lg" class="au-btn au-btn-secondary">
          Back to sign in
        </UiButton>
      </div>
      <p v-if="resendError" class="au-note" role="alert">{{ resendError }}</p>
      <p v-else class="au-note">{{ CHECK_SPAM_NOTE }}</p>
      <AuthBanner kind="info" title="Nothing is waiting on this">
        SelahCue runs a full service offline without an account. Verifying only unlocks plan,
        license and device management.
      </AuthBanner>
    </template>

    <!-- ============================================================ fresh link sent -->
    <template v-else>
      <StatusDisc tone="brand" glyph="✉" />
      <h1 ref="heading" tabindex="-1" class="au-title">Check your inbox</h1>
      <!-- Conditional by construction, exactly as V5 — `resendVerificationEmail` answers
           the same for an unknown, unverified or already-verified address. -->
      <p class="au-body">
        If {{ submittedEmail }} has a SelahCue account waiting to be verified, a new link is
        on its way. It expires in 24 hours.
      </p>
      <div class="au-actions">
        <UiButton to="/signin" variant="secondary" size="lg" class="au-btn au-btn-secondary">
          Back to sign in
        </UiButton>
      </div>
      <AuthBanner kind="info" :title="NEWEST_LINK_TITLE">
        {{ NEWEST_LINK_BODY }}
      </AuthBanner>
    </template>

    <!-- ==================================================================== footer -->
    <template #footer>
      <template v-if="state === 'form' || state === 'submitting'">
        <span>Already have an account?</span><router-link to="/signin">Sign in</router-link>
      </template>
      <template v-else>
        <span>Need a hand?</span><router-link to="/support">Contact support</router-link>
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
