/**
 * The one email rule the Contact form applies (ClickUp 17tnw2b2cez, review round 2, Vera 1).
 *
 * The rule is the one the form always had: an `@` with something before it and a dot with something on each
 * side after it. It is deliberately permissive (it accepts `x y@z.com`): the Contact form only needs an
 * address a person could answer, and the stricter shape the sign-in pages use is `lib/auth/emailPolicy.ts`.
 *
 * WHY THERE IS A LENGTH CAP IN FRONT OF THE PATTERN. `/\S+@\S+\.\S+/` has no anchors and its runs of `\S+`
 * overlap, so on a long value with no spaces and many `@` signs it backtracks far more than linearly: measured
 * in Node on repeated `a@`, 254 characters take about 9 ms, 1,000 about 120 ms, 2,000 about 0.75 s and 3,000
 * about 2.5 s (the performance review measured 5.7 s at 4,000 and 100 s at 10,000). The form now runs the
 * check every time the field loses focus, so a pasted value could freeze the tab. 254 is the longest valid
 * address (RFC 5321), so a longer value is refused BEFORE the pattern runs and the worst case stays at a few
 * milliseconds. The accepted set is unchanged for every value up to 254.
 */

/** The longest address that can exist (RFC 5321: 254 octets in a path, less the angle brackets). */
export const EMAIL_MAX_LENGTH = 254

const SHAPE = /\S+@\S+\.\S+/

export function looksLikeEmail(value: string): boolean {
  if (value.length > EMAIL_MAX_LENGTH) return false
  return SHAPE.test(value)
}
