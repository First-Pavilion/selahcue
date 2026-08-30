# Goal Contract — TASK-web-auth-wiring

## Identity

- Goal ID: TASK-web-auth-wiring
- Parent goal ID: NONE
- Title: Sign-in, create-account and forgot-password in the marketing SPA run against the real `/graphql/account` surface, with the API's no-enumeration posture intact in the UI and no dead end on any failure.
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak11r67
- Created: 2026-08-25
- Updated: 2026-08-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`SignInView.vue` stops simulating authentication with `setTimeout` and calls the shipped
account mutations, and the two flows that had no client at all — create account and
forgot password — exist and call theirs. Every no-enumeration property the API pays for
server-side survives in the rendered UI, and every failure state offers a way forward.

## Baseline

Verified against the worktree at `main` @ `607a7b5`, `implementation/marketing` clean.

- `src/lib/api/graphql.ts` — working transport seam: relative `/graphql/account`,
  `credentials: 'same-origin'`, HTTP-200 error envelope handled, client-only `NETWORK`
  code, never logs.
- `src/lib/api/account.ts` — 4 wrappers: `verifyEmail`, `confirmPasswordReset`,
  `requestPasswordReset`, `resendVerification`.
- Consumed by exactly two views: `VerifyView.vue`, `ResetView.vue`.
- `SignInView.vue` imports nothing from the API layer. It fakes every outcome behind
  `setTimeout(…, 1000)`: a hardcoded `error@test.com` failure, a fabricated
  "Reset link sent! Please check your email inbox." success, and a
  "Continue with Google" button that waits 800ms and routes to `/account`.
- Its client password rule is 8 characters; the API's is 10, length-only.
- Nothing in the SPA calls `GET /graphql/csrf`. `CsrfViewMiddleware` is active
  (`settings.py:90`) and both GraphQL surfaces declare `*_session_with_csrf`, so no
  account mutation can succeed from a real browser today — including the two shipped
  views. `graphql.ts:182-187` names this ticket as the owner of that gap.
- `/account` is reachable with no session and renders entirely mock data (86ak11rjz owns
  its real data).

## Inputs and evidence sources

- `implementation/api/selahcue_api/graphql/account_schema.py` — the shipped schema (read, not inferred).
- `implementation/api/selahcue_api/apps/accounts/services.py` — `register_customer_user`, `login`, `refresh_session`, `logout_session`, `request_password_reset`, `_validate_password`.
- `implementation/api/selahcue_api/graphql/{context,views,errors}.py` — session cookie, CSRF bootstrap, error codes.
- `src/views/{VerifyView,ResetView}.vue` — the shipped pattern for token failure, merged states and conditional copy.
- ClickUp 86ak11r67 and 86ak120kw (three handoff specs that contradict the API).
- `.github/workflows/ci.yml` — the `marketing (vue spa)` job.

## Scope

### In scope

- Typed wrappers for `registerCustomerUser`, `login`, `logout`, `refreshSession` and the `accountViewer` probe, added next to the existing four in `account.ts`, all through `graphqlRequest`.
- CSRF cookie bootstrap inside the existing seam, so no second transport path appears.
- Sign-in, create-account and forgot-password UI with real validation, loading, error and recovery states.
- Session establishment, persistence across reload, and sign-out.
- A route guard making `/account` unreachable without a session.
- Extending `npm test` and the headless state harness to cover the new flows, including a deliberate enumeration probe.

### Non-goals

- `/verify` and `/reset` token landings (86ak10b1t, complete) — untouched except by the CSRF fix that they also need.
- Wiring `AccountView.vue`'s data (86ak11rjz). It stays mock; only its reachability changes.
- Admin console (86ak11t1f), affiliate portal (out of V1).
- Any change under `implementation/api` — four backend peers hold that tree.

### Constraints

- Footprint: `implementation/marketing/` only.
- Same-origin transport. A cross-origin deployment needs CORS middleware the API does not have.
- The session credential is an opaque HttpOnly cookie. It is not a JWT, must not be decoded, and the `sessionToken` the payload returns for desktop clients must not be persisted by a browser.
- No client behaviour may distinguish a registered address from an unregistered one — not by state, not by copy, not by request count.

### Assumptions and unknowns

- ASSUMED: `crypto.randomUUID()` is available in the target browsers; a `getRandomValues` fallback is written anyway. Validation owner: this ticket's tests.
- UNKNOWN: the exact body of the "account exists" transactional email (86ak0qd9u). The signup success copy is therefore written to be true whichever of the two emails was sent.

## Dependencies and approvals

