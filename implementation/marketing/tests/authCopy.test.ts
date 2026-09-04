/**
 * Copy that more than one auth page says must have exactly one definition.
 *
 * MEDIUM-6 (Cody). Five views shipped byte-identical strings — `RESEND_FAILED` in three
 * files, `RESEND_RATE_LIMITED` in three, the rate-limit banner in two, and the
 * "Only the newest link works" / "Didn't arrive?" pair in five. The reasoning against that
 * is already written in the views: `SignInView.vue` holds its rejection copy as a constant
 * "so there is no seam for a future edit to slip a second variant into". The reasoning was
 * applied within each file and not across them, and five copies is five seams.
 *
 * It matters here more than it usually would. These pages exist to be indistinguishable
 * from one another in the ways that could reveal whether an address is registered, so
 * "the two pages agree word for word" is the property under test, not a preference. A
 * well-meant edit to one page's rate-limit copy that missed the other would be a
 * difference between two states the API answers identically.
 *
 * This is the control that makes a sixth copy a failing test rather than something a
 * reviewer has to notice. It consumes `messages.ts` itself — the shared strings are read
 * from the module, not restated here — so a mutation to a message is not something this
 * file can silently disagree with.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'
import { readFileSync } from 'node:fs'
import * as MESSAGES from '../src/lib/auth/messages.ts'

const AUTH_VIEWS = [
  'SignInView.vue',
  'SignUpView.vue',
  'ForgotPasswordView.vue',
  'VerifyView.vue',
  'ResetView.vue',
] as const

function view(name: string): string {
  return readFileSync(new URL(`../src/views/${name}`, import.meta.url), 'utf8')
}

/** Collapse the whitespace a template wraps across lines, so a re-wrap is not a copy. */
function flat(text: string): string {
  return text.replace(/\s+/g, ' ')
}

/** Every shared string this module exports, by name. */
const SHARED: ReadonlyArray<[string, string]> = Object.entries(MESSAGES).filter(
  (entry): entry is [string, string] => typeof entry[1] === 'string',
)
const SHARED_NAMES = SHARED.map(([name]) => name)

/**
 * The `<script setup>` block. `''` when there is none.
 *
 * The two scans below run on the SCRIPT and not on the whole file, and the reason is
 * mechanical rather than a preference: a `.vue` template is prose, and prose contains
 * apostrophes — "Didn't arrive?", "isn't ready" — so a scanner that treats `'` as a string
 * delimiter mis-parses the template and silently stops finding things. Everything that
 * ASSEMBLES a message in this app happens in the script; the template only interpolates.
 * What the template does with the result is covered from the other side, by the rendered
 * scan in `scripts/auth_pages_headless.py`, and the template's bound expressions get the
 * decoration check below through `templateExpressions`.
 */
function script(name: string): string {
  const match = /<script[^>]*>([\s\S]*?)<\/script>/.exec(view(name))
  return match ? match[1] : ''
}

/**
 * One pass over real JavaScript: comments out, string literals collected.
 *
 * A scanner rather than a regex because the two jobs are the same job. `codeOnly` in
 * `tests/authViews.test.ts` strips comments with regexes and says in its own comment that
 * a `//` inside a string over-strips — safe there, because every assertion in that file is
 * "this string is absent" and over-stripping can only remove candidates. Here the
 * assertions run in BOTH directions (a binding must be USED; a literal must be COLLECTED),
 * so an over-strip would make a test pass by losing the thing it was meant to inspect.
 */
function scan(code: string): { code: string; literals: string[] } {
  let out = ''
  const literals: string[] = []
  let index = 0
  while (index < code.length) {
    const here = code[index]
    const next = code[index + 1]
    if (here === '/' && next === '*') {
      const end = code.indexOf('*/', index + 2)
      index = end === -1 ? code.length : end + 2
      out += ' '
      continue
    }
    if (here === '/' && next === '/') {
      while (index < code.length && code[index] !== '\n') index += 1
      out += ' '
      continue
    }
    if (here === "'" || here === '"' || here === '`') {
      let body = ''
      index += 1
      while (index < code.length && code[index] !== here) {
        if (code[index] === '\\') {
          body += code[index] + (code[index + 1] ?? '')
          index += 2
          continue
        }
        body += code[index]
        index += 1
      }
      index += 1
      literals.push(body)
      out += here + body + here
      continue
    }
    out += here
    index += 1
  }
  return { code: out, literals }
}

