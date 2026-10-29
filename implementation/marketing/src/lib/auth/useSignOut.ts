import { onScopeDispose } from 'vue'
import { useRouter, type Router } from 'vue-router'

import { createSignOutFlow, createSignOutState, SIGN_OUT_LANDING, type SignOutState } from './signOutFlow.ts'
import { signOut } from './sessionStore.ts'

interface SignOutEntry {
  state: SignOutState
  consumers: number
}

// One operation for the app's controls, without leaking state between SSR apps. Keep an active
// operation across remounts, but expire settled feedback when no control can display it anymore.
const states = new WeakMap<Router, SignOutEntry>()

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
  const entry = states.get(router) ?? { state: createSignOutState(), consumers: 0 }
  states.set(router, entry)
  entry.consumers += 1

  function releaseIfUnused(): void {
    if (entry.consumers === 0 && !entry.state.pending.value && states.get(router) === entry) {
      states.delete(router)
    }
  }

  const flow = createSignOutFlow({
    landing,
    revoke,
    navigate: (to) => router.push(to),
    hardNavigate: (to) => window.location.assign(to),
  }, entry.state)
  onScopeDispose(() => {
    flow.dispose()
    entry.consumers -= 1
    releaseIfUnused()
  })
  async function run(): Promise<boolean> {
    try {
      return await flow.run()
    } finally {
      // A request may settle after the last scope left. Do not carry its now-invisible
      // feedback into a later sign-in; an existing/remounted consumer still retains it.
      releaseIfUnused()
    }
  }
  return { ...flow, run }
}
