# Goal Contract — 86ajy0hxg

## Identity

- Goal ID: 86ajy0hxg
- Parent goal ID: 86ajxxqtp (Service Plan builder)
- Title: Service Plan resilience — autosave slots + restore, crash-loop Resume/StartClean, item Undo, all additive on the LAN wire
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy0hxg
- Created: 2026-09-25T20:52:00Z
- Updated: 2026-09-26T01:30:00Z
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Expose, over the LAN wire, three resilience capabilities that already have partial
groundwork in the desktop app but no client-reachable surface: (1) a bounded
autosave-slot history with a restore command, (2) a crash-loop Resume/StartClean
decision the operator can make instead of the desktop silently forcing a clean
start, and (3) a wire-level plan-item Undo/Redo. All additive to the wire
protocol; `make ci` green; a controller test for restore + crash-loop.

## Baseline (verified)

- `ControllerSnapshot`/`LiveController::snapshot`/`restore` exist
  (`selahcue-app/src/controller.rs:54`, `:1674`, `:1718`) but only round-trip the
  SINGLE `session_state` singleton row via `session_repo` — no slot history.
- `guard::LaunchGuard`/`LaunchVerdict` (`selahcue-desktop/src/guard.rs`) already
  detect a crash loop (3 rapid launches/60s) and `App::new()` already force-starts
  clean with checkpointing paused when tripped — but this decision is baked in at
  process boot, before the LAN server exists, and is never exposed as an operator
  choice. `SessionHealthView` (`selahcue-lan/src/protocol.rs:1381`) already reports
  `restored`/`crash_loop`/`rapid_launches`/`autosave_error` read-only.
- Whole-plan undo/redo (`LiveController::undo_plan`/`redo_plan`,
  `controller.rs:3469`/`:3483`, bounded by `MAX_PLAN_UNDO=60`) already exists and
  is exercised by the LOCAL Tauri operator shell (`operator.rs:371-387`), but has
  no `Command` variant — a remote/LAN client cannot invoke it at all today.
  `ServicePlan::remove` (`selahcue-core/src/plan.rs:676`) returns the removed
  `PlanItem` (id + content link intact); `ItemId` is never reused. Undo already
  restores the exact prior document (id + content link), which is the cheapest,
  best-tested way to satisfy "undo a deleted item without losing its id/link".
- The remote-command dispatch path (`handler_for` in `controller.rs`, wired via
  `start_remote_control`/`run_server` in `main.rs`) closes ONLY over
  `Arc<Mutex<LiveController>>` — it has no access to `App`'s `store`/`clean_mode`/
  `launch_guard`. `selahcue-app` must not depend on `selahcue-data` (explicit
  constraint, documented at `sermon_note_store.rs:1-20`); host-storage-backed
  commands go through an injected trait seam (`TranscriptSink`, `SermonNoteStore`
  are the existing examples), not a direct dependency.

## Inputs and evidence sources

- ClickUp task 86ajy0hxg (full description) + parent 86ajxxqtp.
- `implementation/desktop/crates/selahcue-app/src/controller.rs`,
  `sermon_note_store.rs`, `transcript_sink.rs`.
- `implementation/desktop/crates/selahcue-desktop/src/main.rs` (`App`,
  `SessionStore`, `autosave`, `guard` usage).
- `implementation/desktop/crates/selahcue-data/src/{session_repo,migrations,
  plan_repo,db}.rs`.
- `implementation/desktop/crates/selahcue-lan/src/{protocol,rbac}.rs` +
  `tests/test_protocol.rs`, `tests/test_rbac.rs`.
- `implementation/mobile/selahcue_controller/test/models/protocol_test.dart`.
- Repo `CLAUDE.md` (wire cross-language contract; bounded-memory test
  convention) and `implementation/desktop/CLAUDE.md` (build/test commands,
  worktree binary staging, one-`make ci`-at-a-time).

## Scope

### In scope

