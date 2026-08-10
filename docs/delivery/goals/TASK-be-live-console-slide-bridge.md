# Goal Contract — TASK-be-live-console-slide-bridge

## Identity

- Goal ID: TASK-be-live-console-slide-bridge
- Parent goal ID: NONE (design: docs/design/LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md §5–§6, Phase 1 / Dep 1)
- Title: Read-only deck-slide bridge + within-item slide staging for the Live Console slide picker
- Role: backend-engineer
- Status: GATE_REVIEW (all mandatory criteria PASS; awaiting independent review + owner gate before frontend)
- Execution engine: goal
- ClickUp task: NONE (to link/create under Presentation & Slides epic 86ajp07ce — see Dependencies)
- Created: 2026-08-09
- Updated: 2026-08-09
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Expose the three Phase-1 backend commands the Live Console slide picker needs — list a plan-linked
deck's slides, render one of its slides read-only, and stage a specific within-item slide to Preview —
without touching the audience-output routing (Dep 2) or slide editing (Dep 3), and without disturbing the
editor's `DeckWorkspace`.

## Baseline

Verified against the current tree:
- A presentation plan item is a `slide_group` linked to a deck by id (ADR-0020). `ItemView`
  (`selahcue-app/src/operator.rs`) already exposes `link` (deck id), `slide_index`, `slide_count`, `kind`,
  so the frontend can derive "staged presentation + deck id + cursor" — **no `OperatorView` change needed**.
- `DeckLibrary` (`selahcue-operator/src/deck_library.rs`) has `get(DeckId) -> Option<SlideDeck>`; a
  `SlideDeck` exposes `slides()` / `get(SlideId)`; `render_authored_slide(slide, &Theme, w, h)`
  (`selahcue-present`) renders a slide with no workspace. `DeckWorkspace::render_slide` previews with
  `Theme::dark()` and clamps to ≤960×540.
- The console currently only knows a deck's slide *count* (`plan_deck_slides`/`render_plan_deck_slide` do
  not exist). `Command::SelectItem` stages slide 0 only (`stage_index -> stage_slide(idx, 0)`); there is no
  "stage slide k" command. `stage_slide` already clamps to `slide_count-1` and never touches Live (FR-012).
- `Command` is the LAN wire enum (`selahcue-lan/src/protocol.rs:42`), authorised at the single
  `required_permission` choke point (`rbac.rs`); `SelectItem` maps to `Navigate`. Command wire shapes are
  cross-language-pinned in the Rust protocol test and `protocol_test.dart`.

## Inputs and evidence sources

- docs/design/LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md (§2, §4, §6 contract)
- selahcue-operator: deck_library.rs, deck_workspace.rs, main.rs (Backend enum, render_deck_slide, select)
- selahcue-app: controller.rs (apply/stage_slide/stage_index), operator.rs (Operator/remote/Backend select)
- selahcue-lan: protocol.rs (Command), rbac.rs (required_permission), tests/test_protocol.rs
- implementation/mobile/.../test/models/protocol_test.dart (cross-language command fixtures)

## Scope

### In scope

- `plan_deck_slides(deck_id)` — operator-local Tauri command: list a saved deck's slides
  (`{slide_id,label,has_notes}`); `available:false` for an unknown deck.
- `render_plan_deck_slide(deck_id, slide_id, max_w, max_h)` — operator-local Tauri command: read-only render
  of one saved-deck slide to a bounded RGBA frame (Theme::dark, ≤960×540); `available:false`/null when
  missing.
- `Command::SelectSlide { item_id, slide_index }` — additive wire command; RBAC `Navigate`; stages the
  within-item slide to Preview only (never Live); clamps out-of-range; denies unknown item.
- Focused Rust tests + a mirrored Dart `select_slide` fixture (cross-language stability).

### Non-goals

- Dep 2 audience-output routing (deck pixels → physical output) — needs ADR ~0022.
- Dep 3 console slide editing / persistence.
- Any frontend (the `Slides` tab / filmstrip) — sequenced after this, per owner decision.
- `OperatorView` field additions (existing `ItemView` fields suffice).

### Constraints

- FR-012: staging never touches Live. FR-115: operator-confirmed staging only.
- Bounded memory (`no-memory-leaks`): render clamps dimensions; no unbounded allocation/caching.
- Must NOT disturb the editor `DeckWorkspace` (reads from `DeckLibrary`, not the open workspace).
- Live tree holds ~5k lines of unrelated Providers/notes WIP — edits are additive and staged as own hunks;
  do not modify or stage others' WIP.
- Existing cross-language fixtures must remain byte-stable; new command adds a new fixture on both sides.

### Assumptions and unknowns