/**
 * The template's BOUND expressions — `{{ … }}` and `:attr="…"`.
 *
 * Not the template's text. These are the only places a template can decorate a shared
 * constant with code, and they contain expressions rather than prose, so the apostrophe
 * problem above does not arise inside them.
 */
function templateExpressions(name: string): string[] {
  const template = view(name).replace(/<!--[\s\S]*?-->/g, ' ')
  return [
    ...[...template.matchAll(/\{\{([\s\S]*?)\}\}/g)].map(([, body]) => body),
    ...[...template.matchAll(/[:@][\w.-]+="([^"]*)"/g)].map(([, body]) => body),
  ]
}

/**
 * Where a shared constant is DECORATED instead of used whole.
 *
 * THE HOLE THIS CLOSES, measured twice. Quinn planted
 * `RESEND_RATE_LIMITED + ' Too many requests for that address just now.'` at ONE of that
 * constant's four call sites and every gate stayed green: `npm run build` 0, `npm test` 0
 * at 132/0, `npm run test:states` 0 at 55 scenarios / 1556 checks / 0 FAIL. Cody closed
 * this control in review round 2 on the grounds that it "asserts both directions, which is
 * what stops it being satisfiable by deleting copy" — true of DELETION and of a
 * byte-identical DUPLICATE, and false of DIVERGENCE, which is the risk the module's own
 * header names. He reopened it in round 3 after reproducing her mutant himself.
 *
 * The rule is narrow on purpose: a shared constant is used WHOLE or not at all. Adjacent
 * `+`, a member access on it, or interpolation into a larger template literal are the
 * three ways to author a variant without ever restating the string, and all three are
 * refused. Composition that genuinely needs to happen belongs in `messages.ts`, where one
 * edit still reaches every page.
 */
function decorations(code: string, names: readonly string[]): string[] {
  const offences: string[] = []
  for (const name of names) {
    const occurrence = new RegExp(`(?<![.\\w$])${name}(?![\\w$])`, 'g')
    for (const match of code.matchAll(occurrence)) {
      const start = match.index ?? 0
      const before = code.slice(0, start).replace(/\s+$/, '')
      const after = code.slice(start + name.length).replace(/^\s+/, '')
      const context = code.slice(Math.max(0, start - 30), start + name.length + 30).trim()
      if (before.endsWith('+')) offences.push(`${name} has something concatenated BEFORE it: ${context}`)
      if (after.startsWith('+')) offences.push(`${name} has something concatenated AFTER it: ${context}`)
      if (after.startsWith('.')) offences.push(`${name} is transformed by a member call: ${context}`)
      if (before.endsWith('${')) offences.push(`${name} is interpolated into a larger string: ${context}`)
    }
  }
  return offences
}

/** The shared identifiers a view actually binds, parsed from its import statement. */
function sharedBindings(name: string): string[] {
  const code = scan(script(name)).code
  const statement = /import\s*\{([^}]*)\}\s*from\s*['"]@\/lib\/auth\/messages\.ts['"]/.exec(code)
  if (!statement) return []
  return statement[1]
    .split(',')
    .map((binding) => binding.trim().split(/\s+as\s+/).pop()?.trim() ?? '')
    .filter((binding) => binding !== '')
}

/**
 * Every fragment of a view in which a shared constant can be USED, as a list.
 *
 * The script with its import statements removed, then each bound template expression.
 * BOTH halves are required and the first version of this had only the first: in
 * `<script setup>` an imported binding is exposed to the template directly, so
 * `CHECK_SPAM_NOTE` is imported in the script and referenced only in `{{ … }}`. Counting
 * script references alone reported four correct views as importing copy they never used.
 *
 * Kept as separate fragments rather than one joined string so the decoration ban cannot
 * read a `+` at the end of one fragment as decoration of a constant at the start of the
 * next.
 */
function usageFragments(name: string): string[] {
  const body = scan(script(name)).code.replace(
    /import\s*(?:type\s*)?\{[^}]*\}\s*from\s*['"][^'"]*['"]/g,
    ' ',
  )
  return [body, ...templateExpressions(name)]
}

/** How often `name` is referenced across `fragments`. */
function referenceCount(fragments: readonly string[], name: string): number {
  const occurrence = new RegExp(`(?<![.\\w$])${name}(?![\\w$])`, 'g')
  return fragments.reduce(
    (total, fragment) => total + [...fragment.matchAll(occurrence)].length,
    0,
  )
}

