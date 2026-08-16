# Goal Contract — GOAL-desktop-window-lifecycle-defects

## Identity

- Goal ID: GOAL-desktop-window-lifecycle-defects
- Parent goal ID: BUILD-selahcue
- Title: The output process can always be quit, and a transient window-open failure never becomes a persisted "screen disabled"
- Role: backend-engineer
- Status: BLOCKED (C-001..C-007 PASS; C-008 blocked by another agent's in-flight crates)
- Execution engine: goal
- ClickUp task: NONE (post-merge review remediation of 447a4a9 / 4aac4af; Build Control 86ajnx548)
- Created: 2026-08-16
- Updated: 2026-08-16
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Two defects already on `main` are fixed with tests that fail if the fix is reverted: (1) closing
every output window leaves an unquittable process; (2) a transient window/GPU open failure is
written to the persisted screen registry as a durable "screen disabled".

## Baseline

Verified by reading `implementation/desktop/crates/selahcue-desktop/src/main.rs` at commit
`419d8a6` (working tree):

- `WindowEvent::CloseRequested` (line ~1960) calls `close_screen(role)` and never exits.
  `App`'s `ApplicationHandler` implements only `resumed`, `window_event`, `new_events`,
  `about_to_wait` — no `device_event`, no `user_event` — so `KeyboardInput`, and therefore the
  Cmd-Q / Ctrl-Q quit chord, can reach the process only through a focused window. With both
  windows closed there is no route to `event_loop.exit()` outside smoke mode.
- `print_connect_banner` (line ~2485) tells the operator that closing a window never stops the
  process and that Cmd-Q is the way out.
- `open_screen`'s failure arm (line ~1876) calls `set_screen_enabled_locally(role, false)`, which
  dispatches `Command::SetScreenEnabled` → `screen_registry_dirty = true` → the autosave at
  line ~1634 writes the registry to the store.
- `set_screen_enabled_locally` (line ~1825) reads `already` through `.unwrap_or(false)`, so a
  poisoned controller mutex makes it call `drive`, which silently no-ops; retry suppression
  therefore depends on a registry write that can fail without a signal.
- `mod window_lifecycle_tests` models `reconcile_windows` decisions only. Nothing models what the
  process can still do after those decisions are performed.

## Inputs and evidence sources

- `implementation/desktop/crates/selahcue-desktop/src/main.rs`
- `implementation/desktop/crates/selahcue-app/src/controller.rs` (`set_screen_enabled`, `take_screen_registry_dirty`)
- Commits `447a4a9`, `4aac4af`, `f40e9c1`
- `CLAUDE.md`, `docs/architecture/ARCHITECTURE.md` (bounded resource use; no component failure blanks live output)

## Scope

### In scope

- `implementation/desktop/crates/selahcue-desktop/src/main.rs` (behaviour + tests + banner text)
- `implementation/desktop/crates/selahcue-operator/dist/app.css` — the `.scr-pill-closed` comment only
- `implementation/mobile/selahcue_controller/analysis_options.yaml` — a comment recording why the exclusion list exists

### Non-goals

- `selahcue-import/`, `selahcue-engine/`, `selahcue-operator/src/media_store.rs` (another agent owns these)
- Any colour change in `dist/`, any change to the Dart exclusion list itself
- Committing, staging, resetting or reverting — the owner commits

### Constraints

- Closing one window while another remains open must keep the process alive (it hosts the LAN
  server and the presentation state paired controllers depend on).
- An open failure must be transient in-memory state, never a persisted registry change.
- Retry suppression must not depend on a registry write that can silently fail.
- Memory stays bounded (no unbounded retry state).

### Assumptions and unknowns

- ASSUMED: "closing the last window exits" is scoped to the close-button gesture, not to every
  transition to zero open windows. A registry toggle that disables both built-ins is a
  configuration action and must not kill the host — an NDI-only venue (main/stage off, a virtual
  `stream` screen on) is a valid windowless configuration, and the remote operator who reached
  that state still has a console to recover from. Flagged to the owner for confirmation.
- ASSUMED: closing the LAST window is a QUIT gesture, so it must not also write
  `enabled = false` for that screen. Persisting it would reproduce defect 2's end state (next
  launch presents nothing, smoke gate exits 1) through the quit path.

## Dependencies and approvals

