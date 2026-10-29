# Goal Contract — TASK-17tnw2axpq3

## Identity
- Goal ID: TASK-17tnw2axpq3
- Parent goal ID: NONE
- Title: Verify persisted sermon drafts outside async runtime workers
- Role: mobile-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2axpq3
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective
Loading a persisted sermon-note draft re-verifies scripture addresses on a blocking worker while retaining the existing loaded-draft result and recovery behavior.

## Baseline
Verified origin/main f121aaba5b632ed5d41771f57ae4897dc8b21edd: async load_sermon_note_draft calls sermon_note_draft_json inline after reading the authoritative backend and best-effort transcript segments. That codec invokes CPU-bound verify_scriptures. Existing generation paths use tauri::async_runtime::spawn_blocking.

## Inputs and evidence sources
- Coordinator's full native ClickUp read, 2026-10-29, saved in /private/tmp/selahcue-batch20-20261029/native-queued-payloads.md. Planning/todo, no blocker, related QA ticket86akgqdwc, no substantive comments.
- Operator main.rs command, codec, success builder, real DB-backed retention fixtures and existing spawn_blocking sites.
- Mobile skill, team runtime, operating contract; no applicable repository AGENTS.md found.

## Scope
### In scope
- Offload the loaded-draft CPU conversion using existing Tauri blocking runtime.
- Test actual runtime placement, verified JSON result, absent/error recovery and persistence retention.
### Non-goals
- No other reload/edit/generation path, verification bounds, provider, public API, dependencies, scanning algorithms or mobile UI change.
### Constraints
- Move owned draft and segments into the worker; do not move State or locked guards into it. No detached mutation, transcript reread or regeneration.
- Keep worker errors content-free and recoverable. Coordinator owns tracker, PR, four reviews, CI, merge and QA.
### Assumptions and unknowns
- Device/native UI navigation, battery, permissions, signing and offline network behavior are not changed by this host-side pure conversion; no device acceptance is required for those untouched surfaces.
- Blocking jobs already started cannot be forcibly aborted; this matches existing Tauri blocking patterns, and this task adds no persistence side effect or new concurrency cap.

## Dependencies and approvals
- Current user approves selected tickets, implementing agents, four independent reviews, remediation and merge/QA. Coordinator explicitly assigned this ticket.
- Exclusive released Rust caches available; coordinate make ci and Flutter/headless use with parent.

## Completion predicate
All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Real loaded-draft command never runs codec on its async caller thread | current-thread runtime placement regression and inline mutation | baseline/mutant fail, worker passes | /private/tmp/selahcue-batch20-20261029/17tnw2axpq3-focused.log | PASS |
| C-002 | yes | Loaded result preserves verification, labels and timestamps; failed/absent loads recover without modifying draft | real DB-backed command tests plus existing retention/codec tests | all tests pass | /private/tmp/selahcue-batch20-20261029/17tnw2axpq3-focused.log | PASS |
| C-003 | yes | Operator/core and required broad gates pass | Cargo suites, clippy, format and serialized make ci | exit0, no new failure | /private/tmp/selahcue-batch20-20261029/17tnw2axpq3-make-ci.log | PASS |
| C-004 | yes | Independent code, QA, performance and security reviews pass | Cody, Quinn, Vera and Shadow reviewed frozen revision | four passes | coordinator reports | BLOCKED |
| C-005 | yes | Exact-head hosted CI passes, PR merges and linked task QA is read back | coordinator GitHub/ClickUp verification | merge and QA confirmed | coordinator delivery evidence | BLOCKED |

## Verification plan
- Focused verification: test first real command runtime placement; existing codec/retention and failure recovery.
- Broader regression verification: full operator default/feature suites, core workspace, clippy/format and serialized make ci.
- Independent verifier: coordinator dispatches four distinct reviewers.
- Required environment: macOS pinned Rust toolchain and existing native build cache; no live provider/credentials.

## Iteration ledger
### Iteration 1
- Target criterion: C-001 and C-002.
- Hypothesis: moving the owned loaded draft and segments into spawn_blocking preserves output while keeping codec calls off the current-thread async caller.
- Change or investigation: source qualification complete; write deterministic test-only thread-local codec observation and real DB-backed tests before production change.
- Verifier executed: pending test-first run.
- Result: pending.
- New evidence: exact inline path confirmed at f121aaba.
- Decision: iterate.

