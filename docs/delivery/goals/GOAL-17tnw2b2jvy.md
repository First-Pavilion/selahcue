# Goal Contract — TASK-17tnw2b2jvy

## Identity

- Goal ID: TASK-17tnw2b2jvy
- Parent goal ID: NONE
- Title: Read-only current public plan catalogue
- Role: backend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2jvy
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Serve bounded truthful public catalogue data, preserving effective prices and refusing degraded data without exposing private limits.

## Baseline

Verified prerequisite PR358 f65731dd supplies catalogue rows/internal writers but no public endpoint or staff mutations. Parent verified In Progress/start comment. Dedicated worktree/branch starts from frozen parent without modifying it.

## Inputs and evidence sources

- Root live task consolidation /private/tmp/wave2-public-catalogue-contract.md.
- https://github.com/First-Pavilion/selahcue/pull/358.
- Existing catalogue revision signals, prices, trusted-IP resolution and shared limiter.

## Scope

### In scope

- GET /v1/catalogue/plans; exact keys, current offers, weekly grants, watermark, bounded cache/queries/throttle; tests and documentation.

### Non-goals

- Staff mutations/auth/permissions, collection, deployment, usage enforcement, private output/device/NDI limits, prices chosen by code.

### Constraints

- One-ticket stacked branch; preserve frozen parent/user checkout. Decimal string prices preserve64-bit amounts; no guessed currencies/defaults. Refuse missing/malformed allowances and limiter outage. No runtime currency fetch.

### Assumptions and unknowns

- UNKNOWN actual admin E2E until separate17tnw2az0gg/staff sign-in. Service writes do not satisfy admin E2E.

## Dependencies and approvals

- Parent authorizes scope and draft publication, owns quota-limited ClickUp UI, review/CI/merge/QA.
- PR358 pending review/merge; temporary stacked PR base. Root coordinates retarget/current-main integration.
- Task17tnw2az0gg/staff sign-in blocks original admin-mutation acceptance; root disposition required.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Anonymous GET exact public data and all current offers distinguish unpriced/null/zero | pytest tests/test_public_catalogue.py | Seed, currency, temporal and privacy cases pass | docs/delivery/evidence/17tnw2b2jvy-public-catalogue.md | PASS |
| C-002 | yes | Bounded cache invalidates for actual writers and scheduled boundaries | pytest tests/test_public_catalogue.py | Writer/query/TTL cases pass | docs/delivery/evidence/17tnw2b2jvy-public-catalogue.md | PASS |
| C-003 | yes | Missing/malformed/outage data and limiter failures safely refuse; trusted IP/budgets enforced | pytest tests/test_public_catalogue.py tests/test_throttling.py | No invented data or leak; throttle cases pass | docs/delivery/evidence/17tnw2b2jvy-public-catalogue.md | BLOCKED |
| C-004 | yes | Full API migration/check/regression gate and hosted services pass | make api-check and hosted API CI | Local exit0 with service skips explicit; hosted pass | docs/delivery/evidence/17tnw2b2jvy-public-catalogue.md | PENDING |
| C-005 | yes | Actual authenticated admin mutation appears next public response | Actual admin mutation E2E after17tnw2az0gg/staff sign-in | Authorized mutation updates next response | Absent prerequisite; root disposition required | BLOCKED |
| C-006 | yes | Four independent current-source reviews pass | Parent Cody/Shadow/Quinn/Vera reports | All four PASS | Parent review handoff | PENDING |

## Verification plan

- Focused verification: real Django route, real catalogue writers/cache, deterministic time boundaries, query count and trusted-IP/limiter transport.
- Broader regression verification: install-free make api-check and actual hosted API CI.
- Independent verifier: parent dispatches Cody, Shadow, Quinn and Vera.
- Required environment: own fresh locked Python3.14/uv0.13.4 venv; SQLite/local cache locally, Postgres/Redis hosted.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: bounded projection and revision/time cache behind shared fail-closed throttle meets public read contract.
- Change or investigation: traced routes, models, revision signals and actual staff mutation absence.
- Verifier executed: structural goal validation before RED tests.
- Result: RED19 missing-route tests, then GREEN19.
- New evidence: original admin E2E remains blocked.
- Decision: iterate.

### Iteration 2

