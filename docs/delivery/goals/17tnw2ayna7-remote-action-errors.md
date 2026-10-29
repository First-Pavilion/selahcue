# Goal Contract — 17tnw2ayna7-remote-action-errors

## Identity

- Goal ID: TASK-17tnw2ayna7
- Parent goal ID: NONE
- Title: Remote Control actions retain confirmed state and visibly report host failures
- Role: frontend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2ayna7
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Approve, deny, revoke and role changes never present an unconfirmed local change as host truth; a rejected action remains visibly explained even if the follow-up snapshot also fails.

## Baseline

Verified main ca2c415de81f23d7f515f3f036d50208c3e19677. remote.js mutates the model and announces success before IPC resolves. reconcile writes only the screen-reader live region, then loadSnapshot swallows any second failure. The visible list can therefore retain a false role or revoke/approval outcome.

## Inputs and evidence sources

- Coordinator's complete live task read: planning/todo, Normal, no blocking dependencies or substantive comments. Full qualification saved in /private/tmp/selahcue-batch20-20261029/farah-qualified.md item 2.
- Shipped remote.js/index.html, existing warning-banner pattern and committed operator_headless.py real-DOM gate.

## Scope

### In scope

- Existing four device-management actions, visible accessible failure feedback, host-confirmed state and reject/recovery regressions.

### Non-goals

- Host permissions, wire shapes, reconnect behavior, device persistence, pairing-code errors or new design patterns.

### Constraints

- Reuse existing warning styles. No raw host error data in visible copy. Preserve host authority and existing two-step revoke.
- One ticket/branch/PR; shared repository, do not revert other agents. Coordinator owns ClickUp, publication, independent reviews, CI and merge.

### Assumptions and unknowns

- Verified: action success returns the host snapshot. Browser gate exercises production DOM/JS with the existing IPC seam, not native Tauri transport or physical devices.

## Dependencies and approvals

- User authorized this implementation and all four independent reviews, remediation, conditional merge and QA. Root coordinator owns tracker updates while ClickUp connector quota is exhausted.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Rejected approve/deny/revoke/role actions plus rejected snapshot preserve confirmed list/role and show visible accessible warning | SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/operator_headless.py | All four actual DOM failure cases pass | /private/tmp/selahcue-batch20-20261029/17tnw2ayna7-green.log | PASS |
| C-002 | yes | Successful actions apply host snapshots, confirm the requested postcondition, retain two-step revoke and recover from prior warning | Same full real-DOM gate | Success/recovery controls pass | Same log | PASS |
| C-003 | yes | Pending work does not announce success or dispatch duplicate actions; warning never exposes raw host error | Same real-DOM gate | Deferred action and hostile error controls pass | Same log | PASS |
| C-004 | yes | Full operator gate and source syntax/diff checks pass | Same gate; node --check remote.js; Python compilation; git diff --check | Exit 0 and zero failures | Report and logs | PASS |
| C-005 | yes | Independent Cody/Quinn/Vera/Shadow reviews and applicable final CI pass | Coordinator review/CI evidence | All pass at final revision | Coordinator report | BLOCKED |
| C-006 | yes | PR merged and linked ticket QA status persisted | Coordinator GitHub/ClickUp read-back | Verified merge and exact configured QA | Coordinator report | BLOCKED |

## Verification plan

- Focused verification: action rejection and failed snapshot for all four actions; deferred host confirmation; success and recovery with the existing IPC fixture.
- Broader regression verification: full operator JS real-DOM suite, syntax/diff checks and applicable hosted CI. No Rust/dependency change or cold native suite for this JS/HTML-only behavior fix.
- Independent verifier: Cody, Quinn, Vera and Shadow through coordinator.
- Required environment: Chrome on macOS with the established host seam; final hosted applicable CI.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-003
- Hypothesis: real DOM actions with rejected IPC and snapshot expose false local authority and absent visible warning.
- Change or investigation: add deterministic command rejection/defer controls in the existing test-only IPC seam, then failure and recovery cases before changing production code.
- Verifier executed: full mandatory-Chrome operator_headless.py on unchanged production JS
- Result: RED exits 4; 2335 checks, 17 behavioral failures, all prior 2315 checks pass. Count drift is expected until the newly measured 2335 count is recorded.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2ayna7-red.log
- Decision: iterate

### Iteration 2

- Target criterion: C-001..C-004
- Hypothesis: keep the confirmed model until IPC succeeds, serialize mutation controls and visibly retain an uncertainty warning if a resync also fails.
- Change or investigation: shared mutation lifecycle, fixed-copy alert using the existing banner style, no raw IPC error output; original two-step revoke retained. Real DOM tests drive all four reject paths, successful recovery, deferred denial, duplicate-submit prevention and successful role confirmation. Existing Approve/Revoke checks now await the actual resulting list state.
- Verifier executed: full mandatory-Chrome browser gate; node syntax, Python compilation and git diff --check.
- Result: GREEN exits 0; 2335 checks, 0 FAIL. All twenty new assertions pass. Syntax and diff checks exit 0.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2ayna7-green.log
- Decision: handoff

### Iteration 3 — independent review C-REMOTE-1

- Target criterion: C-002
- Hypothesis: a resolved host snapshot can be an unchanged no-op, so awaiting the reply alone cannot justify a success announcement.
- Change or investigation: verified the actual host absorbs NoSuchRequest/TooManySessions into successful snapshot replies and existing host tests pin unknown-target no-ops. Added actual DOM no-op cases for all four actions, missing role target and stale Deny after another actor approved the target.
- Verifier executed: full mandatory-Chrome operator_headless.py on unchanged be231c25 production.
- Result: first RED2345 checks/5 behavioral failures; expanded RED2347 checks/6 behavioral failures, exit4. All2335 earlier checks passed. Count drift expected before recording the measured2347 total.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2ayna7-noop-red.log and17tnw2ayna7-noop-deny-red.log; Cody report17tnw2ayna7-cody.md.
- Decision: iterate

### Iteration 4 — remediate C-REMOTE-1

- Target criterion: C-002
- Hypothesis: compare the requested result with the returned host snapshot before positive feedback; keep the authoritative list and show fixed unconfirmed feedback when the result is absent.
- Change or investigation: approval requires matching paired role and no pending request; denial requires no pending request or paired target; revocation requires target absence; role change requires target presence with the requested role. Unfulfilled resolved replies use the existing visible uncertainty warning without an unnecessary second fetch. Copy advises checking the list/output window without claiming a transport error.
- Verifier executed: full mandatory-Chrome browser gate, JavaScript/Python syntax and diff checks.
- Result: GREEN2347 checks/0FAIL, exit0. All12 no-op assertions and all prior reject/deferred/success/recovery controls passed. Syntax/diff checks passed.
- New evidence: /private/tmp/selahcue-batch20-20261029/17tnw2ayna7-noop-green.log.
- Decision: handoff

## Risks and rollback

- Risks: asynchronous polls can interleave with actions; keep last confirmed model and serialize mutation controls without introducing another poll.
- Rollback or recovery: revert the isolated ticket commits.

## Pause and escalation conditions

- New host contracts or product decisions go to coordinator. No external updates or source publication by implementation agent.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2ayna7-remote-action-errors.md
- Validator result: structural PASS; completion blocked by independent review/delivery C-005,C-006
- Independent verification result: initial Cody C-REMOTE-1 remediated; all four current-revision reviews pending coordinator
- Terminal state: BLOCKED
- Remaining failed or blocked criteria: C-005,C-006
- ClickUp final evidence comment: coordinator owned
