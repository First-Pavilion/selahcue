/**
 * What pressing "Sign out" does, and what it is allowed to tell the visitor.
 *
 * Kept free of the router, `window` and the network on purpose: all three arrive as `deps`, so
 * `tests/accountSignOut.test.ts` can drive every branch under `node --test`. `useSignOut.ts`
 * is the thin wiring that gives it the real ones.
 *
 * THE HONEST MODEL (the one `sessionStore.signOut` enforces)
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

import { ref, type Ref } from 'vue'

/** Shared wording and the owner-approved destination for both controls. */
export const SIGN_OUT_LABEL = 'Sign out'
export const SIGN_OUT_PENDING_LABEL = 'Signing out…'
export const SIGN_OUT_LANDING = '/signin'

/** What a sign-out that did not complete says. */
export const SIGN_OUT_FAILED = "We couldn't sign you out. Check your connection and try again."

export interface SignOutState {
  pending: Ref<boolean>
  error: Ref<string>
}

export function createSignOutState(): SignOutState {
  return { pending: ref(false), error: ref('') }
}

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

export function createSignOutFlow(deps: SignOutDeps, state: SignOutState = createSignOutState()) {
  const { pending, error } = state
  let disposed = false

  /**
   * The page that asked has gone (the visitor clicked away mid-request, and the component
   * unmounted). Called by `useSignOut` when its scope stops.
   *
   * It stops the flow ACTING, nothing more. The request is not cancelled: a logout that may
   * already have landed must not be abandoned, and `revoke` clears the session hint itself when
   * the server says yes. What a late reply must not do is act for a page that is no longer
   * there: a success pulling the visitor off the page they chose. The operation's state still
   * settles: surviving shared chrome reports a late failure and allows a retry.
   */
  function dispose(): void {
    disposed = true
  }

  /** Resolves true when the visitor is signed out, false when they are not (or a press was ignored). */
  async function run(): Promise<boolean> {
    if (disposed || pending.value) return false
    pending.value = true
    error.value = ''

    try {
      try {
        await deps.revoke()
      } catch {
        error.value = SIGN_OUT_FAILED
        return false
      }

      // ---- the session is GONE. Nothing below may suggest otherwise. ----
      if (disposed) return true
      try {
        await deps.navigate(deps.landing)
      } catch {
        // A lazy chunk may have disappeared in a deploy. A caller that has since unmounted
        // must not pull the visitor away with a late full-page navigation either.
        if (!disposed) deps.hardNavigate(deps.landing)
      }
      return true
    } finally {
      // Shared chrome survives the initiating page. Never strand its controls on pending.
      pending.value = false
    }
  }

  return { pending, error, run, dispose }
}
