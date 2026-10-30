# Goal Contract — TASK-17tnw2b9dq6

## Identity

- Goal ID: TASK-17tnw2b9dq6
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Unsaved regenerated notes remain read-only and cannot replace accepted notes
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9dq6
- Created: 2026-10-29
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A generated draft that could not be saved or staged is explicitly reported as Not saved and shown read-only; it cannot be edited/saved over the accepted draft through an inferred transcript id.

## Baseline

Verified by source inspection at fetched main 0d3d3da8658985ad6dbb758933557dbc18df1c59: transcripts.js showGenResult falls back from a null response transcript_id to openId; renderDraftView offers Edit and saveDraftEdit sends update_sermon_note_draft with that id. save_and_describe_generated_notes reports ok true and transcript_id null when staging is refused, without an explicit unsaved flag. No runtime reproduction is yet claimed.

## Inputs and evidence sources

- Complete saved task/comments: wave2-20261029/frontend-qualification/17tnw2b9dq6-live.json; no comments or blocking dependencies.
- Related accepted-draft protection ticket 17tnw2b9af5 / merged PR235, current persist_generated_draft and response seam.
- Root and desktop CLAUDE.md; existing operator headless driver and regeneration retention tests.

## Scope

### In scope

- transcripts.js generated-draft id, edit/save eligibility and truthful unsaved feedback; inspect other openId fallback paths.
- Narrow main.rs save_and_describe_generated_notes JSON response field and focused real-store response tests, ownership confirmed by root.
- Behavioral operator browser regression for null-id staging failure, accepted edit/provenance preservation, positive controls and mutation proof.

### Non-goals

- Generation provider, persistence transaction, confirm/compare policy, provenance schema or load-to-save timing ticket 17tnw2axpt3.
- Auth tickets ka8/ka9, mobile controller or API settings changes.

### Constraints

- Isolated managed worktree, one ticket/branch/PR. Root owns ClickUp, publication, hosted verification, reviews, merge and QA.
- No local project runtime, Node/Rust builds or browser runs while host is paging. Prepare tests-only checkpoint for hosted RED before product changes.
- Preserve existing generation consent, retention, degraded/provenance and pending-confirmation behavior. No raw host error text in new notices.

### Assumptions and unknowns

- UNKNOWN: hosted behavioral and response-test RED/GREEN until executed by root.
- Portable DOM/JS behavior is tested in Chrome and WebKit; no claim of native Tauri session or full OS coverage from those gates.

## Dependencies and approvals

- User authorized next wave; root selected this independent ticket and owns UI start/status.
- Root explicitly assigned transcripts.js plus narrow main.rs reply/test ownership; Mika owns Flutter and Kenji API settings, so no concurrent Rust-file owner.
- No unresolved owner/design/native gate appears in the full saved task. Normal operator Rust/build/headless/WebKit gates remain required.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Null-id staging-failure draft is visible, explicitly Not saved/read-only and cannot send update for accepted notes | `SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py` | Named dq6 checks pass, no accepted edit/provenance change, numeric persisted control still editable | Full CI40948945941 and mutation40949416923 baseline/restored:2358 checks,0 FAIL,exit0 | PASS |
| C-002 | yes | Actual failed-stage response explicitly reports unsaved and preserves accepted data | Operator Rust regenerate_with_retention_tests | Real repository refusal yields ok true, null id, not_saved true; accepted row unchanged, successful save/stage controls pass | Diagnostic40947455308 job123706457514, notes-unsaved/rust-green1.log:28 passed,0 failed | PASS |
| C-003 | yes | Restoring null-id to openId fallback is detected by behavioral checks | Full headless run on isolated mutated dist via SELAHCUE_OPERATOR_DIST | Mutation produces named dq6 assertion failures and restored source passes | Hosted mutation40949416923 notes-unsaved/mutation.log:baseline2358/0FAIL,mutant2358/7FAIL,restored2358/0FAIL | PASS |
| C-004 | yes | Operator checks and existing browser behavior regressions pass | Normal path-filtered operator CI, Chrome headless and WebKit smoke | Required jobs exit zero on frozen source; strict check count measured, never guessed | Hosted CI links | PENDING |
| C-005 | yes | All independent reviews approve current revision | Cody, Quinn, Vera and Shadow | No unresolved blocking findings after remediation/re-review | Root consolidated review | PENDING |

