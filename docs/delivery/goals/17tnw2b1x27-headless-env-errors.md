# Goal Contract — 17tnw2b1x27-headless-env-errors

## Identity

- Goal ID: TASK-17tnw2b1x27
- Parent goal ID: NONE
- Title: Headless environment failures return clear infrastructure errors
- Role: frontend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b1x27
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Temporary-directory failures and explicitly unusable CHROME_BIN values produce one-line infrastructure diagnostics and exit2/3 without traceback, silent fallback or false passing results.

## Baseline

Verified maind8b296efd2e807393b0b32870464ba33cde54bf6. self_test creates its root outside error mapping; find_chrome ignores a missing explicit path, accepts directories/non-executable files, and the launch can raise uncaught OSError. Existing launcher cleanup, timeout, signal and strict result-count behavior remain required.

## Inputs and evidence sources

- Coordinator complete live task read in /private/tmp/selahcue-batch20-20261029/farah-qualified.md item3: planning/todo Low, no blocking dependencies/comments; related17tnw2b1f32 is QA.
- scripts/operator_headless.py and scripts/headless_chrome.py.

## Scope

### In scope

- Environment error mapping at existing CLI boundaries, explicit Chrome selection and behavioral regressions.

### Non-goals

- Chrome lifecycle, result grammar/counts, performance optimization, other launcher migrations, dependencies or workflow redesign.

### Constraints

- Explicit CHROME_BIN never falls back silently; valid configured/default discovery retained.
- Own this isolated branch only; no reverting others. Root owns publication/review/merge/ClickUp. No makeci/Flutter/Rust caches while Mika owns that window.

### Assumptions and unknowns

- Real CLI subprocesses exercise temporary fake executables. ENOSPC/EACCES are injected at the allocation boundary rather than filling the developer disk. Full Chrome verification is separate.

## Dependencies and approvals

- User authorized this ticket, all four reviews/remediation, merge and QA. Coordinator owns tracker actions while connector quota is exhausted and the Mac locked.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Self-test ENOSPC/EACCES returns exit2 with one-line reason/no traceback before Chrome | python3 scripts/headless_chrome.py with actual-entrypoint regressions | Environment scenarios pass | /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-browser-green.log | PASS |
| C-002 | yes | Explicit missing/nonexec/directory/empty/bad-shebang CHROME_BIN names variable/path and returns2or3 without fallback/traceback; valid/default discovery works | Same self-test subprocess scenarios | Invalid cases refuse and positive controls launch | Same log | PASS |
| C-003 | yes | Removing new protections makes meaningful regressions red; restored siblings pass | Focused temporary mutation runs | Expected scenarios fail; restored self-test passes | Mutation logs/report | PASS |
| C-004 | yes | Full browser and existing cleanup/signal/timeout/result contracts pass | SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py; syntax/diff/goal checks | Full measured browser count0FAIL/exit0 | /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-browser-green.log | PASS |
| C-005 | yes | Cody/Quinn/Vera/Shadow and final CI pass on final head | Coordinator reviews/hostedCI | All pass | Coordinator evidence | BLOCKED |
| C-006 | yes | PR merged and linked ticket QA persisted | Coordinator GitHub/ClickUp read-back | Merged revision and saved QA | Coordinator evidence | BLOCKED |

## Verification plan

- Focused verification: actual helper/operator entrypoints, OS allocation errors and selected temporary executable paths; positive discovery controls.
- Broader regression verification: complete launcher self-test and actual Chrome operator gate, syntax/diff and applicable hostedCI. No native/dependency changes or cold fullmakeci.
- Independent verifier: Cody, Quinn, Vera, Shadow through root.
- Required environment: macOS/POSIX/Python/Chrome; final Linux hostedCI.

## Iteration ledger

### Iteration 1

- Target criterion: C-001,C-002
- Hypothesis: real CLI subprocesses reproduce uncaught OSError and unwanted fallback before production edits.
- Change or investigation: add deterministic environment scenarios to existing launcher self-test.
- Verifier executed: python3 scripts/headless_chrome.py against unchanged production error mapping and selection.
- Result: RED exit1; 12 of14 CLI scenarios exposed the defect (20 diagnostic failures); valid configured/default selection controls passed.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-selftest-red.log
- Decision: iterate

### Iteration 2

- Target criterion: C-001,C-002
- Hypothesis: catch OSError at both CLI self-test boundaries and actual browser launch, and reject unusable explicit CHROME_BIN before default discovery.
- Change or investigation: explicit empty/missing/directory/non-executable paths raise a configuration error (required exit3, optional configured error exit2). Runtime image/interpreter/temp failures map exit2. One-line details escape line breaks; diagnostics name the configured variable/path. No helper lifecycle or result semantics changed.
- Verifier executed: complete launcher self-test, Python compilation and diff checks.
- Result: GREEN exit0, all14 environment scenarios plus existing launcher siblings pass.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-selftest-green.log.
- Decision: iterate

### Iteration 3

- Target criterion: C-003
- Hypothesis: removing each new protection independently makes its real CLI scenario fail without breaking unrelated categories.
- Change or investigation: temporary source mutations remove explicit selection validation, operator self-test mapping, helper self-test mapping and browser launch mapping, one at a time. A finally block restores both exact sources after each mutation.
- Verifier executed: /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-mutation-proof.py.
- Result: expected RED10/2/2/4 diagnostic failures respectively; only the relevant categories fail. Restored all14 scenarios GREEN. Strengthened allocation scenarios to additionally assert no fake Chrome launched; final full gate exercises this version.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-mutation.log.
- Decision: iterate

### Iteration 4

- Target criterion: C-001..C-004
- Hypothesis: the restored implementation preserves the complete real browser gate and all process/temp cleanup, signal, timeout and strict-result siblings.
- Change or investigation: run the complete mandatory-Chrome gate; no production/test checks skipped. Fetch currentmain remainsd8b296ef, no integration drift.
- Verifier executed: SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py; Python compilation with scratch pycache; git diff --check; structural validator; target freshness/ancestry.
- Result: GREEN exit0,2347 browser checks/0FAIL and complete launcher contract/environment scenarios PASS. Syntax/diff/structural checks pass. Target behind0.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-browser-green.log.
- Decision: handoff

## Risks and rollback

- Risks: child self-test recursion and unwanted real Chrome fallback; skip only the child launch-contract check in selection cases and provide controlled fake discovery. Outer real launcher/self-test still executes.
- Rollback or recovery: revert the isolated ticket commits.

## Pause and escalation conditions

- New owner decisions/access needs go to coordinator. No external actions by implementation agent.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1x27-headless-env-errors.md
- Validator result: structural PASS; completion blocked only C-005,C-006
- Independent verification result: pending coordinator
- Terminal state: BLOCKED
- Remaining failed or blocked criteria: C-005,C-006
- ClickUp final evidence comment: coordinator owned