- ASSUMED: rendering library thumbnails with `Theme::dark()` matches the editor preview (both use it).
  Validation owner: frontend review during Phase 1 (visual parity). Theme-accurate audience render is Dep 2.
- ASSUMED: `select_slide` is initially operator-driven; exposing it on the wire is forward-compatible for
  mobile. Validation owner: this contract (wire test) + product for mobile adoption.

## Dependencies and approvals

- ClickUp story under epic 86ajp07ce — owner: delivery/PM — status: TO CREATE/LINK (records goal id + engine).
- Independent review (code-reviewer) + QA before this slice is `Done` — status: PENDING (returns GATE_REVIEW).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `plan_deck_slides` lists a known deck's slides and returns `available:false` for an unknown id | `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml slide_list` | test PASS | operator deck_library tests | PASS |
| C-002 | yes | `render_plan_deck_slide` renders a bounded RGBA frame for a known deck+slide and returns none for a missing deck/slide; dimensions clamped ≤960×540 | `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml render_library_slide` | test PASS | operator deck_library tests | PASS |
| C-003 | yes | `Command::SelectSlide` stages the given within-item slide to Preview (staged_slide == index, clamped), leaves Live unchanged, denies unknown item | `cargo test -p selahcue-app --test test_controller select_slide` | test PASS | test_controller.rs | PASS |
| C-004 | yes | `SelectSlide` serialises to `{"cmd":"select_slide","item_id":N,"slide_index":M}` and maps to `Navigate`; existing fixtures unchanged | `cargo test -p selahcue-lan --test test_protocol` | test PASS | test_protocol.rs | PASS |
| C-005 | yes | Dart client fixture for `select_slide` matches the Rust wire shape | `cd implementation/mobile/selahcue_controller && flutter test test/models/protocol_test.dart` | test PASS | protocol_test.dart | PASS |
| C-006 | yes | Touched crates are fmt-clean and clippy-clean (`-D warnings`) | `cargo fmt --check` + `cargo clippy -p selahcue-lan -p selahcue-app -D warnings` (+ operator check) | no diff / no warnings | CI-mirror output | PASS |
| C-007 | no | No new LAN transport behaviour (server feature) regressions | `cargo test -p selahcue-lan --features server` | test PASS | test output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001..C-005 targeted tests (new + existing).
- Broader regression verification: `cargo test -p selahcue-app -p selahcue-lan`; operator crate tests;
  `make ci` before any push (CI has a fmt gate).
- Independent verifier: code-reviewer + qa-engineer (owner reviews before frontend begins).
- Required environment: desktop Rust toolchain; Flutter for C-005.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-005
- Hypothesis: The three commands can be added additively (library read + present render + new wire variant)
  without OperatorView/protocol-break, reusing `render_authored_slide`, `stage_slide`, and the `Navigate`
  permission.
- Change or investigation: traced deck library, render path, controller staging, wire enum + rbac + fixtures.
- Verifier executed: operator deck_library tests; `test_controller select_slide` (`--features server`);
  `test_protocol`/`test_rbac` (with + without server); `flutter test protocol_test.dart`; `cargo fmt --check`;
  `cargo clippy` (lan/app `--features server` + operator).
- Result: all mandatory criteria C-001..C-006 PASS; C-007 PASS. deck_library 13/0; controller select_slide
  1/0; protocol 25/0 + rbac 17/0 (server); Dart 24/0; fmt exit 0; clippy no warnings.
- New evidence: `ItemView` already carries link/slide_index → no OperatorView change; `Command` is the LAN
  enum so `SelectSlide` was added there with rbac (Navigate) + a mirrored Dart fixture; the remote
  `select_slide` sits inside the existing `#[cfg(feature = "server")]` block.
- Decision: gate-review

## Risks and rollback

- Risks: (a) editing shared-WIP files (controller/protocol/rbac/tests) risks textual overlap with the
  Providers WIP — mitigated by additive edits + own-hunk staging; (b) rendering a library deck could
  accidentally load/mutate the editor workspace — mitigated by reading `DeckLibrary` only; (c) unbounded
  render allocation — mitigated by the ≤960×540 clamp + a bounded-frame test.
- Rollback or recovery: all changes additive; revert the specific hunks. No migration, no data change.

## Pause and escalation conditions

- Audience-routing or edit-persistence decisions arise → STOP, escalate to architect (Dep 2/Dep 3 own it).
- ClickUp unavailable → produce a pending update, do not create a shadow backlog.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-be-live-console-slide-bridge.md`
- Validator result: PASS (structural) — to re-run with `--require-complete`.
- Independent verification result: PENDING — owner review, then code-reviewer/qa-engineer.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: none (all mandatory PASS).
- ClickUp final evidence comment: to post once the Presentation & Slides story is linked (epic 86ajp07ce).