1. **Autosave slots + restore (FR-005 last-3, FR-079 integrity).**
   New `selahcue-data` table `autosave_slot` (migration v22→v23) holding up to
   `MAX_AUTOSAVE_SLOTS = 3` distinct restore points (mirrors `session_state`'s
   columns + `saved_at_ms` + optional `label`), captured from the existing
   autosave path at a minimum spacing so slots are meaningfully distinct. New
   `selahcue-app::AutosaveStore` trait (seam, mirrors `SermonNoteStore`) with
   `list_slots`/`load_slot`; `load_slot` runs `Database::integrity_check` (the
   existing FR-079 `PRAGMA integrity_check` wrapper) before trusting the read.
   New wire: `Command::ListAutosaveSlots` → `ServerMessage::AutosaveSlots`,
   `Command::RestoreAutosave { slot }` → Ack/Deny.
2. **Crash-loop Resume/StartClean.** New `Command::Resume` / `Command::StartClean`,
   only accepted while the cached `SessionHealthView.crash_loop` is true. The
   controller records the decision (`pending_crash_decision`, poll/drain — the
   existing `state_dirty`-style pattern, since the controller stays storage-free)
   and the host's existing per-frame `App::autosave` tick — which already owns
   `store`/`clean_mode`/`launch_guard` — performs the actual I/O: `Resume` re-reads
   the untouched preserved session and swaps it in (new
   `LiveController::resume_preserved(plan, snap)`, built from the existing,
   already-tested `restore()`); `StartClean` re-enables checkpointing and
   persists the already-running fresh plan. Both call `LaunchGuard::mark_stable`
   so a resolved trip does not compound. `SessionHealthView` gains a `resumable`
   bool (computed once at boot, read-only, no side effect on `SessionStore`) so a
   client can tell "crash loop, nothing to resume" from "crash loop, a session is
   waiting."
3. **Item Undo (wire-level).** `Command::UndoPlan` / `Command::RedoPlan`, thin
   wire wrappers over the existing `undo_plan()`/`redo_plan()`. No new
   soft-delete state — the existing whole-plan undo stack already restores a
   removed item with its original id and content link, which is a strictly
   better fidelity guarantee than a new value-level "undo just this remove"
   would give for less new code and no new risk to the already-tested undo
   invariants (Live integrity, MAX_PLAN_UNDO bound).
4. RBAC wiring for all 6 new commands in `selahcue-lan::rbac::required_permission`
   (an exhaustive match — the compiler forces this).
5. Rust-side wire fixture tests for every new `Command`/`ServerMessage`/view
   field in `selahcue-lan/tests/test_protocol.rs`, following the existing
   additive-field/new-variant pattern.
6. Controller tests in `selahcue-app/tests/test_controller.rs` for: slot
   listing/restore (including an integrity-check failure path), the
   Resume/StartClean gate (denied when not in a crash-loop), and UndoPlan/RedoPlan
   over the wire.
7. `selahcue-data` repo tests for `autosave_repo` (bound enforcement, ordering,
   integrity-check interaction).

### Non-goals (explicit, justified)

- **Item 4, "loading/scanning" signal (frame 9)** — the ticket marks this
  optional ("otherwise the frontend fakes it optimistically"). Deferred: no
  natural host-side seam exists today for a multi-phase "opening/scanning"
  seam without inventing new state with no consumer in this batch (the
  consuming frontend ticket 86ak8467m is explicitly out of scope for this
  session). Not required for `make ci` green or the ticket's DoD.
- **Mobile Dart (`protocol.dart`) changes.** The ticket's frontend consumer
  (86ak8467m, "Service Plan states") is the desktop OPERATOR console
  (`selahcue-operator`, plain JS), not the Flutter mobile controller — verified
  by grep: `protocol.dart` today has NO builders for most existing plan-editing
  commands (`AddItem`/`RemoveItem`/`PublishPlan`/etc.) and does not model
  `SessionHealthView`/`StorageHealthView` at all, even though both already exist
  on the wire. Adding Dart support for commands the mobile client does not send
  would be unrequested scope. The cross-language byte-stability CLAUDE.md rule
  is satisfied because nothing EXISTING on either side changes shape — only new,
  purely-additive fields/variants are introduced, and the Rust-side fixture test
  is extended to pin them.
