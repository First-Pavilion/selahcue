/**
 * Client-side email check — a MIRROR of the server's rule, not a looser approximation.
 *
 * The API's `_require_valid_email` (`services.py:488`) normalises with
 * `(raw or "").strip().lower()` and then calls Django's `validate_email`, raising
 * `VALIDATION_FAILED` — the same code every token failure raises — for anything it
 * refuses. The client cannot tell those apart, so an address this module lets through and
 * the server rejects surfaces as an error the page attributes to the wrong thing.
 *
 * WHY THIS IS NOT "DELIBERATELY PERMISSIVE"
 * -----------------------------------------
 * It used to be `/\S+@\S+\.\S+/`, with a header explaining that an over-strict client rule
 * would lock real customers out. That reasoning is sound and it is preserved below — what
 * was wrong was the conclusion, because permissive is not the safe direction here, it is
 * only a different way to be wrong. Four ordinary typos —
 *
 *     a@b.c      a@b..com      a@-b.com      a@b-.com
 *
 * all passed the old module and were all rejected by the server. On `/signup` the user got
 * an unattributed banner with no field-level error pointing at the address. On
 * `/forgot-password` it was worse: `VALIDATION_FAILED` mapped to "try again in a moment",
 * a TRANSIENT message for a PERMANENT error, so the user retries forever and no link ever
 * comes. That is the FR-552 dead end, reached through a typo.
 *
 * WHICH DJANGO, AND HOW THAT IS KNOWN
 * -----------------------------------
 * `implementation/api/pyproject.toml` pins `Django>=6.1,<6.2`, and **6.1 is not the
 * validator most references describe**. Django rebuilt `EmailValidator.domain_regex` on
 * `DomainNameValidator` in 5.2; every release up to and including 5.1 used a different
 * pattern. The first version of this module transcribed the OLD one and labelled it "6.1",
 * which is how `a@b.12` and `a@b.-xy` came to be recorded as server-ACCEPTED when 6.1
 * rejects both.
 *
 * So the rule below is not transcribed from documentation or memory. It is the composition
 * Django 6.1 itself performs, part for part:
 *
 *     domain_regex = "^" + hostname_re + domain_re + tld_no_fqdn_re + r"\Z"
 *
 * and every claim about what it accepts is checked by asking the pinned Django. See
 * `scripts/service_text_reference.py`: it refuses to run without Django installed rather
 * than falling back to a second copy of this file's rule, and it drives a generated corpus
 * through BOTH runtimes and diffs the verdicts. A transcription checked against another
 * transcription agrees with itself; that is the specific failure this file's review round
 * was about, and it is why no copy of the rule is allowed to be an authority here.
 *
 * THE ORIGINAL WARNING STILL STANDS, and agreement is how it is honoured. Being stricter
 * than the server is a LOCKOUT, and this module reached one: the first mirror rejected
 * every internationalised domain — `a@münchen.de`, `a@éxample.com`, `a@b.cé` — which
 * Django 6.1 accepts and which even the `/\S+@\S+\.\S+/` it replaced accepted. Because
 * `validateEmail` gates sign-in, signup, forgot-password AND resend, that was every auth
 * surface closed to those users. `tests/emailPolicy.test.ts` now fails if the client is
 * stricter than the server on ANY row, which is the class, not the instance.
 *
 * WHAT "MIRROR" IS AND IS NOT CLAIMED HERE
 * ----------------------------------------
 * This module mirrors ONE function: `django.core.validators.validate_email` applied to
 * `_normalize_email(address)`. That is the whole of what sign-in, forgot-password and the
 * resend mutation put an address through, so on those three surfaces the claim is total.
 *
 * SIGNUP HAS ONE MORE RULE THAT IS NOT MIRRORED HERE. `register_customer_user` writes the
 * address to `CustomerUser.email` and `CustomerOrg.primary_contact_email`, both bare
 * `models.EmailField()`, whose default `max_length` is 254 — and it calls `full_clean`, so
 * 255 characters is refused with "Ensure this value has at most 254 characters". Measured
 * against the pinned Django: `EmailField().clean` takes 254 and refuses 255. `validate_email`
 * itself takes anything up to 320, so `MAX_EMAIL_LENGTH` below is right and the 320-character
 * fixture row is right; the extra ceiling is a property of the SIGNUP WRITE, not of the
 * validator. It is mirrored where it belongs, next to the other `max_length` values read off
 * the same models: `MAX_SIGNUP_EMAIL_LENGTH` in `signupPolicy.ts`.
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
 * `EmailValidator.__call__`: `len(value) > 320` is refused before anything is parsed.
 *
 * RFC 3696 §3. Measured against the pinned Django, not assumed: 320 characters is accepted
 * and 321 is not, and both are pinned in the fixture file.
 */