### Iteration 2
- Target criterion: C-001 and C-002.
- Hypothesis: the loaded command can preserve the shared success JSON while offloading the same real codec.
- Change or investigation: added test-only thread-local observation of real codec entry, with direct-call positive control; real DB command checks valid/invalid scripture verdicts, exact timestamp, disclosure/provider, absence, failed read/retry and unchanged row. Then moved owned read snapshot into the existing Tauri blocking pool, reused sermon_note_view_ok_json and returned content-free unavailable response on worker failure.
- Verifier executed: test-first loaded_draft_ Cargo run, whole retention-module inline mutation, restored full default operator Cargo suite.
- Result: baseline RED2/1 at runtime placement; focused GREEN3/0; inline mutation RED25/1; restored full default GREEN434/0 with1 ignored. Fresh worktree initially needed make stage-operator-binaries before its build could run; no source fix or gate waiver for that prerequisite.
- New evidence: 17tnw2axpq3-red.log, focused.log, mutation.log, cargo-default.log under /private/tmp/selahcue-batch20-20261029/.
- Decision: iterate; full serialized make ci running on f121aaba plus this production patch.

### Iteration 3 — complete local gate on original target
- Target criterion: C-003.
- Hypothesis: all configured native feature boundaries and broad regressions remain compatible with the worker placement.
- Change or investigation: no source edits during full make ci; coordinator temporarily held the running process while freeing review capacity. Inspected final exit file and complete stage summaries before recording results.
- Verifier executed: CARGO_TARGET_DIR=/private/tmp/selahcue-review238-target CARGO_INCREMENTAL=0 make ci.
- Result: exit0, ALL GREEN on f121aaba plus this patch. SQLite API: 1,520 passed, 24 service-dependent skips and 1 expected failure; system/migrations clean. Operator default 434 / dev-keys 447 / openai-notes 438 / combined 451 / release 451 passed with 1 ignored each; stt+cloud-stt 460 passed, 2 ignored. Workspace and server/encryption/scripture/cloud debug/release checks and clippy passed. Real cached Whisper large-v3/Metal cold-start test actually loaded a 1,623.92 MB model and passed, rather than taking an absent-model early return. Headless: 2,315 checks, 0 failures; Flutter analyze clean and 380 tests passed. All three audit roots passed, with existing allowed warnings (workspace 2 / operator 4 / STT 0); no waiver added.
- New evidence: 17tnw2axpq3-make-ci.log and make-ci.exit0. Flutter generated only the unrelated SDK-floor lock edit 3.41 to 3.44; saved exact diff and restored it after asserting no other lock difference. Production main.rs SHA256 364882e1e6efcfc1cfbff1c77d31f4ef7b0787921866ac33221226170601af92 unchanged throughout.
- Decision: iterate for current merged target712358a2 integration and proportionate fresh checks; do not claim full make ci was rerun on that later head.


### Iteration 4 — merged target integration and final refresh
- Target criterion: C-003 freshness.
- Hypothesis: the reviewed Remote Control UI and API throttle-header changes compose with the unchanged Rust conversion; refresh their browser boundary and the actual native command suite.
- Change or investigation: inspected the entire 12-file, 753-insertion target delta from f121aaba to merged main 712358a209a01d293fb4b310ebe0ca0d6d3f8846. It changes Remote Control HTML/JS/headless tests, throttle expiry/headers/tests, and supporting docs/goals. No Rust source, dependency or workflow change. Committed implementation 165bebe7 and cleanly merged target into 6182909bc749d67b1f9b4ca47019ed359e7e8f8c. The production Rust file is byte-identical across the merge. No unmerged PR253 branch was integrated.
- Verifier executed: fresh mandatory-Chrome full operator_headless.py and full actual default operator Cargo suite on integrated source. Structural validator, Cargo format and diff checks after final tracked goal prose. Deployment environment docs guard also run after final prose as a proportional check of the newly integrated ops documentation.
- Result: headless 2,347 checks with 0 failures, exit0; native 434 passed, 1 ignored, exit0. These runs include the real loaded-draft runtime-placement and recovery tests. Full make ci remains honestly pinned to the original target plus native patch, rather than claimed on this later merge. Coordinator separately supplies exact hosted API 1,563-pass evidence for the merged header change; Mika did not rerun that entire API suite.
- New evidence: 17tnw2axpq3-integrated-headless.log/.exit and integrated-native.log/.exit; target-delta.diff; final validators and docs-guard log in the batch evidence directory.
- Decision: handoff frozen source for all four independent reviews and exact-head hosted CI. No merge or QA claim.

## Risks and rollback
- Risks: worker join can fail; return existing unavailable-draft shape with a fixed diagnostic. Threadpool contention is possible, with no new admission limit in this ticket.
- Rollback or recovery: revert only this ticket; worker conversion is read-only and never changes stored data.

## Pause and escalation conditions
- New product/verification-budget/concurrency policy requires coordinator decision. Stop after three materially different failed attempts without new evidence.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2axpq3-draft-scripture-worker.md
- Validator result: structural PASS; completion intentionally blocked on C-004/C-005
- Independent verification result: coordinator pending
- Terminal state: BLOCKED on independent review and delivery; implementation verification passed
- Remaining failed or blocked criteria: C-004/C-005 coordinator-owned
- ClickUp final evidence comment: coordinator-owned
