# Goal Contract — GOAL-mobile-reconnect-race-safety

## Identity

- Goal ID: GOAL-mobile-reconnect-race-safety
- Parent goal ID: NONE
- Title: A reconnect can never promote a stale item to Live, and audience-facing mobile controls resist accidental taps and are disabled until live state re-syncs.
- Role: mobile-engineer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxwcft (bug, high) · https://app.clickup.com/t/86ajxx4x8 (story, normal)
- Created: 2026-08-14
- Updated: 2026-08-14
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`LiveController` refuses to complete a compound stage-then-go-live gesture unless the stage is *proven* to have landed on the **current** connection and the go-live guard is evaluated against a snapshot *proven* to post-date it; and the mobile UI disables audience-facing controls until live state has re-synced, with an inline confirm on the destructive Blackout/Clear taps.

## Baseline

Verified by reading `implementation/mobile/selahcue_controller/lib/controllers/live_controller.dart` at HEAD `cc66e75`:

- `act()` returns `void` and swallows `SessionException` into `_reconnect()`. Callers cannot distinguish "command landed" from "command lost, reconnected".
- `_reconnect()` swaps `_session` but never refreshes `_view`; the 1s poll early-returns while `_reconnecting`.
- `_reconnect()` is re-entrancy-guarded (`if (_reconnecting || _disposed) return;`) so a second caller returns **immediately, still disconnected**.
- `refresh()` also early-returns when `_refreshing` is true, so `act()`'s trailing `await refresh()` can be a no-op that coalesces with an in-flight poll whose snapshot **pre-dates** the command.
- `selectAndGoLive()` / `stageScriptureAndGoLive()` read the `_view` field after `act()` and fire `cmdGoLive()` when the guard passes.
- `OperatorStateView` carries **no plan/deck revision** and `stagedIndex` is a positional index into `items`. The only staleness axis the client can defend is snapshot recency relative to the command, bound to the connection that carried it.
- `EmergencyStrip` (mobile_widgets.dart:142-198) fires `cmdBlackout`/`cmdClear` on a single tap, haptic only.
- No control anywhere is disabled while `reconnecting` is true.

Ticket `86ajxwcft` cites line numbers (act 130-146, _reconnect 150-183) that have drifted; the real ranges are act 154-170, _reconnect 174-221.

## Inputs and evidence sources

- ClickUp 86ajxwcft, 86ajxx4x8
- `implementation/mobile/selahcue_controller/lib/controllers/live_controller.dart`, `lib/models/session.dart`, `lib/models/protocol.dart`, `lib/views/widgets/mobile_widgets.dart`
- `docs/design/COMPONENT-SPECS.md` §1.2 (confirmation tiers), §12 (mobile controller: accidental-tap protection, disable-while-offline, re-sync-before-re-enable)
- `docs/design/UX-STATE-MATRIX.md` §11, §15.5
- `CLAUDE.md` (bounded memory, injected clock, cross-language wire contract)

## Scope

### In scope

- `LiveController` command-outcome + connection-epoch state fix (86ajxwcft).
- Inline accidental-tap confirm on Blackout / Clear All; controls disabled while syncing (86ajxx4x8).
- Dart unit + widget tests under `implementation/mobile/selahcue_controller/test/`.

### Non-goals

- Any change to the LAN wire protocol or `test/models/protocol_test.dart` fixtures (cross-language pinned by `selahcue-lan/tests/test_protocol.rs`).
- Expanding mobile RBAC from 4 roles to 7 (tracked at 86ajxufbg).
- Degraded/slow-connection chip, CLOUD-ACTIVE banner, PIN pairing variant (noted as lower-priority in 86ajxx4x8).
- Anything outside `implementation/mobile/`.

### Constraints

- No wire-format change: the fix must be entirely client-side.
- No unbounded queues/caches/logs; any added in-flight work is bounded per user gesture.
- Time-dependent behaviour must be deterministic (injectable duration, driven by `tester.pump`).
- Un-blackout is a *recovery* action and must remain one tap — confirmation may never gate restoring the audience screen (COMPONENT-SPECS invariant 2).

### Assumptions and unknowns

- ASSUMED: widening the injected `connect` seam from `Future<SelahSession>` to `Future<ControllerSession>` is safe — `SelahSession implements ControllerSession` and `_session` is already typed `ControllerSession`. Validated by `flutter analyze`.
- VERIFIED: no revision/version field exists on `OperatorStateView`, so an item-identity or deck-revision guard is not expressible without a wire change.

## Dependencies and approvals

