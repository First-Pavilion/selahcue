# Goal Contract — TASK-86akc46rm

## Identity
- Goal ID: TASK-86akc46rm
- Parent goal ID: NONE
- Title: Refuse oversized developer environment files without partial parsing
- Role: mobile-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akc46rm
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective
Bound the optional developer-key loader's file read and honestly reject oversized files without exporting a valid-looking prefix.

## Baseline
Origin/main34cc40fa8e8e4876f2b3d20ab3b4c63af2ceb949 reads the entire .env via std::fs::read_to_string. Existing feature, allowlist, blank-variable and secret-free diagnostics controls must remain intact. This is developer scaffolding hygiene, not a security vulnerability.

## Inputs and evidence sources
- Coordinator's full live ClickUp payload read through native ClickUp on 2026-10-29; planning/todo, unassigned, Low, no blocking relationships or substantive comments.
- selahcue-operator/src/dev_env.rs and selahcue-cloud/src/transport.rs read_capped shape.
- Team runtime and operating contract; no repository AGENTS.md found.

## Scope
### In scope
- Loader file-read bound, oversize report/advice and meaningful behavioral regressions.
- Record the selected bounded-read option rather than a deliberate exception.
### Non-goals
- No new allowlisted names, provider contracts, dependency changes or unrelated read limits.
### Constraints
- Dev-keys remains off by default; no partial parsing, content-bearing errors, process-global lock changes or secret logging.
- One ticket/branch/PR; coordinator owns external updates, independent reviews and merge.
### Assumptions and unknowns
- A 64KiB cap gives generous room for the two developer key assignments plus the existing model choice and comments; files above it must be shortened. This bounds bytes, not a special-file read duration.

## Dependencies and approvals
- Current user authorizes implementing selected delivery tickets and merging after all four reviews pass. Coordinator assigns native Rust scope despite historical ticket owner prose.
- make ci must be serialized with the coordinator; no competing performance workloads.

## Completion predicate
All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Oversized file exports no prefix or tail assignments and names file plus cap honestly | dev_env test module, oversize/midline test | all cases pass | /private/tmp/selahcue-batch20-20261029/86akc46rm-cargo-feature.log | PASS |
| C-002 | yes | Read consumes at most cap+1 bytes and accepts exact cap and ordinary files | bounded reader and existing loader tests | all cases pass | /private/tmp/selahcue-batch20-20261029/86akc46rm-green.log | PASS |
| C-003 | yes | Removing the read cap makes the bound test fail with siblings | temporary local mutation and full module rerun, then restore | mutant RED, restored GREEN | /private/tmp/selahcue-batch20-20261029/86akc46rm-mutation.log | PASS |
| C-004 | yes | Disabled default and release refusal remain correct, full regression gate passes | default/feature tests, lint and serialized make ci | exit0 | /private/tmp/selahcue-batch20-20261029/86akc46rm-make-ci.log; make-ci.exit | PASS |
| C-005 | yes | Code, QA, performance and security review pass on immutable revision | Cody, Quinn, Vera, Shadow reports | all required reviews pass | coordinator reports | BLOCKED |
| C-006 | yes | Current-head CI passes, PR merges and ticket QA status is read back | coordinator GitHub/ClickUp read-back | verified merge and exact configured QA | coordinator delivery evidence | BLOCKED |

## Verification plan
- Focused: source-linked standalone rustc module suite for quick red/green, followed by actual operator Cargo suites.
- Broader: default and dev-keys operator tests, clippy, format and serialized make ci.
- Independent: coordinator dispatches Cody, Quinn, Vera and Shadow.
- Environment: macOS pinned Rust toolchain; no real developer credentials read.

## Iteration ledger
### Iteration 1
- Target criterion: C-001.
- Hypothesis: cap+1 streaming read plus whole-file refusal prevents partial assignments while preserving ordinary file behavior.
- Change or investigation: selected bounded-read option, inspected production loader/report and existing environment-lock tests.
- Verifier executed: pending test-first regression.
- Result: pending.
- New evidence: current read_to_string is unbounded; no production edits made yet.
- Decision: iterate.

