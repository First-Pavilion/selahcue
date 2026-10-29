# Goal Contract — TASK-17tnw2b1wqc

## Identity

- Goal ID: TASK-17tnw2b1wqc
- Parent goal ID: NONE
- Title: Return remaining retry and no-store headers on shared /v1 throttle denials
- Role: backend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b1wqc
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every denial produced by the shared /v1 throttle returns the existing429 JSON body with Cache-Control:no-store and Retry-After reporting the remaining fixed window in whole seconds.

## Baseline

Verified source at ca2c415de81f23d7f515f3f036d50208c3e19677: decorator directly returns command_error_response with neither header. CacheStore integer counters have expiry but expose no TTL, and the native surface regression is a strict xfail. Root supplied the complete live ClickUp read: planning/todo, Low, related86ak5t1gw already QA, no blockers or substantive comments.

## Inputs and evidence sources

- Full live task supplied by root: /private/tmp/selahcue-batch20-20261029/api-queued-payloads.md.
- apps/throttling/services.py and decorators.py; fixed-window rollover tests and native strict xfail.
- Pinned Django6.1.2 RedisCache and LocMemCache source; generic cache API has no TTL method.

## Scope

### In scope

- Read actual counter expiry only on denial through a narrow adapter for the two configured cache backends.
- Add remaining Retry-After and no-store to shared throttle429 responses without changing keys, budget arithmetic or bodies.
- Test every currently throttled /v1 route, expiration and failures; remove resolved strict xfail.

### Non-goals

- Redesigning405/404/body errors, budgets, authentication, proxy trust, GraphQL, outage ceilings/logging.
- Cache timeout/circuit-breaker changes, dependencies, migrations or extra metadata keys.

### Constraints

- No added counter writes or process-local identity tracking.
- TTL read failure retains proven429 with bounded full-window hint, never500, allowance or leaked error detail.
- Root owns ClickUp, publication, four reviews, final hosted CI, merge and QA read-back.

### Assumptions and unknowns

- Verified only RedisCache and LocMemCache configured; custom backends use bounded full-window hint.
- Expiry may pass between denial and read; return at least one retry second without changing decision.

## Dependencies and approvals

- User authorized20-ticket implementation/review/remediation/merge/QA batch.
- Managed isolated worktree supplied by root, ticket branch cut from freshmain.
- Root owns live ClickUp writes while MCP quota exhausted; no browser or credential search by Kenji.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Shared429 has remaining Retry-After and no-store with unchanged bodies/budget | pytest focused headers and native strict regression | All pass; strict xfail becomes ordinary pass | /private/tmp/selahcue-batch20-20261029/17tnw2b1wqc-focused-final.log | PASS |
| C-002 | yes | Real local/Redis expiry and read-error behavior correct | Clock/Redis/failure tests | Partial window decreases, ceil/min-one, read error remains denial | /private/tmp/selahcue-batch20-20261029/17tnw2b1wqc-postgres-redis.log | PASS |
| C-003 | yes | Existing throttle/native/activation and complete API regressions remain green | Covering modules then full API pytest | No introduced failures; SQLite and real PostgreSQL/Redis separated | /private/tmp/selahcue-batch20-20261029/17tnw2b1wqc-postgres-redis.log and 17tnw2b1wqc-full-api.log | PASS |
| C-004 | yes | Clean branch includes currenttarget; system/migrations clean | diff check, Django check, makemigrations, ancestry/behind | Exit0, no migration, target ancestor and behind0 at handoff | /private/tmp/selahcue-batch20-20261029/17tnw2b1wqc-report.md | PASS |
| C-005 | yes | All four reviews pass final revision after valid fixes | Cody, Quinn, Vera, Shadow exact-head reports | Four Pass, no unresolved blocking findings | Coordinator reports | BLOCKED |
| C-006 | yes | Final CI passes, PR merges and ticket savedQA | Coordinator hosted CI/merge/ClickUp read-back | Exact revision passes, merge verified, QA persisted | Coordinator delivery report | BLOCKED |

## Verification plan

- Focused verification: regression-first header/window/failure cases, baselineRED.
- Broader regression verification: covering modules and complete API; root owns hosted CI.
- Independent verifier: Cody, Quinn, Vera, Shadow through root.
- Required environment: Python3.14/Django6.1.2; SQLite/local cache and real PostgreSQL/Redis where claimed; synthetic isolated data only.