- Target criterion: C-001 through C-003.
- Hypothesis: actual proxy/security/time/query checks expose hidden boundary or compatibility mistakes before final full verification.
- Change or investigation: deep route tests, exact nginx/Vite proxy; fixture-only target selection for two protected locations; retain all security parser/assertions. Actual Node probe caught suffix-path regex bug; real writer vocabulary RED2 exposed overly strict scalar parser, fixed by using governed parser.
- Verifier executed: public/proxy suites; actual numeric writer tests; negative route regex probe.
- Result: 67 focused tests PASS. Initial full gate terminated before correction and not claimed. Fresh complete API/image/proxy verification runs under iteration3.
- New evidence: bounded cold6/warm1 queries; revision/time/TTL/degraded/limiter tests pass; no admin E2E exists.
- Decision: iterate.

### Iteration 3

- Target criterion: C-004 and final C-001 through C-003 evidence.
- Hypothesis: final frozen source passes full install-free API gate and disposable real shipping production/dev proxy plus Redis-outage HTTP rehearsal.
- Change or investigation: bounded final verifiers and docs; iteration4 is used only if actual verification exposes a further necessary correction.
- Verifier executed: make api-check; Docker shipping builds and actual HTTP rehearsal.
- Result: pending.
- New evidence: pending final logs.
- Decision: iterate.

### Iteration 4

- Target criterion: C-003 final truthful upstream-degraded behavior.
- Hypothesis: exact-location upstream fallbacks preserve machine-readable503/no-store/security headers instead of inherited missing50x404 or Vite empty502.
- Change or investigation: actual production startup404 traced to inherited error-page missing file; real dev unavailable502 RED. Scoped production named fallback repeats every security header; dev exact-route handler follows installed Vite error ordering. No API/auth/SQL/runtime or shared GraphQL error-policy change.
- Verifier executed: observed runtime404/502 RED; focused public/trust68PASS; final shipping build and API-stop/committed price-writer HTTP rehearsal.
- Result: final affected verifiers pending; retained fullAPI2408PASS/54explicit skips/57subtests and actual PostgreSQL/Redis67PASS, nginx syntax12PASS.
- New evidence: completed prior30s HTTP phase PASS with measured times, no SLA claim. Original5s observation timeout retained. Actual admin E2E remains blocked.
- Decision: gate-review when affected final checks finish; four original iterations used; root explicitly authorized one bounded continuation to maximum5, retaining this full ledger. No reset or open-ended retry is authorized.

### Iteration 5 — explicitly authorized bounded continuation

- Target criterion: final C-003 affected HTTP proof and prerequisite freshness.
- Hypothesis: after the verified parent uv-compat merge and deliberate venv/image refresh, one final uncompleted HTTP attempt with bounded PostgreSQL readiness can finish the observed proxy/writer proof.
- Change or investigation: root confirmed prerequisite0d7fbb615fe014d5d246d9ab6534e85bd11075c7 and explicitly extended maximum4to5, preserving the ledger. Normal merge only; preserve both README edits. Readiness30seconds per probe/180seconds outer bounds affect disposable setup only, never shipping/CI timeout policy.
- Verifier executed: normal parent integration; deliberate exact0.13.4 bootstrap; runtime hash parity and focused guards; source-matching API image rebuild; one final affected HTTP phase with failure diagnostics and cleanup.
- Result: exact parent merge/bootstrap/image/parity and affected69 checks PASS. Single final setup attempt FAIL: API migrations not ready within180seconds; no final HTTP assertions executed. Process reaped exit1 and task containers/network empty. Existing full2408/native67/nginx12 retained as unchanged-runtime evidence only.
- New evidence: prior final HTTP attempt failed before API creation because5second pg_isready setup timeout; task cache PONG, PostgreSQL socket not yet ready, no application assertion failure. Both prior setup and response-time observations remain recorded.
- Decision: final handoff after this one attempt, with honest blocked proof if it still fails. Further retry, source expansion or review remediation requires an explicit bounded disposition from root.

### Iteration 6 — root-authorized evidence runner observability

- Target criterion: C-002/C-003 evidence reliability only.
- Hypothesis: strict Docker receipts and explicit markers distinguish absent readiness from failed execution, preserving full migration/status/exit/OOM evidence before cleanup.
- Change or investigation: root explicitly extends SAME Goal5to7 retaining all1-5; only task-owned private runner observability plus nonzero/missing-marker shim checks. Product/API/proxy/auth/budget frozen439ca56f.
- Verifier executed: actual subprocess Docker shim17 with fullstdout/stderr, missing-marker/migration-nonzero negatives and pending/ready controls.
- Result: observer controls PASS, but embedded writer scripts were not compile-checked; iteration7 exposed an introduced indentation regression.
- New evidence: read full setup diagnosis and all four reports; no established source defect.
- Decision: iterate once to7 after checks.

