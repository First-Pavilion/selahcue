/**
 * The app-wide answer to "is someone signed in?", and the three operations that change it.
 *
 * Split from `session.ts` on purpose: that module is pure storage and is unit tested
 * under `node --test`; this one reaches for Vue reactivity and the network, and is
 * exercised through the headless state harness instead.
 *
 * THE HONEST MODEL
 * ----------------
 * The credential is a cookie this code cannot read. So there are two different questions
 * and they must not be confused:
 *
 *   - "What should the navbar render right now?" — answered instantly from the HINT.
 *     Wrong occasionally, costs nothing when it is.
 *   - "May this person enter a protected route?" — answered by ASKING THE SERVER
 *     (`accountViewer`). The hint is not evidence; it is attacker-writable localStorage,
 *     and it goes stale in the one direction that matters, claiming a session the server
 *     revoked minutes ago.
 *
 * `confirmSession` is the second question and it always makes the round trip. Nothing in
 * this module grants access on the strength of stored state.
 *
 * And none of it is a security boundary in the first place. The server authorises every
 * request against the session cookie; a client guard that could be bypassed by editing
 * localStorage protects nothing. What it does is keep a signed-out visitor from landing
 * on a page of empty panels and error toasts — a UX job, honestly labelled.
 */

import { computed, readonly, ref } from 'vue'

import {
  accountViewer,
  login as loginMutation,
  logout as logoutMutation,
  refreshSession as refreshSessionMutation,
} from '../api/account.ts'
import { ApiError, type GraphQLRequestOptions } from '../api/graphql.ts'
import {
  clearSessionHint,
  readSessionHint,
  writeSessionHint,
  type SessionHint,
} from './session.ts'

/**
 * Shorter than the seam's 15s default. This probe sits in front of a route transition,
 * so its timeout is how long the app can appear frozen after a click. Fifteen seconds of
 * nothing reads as a broken site; eight is long enough for a slow connection and short
 * enough to fall through to the honest "we couldn't check" branch.
 */
const SESSION_PROBE_TIMEOUT_MS = 8000

/**
 * Refresh only when less than a week of the 30-day session is left.
 *
 * The threshold is the safety mechanism, not a tuning knob. `refresh_session` ROTATES:
 * inside one transaction it revokes the presented token and mints a replacement, and the
 * replacement reaches the browser only in the response. If that response is lost — a
 * dropped connection at exactly the wrong moment — the server has revoked a session whose
 * successor nobody received, and the user is signed out.
 *
 * That risk is unavoidable with rotation, so the design is to run it RARELY rather than
 * to pretend it away: once near the end of a 30-day window, instead of on every protected
 * navigation, which would roll the dice several times an hour for no benefit. The failure
 * mode is also survivable — the guard sees `ended`, sends them to /signin, and /signin
 * says why. Not a dead end, just an unnecessary sign-in.
 */
const REFRESH_WHEN_REMAINING_MS = 7 * 24 * 3_600_000

const hint = ref<SessionHint | null>(readSessionHint())

/**
 * What the SERVER last said, or `null` when it has never been asked.
 *
 * Tracked separately from the hint rather than folded into it, because the two can
 * legitimately disagree and the disagreement is informative. A visitor can hold a live
 * cookie with no hint at all — storage cleared, a fresh profile, a browser that dropped
 * site data — and in that case the honest state is "signed in, metadata unknown".
 * Writing a hint full of empty strings to represent that would be inventing data, and
 * `readSessionHint` would reject it on the next load anyway.
 */
const serverConfirmed = ref<boolean | null>(null)

/** Read-only for consumers. Only the operations below may change it. */
export const sessionHint = readonly(hint)

/**
 * Optimistic. Used for CHROME ONLY — which link the navbar shows, whether to offer
 * "Sign out". Never a gate; `confirmSession` is the gate.
 *
 * The server's answer wins whenever there is one. Before the first probe, the hint is
 * the best guess available and is better than rendering everyone signed out for the
 * first few hundred milliseconds of every visit.
 */
export const isProbablySignedIn = computed(() => serverConfirmed.value ?? hint.value !== null)

function remember(metadata: SessionHint): void {
  hint.value = { role: metadata.role, orgId: metadata.orgId, expiresAt: metadata.expiresAt }
  serverConfirmed.value = true
  writeSessionHint(hint.value)
}

