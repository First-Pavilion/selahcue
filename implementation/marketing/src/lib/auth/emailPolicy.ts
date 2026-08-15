/**
 * Client-side email check for the "send me a fresh link" forms on /verify and /reset.
 *
 * Same reasoning as `passwordPolicy.ts`, one step milder. The API's `_require_valid_email`
 * raises `VALIDATION_FAILED` for a malformed address — the same code every token failure
 * raises — so submitting an obviously-broken address produces an error the page cannot
 * attribute correctly. Catching it here keeps the failure on the field where the user can
 * fix it.
 *
 * DELIBERATELY PERMISSIVE. This mirrors the regex already used in `SignInView.vue` rather
 * than trying to be clever: an over-strict client rule would reject valid addresses
 * (plus-tags, new TLDs, unicode local parts) and lock a real customer out of their own
 * recovery path. The server is the authority on what it will accept; this only catches
 * input that cannot possibly be an address.
 *
 * There is NO existence check here and there must never be one. `requestPasswordReset`
 * and the resend mutation both return `accepted: true` regardless of whether the address
 * is registered — the no-enumeration contract. Any client-side "we don't recognise that
 * email" would hand back exactly the oracle the API was written to withhold.
 *
 * Pure and dependency-free so it can be unit tested under `node --test`.
 */

export const EMAIL_REQUIRED = 'Enter your email address.'
export const EMAIL_INVALID = 'Enter a valid email address.'

/** Matches `SignInView.vue`'s existing check — kept identical so the two agree. */
const LOOSE_EMAIL = /\S+@\S+\.\S+/

/** Returns an error message, or `''` when the address is safe to submit. */
export function validateEmail(email: string): string {
  const trimmed = email.trim()
  if (trimmed === '') return EMAIL_REQUIRED
  if (!LOOSE_EMAIL.test(trimmed)) return EMAIL_INVALID
  return ''
}
