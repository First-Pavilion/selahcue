<script setup lang="ts">
/**
 * `/verify?token=…` — where the verification email's button lands.
 *
 * Design: `docs/design/AUTH-LANDING-PAGES-HANDOFF.md` §4 + §8.1.
 * Figma: V1 `743:125` · V2 `743:139` · V3 `746:124` · V5 `746:172` · V6 `747:124`.
 *
 * WHICH STATES EXIST, AND WHY V4 DOES NOT
 * ---------------------------------------
 * `verify_email` (`apps/accounts/services.py:494`) collapses unknown / wrong-purpose /
 * already-consumed / EXPIRED into a single `VALIDATION_FAILED`, deliberately, so the
 * endpoint cannot be used as an oracle. The client therefore CANNOT know why a token
 * failed.
 *
 * V4 ("This verification link has expired", naming the 24-hour TTL) is designed and
 * ready, but rendering it would mean claiming knowledge we do not have — half the users
 * who saw it would have a link that was consumed or mistyped, not expired. So this view
 * ships the MERGED failure state V3, whose copy names all three possible causes without
 * asserting which, and which always carries the resend affordance. As the design note
 * puts it: the user never needs to know why it failed if the fix is one click either way.
 *
 * V4 becomes buildable only if 86ak120fz decides the API should return a distinguishable
 * `EXPIRED`. That is a security-posture decision, not a frontend one.
 *
 * The one failure the CLIENT can genuinely distinguish is "no token at all" — a bookmark,
 * a stripped query, a mangled link — so that keeps its own state (V6), and is not red,
 * because arriving without a link is not an error.
 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import AuthShell from '@/components/auth/AuthShell.vue'
import AuthBanner from '@/components/auth/AuthBanner.vue'
import StatusDisc from '@/components/auth/StatusDisc.vue'
import FormField from '@/components/FormField.vue'
import UiButton from '@/components/UiButton.vue'
import { resendVerification, verifyEmail } from '@/lib/api/account.ts'
import { ApiError } from '@/lib/api/graphql.ts'
import { validateEmail } from '@/lib/auth/emailPolicy.ts'
import { takeLandingToken } from '@/lib/auth/useLandingToken.ts'

type VerifyState =
  /** V1 — the mutation is in flight. */
  | 'verifying'
  /** V2 — the account is active. */
  | 'verified'
  /** V3 — merged failure: expired OR consumed OR unknown OR mistyped. */
  | 'invalid'
  /** V6 — opened without `?token=`. Not an error. */
  | 'missing'
  /** V5 — a fresh link has been requested. */
  | 'sent'
  /** Extrapolated from R7 — we could not reach the API at all. See below. */
  | 'unreachable'

/**
 * §4.1: "Do not show this for less than ~300 ms — flash it only if the request is
 * genuinely in flight." A verification that resolves in 40ms would otherwise strobe a
 * spinner and a progress bar on screen, which reads as a glitch rather than as work.
 * Once V1 is on screen it stays for at least this long.
 */
const MIN_VERIFYING_MS = 300

const state = ref<VerifyState>('verifying')
const heading = ref<HTMLElement | null>(null)

// The token is held OUTSIDE reactive state on purpose: it is a single-use credential,
// and reactive state is the thing most likely to end up in a devtools dump or a future
// serialisation. `takeLandingToken` has already removed it from the address bar.
let landingToken = ''

const controller = new AbortController()
let unmounted = false

// Resend sub-form, shared by V3 / V6.
const email = ref('')
const emailError = ref('')
const resendPending = ref(false)
const resendFailed = ref(false)
const sentToEmail = ref('')

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Move focus to the card's heading when the page resolves to a new state.
 *
 * Preferred over wrapping the whole card in a live region: the terminal states are
 * several paragraphs plus a banner, and announcing all of that on every transition is
 * worse than useless. Focusing the heading tells a screen-reader user exactly where they
 * now are and leaves them at the top of the new content. V1 itself is announced by its
 * own `role="status"` (§12).
 */
async function focusHeading(): Promise<void> {
  await nextTick()
  heading.value?.focus()
}

