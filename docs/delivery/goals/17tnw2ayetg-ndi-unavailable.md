# Goal Contract — 17tnw2ayetg-ndi-unavailable

## Identity

- Goal ID: TASK-17tnw2ayetg
- Parent goal ID: NONE
- Title: Explain the saved-on NDI preference when this host cannot broadcast
- Role: frontend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2ayetg
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 5
- Independent verification required: yes

## Objective

The checked but disabled Broadcast control explains that its preference is saved on while broadcasting is unavailable now, without changing that preference or claiming current transmission.

## Baseline

Base main034fa597958a46939abe55a22d9f8269710f39d9: app.js preserves cfg.ndi_enabled in the toggle and disables it when ndi_available is false, but its warning is identical for saved-on and saved-off states. The scalar validation fix from PR246 is already on main and remains untouched.

## Inputs and evidence sources

- Complete live native ClickUp read supplied by coordinator: planning/todo, Low, unassigned, no dependencies or substantive comments; MR field blank. Native UI currently locked; coordinator owns tracker updates pending manual unlock.
- Shipped Screens NDI inspector app.js and full committed operator_headless.py suite.

## Scope

### In scope

- Existing NDI status copy and actual DOM regressions for saved-on/off crossed with available/unavailable.

### Non-goals

- Transport, persisted settings, host authority, wire shapes, availability hot-switch contract, roles, new design system or scalar-validation changes.

### Constraints

- Keep the saved checkbox state and existing runtime-unavailable disabling; no host commands during rendering.
- Shared repository: only this ticket branch; no reverting others; coordinator owns publication/review/merge/QA.

### Assumptions and unknowns

- ndi_available is constant per host startup. Fixture changes cover separate startup-state combinations, not a newly supported runtime capability transition.
- Browser gate uses the existing mocked host seam; physical NDI/native webview execution is outside local evidence.

## Dependencies and approvals

- User authorized implementation and four independent reviews, remediation, merge and QA. Coordinator dispatched this exact ticket; tracker actions remain coordinator-owned.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Saved-on/unavailable renders checked and disabled with a truthful saved-preference and no-current-broadcast explanation | SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py | Actual DOM case passes | /private/tmp/selahcue-batch20-20261029/17tnw2ayetg-green.log | PASS |
| C-002 | yes | Other three availability/preference combinations retain accurate controls and status | Same full browser gate | All four combinations pass | Same log | PASS |
| C-003 | yes | Rendering retains preferences and sends no NDI mutation; live status semantics preserved | Same full browser gate | Fixture, command-count and status-role controls pass | Same log | PASS |
| C-004 | yes | Full local operator JS suite and syntax/diff checks pass | Same gate; node --check app.js; Python compilation; git diff --check | Exit0 and zero failures | Report and logs | PASS |
| C-005 | yes | Independent Cody/Quinn/Vera/Shadow reviews and final applicable CI pass | Coordinator review and hosted CI | All pass at final revision | Coordinator evidence | BLOCKED |
| C-006 | yes | PR merged and ticket QA persisted | Coordinator GitHub/ClickUp read-back | Verified merged and exact configured QA | Coordinator evidence | BLOCKED |

## Verification plan

- Focused verification: real inspector controls/status for four startup combinations; no command or preference mutation.
- Broader regression verification: full operator JS browser gate, source syntax/diff checks; final applicable hosted CI. No cold Rust build for this JS-only change, per coordinator's explicit scope ruling.
- Independent verifier: Cody, Quinn, Vera, Shadow via coordinator.
- Required environment: Chrome DOM execution on macOS, existing host seam; hosted applicable CI before merge.

## Iteration ledger

### Iteration1

- Target criterion: C-001..C-003
- Hypothesis: append a saved-on explanation only to the unavailable-on state, preserving the existing status branch and authority.
- Change or investigation: add actual DOM matrix regression before production edit.
- Verifier executed: SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py against unchanged production JS.
- Result: RED exits4,2315checks with exactly one behavioral failure: unavailable/saved-on copy omits the saved preference/no-current-broadcast explanation. All11other matrix assertions pass; exact-count drift is expected before updating the measured count.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2ayetg-red.log
- Decision: iterate

### Iteration2

- Target criterion: C-001..C-004
- Hypothesis: conditionally append the saved-on/no-current-broadcast sentence only in the existing unavailable branch.
- Change or investigation: two-line status copy edit; retained original warning prefix, checkbox preference, host disabling, scalar validation, role=status and all authority paths.
- Verifier executed: full mandatory-Chrome browser gate; node syntax; Python syntax with scratch cache; git diff --check; structural Goal Contract validator.
- Result: GREEN exits0,2315checks,0FAIL. All12new matrix assertions and the prior Unicode/empty/duplicate/unavailable controls pass. Syntax/diff/structural checks exit0. No Rust source/dependency/build changes and no cold Rust suite, per explicit coordinator verification scope.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2ayetg-green.log
- Decision: handoff

## Risks and rollback

- Risks: stale test DOM during async polling; wait for actual case controls before assertions and restore original fixture.
- Rollback or recovery: revert the isolated ticket commit.

## Pause and escalation conditions

- New product/host behavior or access needs go to coordinator. No UI retry until manual unlock.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2ayetg-ndi-unavailable.md
- Validator result: structural PASS; completion blocked by coordinator rows C-005,C-006
- Independent verification result: pending coordinator
- Terminal state: BLOCKED
- Remaining failed or blocked criteria: C-005,C-006
- ClickUp final evidence comment: pending coordinator/manual unlock
