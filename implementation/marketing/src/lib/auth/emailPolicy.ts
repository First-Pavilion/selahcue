/**
 * Client-side email check — a MIRROR of the server's rule, not a looser approximation.
 *
 * The API's `_require_valid_email` (`services.py:488`) normalises with
 * `(raw or "").strip().lower()` and then calls Django's `validate_email`, raising
 * `VALIDATION_FAILED` — the same code every token failure raises — for anything it
 * refuses. The client cannot tell those apart, so an address this module lets through and
 * the server rejects surfaces as an error the page attributes to the wrong thing.
 *
 * WHY THIS IS NO LONGER "DELIBERATELY PERMISSIVE"
 * ----------------------------------------------
 * It used to be `/\S+@\S+\.\S+/`, with a header explaining that an over-strict client rule
 * would lock real customers out. That reasoning is sound and it is preserved below — what
 * was wrong was the conclusion, because permissive is not the safe direction here, it is
 * only a different way to be wrong. Cody measured it on PR #17 against Django 6.1's real
 * validator:
 *
 *     a@b.c      a@b..com      a@-b.com      a@b-.com
 *
 * all four passed this module and were all rejected by the server. They are ordinary
 * typos — a truncated TLD, a double-tapped dot — not adversarial input. On `/signup` the
 * user got an unattributed banner with no field-level error pointing at the address. On
 * `/forgot-password` it was worse: `VALIDATION_FAILED` mapped to "try again in a moment",
 * a TRANSIENT message for a PERMANENT error, so the user retries forever and no link ever
 * comes. That is the FR-552 dead end, reached through a typo.
 *
 * So the rule now mirrors `EmailValidator` rather than approximating it. "Mirrors" is a
 * claim, so it is tested as one: `tests/fixtures/email-mirror.json` holds the SERVER's
 * verdict for every fixture, `tests/emailPolicy.test.ts` asserts this module agrees with
 * that column on every row, and `scripts/service_text_reference.py` re-derives the column
 * from Django itself and fails on drift. One definition, two consumers — neither side can
 * quietly disagree with the other, which is the specific failure this PR's review round
 * was about.
 *
 * THE ORIGINAL WARNING STILL STANDS, and agreement is how it is honoured: plus-tags, long
 * modern TLDs, deep sub-domains, quoted local parts, `localhost` and IP literals are all
 * accepted here BECAUSE the server accepts them, and every one of them is pinned in the
 * fixture file. Being stricter than the server is still a lockout; the cure for it is
 * agreement, not looseness.
 *
 * There is NO existence check here and there must never be one. `requestPasswordReset`
 * and the resend mutation both return `accepted: true` regardless of whether the address
 * is registered — the no-enumeration contract. Any client-side "we don't recognise that
 * email" would hand back exactly the oracle the API was written to withhold. This module
 * decides SHAPE only and knows nothing about who has an account.
 *
 * Pure and dependency-free so it can be unit tested under `node --test`.
 */

import { serviceStrip } from './serviceText.ts'

export const EMAIL_REQUIRED = 'Enter your email address.'
export const EMAIL_INVALID = 'Enter a valid email address.'

/**
 * `EmailValidator.user_regex` — the dot-atom form, or an RFC quoted string.
 *
 * Transcribed from Django 6.1 `django/core/validators.py`. Built from a string of escapes
 * rather than written as a regex literal so the source carries no literal control bytes;
 * `redirect.ts` and `serviceText.ts` follow the same rule for the same reason.
 */
const USER = new RegExp(
  '^(?:' +
    // dot-atom
    "[-!#$%&'*+/=?^_`{}|~0-9A-Za-z]+(?:\\.[-!#$%&'*+/=?^_`{}|~0-9A-Za-z]+)*" +
    '|' +
    // quoted-string. The class is Django's `!#-\\[\\]-\\177` — every printable except
    // space, `"` and `\\` — plus the control characters it permits unescaped.
    '"(?:[\\u0001-\\u0008\\u000b\\u000c\\u000e-\\u001f!#-\\[\\]-\\u007f]' +
    '|\\\\[\\u0001-\\u0009\\u000b\\u000c\\u000e-\\u007f])*"' +
    ')$',
)

/**
 * `EmailValidator.domain_regex`.
 *
 * Every label starts and ends alphanumeric and is at most 63 characters; the final label
 * is at least two characters and may not END in a hyphen — though it MAY begin with one,
 * which Django allows and `a@b.-xy` is pinned in the fixtures to keep honest.
 *
 * Django spells the final label `[A-Z]{2,63}|[A-Z0-9-]{2,63}(?<!-)`. Written here as
 * `{1,62}` plus one alphanumeric instead: the same language, without depending on
 * lookbehind, which only reached Safari in 16.4.
 */
const DOMAIN = /^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9-]{1,62}[A-Za-z0-9]$/

/** `EmailValidator.literal_regex` — the SMTP 4.1.3 address-literal form. */
const LITERAL = /^\[(?:[A-Fa-f0-9:.]+|\[IPv6:[a-f0-9:.]+\])\]$/

/** `EmailValidator.domain_allowlist`. */
const DOMAIN_ALLOWLIST = ['localhost']

/**
 * `_normalize_email` (`services.py:484`): `(raw or "").strip().lower()`.
 *
 * `serviceStrip`, not `String.prototype.trim`: the two disagree on five characters Python
 * strips and one it does not, and a mirror that strips a different set validates a
 * different string than the server stores. See `serviceText.ts`.
 */
export function normalizeEmail(email: string): string {
  return serviceStrip(email).toLowerCase()
}

/**
 * True when Django's `validate_email` would accept this address, as the server sees it.
 *
 * Exported so the mirror can be checked directly against the server's verdict column
 * rather than only through `validateEmail`'s message strings.
 */
export function serverWouldAcceptEmail(email: string): boolean {
  const normalized = normalizeEmail(email)
  // Django splits on the LAST at-sign, which is what makes a quoted local part containing
  // one work at all.
  const at = normalized.lastIndexOf('@')
  if (at <= 0 || at === normalized.length - 1) return false

  const user = normalized.slice(0, at)
  const domain = normalized.slice(at + 1)
  if (!USER.test(user)) return false
  if (DOMAIN_ALLOWLIST.includes(domain)) return true
  return DOMAIN.test(domain) || LITERAL.test(domain)
}

/** Returns an error message, or `''` when the address is safe to submit. */
export function validateEmail(email: string): string {
  if (normalizeEmail(email) === '') return EMAIL_REQUIRED
  if (!serverWouldAcceptEmail(email)) return EMAIL_INVALID
  return ''
}