async function runVerification(): Promise<void> {
  state.value = 'verifying'
  const startedAt = Date.now()

  try {
    const verified = await verifyEmail(landingToken, { signal: controller.signal })
    await holdMinimumSpinner(startedAt)
    if (unmounted) return
    // `verified: false` without an error is not a shape the API produces today, but
    // trusting it blindly would show a success card for a non-success. Treat anything
    // that is not an affirmative `true` as the failure state.
    state.value = verified ? 'verified' : 'invalid'
  } catch (error) {
    if (unmounted || controller.signal.aborted) return
    await holdMinimumSpinner(startedAt)
    if (unmounted) return
    // The ONLY split available: could we talk to the API at all? A transport failure
    // must not be reported as a dead link — the link is very probably fine, and sending
    // the user off to request a new one because their wifi dropped wastes a token and
    // their time. Everything the server actually rejected is the merged V3.
    state.value = error instanceof ApiError && error.code === 'NETWORK' ? 'unreachable' : 'invalid'
  }
  void focusHeading()
}

async function holdMinimumSpinner(startedAt: number): Promise<void> {
  const elapsed = Date.now() - startedAt
  if (elapsed < MIN_VERIFYING_MS) await sleep(MIN_VERIFYING_MS - elapsed)
}

async function submitResend(): Promise<void> {
  emailError.value = validateEmail(email.value)
  if (emailError.value) return

  resendPending.value = true
  resendFailed.value = false
  const address = email.value.trim()

  try {
    await resendVerification(address, { signal: controller.signal })
    if (unmounted) return
    sentToEmail.value = address
    state.value = 'sent'
    void focusHeading()
  } catch {
    if (unmounted) return
    // Do NOT fall through to V5 on failure. `resendVerification` is expected to return
    // `accepted: true` for every address (86ak120ac's no-enumeration contract), so an
    // error genuinely means the request did not happen — and until that mutation is
    // merged, EVERY call lands here. Showing "check your inbox" would be a lie told to
    // someone already stuck. This message reveals nothing about the address.
    resendFailed.value = true
  } finally {
    if (!unmounted) resendPending.value = false
  }
}

onMounted(() => {
  landingToken = takeLandingToken()
  if (!landingToken) {
    state.value = 'missing'
    return
  }
  void runVerification()
})

onBeforeUnmount(() => {
  unmounted = true
  // Stop an in-flight verification from resolving into a torn-down component.
  controller.abort()
})
</script>