- 86ak120kw (doc correction) — not merged. Its three corrections are applied here from the code, not from the doc.
- No backend change required; confirmed by reading the schema.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Sign-in, create-account and forgot-password each dispatch the real mutation with the shape `account_schema.py` declares | `npm test` | exits 0 | 103 pass / 0 fail; `tests/accountApi.test.ts` | PASS |
| C-002 | yes | Unknown-email and wrong-password sign-in render byte-identical card text | `npm run test:states` cross-scenario text equality | exits 0 | `PASS [enumeration] … indistinguishable at sign-in (card)` and `(ops)` | PASS |
| C-003 | yes | Signup for a new address and for an already-registered address render byte-identical card text | `npm run test:states` cross-scenario text equality | exits 0 | `PASS [enumeration] … new and an already-registered address (card)` and `(ops)` | PASS |
| C-004 | yes | Forgot-password for a registered and an unregistered address render byte-identical card text | `npm run test:states` cross-scenario text equality | exits 0 | `PASS [enumeration] … registered and an unregistered address (card)` and `(ops)` | PASS |
| C-005 | yes | No auth failure state is a dead end — each offers a control that can be ACTUATED and is not part of a field (FR-552) | `npm run test:states` | exits 0 | `forwardPathCheck` on 16 failure scenarios (was 6); it requires an enabled button outside `.form-field`, or an `a[href]`. Mutation-verified: hiding the submit button and the forgot link on a rejected sign-in gives 15 FAIL including 3 forward-path FAIL (it previously gave **zero** behavioural failures) | PASS |
| C-006 | yes | A password shorter than 10 chars is never sent to `registerCustomerUser` | `npm run test:states` | exits 0; 0 mutations dispatched | `signup-short-password`: `NO mutation dispatched for a 9-character password` | PASS |
| C-007 | yes | No session token is written to browser storage; a hint carrying one is rejected | `npm test` | exits 0 | `tests/session.test.ts`; plus a live localStorage sweep in `signin-success` | PASS |
| C-008 | yes | The session hint alone never grants entry to a protected route | `npm test` + `npm run test:states` | exits 0 | `account-stale-hint` plants a LIVE-LOOKING hint (30-day expiry) over a dead server session. Previously both guard-refusal scenarios ran with no hint at all, proving only that an ABSENT hint is refused (Quinn). Mutation-verified: a guard that returns early on `isProbablySignedIn` gives 4 FAIL on this scenario alone | PASS |
| C-009 | yes | Sign-out revokes server-side, clears local state, and `/account` redirects to `/signin` afterwards | `npm run test:states` | exits 0 | `session-lifecycle`; `signout-failure` covers the failed case | PASS |
| C-010 | yes | A transport failure is never rendered as a credential failure | `npm test` + `npm run test:states` | exits 0 | `signin-unreachable`, `signup-unreachable` | PASS |
| C-011 | yes | The CSRF cookie is bootstrapped through the existing seam, and no second transport path exists | `npm test` | exits 0; one `fetch` module | `tests/accountApi.test.ts` CSRF suite; `csrfChecks()` in every scenario. The `fetch`/`XMLHttpRequest` ban used to iterate the three VIEWS only, so a raw `fetch` in `sessionStore.ts` would have passed (Quinn LOW-9); it now runs over all 20 guarded modules | PASS |
| C-012 | yes | Typecheck and production build are clean | `npm run build` | exits 0 | `vue-tsc -b && vite build`, exit 0 | PASS |
| C-013a | yes | Fields carry labels, `autocomplete`, `aria-invalid` and `aria-describedby`; errors are announced; targets clear 44px | `npm run test:states` | exits 0 | autocomplete/label/aria/44px-target checks per scenario | PASS |
| C-013b | no | Every flow is completable by keyboard alone | **not verified** | — | **NOT_APPLICABLE — this was an overclaim and is withdrawn rather than left standing.** Quinn: `Tab`, `keydown` and `KeyboardEvent` appear nowhere in the harness, every interaction is a programmatic `submit`/`click`, and `document.activeElement` is asserted exactly once in the whole file — on `verify-success`, a view this PR does not touch. `focusHeading()` is called five times across the new views and `SignInView` moves focus to the password field after a rejection; none of it is checked. The ARIA half genuinely holds and is C-013a. Keyboard verification needs a driver that can send real key events; tracked as a follow-up, not claimed here | NOT_APPLICABLE |
| C-014 | yes | No fabricated success remains — no timer-simulated outcome, no unbacked OAuth affordance | `npm run test:states` + `npm test` | no matches | universal check `no unbacked OAuth affordance`; the timer ban covers `setTimeout`, `setInterval`, `setImmediate`, `requestIdleCallback` and `requestAnimationFrame` across 20 modules. Vera planted a ~900ms delay built from 56 chained `requestAnimationFrame` calls in a COVERED file and it passed 110/110, because the primitive was not on the list | PASS |
| C-015 | yes | The headless suite did not shrink; its floor was raised to the new count | `npm run test:states` | exits 0, not 4 | floor 495 → 1384 → **1556**; 55 scenarios, 1556 checks. Note what the floor is: it counts LINES PUSHED TO `results`, not assertions (Quinn verified this by pushing two INFO lines and watching the total rise), so it catches a driver regression that runs fewer checks and is **not** a measure of coverage | PASS |
| C-016 | yes | No wait in the request path is unbounded — a hung CSRF bootstrap still resolves to an honest state, and a caller who abandons the request is not held to it | `npm test` | exits 0 | `tests/accountApi.test.ts`. Now on `node:test` mock timers (Vera LOW-3: the old form waited out the real 5s and was ~93% of the suite's wall time; 5.1s → 0.34s) and the bounds are TIGHTER for it — the mutation is pinned as not-issued one millisecond before the deadline and issued just after. Plus `a caller who abandons the request does not sit out the seed deadline`, which was 5,001ms for a 500ms abort | PASS |
| C-017 | yes | The enumeration probe compares the two branches of each pair at THREE moments — before submit, in flight, and settled — over copy, whole-page text, request sequence, colour, every DOM attribute, and elapsed time | `npm run test:states` | exits 0; 45 `PASS [enumeration]` lines | 3 groups × (5 settled facets + elapsed) + 6 surface groups × 4 facets. **The old wording claimed each facet is "mutation-verified to be the sole catcher of its own channel", and that was FALSE of `tone`** — Quinn planted a class-based colour leak with identical text and BOTH `tone` and `attrs` failed, because `attrs` signs `class` and `toneSignature()` reads nothing but class names. `tone` is kept (it is cheap and it names the channel) but it is not sole. `card`, `page`, `ops` and `attrs` are each sole; `ops` verified by Quinn and Cody independently with an address-keyed extra request | PASS |
| C-018 | yes | The source-level bans are TRIPWIRES with a stated ceiling, each with a positive control that consumes the ban's own definition; the timing channel is gated at a wide paired delta | `npm test` + `npm run test:states` | exits 0 | `tests/authViews.test.ts`. **Two claims in the old wording were false and are withdrawn.** (1) "including inside bound attributes" — Cody extracted `function looksRegistered(value: string)`, moved the inspection onto a parameter outside the name list, bound it to a `:placeholder`, and both gates passed. A ban keyed on identifier names can always be walked past by renaming; that is the ceiling of the technique, it is now stated in the file header, and the boundary is C-017's behavioural comparison instead. (2) "positive control on its own regexes" — the control declared its OWN copies of the regexes, so Quinn disarmed the ban, planted the leak, and the control printed `ok`. Every predicate is one module-scope definition now, consumed by both. `elapsed` is gated at a 600ms paired delta, calibrated on local runs only — see the constant's comment | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

### What the probe does NOT cover, stated so it is not mistaken for more

Four reviewers each broke the round-1 guard set independently, and the honest summary of
why is that the guards **enumerated syntax where they needed to observe behaviour**, and
the controls that vouched for them **read private copies of the guards' own lists**. Both
are fixed; what follows is what is still true after the fix.

- **The source-level bans are tripwires and cannot be more than that.** They key on
  identifier names, and an identifier can always be renamed. Cody's `looksRegistered(value)`
  helper extraction is the proof, and no widening of the regexes would have changed it. The
  file header says so now. The boundary is the behavioural comparison in C-017, which does
  not care how the source is written.
- **`elapsed`'s threshold is calibrated on developer machines only.** Every clean reading on
  record — Vera's 18/18, Quinn's, Cody's, and this round's — comes from a laptop. Nobody has
  measured a CI runner's variance and, with this repository's Actions minutes exhausted,
  nobody could. 600ms sits well above the worst recorded correct-code spread (321ms, at load
  41) and well below every planted mutant (869–900ms). **If CI turns it red on correct code,
  widen it to 1500ms — which still catches every mutant on record — rather than removing
  the gate, and record the measurement here.**
- **`tone` is not a sole catcher and the contract no longer says it is.** A class-based
  colour leak fails `attrs` too, because `attrs` signs `class`. The half of the colour
  channel that neither covered — inline `style` — is closed by signing every attribute.
- **The facet set is not proven exhaustive.** It never was, and two rounds of review have now
  each found a channel the previous set was blind to (`attrs` after round 1; the pre-submit
  and in-flight WINDOWS, and inline `style`, after round 2). Signing every attribute rather
  than a whitelist, and sampling three moments rather than one, is an attempt to make the
  next hole a different SHAPE rather than the same shape one item along — not a proof there
  is no next hole.
- **The guarded module list is hand-maintained.** It is 20 files now (was 11), and it grew
  because the auth path grew in this PR and the list did not follow. Nothing detects that
  automatically; a new component on this path is uncovered until someone adds it.
- **The client does hold one piece of registration-adjacent knowledge: the address the user
  typed.** That is why the address ban is load-bearing rather than decorative, and why a
  strip that blinded it to bound attributes was a real hole. It was re-introduced and
  re-fixed during this very round — `withoutStringContents` blanked Vue's double-quoted
  bound attributes, and Quinn's inline-style mutation is what exposed it.
- **The strongest guarantee on timing is structural, not a test.** The server equalises the
  branches itself — `check_password` against `_DUMMY_PASSWORD_HASH` on the unknown-email
  path, and a dummy-PBKDF2 pad in `request_password_reset` — and its responses to the two
  branches are byte-identical. The client is never told which branch occurred, so it holds
  no registration knowledge to time-branch on. A client-side timing oracle would require the
  client to first acquire the very fact the whole design withholds.
- **The fixtures never present a difference.** Every scenario scripts identical responses for
  both branches, because that is what the API really returns. So the probe proves the client
  does not **invent** a distinction; it cannot prove the client would not **render** one if
  the server ever started emitting it. "No *response* difference reveals whether an address
  is registered" is a server property, and this branch verifies it nowhere.
- **Keyboard operability is not verified at all.** See C-013b. The ARIA half holds; the
  keyboard half was claimed and never tested, and the claim is withdrawn rather than
  softened.

### Findings deliberately NOT actioned, with reasoning

Both are reviewer findings I disagree with on the evidence, recorded here so the
disagreement is reviewable rather than silent.

- **A negative cache on the CSRF seed (Cody LOW-8, sized by Vera).** Three sequential
  logins against a hanging `/graphql/csrf` cost three 5s waits. A session-scoped backoff
  would remove the wait — and would also send the next mutation with no CSRF token, turning
  a bounded DELAY into a functional 403 the moment the seed recovers. Today a failed seed
  costs time and the mutation still runs; with a negative cache a transient failure costs
  correctness. Vera's own verdict is "acceptable while the seed shares fate with the API; a
  session-scoped backoff is only worth it if that ever changes". Not implemented; the abort
  half of the same finding, which has no such trade, is fixed.
- **`?next=` reachability of the unguarded `/admin/*` routes (Cody LOW-7, routed to Sana).**
  `?next=/admin` does land a signed-in customer on an admin view. But those routes carry no
  `requiresSession` and are reachable by typing the URL, so `?next=` grants no access that
  did not already exist — it is a shorter path to the same place. The real defect is that
  `/admin/*` is unguarded, which is neither this ticket's scope nor something `safeNextPath`
  should paper over by growing a route blacklist. Raised as a follow-up instead.

### Follow-ups this round did not close

- Keyboard operability verification (C-013b) — needs a driver that sends real key events.
- Quinn's remaining coverage gaps: `confirmSession`'s `unreachable` branch and the guard's
  deliberate `return true` for it; both `submitResend` failure paths; `signOut`'s
  "already gone counts as success"; a failed `refreshSession`; `Navbar.vue`'s mobile drawer,
  which holds a second copy of the signed-in controls and a second `handleSignOut`;
  `ForgotPasswordView`'s NETWORK-path scenario (`forgot-failure` uses `INTERNAL`).
- Guarding `/admin/*` and `/affiliates/*`.
- CI has never run the marketing job on this PR (see the PR description).

## Verification plan

- Focused verification: `npm test` (pure logic — request shapes, session storage, guard decisions), `npm run test:states` (real bundle in headless Chrome — rendered states, focus, ARIA, enumeration equality).
- Broader regression verification: the full `marketing (vue spa)` CI job locally — `npm ci`, `npm run build`, `npm test`, `SELAHCUE_HEADLESS_REQUIRE=1 npm run test:states` — each exit code captured directly, never through a pipe.
- Independent verifier: Cody, Sana, Vera, Quinn before any PR.
- Required environment: Node 22, headless Chrome.

## Iteration ledger

### Iteration 1 — build against the code, not the docs

- Target criterion: C-001 … C-015
- Hypothesis: The gap is entirely client-side; the schema already carries every operation the three flows need, so no backend change is required.
- Change or investigation: read the shipped schema and services rather than the design docs, which 86ak120kw records as wrong in three places. A fourth of the same kind was found during this work — gap-fill §5c's "We couldn't find an account with this email", a second enumeration oracle that 86ak120kw does not list.
- Verifier executed: `npm ci`, `npm run build`, `npm test`, `SELAHCUE_HEADLESS_REQUIRE=1 npm run test:states`
- Result: hypothesis held — no backend change was needed. 108 unit tests, 49 headless scenarios, 1384 checks as finally shipped.
- New evidence: nothing in the SPA called `GET /graphql/csrf`, so every account mutation — including on the two views that shipped earlier — was a permanent 403 in a real browser. Fixed inside the existing seam.
- Decision: iterate

### Iteration 2 — mutation verification

- Target criterion: the credibility of C-002 … C-011 themselves
- Hypothesis: a passing test proves nothing until it has been shown to fail. Seven controls were broken one at a time and the suites re-run.
- Change or investigation: (1) select `sessionToken` in the login document; (2) delete the CSRF bootstrap call; (3) persist the caller's whole object in `writeSessionHint`; (4) delete the protocol-relative refusal in `safeNextPath`; (5) branch the sign-in rejection copy on the address — the same shape as the `error@test.com` special case the simulated view had; (6) skip signup validation before submitting; (7) make the route guard return `true` for every outcome.
- Verifier executed: `npm test` for 1-4; `npm run build && npm run test:states` for 5-7.
- Result: ALL SEVEN caught, each by the suite that names it. 1-4 turned four unit suites RED. 5 was caught by the enumeration comparison, which printed the two divergent renders side by side, and independently by the banned-phrase check. 6 turned three signup scenarios RED. 7 turned `account-guarded` and `session-lifecycle` RED. The shrink guard fired as well, below the floor. All mutants reverted and green restored.
- New evidence: the harness itself had a false-green path. Mutant 7 failed `vue-tsc`, so `dist/` was never rebuilt — and running the script directly served the previous good bundle: 0 FAIL, exit 0, with none of the code under test in it. Added `check_bundle_is_current()`, which compares source and bundle mtimes and exits 2; verified it refuses that exact situation.
- Decision: iterate

### Iteration 3 — a flake I introduced, and its cause

- Target criterion: C-015, and the trustworthiness of every headless result
- Hypothesis: `verify-loading` failed all 11 of its checks with `calls=0` — the view had not mounted inside its 120ms window — in the chained CI run, having passed minutes earlier. Suspected the async route guard.
- Change or investigation: `router.beforeEach(async …)` returns a promise even on its early-exit path, so vue-router awaited it on EVERY navigation, delaying first paint on all ~30 routes to serve a check only `/account` needs. Rewritten to return a plain boolean for unguarded routes and a promise only for the guarded one. Separately, `verify-loading`'s 120ms wait was implicitly asserting how fast a lazy chunk mounts; raised to 400ms, which cannot weaken the check because that scenario's scripted reply is a promise that never resolves.
- Verifier executed: `npm run build`, then `SELAHCUE_HEADLESS_REQUIRE=1 npm run test:states`, repeated.
- Result: 49 scenarios, 1384 checks, 0 FAIL, repeatedly.
- New evidence: the async guard was a real site-wide latency regression, not only a test problem. The flaky test was the only thing that surfaced it.
- Decision: complete

### Iteration 4 — security review (Sana): five low findings, three of them about my own guards

- Target criterion: C-016, C-017, and the honesty of the evidence behind C-015
- Hypothesis: a guard that reads broader than it is, is worse than no guard, because it is trusted. Sana found three of those in work that had already been mutation-verified.
- Change or investigation:
  - **LOW-1** `ensureCsrfCookie` had no timeout and is awaited *before* the mutation's timer starts, so a proxy that accepts and never answers left "Signing in…" up forever — an FR-552 dead end reached sideways. Gave it its own 5s `AbortController`; a timed-out seed already degrades correctly on the best-effort path. Deliberately does NOT take the caller's signal: the promise is shared, so one caller's cancellation must not abort a seed the others are awaiting.
  - **LOW-2** `AuthShell` renders the footer OUTSIDE `.au-card`, so `cardText()` could not see it — a footer branched on the address ("Sign in instead" vs "Create an account", the §4c shape) would have passed both existing facets. Added a `page` facet over the whole body.
  - **LOW-3** Added a `tone` facet (status classes — identical copy in a different colour is a colour-only oracle) and an `elapsed` facet, plus `tests/authViews.test.ts` as the *named* control banning timers and address literals in the three views outright.
  - **LOW-4** The staleness guard watched `src/` and `index.html` only; a change to `vite.config.ts`, `package.json` or the lockfile alters the bundle without touching `src/`. All three added.
  - **LOW-5** Contract numbers corrected to the then-shipped 49 / 1384 (1381 after iteration 5 demoted the `elapsed` facet, and 1384 again after iteration 6 added `attrs`).
- Verifier executed: one mutation per equivalence group, so each facet's failure could be attributed to exactly one channel — a footer leak in signup, a colour-only leak in forgot-password, an address-keyed 900ms delay in sign-in.
- Result: `page` caught only the footer leak; `tone` caught only the colour leak; **`elapsed` caught nothing.** The facet was reading `Date.now()` after the scenario's fixed `await wait(700)`, so every branch reported ~700ms regardless — it was measuring the harness's patience, not the application. Rewritten to POLL for the terminal copy and record when it actually appeared. Re-run with the same three mutants: 3 FAIL, exactly one per group, `elapsed` reporting `924ms` vs `55ms` while every text and colour facet passed. All mutants reverted; the three views verified byte-identical to the commit via `git diff`.
- New evidence: the first `elapsed` facet was vacuous, and only its own mutation test showed it. That is the second guard in this ticket that read broader than it was — the first being the harness running happily on a stale bundle. Both were found by attacking the guard, neither by reading it.
- Decision: iterate

### Iteration 5 — the timing facet is honest about what it can and cannot do

- Target criterion: C-017, C-018
- Hypothesis: the repaired `elapsed` facet caught the planted oracle cleanly (924ms vs 55ms), so it should ship as a gate.
- Change or investigation: it failed on CORRECT code in the very next full run — `signup-new: 24ms` against `signup-existing: 345ms`, a 321ms spread from nothing but poll granularity and Chrome scheduling. Its noise floor is wider than any tolerance tight enough to be useful. Widening past the noise would leave it unable to catch anything smaller than the noise; gating on it as-is would produce intermittent red on correct code.
- Verifier executed: repeated full runs, observing the spread.
- Result: demoted from `COMPARED_FACETS` to `REPORTED_FACETS` — still measured, still printed as `INFO` on every run so a real divergence is visible to a reviewer, but not a pass/fail gate. The deterministic control on that channel is `tests/authViews.test.ts`, which refuses a timer or an address literal in these three views outright, never flakes, and is mutation-verified. This is the fallback the security review explicitly offered. The shrink guard then refused the run (1381 < 1384) until the floor was lowered on purpose, with the reason recorded beside it.
- New evidence: a gate that cries wolf is worse than no gate — it teaches people to re-run until green, which is exactly the habit that let the stale-bundle false green survive in iteration 2. Trading a flaky broad check for an exact narrow one plus visible evidence is the better bargain, and the limitation is documented rather than hidden.
- Decision: complete

### Iteration 6 — QA review (Quinn): the channel four facets could not see

- Target criterion: C-017, C-018, and the accuracy of what C-017 claims
- Hypothesis: after two rounds of mutation verification the probe was complete. It was not.
- Change or investigation: Quinn built a mutant with **identical visible text** and an
  address-keyed destination — `<router-link :to="submittedEmail.startsWith('second-attempt') ? '/signin' : '/support'">Contact support</router-link>`
  — and ran the full gate against it: **1384 checks, 0 FAIL, exit 0, every facet PASS**,
  with registration status readable straight off the DOM as `href="/signin"` versus
  `href="/support"`. `card`/`page` read innerText, `tone` read a class whitelist, `ops`
  read operation names; nothing sampled any other attribute.
  - Added an **`attrs` facet**: tag name plus `href`/`target`/`rel`/`disabled`/`type`/
    `name`/`role`/`class`/`checked`/`autocomplete`/`aria-*`/`tabindex` for every element on
    the page. Two normalisations are load-bearing: `FormField` derives its id from
    `Math.random()`, so ids are collapsed to `<ID>` (keeping "is this field described?"
    while discarding the randomness), and addresses are masked as elsewhere.
  - **Widened `toneSignature()` from `.au-card` to `document.body`.** LOW-2 had widened
    *text* to the whole page but left *colour* scoped to the card, and `AuthShell` renders
    the footer outside it — so footer colour was uncovered by both.
  - **Widened the address-literal ban** in `authViews.test.ts`. It matched only a full
    address in quotes, so `startsWith('second-attempt')` walked past a test that claims to
    forbid exactly that. It now refuses any string-inspection method on an address-bearing
    ref and any direct comparison to a literal — and carries a **positive control on its
    own regexes**, asserting they match Quinn's mutation verbatim while not matching the
    legitimate `email.value.trim()` and `validateEmail(email.value)` the views use.
  - **Two more staleness inputs**: `tsconfig.app.json` (carries the `@/*` alias) and
    `public/` (copied verbatim into `dist/`). All eight inputs re-verified to bite
    individually, each restoring to clean.
- Verifier executed: Quinn's mutant verbatim, then the full gate.
- Result: `attrs` FAILed for the signup group alone; `card`, `page`, `ops` and `tone` all
  passed, confirming the leak was invisible to every pre-existing facet. The widened
  literal ban caught it independently in `npm test` — defence in depth. Mutant reverted;
  views confirmed byte-identical to the commit by `git diff`.
- Rulings accepted on the two open judgement calls, both upheld with better reasoning than
  I had: gating `elapsed` at ~750ms would be **worse** than not gating (a real timing
  oracle is a stable few-millisecond difference over many samples, invisible at that
  threshold, while the gate would imply the channel is covered); and tightening the
  bootstrap 5s→3s would move the worst case only 20s→18s while risking a spuriously
  timed-out seed on a cold path (DNS + TLS + Django cold start on mobile) sending the
  mutation tokenless into a 403 rendered as "we couldn't reach SelahCue" **on a working
  network** — trading 2s for a new false-failure mode.
- New evidence: this is the third guard in this ticket that read broader than it was, and
  the first one that survived two rounds of my own mutation testing before an independent
  reviewer broke it. The lesson recorded in the contract is that mutation-verifying each
  facet proves each facet, and proves nothing about whether the SET is complete.
- Decision: complete

### Iteration 7 — code review (Cody): the guard set is the deliverable, and it had a hole

- Target criterion: C-017, C-018, and two claims written in this contract that were false
- Change or investigation:
  - **HIGH-1, and it was mine twice over.** `SIGNED_ATTRS` omitted `placeholder`, and
    `innerText` excludes attribute text — so attribute-borne TEXT was unsigned. Worse, the
    strip I added to `authViews.test.ts` so the constant `placeholder="you@yourchurch.org"`
    would not trip `fullAddress` had no leading boundary, so it also matched the BOUND form
    `:placeholder="…"` and removed it before the ban could look inside. One line —
    `:placeholder="email.startsWith('nobody') ? 'This address has no account' : '…'"` —
    passed all fifteen facets and `npm test`, putting a sentence stating registration
    status on screen. Signed `placeholder`/`title`/`alt`/`value` plus `document.title`
    (which lives in `<head>`, outside the facet's walk), and narrowed the strip to static
    placeholders only.
  - **MEDIUM-1.** The `<ID>` collapse ran over every signed attribute including `class`,
    and `/field-[a-z0-9]+/` matches `field-error` (red) and `field-hint` (muted) — both
    shipping in `FormField.vue`. Identical copy in two different colours normalised to the
    same string. Scoped the collapse to ID-referencing attributes only and anchored the
    pattern to `FormField`'s generator shape (7-9 base36 characters), so a semantic class
    name cannot match it even there.
  - **MEDIUM-2.** The email mask was unanchored and greedy over `/` and `?`, so
    `/signin?u=a@b.com` and `/support?u=a@b.com` both collapsed to `<EMAIL>` —
    re-encoding the exact address-keyed-`href` leak the facet was created to catch.
    Restricted the local part to characters that cannot appear in a path separator.
  - **LOW-1 / LOW-2.** The transport's address test had no `codeIsIntact` call, and
    `codeIsIntact`'s floor was ABSOLUTE (`length > 150` — 1.3% of `SignUpView.vue`), so it
    could not notice an over-strip removing 95% of a file. Replaced with a proportional
    floor (22%, against measured real ratios of 30.2%-65.8%) plus a per-export anchor, so
    a deletion that takes out the top of a file is named rather than merely measured.
  - **LOW-3.** Two comments overclaimed against the code directly beneath them: "every
    timer is armed from a module CONSTANT" (the whitelist permits `options.timeoutMs`, and
    one timer uses it) and "a transport that cannot name an address cannot branch on
    registration status" (it receives the address in `variables` and the outcome in
    `envelope.errors`, so it could branch on either without writing "email"). Both
    corrected to what the assertions actually buy. The address-inspection ban now also
    covers the auth-path modules, closing the `account.ts` gap.
