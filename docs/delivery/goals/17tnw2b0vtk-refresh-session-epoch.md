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
- Hosted RED, corrected GREEN and independent review remain pending.

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
| C-005 | yes | New regression detects the baseline bug before production changes | Frozen test-only commit on unchanged production | Behavioral stale-state/reconnect/progress failure; setup and controls work | Hosted RED log | PENDING |
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
- Verifier executed: structural Goal validator and full baseline diff check; hosted test-only RED pending root.
- Result: pending hosted execution
- New evidence: real SelahSession.forTest preserves the production turn chain; an outer test wrapper can control close without adding production seams.
- Decision: freeze test-only source and hand off for actual RED before implementing.

## Risks and rollback

- Risks: a stale finally block must not release a newer refresh claim; invalidating an old session must not authorize a compound gesture or suppress legitimate recovery.
- Rollback or recovery: revert this ticket only; no schema, wire, storage or platform migration.

## Pause and escalation conditions

- Wait for actual hosted behavioral RED before production edits.
- Keep valid failures explicit and remediate within eight iterations; report any missing owner decision or runtime gate to root.
- Never substitute local heavy execution or a skipped gate for admitted hosted evidence.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b0vtk-refresh-session-epoch.md
- Validator result: structural validation passed (exit 0); behavior awaits hosted test-only execution
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-007
- ClickUp final evidence comment: root owns publication
