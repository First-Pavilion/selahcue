/**
 * Source-level controls on the auth path.
 *
 * These assert on the FILES rather than on rendered output, because what they guard cannot
 * always be seen in a render. Raised as LOW-3 by Sana: the headless suite runs Chrome with
 * `--virtual-time-budget`, which fast-forwards timers, so an address-keyed `setTimeout`
 * would render identical text after different wall-clock delays.
 *
 * WHAT THESE ARE, AND WHAT THEY ARE NOT — stated up front because the previous version of
 * this file overclaimed and three reviewers stepped around it independently.
 *
 * They are TRIPWIRES, not the boundary. Every one of them is lexical, and a lexical rule
 * keyed on identifier names can always be walked past by renaming: Cody extracted
 * `function looksRegistered(value: string)` and moved the inspection onto a parameter this
 * file has never heard of, and both gates stayed green. That is not a bug in the regexes,
 * it is the ceiling of the technique.
 *
 * THE BOUNDARY IS BEHAVIOURAL, and it lives in `scripts/auth_pages_headless.py`: each
 * enumeration pair now records its rendered surface at three moments — before submit, in
 * flight, and settled — and every attribute of every element is signed. That compares WHAT
 * THE TWO BRANCHES RENDER, so it does not care how the source was written, and it catches
 * Cody's helper extraction, Sana's computed placeholder and both of Quinn's oracles. These
 * tests remain because they are exact, instant and never flake; they are the cheap first
 * line, not the guarantee.
 *
 * EVERY BAN BELOW HAS EXACTLY ONE DEFINITION, and its positive control consumes THAT
 * definition rather than a second copy. Quinn showed why: `INSPECTORS` used to be declared
 * once in the ban and again in the control that vouched for the ban. She deleted
 * `startsWith|` from the ban's copy only, planted `address.startsWith('pastor')` in
 * `ForgotPasswordView.vue`, and got `npm test` EXIT=0 with the control itself printing
 * `ok - the literal ban actually matches the shapes it claims to`. The ban was dead, the
 * leak was in the tree, and the proof-of-life said fine. So the predicates are module
 * scope now, and mutating one turns its own control RED.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'
import { readFileSync } from 'node:fs'

/**
 * Every view on the auth path — all five.
 *
 * LOW-8 (Cody): this was the three views that submit credentials, and `VerifyView.vue` and
 * `ResetView.vue` were neither listed nor excluded with a reason. Both call auth mutations
 * and both can navigate, so the shared-try ban, the address ban and the transport ban all
 * mean the same thing on them as on the other three; the documented reason `VerifyView`
 * sits outside the TIMER ban is its 300ms display floor, which says nothing about the
 * other three bans. An omission that is not written down reads as a decision nobody made.
 */
const VIEWS = [
  'views/SignInView.vue',
  'views/SignUpView.vue',
  'views/ForgotPasswordView.vue',
  'views/VerifyView.vue',
  'views/ResetView.vue',
] as const

/**
 * The ONE file the timer ban does not run over, named here instead of being left out of
 * `VIEWS` — and EARNED rather than granted.
 *
 * `VerifyView.vue` holds its spinner for a 300ms minimum (design §4.1), which is a display
 * floor applied to every outcome equally, not an outcome being simulated. An exemption on
 * a list is indistinguishable from an oversight, and it is also a hole: the file could
 * gain a second, address-keyed timer and inherit the same pass. So the exemption comes
 * with `theDisplayFloorIsTheOnlyTimer` below, which asserts what the exemption is FOR —
 * one primitive, one call site, armed from the floor constant. Same treatment
 * `lib/api/graphql.ts` gets for the same reason.
 */
const TIMER_BAN_EXEMPT: ReadonlySet<string> = new Set(['views/VerifyView.vue'])

/**
 * Everything else on the auth path where a timer, an inspection or a second transport
 * would be just as effective as it would be in a view.
 *
 * Quinn's LOW-2 created this list; her LOW-4 and Vera's F2 are why it is this long. The
 * path grew in this PR and the list did not grow with it: `Navbar.vue` gained `signOut`,
 * `router/index.ts` gained the session guard, `FormField.vue` renders every auth input's
 * `placeholder` — the very attribute Cody's leak used — and five of the ten modules in
 * `lib/auth/` were outside the ban entirely. Vera planted a `requestAnimationFrame` chain
 * in a COVERED file and it passed 110/110, which is why `requestAnimationFrame` and
 * `setImmediate` are on the primitive list below.
 *
 * `lib/api/graphql.ts` is deliberately NOT here: it uses `setTimeout` legitimately, for
 * the request and bootstrap deadlines. It gets its own, stronger assertion at the bottom.
 */
const AUTH_PATH_MODULES = [
  'lib/api/account.ts',
  'lib/auth/session.ts',
  'lib/auth/sessionStore.ts',
  'lib/auth/signupPolicy.ts',
  'lib/auth/passwordPolicy.ts',
  'lib/auth/emailPolicy.ts',
  'lib/auth/serviceText.ts',
  'lib/auth/countries.ts',
  'lib/auth/redirect.ts',
  'lib/auth/tokenParam.ts',
  'lib/auth/useLandingToken.ts',
  'components/auth/AuthShell.vue',
  'components/auth/AuthBanner.vue',
  'components/auth/StatusDisc.vue',
  'components/Navbar.vue',
  'components/FormField.vue',
  'router/index.ts',
] as const

