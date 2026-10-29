import { onScopeDispose } from 'vue'
import { useRouter, type Router } from 'vue-router'

import { createSignOutFlow, createSignOutState, SIGN_OUT_LANDING, type SignOutState } from './signOutFlow.ts'
import { signOut } from './sessionStore.ts'

// One operation for the app's controls, without leaking pending/error state between SSR apps.
// The router owns the state lifetime; each caller retains its own disposal/navigation lifetime.
const states = new WeakMap<Router, SignOutState>()

/**
 * The real sign-out, for a component: `sessionStore.signOut` for the revocation, the app's own
 * router for navigation, and a full page load if the router cannot get there. All consumers of
 * the same router share pending and failure feedback. The rules live in `signOutFlow.ts`.
 *
 * Call it from `<script setup>` (it reads the router and registers an unmount hook). `landing`
 * is where a visitor who is now signed out should end up. When the component unmounts with a
 * request still in flight its controller stops navigating, but the request is not cancelled
 * and surviving chrome still receives the operation's result.
 *
 * `revoke` is a seam for tests (`tests/accountSignOut.test.ts` drives this module against a real
 * router with a held revocation). Components never pass it.
 *
 * Both real controls use the owner-approved default `/signin`. Tests may override revocation
 * to hold a real router transition without making a network request.
 */
export function useSignOut(landing = SIGN_OUT_LANDING, revoke: () => Promise<void> = () => signOut()) {
  const router = useRouter()
  let state = states.get(router)
  if (!state) {
    state = createSignOutState()
    states.set(router, state)
  }
  const flow = createSignOutFlow({
    landing,
    revoke,
    navigate: (to) => router.push(to),
    hardNavigate: (to) => window.location.assign(to),
  }, state)
  onScopeDispose(() => flow.dispose())
  return flow
}
