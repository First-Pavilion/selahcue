<script setup lang="ts">
/**
 * `/signin` — email + password, against the real `login` mutation (86ak11r67).
 *
 * Design: Sign in `505:124`; states from `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §3,
 * corrected by `AUTH-LANDING-PAGES-HANDOFF.md` §11 and 86ak120kw. Card geometry, banner
 * rules and a11y conventions come from the auth handoff §2.3 / §12, shared with the
 * shipped /verify and /reset pages through `AuthShell` and `auth.css`.
 *
 * WHAT THIS REPLACED
 * ------------------
 * A `setTimeout(…, 1000)` that faked every outcome: a hardcoded `error@test.com` failure,
 * a fabricated "Reset link sent!" success for an email nobody sent, and a "Continue with
 * Google" button that waited 800ms and routed to /account. The OAuth button is gone
 * rather than wired: DEC-007 chose SelahCue-owned email/password and explicitly rejected
 * OIDC, there is no social mutation on the account schema, and no config key for one
 * exists anywhere in the tree. It was an assumed placeholder in
 * `MARKETING-SITE-HANDOFF.md` §161, spec'd before the provider decision was taken.
 *
 * THE ONE RULE THIS VIEW EXISTS TO KEEP
 * -------------------------------------
 * `login` returns `UNAUTHENTICATED` for an unknown email, for a wrong password, AND for
 * a locked-out account. That is not laziness in the service — it runs a dummy PBKDF2 on
 * the unknown-email branch and a real one on the locked branch specifically so the three
 * take the same time. The server buys indistinguishability; a client that renders any
 * difference between them spends it. So there is exactly ONE rejection state here, with
 * one message, reached by one code path. Do not add a branch to it, however tempting the
 * support ticket that asks for one.
 *
 * `POLICY_DENIED` is the single sanctioned exception and it is safe for a specific
 * reason: `login` raises it only AFTER `check_password` has returned true, so it is
 * reachable only by someone who already proved they know the password. It still does not
 * assert WHICH of its two causes applied — unverified email, or a deactivated account —
 * because the API does not say, and it always offers a way forward (FR-552).
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthShell from '@/components/auth/AuthShell.vue'
import AuthBanner from '@/components/auth/AuthBanner.vue'
import StatusDisc from '@/components/auth/StatusDisc.vue'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'
import { resendVerification } from '@/lib/api/account.ts'
import { ApiError } from '@/lib/api/graphql.ts'
import { validateEmail } from '@/lib/auth/emailPolicy.ts'
import { signIn } from '@/lib/auth/sessionStore.ts'
import { safeNextPath } from '@/lib/auth/redirect.ts'

type SignInState =
  /** The form, with or without field-level errors. */
  | 'form'
  /** The mutation is in flight. */
  | 'submitting'
  /** Correct password, but the account is unverified or deactivated. */
  | 'notReady'
  /** A fresh verification link has been requested. */
  | 'resent'

const route = useRoute()
const router = useRouter()

const state = ref<SignInState>('form')
const heading = ref<HTMLElement | null>(null)

const email = ref('')
const password = ref('')
const errors = ref<{ email?: string; password?: string }>({})

/** Empty when there is nothing to report. Rendered as the card-top banner. */
const bannerTitle = ref('')
const bannerBody = ref('')

const resendPending = ref(false)
const resendError = ref('')

const controller = new AbortController()
let unmounted = false

/**
 * ONE message for unknown email, wrong password and lockout alike.
 *
 * Held as a constant and assigned from a single place so there is no seam for a future
 * edit to slip a second variant into. `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §3b's copy.
 */
const REJECTED_TITLE = 'Invalid email or password'
const REJECTED_BODY = 'Check both and try again.'

const UNREACHABLE_TITLE = "We couldn't sign you in just now"
const UNREACHABLE_BODY =
  "We couldn't reach SelahCue. Check your connection and try again — your account is unaffected."

const RATE_LIMITED_TITLE = 'Too many attempts'
const RATE_LIMITED_BODY = 'Wait a few minutes, then try again.'

const RESEND_FAILED = "We couldn't send a link just now. Please try again in a moment."
const RESEND_RATE_LIMITED =
  'Too many requests for a new link. Wait a few minutes, then try again.'

