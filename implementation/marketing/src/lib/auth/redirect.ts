/**
 * Sanitising the `?next=` that the route guard round-trips through sign-in.
 *
 * A guard that bounces someone to `/signin?next=/account` and then sends them wherever
 * `next` says is an OPEN REDIRECT if `next` is not checked. The attack is ordinary and
 * effective: mail a church admin `…/signin?next=https://selahcue-billing.example/pay`,
 * they sign in on the real SelahCue with the real padlock, and land on a page they have
 * every reason to trust. Nothing about the sign-in was fake, which is what makes it work.
 *
 * So the rule is a whitelist, not a blacklist: a same-site ABSOLUTE PATH and nothing
 * else. No scheme, no host, no protocol-relative form. Anything that does not obviously
 * qualify falls back to the caller's default, because the cost of a wrong fallback is
 * one extra click and the cost of a wrong redirect is a phished credential.
 *
 * Pure and dependency-free so it can be unit tested under `node --test`.
 */

import type { QueryTokenValue } from './tokenParam.ts'

/**
 * Auth routes are refused as destinations.
 *
 * Not for safety — for termination. `/signin?next=/signin` would sign someone in and
 * return them to the sign-in page, where the guard is not involved and nothing tells them
 * why they are back. A loop with no error message is the hardest kind to report.
 *
 * Stored lowercase and without a trailing slash, because that is the form `matchPath`
 * normalises a candidate into. See it for why.
 */
const NON_DESTINATIONS = ['/signin', '/signup', '/forgot-password', '/verify', '/reset']

/**
 * Normalise a path the way vue-router MATCHES one.
 *
 * MEDIUM-3 (Cody). The comparison used to be case-sensitive and exact, and vue-router is
 * neither. Verified against the router vendored in this branch:
 *
 *     router.resolve('/SIGNIN')  -> matched: 1  name: signin
 *     router.resolve('/signin/') -> matched: 1  name: signin
 *
 * So `?next=/signin/` produced exactly the loop this module documents itself as existing
 * to prevent — sign in, land back on the sign-in page, with nothing saying why. And
 * `?next=/reset/` was worse: it dropped a freshly-signed-in user onto the "this link
 * didn't work" state with no token in the URL.
 *
 * Only the COMPARISON is normalised. The value handed back to the caller is the original,
 * so a destination that legitimately depends on case is not rewritten on the way through.
 *
 * EXPORTED FOR THE CONTROL, and LOW-10 (Quinn) is why. Because `safeNextPath` returns the
 * untouched candidate, this function is observable through exactly one channel — whether
 * the normalised path lands in `NON_DESTINATIONS` — and only the CASE-FOLD half of it
 * reaches that channel. Quinn mutated `lowered.length > 1` to `> 0`, which turns `'/'`
 * into `''`, and all three gates stayed green: `''` is not a non-destination either, so
 * the verdict never moved. The test that names the trailing-slash strip
 * (`safeNextPath('/', FALLBACK) === '/'`) holds for ANY implementation of this function,
 * because the value it inspects never passed through it. Cody's mutation of the other half
 * (`.toLowerCase()` removed) DID go red, so this was a half-live control, not a dead one.
 *
 * Exporting it is the cheapest way to make the expression the control names the expression
 * the control reads. It is not part of the module's contract with the app — `safeNextPath`
 * is the only thing any caller in `src/` uses — and `tests/redirect.test.ts` says so.
 */
export function matchPath(path: string): string {
  const lowered = path.toLowerCase()
  // One trailing slash, and only when something remains — `'/'` must stay `'/'`.
  return lowered.length > 1 && lowered.endsWith('/') ? lowered.slice(0, -1) : lowered
}

/**
 * C0 controls and DEL.
 *
 * Tested by code point rather than with a regex character range, so the source carries no
 * literal control bytes — a file that does is one careless copy-paste away from a range
 * that silently means something else.
 */
function hasControlCharacter(value: string): boolean {
  for (const character of value) {
    const code = character.codePointAt(0) ?? 0
    if (code < 0x20 || code === 0x7f) return true
  }
  return false
}

/**
 * Return `value` if it is a safe same-site path, otherwise `fallback`.
 *
 * Refused, in order: non-strings; anything not starting with `/`; `//host`, which
 * browsers resolve as a protocol-relative URL to ANOTHER ORIGIN despite the leading
 * slash; any backslash at all, since several parsers normalise it to `/` and `/\host` is
 * the same attack wearing a different hat; any control character, which can truncate or
 * split a URL downstream; and the auth routes themselves.
 */
export function safeNextPath(value: QueryTokenValue, fallback: string): string {
  const raw = Array.isArray(value) ? value[0] : value
  if (typeof raw !== 'string') return fallback

  const candidate = raw.trim()
  if (candidate === '') return fallback

  // The single most important check. `//evil.example/x` is a URL to another origin.
  if (!candidate.startsWith('/')) return fallback
  if (candidate.startsWith('//')) return fallback
  if (candidate.includes('\\')) return fallback
  if (hasControlCharacter(candidate)) return fallback

  const path = matchPath(candidate.split(/[?#]/)[0])
  if (NON_DESTINATIONS.includes(path)) return fallback

  return candidate
}
