# Goal Contract — 17tnw2b1wpc-pipe-safe-launchers

## Identity

- Goal ID: TASK-17tnw2b1wpc
- Parent goal ID: NONE
- Title: Three additional launchers finish without inherited pipe EOF waits
- Role: frontend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b1wpc
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Marketing auth, Blink captures and native raster captures reuse the existing file-backed lifecycle, return promptly after their command exits, and refuse genuine hangs with complete cleanup.

## Baseline

Verified main c0b8f84aa801ae97ac3faf7717cc313dcc4b312b. Auth uses capture_output with90s; Blink probe/capture use60/180s; native cargo test uses capture_output with no timeout. Native protocol is cargo test visual_parity_render plus SELAHCUE_VISUAL_OUT, PNG files and index.json. No desktop screen automation is involved.

## Inputs and evidence sources

- Coordinator full live ticket/comments/dependency read: /private/tmp/selahcue-batch20-20261029/additional-live-payloads.md section17tnw2b1wpc; owner explicitly includes native capture.
- Three current callers, shared helper module contract and Rust visual_parity_render.rs.

## Scope

### In scope

- Shared existing file-backed command lifecycle, ready URL support and migration of three named callers (including the web version probe), meaningful caller regressions and the coordinator-authorized minimal CI step/documentation.

### Non-goals

- Screenshot/DOM/business assertions, rendering or wire protocols, unrelated launchers, Rust/Flutter builds or shared caches.

### Constraints

- Preserve existing Chrome flags, file callers, exit codes and failure text; true hangs never pass. No temporary executable fixture dependency; no user-data-dir/TMPDIR redirection. Native commands receive no browser flags or Chrome litter sweep. Root owns tracker, PR, CI, four reviews and merge.

### Assumptions and unknowns

- Actual pipe-hold frequency on these callers is unknown. Fakes prove mechanism; browser gates independently prove real bundles. Native build may take longer than rendering; use a documented bounded command timeout rather than the Chrome timeout.

## Dependencies and approvals

- User approved batch implementation, reviews/remediation, merge and QA. Coordinator expanded ownership to the minimal existing-workflow caller step/prerequisites, retaining runner/matrix/permissions/minute rules. Parent17tnw2b1f32 is QA and does not block. Shared worktree ownership respected; Kenji notified about auth launch-block-only ownership.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Real caller commands with completed output and inherited stderr holder finish promptly and preserve URL/flags/native env/protocol | python3 scripts/test_pipe_safe_launchers.py | Caller regression suite exits0; helpers dead/temp empty | Batch callers-final-green.log, caller-results.json | PASS |
| C-002 | yes | Real hung commands remain failures with existing caller diagnostics and no process/temp leaks | Same suite and shared self-test | Failure/cleanup positive and negative controls pass | Batch callers-final-green.log, no-sweep-mutation.log | PASS |
| C-003 | yes | Existing HTML/URL launch lifecycle, strict results and browser assertions remain intact | Shared self-test, mandatory operator/auth gates and Blink capture | Existing exact checks and captures pass | Batch operator-green.log, auth-green.log, blink-green.log, vp-selftest.log | PASS |
| C-004 | yes | Current-target integration, syntax and structural contract checks pass on frozen clean head | Python compilation; git diff --check; validator; ancestry | Exit0 and behind0 | Batch final-checks.log and report | PASS |
| C-005 | yes | Cody/Quinn/Vera/Shadow and hosted CI pass on final revision | Coordinator evidence | All pass | Coordinator report | BLOCKED |
| C-006 | yes | PR merged and linked ticket QA saved | Coordinator read-back | Merged and QA | Coordinator evidence | BLOCKED |

## Verification plan

- Focused verification: actual caller subprocess boundaries using interpreter-backed fakes; exact command/env and elapsed/cleanup assertions; genuine hang/missing results/crash controls.
- Broader regression verification: full shared launcher self-test, operator2347-check gate, complete marketing auth scenarios and actual Blink viewport/capture.
- Independent verifier: Cody, Quinn, Vera, Shadow through root.
- Required environment: Python/POSIX/macOS/Chrome, separately hosted Linux CI. No desktop automation or shared Cargo/Flutter use.

## Iteration ledger

### Iteration 1

- Target criterion: C-001,C-002
- Hypothesis: real caller boundaries expose inherited-pipe waits before migration.
- Change or investigation: add interpreter-backed actual caller regressions.
- Verifier executed: python3 scripts/test_pipe_safe_launchers.py against unchanged production callers.
- Result: expected RED8 behavioral failures: completed auth/probe/web/native wait3.1–3.5s; all4 hangs leave a live helper; native has no timeout result mapping.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2b1wpc-callers-red.log
- Decision: iterate

### Iteration 2

