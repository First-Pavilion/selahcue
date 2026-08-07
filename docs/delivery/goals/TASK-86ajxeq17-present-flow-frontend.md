# Goal Contract — TASK-86ajxeq17-present-flow-frontend

## Identity

- Goal ID: TASK-86ajxeq17-present-flow-frontend
- Parent goal ID: STAGE8-core-presentation
- Title: Operator webview browse→present→edit flow — Presentation surface (Track B)
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxeq17
- Created: 2026-08-07
- Updated: 2026-08-07
- Maximum iterations: 12
- Independent verification required: yes

## Objective

Turn the operator's Presentation surface from editor-first into browse/present-first: land on the library, open a presentation into a slide grid, double-click a slide to go live, advance live with arrows/transport, and reach the existing editor via Edit ▸ / ‹ Done — consuming Track A's `deck_go_live_delta`/`live_authored_id`/`output_connected`, with the full §8 state matrix and a11y.

## Baseline

**Verified (2026-08-07, reconciled against the current `dist/`):**
- Track B is unstarted: no `#pm-grid`/`.pm-tile` DOM, no `.pm-grid`/`.pm-tile`/`.pm-transport` CSS, no `pmMode`/`pmSetMode`/`pmRenderGrid`/`pmGridSyncLive` JS, and no reference to `deck_go_live_delta`/`output_connected`/`live_authored_id` in `app.js` or `operator_headless.py`.
- The old editor-first structure is intact: `#pm-present` (index.html:738), `#pm-lib-back` (index.html:753); `pmActivate` (app.js:4388) opens the editor; `pmLibOpen` (app.js:4551) opens the editor after `deck_open`.
- Key seams: `pAct` (4205, returns bool), `pmShowLibrary`/`pmHideLibrary` (4423/4429), `pmRenderSlides` (4942), `pmPresent` (4592), `render_deck_slide` invoke (5158, args `{id,maxW,maxH}`), palette "Present slide" (4018, surface-gated 4015), `wirePresentation` (5246–5480).
- `#surface-presentation` spans index.html **729–874**; `#surface-remote` (owner's Remote Control, **do not touch**) starts at 890, JS in `remote.js`.

## Inputs and evidence sources

- Design spec: `docs/superpowers/specs/2026-08-04-presentation-browse-present-flow-design.md`
- Plan Phase 3 (Tasks 7–13): `docs/superpowers/plans/2026-08-07-presentation-browse-present-flow.md`
- §0 contract (Track A, delivered): `docs/superpowers/plans/2026-08-07-presentation-flow-delivery-tracks.md`
- Source: `dist/{index.html,app.js,app.css}`, `scripts/operator_headless.py`, and the pinned `selahcue-present/tests/` webview tests.

## Scope

### In scope

- Presentation surface only (`#surface-presentation`, `pm-*`): three-mode state (library|grid|editor); grid DOM/CSS/JS; lazy bounded-cache thumbnails; select/double-click-go-live/arrows-advance-live/transport; §8 states; a11y ring geometry + announcements; `--sc-*` tokens; relocate `#pm-present` + palette; headless-gate coverage.

### Non-goals

- Track A backend (done). Remote Control surface (`#surface-remote`/`remote.js`) — owner's concurrent work; never touched.
- On-slide video, media-library changes, editor internals (unchanged).

### Constraints

- **Concurrency:** `app.js`/`index.html`/`operator_headless.py` hold uncommitted owner WIP; edit ONLY Presentation-surface regions; at commit stage only own hunks (or hand off) — never sweep owner WIP; never rewrite shared history.
- **Gotchas (verified):** `blitFrame` (app.js:335) returns a **boolean**, not a dataURL → cache via `canvas.toDataURL()`. Text tokens are `--sc-text-secondary`/`--sc-text-muted` (not `-2`/`-3`). `#pm-live-region` is inside `.pm-body` (index.html:819) → grid needs its own reachable live region. `--sc-*` token block (app.css:28–57) is pinned by `test_tokens.rs` — do NOT change token defs; only consume them.
- **Pinned webview tests:** `selahcue-present/tests/` contains `operator_presentation_*`/`operator_presentations_library_*` content pins; removing/renaming `#pm-present`/`#pm-lib-back`/structure may break them — update them together and keep green.
- Bounded memory (thumbnail cache capped). No legacy `--live`/`--panel`/`--line`/`--accent`.
- Operator crate excluded from workspace: `cargo check --manifest-path`. Headless via `python3 scripts/operator_headless.py` (bump `EXPECTED_MIN_CHECKS` = 319 for added checks).

### Assumptions and unknowns

- ASSUMED: the pinned `selahcue-present` tests assert some Presentation-surface ids — validate by grep before removing any element (Iteration 1).
- ASSUMED: `dist/` is safe to edit in Presentation regions now (owner active on `remote.js`/backend). Re-check on any Edit anchor failure.

## Dependencies and approvals

- Track A §0 contract delivered + review-approved (86ajxeq0y) — no blocker.
- `test_protocol.rs` fixture break (owner's Stage/confidence WIP) is handled by another process — not a Track B dependency.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Three-mode state; presentation nav lands on the Library (not editor); `#pm-lib-back` removed; open a card → grid | `python3 scripts/operator_headless.py` (new checks) | PASS | headless output | PENDING |
| C-002 | yes | Grid renders one tile per slide via `render_deck_slide`; bounded thumbnail cache | headless: `.pm-tile` count == slides; `render_deck_slide` called | PASS | headless output | PENDING |
| C-003 | yes | Single-click selects (safe); double-click/Enter go-live (`deck_go_live`); ◀▶ + live-mode arrows advance (`deck_go_live_delta`); LIVE ring from `view().live_authored_id` | headless | PASS | headless output | PENDING |
| C-004 | yes | §8 states: go-live-failed (no ring + alert), preview-only (`!output_connected`), blackout cue, deck-open-failed (stay on library), empty-deck, first/last disabled, reconnecting | headless | PASS | headless output | PENDING |
| C-005 | yes | `#pm-present` relocated out of editor; palette "Present slide" re-scoped by mode; Edit ▸ / ‹ Done nav | headless | PASS | headless output | PENDING |
| C-006 | yes | a11y: `role=grid` + roving tabindex; three separable rings (inset selection / outset focus / live+label); aria-live announces live changes; `--sc-*` tokens only | headless + grep new rules for legacy vars (--live/--panel/--line/--accent) → none | PASS | headless + grep | PENDING |
| C-007 | yes | Pinned `selahcue-present` webview tests stay green after DOM changes | `cargo test -p selahcue-present` (operator_* pins) | PASS | test output | PENDING |
| C-008 | yes | Headless gate green with bumped `EXPECTED_MIN_CHECKS`; operator compiles | `python3 scripts/operator_headless.py` + `cargo check --manifest-path .../selahcue-operator/Cargo.toml` | PASS + clean | outputs | PENDING |
| C-009 | yes | Independent review + QA of Track B | /code-reviewer + /qa-engineer | approved | review/QA comments | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-task `operator_headless.py` driver checks (add stubs for `deck_go_live_delta`/`output_connected`/`live_authored_id` in `V`/`D`); `cargo check` of the operator crate.
- Regression: `cargo test -p selahcue-present` (webview content pins) + full `python3 scripts/operator_headless.py` (no lost checks; floor bumped).
- Manual: `make operator` — library → grid → double-click go-live → arrows advance → Edit ▸ / ‹ Done.
- Independent verifier: /code-reviewer + /qa-engineer (C-009).
- Required environment: local dev (headless Chrome for the gate).

## Iteration ledger

### Iteration 2 (Slice 1 — Tasks 7–8) — resumed on a clean base 2026-08-07

- Delivered: three-mode state (`pmSetMode`), nav lands on Library, open card → slide GRID, native `render_deck_slide` thumbnails (lazy IO + bounded cache + eager first fold), single-click select (safe), double-click go-live (`deck_go_live`) with red LIVE ring, Edit ▸ / ‹ Presentations nav, grid CSS (`--sc-*` only), grid aria-live region. Commit `51e3f4e`.
- Verifier: `python3 scripts/operator_headless.py` → **342 checks, 0 FAIL** (driver navigates library→grid→edit; +14 grid checks; `EXPECTED_MIN_CHECKS` 319→342).
- Fixes vs plan: `pmGridGoLive` always `deck_select_slide` then `deck_go_live` (client cursor ≠ host selection); eager-render first fold (IO doesn't fire in headless).
- Progress: C-001 (landing+open→grid) and C-002 (grid+thumbnails) substantially met (except `#pm-lib-back` removal, deferred to the relocation slice). C-003/004/005/006 remaining.
- Decision: iterate — next Slice 2 (host-truth ring `live_authored_id` + `◀▶`/arrows advance live via `deck_go_live_delta` + `output_connected`).

### Iteration 1

- Target criterion: C-007 (guard) then C-001
- Hypothesis: grepping the pinned `selahcue-present` tests for `pm-present`/`pm-lib-back` reveals what must be updated when relocating/removing them; then `pmMode`/`pmSetMode` + landing on library is the smallest first slice.
- Change or investigation: grep pinned tests; implement Task 7.
- Verifier executed: `grep pm-present|pm-lib-back` in `selahcue-present/tests/`
- Result: **CONFIRMED pinned** — `test_tokens.rs:619` pins `id="pm-present"` (in `operator_presentation_media_surface_is_wired`) and `test_tokens.rs:777` pins `id="pm-lib-back"` (in the library-wiring test). Relocating/removing them per the design (Tasks 7/11) REQUIRES updating those two needles in `test_tokens.rs` together (same file also pins the `--sc-*` tokens). Folded into C-007.
- Reconciliation gotchas confirmed: `blitFrame` returns bool (cache via `canvas.toDataURL()`); tokens `--sc-text-secondary`/`--sc-text-muted`; `#pm-live-region` inside `.pm-body` (grid needs its own); `EXPECTED_MIN_CHECKS=319`; bare arrows/Enter/Space free on the Presentation surface (transport hard-gated to console; canvas nudge is element-focus-gated).
- Decision: **paused for owner** — implementation is fully mapped, but the shared files it edits (`app.js`/`index.html`/`operator_headless.py`/`test_tokens.rs`) carry the owner's uncommitted concurrent WIP, so the commit strategy + a clean base are an owner-owned coordination decision before extensive edits (avoids the Track-A clobbering repeat). Working tree left UNMODIFIED.

## Risks and rollback

- Risks: clobbering owner's concurrent `dist/` WIP (mitigate: Presentation-region-only edits, Read-before-Edit, stage own hunks); breaking pinned webview tests (mitigate: grep + update together); thumbnail fan-out memory (mitigate: bounded cache + test hook).
- Rollback: changes are working-tree only until an explicit commit; revert per-file or discard hunks. No backend/schema change.

## Pause and escalation conditions

- An Edit anchor unexpectedly fails (owner edited the same region) → pause, re-read, re-scope.
- A required change to the §0 contract or the pinned token block → escalate (do not change token defs).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajxeq17-present-flow-frontend.md`
- Validator result: PASS (structural)
- Independent verification result: N/A (implementation not started)
- Terminal state: **BLOCKED (held per owner, 2026-08-07)** — reconciliation + contract complete; implementation (Tasks 7–13) not started. The four target files (`dist/app.js`, `dist/index.html`, `scripts/operator_headless.py`, `selahcue-present/tests/test_tokens.rs`) are under continuous concurrent owner editing (a stage/confidence feature), so no durable clean base exists. Owner chose to finish that work first; working tree left UNMODIFIED by Track B.
- **Exact unblocker (resume condition):** the four files above are committed and stay clean (stable base). Then implement Tasks 7–13 per the plan + this contract's completion predicate. All gotchas already mapped in Iteration 1.
- Remaining failed or blocked criteria: C-001…C-009 all PENDING (not started; held).
- ClickUp final evidence comment: posted on 86ajxeq17; task set to `ready dev` (scoped + contract-ready, awaiting a stable clean base).
