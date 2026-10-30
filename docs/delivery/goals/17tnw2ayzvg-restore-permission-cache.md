# Goal Contract — TASK-17tnw2ayzvg

## Identity

- Goal ID: TASK-17tnw2ayzvg
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Restore autosave respects the latest confirmed edit permission
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2ayzvg
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A Remote viewer most recently confirmed can_edit:false never gets a Restore last autosave banner after a failed plan open, while true and never-known/unknown viewers retain the explicitly approved offer and asynchronous stale/delayed lookups cannot reintroduce a false banner.

## Baseline

Fresh actual main2412390655b5e04591e59482c116295f676abe51 includes AXPP3 and measured2536 headless checks. app.js planRenderLoadFailed clears current permission chrome then unconditionally requests/publishes autosave slots, with no last-confirmed Boolean permission cache. Server RBAC is authoritative and already denies unauthorized RestoreAutosave; this narrow UI gap must not be mistaken for a backend grant.

## Inputs and evidence sources

- Complete fresh frontend-qualification/17tnw2ayzvg-dispatch-live.json: planning/todo, null parent, no dependencies, zero comments; explicit whole AC retains unknown offer.
- Qualification report/current app.js Plan render/poll/failure paths and existing headless seams; original linked86ak8467m feature is implemented, historical parent is not new scope.
- Frozen WAVE3 selected20 owner sequence2, root explicit dispatch and frontend/Goal/repository guidance.

## Scope

### In scope

- Existing Plan module permission hint: module-level null default, updated only from real Boolean can_edit in confirmed successful views.
- Narrow Restore availability/publication/late-response behavior, real browser negative/positive controls, Goal and measured count.

### Non-goals

- Fabricating a permission from missing/malformed viewer, altering explicit unknown-offer policy, replacing server RBAC, or cheap Local fetch-skip-only partial completion.
- Undo, edit-palette, Local/Remote authority, host persistence/protocol, unrelated surfaces/native/Rust changes.

### Constraints

- One new managed isolated worktree/branch/PR, preserve other agents; shared headless DRIVER serialized. No staging/reverting others or subagents/force push/protected edits.
- No local project runtime/import/install/build/browserbench/containers. Hosted real browser verification; tiny stdlib/source/Git/structural preparation only locally.
- Tests-only actual behavioral RED before production. Preserve existing Undo/edit/palette and all sibling assertions; no ignored failures/retry wrappers/guessed counts.
- Author owns bounded exact-parent workflow-only diagnostics/ordinary push/draft/body-file/immediate attach. Root owns ClickUp/start, all four reviews/remediation routing, merge and QA. No third unit until dispatch.

### Assumptions and unknowns

- VERIFIED: whole task demands the real Remote false case; unknown silence may not be converted to a restriction or a grant of server authority.
- UNKNOWN: exact asynchronous boundaries and real RED/count/current CI until inspected/executed. Cache update/publication must account for confirmed demotion and stale responses.

## Dependencies and approvals

- AXPP3 actually merged24123906 and QA persisted; completed child exported separately with completion validator PASS, no tracked evidence churn.
- User authorizes selected wave workflow; root confirms this fresh standalone ticket and posts In Progress/start after child validation.

## Completion predicate

All mandatory rows must PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Most recently confirmed false Remote viewer never sees Restore on failed open; true/unknown controls retain offer | Actual successful render followed by failed open and autosave reply | False no banner/action, true and never-known still offer; no fabricated viewer | Hosted RED/GREEN real DOM | PENDING |
| C-002 | yes | Cache defaults null and changes only for confirmed real Boolean; late/delayed lookup cannot restore a forbidden/stale banner | Browser demotion/promotion, missing/malformed and held reply ordering controls | Latest confirmed value governs; stale async response cannot publish false offer | Hosted full controls/raw | PENDING |
| C-003 | yes | Existing server/Undo/Local/edit-palette behavior and real cache/gate sensitivity remain protected | Full siblings and cache/gate mutants with complete restoration | Targeted intended failures on mutants, positive controls preserved, restored clean | Current parent/blob/manifest/raw proof | PENDING |
| C-004 | yes | Normal affected CI passes with exact actual measured count | Normal full configured operator/Rust/native/WebKit jobs | Applicable gates succeed; skipped/unexecuted domains remain explicit | Official current CI raw/receipt | PENDING |
| C-005 | yes | Four independent current-source reviews pass | Root-owned Cody/Quinn/Vera/Shadow | No unresolved blocking finding after remediation/re-review | Root consolidated reports | PENDING |