- Target criterion: C-001,C-002
- Hypothesis: factoring the existing lifecycle once and adding ready URL routing removes pipe EOF waits without changing assertions or native command protocol.
- Change or investigation: shared file-backed lifecycle serves HTML/ready URLs and plain argv+env; native receives no browser flags or litter sweep. Preserve60/90/180s browser limits and add a documented600s whole native-command bound. Version probe separately reproduced3.096s EOF wait, then migrated with its existing20s/unknown-on-failure policy.
- Verifier executed: actual-caller suite with completed/hung/missing/crash paths; SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py.
- Result: caller15 cases GREEN; shared process/signal/environment/strict-parser self-test and real2347 browser assertions GREEN. Test-only hang budget2s; every fake proves output flushed and helper alive beyond the assertion window before production cleanup. No direct execution of temporary scripts.
- New evidence: batch callers-final-green.log, version-red.log, operator-green.log.
- Decision: iterate

### Iteration 3

- Target criterion: C-003,C-004
- Hypothesis: existing real auth/Blink assertions and workflow validators verify compatibility independent of fixture outputs.
- Change or investigation: run real complete auth gate; authorized caller suite in existing always-run Linux workflows job/full checkout with documented pinned Pillow prerequisite; no new runner/filter/matrix/permissions or Cargo execution. Document native prebuild/cold-build limits honestly.
- Verifier executed: npm run test:states; actionlint; check_workflows.py --self-test and normal; check_ci_minutes.py; Python compilation.
- Result: workflow checks5 workflows/17 jobs and minute rules PASS; compilation PASS. Real auth gate71 scenarios/2570 checks/0FAIL and existing visual-parity self-test206 checks/0FAIL (exit0). Complete Blink catalogue14 images/0FAIL PASS (exit0); PNG dimensions, measured viewport, driver results and screenshot existence all use unchanged assertions.
- New evidence: batch auth-green.log, vp-selftest.log, workflow-selftest.log, workflow-check.log, minute-check.log, actionlint.log.
- Decision: iterate

### Iteration 4

- Target criterion: C-001,C-002
- Hypothesis: preserving full command details on TimeoutExpired keeps the existing web diagnostic contract; plain commands must not acquire Chrome litter deletion authority.
- Change or investigation: added a diagnostic assertion, observed2 expected failures for abbreviated probe/web exceptions, then restored full argv. Added a real plain-command sentinel test and enabled Chrome cleanup only in an isolated in-memory default mutation.
- Verifier executed: caller diagnostic RED; focused no-sweep mutation; final full caller suite.
- Result: diagnostic RED2 then GREEN. No-sweep mutation removes the sentinel and fails; restored plain command leaves it and removes only its private work directory. Final15 cases across5 test methods GREEN in16.410s. Complete-looking hangs prove flushed output;30s helpers cannot expire naturally during the checks; recorded processes dead and work roots empty.
- New evidence: batch command-diagnostic-red.log, no-sweep-mutation.log, callers-final-green.log.
- Decision: iterate

### Iteration 5

- Target criterion: C-003,C-004
- Hypothesis: complete real Blink captures independently verify ready file URLs, flags, screenshot dimensions and driver manifests.
- Change or investigation: capture the full declared Blink catalogue after the complete auth gate exited, keeping browser runs sequential. No native Cargo/cache use while Mika owns the shared build window.
- Verifier executed: SELAHCUE_VISUAL_REQUIRE=1 python3 scripts/vp_capture_web.py --engine blink --out /private/tmp/selahcue-batch20-20261029/17tnw2b1wpc-blink; final syntax/workflow/diff/goal/target checks.
- Result:14 real images/0FAIL, Google Chrome156.0.8078.49, exit0. Fresh mainc72ae6f7fe398040ecc8fdb6067d88d3a68f5e8f integrated as a fast-forward:4 API/deployment/goal paths only; all tested launcher/browser files retain their verified bytes. Target ancestry/behind0, syntax/actionlint/workflow/minute/structural/diff checks PASS; final source freeze and clean check recorded in report. Actual auth71/2570/0FAIL, operator2347/0FAIL and visual-parity self-test206/0FAIL are separate observed checks. Independent reviews, hosted CI and merge/QA remain coordinator-owned.
- New evidence: batch blink-green.log and blink/captures.json; final-checks.log and report.
- Decision: handoff

## Risks and rollback

- Risks: shared lifecycle refactor could disturb signal cleanup; URL support could alter file callers; native cargo command needs env and long build allowance.
- Rollback or recovery: revert isolated ticket commits.

## Pause and escalation conditions

- New product/architecture/access decisions go to root. No external actions or broad shared builds by this agent.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wpc-pipe-safe-launchers.md
- Validator result: structural PASS; completion blocked only C-005,C-006
- Independent verification result: pending root
- Terminal state: BLOCKED
- Remaining failed or blocked criteria: C-005,C-006
- ClickUp final evidence comment: coordinator owned