export const MAX_EMAIL_LENGTH = 320

/**
 * `django.utils.ipv6.MAX_IPV6_ADDRESS_LENGTH`.
 *
 * `is_valid_ipv6_address` refuses a longer string BEFORE parsing it, so a fully expanded
 * 39-character address is valid and one character more is not — regardless of whether the
 * longer string would otherwise parse.
 */
const MAX_IPV6_TEXT_LENGTH = 39

/**
 * The non-ASCII code points Django's local-part classes contain even though nobody wrote
 * them there. NOT A CURIOSITY — leaving them out locks real people out.
 *
 * `user_regex` is compiled with `re.IGNORECASE`, and Python's `re.IGNORECASE` on a `str`
 * pattern does FULL CASE FOLDING rather than an ASCII case pair, so an ASCII letter class
 * quietly gains every code point that folds into it. Swept exhaustively over all 0x110000
 * code points against the installed 6.1.1 `user_regex`, exactly four non-ASCII code points
 * match as a one-character local part:
 *
 *     U+0130 İ    U+0131 ı    U+017F ſ    U+212A K (Kelvin sign)
 *
 * Two of them never reach the regex, because `_normalize_email` lowercases first: `İ`
 * becomes `i` + U+0307 COMBINING DOT ABOVE, which is not in the class, so `İ@example.com`
 * is REJECTED by both sides; `K` becomes a plain `k`, so `K@example.com` is ACCEPTED by
 * both sides as an ordinary `k`. JavaScript's `toLowerCase` and Python's `str.lower` were
 * measured to emit identical code point sequences for all four, so that reasoning holds on
 * this side of the mirror too.
 *
 * The other two are LOWERCASE ALREADY and survive normalisation unchanged. `ı` is the
 * ordinary Turkish dotless i — `bılgi@example.com` is an unremarkable real address — and
 * `ſ` is the long s. Django accepts both, and so does `EmailField.clean` on the signup
 * path. A client that omits them refuses an address the server would have taken: the same
 * lockout as the IDN one, in the half of the address the IDN fix does not touch. It was
 * found by a differential against real Django, not by reading, because reading the class is
 * exactly what produced the omission.
 *
 * ONE definition, consumed by all three of Django's local-part classes below and by the
 * control in `tests/emailPolicy.test.ts`, so narrowing any single class is a failing test
 * rather than a silent lockout.
 */
export const CASE_FOLDED_LOCAL_LETTERS = 'ıſ'

/**
 * `EmailValidator.user_regex` — the dot-atom form, or an RFC quoted string.
 *
 * Unchanged across the 5.2 rebuild: only the DOMAIN half was rewritten. Built from a string
 * of escapes rather than written as a regex literal so the source carries no literal
 * control bytes; `redirect.ts` and `serviceText.ts` follow the same rule for the same
 * reason.
 *
 * All three of Django's classes here span the ASCII letters — the dot-atom class, the
 * quoted-string class `!#-\\[\\]-\\177`, and the backslash-escape class — so all three
 * acquire `CASE_FOLDED_LOCAL_LETTERS` under `re.IGNORECASE`. Measured rather than reasoned:
 * the sweep above was run three times, against `x`, `"x"` and `"\\x"`, and returned the
 * same four code points each time.
 *
 * `u`-flagged like `DOMAIN`, so the class members are compared as code points.
 */
const FOLDED = CASE_FOLDED_LOCAL_LETTERS
const USER = new RegExp(
  '^(?:' +
    // dot-atom
    `[-!#$%&'*+/=?^_\`{}|~0-9A-Za-z${FOLDED}]+` +
    `(?:\\.[-!#$%&'*+/=?^_\`{}|~0-9A-Za-z${FOLDED}]+)*` +
    '|' +
    // quoted-string. The class is Django's `!#-\\[\\]-\\177` — every printable except
    // space, `"` and `\\` — plus the control characters it permits unescaped.
    `"(?:[\\u0001-\\u0008\\u000b\\u000c\\u000e-\\u001f!#-\\[\\]-\\u007f${FOLDED}]` +
    `|\\\\[\\u0001-\\u0009\\u000b\\u000c\\u000e-\\u007f${FOLDED}])*"` +
    ')$',
  'u',
)

