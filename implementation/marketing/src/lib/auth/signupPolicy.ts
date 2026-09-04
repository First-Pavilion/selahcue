/**
 * Client-side mirror of everything `register_customer_user` checks before it does any work.
 *
 * SAME CORRECTNESS REQUIREMENT AS `passwordPolicy.ts`, ONE FIELD WIDER.
 *
 * `register_customer_user` (`apps/accounts/services.py`) validates, in order: the
 * idempotency key, the email, the password, the org name and the country — and raises
 * the SAME `VALIDATION_FAILED` for every one of them. It then checks whether the address
 * is already registered and returns `accepted: true` either way.
 *
 * So an unvalidated submit puts the UI in an impossible position. It receives one
 * undifferentiated `VALIDATION_FAILED` and cannot tell a 9-character password from a
 * blank org name from a missing country. And the guess it must NEVER make is the one a
 * developer reaches for first — "the email must be taken" — because that is precisely
 * the enumeration oracle the service was written to withhold, and `register_customer_user`
 * does not raise for a taken address at all.
 *
 * With this module, no request that could fail on a field is ever sent, so any
 * `VALIDATION_FAILED` that does come back is a genuine client/server disagreement and is
 * reported as one, honestly and without speculating about the address.
 *
 * Bounds are read off the models, not guessed:
 *   - org name        `CustomerOrg.name`         max_length=200
 *   - display name    `CustomerUser.display_name` max_length=200
 *   - country         `CustomerOrg.country`       max_length=2, and `len(country) != 2` is an explicit reject
 *   - timezone        `CustomerOrg.timezone`      max_length=64
 *   - email           `CustomerUser.email` and `CustomerOrg.primary_contact_email`, both
 *                     bare `models.EmailField()`, whose default max_length is 254
 *   - password        10-200, length only (`passwordPolicy.ts`)
 *
 * Pure and dependency-free so it can be unit tested under `node --test`.
 */

import { COUNTRY_CODES } from './countries.ts'
import { normalizeEmail, validateEmail } from './emailPolicy.ts'
import { validateNewPassword, type NewPasswordErrors } from './passwordPolicy.ts'
import { codePointLength, serviceCollapse } from './serviceText.ts'

/** `CustomerOrg.name` max_length. */
export const MAX_ORG_NAME_LENGTH = 200
/** `CustomerUser.display_name` max_length. */
export const MAX_DISPLAY_NAME_LENGTH = 200
/** `CustomerOrg.timezone` max_length. */
export const MAX_TIMEZONE_LENGTH = 64

/**
 * `EmailField()`'s default max_length — a SIGNUP-ONLY ceiling, and the reason this constant
 * lives here and not in `emailPolicy.ts`.
 *
 * `emailPolicy.ts` mirrors `validate_email`, which caps an address at 320 characters
 * (RFC 3696). That is the whole rule on sign-in, forgot-password and resend, and its
 * 320-character fixture row is correct.
 *
 * Signup writes the address as well as validating it. `register_customer_user` builds a
 * `CustomerOrg` with `primary_contact_email=email` and a `CustomerUser` with `email=email`,
 * both bare `models.EmailField()` — default `max_length=254` — and then calls `full_clean`
 * on each inside the same `transaction.atomic()`. Measured against the pinned Django
 * 6.1.1: `EmailField().clean` accepts a 254-character address and refuses 255 with
 * "Ensure this value has at most 254 characters".
 *
 * Without this check, an address of 255-320 characters passes every client rule, reaches
 * the server, fails `full_clean`, and comes back as the same undifferentiated
 * `VALIDATION_FAILED` every other field raises — which on `/signup` is an unattributed
 * banner and on the reset surfaces is the FR-552 dead end. It is the exact failure
 * `emailPolicy.ts`'s header describes, arriving through the one rule that module does not
 * mirror.
 */
export const MAX_SIGNUP_EMAIL_LENGTH = 254

/** `validate_idempotency_key` (`graphql/context.py`), character for character. */
export const IDEMPOTENCY_KEY_PATTERN = /^[A-Za-z0-9._:-]{12,128}$/

export const ORG_NAME_REQUIRED = 'Enter your church or organisation name.'
export const ORG_NAME_TOO_LONG = `Name must be ${MAX_ORG_NAME_LENGTH} characters or fewer.`
export const DISPLAY_NAME_TOO_LONG = `Name must be ${MAX_DISPLAY_NAME_LENGTH} characters or fewer.`
export const EMAIL_TOO_LONG = `Email address must be ${MAX_SIGNUP_EMAIL_LENGTH} characters or fewer.`
export const COUNTRY_REQUIRED = 'Select your country.'
export const TERMS_REQUIRED = 'Accept the terms to continue.'

/**
 * Collapse whitespace exactly as the service does.
 *
 * `" ".join(value.strip().split())` — so `"  Grace   Community  "` is `"Grace Community"`,
 * and a name of only whitespace is empty. The length check below runs on the COLLAPSED
 * value because that is what the server stores and validates; measuring the raw input
 * would reject a name the server would have accepted.
 *
 * "Exactly as the service does" was FALSE until PR #17. This used `value.trim()` and
 * `/\s+/`, and JavaScript's whitespace set is not Python's: five characters Python strips
 * that JavaScript does not (U+001C..U+001F, U+0085) and one the other way (U+FEFF). An
 * org name of three U+001C survived this collapse, passed `ORG_NAME_REQUIRED`, and
 * collapsed to `""` on the server — the undifferentiated `VALIDATION_FAILED` this whole
 * module exists to prevent, produced by the module itself. `serviceText.ts` now holds the
 * one definition of the set; this function is a thin caller of it rather than a second
 * copy of the rule.
 */
