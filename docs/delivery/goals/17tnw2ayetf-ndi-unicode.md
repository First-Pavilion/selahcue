# Goal Contract — 17tnw2ayetf-ndi-unicode

## Identity

- Goal ID: TASK-17tnw2ayetf
- Parent goal ID: NONE
- Title: NDI name validation agrees with the host Unicode scalar limit
- Role: frontend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2ayetf
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 6
- Independent verification required: yes

## Objective

An operator can disable broadcasting for a host-valid Unicode source name; client validation accepts at most64 Unicode scalars and explains length and control-character refusals separately.

## Baseline

Verified main34cc40fa app.js uses name.length<=64 and input.maxLength64, while controller.rs ndi_name_valid uses chars().count(). Forty emoji are80 UTF16 units but40 scalars. Client refuses even Broadcast OFF before invoke.

## Inputs and evidence sources

- Coordinator's complete live native ClickUp task read on29October2026, no relationships or substantive comments; task description explicitly requests scalar-aware length and distinct refusal explanations.
- app.js Screens NDI inspector; controller.rs ndi_name_valid and set_ndi_output; committed operator_headless.py behavioral gate.

## Scope

### In scope

- Client scalar length, input truncation, separate length/control messages and real DOM behavioral regression coverage.

### Non-goals

- NDI host authority, runtime-unavailable semantics, bidi/FEFF policy, normalization or provider/network behavior.

### Constraints

- Existing host controls, empty enable and duplicate-name refusal remain; no dependencies, migrations or wire changes.
- One ticket/branch; coordinator owns tracker changes, reviews, push, CI, merge and QA.

### Assumptions and unknowns

- Host-valid imported names are reachable through persisted configuration; tests exercise the shipped UI with the existing host seam.
- Native Tauri runtime is not independently exercised by the Blink gate.

## Dependencies and approvals

- User authorized implementation/review/remediation/merge/QA; coordinator dispatched this exact ticket after full live read. Tracker start evidence is coordinator-owned.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Imported40emoji source can be disabled through the actual Broadcast UI | SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py | Correct command reaches host and settled UI is off | /private/tmp/selahcue-batch20-20261029/17tnw2ayetf-green-final.log | PASS |
| C-002 | yes |64scalars accepted;65refused with length explanation; controls keep their own explanation | Same behavioral gate | Boundary and negative controls pass | Same log | PASS |
| C-003 | yes | Field does not truncate valid astral names through a UTF16 maxlength | Same behavioral gate | Actual field permits64astral scalars | Same log | PASS |
| C-004 | yes | Existing operator suite and source checks pass | Same behavioral gate; node --check app.js; Python syntax compilation; git diff --check | Gates exit0, no hidden skips | Report and logs | PASS |
| C-005 | yes | Four independent reviews and final required hosted CI pass on reviewed revision | Coordinator code/QA/security/performance reviews and CI | All required checks pass | Coordinator evidence | BLOCKED |
| C-007 | yes | Oversized names are rejected after at most65 scalar iterator reads | Instrumented actual-handler case in the full browser gate | A million-scalar name is refused with <=65 reads, no host call and length explanation | /private/tmp/selahcue-batch20-20261029/17tnw2ayetf-green-final.log | PASS |
| C-006 | yes | PR is merged and ticket QA state read back | Coordinator GitHub/ClickUp read-back | Verified merged and QA | Coordinator evidence | BLOCKED |

## Verification plan

- Focused verification: real Screens NDI controls in operator_headless.py, imported astral name, scalar boundaries and refusal messages.
- Broader regression verification: full existing operator browser gate, JavaScript/Python syntax and diff checks. The coordinator explicitly scoped local verification to the changed JS/test paths rather than a cold Tauri/Rust compile; hosted applicable CI remains mandatory.
- Independent verifier: Cody, Quinn, Vera, Shadow via coordinator.
- Required environment: macOS Chrome for DOM logic; hosted applicable CI before merge.

## Iteration ledger

### Iteration1

- Target criterion: C-001..C-003
- Hypothesis: UTF16 length and maxlength are the source of false refusal/truncation.
- Change or investigation: Add real UI regressions before implementation; inspect host scalar rules.
- Verifier executed: full committed headless gate with mandatory Chrome. Baseline scratch dist uses immutable main app.js and current tests.
- Result: corrected RED run exits1,2302checks with exactly5 intended Unicode/length failures. Two negative controls pass. Initial test revision retained a replaced config object; corrected to read the current host-seam object, then repeated baseline RED rather than hiding that fixture mistake.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2ayetf-red-corrected.log
- Decision: iterate

### Iteration2

- Target criterion: C-001..C-004
- Hypothesis: scalar-aware count, absent UTF16 maxlength and separate refusal copy close the mismatch without changing host authority.
- Change or investigation: minimal app.js edit; existing empty/duplicate/unavailable branches preserved. Full browser suite uses current production JS and restores the NDI fixture.
- Verifier executed: SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py; node --check app.js; Python syntax compilation with a writable scratch cache; git diff --check.
- Result: exit0,2302checks,0FAIL; all seven new checks and existing NDI controls pass. Syntax and diff checks exit0. An initial Python compile attempt hit sandbox cache permissions; using PYTHONPYCACHEPREFIX under/private/tmp passed, without code changes.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2ayetf-green-final.log
- Decision: handoff

### Verification scope ruling

- Coordinator explicitly requested full local JS behavioral suite and source checks for this JS-only delta, with no cold Rust rebuild. No Rust, dependency, build configuration or wire contract changed. Final applicable hosted CI remains required before merge.

### Iteration3 — independent review remediation

- Target criterion: C-007 and accurate C-001..C-003 evidence.
- Hypothesis: full scalar-array construction is unnecessary because65scalars prove refusal; a for-of loop can stop there.
- Change or investigation: accepted Vera V246-1 and Cody C20-NDI-1. Added an instrumented actual-handler test for a million-scalar name before changing production code; the unchanged array predicate read all1000000scalars, and only this new check failed (2303checks,1FAIL, plus expected exact-count drift; exit4).
- Verifier executed: full SELAHCUE_HEADLESS_REQUIRE=1 browser gate before and after the loop correction; JavaScript/Python syntax, diff and structural goal checks.
- Result: final2303checks,0FAIL,exit0; the oversized-name case reads exactly65scalars with no host call, while40/64/65astral cases and prior NDI controls pass. The loop avoids a full-name array; this bounds the length predicate, not existing input storage or trim work. Corrected the C-001 evidence pointer to the actual final GREEN log, inherited by C-002/C-003.
- New evidence: 17tnw2ayetf-review-red.log; 17tnw2ayetf-green-final.log. The prior2302-check GREEN is preserved as17tnw2ayetf-green-pre-review.log.
- Decision: handoff for scoped independent re-review and remaining gates.

## Risks and rollback

- Risks: stale DOM references across asynchronous host response; tests reacquire fields and restore fixtures.
- Rollback or recovery: revert this ticket's isolated commit.

## Pause and escalation conditions

- New product/host contract decisions or required external access go to coordinator.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2ayetf-ndi-unicode.md
- Validator result: structural PASS; completion intentionally BLOCKED by C-005,C-006
- Independent verification result: pending coordinator review
- Terminal state: BLOCKED
- Remaining failed or blocked criteria: C-005,C-006 coordinator-owned
- ClickUp final evidence comment: pending coordinator
