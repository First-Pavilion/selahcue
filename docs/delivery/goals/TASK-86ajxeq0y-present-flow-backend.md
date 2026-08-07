# Goal Contract — TASK-86ajxeq0y-present-flow-backend

## Identity

- Goal ID: TASK-86ajxeq0y-present-flow-backend
- Parent goal ID: STAGE8-core-presentation
- Title: Authored deck slides live on all outputs + atomic advance-and-present + host-truth live signal (Track A)
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxeq0y
- Created: 2026-08-07
- Updated: 2026-08-07
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Deliver the backend of the browse/present/edit flow: presenting an authored deck slide sets the single live content for ALL audience outputs (primary + secondary/NDI), an atomic `deck_go_live_delta(±1)` advances-and-presents, and the host exposes truthful live/output signals — implementing Tasks 1–6 of the implementation plan and the frozen §0 integration contract exactly.

## Baseline

**Verified (2026-08-07, against the codebase):**
- `Presenter::present_authored` (`selahcue-present/src/present.rs:161`) writes `self.live` then sets `live_slide = None; live_theme = None;` — so `compose_screen_live` (`present.rs:278`) returns an idle black frame while an authored slide is live (secondary/NDI go black).
- No `deck_go_live_delta` symbol exists. `DeckWorkspace::go_live` (`deck_workspace.rs:643`) sets `self.live = effective_selected()`. `SlideDeck` exposes `index_of`/`get_index`/`len` (`deck.rs:226–231`). `deck_go_live` command routes `present_payload()` → `backend.present_authored_slide` (`main.rs:1153`).
- `OperatorView` (`selahcue-app/src/operator.rs:45`) has `blackout` but no `live_authored_id`. `Backend` enum (`main.rs:46`) has no `is_remote`; no `output_connected` command.
- GPU parity harness `selahcue-gpu/tests/test_parity.rs` asserts SSIM ≥ 0.99 over a `scenes()` vec of `Frame`s.

## Inputs and evidence sources

- Design spec: `docs/superpowers/specs/2026-08-04-presentation-browse-present-flow-design.md`
- Implementation plan (Tasks 1–6): `docs/superpowers/plans/2026-08-07-presentation-browse-present-flow.md`
- Frozen §0 contract: `docs/superpowers/plans/2026-08-07-presentation-flow-delivery-tracks.md`
- Source: `selahcue-present/src/{present.rs,compose.rs,deck.rs}`, `selahcue-gpu/tests/test_parity.rs`, `selahcue-operator/src/{main.rs,deck_workspace.rs}`, `selahcue-app/src/{operator.rs,controller.rs}`

## Scope

### In scope

- Engine: retain the authored slide as live content; mirror it in `compose_screen_live`; recompose it on theme/layer switches; authored-representative SSIM parity scene (Tasks 1–3).
- Host: `DeckWorkspace::go_live_delta`; `deck_go_live_delta` command; `OperatorView.live_authored_id`; `output_connected` command + `Backend::is_remote` (Tasks 4–6).

### Non-goals

- All `dist/` webview work (Track B, 86ajxeq17).
- On-slide video (deferred, ADR-0020).
- Per-output layer masking of authored slides (authored elements are content, not theme-layer categories).

### Constraints

- `clippy -D warnings`; no `unwrap`/`expect` in non-test code (`clippy::unwrap_used = warn`).
- Bounded memory; never-blank (NFR-024); SSIM ≥ 0.99 GPU↔CPU parity.
- Live invariant: presenting takes over the single live surface, last-writer-wins with plan/scripture content; mutual exclusion of `live_slide` and `live_authored`.
- Operator crate is excluded from the workspace: verify with `cargo check --manifest-path` + headless.
- Deliver the §0 contract names/args/types exactly. Commit messages end with the required Co-Authored-By trailer.

### Assumptions and unknowns

- ASSUMED: `AuthoredSlide` derives `Clone` (it is stored in the deck + undo stack) — validate at Task 1 compile.
- ASSUMED: the `Backend` remote variant is named `Backend::Remote(_)` — validate by reading the enum at Task 6.

## Dependencies and approvals

