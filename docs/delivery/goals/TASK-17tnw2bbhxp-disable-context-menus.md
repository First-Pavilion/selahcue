# Goal Contract — TASK-17tnw2bbhxp-disable-context-menus

## Identity

- Goal ID: TASK-17tnw2bbhxp-disable-context-menus
- Parent goal ID: NONE
- Title: Operator secondary-click menus are suppressed while keyboard editing commands remain available
- Role: frontend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhxp
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Suppress browser/webview and custom context-menu activation throughout the Operator Console. Preserve Theme Designer commands through keyboard activation and existing controls.

## Baseline

Verified at main `93bf472f65a1846117eecf09b1972c4118dc0cd4`: app.js opens a custom Theme Designer menu on contextmenu; the headless driver explicitly expects right-click to open it. The designer already has ContextMenu and Shift+F10 key handlers; the window-level F10 shortcut also sees the latter event.

## Inputs and evidence sources

- ClickUp 17tnw2bbhxp and owner-approved scope reproduced in the parent chat.
- implementation/desktop/crates/selahcue-operator/dist/app.js
- scripts/operator_headless.py

## Scope

### In scope

- Console contextmenu prevention, including custom Theme Designer pointer activation.
- Keyboard menu regression coverage and existing copy/paste/delete/arrange controls.

### Non-goals

- Marketing, mobile and audience-output behavior; security restrictions; unrelated shortcuts.

### Constraints

- Isolated worktree and one ticket branch; no merge or production deployment.
- No concurrent Flutter/full make ci run.

### Assumptions and unknowns

- Real OS secondary-click/native webview smoke needs representative platform evidence; synthetic browser events prove cancellation and handler dispatch, not OS chrome rendering.

## Dependencies and approvals

- User authorized implementation. Root owns ClickUp browser status/evidence updates.
- Cody, Vera, Shadow and Quinn reviews are pending; no self-completion claim.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Console contextmenu events are cancelled across representative targets without opening a custom menu | operator_headless.py pointer scenarios | zero named pointer failures | /private/tmp/farah-p16-focused-green.log: 28 checks, 0 FAIL | PASS |
| C-002 | yes | Keyboard designer menu commands still work and do not also open app navigation | operator_headless.py keyboard scenarios | copy/paste/delete and ContextMenu/Shift+F10 pass | /private/tmp/farah-p16-focused-green.log | PASS |
| C-003 | yes | Existing operator browser-portable suite remains green | SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py | exit 0, no failures | pending | PENDING |
| C-004 | yes | Independent code/performance/security/QA review and platform smoke completed | independent review + native smoke | no unresolved blockers | pending | PENDING |

## Verification plan

- Focused verification: failing pointer and keyboard tests before implementation, then passing tests.
- Broader regression verification: complete committed operator headless suite; no Rust logic changes.
- Independent verifier: Cody, Vera, Shadow, Quinn coordinated by root.
- Required environment: Python, Chrome; native Tauri webviews for platform smoke.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: capture-phase contextmenu cancellation prevents native and descendant custom handlers, while explicit keydown menu activation remains available.
- Change or investigation: trace real custom and global shortcut handlers; add browser behavioral checks first.
- Verifier executed: real-Chrome focused extraction of the committed fixture/driver block via /private/tmp/farah_p16_focused.py before and after implementation; node --check app.js; git diff --check.
- Result: focused RED 25 checks with 6 intended behavioral failures; focused GREEN 28 checks with 0 failures including dialog coverage. An escalated broad run observed 2628 checks with zero behavioral failures but an expected-count mismatch; it started before the final test count change. Final full-suite rerun remains pending. Sandboxed baseline Chrome aborted with SIGABRT (-6); it is not passing evidence.
- New evidence: Shift+F10 previously opened both element actions and app navigation. Reserving shifted F10 fixes that without changing ordinary F10.
- Decision: handoff

## Risks and rollback

- Risks: native context menus also expose editing commands; keyboard shortcuts and designer keyboard menu remain available. Native keyboard-generated contextmenu events are cancelled too; explicit designer keydown activation remains accessible.
- Rollback or recovery: revert the single ticket commit.

## Pause and escalation conditions

- Unrelated baseline failures or unavailable browser platform evidence are reported rather than waived.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbhxp-disable-context-menus.md
- Validator result: structural check passed before implementation; completion validator withheld.
- Independent verification result: pending
- Terminal state: IN_PROGRESS
- Remaining failed or blocked criteria: C-003 final broad regression; C-004 independent review/native smoke
- ClickUp final evidence comment: root to post