- Verifier executed: Cody's three mutations, one per equivalence group.
- Result: all three FAIL, each caught by `attrs` alone — `placeholder=This address has no
  account`, `href=/signin?u=<EMAIL>` versus `href=/support?u=<EMAIL>` with the path now
  surviving the mask, and `field-error` versus `field-hint`. The placeholder leak was
  caught independently by the un-blinded inspection ban in `npm test`. His comment-strip
  regression is caught by the proportional floor at his exact number: 14.6% (2190/15041).
  All mutants reverted; views byte-identical to the commit.
- New evidence: this is the fourth guard on this branch that read broader than it was, and
  the second where MY OWN accommodation created the hole — the placeholder strip was added
  to stop a false positive and silently removed a true one. An exception carved into a
  guard to make it pass is the thing to re-examine first.
- Decision: complete

### Iteration 8 — four-reviewer round 2: the guards enumerated syntax where they needed to observe behaviour

- Hypothesis under test: that the round-1 guard set covered what it claimed, and that the
  controls vouching for it were alive.
- Verifier executed: the four review reports on PR #17 (2 High, ~7 Medium, ~9 Low), then
  every finding re-derived here and every fix mutation-verified before being claimed.
- Result: **both halves of the hypothesis were false, and they share one root cause.**
  - **The bans enumerated SYNTAX.** Four leaks passed both gates: Cody's helper extraction
    onto a parameter name (`looksRegistered(value)`), Sana's computed `:placeholder` keyed
    on the typed address, Quinn's inline-`style` colour oracle in the settled state, and
    Quinn's in-flight `au-note` in a window nothing sampled. `INSPECTORS` was a ten-name
    whitelist missing `split`, `toLowerCase`, `replace`, `at` and `.length`; `SIGNED_ATTRS`
    was a twenty-three-name whitelist missing `style`; `recordBranch` fired once, after
    `settle()`, and with synchronous fixtures the `submitting` state never painted at all.
  - **The controls read PRIVATE COPIES.** `authViews.test.ts` declared its regexes at lines
    149-152 and again at 179-182. Quinn deleted `startsWith|` from the first copy only,
    planted the leak, and got `npm test` EXIT=0 with the control printing `ok`. This is
    Shape 3 in `CLAUDE.md` verbatim, in a file written to remediate an earlier round.
  - **A real user-facing defect**, separate from the guards: `await router.replace(...)`
    inside the credential-failure `try`, so a rejected navigation rendered "Invalid email
    or password" over a login that had succeeded — triggered in production by a stale
    `index.html` pointing at a lazy chunk a deploy removed.
  - **Two client/server mirrors were wrong and their tests pinned the wrongness** with
    fixtures drawn from the region where the two languages already agree.
