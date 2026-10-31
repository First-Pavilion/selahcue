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

Verified at original main `93bf472f65a1846117eecf09b1972c4118dc0cd4`: app.js opens a custom Theme Designer menu on contextmenu; the headless driver explicitly expects right-click to open it. The designer already has ContextMenu and Shift+F10 key handlers; the window-level F10 shortcut also sees the latter event. Rebased onto main `179dbb97665148170a7d20eb5419fa710b2b3ab1` before review; app.js, operator_headless.py and headless_chrome.py are unchanged between those two main revisions.

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
| C-003 | yes | Existing operator browser-portable suite remains green | SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py | exit 0, no failures | /private/tmp/farah-p16-review-green-full.log: 2633 checks, 0 FAIL | PASS |
| C-004 | yes | Independent code/performance/security/QA review and platform smoke completed | independent review + native smoke | no unresolved blockers | Round 1 requested hint correction; native candidate built but Mac is locked and automatic unlock failed (root CUA observation) | BLOCKED |

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
- Result: focused RED 25 checks with 6 intended behavioral failures; focused GREEN 28 checks with 0 failures including dialog coverage. The final full-suite run passed 2631 checks with 0 failures and process exit 0 (/private/tmp/farah-p16-green-full.log). The earlier 2628-check run had an expected-count mismatch and is not passing evidence. Sandboxed baseline Chrome aborted with SIGABRT (-6); that run is not passing evidence either.
- New evidence: Shift+F10 previously opened both element actions and app navigation. Reserving shifted F10 fixes that without changing ordinary F10.
- Decision: handoff

### Review preparation

- Rebased onto origin/main `179dbb97665148170a7d20eb5419fa710b2b3ab1` without conflicts. Confirmed no upstream change to the production JS, committed driver or Chrome launcher covered by the full-suite result.
- Re-ran the focused real-Chrome smoke on the rebased tree: 28 checks, 0 failures, exit 0 (/private/tmp/farah-p16-focused-rebased.log).
- Re-ran node --check, git diff --check and structural Goal Contract validation. Native Windows/WebView2, Linux/WebKitGTK and macOS/WKWebView smoke remain unverified; they are not implied by headless Chrome.

### Iteration 2 — review remediation

- Confirmed Cody/Quinn finding: the visible canvas help still advertised disabled right-click actions.
- Added behavioral checks for visible Context Menu / Shift+F10 instructions and their accessible association with the focusable selection, while retaining actual keyboard menu command checks. Focused RED: 30 checks with exactly 2 intended hint failures. Focused GREEN: 30 checks, 0 failures (/private/tmp/farah-p16-hint-green.log). Full operator regression: 2633 checks, 0 failures (/private/tmp/farah-p16-review-green-full.log).
- Corrected the hint and its selection aria-describedby association. No new product scope.
- Built the actual candidate Tauri app offline in 55.93s, using an isolated copy-on-write build cache. Candidate: /private/tmp/farah-p16-native/SelahCueP16Candidate.app, identifier com.selahcue.p16smoke; debug defaults, no provider-key features or bundled output sidecar. The only temporary build configuration overrides are the nonproduction app identifier and window title.
- Native smoke did not run. The cua.getApp call stalled for 719.8s and was interrupted; root recovered the UI session and observed that the Mac is locked and automatic unlock failed. The user was asked to unlock it. No bypass, criterion waiver, repeated app-control call or completed native check is claimed.
- Candidate source hashes: index.html SHA-256 e91f74ff692a0006fe16540a08ebaae8d2adeb69145695391094d1d68beae281; app.js SHA-256 4b5b8797543e273bedbed25ecb27957387f8c76779a9760261733bb3fd56d033. Ad-hoc-signed candidate executable SHA-256 2b9db740af4023a609f70d654288facd2b629a1e763fc6e1b1222faa4e4efd5c. Provenance is retained at /private/tmp/farah-p16-native/provenance.json. Compare final source bytes with those hashes before later native smoke; the earlier pre-sign binary hash is not the signed executable hash.
- Decision: hand off corrected source for all-four re-review; mandatory native QA remains blocked until unlock and actual candidate interaction.
- Integrated main `bf8190c26b66cc998d54cc316eeaff6823e0f8ee` with a conflict-free merge because the ticket branch was already published and force-push is prohibited. The resulting source commit is `f0509061058cc815a68fa030cad86bacef4e73f0`, with zero commits behind origin/main. The newly integrated workflow/mobile/API changes do not touch the Operator JS/HTML or browser gate; final dist hashes still exactly match the native candidate above, so no rebuild or repeated stable suite was needed.

## Risks and rollback

- Risks: native context menus also expose editing commands; keyboard shortcuts and designer keyboard menu remain available. Native keyboard-generated contextmenu events are cancelled too; explicit designer keydown activation remains accessible.
- Rollback or recovery: revert the single ticket commit.

## Pause and escalation conditions

- Unrelated baseline failures or unavailable browser platform evidence are reported rather than waived.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbhxp-disable-context-menus.md
- Validator result: structural check passed before implementation; completion validator withheld.
- Independent verification result: pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-004 independent review/native smoke
- ClickUp final evidence comment: root to post
