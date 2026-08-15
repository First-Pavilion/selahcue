import { useRoute, useRouter } from 'vue-router'
import { readTokenParam } from './tokenParam.ts'

/**
 * Read the landing token out of the URL and immediately take it back out of the URL.
 *
 * "Take", not "read": the token is captured into a plain (NON-reactive) local and the
 * address bar is rewritten in the same tick. That matters for four separate leaks, and
 * one call closes all of them:
 *
 *   - BROWSER HISTORY — `router.replace` overwrites the current entry rather than
 *     pushing a new one, so the token-bearing URL does not survive in history, in the
 *     back button, or in the browser's synced-history/autocomplete store.
 *   - REFERER — any later outbound click ("Contact support", "Back to Sign in") would
 *     otherwise carry the whole token-bearing URL to the destination. `nginx.conf` also
 *     sets `strict-origin-when-cross-origin`, but scrubbing means there is nothing to
 *     leak even if a future deployment loosens that header.
 *   - ANALYTICS — the SPA has none today, but a page-view tag added later reads
 *     `location.href` at load. After this runs there is no token in it.
 *   - SHOULDER/SCREEN-SHARE — these pages are opened on a projector-attached machine in
 *     a church office more often than anywhere else.
 *
 * The return value is deliberately a plain string, not a ref: the caller owns the only
 * copy, and it must never be written back into route state or into a log line.
 */
export function takeLandingToken(): string {
  const route = useRoute()
  const router = useRouter()

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