/** Everything the bans below run over. */
const GUARDED = [...VIEWS, ...AUTH_PATH_MODULES] as const

function source(relative: string): string {
  return readFileSync(new URL(`../src/${relative}`, import.meta.url), 'utf8')
}

/**
 * How much of a file must survive the comment strip — the COARSE half of the vacuity guard.
 *
 * BE CLEAR ABOUT WHAT THIS NUMBER CAN AND CANNOT DO, because the previous comment claimed
 * more than it delivered and the measurement says so. The floor was 0.22, chosen because
 * the lazy→greedy comment-strip regression Cody demonstrated left `graphql.ts` at 14.6%.
 * Re-measured against the file as it stands today, the SAME greedy strip leaves 24.3% —
 * above 0.22 as well as above 0.18. Meanwhile `tokenParam.ts`, which is 79% comment and
 * entirely correct, sits at 21.2%, so 0.22 now fails a good file.
 *
 * There is therefore NO ratio that both passes the real files and catches that regression.
 * A number in between would be a control that reads as if it guards the thing it names and
 * does not, which is the exact failure this review round was about. So the claim is
 * narrowed to what a ratio can actually do — notice a strip that empties a file — and the
 * regression is caught by the DECLARATION ANCHOR below instead, which loses 5 of
 * `graphql.ts`'s 13 declared symbols under the greedy strip and says which. The control
 * `the vacuity guard catches the over-strip it was written for` asserts exactly that, and
 * consumes the same `codeIsIntact` the guard does.
 */
const STRIP_RATIO_FLOOR = 0.18

/**
 * The file with its comments removed.
 *
 * Necessary, and the first version of this file proved it: these views DOCUMENT the
 * simulated code they replaced — "a `setTimeout(…, 1000)` that faked every outcome, a
 * hardcoded `error@test.com` failure" — so a naive grep failed on the prose explaining why
 * the thing is banned. Stripping comments is what makes these assertions about code.
 *
 * Crude on purpose: it does not parse, and a `//` inside a string literal would be
 * over-stripped. That direction is safe here (it can only remove more), and `codeIsIntact`
 * below refuses to let the stripping quietly empty the file.
 */
function codeOnly(view: string): string {
  return source(view)
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1 ')
}

/**
 * Blank out the CONTENTS of string and template literals, keeping the quotes.
 *
 * FOR `tryBlocks` ONLY, and the scope matters. This was briefly used by the address ban as
 * well, to stop prose like `'Enter your email address. Try again.'` tripping the
 * member-access rule — and it silently BROKE the ban, because in a `.vue` file every bound
 * attribute is a double-quoted string:
 *
 *     :placeholder="email.startsWith('nobody') ? 'This address has no account' : '…'"
 *     :style="{ color: submittedEmail.split('@')[0] === 'x' ? red : black }"
 *
 * Blanking those blanks exactly the place Cody's original leak lived, so the ban would
 * have kept passing while claiming to cover the one channel it was extended for. Caught by
 * re-planting Quinn's inline-style mutation and noticing `npm test` stayed green when it
 * should not have. The address ban reads the raw text instead, and excludes prose by
 * requiring real code SHAPE — no whitespace around the member access, which `address. Try`
 * has and `email.split` does not.
 */
function withoutStringContents(code: string): string {
  return code
    .replace(/'(?:[^'\\\n]|\\.)*'/g, "''")
    .replace(/"(?:[^"\\\n]|\\.)*"/g, '""')
    .replace(/`(?:[^`\\]|\\.)*`/g, '``')
}

/**
 * Guard against the guard being vacuous.
 *
 * Every assertion below is of the form "this string is absent". If `codeOnly` ever
 * over-stripped — a regex change, a syntax it mishandles — it would return something close
 * to empty and every one of them would pass while checking nothing. This asserts the
 * stripped text still contains the file's real machinery.
 */
function codeIsIntact(name: string, code: string): void {
  const raw = source(name)

  if (name.endsWith('.vue')) {
    // A component's proof of life is its template. `AuthShell.vue` is pure markup — its
    // `<script setup>` holds nothing but the comment explaining the design — so requiring
    // a declaration there would fail on a file that is entirely correct.
    assert.ok(code.includes('<template>'), `${name}: stripping removed the template`)
  }

  const ratio = code.length / raw.length
  assert.ok(
    ratio >= STRIP_RATIO_FLOOR,
    `${name}: stripping left ${(ratio * 100).toFixed(1)}% of the file ` +
      `(${code.length}/${raw.length}) — the comment strip has over-matched`,
  )

  /**
   * And a NAMED anchor, because a proportional floor still cannot say WHICH part went
   * missing. Cody's regression lost "everything above `graphqlRequest`".
   *
   * MEDIUM-3 (Quinn): this used to anchor on `export …` declarations only, and matched
   * ZERO of them in every `.vue` file — including all three views this file exists to
   * guard, where the loop body simply never ran. `<script setup>` exports nothing; its
   * declarations are plain top-level `const`s. So both kinds are collected, and the count
   * is asserted non-zero rather than left to iterate over an empty list.
   */
  const declared = [
    ...raw.matchAll(/export\s+(?:async\s+)?(?:function|const|class|interface|type)\s+(\w+)/g),
    ...raw.matchAll(/^const\s+(\w+)/gm),
    // `<script setup>` compiler macros and the prop names they declare. `StatusDisc.vue`
    // is the file that needs this: it calls `defineProps<{ tone; glyph }>()` with no
    // binding at all, so the two patterns above find nothing in a file that is full of
    // real logic — precisely the "the loop never runs" hole MEDIUM-3 reported for `.vue`
    // files, one shape further in.
    ...raw.matchAll(/\b(defineProps|defineEmits|defineExpose|defineModel|defineOptions)\b/g),
    ...(/define(?:Props|Emits|Model)<\{([\s\S]*?)\}>/.exec(raw)?.[1] ?? '').matchAll(
      /^\s*(\w+)\??\s*:/gm,
    ),
  ].map(([, symbol]) => symbol)

  if (declared.length === 0) {
    // Legitimate for exactly one shape: a component that is pure markup, whose
    // `<script setup>` holds nothing but the comment explaining the design. `AuthShell.vue`
    // is that file. Asserted rather than exempted by name, so a component that later gains
    // logic without a top-level declaration cannot inherit the exemption silently.
    const script = /<script[^>]*>([\s\S]*?)<\/script>/.exec(raw)?.[1] ?? raw
    const scriptCode = script
      .replace(/\/\*[\s\S]*?\*\//g, ' ')
      .replace(/\/\/[^\n]*/g, ' ')
      .trim()
    assert.equal(
      scriptCode,
      '',
      `${name}: has script logic but no declaration to anchor on — this check would go ` +
        'quiet on it, which is the failure it exists to prevent',
    )
    return
  }

  for (const symbol of declared) {
    assert.ok(code.includes(symbol), `${name}: stripping removed the declaration \`${symbol}\``)
  }
}

