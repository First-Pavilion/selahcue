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
| C-005 | yes | No auth failure state is a dead end — each offers a named forward action (FR-552) | `npm run test:states` | exits 0 | `forwardPathCheck` asserted on every failure scenario | PASS |
| C-006 | yes | A password shorter than 10 chars is never sent to `registerCustomerUser` | `npm run test:states` | exits 0; 0 mutations dispatched | `signup-short-password`: `NO mutation dispatched for a 9-character password` | PASS |
| C-007 | yes | No session token is written to browser storage; a hint carrying one is rejected | `npm test` | exits 0 | `tests/session.test.ts`; plus a live localStorage sweep in `signin-success` | PASS |
| C-008 | yes | The session hint alone never grants entry to a protected route | `npm test` + `npm run test:states` | exits 0 | guard calls `confirmSession` unconditionally; `account-guarded` | PASS |
| C-009 | yes | Sign-out revokes server-side, clears local state, and `/account` redirects to `/signin` afterwards | `npm run test:states` | exits 0 | `session-lifecycle`; `signout-failure` covers the failed case | PASS |
| C-010 | yes | A transport failure is never rendered as a credential failure | `npm test` + `npm run test:states` | exits 0 | `signin-unreachable`, `signup-unreachable` | PASS |
| C-011 | yes | The CSRF cookie is bootstrapped through the existing seam, and no second transport path exists | `npm test` | exits 0; one `fetch` module | `tests/accountApi.test.ts` CSRF suite; `csrfChecks()` in every scenario | PASS |
| C-012 | yes | Typecheck and production build are clean | `npm run build` | exits 0 | `vue-tsc -b && vite build`, exit 0 | PASS |
| C-013 | yes | Every flow is completable by keyboard alone; fields carry labels, `aria-invalid`, `aria-describedby`, and errors are announced | `npm run test:states` | exits 0 | autocomplete/label/aria/44px-target checks per scenario | PASS |
| C-014 | yes | No fabricated success remains — no `setTimeout`-simulated outcome, no unbacked OAuth affordance | `npm run test:states` + review | no matches | universal check `no unbacked OAuth affordance`; no `setTimeout` in the views | PASS |
| C-015 | yes | The headless suite did not shrink; its floor was raised to the new count | `npm run test:states` | exits 0, not 4 | floor 495 → 1356; 47 scenarios, 1356 checks | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

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
- Result: hypothesis held — no backend change was needed. 103 unit tests, 47 headless scenarios, 1356 checks.
- New evidence: nothing in the SPA called `GET /graphql/csrf`, so every account mutation — including on the two views that shipped earlier — was a permanent 403 in a real browser. Fixed inside the existing seam.
- Decision: iterate

### Iteration 2 — mutation verification

- Target criterion: the credibility of C-002 … C-011 themselves
- Hypothesis: a passing test proves nothing until it has been shown to fail. Seven controls were broken one at a time and the suites re-run.
- Change or investigation: (1) select `sessionToken` in the login document; (2) delete the CSRF bootstrap call; (3) persist the caller's whole object in `writeSessionHint`; (4) delete the protocol-relative refusal in `safeNextPath`; (5) branch the sign-in rejection copy on the address — the same shape as the `error@test.com` special case the simulated view had; (6) skip signup validation before submitting; (7) make the route guard return `true` for every outcome.
- Verifier executed: `npm test` for 1-4; `npm run build && npm run test:states` for 5-7.
- Result: ALL SEVEN caught, each by the suite that names it. 1-4 turned four unit suites RED. 5 was caught by the enumeration comparison, which printed the two divergent renders side by side, and independently by the banned-phrase check. 6 turned three signup scenarios RED. 7 turned `account-guarded` and `session-lifecycle` RED. The shrink guard fired as well (1335 < 1356). All mutants reverted and green restored.
- New evidence: the harness itself had a false-green path. Mutant 7 failed `vue-tsc`, so `dist/` was never rebuilt — and running the script directly served the previous good bundle: 47 scenarios, 0 FAIL, exit 0, with none of the code under test in it. Added `check_bundle_is_current()`, which compares source and bundle mtimes and exits 2; verified it refuses that exact situation.
- Decision: iterate

### Iteration 3 — a flake I introduced, and its cause

- Target criterion: C-015, and the trustworthiness of every headless result
- Hypothesis: `verify-loading` failed all 11 of its checks with `calls=0` — the view had not mounted inside its 120ms window — in the chained CI run, having passed minutes earlier. Suspected the async route guard.
- Change or investigation: `router.beforeEach(async …)` returns a promise even on its early-exit path, so vue-router awaited it on EVERY navigation, delaying first paint on all ~30 routes to serve a check only `/account` needs. Rewritten to return a plain boolean for unguarded routes and a promise only for the guarded one. Separately, `verify-loading`'s 120ms wait was implicitly asserting how fast a lazy chunk mounts; raised to 400ms, which cannot weaken the check because that scenario's scripted reply is a promise that never resolves.
- Verifier executed: `npm run build`, then `SELAHCUE_HEADLESS_REQUIRE=1 npm run test:states`, repeated.
- Result: 47 scenarios, 1356 checks, 0 FAIL, repeatedly.
- New evidence: the async guard was a real site-wide latency regression, not only a test problem. The flaky test was the only thing that surfaced it.
- Decision: complete

## Risks and rollback

- Risk: adding a CSRF bootstrap changes request counts seen by the existing tests and harness. Mitigated by skipping the bootstrap where there is no cookie jar (`typeof document === 'undefined'`), so the Node unit tests keep measuring exactly what they were written to measure, and by recording CSRF GETs separately from GraphQL POSTs in the harness.
- Risk: a client guard reads as a security boundary. It is not; the server authorises every request via the session cookie. Documented in the guard itself.
- Rollback: the branch is additive to `account.ts` and rewrites one view; reverting the branch restores the simulated view.
