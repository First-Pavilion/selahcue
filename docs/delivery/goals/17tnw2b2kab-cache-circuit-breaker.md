# Goal Contract — TASK-17tnw2b2kab

## Identity

- Goal ID: TASK-17tnw2b2kab
- Parent goal ID: NONE
- Title: Bound repeated cache outage cost with one process circuit
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b2kab
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

After consecutive cache errors, skip store calls briefly and permit exactly one recovery probe while retaining existing budget outcomes and caller policies.

## Baseline

Verified origin/main 6ef0e098 includes merged PR186 socket bounds and CACHE_URL guard PR256. Each failed budget currently touches store. Full active task payload supplied by coordinator in /private/tmp/selahcue-batch20-20261029/additional-live-payloads.md. No repository AGENTS.md found in tree or ancestors.

## Inputs and evidence sources

- Existing throttle services, guards, cache timeout tests and deployment guide.
- Coordinator owns ClickUp updates, independent reviews, CI and integration.

## Scope

### In scope

- Fixed process state, failure threshold and cooldown settings, synchronized half-open admission, stale-response fencing, tests, docs.

### Non-goals

- Celery broker circuit; broker timeout ticket is separate. No new authentication decisions or per-identity circuit maps. No schema changes.

### Constraints

- No I/O under circuit lock; preserve ALLOWED, DENIED and STORE_UNAVAILABLE hooks.
- Integrate actual merged native outage policy before final freeze; do not copy pending source.

### Assumptions and unknowns

- Operational range selected as threshold 1..100 and cooldown 0.1..60 seconds; coordinator authorized bounded technical choices.

## Dependencies and approvals

- PR186 verified merged by coordinator. Native outage task 17tnw2b1wq9 verified actually merged as d5476edde13649e8b1c4fbfc92647d07e2f9e3eb (PR261); root owns integration and all external actions.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Threshold, recovery, exactly one concurrent probe and stale responses behave correctly | pytest test_cache_circuit_breaker.py | all pass including mutation control | /private/tmp/selahcue-batch20-20261029/17tnw2b2kab-ceiling-restored.log | PASS |
| C-002 | yes | Validated tunables, bounded state, actual stalled Redis bypass in milliseconds | pytest test_cache_circuit_breaker.py | config matrix and actual socket checks pass | /private/tmp/selahcue-batch20-20261029/17tnw2b2kab-ceiling-restored.log | PASS |
| C-003 | yes | Existing auth, native and throttle behavior preserved after actual dependency merge | full API pytest and Django checks | all pass or owner disposition of baseline failures | /private/tmp/selahcue-batch20-20261029/17tnw2b2kab-report.md | PENDING |
| C-004 | yes | Four independent reviews, hosted CI and release checks passed | coordinator evidence | all four pass at frozen revision | coordinator review report | PENDING |

## Verification plan

- Focused verification: circuit tests plus mutation and timeout siblings.
- Broader regression verification: full API suite with private PostgreSQL and LocMem; actual dedicated Redis checks; Django system/migration and deployment docs.
- Independent verifier: root coordinates Cody, Quinn, Vera, Shadow.
- Required environment: Python3.14 temporary runtime, synthetic private PG database, unique cache namespace.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: three consecutive errors should stop further store access across identities.
- Change or investigation: first regression demonstrates missing bypass.
- Verifier executed: test_consecutive_errors_skip_store_across_identities on private PG.
- Result: RED; ten store calls instead of three, then GREEN after implementation.
- New evidence: baseline source has no breaker.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 and C-002
- Hypothesis: synchronized admission and response fencing retain one probe and isolate stale responses.
- Change or investigation: added clock/event/barrier controls, recovery epochs, real socket and Redis, config and HTTP degraded-ceiling checks.
- Verifier executed: test_cache_circuit_breaker.py against private PostgreSQL, LocMem and dedicated Redis.
- Result: 36 passed in 22.07s. Earlier fencing regression was RED (old error consumed new threshold), then GREEN after epoch fence.
- New evidence: actual three silent TCP Redis failures 0.698215s; subsequent 50 budgets 0.000103s, exactly three connections. Ten thousand unique failed identities retain fixed slots and three counted failures.
- Decision: iterate

### Iteration 3

