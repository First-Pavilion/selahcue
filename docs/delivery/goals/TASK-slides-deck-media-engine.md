# Goal Contract — TASK-slides-deck-media-engine

## Identity

- Goal ID: TASK-slides-deck-media-engine
- Parent goal ID: EPIC-86ajp07ce (Presentation & Slides)
- Title: Slides & Media engine (backend) — authored deck model + compose + playback + media library
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajv8qd9
- Created: 2026-08-03
- Updated: 2026-08-03
- Maximum iterations: 12
- Independent verification required: yes (adversarial multi-lens review + reproduce)

## Objective

Build the backend engine beneath the Design-2.0 "Presentation & Media" surface (Figma 329:124): the
domain model, compose path, preview→live playback, and persistence for **authored slide decks** and a
**media library** — reusing the existing `Element`/`Background`/`Presenter`/never-blank `Engine` stack,
so the frontend editor (S8-4, 86ajpzhan) has a real engine to drive.

## Baseline

**Verified (architecture map + source reads):**
- No `SlideDeck`/`Deck`/authored-slide content model exists. `selahcue-present::slide::Slide`
  (`slide.rs:9`) is a transient title+body render pair; `PlanItem.stanzas` (`plan.rs:73`) is the only
  multi-slide content. `ItemKind::SlideGroup` (`plan.rs:11`) is a bare tag with no body. The
  ARCHITECTURE §8 `document`(slide/deck) entity is spec'd but unimplemented (no data-layer table).
- Reuse is available and public: `theme::Element` (Shape/Image/Text; z-order; `visible`; `z()`,
  `within_bounds()`; `MAX_ELEMENTS=64`; `MAX_TEXT_ELEMENT_LEN=2000`; additive skip-default serde) at
  `theme.rs:139`; `theme::Background` (Solid/Gradient/Image; `base_color()`) at `theme.rs:348`;
  `compose_slide`/`push_background`/`element_layers` in `compose.rs`; `Presenter` preview→live/go_live
  in `present.rs`; never-blank `Engine` (NFR-024) in `selahcue-engine`.
- `selahcue-data` migrations (`migrations.rs`) are a forward-only, append-only ordered array (index n:
  `user_version n→n+1`, one atomic txn each), tables through `screen_output_config`. `saved_theme_repo`
  persists a present type as a JSON-blob row — the pattern to mirror for `deck_repo`/`media_repo`.
- Tests are public-API integration tests, one file per module. Injected-clock `Timer` pattern
  (`timer.rs`) is the model for deterministic auto-advance. Workspace lints: `clippy::unwrap_used=warn`,
  `-D warnings` in CI.
- `make ci` is currently intermittently blocked by the owner's **concurrent** `LayerMask`/per-screen WIP
  spanning `present.rs`/`compose.rs`/`app.js` — this story ADDS modules and new compose fns rather than
  refactoring existing paths to avoid collision; in-scope crates verified in isolation as needed.

## Inputs and evidence sources

- Figma 329:124 ("Presentation & Media — Design 2.0"): authored SLIDES list, slide-canvas
  (Text/Shape/Image/Video/Background + speaker notes + per-slide Transition + Auto-advance), MEDIA
  LIBRARY (import; images/video/audio; missing + unused states; storage accounting).
- `docs/architecture/ARCHITECTURE.md` §8 (`document` entity), §Presentation service.
- `docs/product/prds/SelahCue-PRD.md` FR-009, FR-003, FR-011, FR-070.
- Source: `selahcue-core/src/plan.rs`, `selahcue-present/src/{slide.rs,theme.rs,compose.rs,present.rs}`,
  `selahcue-engine/src/{scene.rs,engine.rs,raster.rs}`, `selahcue-data/src/{migrations.rs,saved_theme_repo.rs}`.

## Scope

### In scope

- **Deck model** (`selahcue-present::deck`): `SlideDeck { name, slides: Vec<AuthoredSlide>, … }` +
  `AuthoredSlide { id: SlideId, elements: Vec<Element>, background: Option<Background>, notes: String,
  transition: Transition, auto_advance_secs: Option<u32> }`. Ordered, stable `SlideId`, CRUD + reorder +
  duplicate, bounded (`MAX_DECK_SLIDES`), additive byte-stable serde.
