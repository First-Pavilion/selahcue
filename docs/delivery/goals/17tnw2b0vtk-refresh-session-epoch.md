# Goal Contract — 17tnw2b0vtk

## Identity

- Goal ID: TASK-17tnw2b0vtk
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Retired-session reads cannot mutate current state or restart recovery
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b0vtk
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A refresh or confirmed-view read belonging to a retired connection must have no current-session effects. A failed action plus queued old poll causes exactly one reconnect, retains rejection/status until a current snapshot lands, and permits replacement-session resync without waiting for the old read.

## Baseline

Freshly fetched origin/main 09168758b8c850958a514d55a41b9fc8cfe52270 (tree 60b76500) retains the task's gap: refresh checks epoch only after success, its exception path reconnects unconditionally, and reconnect advances epoch only after old close and new connect. The confirmed-view exception boundary has the same stale-read risk. Existing controller tests cover reconnect, syncing and compound-gesture races but do not control the close window with a queued old turn.

Full captured task and successful empty comments are in orchestration evidence wave2-20261029/mobile-qualification/17tnw2b0vtk.json. No runtime baseline is claimed from inspection.

Before publication, ordinary merge a498764c integrated freshly fetched main 0d3d3da8658985ad6dbb758933557dbc18df1c59, whose additional API/deployment changes leave mobile production unchanged. Hosted RED was observed on that integrated test-only source.

## Inputs and evidence sources

- Existing standalone task 17tnw2b0vtk: full description, all acceptance criteria, empty comments, no declared blocking dependency.
- lib/controllers/live_controller.dart and the existing ControllerSession interface.
- Real SelahSession.forTest serialization and existing controller race/sync/stalled-command tests.
- Root authorization for this ticket; root owns UI status, hosted CI, external publication, reviews, merge and QA.

## Scope

### In scope

- LiveController refresh/confirmed-view lifecycle, epoch validity and replacement resync.
- Focused deterministic public-controller regressions using the real in-memory session turn chain, controlled old close and host replies.

### Non-goals

- Session transport/queue implementation, pairing policy, wire format, retry budget or command deadline changes.
- Other mobile tickets, UI/design changes, platform configuration, signing and application publication.

### Constraints

- Work only in this isolated ticket branch; other agents own separate changes.
- No local project runtime, pub, build, simulator, container or performance run while host paging fails resource admission.
- Freeze test-only source and observe actual hosted behavioral RED before production edits.
- Preserve controls, rejection evidence and no-replay behavior; no new production test seams.
- Do not push, create PRs, modify ClickUp or spawn agents; root owns those actions.

### Assumptions and unknowns

- Controlled stream and close completions can exercise the real lockstep queue without a real socket or elapsed-time sleeps.
- Recovery is verified by causal progress (one connect and one replacement state read while the old read remains pending), not a local timing/performance claim.
- Hosted test-only RED is established; corrected GREEN and independent review remain pending.

## Dependencies and approvals

- Prior command-deadline/gesture prerequisites are present in current main.
- Task has no declared blocker or unresolved owner decision in captured full task/comments.
- Root explicitly assigned implementation and owns source-of-truth status/start comment.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A failed act plus queued old poll causes one reconnect | Real serialized-session controller regression with late old failure after replacement | One connect; healthy replacement is not closed; no replay | Hosted focused test receipt | PENDING |
| C-002 | yes | Retired refresh and confirmed-view results cannot change current state or notices | Controlled old close/reply success and error races through public controller operations | Old view ignored, rejection/status retained until current snapshot, no second reconnect or go-live | Hosted focused test receipts | PENDING |
| C-003 | yes | Recovery does not await an old queued read | Hold old read pending through replacement connect and supply one replacement snapshot | One replacement read starts and controls recover before old read is released | Hosted causal-progress regression | PENDING |
| C-004 | yes | Legitimate same-session reads and compound gestures still work | Positive controls plus existing controller race/sync/reentrancy tests | Current view updates; confirmed stage can go live; gates preserved | Hosted focused/full suite receipts | PENDING |
| C-005 | yes | New regression detects the baseline bug before production changes | Frozen test-only commit on unchanged production | Behavioral stale-state/reconnect/progress failure; setup and controls work | PR 269 CI 40944254684 on a498764c; saved wave2-20261029/mobile-refresh-red.log | PASS |
| C-006 | yes | Corrected source passes broader mobile gates | Hosted flutter analyze and full flutter test | Analysis exits 0 and suite passes on exact corrected source | Root hosted CI receipt | PENDING |
| C-007 | yes | Independent review and authorized delivery close | Cody, Quinn, Vera, Shadow and root delivery evidence | All four pass current source, merge verified, exact linked ticket QA reread | Root reviews/merge/ClickUp receipts | PENDING |