export function collapseWhitespace(value: string): string {
  return serviceCollapse(value)
}

/**
 * A fresh idempotency key for one signup ATTEMPT.
 *
 * Call once per attempt and REUSE it for every retry of that attempt. That is the whole
 * point of the key: after a timeout the client cannot know whether the first request
 * landed, and `register_customer_user` namespaces its guard per email fingerprint so a
 * repeat carrying the same key converges on the row that already exists. Minting a new
 * key on retry throws that away exactly when it is needed.
 *
 * `crypto.randomUUID()` produces 36 characters of `[0-9a-f-]`, comfortably inside
 * `^[A-Za-z0-9._:-]{12,128}$`. The `getRandomValues` fallback covers non-secure contexts
 * and older engines where `randomUUID` is absent. `Math.random` is deliberately NOT a
 * fallback: a colliding key would alias two different churches' signups onto one another.
 */
export function newIdempotencyKey(): string {
  const webcrypto = globalThis.crypto
  let candidate = ''

  if (typeof webcrypto?.randomUUID === 'function') {
    candidate = webcrypto.randomUUID()
  } else if (typeof webcrypto?.getRandomValues === 'function') {
    const bytes = new Uint8Array(16)
    webcrypto.getRandomValues(bytes)
    candidate = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  }

  // A generated key that the API would reject is worse than no key: it fails the whole
  // signup on a field the user cannot see, let alone fix. Verified against the real
  // pattern rather than assumed to match it.
  if (!IDEMPOTENCY_KEY_PATTERN.test(candidate)) {
    throw new Error('Could not generate a signup key: this browser has no secure random source.')
  }
  return candidate
}

/**
 * The visitor's IANA time zone, or `UTC`.
 *
 * Sent rather than left blank so a new org's timers and schedules are right from the
 * first login instead of being silently Universal Time. Anything unparseable, absent or
 * over the column width falls back rather than failing the signup.
 */
export function detectTimezone(): string {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (typeof zone === 'string' && zone !== '' && zone.length <= MAX_TIMEZONE_LENGTH) return zone
  } catch {
    // No Intl, or a locked-down environment. UTC is the server's own default.
  }
  return 'UTC'
}

export interface SignupFields {
  orgName: string
  displayName: string
  email: string
  password: string
  confirmPassword: string
  country: string
  agreeTerms: boolean
}

export interface SignupErrors extends NewPasswordErrors {
  orgName?: string
  displayName?: string
  email?: string
  country?: string
  terms?: string
}

/**
 * Validate the whole create-account form. Empty object means it is safe to submit.
 *
 * Every field is reported at once rather than stopping at the first, because the form
 * shows them together and walking a user down a form one error at a time is the
 * slowest possible way to fill it in.
 *
 * Note what is NOT here and never may be: any check of whether the address is already
 * registered. There is no API that would answer it, and building one — client-side or
 * server-side — is the oracle 86ak120kw exists to keep out of this form.
 */
export function validateSignup(fields: SignupFields): SignupErrors {
  const errors: SignupErrors = validateNewPassword(fields.password, fields.confirmPassword)

  const orgName = collapseWhitespace(fields.orgName)
  if (orgName === '') {
    errors.orgName = ORG_NAME_REQUIRED
  } else if (codePointLength(orgName) > MAX_ORG_NAME_LENGTH) {
    // Code points, not UTF-16 units — Django's max_length counts characters the way
    // Python does, so a name of emoji or non-BMP script measures double in JS `.length`
    // and would be rejected here while the server would have accepted it.
    errors.orgName = ORG_NAME_TOO_LONG
  }

  const displayName = collapseWhitespace(fields.displayName)
  if (codePointLength(displayName) > MAX_DISPLAY_NAME_LENGTH) {
    errors.displayName = DISPLAY_NAME_TOO_LONG
  }

  const email = validateEmail(fields.email)
  if (email) {
    errors.email = email
  } else if (codePointLength(normalizeEmail(fields.email)) > MAX_SIGNUP_EMAIL_LENGTH) {
    // The shape is fine and `validate_email` would take it — it is the model field that
    // will not. Measured on the NORMALISED address, because the normalised string is what
    // `register_customer_user` assigns to the field and `full_clean` then measures; and in
    // code points, because Django's `max_length` counts characters the way Python does.
    errors.email = EMAIL_TOO_LONG
  }

  // Trusts the select, but does not assume it: a country the API would reject is another
  // unattributable VALIDATION_FAILED.
  const country = fields.country.trim().toUpperCase()
  if (country.length !== 2 || !COUNTRY_CODES.includes(country)) {
    errors.country = COUNTRY_REQUIRED
  }

  if (!fields.agreeTerms) {
    // Reported on submit rather than by disabling the button. A disabled control gives a
    // keyboard user nothing to act on and no reason for the dead end — AUTH handoff A12
    // specifies this message for exactly that reason.
    errors.terms = TERMS_REQUIRED
  }

  return errors
}

/** True when `validateSignup` found nothing — i.e. the mutation may be called. */
export function isSubmittableSignup(fields: SignupFields): boolean {
  return Object.keys(validateSignup(fields)).length === 0
}