function forget(): void {
  hint.value = null
  serverConfirmed.value = false
  clearSessionHint()
}

/**
 * Sign in. Resolves when the session cookie is set; rejects with the API's own `ApiError`.
 *
 * The caller renders the failure, because only the caller knows which copy each code
 * maps to — and `UNAUTHENTICATED` in particular must map to ONE message covering unknown
 * email, wrong password and lockout alike.
 */
export async function signIn(
  email: string,
  password: string,
  options?: GraphQLRequestOptions,
): Promise<void> {
  const metadata = await loginMutation(email, password, options)
  remember(metadata)
}

/**
 * Sign out. Rejects if the session was NOT revoked.
 *
 * This function deliberately does not swallow a failure and clear locally anyway. The
 * cookie is HttpOnly: JavaScript cannot delete it, only the server can, and it does that
 * by responding to this mutation. So if the mutation fails, the session is still live —
 * clearing the hint would paint "signed out" over a browser that is still carrying a
 * working credential, which is the most consequential lie this UI could tell. The caller
 * shows the failure and offers a retry.
 *
 * `UNAUTHENTICATED` is the one failure that IS success: the session was already gone.
 */
export async function signOut(options?: GraphQLRequestOptions): Promise<void> {
  try {
    await logoutMutation(false, options)
  } catch (error) {
    if (error instanceof ApiError && error.code === 'UNAUTHENTICATED') {
      forget()
      return
    }
    throw error
  }
  forget()
}

export type SessionCheck =
  /** The server confirmed a live customer session. */
  | 'live'
  /** The server said there is no session. Any local hint has been dropped. */
  | 'ended'
  /** We could not ask. Says nothing either way — must not be rendered as "signed out". */
  | 'unreachable'

/**
 * Ask the server whether the cookie we are carrying is still a session.
 *
 * The three codes that mean "no session" are collapsed into `ended`:
 * `UNAUTHENTICATED` (expired, revoked, or invalidated by a password change),
 * `PERMISSION_DENIED` (a non-customer actor) and `NOT_FOUND` (`require_customer_org`
 * raises it for an actor with no org). None is actionable differently by a visitor.
 *
 * Everything else — transport failure, an API 500 — is `unreachable`, and the difference
 * matters: reporting a dropped connection as "your session ended" signs a working user
 * out of their own account and sends them to re-enter a password they never needed to.
 */
export async function confirmSession(options?: GraphQLRequestOptions): Promise<SessionCheck> {
  try {
    await accountViewer({ timeoutMs: SESSION_PROBE_TIMEOUT_MS, ...options })
    // The cookie is good. Recorded on `serverConfirmed`, not by fabricating a hint: the
    // probe returns no expiry, and a hint carrying a made-up one would either expire the
    // chrome early or keep it alive past the real session.
    serverConfirmed.value = true
    return 'live'
  } catch (error) {
    if (
      error instanceof ApiError &&
      (error.code === 'UNAUTHENTICATED' ||
        error.code === 'PERMISSION_DENIED' ||
        error.code === 'NOT_FOUND')
    ) {
      forget()
      return 'ended'
    }
    return 'unreachable'
  }
}

/**
 * Extend the session when it is close to running out. Never throws.
 *
 * Called by the route guard after a live check. Deliberately opportunistic: a failure
 * leaves the hint exactly as it was and the user carries on with the session they
 * already had, because a refresh that did not happen is not a session that ended.
 *
 * Returns true when a rotation actually happened, which is what the tests assert on —
 * without it, "did not refresh" and "refreshed silently" look identical.
 */
export async function refreshIfExpiringSoon(
  now: number = Date.now(),
  options?: GraphQLRequestOptions,
): Promise<boolean> {
  const current = hint.value
  if (current === null) return false

  const expiresAt = Date.parse(current.expiresAt)
  if (Number.isNaN(expiresAt)) return false
  if (expiresAt - now > REFRESH_WHEN_REMAINING_MS) return false

  try {
    const rotatedExpiry = await refreshSessionMutation({
      timeoutMs: SESSION_PROBE_TIMEOUT_MS,
      ...options,
    })
    // The new token went into the cookie, which this code cannot read and does not need
    // to. Only the expiry is ours to remember.
    remember({ ...current, expiresAt: rotatedExpiry })
    return true
  } catch {
    return false
  }
}