- Design approved by owner 2026-08-04 (spec status). No further product/architecture gate for Track A.
- Track B (86ajxeq17) consumes this track's §0 contract; frozen — any change is a two-track event.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Authored slide retained as live content; cleared by a later plan go-live | `cargo test -p selahcue-present --test test_present authored_live_is_tracked` | PASS | test_present 23→ ok; commit C-001 | PASS |
| C-002 | yes | Secondary screens mirror the presented authored slide; zero-element still non-blank | `cargo test -p selahcue-present --test test_present secondary_screens_mirror an_authored_slide_with_no_elements` | PASS | 2 passed; commit C-002 | PASS |
| C-003 | yes | Authored live slide survives a theme/per-screen-theme switch | `cargo test -p selahcue-present --test test_present a_theme_switch_keeps_a_live_authored` | PASS | 1 passed (stronger bg-less test); commit C-003 | PASS |
| C-004 | yes | GPU↔CPU SSIM ≥ 0.99 incl. authored-representative scene | `cargo test -p selahcue-gpu` | PASS (or explicit GPU-absent SKIP) | 2 passed (GPU present, ran); commit C-004 | PASS |
| C-005 | yes | `go_live_delta` steps and clamps at both ends; empty-deck no-op | `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml go_live_delta` | PASS | 2 passed; commit C-005 | PASS |
| C-006 | yes | `deck_go_live_delta` command implemented + registered; operator crate compiles | `cargo check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` | clean (no errors/warnings) | check clean; commit C-006 | PASS |
| C-007 | yes | `OperatorView.live_authored_id` reflects the presented authored slide id | `cargo test -p selahcue-app --test test_controller operator_view_reports_the_live_authored` | PASS | 1 passed | PASS |
| C-008 | yes | `output_connected` command + `Backend::is_remote` present and registered | review: grep the command in `generate_handler!` + `is_remote` on `Backend`; `cargo check` clean | present + check clean | PASS |
| C-009 | yes | §0 contract delivered exactly (command names, arg `delta`, field `live_authored_id`, `output_connected` bool) — incl. the WIRE `OperatorStateView.live_authored_id` needed for the real Remote path (a plan gap closed) | review against delivery-tracks §0 table | exact match | self-review PASS; independent confirm at C-011 | PASS |
| C-010 | yes | Rust CI gates pass (fmt, clippy -D warnings, present/gpu/app/lan suites; operator check) | `make ci` (Rust portions) | PASS | fmt --check clean (both manifests); clippy -D warnings exit 0 (workspace + operator); present/gpu/app/lan suites + operator go_live_delta green | PASS |
| C-011 | yes | Independent code review of Track A | /code-reviewer (or requesting-code-review) | approved | HANDOFF — awaiting review (GATE_REVIEW) | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-task `cargo test`/`cargo check` commands in C-001…C-008 run after each task's implementation (TDD: failing test first).
- Broader regression verification: `cargo test -p selahcue-present -p selahcue-gpu -p selahcue-app` full suites + `make ci` Rust gates (C-010) after all tasks land.
- Independent verifier: /code-reviewer on the Track A diff (C-011); QA at the story level.
- Required environment: local dev (macOS); GPU parity skips gracefully without a GPU adapter, REQUIRED in CI.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: adding a `live_authored: Option<AuthoredSlide>` field set by `present_authored` and cleared by `go_live` makes the authored-live signal observable and mutually exclusive with `live_slide`.
- Change or investigation: implement plan Task 1.
- Verifier executed: `cargo test -p selahcue-present --test test_present authored_live_is_tracked`
- Result:
- New evidence:
- Decision: iterate | handoff | blocked | gate-review | complete

## Risks and rollback

- Risks: `AuthoredSlide` not `Clone` (mitigate: derive/clone at Task 1); `Backend` variant name differs (validate at Task 6); recompose branches double-applying (mitigated by `live_slide`/`live_authored` mutual exclusion).
- Rollback or recovery: each task is a separate commit; revert the offending commit. No data migration, no persisted-schema change — pure in-memory engine/host state.

## Pause and escalation conditions

- Any change to the §0 contract → pause, notify Track B, update both contracts (owner-visible).
- Secondary-screen mirroring requiring a compositor architecture change beyond `compose_screen_live` → escalate to /software-architect.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajxeq0y-present-flow-backend.md`
- Validator result: PASS (structural)
- Independent verification result: PENDING — handed to /code-reviewer (C-011)
- Terminal state: **GATE_REVIEW** (C-001…C-010 PASS; C-011 independent review is a handoff the implementation role cannot self-approve)
- Remaining failed or blocked criteria: C-011 (independent review) PENDING
- ClickUp final evidence comment: posted on 86ajxeq0y; task moved to `code review`

### Notes / deviations (honest record)

- **Wire-scope addition (beyond the plan):** `live_authored_id` was added to the wire `OperatorStateView` (not just the app `OperatorView`), because the real multi-process operator reads its view via `From<OperatorStateView>` — without the wire field the grid's LIVE ring would never light over the Remote path. Added as `Option` with `skip_serializing_if=None`, so the byte-pinned cross-language fixtures stay identical (verified: `selahcue-lan` suite green).
- **Stronger C-003 test:** the plan's draft used a solid-bg slide (theme-independent → would not fail-first). Replaced with a background-less slide whose main-surface bg depends on the theme, genuinely exercising the recompose branch.
- **Repo/history context:** Track-A code landed as commits `bd90f9a`…`821be31`; the owner then committed `3db5398` ("Remote Control surface") ON TOP (accepting them as base), so a requested squash was **aborted** as unsafe (would rewrite the parent of the owner's concurrent commit). History left as-is; nothing pushed. The Presentation & Media feature was already substantial uncommitted WIP at session start — Track A layered small deltas onto it.
- **Scope boundary:** C-010 covers the **Rust** gates; the full `make ci` (frontend headless + Flutter) is the story-level gate and now includes the owner's concurrent `dist/` changes — owned by Track B / the owner.