/** Copy that is ABOUT rate limiting, which is the copy `ADDRESS_CLAIM_PHRASES` governs. */
const RATE_LIMIT_TOPIC = /rate.?limit|too many|wait a few minutes/i

describe('shared auth copy has one definition', () => {
  test('the module actually holds shared copy', () => {
    // The premise. Without it, emptying `messages.ts` would make every assertion below
    // pass by having nothing to look for.
    const values = Object.values(MESSAGES).filter((value) => typeof value === 'string')
    assert.ok(values.length >= 6, `expected the shared copy, found ${values.length} strings`)
    for (const value of values) {
      assert.ok(value.length > 10, `a shared message is suspiciously short: ${value}`)
    }
  })

  test('no view re-declares a shared message as a literal', () => {
    const offences: string[] = []
    for (const name of AUTH_VIEWS) {
      const source = flat(view(name))
      for (const [key, value] of Object.entries(MESSAGES)) {
        if (typeof value !== 'string') continue
        if (source.includes(flat(value))) {
          offences.push(`${name} contains a second copy of ${key}: "${value}"`)
        }
      }
    }
    assert.deepEqual(
      offences,
      [],
      `shared copy must be imported from '@/lib/auth/messages.ts', not repeated:\n  ` +
        offences.join('\n  '),
    )
  })

  test('every view BINDS shared copy and USES every binding it takes', () => {
    // The other half. Without it, a view could satisfy the test above by DELETING the copy
    // rather than by importing it, and the first test would read that as a pass.
    //
    // IT USED TO BE `view(name).includes("from '@/lib/auth/messages.ts'")` — the presence
    // of a STRING, not the use of a module. LOW-5 (Quinn) walked through it exactly as it
    // reads: she stripped `ResetView.vue`'s whole shared-copy import, replaced all four
    // uses (`RESEND_FAILED`, `NEWEST_LINK_BODY`, `NEWEST_LINK_TITLE`, `CHECK_SPAM_NOTE`)
    // with divergent literals, and left the module path alive inside a COMMENT. grep for
    // the four identifiers in the view: 0. grep for the path: 1. All three gates EXIT=0.
    //
    // So it reads bindings out of the parsed import statement, with comments removed
    // first, and then asks whether each binding is actually referenced. A path in a
    // comment is not an import, and an import nothing uses is not shared copy.
    for (const name of AUTH_VIEWS) {
      const bindings = sharedBindings(name)
      assert.ok(
        bindings.length > 0,
        `${name} binds no shared copy at all. Either it imports nothing from ` +
          "'@/lib/auth/messages.ts', or the only trace of that path is in a comment — " +
          'check the copy was moved rather than replaced with a local variant.',
      )

      const fragments = usageFragments(name)
      for (const binding of bindings) {
        assert.ok(
          SHARED_NAMES.includes(binding),
          `${name} imports \`${binding}\` from messages.ts, which exports no such string`,
        )
        assert.ok(
          referenceCount(fragments, binding) > 0,
          `${name} imports \`${binding}\` and never uses it — an import kept alive over a ` +
            'literal that took its place is exactly what this check exists to catch',
        )
      }
    }
  })

  test('no view DECORATES a shared message instead of using it whole', () => {
    // W-04, and the finding this whole control was reopened for. Deletion and duplication
    // were already caught; DIVERGENCE was not, and divergence is the risk the module's
    // header actually names — four pages that must say the same thing, one of which has
    // been quietly given a fifth variant assembled at the call site.
    //
    // Scope, stated rather than implied: the `<script setup>` block and the template's
    // BOUND expressions. That is every place a `.vue` file can compose a string from a
    // constant. Template PROSE placed next to a `{{ … }}` is a different shape and is
    // caught from the other side, by the rendered scan in `auth_pages_headless.py`.
    for (const name of AUTH_VIEWS) {
      const bindings = sharedBindings(name)
      const offences = usageFragments(name).flatMap((fragment) =>
        decorations(fragment, bindings),
      )
      assert.deepEqual(
        offences,
        [],
        `${name} builds a variant of shared copy at a call site. Four pages must say this ` +
          'word for word; a fifth variant assembled here is a difference between states ' +
          `the API answers identically:\n  ${offences.join('\n  ')}`,
      )
    }
  })

  test('the decoration ban matches the shapes it claims to, and nothing else', () => {
    // POSITIVE CONTROL, consuming `decorations` — the same function the ban above
    // consumes, not a restatement of its rules. Row one is Quinn's mutant verbatim.
    const names = ['RESEND_RATE_LIMITED', 'RESEND_FAILED']
    for (const shape of [
      "resendNote.value = RESEND_RATE_LIMITED + ' Too many requests for that address just now.'",
      "resendNote.value = 'Careful: ' + RESEND_RATE_LIMITED",
      'resendNote.value = RESEND_RATE_LIMITED.replace(/link/, "email")',
      'resendNote.value = RESEND_RATE_LIMITED.toUpperCase()',
      'resendNote.value = `${RESEND_RATE_LIMITED} for that address`',
    ]) {
      assert.ok(
        decorations(shape, names).length > 0,
        `the ban does not catch: ${shape} — it is disarmed for this shape`,
      )
    }

    // And the ways these views legitimately use a shared constant, or the ban would be
    // unusable and get deleted rather than corrected.
    for (const allowed of [
      'resendNote.value = RESEND_RATE_LIMITED',
      'resendNote.value = failed ? RESEND_RATE_LIMITED : RESEND_FAILED',
      '{{ RESEND_FAILED }}',
      ':title="RESEND_FAILED"',
      'import { RESEND_FAILED, RESEND_RATE_LIMITED } from "@/lib/auth/messages.ts"',
      // A DIFFERENT identifier that merely ends with a shared name must not fire it.
      "note.value = LOCAL_RESEND_FAILED + ' extra'",
    ]) {
      assert.deepEqual(
        decorations(allowed, names),
        [],
        `the ban false-positives on legitimate code: ${allowed}`,
      )
    }
  })

  test('the rate-limit CONSTANTS never imply the account exists', () => {
    // The reason `RESEND_RATE_LIMITED` is worded the way it is, asserted rather than left
    // to a comment. A limiter that spent its budget before looking the account up is not
    // evidence the account is real, and copy like "too many requests for this account"
    // would claim it is.
    //
    // WHAT THIS TEST CANNOT DO, stated because it used to be mistaken for more. It reads
    // the CONSTANTS. A view that writes `RESEND_RATE_LIMITED + ' for that address'` leaves
    // every constant here clean and still renders the forbidden phrase — Quinn walked past
    // this check exactly that way, at one of four call sites, with both gates green. The
    // rendered-output half is in `auth_pages_headless.py`, and the control below asserts it
    // is still there, because this file cannot see a page.
    const rateLimited = [MESSAGES.RESEND_RATE_LIMITED, MESSAGES.RATE_LIMITED_BODY].join(' ')
    for (const claim of MESSAGES.ADDRESS_CLAIM_PHRASES) {
      assert.ok(
        !rateLimited.toLowerCase().includes(claim),
        `rate-limit copy says "${claim}", which describes what the server knows rather ` +
          'than what the caller did',
      )
    }
  })

  test('no VIEW authors rate-limit copy that claims the account exists', () => {
    // The ban above reads the CONSTANTS. This one reads what the views themselves author,
    // because a view that never touches a shared constant can still write rate-limit copy
    // from scratch — `bannerBody.value = 'Too many requests for that address.'` — and the
    // constant scan would have nothing to say about it.
    //
    // Scoped to literals ABOUT rate limiting, deliberately. A blanket ban on these phrases
    // across the views would be wrong and would be deleted within a week: `SignInView`
    // legitimately says "This account isn't ready to sign in yet" in a state where the
    // password already PROVED the account exists, and `ResetView` says "on this account"
    // to someone holding a live reset token. The claim these phrases must never make is
    // about a RATE LIMIT, which is spent before the account is looked up.
    // NO FLOOR ON WHAT THIS SCANS, and that is deliberate rather than an omission. Every
    // rate-limit sentence in this app lives in `messages.ts` — which is the entire point of
    // that module — so the correct number of topical literals in the views is ZERO, and a
    // "at least N were scanned" premise would fail a tree that is exactly right. The
    // vacuity this file guards everywhere else is answered here by the positive control
    // below instead, which runs the same three definitions over a corpus that HAS one.
    const offences: string[] = []
    for (const name of AUTH_VIEWS) {
      for (const literal of scan(script(name)).literals) {
        if (!RATE_LIMIT_TOPIC.test(literal)) continue
        for (const claim of MESSAGES.ADDRESS_CLAIM_PHRASES) {
          if (literal.toLowerCase().includes(claim)) {
            offences.push(`${name}: "${literal}" says "${claim}"`)
          }
        }
      }
    }
    assert.deepEqual(
      offences,
      [],
      'a view authors rate-limit copy that describes what the server knows rather than ' +
        `what the caller did:\n  ${offences.join('\n  ')}`,
    )
  })

  test('the view-copy scan can actually find a literal, on a corpus that has one', () => {
    // POSITIVE CONTROL, and the reason the test above can be honest about scanning zero
    // literals. It consumes `scan`, `RATE_LIMIT_TOPIC` and `ADDRESS_CLAIM_PHRASES` — the
    // same three definitions — over a synthetic script block containing the offence.
    // Without this, "0 offences" and "the extractor is broken" are the same green.
    const planted = `
      // A comment that says 'too many requests for that address' must NOT be scanned.
      const UNREACHABLE = "We couldn't reach SelahCue. Your account is unaffected."
      const BAD = 'Too many requests for that address. Wait a few minutes, then try again.'
    `
    const literals = scan(planted).literals
    assert.ok(
      literals.includes(
        'Too many requests for that address. Wait a few minutes, then try again.',
      ),
      'the literal extractor no longer returns string contents — the scan above is blind',
    )
    assert.ok(
      !literals.some((literal) => literal.includes('must NOT be scanned')),
      'the extractor is reading COMMENTS as authored copy, which would make it fire on ' +
        'the prose explaining why a phrase is banned',
    )

    const topical = literals.filter((literal) => RATE_LIMIT_TOPIC.test(literal))
    assert.equal(topical.length, 1, 'the rate-limit filter selected the wrong set')
    assert.ok(
      MESSAGES.ADDRESS_CLAIM_PHRASES.some((claim) => topical[0].toLowerCase().includes(claim)),
      'the phrase list no longer matches the offence this control was written against',
    )

    // And the UNREACHABLE row proves the filter is doing real work: it contains a banned
    // phrase and is NOT about a rate limit, so it must not be selected. Without this, a
    // filter that matched everything would look identical to one that matched correctly.
    assert.ok(
      literals.some((literal) => literal.includes('Your account is unaffected')),
      'the extractor missed the non-topical literal, so the row below proves nothing',
    )
    assert.equal(
      topical.filter((literal) => literal.includes('unaffected')).length,
      0,
      'the rate-limit filter selects copy that is not about a rate limit — it would ban ' +
        'the honest network-failure message, and be deleted rather than corrected',
    )
  })

  test('the phrase list is real, and is the one the rendered-output scan reads', () => {
    // The premise. An emptied list makes the loop above pass by having nothing to look for,
    // which is the same vacuity the first test in this file guards against for the messages.
    assert.ok(
      MESSAGES.ADDRESS_CLAIM_PHRASES.length >= 4,
      `expected the forbidden-claim phrases, found ${MESSAGES.ADDRESS_CLAIM_PHRASES.length}`,
    )
    for (const phrase of MESSAGES.ADDRESS_CLAIM_PHRASES) {
      assert.equal(phrase, phrase.toLowerCase(), 'the scan lowercases before comparing')
      assert.ok(phrase.length > 5, `"${phrase}" is short enough to match by accident`)
    }

    // ONE DEFINITION, TWO CONSUMERS. The headless harness reads this array out of this
    // module's source rather than restating it, so the two checks cannot disagree about
    // what is forbidden. If that reader is renamed or removed, this fails rather than
    // leaving the rendered half silently unscanned.
    const harness = readFileSync(
      new URL('../scripts/auth_pages_headless.py', import.meta.url),
      'utf8',
    )
    assert.ok(
      harness.includes('ADDRESS_CLAIM_PHRASES'),
      'the headless harness no longer reads ADDRESS_CLAIM_PHRASES out of messages.ts. ' +
        'Without it, the only scan of the forbidden phrases is this file, which reads ' +
        'constants and cannot see what a page renders.',
    )
    assert.ok(
      harness.includes('RATE_LIMIT_CLAIM_SCENARIOS_MIN'),
      'the harness no longer asserts the rendered scan actually ran on any state. A ' +
        'conditional check that never fires is not a check.',
    )
  })
})