## Verification plan

- Focused verification: real successful render/poll, actual failed open and delayed slot replies, seeded Remote false/true/unknown transitions and stale response controls through existing seams.
- Broader regression verification: full operator headless siblings, meaningful cache/gate mutations and identical restoration, normal selected CI.
- Independent verifier: root coordinates all four roles and final tree/merge/QA receipts.
- Required environment: hosted Chrome and normal pinned Linux/WebKit; no actual native/physical/macOS/Windows acceptance inferred.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-002.
- Hypothesis: failed-open Restore currently ignores most recent confirmed false and late slot replies can publish obsolete offers; real successful-render/failure controls can expose this without inventing permission data.
- Change or investigation: trace existing permission/render/poll/failure hooks in fresh actual-main worktree; prepare tests-only controls, no production cache/gate edits before actual RED.
- Verifier executed: Goal structural and stdlib/static preparation checks, followed by frozen tests-only hosted RED.
- Result: Actual hosted41119095716 on tests-only40c494b9 ran2552 checks with8 intended behavioral failures; old2536 count mismatch is separate. The16 new actual DRIVER records contain8 PASS and8 FAIL, with no other behavioral failure.
- New evidence: restore-permission/red-job.log, red-receipt.json, red-object-proof.json and red-classification.json. Unknown offer/action, true/malformed-true, failure chrome, held lookup premise, visible-offer premise and no-live-command controls PASS.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-004.
- Hypothesis: remembering only actual Boolean viewer verdicts from successful host views, removing offers on false, and checking the exact failed-open node before async publication prevents the observed forbidden and superseded offers without fabricating permissions.
- Change or investigation: add one bounded module-level null/Boolean hint using the existing planViewer reader; feed the normal view render and Plan builder paths, suppress/remove false offers and reject replies whose originating failure node has been replaced. Preserve server RBAC and existing current-view chrome. Pin the actual measured2552 count; DRIVER/STUB/CSS_SRC assertions remain byte-identical to the observed RED.
- Verifier executed: stdlib AST, baseline diff check, structural Goal validator; current-source hosted full sibling/mutation and normal configured CI receipts to follow.
- Result: Static preparation PASS; runtime and independent review gates pending, no green claim yet.
- New evidence: restore-permission current candidate/object receipts and hosted raw logs.
- Decision: iterate

## Risks and rollback

### Iteration 3 — CODY-AYZVG-01 review regression

- Target criterion: C-002, latest genuine host confirmation survives cached UI rendering.
- Hypothesis: a false poll during a Remove dialog updates the hint but intentionally leaves planLastView true; Cancel and selection/deselection replay that snapshot through planRenderBuilder and incorrectly publish a new true hint.
- Change or investigation: add the real selected-row Remove dialog, actual false poll, Cancel, selection and blank-list deselect regression plus modal/stale-snapshot/no-new-view premises. Existing AYZVG fixture views now feed the normal successful full-view consumer before the Plan renderer, distinguishing a confirmed view fixture from UI-only replay; all existing assertions retained. Shipping implementation unchanged from cc02f357 while this new RED runs.
- Verifier executed: tests-only stdlib AST, production-tree identity and baseline diff check; bounded hosted actual regression RED.
- Result: Pending actual hosted observation; prior source CI/mutations do not close this review finding.
- New evidence: restore-permission/review-red receipt, object proof and actual raw log.
- Decision: iterate

- Risks: treating absent/malformed permission as false/true, cache not updated by actual polls, stale async lookups reintroducing controls, unrelated Undo/Local change. Both-direction/ordering controls and unchanged siblings address these boundaries.
- Rollback or recovery: revert this scoped UI/test PR, no data/protocol/schema changes.

## Pause and escalation conditions

- No production fix before qualified actual RED; escalate new owner policy or unrelated backend scope.
- Respect max8 iterations and no-progress limit; preserve failed/partial/unexecuted gates and do not weaken assertions or silently extend.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2ayzvg-restore-permission-cache.md
- Validator result: Initial structural check PASS before tests; stdlib AST, unchanged existing STUB/CSS_SRC/shipping implementation and full baseline diff checks PASS at tests-only freeze.
- Independent verification result: Pending four root-owned reviews.
- Terminal state: ACTIVE, tests-first inspection.
- Remaining failed or blocked criteria: C-001 through C-005 pending.
- ClickUp final evidence comment: Root owns delivery/status and persisted QA readback.