## Verification plan

- Focused verification: real-store Rust reply regression plus full operator headless suite with its sibling checks.
- Broader regression verification: normal operator type/format/lint/test/build gates, full Chrome behavioral checks and WebKit engine smoke.
- Independent verifier: root coordinates Cody, Quinn, Vera and Shadow.
- Required environment: hosted Linux with required Chrome, pinned Rust/operator native libraries for Rust tests, staged create-only Tauri binary/resource placeholders and WebKit for smoke. Browser-only headless diagnostic reads committed dist and source constants without a Rust build.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 and C-002.
- Hypothesis: the existing null-id fallback enables a real Edit/Save request after a staged regeneration failed, replacing a hand-edited accepted draft while retaining its old provenance.
- Change or investigation: source trace and tests-only regression/positive controls against unchanged production.
- Verifier executed: hosted run 40946405217, browser job 123702816794, on test-only fd01fe04a49d88f300c6dde7b57f7068c969d3f8.
- Result: Actual browser assertion RED: 2358 checks, seven named behavioral failures, plus old strict count 2347 mismatch (exit 4). Accepted numeric-id Edit/Save and readable generated-content controls passed. Attempting the incorrectly exposed controls sent an update and overwrote the accepted hand-edited non-AI row. Rust response regression was still running, so no Rust production edit is authorized from this browser evidence.
- New evidence: wave2-20261029/notes-unsaved/browser-red.log; https://github.com/First-Pavilion/selahcue/actions/runs/40946405217.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 and C-003.
- Hypothesis: keeping the generated response's null id, deriving unsaved state from that id or the explicit host flag, and consuming one edit predicate for render/click/save prevents the accepted draft from being used as an inferred save target.
- Change or investigation: remove the openId fallback, add Not saved/read-only visible/live/badge states, keep unsaved content readable and independent copy actions, retain legitimate accepted editing and regeneration. The browser fixture now omits the new flag deliberately to cover the older host's real null-only shape and make restoring the id fallback detectable; the real Rust response test covers explicit not_saved. Merge current main ff7d1313 normally; its marketing advance does not touch notes files. No Rust production response edits yet.
- Verifier executed: Goal Contract structural validation, stdlib Python AST and full original baseline diff check. No local project runtime.
- Result: Static gates PASS; hosted UI GREEN and isolated fallback mutation proof pending. Exact count guard remains unchanged until corrected hosted run confirms the measured total. Rust assertion RED remains pending separately.
- New evidence: UI-only candidate commit and parent handoff; merge a34b951a8262a7a200445f8fe6bb0538467462c9.
- Decision: handoff

### Iteration 3

- Target criterion: C-002.
- Hypothesis: the existing persistence outcome already knows whether save/stage succeeded; exposing that as not_saved preserves the distinction in the actual generation reply without changing repository data or generation policy.
- Change or investigation: first inspect actual hosted Rust RED on source fd01fe04, then add only `not_saved: persist.transcript_id.is_none()` to the production JSON seam. Positive save/stage controls now require the explicit false flag. Ordinarily merge current main be3bd43576757d2963b6ef1748fe29afa1f1e622 (mobile-only advance, no notes conflict).
- Verifier executed: read notes-unsaved/rust-red.log from run 40946405217, operator job 123702816555. Goal structural, stdlib AST and full baseline diff checks; no local project runtime.
- Result: Actual Rust RED compiled and ran 28 regeneration tests: 27 passed, one failed because not_saved was Null instead of true. Numeric save/stage control passed. Corrected UI/Rust GREEN, exact corrected browser count, mutation proof, full CI and all reviews remain pending with root.
- New evidence: https://github.com/First-Pavilion/selahcue/actions/runs/40946405217, notes-unsaved/rust-red.log and the narrow response change.
- Decision: handoff

