/**
 * Reading — and then getting rid of — the `?token=` on `/verify` and `/reset`.
 *
 * These URLs carry a single-use credential in the query string, which is the one place a
 * secret is hardest to contain: it lands in browser history, in the `Referer` of every
 * outbound link, in any analytics page-view, and in anything that later serialises
 * `location.href`. The emails already shipped this way (`apps/accounts/tasks.py:55,64`),
 * so the link shape is not ours to change — but how long the token stays in the address
 * bar is.
 *
 * Pure and dependency-free so it can be unit tested under `node --test`.
 */

/** What vue-router hands back for `route.query.token`. */
export type QueryTokenValue = string | null | (string | null)[] | undefined

/**
 * Normalise `route.query.token` to a plain string.
 *
 * `?token=a&token=b` gives vue-router an array; take the first entry rather than
 * stringifying the array into `"a,b"`, which would send garbage to the API.
 * Trimmed to match the API's own `(raw_token or "").strip()`.
 */
export function readTokenParam(value: QueryTokenValue): string {
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' ? raw.trim() : ''
}

function decodeQueryPart(part: string): string {
  const normalized = part.replace(/\+/g, ' ')
  try {
    return decodeURIComponent(normalized)
  } catch {
    // Classic Router keeps the whole segment when percent decoding fails.
    return normalized
  }
}

/** Read the first token field before Router parses it. Undefined means the field was absent. */
export function readTokenFromSearch(search: string): string | undefined {
  const query = search.startsWith('?') ? search.slice(1) : search
  for (const entry of query.split('&')) {
    const equals = entry.indexOf('=')
    const name = equals < 0 ? entry : entry.slice(0, equals)
    if (decodeQueryPart(name) === 'token') {
      return readTokenParam(equals < 0 ? null : decodeQueryPart(entry.slice(equals + 1)))
    }
  }
  return undefined
}

/**
 * True when the page was opened without a usable token — a bookmark, a stripped query,
 * a hand-typed URL, or a link a mail client mangled.
 *
 * This is the ONE token failure the client can distinguish on its own, which is why it
 * gets its own designed state (V6) instead of the merged failure state: it is not an
 * error, and showing a red "this link didn't work" for it would be a lie.
 */
export function isMissingToken(value: QueryTokenValue): boolean {
  return readTokenParam(value) === ''
}
