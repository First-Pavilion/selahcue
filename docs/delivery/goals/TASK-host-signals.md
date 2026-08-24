# Goal Contract — TASK-host-signals

## Identity

- Goal ID: TASK-host-signals
- Parent goal ID: BUILD-selahcue (Build Control 86ajnx548)
- Title: Host signal seams — the operator console reports system health honestly instead of fabricating it
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak4xxwm
- Created: 2026-08-23
- Updated: 2026-08-23
- Maximum iterations: 12
- Independent verification required: yes

## Objective

Every system-health signal the operator console renders is backed by a real host signal that a
test drives end to end, and any signal the host cannot determine is reported as an explicit
**unknown** rather than as a healthy or a faulted value.

## Baseline

Verified by reading source on 2026-08-23; `docs/design/HOST-SIGNAL-INVENTORY.md` re-checked
anchor by anchor and found accurate.

- `EngineEvent::{OutputHeld, Recovered}` and `Engine::is_faulted()` had **zero consumers**
  outside `selahcue-engine`'s own tests. `Presenter` discarded the returned event at all 13
  live-apply call sites, so NFR-024's never-blank guarantee was correct but unobservable.
- `OperatorStateView` carried no health, recovery, session, disk, crash, fault or connection
  field. There is no system/health event channel of any kind; the console polls `view()` at 1 Hz.
- Four live fabrications: an untrue "Reconnecting…" (nothing retries — `build_backend()` is
  called exactly once, at `main.rs:2702`); absent telemetry rendered as `NO SIGNAL`; a permanent
  green "Connected" in `Backend::Local`; and the unobservable never-blank guarantee above.
- `TranscriptProvider::label()` (FR-120 honest disclosure) unsurfaced; `is_listening()` has zero
  callers; `ServicePlan::unresolved_content` has zero production callers; `cooldown` appears 0
  times in the workspace.

Three baseline corrections to the inventory, found while re-verifying:

1. `quote_match.rs` lives in `selahcue-scripture`, not `core`, and never materialises candidates
   — it tracks a running `best`, so "alternatives" is a running-max → bounded top-N change.
2. The host can resolve **neither** deck nor media existence (`media_repo` is wired into no
   consumer; decks are operator-owned), so `unresolved_content` has no host-side probe.
3. The host runs **no** `TranscriptProvider`. STT runs in the operator process and pushes in via
   `IngestTranscript`, so the detector whose liveness matters is not on the host.

## Inputs and evidence sources

- `docs/design/HOST-SIGNAL-INVENTORY.md` (the specification)
- ClickUp 86ak4xxwm; Build Control 86ajnx548
- `CLAUDE.md` — bounded-memory test rules, crate/feature traps, shared-checkout rules

## Scope

### In scope

- Tier 1b — fault/recovery observability from `Presenter` through `OperatorView` to the wire.
- Tier 1a — detector liveness + `retry_detection`.
- Tier 2 — control-link state (pure state machine in `selahcue-lan::link`); session/storage health.
- Tier 3 — `ContentLinkView.missing: Option<bool>`, then alternatives, then cooldown, then history.

### Non-goals

- Any edit under `implementation/mobile/**` (owned by another session).
- Overturning the deliberate output-window retry design (`desktop/main.rs:266-271`).
- Webview/`dist/**` changes (owned by another agent).
- A fault log or detection history of unbounded size.

### Constraints

- Additive wire fields only; `VERSION` stays 2 and the pinned cross-language fixture bytes are unchanged.
- `cargo test -p selahcue-app` requires `--features server`.
- `make ci` must not be run (slot held by the coordinator).
- Bounded memory throughout; every bounded claim mutation-verified with siblings, never `--exact`.

### Assumptions and unknowns

- UNKNOWN: whether the host should report detector liveness at all, given it cannot observe the
  operator-local STT worker. Current position: report only what the host knows and mark the rest
  unknown. Validation owner: coordinator.

## Dependencies and approvals