/** Shown when the route guard bounced someone here because their session had ended. */
const arrivedExpired = computed(() => route.query.reason === 'expired')

async function focusHeading(): Promise<void> {
  await nextTick()
  heading.value?.focus()
}

function clearBanner(): void {
  bannerTitle.value = ''
  bannerBody.value = ''
}

function validate(): boolean {
  const next: { email?: string; password?: string } = {}
  const emailError = validateEmail(email.value)
  if (emailError) next.email = emailError
  // Length is NOT checked here, and that is deliberate. On /reset a short password must
  // be caught client-side because the server would answer with the same code as a dead
  // token. Here there is no such confusion — a wrong password is simply wrong — and a
  // "must be at least 10 characters" message on a SIGN-IN form would tell an attacker
  // that any shorter guess is not worth submitting, and would lock out a legacy account
  // whose password predates the current rule.
  if (password.value === '') next.password = 'Enter your password.'
  errors.value = next
  return Object.keys(next).length === 0
}

async function submit(): Promise<void> {
  if (state.value === 'submitting') return
  clearBanner()
  if (!validate()) return

  state.value = 'submitting'
  try {
    await signIn(email.value.trim(), password.value, { signal: controller.signal })
    if (unmounted) return
    // Drop the plaintext rather than leave it in component state for as long as the tab
    // is open. The session is a cookie now; this value has served its purpose.
    password.value = ''
    // `safeNextPath` refuses anything that is not a same-site path, so a crafted
    // `?next=https://evil.example` cannot turn this redirect into an open redirect.
    await router.replace(safeNextPath(route.query.next, '/account'))
    return
  } catch (error) {
    if (unmounted || controller.signal.aborted) return

    if (error instanceof ApiError && error.code === 'POLICY_DENIED') {
      state.value = 'notReady'
      void focusHeading()
      return
    }

    state.value = 'form'
    if (error instanceof ApiError && error.code === 'NETWORK') {
      // A dropped connection is NOT a credential failure. Saying "invalid email or
      // password" here would send someone to reset a password that was never wrong.
      bannerTitle.value = UNREACHABLE_TITLE
      bannerBody.value = UNREACHABLE_BODY
    } else if (error instanceof ApiError && error.code === 'RATE_LIMITED') {
      bannerTitle.value = RATE_LIMITED_TITLE
      bannerBody.value = RATE_LIMITED_BODY
    } else {
      // UNAUTHENTICATED and everything else the server rejected. Note there is no branch
      // inside this branch: unknown email, wrong password and lockout land here together
      // and are indistinguishable, exactly as the service arranged.
      bannerTitle.value = REJECTED_TITLE
      bannerBody.value = REJECTED_BODY
    }
    // §3b: keep the email, clear the password, return focus to it.
    password.value = ''
    await nextTick()
    document.querySelector<HTMLInputElement>('input[type="password"]')?.focus()
  }
}

async function submitResend(): Promise<void> {
  const address = email.value.trim()
  const emailError = validateEmail(address)
  if (emailError) {
    resendError.value = emailError
    return
  }

  resendPending.value = true
  resendError.value = ''
  try {
    // Padded to a ~0.25s floor server-side so its branches are indistinguishable. The
    // pending state must stay visible; do not optimise it away.
    await resendVerification(address, { signal: controller.signal })
    if (unmounted) return
    state.value = 'resent'
    void focusHeading()
  } catch (error) {
    if (unmounted) return
    // Never fall through to the sent state. The mutation returns `accepted: true` for
    // every valid address, so an error means the request genuinely did not happen.
    resendError.value =
      error instanceof ApiError && error.code === 'RATE_LIMITED'
        ? RESEND_RATE_LIMITED
        : RESEND_FAILED
  } finally {
    if (!unmounted) resendPending.value = false
  }
}

onMounted(() => {
  // Only ever a path, never a token: `next` is sanitised at use, and nothing on this
  // route carries a credential in the query string.
  if (arrivedExpired.value) void focusHeading()
})

onBeforeUnmount(() => {
  unmounted = true
  controller.abort()
})
</script>

