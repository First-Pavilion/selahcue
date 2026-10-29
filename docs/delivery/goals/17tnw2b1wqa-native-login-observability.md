# Goal Contract — 17tnw2b1wqa

## Identity

- Goal ID: 17tnw2b1wqa
- Parent goal ID: NONE
- Title: Bounded native login and throttle-denial visibility without identifiers
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b1wqa
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Native shared throttle denials and service-refused sign-ins produce useful warnings at most once per minute per known scope/event/process, without identifiers or unbounded state. Preserve all authentication and transport behavior.

## Baseline

Verified main c0b8f84a. Shared view decorator calls should_allow directly and never invokes existing guard denial reporting. Native session view catches login SafeAPIError silently; browser GraphQL calls the same login service independently.

## Inputs and evidence sources

- Full live task/status/comments/dependencies in /private/tmp/selahcue-batch20-20261029/api-queued-payloads.md section17tnw2b1wqa; selected20.md.
- Native views, shared throttle decorator/guard, existing native surface/header/guard tests and API README.

## Scope

### In scope

- Reuse guard warning suppression through fixed native-scope adapter; one aggregate native service-failure warning without request/error data.
- Native view hook, focused actual HTTP and concurrency/privacy tests, API operational documentation and this Goal Contract.

### Non-goals

- Browser GraphQL/shared login semantics, budgets, cache outage ceiling, circuit breaker, broker/email pipeline, settings or deployment logging configuration.

### Constraints

- No email/IP/password/token/fingerprint/exception data in new logs; no per-identity state.
- Five code-defined native throttle scope keys maximum and one aggregate failure timestamp, synchronized across threads.
- Preserve no-store/remaining Retry-After, JSON/content-type guards, cookies and current cache fail-open behavior.
- Root owns external actions and all four independent reviews; other agents own broker source/settings and native build caches. Do not revert others or run Cargo/UI.

### Assumptions and unknowns

- Verified technical policy permits rate-limited warnings rather than a persistent counter. Existing framework request-status logs are separate from the new application warning stream and remain unchanged.

## Dependencies and approvals

- Related86ak5t1gw is QA with no blocking dependency; live activity only creation/reporter. User approved ticket delivery with all four reviews, final CI and conditional merge/QA. Root owns live ClickUp updates.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Fifty native throttle denials and service login failures produce bounded scope-only warnings | New actual HTTP regression tests | Baseline RED; exactly one application warning per scope/event per60s | /private/tmp/selahcue-batch20-20261029/17tnw2b1wqa-focused.log | PASS |
| C-002 | yes | State is bounded and emission synchronized, clock/reset and redaction behavior proven | New concurrent/known-scope/clock/privacy tests | One emission under concurrency, fixed known keys, no identifiers | /private/tmp/selahcue-batch20-20261029/17tnw2b1wqa-focused.log | PASS |
| C-003 | yes | Preserve browser behavior, native transport guards, budgets and retry headers | Whole native surface/shared throttle/header/guards modules on PostgreSQL | All required checks pass; any environment scope explicit | /private/tmp/selahcue-batch20-20261029/17tnw2b1wqa-regression.log plus final Redis control | PASS |
| C-004 | yes | Final prose/source checks and full exact-head API CI pass | Static/Goal/diff checks plus root hosted full CI | Local static and hosted full API job pass | Root CI and local report | BLOCKED |
| C-005 | yes | Independent reviews pass after valid author fixes | Cody, Quinn, Vera and Shadow | All PASS at frozen revision | Root review reports | BLOCKED |
| C-006 | yes | Merge and linked QA status persisted | Root remote merge and ClickUp read-back | Reviewed PR merged; exact linked ticket QA | Root delivery receipts | BLOCKED |

## Verification plan