// ---------------------------------------------------------------------------------------
// THE PREDICATES. One definition each. Both the bans and their positive controls consume
// these, so mutating one is visible in its own control.
// ---------------------------------------------------------------------------------------

/** Identifiers that hold an email address anywhere on this path. */
const ADDRESS_REFS = 'email|submittedEmail|sentToEmail|address'

/**
 * The ONLY members an address-bearing ref may have touched.
 *
 * INVERTED from the old whitelist of banned method names, which is how three of the four
 * demonstrated leaks got through. `INSPECTORS` named ten methods and omitted `split`,
 * `toLowerCase`, `replace`, `at`, `codePointAt`, `normalize` and `.length` — every one of
 * them a perfectly good oracle. A whitelist of the two members the real code actually uses
 * is a rule that does not need extending every time someone finds another string method.
 */
const ALLOWED_ADDRESS_MEMBERS = new Set(['value', 'trim'])

/** Methods that INSPECT their argument, for the shape where the address is passed in. */
const INSPECTOR_METHODS =
  'test|exec|includes|indexOf|lastIndexOf|search|match|startsWith|endsWith|has|localeCompare'

// NO `\s*` around the dot, deliberately. That is what separates code from prose: real code
// writes `email.split`, and an English sentence writes `address. Try again`. Without it the
// ban fires on every message constant that ends a sentence with the word "address".
//
// W-06 (Vera): this used to capture ONE member — `(?:\.value)?\.(\w+)` — so it saw the
// first hop and stopped. `email.value.trim().length` presented `trim`, which is on the
// whitelist, and the `.length` that was doing the actual work was never examined. Her
// 400ms oracle keyed on exactly that expression and passed both gates. The whitelist was
// never the problem; reading only the first link of the chain was. So the WHOLE chain is
// captured now — every member, past every call — and each hop is checked.
const ADDRESS_CHAIN = new RegExp(
  `(?<![.\\w$])(?:${ADDRESS_REFS})((?:\\.\\w+(?:\\([^()]*\\))?)+)`,
  'g',
)
const ADDRESS_INDEXED = new RegExp(`(?<![.\\w$])(?:${ADDRESS_REFS})(?:\\.value)?\\[`, 'g')
const ADDRESS_AS_ARGUMENT = new RegExp(
  `\\.\\s*(?:${INSPECTOR_METHODS})\\s*\\(\\s*(?:${ADDRESS_REFS})\\b`,
  'g',
)
const ADDRESS_VS_LITERAL = new RegExp(
  `(?<![.\\w$])(?:${ADDRESS_REFS})(?:\\.value)?\\s*[=!]==?\\s*['"\`]`,
  'g',
)
const LITERAL_VS_ADDRESS = new RegExp(
  `['"\`]\\s*[=!]==?\\s*(?:${ADDRESS_REFS})(?:\\.value)?(?![\\w$])`,
  'g',
)
/**
 * A hardcoded address.
 *
 * The `@` must be preceded by local-part characters, which is what keeps Vue's
 * `@submit.prevent="…"` and CSS `@media` out of it, and the TLD is any two-plus letters
 * rather than the old fixed `com|org|test|net`.
 *
 * RESIDUAL, stated rather than papered over: `'you@yourchurch.' + 'org'` reassembles an
 * address past this and always will. A literal ban cannot see through concatenation. That
 * shape is caught behaviourally instead — it has to RENDER to be an oracle, and the
 * headless probe compares what renders.
 *
 * AND THE BEHAVIOURAL NET HAS ITS OWN LIMIT, which that sentence used to leave implied.
 * W-14 (Sana): `auth_pages_headless.py` samples exactly TWO addresses per equivalence pair
 * (`EQUIVALENCE_GROUPS` / `SURFACE_GROUPS`), so a branch keyed on a THIRD address renders
 * identically for both sampled sides and passes both gates. The window-sampling and
 * facet-sampling limits were already written down beside those groups; input sampling was
 * the one axis that was not, which made "caught behaviourally instead" read as a closure
 * rather than as a narrower net. It is a narrower net. The residual is not closable by any
 * finite sample — adding a third address moves it to a fourth — so what is owed here is
 * the honest statement, not another row.
 */
