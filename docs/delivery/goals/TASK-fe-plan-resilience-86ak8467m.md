# Goal Contract — TASK-fe-plan-resilience-86ak8467m

## Identity

- Goal ID: TASK-fe-plan-resilience-86ak8467m
- Parent goal ID: NONE (follow-on round; prior round's contract is
  `docs/delivery/goals/TASK-fe-plan-lifecycle-86ak8467m.md`, which delivered AC-1/AC-3/AC-5/AC-7/AC-8
  for frames 5/8/14/17-badge-only and is VERIFIED_COMPLETE for that slice)
- Title: Service Plan resilience states — recovery/restore banner, item-delete Undo (backend-kind
  conditional), and the "Plan updated · Review changes" reload/keep banner
- Role: frontend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak8467m
- Created: 2026-09-26
- Updated: 2026-09-26
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Ship the two backend-dependent acceptance criteria this ticket has been carrying since 86ajy0hxg
merged (PR #102) — AC-4 (Restore last autosave + amber "Recovery mode" indicator, frame 13,
`612:124`) and AC-6 (item-delete Undo restoring the original id + content link, backend-kind
conditional, frame 15, `612:584`) — plus AC-2's "Plan updated · Review changes" banner
(frame 17, `612:1020`) to the extent buildable without an architecture change, with a11y and
`make ci` green (AC-7/AC-8) covering all of it.

## Baseline