- **Compose** (`selahcue-present::compose`): `compose_authored_slide(&AuthoredSlide, &Theme, w, h) -> Frame`
  (slide-owned background+elements, zero loss, never-blank); deterministic crossfade for `Fade`.
- **Playback** (`selahcue-present::deck` or `deck_session`): `DeckSession` — preview→live isolation,
  next/prev, current/N-of-M, auto-advance on an injected clock.
- **Media library** (`selahcue-core::media` + `selahcue-present` usage correlation): `MediaLibrary` /
  `MediaAsset` / `MediaKind` (image/video/audio) registry — import, metadata, missing detection (injected
  existence probe), used/unused correlation vs decks, storage accounting, bounded (`MAX_MEDIA_ASSETS`).
- **Persistence** (`selahcue-data`): forward-only migrations for `deck` + `media_asset`; `deck_repo`/
  `media_repo` (JSON-blob rows); survive reopen; `--features encryption` compiles.
- **ADR-0020** + DECISION-LOG entry: authored-deck/media-library model + video-render deferral.

### Non-goals

- Live video/audio playback on the wgpu output (ADR-0020 flags for its own story).
- The in-webview editor UI, undo/redo, command palette (S8-4, frontend).
- New LAN wire-protocol commands to drive decks (belongs with the editor; avoids cross-language fixture
  churn this pass).
- Slide auto-pagination (FR-029, `Fit::Paginate`).

### Constraints

- Pure/deterministic `selahcue-core` (no I/O; never panics on untrusted input; no `unwrap` in prod paths).
- Bounded memory: every new registry/list/string is capped with a bounded-memory test.
- Byte-stable additive serde (skip-defaults) with round-trip + old-JSON-compat tests.
- NFR-024 never-blank preserved by `compose_authored_slide`.
- Injected clock for auto-advance (deterministic, like `Timer`).
- TDD (red→green); public-API integration tests, one file per module; `make ci` green.
- Add new modules/fns; do not refactor the owner's concurrently-edited compose/present paths.

### Assumptions and unknowns

- ASSUMED: an authored slide renders purely from its own elements+background (no theme title/body
  regions) — the theme supplies the fallback background + default styling only. Validate against the
  design during compose. Owner: this role.
- ASSUMED: media assets are referenced by `Element::Image { source: MediaRef }`; "used" = a deck slide
  references the asset's path. Owner: this role.
- UNKNOWN: exact `deck`/`media_asset` column shape — resolve by mirroring `saved_theme_repo`.

## Dependencies and approvals

- Concurrent owner WIP (`LayerMask`/per-screen, 86ajq321k) touches `present.rs`/`compose.rs` — additive,
  non-blocking; coordinate by adding new fns/modules. Status: active, not blocking.