<template>
  <AuthShell>
    <!-- ============================================================ the form + errors -->
    <template v-if="state === 'form' || state === 'submitting'">
      <AuthBanner
        v-if="bannerTitle"
        kind="danger"
        :title="bannerTitle"
        alert
      >
        {{ bannerBody }}
      </AuthBanner>

      <!-- Not an error: the session simply ran out, or was revoked elsewhere. Muted, and
           it says what to do rather than what went wrong. -->
      <AuthBanner
        v-else-if="arrivedExpired"
        kind="info"
        title="You've been signed out"
        alert
      >
        Sign in again to get back to your account. Devices you have already activated kept
        presenting throughout.
      </AuthBanner>

      <h1 ref="heading" tabindex="-1" class="au-title au-title-form">Sign in to SelahCue</h1>
      <p class="au-body">Manage your plan, license and the devices you have activated.</p>

      <form
        novalidate
        aria-label="Sign in"
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
          :error="errors.email"
          :disabled="state === 'submitting'"
        />
        <FormField
          v-model="password"
          type="password"
          label="Password"
          autocomplete="current-password"
          :error="errors.password"
          :disabled="state === 'submitting'"
        />

        <p class="au-inline-link">
          <router-link to="/forgot-password">Forgot your password?</router-link>
        </p>

        <div class="au-actions">
          <UiButton
            variant="primary"
            size="lg"
            class="au-btn au-btn-primary"
            :loading="state === 'submitting'"
          >
            <template v-if="state === 'submitting'">Signing in…</template>
            <template v-else>Sign in</template>
          </UiButton>
        </div>
      </form>

      <p v-if="state === 'submitting'" class="au-note" role="status" aria-live="polite">
        Signing you in…
      </p>

      <!-- The hard invariant (auth handoff §1): account state never blocks presentation,
           and every frame says so. -->
      <AuthBanner kind="info" title="You don't need an account to run SelahCue">
        Signing in manages your plan, license and devices. Live presentation works offline,
        always.
      </AuthBanner>
    </template>

    <!-- ================================== correct password, account not usable yet -->
    <!-- Merged on purpose. `login` raises POLICY_DENIED for an unverified email AND for a
         non-active account, and does not say which, so this must not assert either. It
         always offers the one action that fixes the common case. -->
    <template v-else-if="state === 'notReady'">
      <StatusDisc tone="warning" glyph="!" />
      <h1 ref="heading" tabindex="-1" class="au-title">This account isn't ready to sign in yet</h1>
      <p class="au-body">
        It may still need its email address verified, or it may have been deactivated. If
        {{ email.trim() }} is waiting to be verified, we can send a new link.
      </p>
      <div class="au-actions">
        <UiButton
          variant="primary"
          size="lg"
          class="au-btn au-btn-primary"
          :loading="resendPending"
          @click="submitResend"
        >
          Send a verification link
        </UiButton>
      </div>
      <p v-if="resendError" class="au-note" role="alert">{{ resendError }}</p>
      <AuthBanner kind="info" title="Still stuck after verifying?">
        If you have already verified this address, contact support and we'll take a look at
        the account.
      </AuthBanner>
    </template>

    <!-- ============================================================ fresh link sent -->
    <template v-else>
      <StatusDisc tone="brand" glyph="✉" />
      <h1 ref="heading" tabindex="-1" class="au-title">Check your inbox</h1>
      <!-- Conditional by construction, as V5. `resendVerificationEmail` returns the same
           answer for an address that is unknown, unverified or already verified, so a
           direct claim would be both a lie and an oracle. -->
      <p class="au-body">
        If {{ email.trim() }} has a SelahCue account waiting to be verified, a new link is
        on its way. It expires in 24 hours.
      </p>
      <div class="au-actions">
        <UiButton
          variant="secondary"
          size="lg"
          class="au-btn au-btn-secondary"
          @click="state = 'form'"
        >
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
      <template v-if="state === 'form' || state === 'submitting'">
        <span>New to SelahCue?</span><router-link to="/signup">Create an account</router-link>
      </template>
      <template v-else-if="state === 'notReady'">
        <span>Need a hand?</span><router-link to="/support">Contact support</router-link>
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

/* Fields at 50% opacity while the mutation is in flight, matching R3. They are also
   genuinely disabled — dimming alone would leave them editable. */
.is-submitting :deep(.form-field) {
  opacity: 0.5;
}
</style>