## Verification plan

- Focused command: flutter test test/controllers/live_controller_retired_read_test.dart from implementation/mobile/selahcue_controller.
- First hosted execution uses unchanged production; require actual behavioral RED, not analyzer/setup failure.
- Corrected source requires hosted flutter analyze and full flutter test, including existing race, sync and reentrancy coverage.
- Required independent verifiers: Cody, Quinn, Vera and Shadow, coordinated by root.
- Shared Dart controller behavior is exercised without platform configuration changes; no physical-device or socket timing claim.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-005
- Hypothesis: missing error-side epoch checks and epoch retirement after close allow old turns to affect recovery; a global refreshing flag can block the replacement's first read.
- Change or investigation: inspect fresh main/full task/comments and add focused regression/controls before any production changes.
- Verifier executed: structural Goal validator/full baseline diff check, then root-hosted Flutter analysis/full test suite on integrated test-only commit a498764cd063371b5d7046aa5a4b148b3d12ab97.
- Result: Flutter analysis passed; actual behavioral RED, 384 passed and 5 failed. Same-session control passed. The old poll published forged-old, its late failure caused two connects, replacement state reads stayed at zero while old poll remained pending, confirming success published forged-confirmation, and confirming failure caused two connects.
- New evidence: PR 269 CI 40944254684, saved wave2-20261029/mobile-refresh-red.log; inspected all five behavioral assertions before production edits. The real session queue and controlled close reached the intended windows.
- Decision: iterate with minimal lifecycle fencing; retain all original regressions and control.

### Iteration 2

- Target criterion: C-001 through C-004, C-006 and C-007
- Hypothesis: retiring epoch before the old close yields, checking that epoch on both result branches, and scoping the refresh claim to its epoch isolates every old read from replacement recovery.
- Change or investigation: advance epoch once at reconnect entry instead of replacement installation; make the single-flight refresh claim epoch-specific; ignore disposed/revoked/retired read success and failure in refresh and confirmed-view; let only its owning epoch release the refresh claim; preserve outage notice until a current snapshot. Existing real-serialization tests remain, with extra assertions for current resync coalescing after stale finally and warning/rejection lifetime before current reply.
- Verifier executed: full baseline diff check, structural Goal validator and source inspection. No local project runtime ran while resource admission remained unavailable.
- Result: corrected source prepared; no corrected-source analysis/test pass is claimed before root executes fresh hosted CI.
- New evidence: production changes are confined to LiveController lifecycle/read guards, with no transport, protocol, retry budget, storage or platform changes.
- Decision: hand off frozen corrected source for hosted GREEN and all four independent current-head reviews; remediate valid findings within the remaining budget.

## Risks and rollback

- Risks: a stale finally block must not release a newer refresh claim; invalidating an old session must not authorize a compound gesture or suppress legitimate recovery.
- Rollback or recovery: revert this ticket only; no schema, wire, storage or platform migration.

## Pause and escalation conditions

- Actual hosted behavioral RED was observed before production edits; wait for corrected-source CI and independent review before completion.
- Keep valid failures explicit and remediate within eight iterations; report any missing owner decision or runtime gate to root.
- Never substitute local heavy execution or a skipped gate for admitted hosted evidence.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b0vtk-refresh-session-epoch.md
- Validator result: structural validation passed (exit 0); corrected-source behavior awaits hosted execution
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-004, C-006 and C-007; C-005 passed on integrated test-only source
- ClickUp final evidence comment: root owns publication