- **selahcue-operator (dist/ JS) wiring.** Explicitly out of scope per the
  dispatching agent's instruction — follow-on work for 86ak8467m once this
  merges.
- **A new `Permission` enum variant for RBAC.** The 6 new commands are all
  Operator-only in effect; reusing the existing Operator-only `EditPlan`
  permission (for `RestoreAutosave`/`Resume`/`StartClean`/`UndoPlan`/`RedoPlan`)
  and `Monitor` (for the read-only `ListAutosaveSlots`) keeps the RBAC table's
  blast radius minimal. Documented inline at the match arm.

### Constraints

- Live output must remain unaffected / never blank during any of this (NFR-024).
- Wire changes additive only: new `Option` fields with
  `skip_serializing_if`, new enum variants — no existing fixture byte changes.
- `selahcue-app` must not gain a dependency on `selahcue-data` (seam pattern only).
- One `make ci` at a time in this shared checkout (CLAUDE.md) — check for
  concurrent sessions before running it.
- `binaries/` placeholders needed before `selahcue-operator` compiles in a
  fresh worktree — `make stage-operator-binaries` / the `make ci` target
  already does this.

### Assumptions and unknowns

- ASSUMED: "default Resume" in the ticket's scope line describes the
  frontend's default-selected UI affordance for the two-button choice, not a
  requirement that the backend auto-fire Resume without an explicit command —
  the ticket only asks this story to expose "a crash-count/last-live-state
  signal on the view + Resume vs StartClean commands," which this contract
  delivers; the frontend ticket (86ak8467m, out of scope here) owns which
  button reads as the default. If this reading is wrong, it is a cheap,
  additive follow-up (no wire break).