/**
 * `DomainNameValidator.ul` — "Unicode letters range", Django's own comment.
 *
 * This one range is why `a@münchen.de` and `a@b.cé` are valid addresses on Django 5.2+.
 * It is a BMP range: a code point above U+FFFF is outside it, and Python's `re` compares
 * whole code points. JavaScript only agrees if the pattern carries the `u` flag — without
 * it the engine works in UTF-16 units, and BOTH halves of an astral character's surrogate
 * pair fall inside the range, so an emoji domain the server rejects would be accepted
 * here. Every regex built from `UL` below is therefore a `u`-flagged literal.
 */
const UL = '\\u00a1-\\uffff'

/** Letters, digits and the Unicode range — the characters a label may START and END with. */
const EDGE = `[a-zA-Z0-9${UL}]`
/** The same, plus the hyphen a label may carry internally. */
const INNER = `[a-zA-Z0-9-${UL}]`

/**
 * One label of 1–63 characters that neither starts nor ends with a hyphen.
 *
 * Django writes this two ways — `hostname_re` spells it out as an edge/inner/edge triple,
 * `domain_re` writes `(?!-)…{1,63}(?<!-)` — and they are the same language. The spelled-out
 * form is used for both here because lookbehind only reached Safari in 16.4, and one
 * definition consumed twice cannot drift from itself the way two copies can.
 */
const LABEL = `${EDGE}(?:${INNER}{0,61}${EDGE})?`

/**
 * `tld_no_fqdn_re` — the final label, and the part that surprises people.
 *
 * `(?!-)(?:[a-z` + ul + `-]{2,63}|xn--[a-z0-9]{1,59})(?<!-)`
 *
 * Two things follow from that class, and both were wrong in the first version of this file:
 *
 *   - there are NO DIGITS in it. `a@b.12` and `a@b.c0m` are rejected by Django 6.1. Only
 *     the `xn--` punycode alternative may contain them, which is why `a@b.xn--p1ai` is
 *     valid and `a@b.c0m` is not.
 *   - the leading hyphen is refused. `a@b.-xy` is rejected. Django ≤ 5.1 accepted it, and
 *     that is exactly the row this file used to pin as evidence it was faithful.
 *
 * `EmailValidator` uses `tld_no_fqdn_re`, NOT `tld_re`, so the trailing dot a fully
 * qualified name may carry is not allowed in an address: `a@b.com.` is refused.
 *
 * The `{2,63}` alternative is spelled edge/inner/edge for the same no-lookbehind reason as
 * `LABEL`; `xn--[a-z0-9]{1,59}` cannot end in a hyphen to begin with, so the trailing
 * guard is a no-op on it and is dropped rather than faked.
 */
const TLD_EDGE = `[a-zA-Z${UL}]`
const TLD_INNER = `[a-zA-Z-${UL}]`
const TLD = `\\.(?:${TLD_EDGE}${TLD_INNER}{0,61}${TLD_EDGE}|xn--[a-zA-Z0-9]{1,59})`

/**
 * `EmailValidator.domain_regex`, composed exactly as Django composes it.
 *
 * `re.IGNORECASE` is why `A-Z` appears in each class above. An earlier version of this
 * comment went on to say that the flag "never matters in practice" because `normalizeEmail`
 * has already lowercased the input — and that sentence was the whole mistake. Python's
 * `re.IGNORECASE` is full case folding, so it does not merely pair `A-Z` with `a-z`; it
 * pulls in code points nobody wrote, and two of them survive lowercasing. See
 * `CASE_FOLDED_LOCAL_LETTERS`. Here in the DOMAIN half it genuinely is inert — all four of
 * those code points sit inside `UL` already, so the fold adds nothing this class did not
 * already contain — but that is a measured fact about this regex, not a general one about
 * the flag.
 */
const DOMAIN = new RegExp(`^${LABEL}(?:\\.${LABEL})*${TLD}$`, 'u')

/**
 * `EmailValidator.literal_regex` — the SMTP 4.1.3 address-literal form.
 *
 * `r"\[([A-F0-9:.]+)\]\Z"`, and that is the WHOLE pattern. The earlier version of this file
 * carried a second alternative for a `[IPv6:…]` tagged form; Django has no such branch, and
 * `I`, `P` and `v` are not in `[A-F0-9:.]`, so `user@[IPv6:::1]` could never have reached
 * it on the server. It was dead code that made the client accept an address Django refuses.
 */
const LITERAL = /^\[([A-Fa-f0-9:.]+)\]$/