- Wire clearance for `protocol.rs` — coordinator, GRANTED 2026-08-23.
- `selahcue-lan::link` placement for the Tier 2 state machine — coordinator, AGREED.
- Tier 3 sequencing, stopping before history — coordinator, AGREED.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A fault reported at the real producer holds the live output without blanking it | `cargo test -p selahcue-present --test test_health` | 9 passed; live bytes unchanged after a fault | test output | PASS |
| C-002 | yes | A held output and a healthy one are distinguishable while pixel-identical | `cargo test -p selahcue-present --test test_health` | `a_held_output_is_distinguishable_from_a_healthy_one_with_identical_pixels` passes | test output | PASS |
| C-003 | yes | A recovery occurring entirely between two polls is still observable | `cargo test -p selahcue-present --test test_health` | `a_recovery_between_two_polls_is_still_visible_to_the_reader` passes | test output | PASS |
| C-004 | yes | Health is bounded: fixed-size record, exact counters over 10 000 fault cycles | `cargo test -p selahcue-present --test test_health` | `health_stays_bounded_and_exact_under_repeated_fault_cycles` passes; compile-time size assert holds | test output + `health.rs` `const _: () = assert!(...)` | PASS |
| C-005 | yes | A fault driven through the real host seam reaches the operator view and changes it | `cargo test -p selahcue-app --features server --test test_health_view` | 6 passed | test output | PASS |
| C-006 | yes | Health survives the round trip a remote console makes | `cargo test -p selahcue-app --features server --test test_health_view` | `health_survives_the_round_trip_a_remote_console_makes` passes | test output | PASS |
| C-007 | yes | "Healthy" and "cannot say" are distinguishable on the wire | `cargo test -p selahcue-app --features server --test test_health_view` | `unknown_health_and_healthy_health_are_different_on_the_wire` passes | test output | PASS |
| C-008 | yes | The pinned cross-language fixture bytes are unchanged by the new field | `cargo test -p selahcue-lan --test test_protocol` | 25 passed, `wire_fixtures_are_stable_for_cross_language_clients` green with no fixture-string edit | test output | PASS |
| C-009 | yes | The Tier 1b tests fail when the control they name is removed | 6 mutations run with siblings, never `--exact` | every mutation RED | mutation log in ClickUp comment | PASS |
| C-010 | yes | No regression in the touched crates | `cargo test -p selahcue-present` / `-p selahcue-lan --features server` / `-p selahcue-app --features server` | 220 / 101 / 176 passed, 0 failed | test output | PASS |
| C-011 | yes | Formatting and lint gates pass on changed files | `rustfmt --check` per file; `cargo clippy --all-targets` | no diff; no warnings | command output | PASS |
| C-012 | yes | The excluded Tauri operator crate still compiles | `cargo check --manifest-path crates/selahcue-operator/Cargo.toml` | exits 0 | command output | PASS |
| C-013 | yes | Tier 1a — detector liveness separates a dead detector from a silent room; retry is unreachable where it cannot work | `cargo test -p selahcue-core --test test_detector`; both operator build configs compile-checked | 8 passed; forging a `RetryRequest` is `error[E0603]` | test output + compile error | PASS |
| C-014 | yes | Tier 2 — control-link state machine is pure, tested, and reports `local` rather than a green "Connected" | `cargo test -p selahcue-lan --test test_link` | 10 passed | test output | PASS |
| C-019 | yes | Tier 2 — the operator shell's connection pill READS `LinkStatus` (the fabrications persist in the UI until it does) | operator shell wiring + headless check | pill reflects real state | `scripts/operator_headless.py` | PENDING |
| C-015 | yes | Tier 2 — session/storage health reaches the view; `DiskStatus` verdict replaces raw `disk_free`, with `unknown` as a real outcome | `cargo test -p selahcue-app --features server --test test_health_view`; `cargo test -p selahcue-desktop` | 14 passed / 28 passed | test output | PASS |
| C-020 | yes | `deck_restore` — undo delete restores the REAL deck, retained in a bounded buffer | `cargo test -p selahcue-present --test test_trash`; `cargo test --manifest-path .../selahcue-operator/Cargo.toml` | 8 passed / 64 passed | test output | PASS |
| C-021 | yes | Webview consumer contract published | `docs/delivery/HOST-SIGNAL-WEBVIEW-CONTRACT.md` + shape pinned by test | `the_tauri_view_matches_the_shape_promised_to_the_webview` passes | doc + test output | PASS |
| C-016 | yes | Tier 3.1 — `ContentLinkView.missing` is tri-state and never claims a deck is missing when the host cannot tell | test asserting `None` for unresolvable-by-host kinds | passes | test output | PENDING |
| C-017 | no | Tier 3.2–3.4 — alternatives, cooldown, history (history deferrable by agreement) | per-slice tests | passes | test output | PENDING |
| C-018 | yes | Independent code review recorded | `docs/delivery/CODE-REVIEW-batch-host-signals.md` | review complete, findings dispositioned | review doc | PENDING |