- Video-render deferral is a scoped decision approved by the user (this session). Status: approved.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `SlideDeck`/`AuthoredSlide` model (reusing `Element`/`Background`): ordered, stable `SlideId`, CRUD+reorder+duplicate, bounded `MAX_DECK_SLIDES` | `cargo test -p selahcue-present --test test_deck` | green incl. cap test | test_deck 9/9 green | PASS |
| C-002 | yes | Additive byte-stable serde: default transition/notes/shown-elements omit keys; old JSON (missing fields) deserialises; round-trips | test_deck serde cases | green | `{"id":1}` byte-stable + old-JSON-compat + full round-trip tests pass | PASS |
| C-003 | yes | `compose_authored_slide` renders slide-owned bg+elements, hidden gated, zero loss, never-blank (empty slide → non-blank bg frame), deterministic | `cargo test -p selahcue-present --test test_deck_compose` | green | test_deck_compose 8/8 (never-blank + hidden-gate + z-order + determinism) | PASS |
| C-004 | yes | Deterministic crossfade compose: progress 0 == from, max == to, monotonic blend, deterministic | test_deck_compose crossfade cases | green | endpoint-exact + mid-blend + determinism + size-mismatch tests pass | PASS |
| C-005 | yes | `DeckSession` playback: preview→live isolation (stage never mutates live), next/prev, N-of-M, auto-advance on injected clock | `cargo test -p selahcue-present --test test_deck_session` | green | test_deck_session 7/7 (isolation + nav + injected-clock advance + restart-dwell + inert-empty) | PASS |
| C-006 | yes | Media domain `MediaLibrary`/`MediaAsset`/`MediaKind` in core: register/import bounded `MAX_MEDIA_ASSETS`, missing detection (injected probe), byte accounting, never panics | `cargo test -p selahcue-core --test test_media` | green | test_media 10/10 (idempotent import + injected missing probe + saturating bytes + cap) | PASS |
| C-007 | yes | Used/unused correlation between a `MediaLibrary` and decks (Element::Image sources) | media-usage test | green | media_usage test: referenced (image element + image bg) = used, orphan = unused | PASS |
| C-008 | yes | Forward-only migrations add `deck`+`media_asset`; `deck_repo`/`media_repo` round-trip survives reopen; `user_version` bumped by added count; `--features encryption` compiles | `cargo test -p selahcue-data --test test_deck_repo --test test_media_repo` + `cargo build -p selahcue-data --features encryption` | green + builds | test_deck_repo 3/3 + test_media_repo 5/5 + test_db 10/10 (pin v17, reopen survival, unknown-kind dropped); encryption compiles | PASS |
| C-009 | yes | Bounded memory: deck slides, media assets, notes length each enforce a cap with a bounded-memory test | the cap tests above | green (bounds asserted) | deck/media/notes cap tests assert the bound; import/add past cap rejected | PASS |
| C-010 | yes | ADR-0020 records the deck/media model + video deferral; DECISION-LOG updated | file exists + grep | present | ADR-0020-authored-slide-decks-and-media-library.md + DECISION-LOG DEC-003 | PASS |
| C-011 | yes | Full CI gate green (fmt --check, clippy -D warnings, all suites) | `make ci` | ALL GREEN (or in-scope crates green in isolation w/ documented concurrent-WIP block) | `make ci` == **ALL GREEN** (exit 0), re-confirmed after the review fixes | PASS |
| C-012 | yes | Independent adversarial multi-lens review; every confirmed Blocker/High fixed + re-verified | review workflow + re-run suites | none unresolved | 4-lens workflow (wff64e30t): 7 confirmed, all `low` (no Blocker/High/Medium survived); **all 7 fixed + re-verified** (test_media 11 / test_deck 11 / test_deck_session 10) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the new cargo suites (`test_deck`, `test_deck_compose`, `test_deck_session`,
  `test_media`, `test_deck_repo`, `test_media_repo`) — TDD red→green; determinism + never-blank +
  bounded-memory + serde-byte-stability assertions.
- Broader regression verification: `make ci` (fmt/clippy/all suites/operator/headless/flutter). Existing
  `test_compose`/`test_present` must stay green (compose additions are new fns, not refactors).
- Independent verifier: a 3–4-lens adversarial review workflow (correctness/integration · concurrency/
  determinism · persistence/migration · test-quality); refute each finding; fix confirmed Blocker/High.
- Required environment: local Rust workspace (`implementation/desktop`); SQLite (+ SQLCipher for the
  encryption compile check).

## Iteration ledger

### Iteration 1 — build the engine (TDD, bottom-up)
- **core::media** (pure, zero-dep): `MediaLibrary`/`MediaAsset`/`MediaKind` — idempotent-by-path import,
  bounded (`MAX_MEDIA_ASSETS`/`MAX_MEDIA_PATH_LEN`), injected-probe missing detection, saturating byte
  accounting, `MediaKind` string tags. Kept serde OUT of core (core has no serde dep) → structured
  persistence instead. `test_media` 10/10.
- **present::deck**: `SlideDeck`/`AuthoredSlide` (reusing `theme::Element`/`Background`), stable
  `SlideId`, CRUD/reorder/duplicate, bounded, additive byte-stable serde; `crossfade` (endpoint-exact
  integer lerp over `FrameBuffer`); `media_usage`; `DeckSession` (Preview→Live isolation + injected-clock
  auto-advance). `compose_authored_slide` added to `compose.rs` (reuses `push_background`/`element_layers`;
  never-blank). `test_deck` 9/9, `test_deck_compose` 8/8, `test_deck_session` 7/7.
- **selahcue-data**: forward-only migrations v16 (`deck`, JSON blob) + v17 (`media_asset`, structured);
  `deck_repo` (mirrors `saved_theme_repo`) + `media_repo` (column mapping, unknown-kind dropped); schema
  pin bumped 15→17; the 5 migration-reset tests in `test_db` updated to drop the two new tables.
  `test_deck_repo` 3/3, `test_media_repo` 5/5, `test_db` 10/10; `--features encryption` compiles.