### Iteration 2
- Target criterion: C-001, C-002, C-003.
- Hypothesis: a running read cap must fail an actual consumed-byte assertion even when an unbounded reader still refuses after allocation.
- Change or investigation: added real loader mid-value oversize refusal, boundary success and counted-source read checks; then cap+1 bounded read and typed oversize advice. Never parse partial bytes. No allowlist change.
- Verifier executed: full source-linked std-only module harness, debug/dev-keys25 passed, disabled12 passed, release-profile dev-keys25 passed. Actual Cargo operator default432 passed/1 ignored, dev-keys445 passed/1 ignored. Cargo dev-keys all-target clippy -D warnings passed. Format/diff checks passed after rerunning formatter with required filesystem permission.
- Result: baseline test-first RED22/1; removing take's cap (u64::MAX) RED24/1 with consumed1048576 vs65537; restored GREEN25/25. Counter observes production-read bytes, not elapsed time or RSS.
- New evidence: logs under /private/tmp/selahcue-batch20-20261029/86akc46rm-*.log; no --exact filtering used for mutation.
- Decision: iterate; full make ci running in coordinator-approved serialized window, then coordinator owns four independent reviews and merge/QA.

## Risks and rollback
- Risks: legitimate unusually large developer files now refuse; diagnostic must explain shortening the file without echoing content. Nonregular files can still block within the small byte budget.
- Rollback: revert this PR; never change the allowlist or release refusal to resolve failures.

### Iteration 3 — broad verification before integration refresh
- Target criterion: C-004.
- Hypothesis: the byte-limit change preserves the full local gate, including default and release feature boundaries.
- Change or investigation: no production change; installed this worktree's API/marketing dependencies and ran serialized make ci with the coordinator's exclusive caches.
- Verifier executed: CARGO_TARGET_DIR=/private/tmp/selahcue-review238-target CARGO_INCREMENTAL=0 make ci.
- Result: exit0, ALL GREEN. SQLite API1411 passed/24 skipped/1 expected failure, system/migrations clean; workspace and server/encryption/cloud feature tests, operator debug/release/native matrix, headless, Flutter and all three Rust audit roots passed. Existing allowed audit warnings were printed and no waiver was added. The cached-model cold-start integration actually loaded whisper/Metal rather than returning early for absent model.
- New evidence: /private/tmp/selahcue-batch20-20261029/86akc46rm-make-ci.log and make-ci.exit. This run belongs to original target34cc40fa plus this dev_env patch. Main advanced through unrelated NDI/API PRs during the run; fresh integration and appropriate scoped rechecks are required before publication.
- Decision: iterate for current-target integration; independent reviews and delivery remain coordinator-owned.

### Iteration 4 — integrate the reviewed target advance
- Target criterion: C-004 freshness before review.
- Hypothesis: the NDI/API target changes compose with the unchanged developer loader because their production paths and dependencies do not overlap.
- Change or investigation: committed verified implementation9140fff5, then merged origin/main034fa597958a46939abe55a22d9f8269710f39d9 into74f50d2c06acbcfdfc3b61d53e803b8743f3134f. Inspected all nine changed NDI/API/goal files. The loader source is byte-identical before/after that merge; no Rust dependency or feature changed. Restored only Flutter's generated one-line SDK-floor lock change after saving its diff.
- Verifier executed: full current-target operator_headless.py; make api-check; git diff --check and origin/main ancestry/behind check.
- Result: headless2303 checks/0FAIL, exit0. Integrated SQLiteAPI1509 passed/24 skipped/1 expected failure,344.97seconds, system/migrations clean, exit0. Full native make ci evidence remains pinned to pre-integration9140fff5, not misrepresented as a repeated run on74f50d2c. Retained native scope is unchanged; NDI/API integration received these fresh checks.
- New evidence: /private/tmp/selahcue-batch20-20261029/86akc46rm-integration-headless.log and86akc46rm-integration-api.log, each with corresponding .exit0. Generated Flutter diff saved as86akc46rm-flutter-generated.diff; current lock matches target.
- Decision: handoff to coordinator for independent reviews and hosted CI; no merge or QA claim.

## Pause and escalation conditions
- Ask coordinator about new product/contract scope or environmental gate failure; stop after three materially different failed approaches without new evidence.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86akc46rm-dev-env-cap.md
- Validator result: structural PASS; completion intentionally blocked on C-005/C-006
- Independent verification result: pending coordinator
- Terminal state: BLOCKED (implementation verifiers passed; independent review and delivery pending)
- Remaining failed or blocked criteria: C-005 and C-006
- ClickUp final evidence comment: coordinator-owned