## Verification plan

- Focused verification: per-crate test files above, each run with siblings.
- Broader regression verification: full suites for `selahcue-present`, `selahcue-lan`, `selahcue-app`.
- Mutation verification: for every criterion claiming a control, break the control and confirm RED.
- Independent verifier: code-reviewer, then QA. Not self-certified.
- Required environment: local macOS desktop workspace; no GPU required.

## Iteration ledger

### Iteration 1 — Tier 1b (fault/recovery)

- Target criterion: C-001…C-011
- Hypothesis: routing every live `apply` through one recording helper, deriving `held` from the
  engine, and carrying counters rather than a log makes NFR-024 observable end to end without
  an event channel and without unbounded growth.
- Change: new `selahcue-present::health` module; `Presenter::{inject_fault, output_health}`;
  13 live-apply sites routed via `apply_live`; `OutputHealthView` on the wire;
  `LiveController::report_fault`; `output_health` on `OperatorView`/`OperatorStateView`.
- Verifier executed: the C-001…C-011 commands, plus a 6-mutation battery on Tier 1b and a
  6-mutation battery on the end-to-end seam.
- Result: all PASS. 11 of 12 mutations killed.
- New evidence: **one mutation survived** — a redundant `held.then(...)` guard in
  `output_health_view` duplicated an invariant already enforced (and mutation-killed) in
  `OutputHealth::record`, so no test could reach the copy. Resolved by removing the duplicate
  and pinning the invariant at its single source across the whole fault matrix
  (`output_health_never_names_a_reason_when_not_held`). Re-verified RED under mutation.
- Decision: iterate to Tier 1a.

## Risks and rollback

- Risk: a future live-apply call site bypasses `apply_live` and drops a fault transition.
  Mitigated by the invariant test at the single enforcement point; not preventable by types alone.
- Risk: shared checkout — `stage.rs`, `test_present.rs`, `test_tokens.rs`, `test_stage.rs`,
  `test_measure.rs` and several untracked test files belong to other sessions. Mitigated by
  using a fresh `tests/test_health.rs` / `tests/test_health_view.rs` and staging only own hunks.
- Rollback: all changes are additive; reverting the `health` module, the wire field and the two
  test files restores prior behaviour with no data or protocol migration.

## Pause and escalation conditions

- Any change that would require editing `implementation/mobile/**` — stop, report to coordinator.
- Any signal that cannot be obtained without unreasonable change — report as an honest unknown
  with evidence rather than inventing a value.
- Before Tier 3.4 (history) — check in with the coordinator, per agreement.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-host-signals.md`
- Validator result: PENDING
- Independent verification result: PENDING
- Terminal state: PENDING
- Remaining failed or blocked criteria: C-014…C-018 pending
- ClickUp final evidence comment: PENDING


### Iteration 2 — Tier 1a (detector liveness)

- Target criterion: C-013
- Hypothesis: putting the state rule in `selahcue-core` (compiled and tested unconditionally)
  and leaving only the worker handle behind the `stt` `#[cfg]` makes detector liveness
  verifiable, and returning a permission *token* rather than a boolean makes retry unreachable
  — not merely disabled — in a build that has no detector.
- Change: new `selahcue-core::detector` (`DetectorState`, `DetectorSignals`, `detector_state`,
  `RetryRequest`); `listening.rs` retains the terminal failure and the FR-120 provider label;
  `detection_health` / `retry_detection` Tauri commands in both build configurations.
- Verifier executed: `cargo test -p selahcue-core --test test_detector` (8 passed); a 5-mutation
  battery with siblings; a compile-failure check that forging a `RetryRequest` is rejected;
  `cargo check` of the operator with AND without `--features stt`; both `cargo fmt --check`
  gates; clippy.
- Result: PASS. All 5 mutations killed, including collapsing `unsupported` into `unavailable`.
  Forging the token is `error[E0603]: tuple struct constructor RetryRequest is private`.
