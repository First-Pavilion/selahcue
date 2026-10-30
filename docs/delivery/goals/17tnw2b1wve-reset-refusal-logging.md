# Goal Contract — TASK-17tnw2b1wve

## Identity

- Goal ID: TASK-17tnw2b1wve
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Bound framework logging of expected reset throttle refusals
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1wve
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Expected password-reset budget refusals retain their safe RATE_LIMITED response and existing one-warning-per-scope-per-minute report without per-request Strawberry tracebacks. Unexpected failures retain framework traceback logging.

## Baseline

Fresh actual main b01ce4e6860be99db2f82a71aef10c4ae229db8a instantiates plain Strawberry schemas. Guard denial warnings are already suppressed per fixed scope for60seconds, but Strawberry independently logs each resolver exception. No existing process_errors override exists.

## Inputs and evidence sources

- Full saved task17tnw2b1wve: wave2-20261029/api-qualification/17tnw2b1wve.json;0comments,0dependencies, linked original reset throttle86ak65mj5.
- guards.py spend_budget/enforce_budget_reporting_outage, account reset service/resolver call paths, existing throttle and safe error tests.
- Repository CLAUDE.md bounded-log rule and existing hosted API job.

## Scope

### In scope

- Framework error logging for actual typed expected RATE_LIMITED refusals, preserving existing scope warning suppression.
-100real refused GraphQL requests per each reset budget; same-minute suppression and next-minute reporting controls.
- Unexpected exceptions and other coded errors retain tracebacks; caller-safe envelopes, rate/security/audit behavior remain.

### Non-goals

- Reset policy/budgets/timing/identity/audit schema changes, suppressing all GraphQL errors, new attacker-keyed logging state, dependencies or held PR233 work.

### Constraints

- No local project runtime/imports/tests/install/containers/benchmarks under host paging; hosted meaningful RED and full API CI required.
- Isolated ticket branch; preserve other agents. Ordinary push/draft PR/attach and bounded diagnostic refs authorized; no force push, merge, UI/ClickUp/status/review publication/subagents.
- Parent handles ClickUp start/evidence, four independent reviews, merge and QA. Integrate fresh main before first PR.

### Assumptions and unknowns

- Runtime wrapper shape must be confirmed by hosted behavior; code string alone must not classify arbitrary unexpected errors as safe throttle refusals.
- Existing warnings remain process-local per fixed scope, as shipped; no distributed logging policy change.

## Dependencies and approvals

- User approved wave implementation, CI, independent reviews/remediation, merge and QA. Parent selected this existing ticket and delegated source/diagnostic/draft publication.
- Prior DB driver exact pin/advisory remains unchanged; DRA source frozen separately.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes |100actual refusals per reset budget produce zero framework ERROR records and at most one application warning per minute, no tracebacks | focused real GraphQL logger regression | RED exposes framework flood; corrected tests pass | wave2-20261029/api-reset-refusal-logging/red.log and green log | PENDING |
| C-002 | yes | Next window emits one warning; legitimate requests and typed response/rate/no-write contracts preserved | focused positive and boundary controls plus existing throttle suite | expected responses/log counts and unchanged audit/token rows | hosted logs | PENDING |
| C-003 | yes | Unexpected and non-throttle errors still log tracebacks even with spoofed RATE_LIMITED extension | real GraphQL failure controls | one framework error with original traceback | hosted logs | PENDING |
| C-004 | yes | Target-integrated source passes API checks,migrations,full regression | normal hosted API CI | green with prior skips preserved | immutable PR/run/raw logs | PENDING |
| C-005 | yes | Cody,Quinn,Vera,Shadow accept frozen source and remediation | parent independent reviews | all four pass with no unresolved findings | parent review receipts | PENDING |
| C-006 | yes | PR merged and exact ticket QA persisted | parent delivery readback | merge/tree and QA verified | parent delivery receipts | PENDING |

## Verification plan

- Focused: tests/test_reset_refusal_logging.py through real account GraphQL route with captured logging; existing throttle regression suites.
- Broader: full normal API hosted PostgreSQL16/Redis7/Python3.14 checks/migrations/pytest.
- Independent verifier: parent routes Cody,Quinn,Vera,Shadow.
- Required environment: hosted services; local stdlib syntax/diff/goal checks only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: typed expected throttle exceptions escape the bounded guard reporter into Strawberry default process_errors and produce one traceback per refusal.
- Change or investigation: full task and existing reset/guard/schema source read; test-only regression and positive controls will target real requests before production edits.
- Verifier executed: structural goal validation; hosted diagnostic next.
- Result: Actual hosted RED41039546303, source345418df/diagnosticbbfeed81:4behavioral failures,4positive passes in4.15s. Each budget produced100Strawberry ERROR records despite one bounded application warning. Setup/checks/migrations passed; raw red.log preserved.
- New evidence: wave2-20261029/api-reset-refusal-logging/red.log; https://github.com/First-Pavilion/selahcue/actions/runs/41039546303
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-004.
- Hypothesis: account schema can omit only original typed SafeAPIError(RATE_LIMITED) from default framework error logging, relying on existing bounded scope warning without altering result errors or other exceptions.
- Change or investigation: confirmed pinned Strawberry0.336.2 BaseSchema.process_errors logs every error. Added account-only override; default logger receives all other errors, including arbitrary exceptions with spoofed RATE_LIMITED extension. Tests unchanged from actual RED.
- Verifier executed: stdlib AST syntax, unchanged test comparison, diff and goal validation; full hosted API next.
- Result: candidate prepared; no local project runtime. Runtime final counts and boundary controls pending corrected full API gate; independent review/delivery pending.
- New evidence: api-reset-refusal-logging candidate/PR/raw normal CI evidence at handoff.
- Decision: gate-review

## Risks and rollback

- Risks: overly broad filtering could hide actual server failures; tests require original exception type plus unexpected traceback controls. Existing operator warning must remain visible and bounded.
- Rollback or recovery: revert isolated framework logging override to restore prior logging; no persistence migration or policy rollback.

## Pause and escalation conditions

- Unexpected wrapper/setup failures require diagnosis before fix; do not treat them as product RED. Escalate any reset policy or cross-ticket change to parent.
- No more than8iterations; stop after3materially different failed attempts without new evidence.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wve-reset-refusal-logging.md
- Validator result: structural validation, stdlib AST syntax and diff checks PASS.
- Independent verification result: pending.
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: hosted GREEN/full API, four reviews, merge and QA pending; meaningful RED observed.
- ClickUp final evidence comment: parent owns publication.