### Iteration 4

- Target criterion: C-001, C-002 and C-004.
- Hypothesis: recording the corrected run's measured total will let the strict browser guard accept the added coverage without changing behavior, bounds or assertions.
- Change or investigation: read actual corrected browser and Rust logs; update the final exact check-count guard to measured 2358. Fetch latest main immediately before freeze: origin/main remains ordinarily integrated be3bd43576757d2963b6ef1748fe29afa1f1e622; API PR270 is not yet in the fetched main.
- Verifier executed: hosted diagnostic40947455308 on corrected candidate1e3b6c2d, browserjob123706457683 and Rustjob123706457514; local Goal structural, script stdlib AST and full original baseline diff check only.
- Result: Browser executed all2358 checks with zero behavioral failures, including every DQ6 assertion and saved numeric-id controls; old2347 guard alone exited4. Rust GREEN:28 passed,0 failed,409 filtered,2.03s, including explicit unsaved response and successful identity controls. C-002 PASS; browser exit-zero rerun after this guard change, isolated fallback mutation proof, full operatorCI and all independent reviews remain pending.
- New evidence: https://github.com/First-Pavilion/selahcue/actions/runs/40947455308; notes-unsaved/browser-green-attempt1.log and notes-unsaved/rust-green1.log.
- Decision: handoff

### Iteration 5

- Target criterion: C-004.
- Hypothesis: applying the exact rustfmt wrapping from the hosted failure corrects the sole failed formatting gate without changing an assertion or product behavior.
- Change or investigation: inspect notes-unsaved/full-operator-failed.log lines 1477-1488 and apply that whitespace-only assert_eq wrapping in the real-store refusal test. Record successful independent fallback mutation proof; preserve all source predicates, tests and the measured 2358 count.
- Verifier executed: hosted full CI40948945941 and mutation40949416923 on frozen38d3be3f; local full original-baseline/current-main diff checks and Goal structural validation only. No local project runtime.
- Result: The full run was NOT all green: operator Format failed solely on this assertion wrapping. Other configured gates passed, including operator tests, headless2358 and WebKit44. The isolated fallback mutation completed baseline2358/0FAIL/exit0, mutant2358/7FAIL/exit1 and restored2358/0FAIL/exit0, so C-001 and C-003 PASS. The formatting correction still needs a fresh full CI receipt; C-004 and all-review gate C-005 remain pending.
- New evidence: https://github.com/First-Pavilion/selahcue/actions/runs/40948945941 and https://github.com/First-Pavilion/selahcue/actions/runs/40949416923; notes-unsaved/full-operator-failed.log and notes-unsaved/mutation.log.
- Decision: handoff

## Risks and rollback

- Risks: making all notes read-only would mask the bug; test accepted numeric-id edit as a positive control. Unsaved notes must remain readable/copyable; accepted/pending data must not be overwritten.
- Rollback or recovery: revert this ticket's PR; no migration or accepted-data rewrite is included.

## Pause and escalation conditions

- Pause product changes until root observes actual assertion RED, not a setup/import failure.
- Escalate any newly discovered owner-level decision; preserve existing native/OS evidence boundaries.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9dq6-unsaved-regenerated-notes.md
- Validator result: PASS structural validation on 2026-10-30; no local project runtime executed.
- Independent verification result: Pending root review pipeline.
- Terminal state: BLOCKED on root-owned fresh full CI and independent reviews after the exact formatting correction; source implementation prepared.
- Remaining failed or blocked criteria: C-004 and C-005 pending; C-001, C-002 and C-003 passed their hosted verifiers.
- ClickUp final evidence comment: Root owns task publication and persisted QA readback after merge.