**Verified 2026-09-26** against this worktree at `82955d2` (origin/main, includes merged PR #102):

- AC-1, AC-3, AC-5 and a badge-only sliver of AC-2 are already shipped in
  `implementation/desktop/crates/selahcue-operator/dist/app.js` (PR #14 backend, PR #15 frontend,
  per ClickUp comment history). Not rebuilding any of that.
- AC-4 and AC-6 are unbuilt. `grep` for "Restore last autosave" / "Recovery mode" /
  "list_autosave_slots" across `dist/app.js` returns nothing.
- The LAN wire protocol for autosave slots/restore is fully implemented and unit-tested
  (`selahcue-lan/src/protocol.rs`: `Command::ListAutosaveSlots` L532, `Command::RestoreAutosave`
  L556, `ServerMessage::AutosaveSlots` L834, `AutosaveSlotView` L849; handled in
  `selahcue-app/src/controller.rs` L3483-3528; behavioural tests in
  `selahcue-app/tests/test_service_plan_resilience.rs`) — but **no Tauri-facing plumbing exists**:
  `selahcue-operator/src/main.rs` registers no `list_autosave_slots`/`restore_autosave` command,
  and neither `OperatorShell` nor `RemoteOperator` (`selahcue-app/src/operator.rs`) has a method
  for either. This is the gap 86ajy0hxg's own scope ("Powers frame 13") did not close.
- `plan_undo`/`plan_redo` (`main.rs` L745-758) are a confirmed, documented no-op for a Remote
  backend ("client-side plan undo is not carried over the wire") — `RemoteOperator` has no
  `plan_undo`/`plan_redo` method to call over the wire at all. This is exactly the ticket's
  named AC-6 trap. `host_connected` (`main.rs` L1180, JS `hostRemote` at `dist/app.js:6393/6741`)
  is the existing, already-wired backend-kind signal.
- Frame 16 (crash-loop Resume/StartClean) stays explicitly OUT OF SCOPE per 86ak846ge (an open
  architecture decision) — `Command::Resume`/`StartClean` are untouched by this contract.
- AC-2's "reload" has no backend primitive under the current single-plan-row model
  (`protocol.rs:1296-1314`: counters are host-authoritative and NOT persisted; there is no
  "snapshot the published document" command) — the 2026-09-14 delivery-hygiene ClickUp comment
  flags this explicitly as needing an architecture decision, not more code. See Scope/Non-goals.

## Inputs and evidence sources

- ClickUp 86ak8467m (full description + both prior comments) and its parent 86ajxxqtp
- ClickUp 86ak846ge (frame-16 decision — read, not touched)
- ClickUp 86ajy0hxg (closed; source of the wire fields this contract exposes to the webview)
- `docs/design/SERVICE-PLAN-2.0-HANDOFF.md` §2 frame table, §5, §9 (copy: "Recovery mode" amber,
  "Following live", "Plan updated · Review changes")
- `docs/delivery/goals/TASK-fe-plan-lifecycle-86ak8467m.md` (prior round's contract — conventions
  this round must keep: DOM-removal not `hidden` for view-only, computed-`display` assertions,
  single-verdict `planCanEdit`/`planIsViewOnly` consumption)
- Repo-root and `implementation/desktop/CLAUDE.md` (bounded-memory test discipline, `make ci`
  scope/gaps, shared-checkout etiquette)
- Direct source reads (this session): `selahcue-operator/src/main.rs`, `selahcue-app/src/operator.rs`,
  `selahcue-app/src/controller.rs`, `selahcue-lan/src/protocol.rs`,
  `selahcue-app/tests/test_operator_remote.rs`, `selahcue-app/tests/test_service_plan_resilience.rs`,
  `dist/app.js`, `dist/app.css`, `dist/index.html`, `scripts/operator_headless.py`

## Scope

### In scope

- **AC-4 (frame 13):** on a failed plan open, fetch autosave slots and — when any exist — show a
  "Restore last autosave" action; restoring re-renders the builder from the host's fresh view.
  Amber "Recovery mode" saved-indicator shown only in this state (no normal-state "All changes
  saved" concept is invented — none exists today and none is requested elsewhere).
  - Minimal, additive Rust plumbing to close the Tauri-command gap identified in Baseline:
    `list_autosave_slots` / `restore_autosave` Tauri commands in `main.rs`, mirrored
    `Backend::Local`/`Backend::Remote` dispatch, `OperatorShell` methods (delegate to the existing
    `LiveController::apply`, same pattern as `active_transcript_id`), `RemoteOperator` methods
    (send `Command::ListAutosaveSlots`/`RestoreAutosave`, same pattern as `load_sermon_note_draft`
    / `publish_plan`). No change to `protocol.rs` or `controller.rs` — both already complete and
    tested; this only exposes them. Flagged explicitly for reviewer scrutiny (Cody/Sana) as work
    that crosses from "frontend" into the operator crate's own Rust shell.
- **AC-6 (frame 15):** item-delete offers an Undo toast (mirrors the deck-library
  `pmLibRestorable` pattern) that calls the existing `plan_undo` command. Offered **only when
  `hostRemote === false`** (Local backend) — resolving the ticket's own trap via option (b)
  (conditional on backend kind), since `plan_undo` is confirmed inert on Remote and shipping an
  Undo that silently does nothing is explicitly disallowed by the ticket text.
- **AC-2 (frame 17), partial:** upgrade the existing badge-only signal to the full
  "Plan updated · Review changes" banner with a real "Reload" action (re-fetches and re-renders
  the full builder from host truth — a genuine action, not a no-op) and a "Keep" action
  (dismisses the banner without a fetch). See Non-goals for what this deliberately does not claim.
- A11y for all new UI: focus-trapped where a dialog is used, `role="alert"`/`role="status"` as
  appropriate, amber Recovery-mode signalled by text ("Recovery mode") never colour alone.
- `scripts/operator_headless.py` coverage for every new control, using computed-`display`
  assertions (never bare `hidden`), per the repo's own webview trap.
- Rust tests: extend `selahcue-app/tests/test_operator_remote.rs` (Remote path,
  `--features server`) and `operator.rs`'s existing `plan_undo_shell_tests` module (Local path)
  for the two new methods.

### Non-goals

- Frame 16 (crash-loop Resume/StartClean dialog) — out of scope per 86ak846ge; `Command::Resume`
  and `Command::StartClean` are not touched.
- A general saved-plan library / multi-plan reload-from-history — the host persists exactly one
  plan row (documented repeatedly in-repo); "Reload" in this contract means "re-fetch the single
  shared plan from the host", not "revert to the published revision specifically". A true
  revert-to-published primitive does not exist and is the architecture gap the 2026-09-14
  delivery-hygiene comment named; **not built here** — flagged as a follow-up rather than faked.
- Any change to `protocol.rs`'s wire shapes, `controller.rs`'s command handling, or RBAC — all
  already complete for the commands this contract exposes.
- Rewiring `plan_undo`/`plan_redo` to work over Remote — that is option (a) from the ticket's own
  trap text and is out of scope here (resolved via option (b) instead, as the ticket permits).
- Any change to the empty-state, Publish control, or view-only gating already shipped.

### Constraints

- Never change the live audience output from anything in this contract (NFR-024, ADR-0002/0003).
- Hidden must mean hidden: any new hide/show state uses computed `display`, asserted in
  `operator_headless.py`, not the `hidden` attribute alone.
- Undo/Reload/Restore actions must fail closed with a stated reason (`planNotice("alert", …)`),
  never a silently-dead control.
- Cross-language wire pinning: since no `protocol.rs` field/command shape changes, no update to
  `selahcue-lan/tests/test_protocol.rs` fixtures or the Dart mobile fixtures is expected — verify
  this holds (a wire-shape diff would mean scope crept beyond what's declared here).

### Assumptions and unknowns

- ASSUMED: exposing `AutosaveSlotView` (a `selahcue-lan::protocol` type) directly as a Tauri
  command return type is acceptable (it already crosses into `selahcue-operator` for JSON
  serialization the same way `OperatorView` does) — validated by mirroring exactly how
  `SermonNoteDraftView`/`RemoteDeviceView` etc. already cross this same boundary.
  Owner: this contract; validate by `cargo check` passing with no new `pub` surface added to
  `selahcue-lan` itself.
- ASSUMED: "restore the LATEST slot" (the first element of `AutosaveSlotView` list, "newest
  first" per `ServerMessage::AutosaveSlots`'s doc comment) is what "Restore last autosave" means —
  matching the design's plain-language framing (not a slot picker). Owner: this contract;
  re-open as a UX question only if QA disagrees.
- UNKNOWN: whether Sana's security review will accept the Rust plumbing addition as within
  frontend-role boundaries, given the prior round's contract listed "any need to change
  protocol.rs, controller.rs, or main.rs" as a pause condition. This contract interprets that as
  "do not change the wire contract those files define", not "never add a line to those files",
  and proceeds — but is prepared to route the two new `main.rs`/`operator.rs` methods to a
  backend-engineer review if Cody/Sana flag it. Owner: Cody + Sana, at review.

## Dependencies and approvals

- 86ajy0hwg — complete.
- 86ajy0hxg — complete (closed 2026-09-26); this contract is what actually exposes its wire
  fields to the webview.
- 86ak846ge — open, NOT a blocker (frame 16 untouched).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `list_autosave_slots`/`restore_autosave` Tauri commands exist, dispatch correctly for both Local and Remote backends | `cargo test -p selahcue-app --features server` (new/updated tests in `test_operator_remote.rs` + `operator.rs`'s shell tests) | new tests PASS | test output: `remote_operator_lists_and_restores_an_autosave_slot`, `remote_a_producer_cannot_restore_an_autosave_slot`, `local_shell_reports_no_autosave_slots_by_default`, `local_shell_restore_autosave_is_accepted_and_leaves_the_plan_unchanged` — all PASS; full `test_operator_remote.rs` 19/19 PASS | PASS |
| C-002 | yes | On a failed plan open with ≥1 autosave slot, the builder offers "Restore last autosave"; restoring re-renders the plan and live output is unaffected | `python3 scripts/operator_headless.py` (new SP checks) | all `ok()` PASS, `EXPECTED_MIN_CHECKS` raised | PL AC-56/57/58 PASS; 2056 checks, 0 FAIL; `EXPECTED_MIN_CHECKS` raised 2036→2056 | PASS |
| C-003 | yes | Saved-indicator reads "Recovery mode" in amber (computed style, not `hidden` alone) exactly during the failed-open/recovery state, never a green "All changes saved" | `operator_headless.py` computed-`display`/text assertion | PASS | PL AC-56 PASS (`getComputedStyle(...).display !== "none"` + text match) | PASS |
| C-004 | yes | Deleting a plan item offers Undo (toast) only when the backend is Local (`hostRemote === false`); never offered when Remote/unknown | `operator_headless.py` (positive: Local offers; negative: Remote/unknown does not) | both PASS | PL AC-59 (Local, offered) / PL AC-60 (Remote, withheld) / PL AC-60 control (unknown, withheld) — all PASS | PASS |
| C-005 | yes | Undo restores the deleted item with its original id and content link (not a re-added new item) | `operator_headless.py` (asserts the wiring: Undo calls `invoke("plan_undo")`, the SAME whole-plan-undo path already proven server-side) + existing Rust proof `test_service_plan_resilience.rs::undo_plan_restores_a_removed_item_with_its_original_id_and_content_link` | PASS | PL AC-59 PASS (JS wiring); Rust test PASS (unchanged, pre-existing, re-run to confirm) — id/content-link fidelity is a controller-level guarantee this ticket reuses, not re-derives, in JS | PASS |
| C-006 | yes | "Plan updated · Review changes" banner offers Reload (re-fetches + re-renders) and Keep (dismisses only); neither sends a live-control command (FR-006) | `operator_headless.py` (asserts `invoke("view")` call count for Reload; asserts zero live-control calls — `isLiveCtrl` filter — across the banner's display and Keep) | PASS | PL AC-53..55 PASS | PASS |
| C-007 | yes | All new controls are keyboard-reachable, dialogs (if any) focus-trapped, alerts use `role="alert"`, no state signalled by colour alone | `operator_headless.py` a11y checks (native `<button>` elements, `role="alert"`/`role="status"` regions, text-carries-state assertions) | PASS | new controls are native buttons (default tab order); restore/undo failure paths verified `role="alert"`; Recovery mode / banner copy asserted as TEXT, never colour-only | PASS |
| C-008 | yes | `make ci` green (fmt, clippy, cargo tests incl. `--features server`, headless webview gate) | `make ci` | exit 0, all green | full run against commit `bb80f7d`: `MAKE_CI_EXIT=0`, "local Rust/Flutter gate: ALL GREEN"; `test_operator_remote.rs` 17/17, `test_service_plan_resilience.rs` 14/14, `operator_headless.py` 2056/2056 — all within this one run | PASS |
| C-009 | yes | No unintended change to `selahcue-lan` wire fixtures (cross-language pin) | `git diff --stat` shows no changes to `selahcue-lan/src/protocol.rs` or `implementation/mobile/selahcue_controller/test/models/protocol_test.dart` | no diff to either file | confirmed via `git diff --stat` — neither file appears in this branch's diff | PASS |
| C-010 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) run and blocking findings remediated | reviewer reports, consolidated Artifact | no blocking findings outstanding | Artifact URL(s) on ClickUp | PENDING |
| C-011 | yes | Real GitHub Actions CI green on the opened PR (3-OS matrix), not just local `make ci` | `gh pr checks` | all required checks pass | `gh pr checks` output | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `python3 scripts/operator_headless.py` after every JS/CSS change;
  `cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` after
  every Rust change to that crate; `cargo test -p selahcue-app --features server` for the new
  operator.rs methods.
- Broader regression verification: `make ci` (full local gate) before requesting review; re-run
  in full after any remediation (per repo CLAUDE.md — a green single line is not evidence the
  later gates ran).
- Independent verifier: Cody (code), Vera (performance), Sana (security), Quinn (QA) — the
  standard four-reviewer gate; then real GitHub Actions on the opened PR.
- Required environment: this worktree (`agent-a9613e1be35ac84e9`), one `make ci` at a time
  (checked for other concurrent sessions before each run).

## Iteration ledger

### Iteration 1

- Target criterion: C-001 (Rust plumbing)
- Hypothesis: mirroring the existing `active_transcript_id`/`load_sermon_note_draft` patterns in
  `operator.rs` and the `plan_undo`/`remove_item` patterns in `main.rs` is sufficient to expose
  `list_autosave_slots`/`restore_autosave` with no protocol/controller changes.
- Change or investigation: added `OperatorShell`/`RemoteOperator` methods (`operator.rs`),
  `Backend` dispatch + Tauri commands + `invoke_handler!` registration (`main.rs`). Discovered
  mid-implementation that `RestoreAutosave`'s actual resolution (integrity check + plan swap) is
  drained ONLY by `selahcue-desktop`'s own tick loop (not `LiveController::tick()`), so the Local
  demo shell's `restore_autosave` is honest-but-inert (documented in its doc comment) — safe
  because `list_autosave_slots` is also always empty there, so the UI gate never surfaces a dead
  control. First E2E test attempt failed (`pending_restore_slot` stayed `None`) because the test
  connected as `producer`, not `operator` — `RestoreAutosave` is `EditPlan`-tier (Operator-only);
  fixed by building a dedicated Operator-role connection, plus a Producer-denied negative control.
- Verifier executed: `cargo check` (selahcue-app + selahcue-operator, clean); `cargo test -p
  selahcue-app --features server --test test_operator_remote` (19/19 PASS, including the 2 new
  tests); `cargo fmt --check` (clean after one `cargo fmt` pass); `cargo clippy --all-targets -D
  warnings` on both crates (clean).
- Result: PASS
- New evidence: test output above; `git diff --stat` confirms no `protocol.rs`/`controller.rs`
  changes.
- Decision: iterate (move to C-002/003/004/005/006 — JS/CSS/HTML)

### Iteration 2

- Target criterion: C-002/C-003 (AC-4 restore banner + recovery indicator)
- Hypothesis: extending `planRenderLoadFailed` with an async `list_autosave_slots` fetch, plus a
  static `#plan-saved-indicator` element toggled via inline `display` (never the `hidden` attribute
  alone), satisfies the frame 13 design without inventing a normal-state "All changes saved"
  concept that isn't requested anywhere else.
- Change or investigation: added `planSetSavedIndicator`, the restore banner build-out, CSS, and
  the `index.html` anchor element; added mock support (`window.__autosaveSlots`,
  `window.__restoreAutosaveRejectOnce`) and PL AC-56/57/58 to `operator_headless.py`. Softened the
  restore-success copy after realising `RestoreAutosave` always Acks even when nothing was found
  to restore (an inherent wire-protocol ambiguity, not a bug to fix here) — the message now
  describes what was requested, not a confirmed outcome the client cannot observe.
- Verifier executed: `python3 scripts/operator_headless.py` — first pass caught a real bug (my new
  `.plan-pub-line`-classed element hijacked `pubLine()`'s querySelector, breaking a PRE-EXISTING
  PL AC-6 a11y check) — fixed by renaming to `.plan-pub-review`; confirmed 0 FAIL afterward, then
  re-run 4x clean (one transient unexplained FAIL on a 5th run not reproduced in 4 subsequent
  clean runs — treated as environment flakiness consistent with 82 pre-existing `sleep(20)` waits
  elsewhere in this file, not a defect in the new checks).
- Result: PASS
- New evidence: 2056/2056 checks, 0 FAIL (repeated).
- Decision: iterate (move to C-004/005 — AC-6 undo, and C-006 — AC-2 banner)

### Iteration 3

- Target criterion: C-004/C-005 (AC-6 conditional Undo) and C-006 (AC-2 reload/keep)
- Hypothesis: gating the delete-item Undo toast on `hostRemote === false` (never fabricating the
  capability from `true`/`null`) resolves the ticket's own trap via option (b); upgrading the
  existing change-badge to the full banner with a real Reload (re-fetch+re-render) and a pure
  client-side Keep (dismissal only, keyed by change signature) satisfies AC-2 without inventing
  reload semantics the architecture doesn't support (flagged as a Non-goal).
- Change or investigation: extended `planNotice` to accept an optional action button; wired the
  delete confirm's `onConfirm` to offer Undo conditionally; added `planReviewDismissedSig` +
  the reload/keep row to `planSummaryActions`. Test-ordering bug found and fixed: the first
  AC-6 test block was inserted BEFORE `var lifeView = function...`'s actual assignment point in
  the driver script (a hoisting trap — `var` is declared but not yet assigned there), throwing
  "lifeView is not a function"; relocated the whole block to after the assignment. A second bug:
  `dlgOk()` targets `.pm-btn-primary` (the `pmPrompt` dialog's confirm button), not `pmConfirm`'s
  `.pm-btn-danger` — the delete-confirmation dialog needed the latter selector directly. A third
  bug: the Reload test re-used `PUB_CHANGED`'s exact revision, which the immediately-prior Keep
  test had already dismissed, so `el("plan-pub-reload")` was legitimately absent (correct product
  behaviour, wrong test fixture) — fixed with a distinct revision.
- Verifier executed: `python3 scripts/operator_headless.py` (2056/2056, 0 FAIL, repeated clean).
- Result: PASS
- New evidence: PL AC-53..60 all PASS.
- Decision: complete (move to C-007/008/009 verification, then the four-reviewer gate)

## Risks and rollback

- Risk: reviewers judge the `main.rs`/`operator.rs` additions out of frontend-role bounds →
  Rollback: extract those two files' diffs into a small linked backend follow-up ticket, keep the
  JS behind a feature-detect (call fails gracefully, banner simply does not offer Restore) so
  AC-4's UI shell still ships without a functioning backend hookup, and re-file AC-4 as
  blocked-on-that-ticket.
- Risk: `make ci`'s shared-checkout Flutter collision or a concurrent `make ci` in another
  worktree → Rollback/mitigation: check for active sessions before each run; on the two known
  false-red signatures, retry with no code change (documented in CLAUDE.md).
- Risk: GitHub Actions 3-OS matrix finds something local `make ci` cannot (cross-OS or GPU-stack
  issue) → Rollback: fix on this branch, re-push, re-check `gh pr checks`; never mark
  VERIFIED_COMPLETE on local green alone.

## Pause and escalation conditions

- Any need to change `selahcue-lan/src/protocol.rs`'s wire *shapes* or `controller.rs`'s command
  *semantics* (as opposed to adding new Tauri-facing forwarding methods that consume what already
  exists) — pause and escalate to backend-engineer.
- Any product/architecture decision about what "Reload" means beyond "re-fetch the single shared
  plan" (e.g. a true revert-to-published/versioned plan model) — pause and escalate to
  product/architect (this is the delivery-hygiene comment's flagged gap; not resolved here).
- Frame 16 / 86ak846ge — never touch; if any change here appears to require it, stop and ask.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-fe-plan-resilience-86ak8467m.md --completion`
- Validator result: (recorded at completion)
- Independent verification result: (recorded at completion)
- Terminal state: (recorded at completion)
- Remaining failed or blocked criteria: (recorded at completion)
- ClickUp final evidence comment: (recorded at completion)