- Owner decision on the two ASSUMED scoping points above — reported, not blocking the fix.
- Concurrent agent in `selahcue-import` / `selahcue-engine` / `media_store.rs` — no file overlap.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The process is never simultaneously running and unreachable by the quit chord, over every close-button press from every reachable window state | `cargo test -p selahcue-desktop --bin selahcue-output window_lifecycle_tests` | `the_process_is_never_left_running_with_no_way_to_quit_it` passes | 20 passed; fails on revert (left false, right true) | PASS |
| C-002 | yes | Closing the last window quits; closing a window while another remains does not | same | `closing_the_last_window_is_a_quit_gesture` passes | 20 passed; fails on revert (left CloseScreen, right Quit) | PASS |
| C-003 | yes | A window-open failure leaves the persisted screen registry untouched (screen still enabled, registry not marked dirty) | same | `a_failed_open_never_reaches_the_persisted_registry` passes | 20 passed; fails on revert ("the screen must still be ENABLED") | PASS |
| C-004 | yes | A window-open failure produces exactly one attempt per operator enable, even when the registry still reports the screen enabled | same | `a_failed_open_is_attempted_once_not_once_per_frame` passes | 20 passed; fails on revert (left 10000, right 1) | PASS |
| C-005 | yes | The connect banner states the real quit routes | manual read of `print_connect_banner` | banner names both Cmd-Q/Ctrl-Q (focused window) and closing the last window | main.rs `print_connect_banner` | PASS |
| C-006 | yes | The `.scr-pill-closed` comment matches the shipped CSS | manual read | comment no longer claims the card is dimmed to 0.5 | app.css line ~2227; `operator_headless.py` 640 checks, 0 FAIL | PASS |
| C-007 | yes | `analysis_options.yaml` records why the analyzer exclusions exist | manual read | comment present, list unchanged | `flutter analyze` — No issues found | PASS |
| C-008 | yes | The full local CI gate is green | `make ci` | exit 0 | fails in `selahcue-engine/tests/test_probe.rs` + `selahcue-import/src/pptx.rs` (another agent's in-flight, non-compiling crates) — every owned gate step run individually is green | BLOCKED |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `cargo test -p selahcue-desktop --bin selahcue-output`
- Broader regression verification: `make ci` (fmt --check, clippy -D warnings, all suites,
  operator check, headless operator webview check, flutter analyze + test)
- Revert-sensitivity: for C-001..C-004, restore the pre-fix behaviour locally and confirm the
  named test fails.
- Independent verifier: code-reviewer (Cody) on the working-tree diff
- Required environment: macOS dev machine, `$HOME/.cargo/bin` and `$HOME/flutter/flutter/bin` on PATH

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004
- Hypothesis: making the exit rule derive from a stated "can the quit chord still reach us"
  predicate, and moving retry suppression into an in-memory `OpenFailures` value threaded through
  `reconcile_windows`, satisfies all four without touching the store.
- Change or investigation: added `quit_chord_reachable` / `CloseOutcome` / `close_button_outcome`
  and `OpenFailures` / `record_open_outcome` to `main.rs`; threaded `&mut OpenFailures` through
  `reconcile_windows`; `CloseRequested` now quits on the last window without writing the registry;
  `open_screen`'s failure arm no longer calls `SetScreenEnabled`; banner and smoke-fail message
  retold; five new tests.
- Verifier executed: `cargo test -p selahcue-desktop --bin selahcue-output`
- Result: 20 passed, 0 failed.
- New evidence: revert-sensitivity run — with the three pre-fix behaviours restored in place,
  exactly the five new tests fail and all eight pre-existing ones still pass, which is direct
  evidence that the shipped suite could not have caught either defect.
- Decision: complete for the owned files; C-008 blocked on another agent's crates.

### Iteration 2

- Target criterion: C-008
- Hypothesis: `make ci` would be green once the desktop crate is fixed.
- Change or investigation: ran `make ci` three times over the session.
- Verifier executed: `make ci`, then each gate step individually.
- Result: `make ci` exits 1 at the first step (`cargo fmt --check`) on
  `selahcue-engine/tests/test_probe.rs` and `selahcue-import/src/pptx.rs`; `selahcue-engine`'s
  test targets do not currently compile (16 errors in `test_media`). Both are the concurrent
  agent's files and are explicitly out of scope.
- New evidence: every gate step that covers the owned files is green on its own — see the final
  evaluation below.
- Decision: blocked; report rather than edit another agent's crates.

## Risks and rollback

- Risks: exiting on the last close changes a shipped behaviour; if the owner intended every
  zero-window transition to exit, the rule needs widening by one call site.
- Rollback or recovery: the change is confined to `main.rs` plus two comments; nothing is
  committed, so `git checkout --` on the three files restores the baseline.

## Pause and escalation conditions

- If either owner decision proves unbuildable as specified, stop and report rather than working
  around it (owner instruction).
- If `make ci` fails for a reason outside the owned files, report rather than editing another
  agent's crates.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-desktop-window-lifecycle-defects.md`
- Validator result: PASS (8 criteria, 8 mandatory)
- Gate steps run individually, all green:
  - `cargo fmt --check -p selahcue-desktop` — clean
  - `cargo fmt --check` (operator root) — clean
  - `cargo clippy -p selahcue-desktop --all-targets -- -D warnings` — clean
  - `cargo clippy -p selahcue-desktop --features encryption --all-targets -- -D warnings` — clean
  - `cargo clippy -p selahcue-app --features server --all-targets -- -D warnings` — clean
  - `cargo clippy` (operator root, all targets, -D warnings) — clean
  - `cargo test -p selahcue-desktop` — 20 passed
  - `cargo test -p selahcue-desktop --features encryption` — 26 passed
  - `cargo test -p selahcue-app --features server` — 161 passed across 9 targets
  - `cargo test` (operator root) — 59 passed
  - `python3 scripts/operator_headless.py` — 640 checks, 0 FAIL
  - `flutter analyze` — No issues found; `flutter test` — 140 passed
- Independent verification result: NOT RUN — recommend code-reviewer (Cody) on the working-tree diff
- Terminal state: BLOCKED (on C-008 only; all behavioural criteria PASS)
- Remaining failed or blocked criteria: C-008 — `make ci` cannot go green until the concurrent
  agent's `selahcue-engine` / `selahcue-import` changes format and compile. Re-run once they land.
- ClickUp final evidence comment: NOT POSTED — the ClickUp MCP is rate-limited
  (`RATE_LIMIT_EXCEEDED`, retry after ~27 min). The comment body is this document's summary and
  must be posted to Build Control `86ajnx548` on the next attempt.
