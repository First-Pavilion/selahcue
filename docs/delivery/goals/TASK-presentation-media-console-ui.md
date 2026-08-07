# Goal Contract — TASK-presentation-media-console-ui

## Identity

- Goal ID: TASK-presentation-media-console-ui
- Parent goal ID: EPIC-86ajp07ce (Presentation & Slides)
- Title: Presentation & Media console UI (Design 2.0, node 329:124) — slide editor + media library, wired to the deck/media engine
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajvccqr
- Created: 2026-08-03
- Updated: 2026-08-03
- Maximum iterations: 16
- Independent verification required: yes (adversarial multi-lens review + headless reproduce)

## Objective

Implement the operator-console **Presentation & Media** surface (webview `dist/`) AND the Tauri bridge
that drives the real deck/media engine (86ajv8qd9) — a genuinely working slide editor + media library
matching Figma 329:124, not a dead shell.

## Baseline

**Verified (architecture scout + source reads):**
- Bridge = **Tauri `invoke` only** (no webview socket). Mutation commands return the LAN-shared
  `OperatorView`; previews return `{w,h,rgba}` base64 that JS blits to a `<canvas>` (compositor is native
  wgpu — the webview never renders audience output, ADR-0002/0003). `preview_theme` (`main.rs:711`) →
  `render_sample` is the preview pattern; `render_console`/`render_screen` show clamping + `blitFrame`.
- **No deck/media bridge exists** — `main.rs` has zero deck/media handlers; the engine
  (`selahcue-present::deck` + `compose_authored_slide` + `selahcue-core::media`) is fully tested but
  entirely unwired. The bridge is this story's to add.
- Add-a-surface recipe: nav `<button data-surface>` (the "Presentation" item is currently
  `nav-later`/`aria-disabled`, `index.html:33`), a `#surface-*` section, register in `APP_SURFACES`
  (`app.js:1069`) + `SURFACE_LABEL` (`:1072`), router hook in `showSurface` (`:1097`). `AppState`
  (`main.rs:518`) is `.manage()`d; commands register in `generate_handler!` (`:1126`).
- Conventions to mirror: Theme Designer `.td-wrap` 2-col grid, `td-*` ids, LAYERS panel, `tdFitCanvas`,
  `--sc-*` tokens (`app.css:29`), `blitFrame`/`b64ToBytes` (`app.js:305`). Tests: `test_tokens.rs` pin
  suite + `operator_headless.py` (stub new invokes, bump `EXPECTED_MIN_CHECKS=185`).

## Inputs and evidence sources

- Figma 329:124 (topbar + SLIDES list + slide-canvas editor + MEDIA LIBRARY).
- Engine: `selahcue-present::deck` (`SlideDeck`/`AuthoredSlide`/`DeckSession`/`crossfade`/`media_usage`),
  `compose_authored_slide`, `selahcue-core::media` (`MediaLibrary`), ADR-0020.
- `crates/selahcue-operator/{src/main.rs,dist/*}`, `crates/selahcue-present/tests/test_tokens.rs`,
  `scripts/operator_headless.py`.

## Scope

### In scope

- **Webview surface** `#surface-presentation`: topbar (plan context + Add-to-plan + Present); **SLIDES**
  list (add/select/reorder/duplicate/delete + thumbnails); **slide-canvas** (add-content Text/Shape/Image/
  Background, element select/move/resize/z/visibility, undo/redo, "Slide N/M · 1920×1080", native preview
  via `render_deck_slide`, canvas fit); bottom bar (notes, Transition, Auto-advance); **MEDIA LIBRARY**
  (Import, All/Images/Video/Audio filters, search, grid w/ image/video/missing states, AUDIO list, storage
  + "N missing · M unused" footer).
- **Tauri bridge** (`main.rs`): `DeckWorkspace` in `AppState` (owns `SlideDeck` + `MediaLibrary` + cursors
  + bounded undo/redo snapshots); deck/media commands returning an operator-local `DeckView`;
  `render_deck_slide` preview.
