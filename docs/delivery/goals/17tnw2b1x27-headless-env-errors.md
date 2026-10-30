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
| C-001 | yes | Self-test ENOSPC/EACCES returns exit2 with one-line reason/no traceback before Chrome | python3 scripts/headless_chrome.py with actual-entrypoint regressions | Environment scenarios pass | /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-final-browser-green.log | PASS |
| C-002 | yes | Explicit missing/nonexec/directory/empty/bad-shebang CHROME_BIN names variable/path and returns2or3 without fallback/traceback; valid/default discovery works | Same self-test subprocess scenarios | Invalid cases refuse and positive controls launch | Same log | PASS |
| C-003 | yes | Removing new protections makes meaningful regressions red; restored siblings pass | Focused temporary mutation runs | Expected scenarios fail; restored self-test passes | Mutation logs/report | PASS |
| C-004 | yes | Full browser and existing cleanup/signal/timeout/result contracts pass | SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py; syntax/diff/goal checks | Full measured browser count0FAIL/exit0 | /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-final-browser-green.log | PASS |
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

### Iteration 5 — review C-ENV-1

- Target criterion: C-002
- Hypothesis: positive-control executables inside TMPDIR violate the existing supported noexec-filesystem contract.
- Change or investigation: verified existing _Case.run documentation and Cody's narrow EACCES probe. Added configured/discovered positive cases that deny direct execution only from the private temporary fixture tree.
- Verifier executed: complete helper CLI self-test before fixture correction.
- Result: RED exit1 with exactly4 diagnostics, exclusively the2 noexec positive scenarios. All14 earlier scenarios and launcher siblings passed.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-noexec-red.log.
- Decision: iterate

### Iteration 6 — correct C-ENV-1

- Target criterion: C-002
- Hypothesis: an installed Python interpreter can read the fixture as an ordinary data-file argument on writable/noexec TMPDIR, matching the existing _Case pattern.
- Change or investigation: positive selection uses sys.executable and injects the fixture script as an argument only for that selected test interpreter; the real launcher, CLI error mapper and strict missing-result refusal still execute. Genuine invalid paths, execute-permission failures, bad format/shebang and allocation cases remain. No production CHROME_BIN validation or permissions changed.
- Verifier executed: complete helper CLI self-test, Python compilation and diff checks.
- Result: GREEN exit0; all16 environment scenarios (including2 noexec positives) and prior process/cleanup/signal/timeout/result siblings pass. Initial four mapping protections are byte-unchanged; prior focused mutation evidence retains its scope.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-noexec-green.log.
- Decision: iterate

### Iteration 7 — current-target integration and observed test deadline

- Target criterion: C-004
- Hypothesis: the target API header-only delta does not overlap either script, so integrate and run the final browser gate.
- Change or investigation: merged main712358a209a01d293fb4b310ebe0ca0d6d3f8846 cleanly into caed32e57f37e2a0fbf14c07074ee47baed8aa6f; source/test scripts unchanged by that8-file API integration.
- Verifier executed: complete mandatory-Chrome gate.
- Result: FAIL before the real Chrome phase: an ordinary positive CLI probe exceeded its introduced20s outer bound and uncaught TimeoutExpired escaped. Its old exception omitted configured-vs-discovery identity. No owned process remained for the exact failed root. Exact transient cause not proved.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-integration-attempt1-failure.md (observed tool-output record).
- Decision: iterate

### Iteration 8 — bounded test deadline mapping and final proof

- Target criterion: C-004
- Hypothesis: align the test-only outer deadline with the existing120s _Case policy, covering the unchanged90s launcher plus cleanup, and make timeout failures named rather than tracebacks.
- Change or investigation: instrumented all16 CLI cases and child spawn/wait phases. All pass; fake positive programs exit about0.07s after spawn, total2.4–4.0s mostly before spawn; a missing-path/no-browser case takes10.143s. No recursive gate invocation observed. Test-only TimeoutExpired now becomes a named failure in both loops; cheap OS-boundary injection verifies continuation through both case families.
- Verifier executed:16-case phase probe, timeout-mapping injection, final complete mandatory-Chrome gate, Python compilation, diff/structural checks and target ancestry/behind count.
- Result: GREEN exit0,2347browser checks/0FAIL. All16 environment scenarios, noexec controls, timeout-mapping regression and all previous process/cleanup/signal/timeout/result siblings pass. No production browser deadline or cleanup/result rule changed. Exact cause of the earlier transient20s delay remains unproven and is not represented as a fixed fixture recursion.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2b1x27-final-browser-green.log and17tnw2b1x27-cli-timing.log.
- Decision: handoff

## Risks and rollback

- Risks: child self-test recursion and unwanted real Chrome fallback; skip only the child launch-contract check in selection cases and provide controlled fake discovery. Outer real launcher/self-test still executes.
- Rollback or recovery: revert the isolated ticket commits.

## Pause and escalation conditions

- New owner decisions/access needs go to coordinator. No external actions by implementation agent.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1x27-headless-env-errors.md
- Validator result: structural PASS; completion blocked only C-005,C-006
- Independent verification result: initial Cody C-ENV-1 remediated; corrected-head four-review round pending coordinator
- Terminal state: BLOCKED
- Remaining failed or blocked criteria: C-005,C-006
- ClickUp final evidence comment: coordinator owned
