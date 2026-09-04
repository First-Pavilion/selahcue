/**
 * Client-side mirror of the API's password rule.
 *
 * THIS IS A CORRECTNESS REQUIREMENT, NOT VALIDATION POLISH.
 *
 * THE ORDERING THIS HEADER USED TO STATE IS NO LONGER TRUE, and correcting it is the
 * point. It read: "`confirm_password_reset` (`services.py:726`) calls `_validate_password`
 * at line 732 — BEFORE it looks up the token at line 733 — and both raise the same
 * `VALIDATION_FAILED`, so the client cannot tell them apart." FR-551 (PR #16, merged into
 * this branch at `33237c0`) reversed exactly that, and this is the third copy of the claim
 * this branch has had to correct after `account.ts` and `ResetView.vue`. On the merged
 * tree the function validates the TOKEN first — fingerprint, purpose, consumed, expiry,
 * `services.py:1185`-`1206`, all collapsed to one `VALIDATION_FAILED` — and only then the
 * password, at `services.py:1245`, where it raises the DISTINCT `PASSWORD_INVALID`.
 *
 * The module is not thereby redundant, and its reasons never depended on the ordering:
 *
 *   - `PASSWORD_INVALID` deliberately carries NO policy detail (`graphql/errors.py:26-28`),
 *     so the server can say "that password was refused" and this module is the only thing
 *     able to say WHICH rule refused it and what to type instead.
 *   - A password this client can reject costs no round trip and no rate-limit slot.
 *   - `register_customer_user` still collapses a bad password into the undifferentiated
 *     `VALIDATION_FAILED` — `_validate_password`'s DEFAULT code — so on `/signup` the
 *     original mis-attribution is live and this module is the whole of the defence.
 *
 * What is gone is the claim that a short password on `/reset` reads as a dead link. It no
 * longer does: `ResetView.vue` branches on `PASSWORD_INVALID` and says the link still
 * works. See `lib/api/account.ts` for the caller contract.
 *
 * Mirrors `_validate_password` (services.py, `MIN_PASSWORD_LENGTH`..`MAX_PASSWORD_LENGTH`)
 * exactly:
 *   - reject a password that is empty or ONLY whitespace (`not password.strip()`)
 *   - reject length outside MIN..MAX inclusive (`MIN <= len(password) <= MAX`)
 *   - nothing else — the rule is LENGTH ONLY. There is no complexity requirement.
 *     (`MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §3c/§4d says "8 characters + one uppercase
 *     + one number". That doc predates the shipped API and is wrong on both counts;
 *     `AUTH-LANDING-PAGES-HANDOFF.md` §11.2 records the correction.)
 *
 * Pure and dependency-free on purpose: no Vue, no DOM, no fetch — so it can be unit
 * tested directly under `node --test`.
 */

import { codePointLength, serviceStrip } from './serviceText.ts'

/** `ACCOUNT_MIN_PASSWORD_LENGTH` (settings.py:273). */
export const MIN_PASSWORD_LENGTH = 10

/** `MAX_PASSWORD_LENGTH` (services.py:209). */
export const MAX_PASSWORD_LENGTH = 200

export const PASSWORD_TOO_SHORT = `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
export const PASSWORD_TOO_LONG = `Password must be ${MAX_PASSWORD_LENGTH} characters or fewer.`
export const PASSWORD_ONLY_SPACES = 'Password must contain more than spaces.'
export const PASSWORDS_DO_NOT_MATCH = 'Both passwords must match.'

/**
 * Count characters the way Python's `len()` does — by code point, not UTF-16 code unit.
 *
 * RE-EXPORTED, NOT DEFINED HERE. LOW-12 (Cody): this was called `passwordLength`, and
 * `signupPolicy.validateSignup` called it on org names, display names and email addresses
 * against three Django `max_length`s that have nothing to do with passwords. The behaviour
 * was always right; the NAME sent a reader checking `CustomerOrg.name` into a password
 * module. The definition now lives in `serviceText.ts` as `codePointLength`, beside the
 * other places a JavaScript builtin and its Python twin disagree, and this line exists so
 * a password caller can still get its length rule from its own policy module.
 */
export { codePointLength } from './serviceText.ts'

export interface NewPasswordErrors {
  password?: string
  confirmPassword?: string
}

/**
 * Validate a new-password pair for `/reset` (design states R1 → R2).
 *
 * Returns an empty object when the pair is safe to submit. Both fields are reported at
 * once because R2 shows both errors together.
 */
export function validateNewPassword(password: string, confirmPassword: string): NewPasswordErrors {
  const errors: NewPasswordErrors = {}
  const length = codePointLength(password)

  if (length < MIN_PASSWORD_LENGTH) {
    // Covers the empty field too — the design uses one message for both.
    errors.password = PASSWORD_TOO_SHORT
  } else if (length > MAX_PASSWORD_LENGTH) {
    errors.password = PASSWORD_TOO_LONG
  } else if (serviceStrip(password) === '') {
    // Long enough, but `_validate_password`'s `not password.strip()` guard still rejects
    // it. A password of twelve spaces is the second way to be wrongly told your link is
    // dead. Note the guard is checked only AFTER length so that a short all-space entry
    // still gets the primary length message.
    //
    // `serviceStrip`, not `.trim()` (Sana, PR #17): a password of twelve U+001C passed
    // this check and failed `not password.strip()` on the server, which is the same
    // mis-attribution one character class over. See `serviceText.ts`.
    errors.password = PASSWORD_ONLY_SPACES
  }

  if (password !== confirmPassword) {
    errors.confirmPassword = PASSWORDS_DO_NOT_MATCH
  }

  return errors
}

/** True when `validateNewPassword` found nothing — i.e. the mutation may be called. */
export function isSubmittableNewPassword(password: string, confirmPassword: string): boolean {
  return Object.keys(validateNewPassword(password, confirmPassword)).length === 0
}