/** `EmailValidator.domain_allowlist`. */
const DOMAIN_ALLOWLIST = ['localhost']

/**
 * `ipaddress.IPv4Address` semantics — four decimal octets, no leading zeros.
 *
 * The literal form is SHAPE-then-MEANING on the server: `literal_regex` only says "hex,
 * colons and dots inside brackets", and `validate_ipv46_address` then has to parse it.
 * Checking the shape alone — which this file used to do — accepts `user@[999.999.999.999]`
 * and `user@[1.2.3]`, both of which Django rejects.
 *
 * The leading-zero rule is not decoration: CPython removed the old octal interpretation, so
 * `01.2.3.4` raises rather than meaning `1.2.3.4`.
 */
function isIpv4(text: string): boolean {
  const octets = text.split('.')
  if (octets.length !== 4) return false
  for (const octet of octets) {
    if (!/^[0-9]{1,3}$/.test(octet)) return false
    if (octet.length > 1 && octet.startsWith('0')) return false
    if (Number(octet) > 255) return false
  }
  return true
}

/** Eight hex groups, or fewer with exactly one `::` standing for the rest. */
function isHexGroupedIpv6(body: string): boolean {
  const compressed = body.indexOf('::')
  let groups: string[]

  if (compressed >= 0) {
    // `1::2::3` is ambiguous and Python refuses it; so does this.
    if (body.indexOf('::', compressed + 1) !== -1) return false
    const left = body.slice(0, compressed)
    const right = body.slice(compressed + 2)
    groups = [
      ...(left === '' ? [] : left.split(':')),
      ...(right === '' ? [] : right.split(':')),
    ]
    // `::` must stand for at least one group, so the written ones cannot fill all eight.
    if (groups.length > 7) return false
  } else {
    groups = body.split(':')
    if (groups.length !== 8) return false
  }

  return groups.every((group) => /^[0-9a-fA-F]{1,4}$/.test(group))
}

/**
 * `django.utils.ipv6.is_valid_ipv6_address`.
 *
 * The length cap comes FIRST, exactly as Django applies it, so a 40-character string that
 * would otherwise parse is still refused.
 */
function isIpv6(text: string): boolean {
  if (text.length > MAX_IPV6_TEXT_LENGTH) return false

  const lastColon = text.lastIndexOf(':')
  if (lastColon < 0) return false

  // A trailing dotted-quad stands for the final two groups (`::ffff:1.2.3.4`). Rewriting it
  // as two hex groups keeps one grouping rule instead of two.
  const tail = text.slice(lastColon + 1)
  if (!tail.includes('.')) return isHexGroupedIpv6(text)
  if (!isIpv4(tail)) return false
  return isHexGroupedIpv6(`${text.slice(0, lastColon + 1)}0:0`)
}

/** `validate_ipv46_address` — IPv4 first, then IPv6, which is the order Django tries them. */
function isIpAddress(text: string): boolean {
  return isIpv4(text) || isIpv6(text)
}

/** `EmailValidator.validate_domain_part`. */
function serverWouldAcceptDomain(domain: string): boolean {
  if (DOMAIN.test(domain)) return true
  const literal = LITERAL.exec(domain)
  return literal !== null && isIpAddress(literal[1])
}

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
 * rather than only through `validateEmail`'s message strings — and so
 * `scripts/service_text_reference.py` can drive a generated corpus through it and through
 * the real Django side by side.
 */
export function serverWouldAcceptEmail(email: string): boolean {
  const normalized = normalizeEmail(email)

  // `EmailValidator.__call__`, in its order: emptiness, the at-sign, then the length cap,
  // all before anything is split.
  if (normalized === '') return false
  if (!normalized.includes('@')) return false
  if (normalized.length > MAX_EMAIL_LENGTH) return false

  // `value.rsplit("@", 1)` — the LAST at-sign, which is what makes a quoted local part
  // containing one work at all.
  const at = normalized.lastIndexOf('@')
  const user = normalized.slice(0, at)
  const domain = normalized.slice(at + 1)

  if (!USER.test(user)) return false
  if (DOMAIN_ALLOWLIST.includes(domain)) return true
  return serverWouldAcceptDomain(domain)
}

/** Returns an error message, or `''` when the address is safe to submit. */
export function validateEmail(email: string): string {
  if (normalizeEmail(email) === '') return EMAIL_REQUIRED
  if (!serverWouldAcceptEmail(email)) return EMAIL_INVALID
  return ''
}
