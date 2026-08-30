/**
 * The customer-facing copy that MORE THAN ONE auth page says.
 *
 * MEDIUM-6 from the PR #17 review. Five views shipped byte-identical strings:
 * `RESEND_FAILED` in three files, `RESEND_RATE_LIMITED` in three, `RATE_LIMITED_TITLE` and
 * `_BODY` in two, and the "Only the newest link works" / "Didn't arrive?" pair in five.
 *
 * The reasoning against that is already written in the views themselves, and it is right —
 * `SignInView.vue` holds its rejection copy as a constant "so there is no seam for a
 * future edit to slip a second variant into", and `ForgotPasswordView.vue` says its
 * wording is `ResetView.vue`'s "so the two pages agree word for word". Both were applied
 * WITHIN a file and not ACROSS files, and five copies of a sentence is five seams.
 *
 * It matters more here than it would in most products. These pages exist to be
 * indistinguishable from one another in the ways that could reveal whether an address is
 * registered, so "the two pages agree word for word" is not a tidiness preference — it is
 * the property under test. A well-meant edit to one page's rate-limit copy that missed the
 * other would be a difference between two states the API answers identically.
 *
 * `tests/authCopy.test.ts` asserts no view re-declares any of these, so a sixth copy is a
 * failing test rather than a review catch.
 *
 * WHAT IS NOT HERE: anything only one page says. `SignInView`'s "Invalid email or
 * password" stays in `SignInView`, because moving single-use copy into a shared module
 * makes it harder to read, not easier to keep consistent.
 */

/** A resend or reset request that did not reach the server, or that it refused. */
export const RESEND_FAILED = "We couldn't send a link just now. Please try again in a moment."

/**
 * Says nothing about the address, deliberately.
 *
 * A limiter that spent its budget before looking the account up cannot be evidence the
 * account is real — and copy like "too many requests for this account" would say it is.
 * "Too many requests" describes what the caller did, not what the server knows.
 */
export const RESEND_RATE_LIMITED =
  'Too many requests for a new link. Wait a few minutes, then try again.'

/** The rate-limit banner on the two forms that submit credentials. */
export const RATE_LIMITED_TITLE = 'Too many attempts'
export const RATE_LIMITED_BODY = 'Wait a few minutes, then try again.'

/** The advice every "we sent you a link" state gives. */
export const CHECK_SPAM_NOTE =
  "Didn't arrive? Check your spam folder, then request another link."

/** And the warning that goes with it, because requesting a new link kills the old one. */
export const NEWEST_LINK_TITLE = 'Only the newest link works'
export const NEWEST_LINK_BODY =
  'Sending a new link cancels the previous one. Use the most recent email you received.'