## Iteration ledger

### Iteration1 — baseline and failing regressions

- Target criterion: C-001/C-002.
- Hypothesis: counter decision works but response has no headers and store has no expiry query.
- Change or investigation: traced five routes/two configured cache backends. Separate deadline metadata can race with counter; read actual expiry after denial instead.
- Verifier executed: pending regression-first run.
- Result: pending.
- New evidence: source and pinned Django implementation inspected. Initial contract write hit inherited sandbox boundary; authorized narrow filesystem escalation used.
- Decision: iterate.

## Risks and rollback

- Risks: narrow pinned-Django internals used because generic cache API omits TTL; pin with real backend tests. One extra bounded Redis PTTL only on denial.
- Rollback or recovery: revert ticket commit; old integer cache format unchanged, no migration.

## Pause and escalation conditions

- Stop for owner scope change, required runtime access failure, unjudgeable target overlap or three distinct failed attempts without evidence.
- Return valid findings to author and re-review, no silent changes to reviewed head.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wqc-throttle-headers.md
- Validator result: structural PASS. Completion intentionally BLOCKED only on C-005/C-006.
- Independent verification result: pending root-owned Cody/Quinn/Vera/Shadow reviews.
- Terminal state: BLOCKED on independent review and delivery; implementation verifiers passed.
- Remaining failed or blocked criteria: C-005/C-006 only.
- ClickUp final evidence comment: exact handoff supplied to root; no task mutation by implementer.


### Iteration2 — expiry and response implementation

- Target criterion: C-001/C-002.
- Hypothesis: reading the existing counter expiry after denial supplies accurate retry seconds without changing window state.
- Change or investigation: narrow actual-Redis/local-memory expiry adapter, same default cache resolved through public handler; denial headers; strict xfail removed. Existing API/handoff/ops docs describe scope, fallback and one extra bounded Redis command only on denial.
- Verifier executed: new regression baseline, focused SQLite, covering PostgreSQL/Redis, in-process constant-retry fault injection, system checks and migration check.
- Result: corrected baseline12failed/1Redis-skip; restored focused18passed/1Redis-skip; covering PostgreSQL/Redis123passed. Constant-full-window replacement of production method in a separate pytest process yielded12failed/5passed/1Redis-skip; normal source unchanged by injection. Five real-route countdown assertions all reject the mutation. System/migration/diff checks pass.
- New evidence:17tnw2b1wqc-red-corrected.log, focused-final.log, postgres-redis.log and fullwindow-mutant.log under the batch evidence directory. Initial fixture URL typo corrected before final baseline; initial psycopg setup command corrected to bundled createdb because runtime uses psycopg2. No observed failures hidden.
- Decision: iterate while complete API suite runs; independent/delivery criteria remain blocked.


### Iteration3 — complete suite and target integration

- Target criterion: C-003/C-004.
- Hypothesis: the shared response-only change preserves all API account/device/guard behavior, and the new target's Rust-only slice does not change that tested API tree.
- Change or investigation: ran complete API pytest against dedicated PostgreSQL16.2/Redis databases. Fetched and fast-forwarded mainf121aaba5b632ed5d41771f57ae4897dc8b21edd after the full run. Entire8992daa5..f121aaba delta is the reviewed dev_env Rust file and its goal; implementation/api and CI workflow are unchanged. Final cleanup adjusts prose/whitespace and test-only cache-handler access/Redis connection cleanup; no executable production behavior changed after the full run.
- Verifier executed: full API suite, target/API tree equality, then final integrated focused backend checks and static checks.
- Result: full suite1563passed, zero skipped/xfail,429.53seconds, exit0. Final integrated PostgreSQL/Redis focused19passed in4.36seconds, exit0; system checks/migrations/diff/structural validator all passed. Implementation commita7f6ff5007d67f1de6749d1c096d5611d98698c3 clean, behind0 and mainf121aaba ancestor verified.
- New evidence:17tnw2b1wqc-full-api.log and .exit, scoped target diff and final integrated checks.
- Decision: hand off for independent reviews when final checks pass; no merge/QA completion claim.