- **Docs/exports**: ADR-0020 + DECISION-LOG DEC-003 (video-render deferral); `deck`/`media` exported.
- **Verify**: `cargo fmt` clean; `clippy -D warnings` clean on core/present/data; full suites for all
  three crates green (52 new tests + every existing suite incl. test_compose 50 / test_present 21 /
  test_tokens 14 — no regressions). `make ci` + adversarial review running.
- **Decision:** iterate — await `make ci` (C-011) + adversarial review (C-012), fix any confirmed finding.

### Iteration 2 — `make ci` green + adversarial review + fixes
- **C-011:** `make ci` == **ALL GREEN** (exit 0) — fmt/clippy `-D warnings`/all Rust suites/operator
  check/headless/flutter. The earlier concurrent-WIP block has cleared.
- **C-012:** 4-lens adversarial review workflow (wff64e30t; 15 agents, each finding refuted before it
  survived) → **7 confirmed, all `low`** (the one `medium` was downgraded on verification). **No
  Blocker/High/Medium survived.** Fixed **all 7** anyway (cheap hardening):
  1. *[id-collision]* `SlideDeck` deserialised `next_id` verbatim → a stale/tampered blob could mint a
     colliding `SlideId`. Added a **self-healing `mint_id`** (advances past every existing id, saturating)
     used by `insert_slide`/`duplicate`; test: rehydrate a stale-`next_id` blob → no collision.
  2. *[correctness]* `MediaLibrary::import` stored paths verbatim while `MediaRef` trims/rejects-NUL/byte-caps
     → whitespace/over-long paths misclassified as unused. Now import **trims + rejects NUL + byte-caps**,
     and `MAX_MEDIA_PATH_LEN` aligned to `MediaRef::CAP` (1024 bytes); test added.
  3. *[panic-safety]* `MediaLibrary::from_assets` used `max + 1` (debug-panic at u64::MAX, violating core's
     never-panic rule) → `saturating_add(1)`.
  4–7. *[test-coverage]* added tests for: non-default Fade/auto-advance serde; backwards-clock `tick` (no
     panic, holds); a two-slide auto-advance chain (0→1→2); `set_theme` restyles Live without moving cursors.
- **Re-verify:** test_media 11/11, test_deck 11/11, test_deck_session 10/10; clippy `-D warnings` clean;
  re-running `make ci` for the final sign-off.
- **Decision:** complete on the final `make ci` green.

## Risks and rollback

- Risk: colliding with the owner's concurrent compose/present edits. Mitigation: additive new
  modules/fns only. Rollback: new files are self-contained; revert the module + migration.
- Risk: a forward-only migration cannot be un-applied. Mitigation: additive `CREATE TABLE` only, atomic
  per-migration txn, tested round-trip + reopen. Rollback: a later additive migration, never an edit.
- Risk: never-blank regression on an empty authored slide. Mitigation: explicit never-blank test; the
  background always fills.

## Pause and escalation conditions

- Stop at `make ci` green (or in-scope-green with a documented concurrent-WIP block) + independent review
  clean + owner gate.
- Escalate if video-render or new wire commands turn out to be required for a testable engine (scope change
  → Product/owner).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-slides-deck-media-engine.md --require-complete`
- Validator result: PASS (12/12 mandatory PASS)
- Independent verification result: 4-lens adversarial review (wff64e30t) — 7 confirmed, all `low`, all fixed + re-verified; no Blocker/High/Medium.
- Terminal state: **VERIFIED_COMPLETE**
- Remaining failed or blocked criteria: none.
- Reviewed vs unreviewed: **reviewed** = the authored-deck model, compose, playback, media library, and
  persistence (this session's delta); **not built/deferred** = live video/audio render (ADR-0020 own
  story), the S8-4 editor UI, new LAN wire commands, FR-029 pagination. QA-ready for the engine surface;
  final pixel-level visual QA is owner-run once the S8-4 editor drives it (no in-repo render harness).
- ClickUp final evidence comment: posted to 86ajv8qd9 (handoff) + BUILD CONTROL 86ajnx548.
