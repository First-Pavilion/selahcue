import { onScopeDispose } from 'vue'
import { useRouter } from 'vue-router'

import { createSignOutFlow } from './signOutFlow.ts'
import { signOut } from './sessionStore.ts'

/**
 * The real sign-out, for a component: `sessionStore.signOut` for the revocation, the app's own
 * router for the navigation, and a full page load if the router cannot get there. The rules
 * about what it may tell the visitor are in `signOutFlow.ts`.
 *
 * Call it from `<script setup>` (it reads the router and registers an unmount hook). `landing`
 * is where a visitor who is now signed out should end up. When the component unmounts with a
 * request still in flight the flow stops acting for it (no navigation, no message) but the
 * request is not cancelled.
 *
 * `revoke` is a seam for tests (`tests/accountSignOut.test.ts` drives this module against a real
 * router with a held revocation). Components never pass it.
 *
 * THE TWO SIGN OUT BUTTONS DO NOT YET AGREE, AND THAT IS TEMPORARY. The owner's decision
 * (2026-10-05) is that both land on `/signin`. The Account page does. `Navbar.vue` still lands
 * on `/`, and it still carries its own copy of this flow (and of the two labels and the failure
 * message). It is shared chrome and the ticket that added this (17tnw2b2cbr) may not edit it:
 * 17tnw2b2ka8 moves the navbar onto this composable and onto `/signin`, and deletes the copy.
 * Until then `tests/accountSignOut.test.ts` pins the wording and pins the difference, so neither
 * can drift unnoticed.
 */
export function useSignOut(landing: string, revoke: () => Promise<void> = () => signOut()) {
  const router = useRouter()
  const flow = createSignOutFlow({
    landing,
    revoke,
    navigate: (to) => router.push(to),
    hardNavigate: (to) => window.location.assign(to),
  })
  onScopeDispose(() => flow.dispose())
  return flow
}
