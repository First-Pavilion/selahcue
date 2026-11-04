# Goal Contract — TASK-370

## Identity

- Goal ID: TASK-370
- Parent goal ID: NONE
- Title: Diagnose and remove evidenced autolaunch fixture spawn hazard
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: NONE
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Retain real process-spawn endpoint safety tests with actionable private error evidence and remove only a demonstrated fixture hazard.

## Baseline

Main2f4dcc25. Unchanged autolaunch.rs failed in STT CI41856346193 at stand-in spawn;461 passed/1 failed/1 ignored. Actual historical OS error was discarded and remains unknown. Separate owned branch codex/370-autolaunch-spawn-ci; STT branch frozen.

## Inputs and evidence sources

- https://github.com/First-Pavilion/selahcue/issues/370
- /private/tmp/wave2-shadow-368.md and actual failed job log.
- Actual autolaunch.rs and local_endpoint.rs source.

## Scope

### In scope

- Narrow autolaunch fixture, error diagnostics, real-spawn safety tests and evidence.

### Non-goals

- STT changes, installers, providers, GUI, workflow/dependency/lock changes, retries or deadline relaxation.

### Constraints

- Preserve production Option/fallback/privacy and private-directory/symlink-victim safety. No mocked successful spawn or skipped tests. All subprocesses finished/reaped.

### Assumptions and unknowns

- UNKNOWN: actual historical CI errno; never infer it from a later controlled reproduction.

## Dependencies and approvals

- Root expressly authorizes necessary CI correction and pending native ClickUp backfill exception. No saved In Progress claim. Root owns four reviewers/CI/merge/QA. STT Goal3/4 unchanged.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Capture actual spawn error and metadata in focused reproduction | Native/Linux controlled real exec | Exact errno/phase/existence/mode captured; past cause unknown stated | docs/delivery/evidence/370-autolaunch-spawn-ci.md | PASS |
| C-002 | yes | Fix demonstrated fixture hazard without weakening actual spawn/safety | RED negative then focused real production-path tests | Real child spawned/reaped; private stale removed and symlink victim survives; failure error retained | docs/delivery/evidence/370-autolaunch-spawn-ci.md | PASS |
| C-003 | yes | Current regression/style checks pass | Focused complete autolaunch and endpoint tests; rustfmt | exit0, no source skip/retry policy change | docs/delivery/evidence/370-autolaunch-spawn-ci.md | BLOCKED |
| C-004 | yes | Actual current CI and four independent reviews pass | Root CI/Cody/Shadow/Quinn/Vera | all PASS before merge | Root handoff | PENDING |
| C-005 | yes | Actual native ticket/start/evidence backfill saved | Root authenticated receipt | Visible correct linked ticket/comment | Root delivery tracking | PENDING |

## Verification plan

- Focused verification: controlled Linux executable writer hazard and actual spawn errors; complete autolaunch source via small module harness.
- Broader regression verification: actual local_endpoint safety tests and formatting.
- Independent verifier: Root dispatches Cody/Shadow/Quinn/Vera.
- Required environment: pinned Rust1.98.0, real native process spawn, local Linux container for platform-specific evidence; no GUI.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: a freshly written executable introduces a concrete Linux writable-file exec hazard absent from immutable shell fixtures; historical cause remains unknown.
- Change or investigation: read complete production/test source and failed log; capture controlled real Linux error before choosing correction.
- Verifier executed: controlled Linux real exec with writable descriptor and existing executable control.
- Result: actual errno26 ETXTBSY/mode0755/existing target; immutable control exits0. Historical CI errno remains unknown.
- New evidence: diagnostic script/log retained; initial tmpfs option setup error corrected before probe.
- Decision: iterate.

### Iteration 2

- Target criterion: C-002/C-003.
- Hypothesis: removing the demonstrated fixture write/exec window preserves real process assertions while retaining underlying errors aids any distinct failure.
- Change or investigation: existing executable symlink fixture; internal Result/public Option fallback; actual nonexec errno negative and metadata diagnostics. Broken /bin/true setup on macOS was diagnosed/corrected to existing /usr/bin/true. Initial nested integration harness was unsuitable for self-subprocess tests; use actual crate instead.
- Verifier executed: expected fixture contract RED, final complete focused autolaunch10PASS, actual crate endpoint integration63PASS/1FAIL/4existingignored.
- Result: focused correction PASS; C-003 BLOCKED by unchanged mode04600 macOS endpoint failure, no unrelated source fix/retry.
- New evidence: source-exact harness and real crate raw logs retained; no historical root-cause claim.
- Decision: gate-review; reserve iteration3 for independent review remediation.

## Risks and rollback

- Risks: masking environmental failure or conflating reproduction with historical cause.
- Rollback or recovery: revert scoped change; preserve raw error evidence and original safety assertions.

## Pause and escalation conditions

- Stop at max3, actual publication rejection, missing environment, or unsupported policy choice. Root owns unresolved CI disposition.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-370.md
- Validator result: pending.
- Independent verification result: pending.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: C-003 unchanged macOS mode regression; C-004 root CI/four reviews; C-005 native authenticated backfill.
- ClickUp final evidence comment: root backfill pending.