- Remediation, and how each was earned:
  - The boundary is behavioural now. Every attribute is signed, and each pair is compared
    at three moments. Re-planting all four leaks: Cody's fails pre-submit and in-flight
    `attrs`; Sana's the same; Quinn's colour oracle fails settled `attrs`; her in-flight
    oracle fails in-flight `card` and `page`.
  - Every predicate is one module-scope definition consumed by both the ban and its
    control. Re-ran Quinn's disarm — ban silenced AND leak planted — and the control goes
    RED.
  - `elapsed` is gated at a 600ms paired delta. Vera's exact mutation now fails with
    `880ms apart, over the 600ms budget. Readings: 920 vs 40`.
  - Both mirrors derive from one definition with two consumers. Flipping a verdict in
    `tests/fixtures/email-mirror.json` turns the TS test AND the Python reference RED.
- New evidence, and the thing worth carrying forward: **a whitelist is the wrong shape for
  a guard whose job is to notice ANY difference.** Round 1 extended `SIGNED_ATTRS` twice
  and `INSPECTORS` once, each time for a demonstrated leak, and each time the next reviewer
  found the next item along. The fix that ended it was not a longer list — it was inverting
  both (sign everything and normalise the two known-nondeterministic things; allow two
  members rather than ban ten methods) and moving the real guarantee to a comparison that
  does not read the source at all.
  Second: **an accommodation added to stop a false positive is the first place to look for
  a hole.** It happened twice on this branch. Round 1's placeholder strip blinded the ban to
  bound attributes; in THIS round I added `withoutStringContents` to keep prose out of the
  member ban and it blanked every Vue bound attribute — the same hole, re-made, one week
  later. It was caught only because re-planting Quinn's mutation showed `npm test` staying
  green when it had no business doing so. Mutation-verify the fix, not just the finding.
- Decision: complete

## Risks and rollback

- Risk: adding a CSRF bootstrap changes request counts seen by the existing tests and harness. Mitigated by skipping the bootstrap where there is no cookie jar (`typeof document === 'undefined'`), so the Node unit tests keep measuring exactly what they were written to measure, and by recording CSRF GETs separately from GraphQL POSTs in the harness.
- Risk: a client guard reads as a security boundary. It is not; the server authorises every request via the session cookie. Documented in the guard itself.
- Rollback: the branch is additive to `account.ts` and rewrites one view; reverting the branch restores the simulated view.