- Kenji (`implementation/api/`) and Farah (`implementation/marketing/`) work concurrently — no shared paths. No approval needed.
- No Rust-side change required, therefore no cross-language coordination needed.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A test reproduces the race: a stage lost to a socket blip, followed by a completed reconnect, causes `go_live` to be sent against a stale view | `flutter test test/controllers/live_controller_race_test.dart` before the fix | Test FAILS asserting no `go_live` was sent | contract iteration ledger | PASS |
| C-002 | yes | After the fix, a stage lost to a socket blip never sends `go_live` | `flutter test test/controllers/live_controller_race_test.dart` | All tests pass | test output | PASS |
| C-003 | yes | `act()` reports a distinguishable outcome; a command that lands on a superseded connection epoch is NOT reported as applied | same file | All tests pass | test output | PASS |
| C-004 | yes | The go-live guard is evaluated against a snapshot proven to post-date the stage, not a poll-coalesced earlier one | same file | All tests pass | test output | PASS |
| C-005 | yes | Blackout and Clear All require a second confirming tap; un-blackout stays one tap | `flutter test test/views/emergency_strip_test.dart` | All tests pass | test output | PASS |
| C-006 | yes | Audience-facing controls are disabled while reconnecting and stay disabled until a post-reconnect snapshot lands | `flutter test test/views/` | All tests pass | test output | PASS |
| C-007 | yes | No LAN wire fixture changed | `git diff --stat` on `test/models/protocol_test.dart` | no diff | git output | PASS |
| C-008 | yes | Full mobile gate is green | `make mobile-test` | `flutter analyze` no issues; all tests pass | terminal output | PASS |
| C-009 | no | Bounded-memory: no unbounded queue/cache added | code review of the diff | no growth-unbounded structure | diff review | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `flutter test test/controllers/ test/views/emergency_strip_test.dart`
- Broader regression verification: `make mobile-test` from repo root (`flutter analyze` + full `flutter test`).
- Independent verifier: code-reviewer (Cody) / QA (Quinn) via ClickUp `code review` status — this agent does not self-approve the fix.
- Required environment: local macOS Flutter toolchain.

## Iteration ledger

### Iteration 1 — reproduce

- Target criterion: C-001
- Hypothesis: `act()` swallowing `SessionException` leaves `_view` pre-disconnect; `selectAndGoLive` then evaluates its guard against that pre-disconnect snapshot and fires `go_live` on the freshly reconnected session.
- Change or investigation: wrote `test/controllers/live_controller_race_test.dart` — a session that fails exactly one `select_item`, an injected `connect` returning a healthy replacement whose host has a DIFFERENT item staged (the desktop moved on while we were away).
- Verifier executed: `flutter test test/controllers/live_controller_race_test.dart` against unfixed code.
- Result: FAIL — 4 behavioural failures, each `Expected: not contains 'go_live' / Actual: ['go_live']`. Race reproduced on the plan-item path, the scripture path, the lost-confirming-refresh path, and the poll-coalescing path.
- New evidence: the poll-coalescing path (`refresh()` early-returning on `_refreshing`) reaches the same stale guard with **no socket blip at all** — not described in the ticket. The happy-path test passed, confirming the harness is not trivially failing.
- Decision: iterate

### Iteration 2 — fix the state layer

- Target criterion: C-002, C-003, C-004
- Hypothesis: a `CommandOutcome` return plus a monotonic connection epoch, with the guard evaluated against a snapshot explicitly fetched under that same epoch, makes every one of the four paths unreachable.
- Change or investigation: `CommandOutcome` enum; `_epoch` bumped on session swap; `_confirmedView(epoch)` non-coalescing, non-reconnecting fetch; both compound helpers gated on `applied` + a same-epoch confirmed snapshot; `act()` refuses while `_reconnecting`.
- Verifier executed: `flutter test test/controllers/` then full `flutter test`.
- Result: PASS — 18 controller tests, then 103 total, all green. Commit `2884c63`.
- New evidence: all pre-existing controller tests (denial lifecycle, revoked device, fetchChapter fallback) unaffected; the state fix is green with **no UI change**, so it stands on its own.
- Decision: iterate

### Iteration 3 — the UI safety story (86ajxx4x8)

- Target criterion: C-005, C-006
- Hypothesis: an inline arm-then-confirm on `EmergencyStrip` plus a `syncing` gate wired through emergency/transport/plan controls satisfies the story without a modal and without relying on the UI to hide the race.
- Change or investigation: `EmergencyStrip` → stateful inline confirm with injectable window; `LiveController.syncing` (`_reconnecting || _viewEpoch != _epoch`); disabled states in `EmergencyStrip`, `LiveTab`, `PlanTab`; banner split; prompt post-reconnect re-read.
- Verifier executed: `make mobile-test`
- Result: PASS — analyze clean, 115 tests. Commit `2706651`.
- New evidence: two harness defects found and fixed in my own tests (a pending 2s reconnect-retry timer, and a deadlock where a never-completing `connect` also blocked `refresh()`); the corrected harness reconnects successfully but holds the *re-sync* open, which is the state the story is actually about.
- Decision: complete

## Risks and rollback

- Risks: making `act()` stricter could suppress a legitimate go-live after a benign reconnect. Mitigated by failing *closed* — the operator simply taps again against a now-truthful view, which is the correct behaviour for an audience-facing action.
- Rollback or recovery: single commit per ticket; `git revert` is sufficient.

## Pause and escalation conditions

- If a fix requires a wire-protocol change: STOP and escalate — the Rust fixtures are pinned cross-language and no one owns the Rust LAN crate this session.
- If `make mobile-test` fails for reasons outside `implementation/mobile/`: report, do not fix another agent's lane.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-mobile-reconnect-race-safety.md`
- Validator result: PASS
- Independent verification result: PENDING — handed to `code review` in ClickUp
- Terminal state: GATE_REVIEW — implementation complete and verified; independent review/QA is owned elsewhere and must not be self-approved
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ajxwcft and 86ajxx4x8; both moved to `code review`