- **≥20-step undo/redo** (bounded snapshot stack) + **command palette** (keyboard-first; canonical keys
  respected; emergency chords pierce).

### Non-goals (honest "later" affordances — visible, disabled/labelled)

- **Present → live audience-output routing** (decks aren't in `LiveController`); native **video/audio disk
  import + on-output playback** (ADR-0020 video deferral); **cross-restart persistence** (deck_repo/
  media_repo wiring). Global command-palette commands beyond this surface.

### Constraints

- WKWebView-safe (no `window.prompt`); AA contrast (`--sc-*`); native-wgpu compositor (preview only, never
  render audience output in the webview); editing/staging never changes Live (FR-012); bounded memory;
  every pinned needle / JS hook preserved; `make ci` green.

### Assumptions and unknowns

- ASSUMED: the operator owns the deck workspace in-memory this pass (persistence deferred). Owner: role.
- ASSUMED: `render_deck_slide` composes one authored slide via `compose_authored_slide` (already tested).

## Dependencies and approvals

- Engine story 86ajv8qd9 (VERIFIED_COMPLETE) supplies the deck/media engine. No blocker.
- Scope (full surface + bridge; undo+palette; new story) approved by the user this session.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Presentation nav activated + `#surface-presentation` + `APP_SURFACES`/`SURFACE_LABEL`; router activates it | headless + token pin | nav-click → surface active | headless: nav item activated + `#surface-presentation` active on click; pin test green | PASS |
| C-002 | yes | Tauri bridge: `DeckWorkspace` in `AppState` + deck/media commands registered; operator compiles | `cargo check` operator manifest | compiles | `cargo check` + `cargo clippy` operator clean; 24 deck/media commands registered | PASS |
| C-003 | yes | SLIDES list: add/select/reorder/duplicate/delete drive the deck; numbered thumbnails | headless | list ops work | headless: add-slide/select-slide + one row per slide + thumbnails | PASS |
| C-004 | yes | Slide-canvas: add-content toolbar (Text/Shape/Image/Background; Video honest-later); preview renders via `render_deck_slide` (`.has-render`); "Slide N/M"; canvas fits | headless | canvas renders, toolbar adds elements | headless: canvas `.has-render` via render_deck_slide; Text tool adds element; "Slide 2 / 2 · 1920×1080" | PASS |
| C-005 | yes | Element select + move/resize (per-mille) + z + visibility on the canvas | headless | element edits drive commands | headless: canvas click-select + arrow-nudge (deck_move_element) + `]` z + `H` visible + Delete | PASS |
| C-006 | yes | Bottom bar: notes / Transition / Auto-advance wired to the slide | headless | controls drive commands | headless: deck_set_notes / deck_set_transition / deck_set_auto_advance | PASS |
| C-007 | yes | MEDIA LIBRARY: filters + search + grid (image/video/missing) + AUDIO + storage/"N missing · M unused"; Import (image picker; video/audio later) | headless | library renders + filters + counts | headless: grid + missing state + AUDIO list + "1 missing · 3 unused" (warn) + Images filter hides video | PASS |
| C-008 | yes | Undo/redo ≥20 steps (buttons + Cmd/Ctrl+Z/Shift+Z) via `deck_undo`/`deck_redo` | headless | 25 edits → undo ≥20 → redo | headless: Undo enabled after edits → deck_undo; ⌘Z/⌘⇧Z surface-scoped; host stack `MAX_UNDO=60` (≥20) | PASS |
| C-009 | yes | Command palette (keyboard-first; canonical keys respected; emergency chords pierce) | headless | palette opens, runs a command, never swallows emergency keys | headless: palette offers "Add slide" while active; extends the existing ⌘K palette (chords intact) | PASS |
| C-010 | yes | Preview→Live isolation (FR-012): editing/staging never changes Live; Present is an honest live-output affordance | headless + review | Live untouched by edits | headless: editing fires no deck_go_live; Rust `select_slide`/edits never set `live`; only `go_live` does | PASS |
| C-011 | yes | a11y + never-blank: keyboard-operable, aria state/labels, focus retained across re-render, AA, canvas never blank | headless + token AA | a11y checks pass | keyboard ops + aria-labels/`aria-current` + `--sc-*` AA (token suite) + compose never-blank (engine) | PASS |
| C-012 | yes | `test_tokens.rs` pins the surface's load-bearing needles | `cargo test -p selahcue-present --test test_tokens` | green | `operator_presentation_media_surface_is_wired` + suite 15/15 | PASS |
| C-013 | yes | Full CI gate green | `make ci` | ALL GREEN | `make ci` == **ALL GREEN** (exit 0), re-confirmed after the 16 review fixes: fmt/clippy/all Rust suites/operator check/headless **223/0**/flutter | PASS |
| C-014 | yes | Independent adversarial multi-lens review; every confirmed Blocker/High fixed + re-verified | review workflow | none unresolved | 4-lens workflow (walb9hb3y): **16 confirmed (5 med, 11 low); no Blocker/High**; **all 16 fixed + re-verified** (operator tests 3/3, headless 223/0) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `node --check app.js`; `cargo check` operator manifest; `python3 scripts/operator_headless.py`
  (new Presentation checks + `EXPECTED_MIN_CHECKS` bump); `cargo test -p selahcue-present --test test_tokens`.
- Broader regression: `make ci` (fmt/clippy/all suites/operator check/headless/flutter). Existing surfaces
  (console/screens/theme-designer) stay green.
- Independent verifier: 3–4-lens adversarial review (correctness/integration · a11y-ux · bridge/state ·
  test-quality); fix confirmed Blocker/High; re-run headless + token + `make ci`.
- Required environment: local workspace; headless Chrome (operator_headless).

## Iteration ledger

### Iteration 1 — build the surface + bridge
- **Rust bridge:** new `deck_workspace.rs` (`DeckWorkspace` owns `SlideDeck` + `MediaLibrary` + cursors
  + a bounded `MAX_UNDO=60` undo/redo snapshot stack; builds the operator-local `DeckView`; `render_slide`
  via `render_authored_slide` — a new thin present helper). 24 `deck_*`/`render_deck_slide` Tauri commands
  (async, `with_deck` helper, std-Mutex held await-free) registered; `AppState.deck` seeded with a demo
  deck + media library (a `demo://` scheme so the missing-probe shows a realistic "1 missing" without real
  files). `cargo check` + `cargo clippy` on the operator: clean.
- **Webview:** activated the Presentation nav item (`data-surface` + `data-nodigit` so the ⌘1–6 map is
  byte-stable; ⌘⇧P shortcut). `#surface-presentation` (topbar + SLIDES rail + slide-canvas editor + MEDIA
  LIBRARY), `.pm-*` CSS on `--sc-*` tokens. `renderPresentation`/`pAct` — a SEPARATE render loop from the
  console's `render(OperatorView)` (deck commands return `DeckView`). Slide preview via `render_deck_slide`
  → `blitFrame` (native compositor). Element select/move (canvas pointer + arrow/`[`/`]`/`H`/Delete
  keyboard), notes/transition/auto-advance, media grid+filters+search+missing/unused footer, undo/redo
  (buttons + surface-scoped ⌘Z/⌘⇧Z), and Presentation commands in the existing ⌘K palette.
- **Tests:** `operator_presentation_media_surface_is_wired` pin (suite 15/15); 29 new headless PM checks
  (nav-activate, canvas `.has-render`, SLIDES, add-element, FR-012 isolation, media missing/unused, filter,
  undo, Present, canvas keyboard, palette, ⌘⇧P) → headless **218/0**; `EXPECTED_MIN_CHECKS` 185→218.
- **Verify:** `node --check` OK; operator compiles + clippy clean; `test_tokens` 15/15; headless 218/0.
  `make ci` + adversarial review running.
- **Decision:** iterate — await `make ci` (C-013) + review (C-014), fix confirmed findings.

### Iteration 2 — `make ci` green + adversarial review + fixes
- **C-013:** `make ci` == ALL GREEN (exit 0) — first pass.
- **C-014:** 4-lens adversarial review (walb9hb3y; 22 agents, each finding refuted before it survived) →
  **16 confirmed: 5 medium, 11 low; no Blocker/High survived** (the 2 `high` candidates downgraded to
  medium on verification). **Fixed all 16:**
  1. *[med correctness]* the "Image"/"Background" tools snapshot-before-no-op, corrupting undo/redo → a
     new `commit()` helper snapshots **only on a real edit**; every guarded op (out-of-range index,
     at-cap add, no-image) now records nothing on a no-op. **+3 operator unit tests** (undo-bounded,
     no-phantom-undo, FR-012 isolation).
  2. *[med a11y]* element selection was mouse-only → canvas **Tab-cycles** elements (front→back) +
     arrow-selects-first + an aria-live announce.
  3. *[med a11y]* media filter was a fake `role=tablist` → real `role=group` + `aria-pressed` toggle group.
  4. *[med a11y]* Live indicator was colour-only → a visible **LIVE badge** + `(live)` in the aria-label.
  5. *[med a11y]* canvas keyboard had no discoverable affordance → an `aria-describedby` key-hint line +
     an aria-live region.
  6–7. *[low]* the "Background" tool now inserts a **full-frame** shape (matching its label), not a small box.
  8. *[low]* fixed the `navGo` comment doc-drift (Presentation is no longer a "later" example).
  9. *[low]* `--sc-text-muted`→`--sc-text-secondary` for small PM text (AA).
  10. *[low]* focus restored across the SLIDES-list rebuild.
  11. *[low]* `:focus-within` outlines on the notes/search inputs (WCAG 2.4.7).
  12,16. *[low]* tightened two non-load-bearing pin needles (scoped `pm-tool` + exact `APP_SURFACES`/`SURFACE_LABEL`).
  13,14,15. *[low test-coverage]* added the ⌘2 digit-map-preserved headless check + the 3 operator unit tests.
- **Re-verify:** node --check OK; operator `cargo check`+`clippy`+`test` (3/3) clean; `test_tokens` 15/15;
  headless **223/0** (+5 checks); re-running `make ci` for the final sign-off.
- **Decision:** complete on the final `make ci` green.

## Risks and rollback

- Risk: bloating the LAN-shared `OperatorView` → churns pinned Dart fixtures. Mitigation: deck/media use a
  SEPARATE `DeckView` (operator-local), never `OperatorView`. Rollback: the surface + commands are additive.
- Risk: rendering audience output in the webview (violates ADR-0002/0003). Mitigation: preview only via
  native `render_deck_slide` base64 blit.
- Risk: unbounded undo stack. Mitigation: bounded snapshot cap + a bounded-behaviour headless check.

## Pause and escalation conditions

- Stop at `make ci` green + independent review clean + owner visual gate.
- Escalate if Present→live-output or persistence turns out to be required for a testable surface (scope).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-presentation-media-console-ui.md --require-complete`
- Validator result: PASS (14/14 mandatory PASS)
- Independent verification result: 4-lens adversarial review (walb9hb3y) — 16 confirmed (5 med, 11 low),
  no Blocker/High; all 16 fixed + re-verified.
- Terminal state: **VERIFIED_COMPLETE**
- Remaining failed or blocked criteria: none.
- Reviewed vs unbuilt: **built** = the Presentation & Media surface + Tauri bridge (deck/media CRUD,
  element edit, notes/transition/auto-advance, media library, undo/redo, palette, native preview);
  **deferred (honest "later")** = Present→live-output routing, native video/audio disk import + on-output
  playback (ADR-0020), cross-restart persistence. QA-ready; final pixel-level visual QA of the running
  Tauri webview is owner-run (no in-repo render harness).
- ClickUp final evidence comment: posted to 86ajvccqr (handoff) + BUILD CONTROL 86ajnx548.