const ADDRESS_LITERAL = /[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}['"`]/

/**
 * Every way this path inspects an address, as a list of what was found.
 *
 * Returns the offending fragments, so a failure names the shape rather than saying "no
 * match" and leaving a reader to guess.
 */
function addressInspections(code: string): string[] {
  const found: string[] = []
  for (const [whole, chain] of code.matchAll(ADDRESS_CHAIN)) {
    // EVERY hop, not the first. A whitelisted call is a step along the chain, never the
    // end of the inspection — `.trim()` is allowed, `.trim().length` is an oracle.
    for (const [, member] of chain.matchAll(/\.(\w+)/g)) {
      if (!ALLOWED_ADDRESS_MEMBERS.has(member)) {
        found.push(whole.trim())
        break
      }
    }
  }
  for (const [whole] of code.matchAll(ADDRESS_INDEXED)) found.push(whole.trim())
  for (const [whole] of code.matchAll(ADDRESS_AS_ARGUMENT)) found.push(whole.trim())
  for (const [whole] of code.matchAll(ADDRESS_VS_LITERAL)) found.push(whole.trim())
  for (const [whole] of code.matchAll(LITERAL_VS_ADDRESS)) found.push(whole.trim())
  return found
}

/**
 * Timing primitives. An outcome here comes from the API, never from a clock.
 *
 * W-06 (Vera) is why the last two rows exist, and the measurement is worth stating because
 * it falsifies what round 2 accepted. The elapsed-time gate in the headless harness is a
 * 600ms backstop; below that band this list is the ONLY control, and round 2 accepted the
 * band on the grounds that the tripwire bans every delay primitive. It did not. Vera
 * planted, in `SignInView.vue`'s submit path:
 *
 *     if (email.value.trim().length > 25) {
 *       await new Promise((r) => AbortSignal.timeout(400).addEventListener('abort', r))
 *     }
 *
 * `npm test` EXIT=0 at 132/0 and `npm run test:states` EXIT=0 at 55/1556/0 FAIL, with the
 * harness itself printing `PASS … 380ms apart (budget 600ms)`. A ready-made 400ms
 * address-keyed oracle, announced as a pass by the gate written to catch it. Her positive
 * controls confirm the machinery was otherwise live: the same key with `setTimeout(900)`
 * failed BOTH gates.
 *
 * `AbortSignal.timeout` is the primitive that was missing. `.animate(` is added with it —
 * a Web Animations timeline is a wall-clock delay with a promise on the end
 * (`el.animate(…, 400).finished`), and it was the next one along the same shelf. Both are
 * absent from `src/` today, so both are added while the tree is clean rather than after a
 * second demonstration.
 */
const TIMER_PRIMITIVES = [
  'setTimeout',
  'setInterval',
  'setImmediate',
  'requestIdleCallback',
  'requestAnimationFrame',
  'AbortSignal.timeout',
  '.animate(',
] as const

function timerUses(code: string): string[] {
  return TIMER_PRIMITIVES.filter((primitive) => code.includes(primitive))
}

/**
 * Every `try { … }` block in `code`, brace-matched.
 *
 * String contents are blanked first so a `}` inside a message cannot end a block early —
 * that direction is the dangerous one, because it would hide code the ban should see.
 */
function tryBlocks(code: string): string[] {
  const text = withoutStringContents(code)
  const blocks: string[] = []
  const opener = /\btry\s*\{/g
  let match: RegExpExecArray | null
  while ((match = opener.exec(text)) !== null) {
    let depth = 1
    let index = match.index + match[0].length
    while (index < text.length && depth > 0) {
      if (text[index] === '{') depth += 1
      else if (text[index] === '}') depth -= 1
      index += 1
    }
    blocks.push(text.slice(match.index, index))
  }
  return blocks
}

/** The calls whose rejection means "the server said no". */
const AUTH_CALL =
  /\b(?:signIn|signOut|refreshSession|confirmSession|requestPasswordReset|resendVerification|registerCustomerUser|confirmPasswordReset|verifyEmail|graphqlRequest)\s*\(/
/**
 * The calls whose rejection means "the page after this one did not load".
 *
 * `router.*` is not the whole set, and LOW-1 (Cody) is why: `window.location.assign(...)`
 * placed inside the credential `try` passed at 132/132. The ban was written against the
 * router because that is what the defect used, and a navigation performed any other way
 * lands in the same `catch` with the same consequence — a sign-in that succeeded rendering
 * "Invalid email or password".
 *
 * So it now names the ways a page can be left, not one library's spelling of it: the
 * router's methods, `location.assign` / `replace` / `reload`, an assignment to
 * `location.href` or to `location` itself, and the History API. Each is exercised in the
 * positive control below, which consumes THIS constant rather than restating it.
 */
const NAVIGATION = new RegExp(
  [
    // vue-router
    String.raw`\brouter\s*\.\s*(?:replace|push|go|back|forward)\s*\(`,
    // location.assign(…) / location.replace(…) / location.reload(…)
    String.raw`\blocation\s*\.\s*(?:assign|replace|reload)\s*\(`,
    // location.href = … / window.location.href = … / document.location.href = …
    String.raw`\blocation\s*\.\s*href\s*=`,
    // window.location = … (assigning the object itself navigates)
    String.raw`\b(?:window|globalThis|self)\s*\.\s*location\s*=`,
    // history.pushState / replaceState
    String.raw`\bhistory\s*\.\s*(?:pushState|replaceState)\s*\(`,
  ].join('|'),
)

/**
 * `try` blocks that wrap BOTH an auth call and a navigation — the HIGH-1 defect.
 *
 * Not "a navigation inside any try": the fixed code deliberately wraps `router.replace` in
 * its own try so a failed redirect can be reported honestly. What must never recur is the
 * two sharing one block, because then one `catch` is handed both kinds of failure and
 * cannot tell them apart — which is how a successful sign-in came to render
 * "Invalid email or password".
 */
function callAndNavigationShareATry(code: string): string[] {
  return tryBlocks(code).filter((block) => AUTH_CALL.test(block) && NAVIGATION.test(block))
}

// ---------------------------------------------------------------------------------------

describe('no auth view can fake, delay or vary an outcome', () => {
  test('none of them contains a timer', () => {
    // The view this replaced ran every outcome through `setTimeout(…, 1000)`, including a
    // hardcoded `error@test.com` failure — a literal address-keyed branch behind a delay.
    // Two branches with identical copy that settle at different times leak exactly what
    // the copy is careful not to.
    //
    // `VerifyView.vue` is deliberately out of scope: it legitimately holds its spinner for
    // a 300ms minimum (design §4.1), which is a display floor applied to every outcome
    // equally, not an outcome being simulated. The exemption is checked, not granted —
    // see `the one exempt file is exempt for the reason it claims` below.
    let scanned = 0
    for (const view of GUARDED) {
      if (TIMER_BAN_EXEMPT.has(view)) continue
      scanned += 1
      const text = codeOnly(view)
      codeIsIntact(view, text)
      const timers = timerUses(text)
      assert.deepEqual(
        timers,
        [],
        `${view} uses ${timers.join(', ')}. Outcomes here come from the API, never a clock.`,
      )
    }
    // The exemption set must not be able to empty the ban. Asserted here rather than
    // trusted, because `TIMER_BAN_EXEMPT.has(view)` is a `continue` and a `continue` that
    // fires on everything is a test that runs on nothing.
    assert.equal(
      scanned,
      GUARDED.length - TIMER_BAN_EXEMPT.size,
      'the timer ban skipped more files than the exemption set names',
    )
    assert.ok(scanned >= 20, `the timer ban ran over only ${scanned} files`)
  })

  test('the one exempt file is exempt for the reason it claims', () => {
    // W-08/LOW-8. `VerifyView.vue` is the single file outside the timer ban, and a name on
    // an exemption list is worth exactly nothing on its own: the file could grow a second,
    // address-keyed timer tomorrow and inherit the same silence. So the exemption is
    // narrowed to the thing it is for, the way `lib/api/graphql.ts` is treated below.
    const view = 'views/VerifyView.vue'
    assert.ok(TIMER_BAN_EXEMPT.has(view), 'this control names a file the ban does not skip')
    const text = codeOnly(view)
    codeIsIntact(view, text)

    // ONE primitive, and it is `setTimeout`. Anything else appearing here is a new
    // mechanism that has never been argued for.
    assert.deepEqual(
      timerUses(text),
      ['setTimeout'],
      'the exempt file gained a timing primitive that is not the display floor',
    )

    // ONE call site, to end of line rather than a balanced-paren match, for the same
    // reason the transport control gives: `[^)]*` would stop at the arrow function's own
    // paren and never examine the delay.
    const timers = text.match(/setTimeout\([^\n]*/g) ?? []
    assert.equal(timers.length, 1, `expected exactly the display floor, found ${timers.length}`)

    // And it is armed from a PARAMETER, whose only caller computes it from the floor
    // constant and the elapsed time — never from anything about the address. Both halves
    // are asserted, because `sleep(ms)` on its own says nothing about what `ms` is.
    assert.match(text, /function sleep\(ms: number\)/)
    // The DECLARATION is removed first, or its own parameter list reads as a call site
    // whose argument is `ms: number` — a control that fails on correct code gets deleted.
    const calls = text.replace(/function\s+sleep\s*\([^)]*\)/g, ' ')
    const callers = [...calls.matchAll(/(?<![.\w$])sleep\(([^)]*)\)/g)].map(([, argument]) =>
      argument.trim(),
    )
    assert.ok(callers.length > 0, 'nothing calls `sleep` — this control now guards nothing')
    for (const argument of callers) {
      assert.match(
        argument,
        /MIN_VERIFYING_MS/,
        `the display floor is armed from \`${argument}\`, which is not the floor constant`,
      )
    }
    // The floor is a literal number, not something derived at runtime.
    assert.match(text, /const MIN_VERIFYING_MS = 300\b/)
  })

  test('the timer ban actually matches the primitives it claims to', () => {
    // Positive control, consuming `timerUses` — the same function the ban above consumes.
    // Vera's mutation is the first row: a ~900ms delay built from 56 chained
    // `requestAnimationFrame` calls, planted in a file this ban already covered, passed
    // 110/110 because the primitive was not on the list.
    assert.deepEqual(timerUses('await new Promise((r) => requestAnimationFrame(r))'), [
      'requestAnimationFrame',
    ])
    assert.deepEqual(timerUses('setTimeout(finish, 900)'), ['setTimeout'])
    assert.deepEqual(timerUses('setInterval(poll, 50)'), ['setInterval'])
    assert.deepEqual(timerUses('setImmediate(finish)'), ['setImmediate'])
    assert.deepEqual(timerUses('requestIdleCallback(finish)'), ['requestIdleCallback'])
    // W-06 (Vera): her mutant verbatim. This row is the one that was missing, and the
    // whole 10-600ms band rested on it.
    assert.deepEqual(
      timerUses("await new Promise((r) => AbortSignal.timeout(400).addEventListener('abort', r))"),
      ['AbortSignal.timeout'],
    )
    // The next primitive along the same shelf: a Web Animations timeline is a wall-clock
    // delay with a promise on the end.
    assert.deepEqual(timerUses('await card.animate(frames, 400).finished'), ['.animate('])
    // And nothing it should not: `nextTick` and `queueMicrotask` cannot express a delay.
    assert.deepEqual(timerUses('await nextTick(); queueMicrotask(paint)'), [])
    // Nor the shapes that merely LOOK like the two new rows. An `AbortController` is not a
    // clock, and a CSS class called `animated` is not a call.
    assert.deepEqual(timerUses('const controller = new AbortController()'), [])
    assert.deepEqual(timerUses(':class="{ animated: pending }"'), [])
  })

  test('the vacuity guard catches the over-strip it was written for', () => {
    // POSITIVE CONTROL on `codeIsIntact`, consuming the guard itself rather than a
    // restatement of its rules. Without this the guard is a pile of assertions nobody has
    // ever seen fire.
    //
    // The regression, reproduced exactly: a lazy → greedy comment-strip, where one match
    // swallows everything between the first `/*` and the last `*/`. Cody found it by
    // making that change and watching every assertion in this file still pass.
    const raw = source('lib/api/graphql.ts')
    const overStripped = raw.replace(/\/\*[\s\S]*\*\//g, ' ')

    assert.throws(
      () => codeIsIntact('lib/api/graphql.ts', overStripped),
      /stripping removed the declaration/,
      'the guard no longer notices an over-strip that loses the top of a file',
    )

    // The RATIO alone would not have caught it — 24.3% survives, above any floor that
    // still passes `tokenParam.ts` at 21.2%. Pinned so the comment above cannot drift
    // away from the measurement.
    const regressionRatio = overStripped.length / raw.length
    assert.ok(
      regressionRatio > STRIP_RATIO_FLOOR,
      'the ratio floor now catches this on its own — the comment above needs updating',
    )

    // Lower half: every guarded file clears the coarse floor today, and the tightest is
    // named so a future file that squeezes under is a visible failure rather than a silent
    // recalibration.
    const tightest = GUARDED.map((file) => ({
      file,
      ratio: codeOnly(file).length / source(file).length,
    })).reduce((low, next) => (next.ratio < low.ratio ? next : low))
    assert.ok(
      tightest.ratio >= STRIP_RATIO_FLOOR,
      `${tightest.file} is at ${(tightest.ratio * 100).toFixed(1)}%, under the floor`,
    )

    // And the guard is not merely permissive: a file stripped to nothing must still fail.
    assert.throws(() => codeIsIntact('lib/api/graphql.ts', ''), /over-matched/)
  })

  test('none of them inspects an email address', () => {
    // The other half of the same defect. `email === 'error@test.com'` was the shape of the
    // simulation, and any branch keyed on WHO the user is is the enumeration oracle
    // arriving through the front door.
    for (const view of GUARDED) {
      // STATIC placeholders only — note the required whitespace before the attribute name.
      // This strip exists so the constant `placeholder="you@yourchurch.org"` does not trip
      // `ADDRESS_LITERAL`. It must NOT match the bound form `:placeholder="…"`, which is
      // exactly where Cody's one-line leak lived.
      const text = codeOnly(view).replace(/(^|\s)placeholder="[^"]*"/g, '$1 ')
      codeIsIntact(view, text)
      const found = addressInspections(text)
      assert.deepEqual(found, [], `${view} inspects an email address: ${found.join(' | ')}`)
      assert.ok(!ADDRESS_LITERAL.test(text), `${view} contains a hardcoded email address`)
    }
  })

  test('the address ban actually matches the shapes it claims to', () => {
    // POSITIVE CONTROL. It consumes `addressInspections` and `ADDRESS_LITERAL` — the SAME
    // definitions the ban above consumes — because the previous version of this control
    // declared its own copies of the regexes and therefore proved nothing. Quinn disarmed
    // the ban and this control still printed `ok`.
    const banned = [
      // The shapes the old whitelist caught.
      "submittedEmail.startsWith('second-attempt')",
      'email.value.includes("nowhere")',
      "sentToEmail.indexOf('nobody') !== -1",
      "email.value === 'error@test.com'",
      'email !== "someone"',
      // Quinn: the whitelist omitted these, and both walked past it.
      "email.value.split('@')[1] === 'x.org'",
      'submittedEmail.toLowerCase()',
      // Sana: nine shapes that stepped around the old ban. A representative sample.
      'email.value.charCodeAt(0)',
      'email.value.codePointAt(0)',
      'email.value.at(0)',
      'address.length > 25',
      'email.value.normalize()',
      // W-06 (Vera): the shape her 400ms oracle was keyed on. `trim` is whitelisted and
      // `.length` was never reached, so the ban saw a legal expression and said nothing.
      'email.value.trim().length > 25',
      'submittedEmail.trim().toLowerCase() === "x"',
      'sentToEmail.value.trim().slice(0, 3)',
      'email.value.replace(/x/, "")',
      // The inspector called ON something else, with the address as the ARGUMENT.
      '/^nobody/.test(email.value)',
      "new RegExp('^nobody').exec(email.value)",
      'KNOWN.indexOf(email.value) !== -1',
      // The comparison written the other way round.
      "'error@test.com' === email.value",
      // Bracket indexing.
      "email.value[0] === 'n'",
      // INSIDE A BOUND ATTRIBUTE, which in a .vue file is a double-quoted string. This is
      // where Cody's original leak lived and where an earlier version of this ban lost its
      // reach without noticing.
      `:placeholder="email.startsWith('nobody') ? 'This address has no account' : 'x'"`,
      `:style="{ color: submittedEmail.split('@')[0] === 'second-attempt' ? red : black }"`,
      `{{ email.endsWith('yourchurch.org') ? 'Checking your account…' : 'Sending…' }}`,
    ]
    for (const shape of banned) {
      assert.ok(
        addressInspections(shape).length > 0,
        `the ban does not catch: ${shape} — it is disarmed for this shape`,
      )
    }

    // And it does NOT match the legitimate uses these files actually make, or the ban
    // would be unusable and get deleted rather than fixed.
    for (const allowed of [
      'email.value.trim()',
      'email.trim()',
      // A whitelisted call is still allowed when nothing follows it — otherwise the ban
      // would forbid the one expression every one of these views legitimately writes.
      'signIn(email.value.trim(), password.value)',
      'validateEmail(email.value)',
      "password.value === ''",
      'submittedEmail.value = address',
      "errors.email = 'Enter your email address. Try again.'",
      'emailError.value = validateEmail(email.value)',
      // PROSE, not code. A message constant that ends a sentence with the word "address"
      // must not fire the member rule, or the ban becomes unusable and gets deleted
      // instead of fixed.
      "const EMAIL_REQUIRED = 'Enter your email address.'",
      "const HINT = 'Check the email address. Then try again.'",
      "const NOTE = 'We could not reach that address [see support].'",
    ]) {
      assert.deepEqual(
        addressInspections(allowed),
        [],
        `the ban false-positives on legitimate code: ${allowed}`,
      )
    }

    // The literal ban, which had NO control at all before — Quinn pointed out that
    // changing it to `\.(zzz)` would kill it with nothing anywhere noticing.
    assert.ok(ADDRESS_LITERAL.test("const KNOWN = 'error@test.com'"))
    assert.ok(ADDRESS_LITERAL.test('if (raw === "pastor@yourchurch.org") {'))
    assert.ok(ADDRESS_LITERAL.test("'someone@church.online'"))
    // Not Vue directives, not CSS at-rules, not import specifiers — the shapes that would
    // make it fire on every correct file.
    assert.ok(!ADDRESS_LITERAL.test('@submit.prevent="submit"'))
    assert.ok(!ADDRESS_LITERAL.test('@click.stop="handleSignOut"'))
    assert.ok(!ADDRESS_LITERAL.test('@media (max-width: 768px)'))
    assert.ok(!ADDRESS_LITERAL.test("import x from '@/lib/auth/session.ts'"))
  })

  test('no auth call and navigation share a try block', () => {
    // HIGH-1 (Cody), asserted rather than remembered. `await router.replace(...)` used to
    // sit inside the same try as `signIn`, so a rejected NAVIGATION landed in the
    // credential-failure handler and rendered "Invalid email or password" over a login
    // that had already succeeded. `/account` is lazy, so a stale `index.html` after a
    // deploy triggers it in production — and retrying never helps, because the credentials
    // were never the problem.
    for (const view of GUARDED) {
      const shared = callAndNavigationShareATry(codeOnly(view))
      assert.deepEqual(
        shared.map((block) => block.slice(0, 120)),
        [],
        `${view} wraps an auth call and a navigation in ONE try block. One catch cannot ` +
          'tell "the server rejected your password" from "the next page did not load".',
      )
    }
  })

  test('the shared-try ban actually matches the shape it claims to', () => {
    // POSITIVE CONTROL, consuming `callAndNavigationShareATry`. The first sample is the
    // defect as it actually shipped; the second is the fix. If the ban stops seeing the
    // first, this goes red.
    const asShipped = `
      state.value = 'submitting'
      try {
        await signIn(email.value.trim(), password.value, { signal: controller.signal })
        password.value = ''
        await router.replace(safeNextPath(route.query.next, '/account'))
      } catch (error) {
        bannerTitle.value = REJECTED_TITLE
      }`
    assert.equal(
      callAndNavigationShareATry(asShipped).length,
      1,
      'the ban no longer sees the defect it was written for',
    )

    const asFixed = `
      const outcome = await callLogin()
      if (!outcome.ok) return reportLoginFailure(outcome.error)
      try {
        await router.replace(landingFallback.value)
      } catch {
        state.value = 'signedIn'
      }`
    assert.equal(callAndNavigationShareATry(asFixed).length, 0, 'the fix must not be flagged')

    // EVERY WAY OUT OF THE PAGE, not just the router's. LOW-1 (Cody): a raw
    // `window.location.assign(...)` inside the credential try passed at 132/132, because
    // the ban only knew `router.*`. One row per navigation primitive, each consuming
    // `callAndNavigationShareATry` — so a primitive dropped from `NAVIGATION` fails here
    // rather than silently widening what may share a try with an auth call.
    for (const navigation of [
      "await router.replace('/account')",
      "window.location.assign('/account')",
      "location.replace('/account')",
      'location.reload()',
      "location.href = '/account'",
      "window.location.href = '/account'",
      "window.location = '/account'",
      "history.pushState({}, '', '/account')",
      "history.replaceState({}, '', '/account')",
    ]) {
      const shared = `
        try {
          await signIn(email.value, password.value)
          ${navigation}
        } catch (error) {
          bannerTitle.value = REJECTED_TITLE
        }`
      assert.equal(
        callAndNavigationShareATry(shared).length,
        1,
        `the ban does not see \`${navigation}\` sharing a try with an auth call. One catch ` +
          'cannot tell "the server rejected your password" from "the next page did not load".',
      )
    }

    // Each half alone is fine — otherwise the ban would be "no try blocks", which is a
    // different and much stupider rule.
    assert.equal(callAndNavigationShareATry('try { await signOut() } catch {}').length, 0)
    assert.equal(callAndNavigationShareATry("try { await router.push('/') } catch {}").length, 0)
    assert.equal(
      callAndNavigationShareATry("try { window.location.assign('/') } catch {}").length,
      0,
    )
    // And nothing that merely MENTIONS a location: reading the URL is not navigating, and
    // `tokenParam.ts` and `useLandingToken.ts` both read `location.href` legitimately.
    assert.equal(
      callAndNavigationShareATry("try { await signIn(a, b); const u = location.href } catch {}")
        .length,
      0,
      'reading location.href is not a navigation and must not be flagged',
    )

    // And a `}` inside a message must not end a block early, which would hide the
    // navigation from the ban.
    const withBraceInString = `
      try {
        await signOut()
        errorText = 'something } went wrong'
        await router.push('/')
      } catch {}`
    assert.equal(callAndNavigationShareATry(withBraceInString).length, 1)
  })

  test('every guarded module reaches the network only through the shared seam', () => {
    // "No second transport path is introduced" (acceptance criterion), asserted rather
    // than reviewed. A raw fetch here would bypass the CSRF bootstrap, the error-envelope
    // handling and the NETWORK classification all at once.
    //
    // LOW-9 (Quinn): this used to iterate `VIEWS` only, so a raw `fetch` in
    // `sessionStore.ts` would have passed and C-011's "no second transport path exists"
    // was narrower than it read.
    for (const module of GUARDED) {
      const text = codeOnly(module)
      codeIsIntact(module, text)
      assert.ok(!/\bfetch\s*\(/.test(text), `${module} calls fetch directly`)
      assert.ok(!text.includes('XMLHttpRequest'), `${module} uses XMLHttpRequest`)
    }
    for (const view of VIEWS) {
      const text = codeOnly(view)
      assert.ok(
        text.includes("from '@/lib/api/account.ts'") ||
          text.includes("from '@/lib/auth/sessionStore.ts'"),
        `${view} imports no API wrapper — check this test still points at a real view`,
      )
    }
  })
})

describe('the transport seam', () => {
  const TRANSPORT = 'lib/api/graphql.ts'

  test('its timers are deadlines, not delays', () => {
    // `graphql.ts` is the one module on this path that legitimately uses `setTimeout`: the
    // request deadline and the CSRF bootstrap deadline. It cannot join the blanket ban, so
    // it gets the assertion that actually matters instead.
    //
    // PRECISELY WHAT THIS ASSERTS: every timer is armed from a module constant OR from
    // `options.timeoutMs`, the caller-supplied per-request deadline. What is excluded is a
    // delay computed from anything else, which is the shape a timing oracle would take.
    const text = codeOnly(TRANSPORT)
    codeIsIntact(TRANSPORT, text)

    // To end of LINE, not a balanced-paren match and not a fixed character window.
    // `[^)]*` stops at the arrow function's own closing paren, so every timer reads as
    // `setTimeout((` and the delay is never examined.
    const timers = text.match(/setTimeout\([^\n]*/g) ?? []
    assert.equal(timers.length, 2, `expected exactly the two deadlines, found ${timers.length}`)
    for (const timer of timers) {
      assert.ok(
        /DEFAULT_TIMEOUT_MS|CSRF_BOOTSTRAP_TIMEOUT_MS|options\.timeoutMs/.test(timer),
        `a timer armed from something other than a deadline constant: ${timer.slice(0, 90)}`,
      )
    }

    // And no OTHER timing primitive has appeared alongside them.
    assert.deepEqual(
      timerUses(text).filter((primitive) => primitive !== 'setTimeout'),
      [],
      'the transport gained a timing primitive that is not a deadline',
    )
  })

  test('it never names an email address', () => {
    // WHAT THIS DOES AND DOES NOT BUY — the earlier version of this comment oversold it.
    //
    // It does NOT prove the transport cannot branch on registration status.
    // `graphqlRequest` is handed the address inside `variables` and the outcome inside
    // `envelope.errors`, so it could branch on either without ever writing the word
    // "email". The honest claim is narrower: it cannot branch on WHO THE USER IS BY NAME.
    // The real guarantee on this channel is structural and lives in the API: the server
    // equalises the branches itself and never tells the client which one occurred.
    const text = codeOnly(TRANSPORT)
    codeIsIntact(TRANSPORT, text)
    assert.ok(!/\bemail\b/i.test(text), 'the transport seam names an email address')
  })
})
