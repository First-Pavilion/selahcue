/**
 * Client-side mirror of the API's password rule.
 *
 * THIS IS A CORRECTNESS REQUIREMENT, NOT VALIDATION POLISH.
 *
 * `confirm_password_reset` (`selahcue_api/apps/accounts/services.py:726`) calls
 * `_validate_password` at line 732 — BEFORE it looks up the token at line 733 — and both
 * the password check and every token check raise the same `VALIDATION_FAILED`. The client
 * cannot tell them apart.
 *
 * So without this module: a user types a 6-character password, the server rejects the
 * PASSWORD, the page can only read "VALIDATION_FAILED" and shows R4 — "this reset link
 * didn't work". The user's link is perfectly fine. They go and request a new one, type
 * the same short password, hit the same wall, and conclude the product is broken.
 *
 * With this module, no request outside the accepted range is ever sent, so a
 * `VALIDATION_FAILED` from that mutation can be honestly attributed to the token.
 *
 * Mirrors `_validate_password` (services.py:273-279) exactly:
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
 * This is not pedantry. JavaScript's `.length` counts surrogate pairs twice, so five
 * emoji measure 10 in JS and 5 in Python. Using `.length` would let a 5-emoji password
 * pass the client and be rejected by the server — reopening exactly the mis-attribution
 * this module exists to close, just for a narrower set of inputs.
 */
export function passwordLength(password: string): number {
  return [...password].length
}

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
  const length = passwordLength(password)

  if (length < MIN_PASSWORD_LENGTH) {
    // Covers the empty field too — the design uses one message for both.
    errors.password = PASSWORD_TOO_SHORT
  } else if (length > MAX_PASSWORD_LENGTH) {
    errors.password = PASSWORD_TOO_LONG
  } else if (password.trim() === '') {
    // Long enough, but `_validate_password`'s `not password.strip()` guard still rejects
    // it. A password of twelve spaces is the second way to be wrongly told your link is
    // dead. Note the guard is checked only AFTER length so that a short all-space entry
    // still gets the primary length message.
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