<template>
  <AuthShell>
    <!-- ============================================================= V1 verifying -->
    <template v-if="state === 'verifying'">
      <StatusDisc tone="brand" glyph="↻" />
      <h1 ref="heading" tabindex="-1" class="au-title">Verifying your email address…</h1>
      <p class="au-body">This only takes a moment. Keep this tab open.</p>
      <!-- §12: announced politely. The bar is indeterminate, so it carries no
           aria-valuenow — claiming a percentage we do not have would be worse than
           silence. It holds static under prefers-reduced-motion (auth.css). -->
      <div role="status" aria-live="polite" aria-label="Verifying your email address">
        <div class="au-progress"><div class="au-progress-fill"></div></div>
      </div>
    </template>

    <!-- ============================================================== V2 verified -->
    <template v-else-if="state === 'verified'">
      <StatusDisc tone="success" glyph="✓" />
      <h1 ref="heading" tabindex="-1" class="au-title">Email address verified</h1>
      <p class="au-body">
        Thanks — your SelahCue account is active. Sign in to manage your plan, license and
        devices.
      </p>
      <div class="au-actions">
        <UiButton to="/signin" variant="primary" size="lg" class="au-btn au-btn-primary">
          Continue to sign in
        </UiButton>
      </div>
      <AuthBanner kind="success" title="You don't need an account to run SelahCue">
        Verification only unlocks plan, license and device management. Live presentation
        works offline, always.
      </AuthBanner>
    </template>

    <!-- ===================================== V3 merged failure (the state that ships) -->
    <template v-else-if="state === 'invalid'">
      <StatusDisc tone="danger" glyph="✕" />
      <h1 ref="heading" tabindex="-1" class="au-title">This verification link didn't work</h1>
      <!-- Names all three causes without claiming to know which, because the API does
           not tell us. Do not "tighten" this into a single cause. -->
      <p class="au-body">
        The link may have expired, already been used, or been copied incompletely. Enter
        your email address and we'll send a fresh one.
      </p>
      <form novalidate @submit.prevent="submitResend">
        <FormField
          v-model="email"
          type="email"
          label="Email"
          placeholder="you@yourchurch.org"
          autocomplete="email"
          :error="emailError"
          :disabled="resendPending"
        />
        <div class="au-actions">
          <UiButton
            variant="primary"
            size="lg"
            class="au-btn au-btn-primary"
            :loading="resendPending"
          >
            Send a new verification link
          </UiButton>
        </div>
      </form>
      <p v-if="resendFailed" class="au-note" role="alert">
        We couldn't send a new link just now. Please try again in a moment.
      </p>
      <AuthBanner kind="info" title="Already verified? Just sign in">
        A verification link stops working once it has been used. If you have already
        confirmed this address, sign in as normal.
      </AuthBanner>
    </template>

    <!-- =============================================================== V6 no token -->
    <template v-else-if="state === 'missing'">
      <!-- Muted, not red: opening this page without a link is not an error. -->
      <StatusDisc tone="neutral" glyph="!" />
      <h1 ref="heading" tabindex="-1" class="au-title">This page needs a verification link</h1>
      <p class="au-body">
        Open the link in the email we sent you. If you no longer have it, enter your
        address and we'll send a new one.
      </p>
      <form novalidate @submit.prevent="submitResend">
        <FormField
          v-model="email"
          type="email"
          label="Email"
          placeholder="you@yourchurch.org"
          autocomplete="email"
          :error="emailError"
          :disabled="resendPending"
        />
        <div class="au-actions">
          <UiButton
            variant="primary"
            size="lg"
            class="au-btn au-btn-primary"
            :loading="resendPending"
          >
            Send a verification link
          </UiButton>
        </div>
      </form>
      <p v-if="resendFailed" class="au-note" role="alert">
        We couldn't send a link just now. Please try again in a moment.
      </p>
    </template>

    <!-- ============================================================== V5 link sent -->
    <template v-else-if="state === 'sent'">
      <StatusDisc tone="brand" glyph="✉" />
      <h1 ref="heading" tabindex="-1" class="au-title">Check your inbox</h1>
      <!-- CONDITIONAL BY CONSTRUCTION. "If … has a SelahCue account" is load-bearing for
           no-enumeration and must not be "improved" into "We've sent you an email" — the
           API returns the same answer for an address that has no account at all, so a
           direct claim would be both a lie and an existence oracle. -->
      <p class="au-body">
        If {{ sentToEmail }} has a SelahCue account waiting to be verified, a new link is
        on its way. It expires in 24 hours.
      </p>
      <div class="au-actions">
        <UiButton to="/signin" variant="secondary" size="lg" class="au-btn au-btn-secondary">
          Back to Sign in
        </UiButton>
      </div>
      <p class="au-note">
        Didn't arrive? Check your spam folder, then request another link.
      </p>
      <AuthBanner kind="info" title="Only the newest link works">
        Sending a new link cancels the previous one. Use the most recent email you
        received.
      </AuthBanner>
    </template>

    <!-- ============================================ transport failure (extrapolated) -->
    <!-- Not in the design: the /verify series has no server-error frame, though /reset
         has R7 for exactly this. Rendering V3 here would tell the user their link is
         dead when we simply never reached the server. This mirrors R7's shape and its
         "your link still works" reassurance, which is accurate — `verify_email` is
         transaction.atomic, and a request that never arrived consumed nothing. -->
    <template v-else>
      <StatusDisc tone="warning" glyph="!" />
      <h1 ref="heading" tabindex="-1" class="au-title">We couldn't verify your email just now</h1>
      <p class="au-body">
        We couldn't reach SelahCue. Check your connection and try again — this page is the
        only thing affected.
      </p>
      <div class="au-actions">
        <UiButton variant="primary" size="lg" class="au-btn au-btn-primary" @click="runVerification">
          Try again
        </UiButton>
      </div>
      <AuthBanner kind="success" title="Your link still works">
        Nothing has been used up. Your verification link is unchanged and will keep
        working until it expires.
      </AuthBanner>
    </template>

    <!-- ==================================================================== footer -->
    <template #footer>
      <template v-if="state === 'verifying'">
        <span>Taking too long?</span><router-link to="/signin">Back to Sign in</router-link>
      </template>
      <template v-else-if="state === 'verified'">
        <span>Not your account?</span><router-link to="/support">Contact support</router-link>
      </template>
      <template v-else-if="state === 'sent'">
        <span>Need a hand?</span><router-link to="/support">Contact support</router-link>
      </template>
      <template v-else-if="state === 'missing'">
        <span>Already verified?</span><router-link to="/signin">Back to Sign in</router-link>
      </template>
      <template v-else>
        <span>Remembered everything?</span><router-link to="/signin">Back to Sign in</router-link>
      </template>
    </template>
  </AuthShell>
</template>

<style scoped>
/* Focusing the heading programmatically must not paint a focus ring — the ring belongs
   to keyboard navigation, and this focus move is a courtesy to screen-reader users. */
.au-title:focus {
  outline: none;
}

.au-title:focus-visible {
  outline: 2px solid var(--sc-primary);
  outline-offset: 4px;
}
</style>
