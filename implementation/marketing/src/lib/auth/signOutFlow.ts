/**
 * What pressing "Sign out" does, and what it is allowed to tell the visitor.
 *
 * Kept free of the router, `window` and the network on purpose: all three arrive as `deps`, so
 * `tests/accountSignOut.test.ts` can drive every branch under `node --test`. `useSignOut.ts`
 * is the thin wiring that gives it the real ones.
 *
 * THE HONEST MODEL (the same one `Navbar.vue` documents, and `sessionStore.signOut` enforces)
 * -----------------------------------------------------------------------------------------
 * The session cookie is HttpOnly. JavaScript cannot delete it; only the server can, by
 * answering the `logout` mutation. So there is no "clear it locally anyway" fallback:
 *
 *   - `revoke` REJECTS when the session was not revoked, and then the visitor is told so and
 *     stays where they are. Painting "signed out" over a browser that still carries a working
 *     credential is the most consequential lie this UI could tell, on what is in this
 *     product often a shared church-office PC.
 *   - A failed NAVIGATION after a successful revocation is NOT a failed sign-out. They are
 *     signed out; the next page just did not load. Reporting it as "We couldn't sign you
 *     out" would tell someone their session is still live when it is not, so they stay
 *     logged in on purpose (PR #17, HIGH-1). The two calls therefore never share a `try`.
 *
 * `pending` holds from the press until the NEXT PAGE has loaded, not merely until the server
 * answered. `/signin` is a lazy route: on a slow connection the session is already revoked and
 * this page is still on screen, and a button that came back to life in that gap would send a
 * second request for a session that no longer exists.
 */

import { ref } from 'vue'

/** The idle label. `Navbar.vue` says the same word for word: `tests/accountSignOut.test.ts` pins it. */
export const SIGN_OUT_LABEL = 'Sign out'
export const SIGN_OUT_PENDING_LABEL = 'Signing out…'

/** What a sign-out that did not complete says. Also pinned against `Navbar.vue`'s copy. */
export const SIGN_OUT_FAILED = "We couldn't sign you out. Check your connection and try again."

export interface SignOutDeps {
  /** Revoke the session on the server. Rejects when it was NOT revoked. */
  revoke: () => Promise<void>
  /** In-app navigation. May reject: a lazy chunk a deploy removed, a guard that threw. */
  navigate: (to: string) => Promise<unknown>
  /** A full document load, the fallback for a navigation that rejected. */
  hardNavigate: (to: string) => void
  /** Where a visitor who is now signed out ends up. */
  landing: string
}

export function createSignOutFlow(deps: SignOutDeps) {
  const pending = ref(false)
  /** Empty when there is nothing to report. Rendered where it is announced, because it is a failed action. */
  const error = ref('')

  /** Resolves true when the visitor is signed out, false when they are not (or a press was ignored). */
  async function run(): Promise<boolean> {
    if (pending.value) return false
    pending.value = true
    error.value = ''

    try {
      await deps.revoke()
    } catch {
      error.value = SIGN_OUT_FAILED
      pending.value = false
      return false
    }

    // ---- the session is GONE. Nothing below may suggest otherwise. ----
    try {
      await deps.navigate(deps.landing)
    } catch {
      // The revocation succeeded and only the navigation failed. A full document load is both
      // the honest outcome (they end up signed out, on the landing page) and the actual remedy
      // for the usual cause: a running page pointing at chunks a deploy has already removed.
      deps.hardNavigate(deps.landing)
    }
    pending.value = false
    return true
  }

  return { pending, error, run }
}
