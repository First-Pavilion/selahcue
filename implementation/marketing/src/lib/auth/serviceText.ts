/**
 * ONE definition of "whitespace", shared by every client rule that mirrors a Python one.
 *
 * WHY THIS MODULE EXISTS
 * ----------------------
 * Three separate client rules claim to reproduce a server transform:
 *
 *   - `signupPolicy.collapseWhitespace` mirrors `" ".join(value.strip().split())`
 *   - `passwordPolicy` mirrors `_validate_password`'s `not password.strip()`
 *   - `emailPolicy` mirrors `_normalize_email`'s `(raw or "").strip().lower()`
 *
 * All three were written with JavaScript's `String.prototype.trim()` and `/\s+/`, and all
 * three were WRONG in the same way, because the two languages do not agree on which
 * characters are whitespace. Measured, not assumed — every code point in 0x0..0x10FFFF
 * classified by both engines (`tests/serviceText.test.ts` re-runs the JS half on every
 * `npm test` and pins the Python half as `PYTHON_WHITESPACE` below):
 *
 *   Python says whitespace, JS does not:  U+001C U+001D U+001E U+001F U+0085
 *   JS says whitespace, Python does not:  U+FEFF
 *
 * The consequence is the exact mis-attribution these mirrors exist to prevent. An org
 * name of three U+001C characters survives the client collapse (so it passes
 * `ORG_NAME_REQUIRED`) and collapses to `""` on the server, which raises the
 * undifferentiated `VALIDATION_FAILED` the form cannot explain. A password of twelve
 * U+001C passes the client and fails `not password.strip()`. U+FEFF runs the other way:
 * the client validates a string the server does not store.
 *
 * Sana raised this on PR #16 and again here; it is the fourth client/server predicate in
 * a week to drift from its server twin. So it is defined ONCE, here, and every mirror
 * consumes this definition rather than re-deriving one. A test that re-derives the rule
 * it is checking cannot fail when the rule is wrong — that is the whole lesson of this
 * round.
 *
 * Pure and dependency-free so it can be unit tested under `node --test`.
 */

/**
 * Python's whitespace set for `str`, as code points.
 *
 * This is what `str.strip()` and `str.split()` (no argument) treat as whitespace: the
 * Unicode White_Space property PLUS the four C0 information separators U+001C..U+001F,
 * which Unicode does not classify as whitespace but CPython does.
 *
 * Written as escapes rather than literal characters on purpose: a source file carrying
 * raw C0 bytes is one careless copy-paste away from a range that silently means something
 * else, and `redirect.ts` already follows the same rule for the same reason.
 *
 * Re-derive with:
 *   python3 -c "print([cp for cp in range(0x110000) if chr(cp).strip() == ''])"
 */
export const PYTHON_WHITESPACE: readonly number[] = [
  0x0009, 0x000a, 0x000b, 0x000c, 0x000d, 0x001c, 0x001d, 0x001e, 0x001f, 0x0020, 0x0085,
  0x00a0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008,
  0x2009, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
]

/**
 * The same set as a regular-expression character class.
 *
 * THE SINGLE DEFINITION. `serviceStrip`, `serviceCollapse` and
 * `tests/serviceText.test.ts`'s whole-domain sweep all consume this one string, so a
 * mutation to it turns the tests RED rather than leaving them agreeing with a copy of
 * themselves. Note U+FEFF is deliberately ABSENT — JS `\s` includes it and Python does
 * not, so treating it as whitespace here would be a new divergence in the other
 * direction.
 */
export const SERVICE_WHITESPACE_CLASS =
  '\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a' +
  '\\u2028\\u2029\\u202f\\u205f\\u3000'

const RUN = new RegExp(`[${SERVICE_WHITESPACE_CLASS}]+`, 'g')
const LEADING = new RegExp(`^[${SERVICE_WHITESPACE_CLASS}]+`)
const TRAILING = new RegExp(`[${SERVICE_WHITESPACE_CLASS}]+$`)

/** True when Python's `str.strip()` would treat this single character as whitespace. */
export function isServiceWhitespace(character: string): boolean {
  return new RegExp(`^[${SERVICE_WHITESPACE_CLASS}]$`).test(character)
}

/** Python's `value.strip()`. */
export function serviceStrip(value: string): string {
  return value.replace(LEADING, '').replace(TRAILING, '')
}

/**
 * Python's `" ".join(value.strip().split())`.
 *
 * `str.split()` with no argument discards empty fields, so runs of whitespace collapse to
 * one space and a string of nothing but whitespace becomes `""`.
 */
export function serviceCollapse(value: string): string {
  const stripped = serviceStrip(value)
  if (stripped === '') return ''
  return stripped.replace(RUN, ' ')
}
