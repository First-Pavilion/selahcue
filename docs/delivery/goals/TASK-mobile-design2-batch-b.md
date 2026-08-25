# Goal Contract — TASK-mobile-design2-batch-b

## Identity

- Goal ID: TASK-mobile-design2-batch-b
- Parent goal ID: NONE
- Title: The mobile controller ships the Design 2.0 timer entry well and the three RBAC enforcement states, built to `MOBILE-2.0-SPEC.md` §4.6 / §4.10–§4.13
- Role: mobile-engineer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: NONE (batch handed down by the requesting agent; Build Control `86ajnx548`)
- Created: 2026-08-21
- Updated: 2026-08-21
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The Flutter controller renders an HH:MM:SS custom-time well on the Timer tab, and the three
enforcement surfaces (Permission blocked · Role changed — live · Action rejected) appear from real
controller state rather than from demo hooks — with `make mobile-test` still green.

## Baseline

**Verified** at the start of this goal, from the working tree:

- Batch A is uncommitted but complete: `lib/models/selah_theme.dart` and
  `lib/views/widgets/primitives.dart` exist; every view is on the `d2*` layer.
- `make mobile-test` reports `flutter analyze: No issues found` and `147` passing tests.
- `lib/views/tabs/timer_tab.dart` has a **minutes-only** `SelahInput`, no HH:MM:SS entry.
- No enforcement surface exists: `grep -rn 'not in your role\|Action rejected\|role changed' lib/`
  returns nothing.
- `CommandOutcome.denied` exists (`live_controller.dart:27`) and is returned (line 276) but the only
  consumer is the red `ConnectionBanner` string.
- `selahcue-lan/src/protocol.rs` has `StartTimer`/`StopTimer`/`AdjustTimer`/`PauseTimer`/
  `ResumeTimer` and no `ResetTimer`; `DenyReason` is the closed set
  `forbidden` / `unauthenticated` / `bad_request` (`protocol.rs:952`).

## Inputs and evidence sources

- `docs/design/MOBILE-2.0-SPEC.md` §3.10, §4.6, §4.10, §4.11, §4.12, §4.13, §6.1–§6.7
- `docs/delivery/CODE-REVIEW-batch-mobile-design2.md` (Batch A, and its open items)
- `implementation/desktop/crates/selahcue-lan/src/rbac.rs` (`required_permission`) and
  `protocol.rs` (`DenyReason`) — the authority for the client mirror
- Figma `SYQn5hFY8YVQKm3c6rw0eJ`, nodes `357:124`, `342:124`

## Scope

### In scope

- HH:MM:SS custom-time well replacing the minutes-only field (§4.6), plus an honest note naming the
  two timer controls that have no wire command.
- Permission-blocked sheet on a `forbidden` denial (§4.10).
- Role-changed inline banner + `PREVIOUS CONTROLS` receipt (§4.11).
- Action-rejected inline toast in the connection-banner slot (§4.12).
- Widget/unit tests for each, and a review document.

### Non-goals

- Timer `Reset` and `Send "TIME UP" to stage` — no wire command exists; building either would be a
  control that does nothing.
- Stage messages; any role expansion (`86ajxuf81` / `86ajxufbg`).
- Any change to `design_tokens.dart` (cross-surface pinned) or to the Batch A guards.

### Constraints

- No commits, no staging, no history changes — the owner has WIP in this tree.
- `test/models/design_tokens_test.dart` and `test/views/token_drift_test.dart` must pass unweakened.
- Bounded memory: every timer cancelled on dispose; no queue, cache or list that grows per event.
- Time-dependent behaviour takes an injected duration so tests stay deterministic.

### Assumptions and unknowns

- **ASSUMED** — the sheet should be raised only for `DenyReason::forbidden`. Validated against the
  Rust enum: `bad_request` (unknown reference) and `unauthenticated` are not role problems, and
  "That's not in your role" would be false for them.
- **ASSUMED** — hours clamp at 23. The frames give two digits and no bound; a service timer past a
  full day is out of range for the product. Validation owner: design.
- **UNKNOWN** — whether the role-changed receipt should also ride the pushed detections route. Left
  to the shell only; recorded in the review doc.

## Dependencies and approvals