- New evidence: baseline premise corrected — the shipped Windows installer builds
  `--features stt` (`windows-installer.yml:110`) and `make` auto-enables it when cmake is
  present, so `unsupported` is a build-configuration state, not the product's normal condition.
  Separately: CI clippies the operator WITHOUT `stt`, and the `stt` configuration has a
  pre-existing `manual checked division` clippy error at `listening.rs:115` (verbatim at HEAD,
  not from this work) that CI therefore cannot see.
- Decision: iterate to Tier 2.


### Iteration 3 — Tier 2 (control-link state machine)

- Target criterion: C-014
- Hypothesis: a pure state machine in `selahcue-lan::link` can make all three connection-pill
  fabrications structurally unrepresentable — `Local` as a state distinct from `Connected`, and
  `Reconnecting` true exactly when an attempt is scheduled.
- Change: new `selahcue-lan::link` (`LinkState`, `LinkStatus`) — bounded automatic retries then
  an honest `Disconnected` with a manual retry; monotonic epoch for stale-reply invalidation
  (mirroring the mobile controller's `_epoch`); one capped, char-boundary-safe retained error.
  The output-window retry decision is called out in the module doc as deliberately distinct.
- Verifier executed: `cargo test -p selahcue-lan --test test_link` (10 passed); full lan suite
  with `--features server` (111 passed); a 7-mutation battery; `cargo fmt --check`; clippy.
- Result: PASS after remediation. All 7 mutations killed.
- New evidence: **a mutation survived and exposed a vacuous test of my own.** The multibyte
  truncation test used a 2-byte character against a 200-byte cap, so the cut always landed on a
  char boundary and a naive `&s[..max]` passed it. Rewritten to sweep character widths (2/3/4
  bytes) AND leading offsets, and to assert that some case genuinely put the cap mid-character
  before believing the result. Re-verified: the naive slice now panics with
  `byte index 200 is not a char boundary; it is inside '☃'`. The sweep also stays non-vacuous
  when the cap is changed to 204, which defeats width-alignment alone.
- Decision: iterate — wire the shell (C-019), then session/storage health (C-015).


### Iteration 4 — C-015 (storage/session health) + webview contract

- Target criterion: C-015, C-021
- Change: `StorageHealthView` / `SessionHealthView` on the wire and the view; `LiveController`
  setters; `guard::DiskStatus::Ok` extended to carry its figure; `SessionStore` retains the last
  autosave error; the desktop host publishes health as the FIRST statement in `autosave()`.
  Published `docs/delivery/HOST-SIGNAL-WEBVIEW-CONTRACT.md`.
- Verifier executed: app 14 / desktop 28; a 6-mutation battery; both fmt gates; clippy.
- Result: PASS. All 6 mutations killed, including reporting an unreadable disk as `"ok"`.
- New evidence: `autosave()` returns early exactly when checkpoints are halted — the moment the
  operator most needs telling. Rather than rely on a test to police the ordering, the publish was
  moved to the first statement of the function, so no future early return can skip it. The
  contract's claimed JSON shapes are pinned by a test rather than left as prose.
- Decision: iterate to `deck_restore`.

### Iteration 5 — `deck_restore` (owner-approved, operator-side)

- Target criterion: C-020
- Note: **operator-side, not host-side.** Decks are operator-owned by design and the host has no
  deck store; only the bounded container lives in the workspace, for testability.
- Change: `selahcue-present::trash::DeckTrash` (bounded on entry COUNT and BYTES);
  `DeckLibrary::{delete → retain, restore, can_restore, restorable}`; `deck_restore` Tauri command.
- Verifier executed: `test_trash` (8 passed), operator suite (64 passed), a 6-mutation battery on
  the buffer and a 3-mutation battery on the library path.
- Result: PASS after remediation. All 9 mutations killed.
- New evidence: **two vacuous controls found, both mine.** (1) The byte budget was originally
  4 MB while the largest legal deck measures 2 010 940 bytes — so no deck could ever be refused,
  the refusal branch was dead code, and its test could not have failed. The premise assert caught
  it before it shipped. Fixed by sizing the budget to 1.5 MB and adding
  `const _: () = assert!(MAX_TRASH_BYTES < MAX_LEGAL_DECK_BYTES);` so raising it past the point
  of uselessness breaks the build. (2) Removing the byte cap entirely SURVIVED the battery,
  because every other deck in the file is a few hundred bytes and only the entry cap was ever
  doing any work; fixed by adding a test using three ~600 KB decks, where an eviction can only
  have come from the byte budget.
- Decision: report; Tier 3 next, stopping before history.