- Focused verification: meaningful HTTP RED before implementation, then scope/clock/concurrency/redaction positives and silent controls.
- Broader regression verification: whole native account, shared throttle logic/guards and retry header modules on dedicated PostgreSQL; real Redis metadata control separately if available; final hosted full API CI required.
- Independent verifier: root dispatches Cody, Quinn, Vera and Shadow.
- Required environment: supplied isolated branch, existing Python runtime, dedicated PostgreSQL test database and local-memory cache; no production access or shared cache flush.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002.
- Hypothesis: a bounded adapter to existing denial suppression plus a fixed native-failure timestamp adds visibility without changing decisions or browser behavior.
- Change or investigation: trace guard/decorator/native login paths and add failing tests before source edits.
- Verifier executed: new actual HTTP/PostgreSQL test module on main c0b8f84a before source edits.
- Result: 15 failed, 2 passed in3.75s. Nine actual native HTTP warning positives fail with zero reports; six new reporter-seam tests fail because helpers are absent. Browser refusal/success-and-precredential silent controls pass.
- New evidence: existing denial helper is thread-locked and scope-only; native integration currently absent.
- Decision: iterate.

### Iteration 2

- Target criterion: C-001, C-002, C-003.
- Hypothesis: fixed native-scope adapter reuses established denial warnings, while one synchronized timestamp safely reports service-refused sign-ins without affecting shared login behavior.
- Change or investigation: add native-only hooks, five-scope whitelist and zero-data aggregate reporter; document warning semantics and boundaries in API README. No broker/settings/account-service changes.
- Verifier executed: focused module, then complete native/throttle/guard/header regressions on PostgreSQL; final static/prose validation before freeze.
- Result: focused17 passed7.06s. Complete new/native/throttling/guards/header/docs modules181 passed1 skipped48.61s on PostgreSQL with local cache. The one existing real-Redis header test was not executed because CACHE_URL was intentionally empty; it is required separately in the final gate with an explicit unique-key Redis client and no shared flush. No API/test/README source changes after this broad gate.
- New evidence: logger accepts only fixed scope or no parameters, and native failure signal is transport-local, preserving GraphQL behavior by construction and by explicit HTTP test.
- Decision: iterate until focused/regression checks pass, then root owns full CI and all four reviews.

### Iteration 3

- Target criterion: C-003 final evidence scope and C-004 local checks.
- Hypothesis: the remaining real-Redis header control and fresh focused/docs gate close the explicit backend skip while preserving already-tested native behavior.
- Change or investigation: finalize this evidence prose before final verification; no production source or test changes. Keep the broader PostgreSQL result scoped to its original local-cache environment.
- Verifier executed: new17 observability cases plus entire53 deployment-doc guards plus existing real-Redis header metadata case, then system/migration/Goal/diff checks. Final execution receipts belong in /private/tmp/selahcue-batch20-20261029/17tnw2b1wqa-report.md to avoid tracked edits after verification.
- Result: required final gate must pass with no skip. The Redis test uses a randomized prefixed key and deletes only that key; no global shared-cache clear is run against Redis. Other selected tests use private local cache or do not clear it.
- New evidence: full local API suite is not claimed; exact-head hosted full CI and four independent reviews remain required.
- Decision: freeze only after final gate and static checks pass; no post-test tracked edits.

## Risks and rollback

- Risks: warning state is process-local, so a fleet produces up to one line per scope/event per worker per minute. Warnings report occurrence, not exact attempt totals or distinct callers.
- Rollback or recovery: revert this ticket's hooks and reporter additions; no persisted data or schema changes.

## Pause and escalation conditions

- Stop for unapproved auth/budget policy changes or source conflicts. Root owns final gates and ClickUp updates; coordinate short benchmark windows and leave reserved build caches untouched.

## Final evaluation

- Validator command: python /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wqa-native-login-observability.md
- Validator result: structurally valid; final validation after this evidence edit required. Completion remains blocked by C-004, C-005 and C-006.
- Independent verification result: pending.
- Terminal state: BLOCKED pending reviews, CI and delivery.
- Remaining failed or blocked criteria: C-004, C-005, C-006.
- ClickUp final evidence comment: parent owns external updates from author evidence.
