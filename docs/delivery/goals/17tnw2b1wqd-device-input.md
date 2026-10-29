# Goal Contract — 17tnw2b1wqd-device-input

## Identity

- Goal ID: TASK-17tnw2b1wqd-device-input
- Parent goal ID: SelahCue-batch20
- Title: Malformed device activation inputs produce safe JSON refusals on both database engines
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b1wqd
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Refuse control characters, non-string metadata and unknown platforms before device creation; return the existing JSON error envelope for oversized or excessively nested activation bodies.

## Baseline

Main34cc40fa has native activation str coercions, no device metadata control-character/platform allowlist, and enrollment JSON parsing catches neither RecursionError nor RequestDataTooBig. No source changes precede regression tests.

## Inputs and evidence sources

- Coordinator's live ClickUp description, four acceptance criteria, sole Quinn comment and relationships, read2026-10-29.
- Existing devices services, native platform views and activation tests; shipped Rust platform identifiers.

## Scope

### In scope

- Shared device activation validation, both native activation transports and regressions including PostgreSQL.
- Oversized body JSON error envelope and Quinn's nested JSON failure.

### Non-goals

- Email normalization, session revocation, limiter outage policy, response header policy, schema changes or unrelated tickets.

### Constraints

- One isolated worktree/branch/PR; no force push or protected branch edits.
- Coordinator owns publication, four independent reviews, merge and QA read-back.

### Assumptions and unknowns

- ASSUMED: supported activation platform identifiers follow shipped clients and existing API fixtures; enumerate evidence before choosing the allowlist.
- UNKNOWN: tracker updates are unavailable during connector quota/browser recovery; coordinator owns pending status/start comment.

## Dependencies and approvals

- Native route prerequisite86ak5t1gw is QA; no blocking dependency listed on live task.
- User explicitly authorized implementation, remediation, review and conditional merge/QA.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Control characters in activation fields are JSON400 without device/token creation on SQLite and PostgreSQL | pytest tests/test_device_input_validation.py | All control-character cases pass on both engines | 98 tests pass on SQLite and PostgreSQL16.2; 17tnw2b1wqd-green.log and 17tnw2b1wqd-postgres.log under coordinator batch evidence directory | PASS |
| C-002 | yes | Non-string fields and unknown platforms are refused without device creation | same regression module | JSON400 and unchanged device/token/audit state | Same98-case real HTTP/service suite, both engines | PASS |
| C-003 | yes | Oversized and deeply nested enrollment/account activation bodies use the JSON400 envelope | same regression module | No HTML400 or500; no device created | Same98-case suite, both engines | PASS |
| C-004 | yes | Existing API behaviors remain green | complete API suite; Django checks/migrations | All applicable tests pass; any skipped engine checks disclosed | API gate log | PENDING |
| C-005 | yes | Independent Cody/Quinn/Vera/Shadow review and final hosted CI pass before merge | coordinator final snapshot review and CI | Four domain passes and green final revision | coordinator report | BLOCKED |
| C-006 | yes | PR merge and linked task QA status verified | GitHub/ClickUp read-back | MERGED and configured QA persisted | coordinator delivery evidence | BLOCKED |

## Verification plan

- Focused verification: test-first native HTTP and direct service activation regressions; no mocked validation or database writes.
- Broader regression verification: full API pytest suite, Django check and committed migration guard.
- Independent verifier: Cody, Quinn, Vera, Shadow through coordinator.
- Required environment: Python3.14, SQLite and disposable PostgreSQL; no production data or credentials.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: validating original values in the shared activation service and handling parser/body-limit exceptions in the native JSON helper closes the observed malformed-input paths.
- Change or investigation: write representative regressions first and observe baseline failures.
- Verifier executed: pending.
- Result: pending.
- New evidence: pending.
- Decision: iterate.

### Iteration 2

- Target criterion: C-001 through C-003.
- Hypothesis: original-type preservation plus shared pre-write validation closes both transports and direct service calls without changing licence authority.
- Change or investigation: both native routes stop str coercion; both public service paths validate strings, controls, UTF-8, lengths and desktop platform identifiers before writes; enrollment reuses the guarded JSON parser and oversized-body exceptions map to existing validation envelope.
- Verifier executed: focused98-case suite on SQLite and own PostgreSQL16.2; existing activation/native/state-transition/remint covering suite; Django check and migration guard.
- Result: 98 passed SQLite;98 passed PostgreSQL in7.59s;238 passed1 expected failure in133.69s for covering suite. Expected failure is the separate429-header ticket17tnw2b1wqc. System/migration checks pass. First SQLite run had a sandbox pytest-cache-write warning; covering run used an explicit temporary cache with escalation and no warning.
- New evidence: original regression run71 failed27 passed; compact rerun reproduces that result. Disposable DB on loopback55453, Redis7 on56453; full suite has reported setup errors and a failed assertion and is still running. No full-suite pass is claimed.
- Decision: iterate.

## Risks and rollback

- Risks: platform allowlist could reject a shipped identifier; request parsing changes must preserve credential authority and privacy.
- Rollback or recovery: revert this ticket's isolated commit; no migrations or stored-data changes.

## Pause and escalation conditions

- Escalate missing platform product contract or materially incompatible client evidence; preserve unrelated email-normalization issue for its own scope.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wqd-device-input.md
- Validator result: pending.
- Independent verification result: pending coordinator.
- Terminal state: pending.
- Remaining failed or blocked criteria: independent reviews/CI/delivery.
- ClickUp final evidence comment: pending coordinator access.