### Iteration 7 — single instrumented original-bound attempt

- Target criterion: separate-process price/boundary HTTP and API-stop503/header proof.
- Hypothesis: observable shipping-image attempt proves journeys or retains exact blocker.
- Change or investigation: ORIGINAL180second setup/30second probes and requests/frozen images; no product/budget change, no eighth retry. Root owns publication disposition.
- Verifier executed: ONE shipping-image HTTP attempt, original deadlines, full observer receipts.
- Result: FAIL exit1/reaped. Migration exit0/marker observed; production seed200/security/POST403HTML/neighborsHTML/query400 completed. First grant writer command0041 exited1 IndentationError introduced by wrapping driver in main and indenting embedded multiline Python. Price/boundary/API-stop never executed; no retry.
- New evidence: full migrationstdout/stderr/exit and APIrunning/exit0/OOMfalse state captured before cleanup, plus all command/probe/HTTP receipts. Task containers/network read back empty.
- Decision: handoff after one attempt; C-005 admin E2E remains blocked separately.

### Iteration 8 — explicit correction of known runner regression

- Target criterion: C-002/C-003 remaining HTTP evidence, unchanged product scope.
- Hypothesis: restoring exact original embedded Python payload values removes the known runner-only indentation error, without deadline/source changes.
- Change or investigation: root explicitly extends SAME Goal7to8, all1–7 retained. New private runner retains oldfailedfile/receipts; AST extracts EVERY actual Docker Python-c payload, restores exact original values and compiles both. Both oldbroken payloads fail IndentationError line2 as meaningful negatives. Diff only two payload values and new receipt directory.
- Verifier executed: both actual payloads compile/equal original; both oldbroken negatives fail. Root inspected full diff/payloads then authorized ONE originaldeadline shipping attempt.
- Result: actual attempt exit1/reaped. Setup/migration0; actual separate service grant5to6 and scheduledUSD/MONTH0 price afterboundary HTTP PASS. Production/devnormalroutes/query400/Redis429 PASS. After actualAPIstop firstproductionGET timedout30.002647seconds; no503/header response, devstop proof not reached. No retry.
- New evidence: preflight payload/diff/checks plus /private/tmp/17tnw2b2jvy-iteration8-evidence fullcommand/HTTP/migration/state receipts; APIexplicitstop observedexit137/OOMfalse, not startup failure. Cleanup independently empty. Frozen product439 unchanged.
- Decision: final honest blocked handoff; no ninth iteration, staffE2E substitution or publication.

## Risks and rollback

- Risks: misleading commercial data if missing grants defaulted; stale scheduled prices if TTL alone used.
- Rollback or recovery: revert read-only route/projection/cache; no migrations/data writes.

## Pause and escalation conditions

- Do not expand staff scope; root owns blocked acceptance disposition, retarget and all independent gates.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-17tnw2b2jvy.md
- Validator result: structural PASS; completion validator intentionally not claimed because mandatory blockers remain.
- Independent verification result: parent-owned Cody/Shadow/Quinn/Vera and actual current hosted CI pending.
- Terminal state: BLOCKED (source inspection/draft handoff; no completion/merge/QA claim).
- Remaining failed or blocked criteria: C-003 actualAPIstop productionGET timedout30seconds; devstop not reached. C-005 authenticatedadmin E2E remains blocked on17gg/staffsignin; C-006 fourrefreshreviews pending. C-002 separatelycommittedprice/boundary HTTP nowPASS; current exact439hostedCI independentlyverifiedPASS. Maximum8 used under explicit5to7to8extensions; no ninth.
- ClickUp final evidence comment: parent owns UI posting.

## 2026-11-05 remediation continuation

The iterations1–8 above remain historical outcomes of their recorded source/runtime. The user explicitly requested fixes and re-review. Current work is tracked by REMEDIATION-17tnw2b2jvy-20261105.md with a new finite budget4. The prior claim that production staff login blocks merging is corrected against the actual task/ADR: actual dev-fixture admin GraphQL HTTP propagation meets this task's mutation criterion; real staff sign-in remains a production enablement gate. See current remediation evidence for actual results and still-pending CI/reviews. No historical failure is erased or retroactively passed.
