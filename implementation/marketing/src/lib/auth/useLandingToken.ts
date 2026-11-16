import { useRoute, useRouter } from 'vue-router'
import { landingTokenHandoff } from './landingTokenHandoff.ts'
import { readTokenParam } from './tokenParam.ts'

/**
 * Transfer the initial landing token after the router has committed its exact destination.
 * The initial URL was scrubbed before web history was created. The mounted view owns
 * the returned plain string for the duration of its existing auth flow.
 *
 * A later client-side token landing still reads its own query and replaces that entry.
 */
export function takeLandingToken(): string {
  const router = useRouter()
  const initialToken = landingTokenHandoff.take(router.currentRoute.value)
  if (initialToken) return initialToken

  const route = useRoute()
  // Captured BEFORE the replace, and by value — `route.query` is reactive and is about
  // to be emptied.
  const token = readTokenParam(route.query.token)

  if (token) {
    // Same route record, only the query changes, so the view is not re-created and
    // `onMounted` does not run twice. Errors are swallowed: failing to tidy the URL must
    // never take down the verification the user actually came here for.
    void router.replace({ path: route.path, query: {} }).catch(() => {})
  }

  return token
}