- **MATERIAL FINDING (discovered mid-implementation, after the crash-loop wire
  commands were already built and tested) — read before claiming this bullet
  "done":** ClickUp 86ak846ge (open architecture decision, status
  `planning/todo`, "Do not implement against this ticket. It records an open
  question; it does not answer it.") establishes that the crash-loop breaker
  decides **at process launch, before the operator webview/LAN server exist**,
  so this ticket's original wording ("Resume vs StartClean commands... Powers
  frame 16") rests on a wrong dependency: wire commands alone cannot unblock
  the frame-16 DIALOG, because the host has already restored-or-started-clean
  by the time any client could send one. 86ak846ge lists three options
  (amend the design / defer startup / **restore-after-the-fact**) and states
  explicitly that an owner/architect decision is still needed, and that once
  decided "re-scope 86ajy0hxg's crash-loop bullet." 86ak8467m (frontend) has
  already had its former AC-5 (the frame-16 dialog) **removed** for exactly
  this reason.

  This contract's `Command::Resume`/`Command::StartClean` implement 86ak846ge's
  **Option 3 ("restore-after-the-fact")** exactly: the boot sequence is left
  completely unchanged (still automatic, still safe — NFR-024 untouched), and
  the two new commands let an operator who has already connected reverse a
  clean-start decision after the fact, without holding launch open. This is a
  genuine, tested, additive capability — but it is **not** an implementation
  of the frame-16 dialog as designed, and it does **not** resolve 86ak846ge;
  that remains an owner/architect call. The honest claim for this contract's
  crash-loop bullet is: *the backend now exposes Option 3, tested and ready,
  for the architect/product owner's consideration* — not *frame 16 is
  unblocked*. The autosave-slots/restore and item-Undo bullets are explicitly
  called out in 86ak846ge as **unaffected** by this question.

  Action taken: flagged on 86ak846ge (informational comment, not a decision)
  and on 86ajy0hxg's own handoff, so the architect/product owner can bless,
  amend, or reject Option 3 with working code already in front of them,
  rather than deciding in the abstract. Not reverted, because it is safe,
  tested, and cheap to keep or discard either way.
- ASSUMED: autosave slots are captured from the SAME state the singleton
  autosave already captures (no separate dirty-tracking needed) — spaced by a
  minimum interval so 3 slots are meaningfully distinct restore points, not
  near-duplicates of the same instant.

## Dependencies and approvals

- None blocking — additive backend work, no product/architecture decision
  required. Four-reviewer gate (Cody/Vera/Sana/Quinn) required before
  VERIFIED_COMPLETE per the operating contract.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `selahcue-data` autosave-slot repo: push bounds to 3, oldest pruned, integrity check surfaced | `cargo test -p selahcue-data` | all pass (13 tests incl. `test_autosave_repo.rs`, `test_db.rs` migration fixture) | test output | PASS |
| C-002 | yes | `selahcue-app` controller: slot list/restore, Resume/StartClean gate, UndoPlan/RedoPlan wire commands | `cargo test -p selahcue-app --features server` | all pass (14 tests in `test_service_plan_resilience.rs`) | test output | PASS |
| C-003 | yes | Crash-loop: a controller test exercises Resume and StartClean paths and the never-blank invariant | `cargo test -p selahcue-app --features server` | pass (`resume_is_*`, `start_clean_is_*`, `resume_preserved_never_blanks_the_live_output`) | test output | PASS |
| C-004 | yes | Wire fixtures for every new Command/ServerMessage/field, additive (old fixtures unchanged) | `cargo test -p selahcue-lan` | all pass (33 tests), `wire_fixtures_are_stable_for_cross_language_clients` unmodified and passing | test output | PASS |
| C-005 | yes | RBAC: new commands mapped, existing `test_rbac.rs` still green | `cargo test -p selahcue-lan` | pass (26 tests, incl. new `edit_plan_implies_go_live_and_blackout_for_every_role`, `list_autosave_slots_is_monitor_tier`) | test output | PASS |
| C-006 | yes | Whole workspace + feature-gated suites clean | `make ci` (from repo root) | ALL GREEN | terminal log, twice (commit `5485763` and remediation `29643e8`), both EXIT:0 | PASS |
| C-007 | yes | Independent review (Cody, Vera, Sana, Quinn) blocking findings remediated | review artifact | 0 blocking outstanding — Cody's Blocking-1 and Vera's B-1 fixed and re-verified; Quinn PASS | published Artifact: https://claude.ai/artifact/UoV4wSbBVdo2FZqUNjJzGP (linked on PR) | PASS |
| C-008 | yes | PR opened against `main`, not self-merged | `gh pr view` | PR #102 open, base=main, Ready for review, not merged | https://github.com/First-Pavilion/selahcue/pull/102 | PASS |

## Verification plan

- Focused: per-crate `cargo test` for `selahcue-data`, `selahcue-app --features
  server`, `selahcue-lan` (default + `--features server`).
- Broader regression: `make ci` (fmt, clippy, full workspace test, feature-gated
  suites, operator check, headless webview, Flutter gate).
- Independent verifier: Cody/Vera/Sana/Quinn per the review pipeline.
- Required environment: this worktree, `implementation/desktop` Cargo workspace,
  pinned toolchain via `rust-toolchain.toml`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-006 (implementation)
- Hypothesis: additive wire + trait-seam + migration, reusing existing
  `restore()`/`undo_plan()`/`integrity_check()` primitives, satisfies all
  mandatory criteria with acceptable risk.
- Change or investigation: implement per Scope above.
- Verifier executed: per-crate `cargo test`, then full `make ci`.
- Result: all per-crate suites green; `make ci` ALL GREEN at commit `5485763`
  (fmt fixed on first attempt, then EXIT:0).
- New evidence: mid-implementation, found ClickUp 86ak846ge (open architecture
  decision) — recorded in Assumptions above; corrected the crash-loop bullet's
  framing before any completion claim.
- Decision: hand off to C-007 (review pipeline)

### Iteration 2 — review remediation

- Target criterion: C-007 (independent review)
- Hypothesis: dispatching Cody/Vera/Sana/Quinn in parallel against PR #102
  would surface real, fixable issues before merge is appropriate.
- Change or investigation: all four reviewed commit `5485763`. Vera found a
  blocking performance defect (B-1: whole-store `integrity_check` under the
  render loop's lock) and Cody found a blocking correctness defect
  (Blocking-1: silent wrong restore on an edited plan, reproduced live) plus
  a medium UX gap (Medium-3: `Resume` accepted without `resumable`). Sana
  found 4 non-blocking issues (S-1/S-2/S-4/S-7, the last two doc-only) plus 3
  nitpicks, including a live-reproduced backward-clock-jump bug (S-4). Quinn
  independently re-ran the suites plus GitHub's own CI matrix and reported
  PASS. Fixed all of the above: moved `RestoreAutosave` resolution off the
  controller lock (mirrors the already-correct `Resume`/`StartClean`
  pattern); added a plan-content fingerprint guard (new `autosave_slot`
  column, migration amended in place — pre-merge, so no v24 needed); fixed
  the ring's prune ordering (`id` not `saved_at_ms`); corrected two doc
  claims and added the RBAC invariant test they were missing; added
  real-SQLite regression tests for every one of the above.
- Verifier executed: per-crate `cargo test` + `cargo clippy -D warnings`
  after each fix, then a second full `make ci` run.
- Result: `make ci` ALL GREEN at commit `29643e8` (fmt clean, 240
  `test result: ok` blocks, 0 failures, Flutter "All tests passed!").
- New evidence: consolidated review Artifact published
  (https://claude.ai/artifact/UoV4wSbBVdo2FZqUNjJzGP) and linked on the PR;
  PR marked Ready for review.
- Decision: complete

## Risks and rollback

- Risk: crash-loop boot-sequencing change regresses existing, heavily-tested
  `App::new()` behaviour. Mitigation: boot sequence itself is UNCHANGED; only
  a new post-boot command path (`Resume`/`StartClean`) is added, gated behind
  `crash_loop` being true, handled in the existing per-frame `autosave()` tick.
- Risk: autosave-slot capture adds I/O load. Mitigation: gated by a minimum
  interval (not every autosave tick), bounded table (3 rows), reuses the
  already-open `SessionStore` connection.
- Rollback: revert the branch; no destructive migration (append-only, new
  table, no column drop).

## Pause and escalation conditions

- A conflict in `implementation/desktop/CLAUDE.md`-documented shared-checkout
  hazards (concurrent `make ci`, shared worktree) — serialize, do not fight it.
- Any requirement to touch ticket 86ak8467m or `selahcue-operator` dist/JS —
  out of scope, escalate/decline.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ajy0hxg-service-plan-resilience.md --completion`
- Validator result: `OK (completion): ... satisfies the Goal Contract schema and all mandatory criteria PASS`
- Independent verification result: Cody/Vera/Sana/Quinn all reported; 2
  blocking findings (Cody's Blocking-1, Vera's B-1) + 1 medium (Cody's
  Medium-3) + Sana's non-blocking S-1/S-2/S-4/S-7/N-1/N-2/N-4 all
  remediated and re-verified (`make ci` ALL GREEN at `29643e8`); Quinn's
  independent QA pass reported PASS with no blocking defects. Consolidated
  report: https://claude.ai/artifact/UoV4wSbBVdo2FZqUNjJzGP
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none. (Non-goal, tracked separately:
  ClickUp 86ak846ge, the crash-loop dialog architecture decision, remains
  open — explicitly not this contract's to resolve; flagged there for the
  architect/product owner.)
- ClickUp final evidence comment: posted on 86ajy0hxg
