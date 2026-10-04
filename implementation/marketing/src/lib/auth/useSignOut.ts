import { useRouter } from 'vue-router'

import { createSignOutFlow } from './signOutFlow.ts'
import { signOut } from './sessionStore.ts'

/**
 * The real sign-out, for a component: `sessionStore.signOut` for the revocation, the app's own
 * router for the navigation, and a full page load if the router cannot get there. The rules
 * about what it may tell the visitor are in `signOutFlow.ts`.
 *
 * Call it from `<script setup>` (it reads the router). `landing` is where a visitor who is now
 * signed out should end up: the Account page sends them to `/signin`.
 *
 * `Navbar.vue` still carries its own copy of this handler. It is shared chrome and out of scope
 * for the ticket that added this (17tnw2b2cbr); adopting this composable there is the
 * follow-up, and `tests/accountSignOut.test.ts` fails if the two copies' wording drifts apart
 * in the meantime.
 */
export function useSignOut(landing: string) {
  const router = useRouter()
  return createSignOutFlow({
    landing,
    revoke: () => signOut(),
    navigate: (to) => router.push(to),
    hardNavigate: (to) => window.location.assign(to),
  })
}