- Target criterion: C-001, C-002 and C-003
- Hypothesis: tests detect absent bypass while existing healthy limiter behavior remains valid.
- Change or investigation: temporarily replaced admit with fixed token in isolated source; restored exact original in finally.
- Verifier executed: new circuit and existing throttle modules under mutation; restored modules plus deployment docs; Django check, migrate and makemigrations --check --dry-run on fresh private DB.
- Result: mutant 13 failed and 44 passed; exact source restored; current circuit/throttle/deployment docs 110 passed in 51.40s. Django system/migration checks exit zero. Full API intentionally deferred until actual WQ9 merge as coordinator directs.
- New evidence: mutation and static logs in /private/tmp/selahcue-batch20-20261029/17tnw2b2kab-*.log.
- Decision: blocked

### Iteration 4

- Target criterion: C-003
- Hypothesis: actual merged native-outage helper and policy compose with circuit skips without additional admission decisions.
- Change or investigation: fetched actual origin/main d5476edd, merged PR261, resolved services.py overlap by direct fixed CircuitOpen reporting; retained merged locked neutral/redacted helper and native-only fail-closed guard. Updated prior native outage test's expected actual cache touches from25 to3 and added same-circuit refusal/device availability/recovery/hash/log checks.
- Verifier executed: combined circuit/native/throttle/socket/deployment checks then full API against private PG and dedicated Redis or disclosed LocMem fallback.
- Result: exact restored integrated circuit/native/throttle/socket/deployment checks 297 passed in40.82s with dedicated Redis, no skips. Integrated admission-off mutation15failed60passed32.79s, source restored exactly. System check and migration drift checks exit0; expected deployment warning W001 with proxy count0.
- New evidence: actual3stalls0.659052s,50cooldown budgets0.000061s,3connections;100dedicated Redis PINGs had zero errors, maximum0.011777s. Full API starts from this frozen clean revision with PID, source fingerprints and atomic result receipts.
- Decision: iterate

### Iteration 5

- Target criterion: C-003 and Vera V263-1
- Hypothesis: the old row-ceiling regression must now expect exactly three physical cache calls while preserving eleven logical per-source checks, no extra trace-budget consultation, three rows, unchanged failure responses and a successful legitimate reset.
- Change or investigation: completed frozen abf5bbcd local full gate and exact hosted CI40885134856 both fail solely at the obsolete11store-call assertion (observed3). Local result retains source_unchanged=true,1690passed/1failed; hosted1690passed/1failed744.28s. This is the intended circuit contract change requiring a precise test correction, not an unrelated baseline failure. Bind threshold3/cooldown5 and freeze only account/circuit clocks to prevent recovery probes under runner load; retain all row/response/success checks and add exact logical-key control against a second trace budget.
- Verifier executed: whole affected customer-auth module plus circuit/native/throttle/socket/deployment siblings, admission-off mutation with siblings and exact byte restoration, then a new durable full API run on clean descendant.
- Result: corrected regression passes all assertions; admission-disabled mutation16failed174passed66.46s including the strict11vs3control. Exact service bytes restored (SHA2564d7ace505b6819c59dc7832bad6405b3ff1bfba612f29fe155106f641b4d1afc). Whole customer-auth/circuit/native/throttle/reset/socket/deployment siblings477passed73.23s, no skips; every retained row/response/final-reset/no-extra-budget assertion executed. Both failed full receipts and hosted pr263-failed-ci.log preserved. A new full API run is pending on a clean ordinary descendant; no final green-gate claim.
- New evidence: Vera V263-1 confirms the precise combined contract gap; production circuit/concurrency probes otherwise passed.
- Decision: iterate

## Risks and rollback

- Risks: per-process fail-open capacity during outage persists by design; thresholds are technical operational bounds. Healthy slow responses below socket timeout do not trip circuit.
- Rollback or recovery: revert ticket commit; restart process clears circuit. No persisted data changes.

## Pause and escalation conditions

- Parent owns external actions and review; report exact integration conflict or unavailable service.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2kab-cache-circuit-breaker.md
- Validator result: structural PASS; completion intentionally pending
- Independent verification result: pending coordinator
- Terminal state: ACTIVE for corrected full API regression; final independent review and hosted CI pending
- Remaining failed or blocked criteria: C-003 combined full API and C-004 independent reviews/CI pending
- ClickUp final evidence comment: coordinator owned