- Rust protocol variants for `reset_timer` / `time_up` — owner decision pending, blocks nothing here.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The Timer tab renders three two-digit fields with `HOURS`/`MIN`/`SEC` labels and `:` separators, each ≥48 wide, and Start sends `start_timer` with hours+minutes+seconds in seconds | `flutter test test/views/custom_time_well_test.dart` | all pass; a 1:05:30 entry sends `{'cmd':'start_timer','seconds':3930}` | `test/views/custom_time_well_test.dart` — 13 passed | PASS |
| C-002 | yes | No control exists for Reset or the stage TIME UP cue; the deferral is stated in words, not drawn as a dead button | `flutter test test/views/timer_tab_test.dart` | existing "TIME UP and Reset controls are not present" test passes **unmodified**, plus a new test asserting the note is not tappable | `test/views/timer_tab_test.dart` — 4 passed, file unmodified | PASS |
| C-003 | yes | A `forbidden` denial raises the permission sheet with the templated body and the `ROLES THAT CAN …` chips; a `bad_request` denial does not | `flutter test test/views/permission_blocked_test.dart` | all pass | `test/views/permission_blocked_test.dart` — 13 passed | PASS |
| C-004 | yes | The emergency strip stays present and tappable while the permission sheet is up, and "Request access" is absent | `flutter test test/views/permission_blocked_test.dart` | blackout still fires from behind the sheet; `find.text('Request access')` finds nothing | `test/views/permission_blocked_test.dart` — 13 passed | PASS |
| C-005 | yes | A reconnect that re-roles the device raises the role-changed banner, lists only the removed capabilities, and the removed controls are already gone from the UI | `flutter test test/views/role_changed_test.dart` | all pass | `test/views/role_changed_test.dart` — 14 passed | PASS |
| C-006 | yes | The role-changed banner auto-dismisses on its injected window and leaves no pending timer | `flutter test test/views/role_changed_test.dart` | passes without a "pending timer" binding failure | `test/views/role_changed_test.dart` — 14 passed | PASS |
| C-007 | yes | A command dropped mid-flight raises the action-rejected toast in the connection-banner slot, queues nothing, and clears itself once the link is healthy and state re-read | `flutter test test/views/action_rejected_test.dart` | all pass | `test/views/action_rejected_test.dart` — 10 passed | PASS |
| C-008 | yes | Reduced motion replaces the toast spinner with a static ring | `flutter test test/views/action_rejected_test.dart` | no `CircularProgressIndicator` when `reduceMotion` is on | `test/views/action_rejected_test.dart` — 10 passed | PASS |
| C-009 | yes | The Batch A palette guards still pass unweakened | `git diff --stat test/models/design_tokens_test.dart test/views/token_drift_test.dart` | no diff | `git diff` empty for both guard files | PASS |
| C-010 | yes | The whole mobile gate is green | `make mobile-test` | `No issues found` + `All tests passed` | `make mobile-test` — No issues found; All tests passed (204) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the five new/updated test files above.
- Broader regression verification: `make mobile-test` (analyze + the full suite) from the repo root.
- Independent verifier: the requesting agent / code review against `MOBILE-2.0-SPEC.md`.
- Required environment: Flutter 3.44.0 stable, macOS.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 … C-010
- Hypothesis: the four surfaces can be driven entirely from existing controller state plus a
  `DenyReason`-typed denial and a remembered prior role; no wire change is needed.
- Change or investigation: see the review document.
- Verifier executed: `make mobile-test`
- Result: all ten mandatory criteria PASS; `make mobile-test` green at 204 tests (from 147).
- New evidence: `docs/delivery/CODE-REVIEW-batch-mobile-design2-b.md`
- Decision: complete

## Risks and rollback

- Risks: the action-rejected toast shares the connection-banner slot, so a wrong trigger condition
  would hide the reconnecting notice. Mitigated by triggering only on a command that reached the
  wire and failed — never on the pre-flight `syncing` refusal — and by giving the toast its own
  reconnecting status row so no information is lost.
- Rollback or recovery: every change is additive in new files plus small, reviewable edits to
  `live_controller.dart`, `controller_view.dart`, `mobile_widgets.dart`, `timer_tab.dart`,
  `rbac.dart`. Nothing is committed.

## Pause and escalation conditions

- A protocol change turns out to be required → BLOCKED, escalate to the owner (already pending).
- A Batch A assertion legitimately needs changing → stop, state the reason, do not silently relax it.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-mobile-design2-batch-b.md --completion`
- Validator result: OK (structural + completion)
- Independent verification result: pending — handed to the requesting agent / code review against `MOBILE-2.0-SPEC.md`
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none. Out-of-scope items (`Reset`, stage `TIME UP`) are recorded as an owner protocol decision in the review document, not as failed criteria.
- ClickUp final evidence comment: see the Build Control task `86ajnx548`
