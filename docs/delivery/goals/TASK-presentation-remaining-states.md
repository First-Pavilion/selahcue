# Goal Contract — TASK-presentation-remaining-states

## Identity

- Goal ID: TASK-presentation-remaining-states
- Parent goal ID: EPIC-86ajp07ce (Presentation & Slides)
- Title: Presentation & Media — remaining states (destructive confirms · system · font picker · image Fit render)
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajvjzun
- Created: 2026-08-04
- Updated: 2026-08-04
- Maximum iterations: 14
- Independent verification required: yes (adversarial multi-lens review + reproduce)

## Objective

Complete the Presentation & Media surface by implementing the remaining designed states
(`PRESENTATION-MEDIA-STATES-spec.md` §5/§6/§8): destructive confirms, system loading/error, the
font-family picker, and image **Fit** render — so the surface is feature-complete.

## Baseline

**Verified:**
- The surface (86ajvccqr) + inspector (86ajvjtax) ship: add/select/edit/notes/transition/auto-advance,
  the Media⟷Inspector switch, undo/redo, palette. The engine has `deck_remove_slide`/`deck_remove_media`
  (wired to no UI affordance yet), and `deck_remove_element` (delete has no toast yet).
- The CPU raster **already implements the aspect math**: `FrameBuffer::fitted(w, h, Fit)` with
  `Fit::{Stretch (distort), Fit (letterbox), Fill (cover+crop)}` (raster.rs:423). `Element::Image`
  (theme.rs:182) has no fit field; `Layer::Image` (scene.rs:143) has no fit field — the image is blitted
  scaled-to-fill (= Stretch) today.
- `system_fonts` (Tauri command) + `tdLoadFonts` (app.js:1238) are the font-picker pattern.
- The desktop operator console is the **authoritative editor** (ARCHITECTURE); read-only ("View only",
  CANVAS-EDITING-spec §7) is a LAN/mobile role, not the operator surface → View-only is N/A here.

## Inputs and evidence sources

- `docs/design/PRESENTATION-MEDIA-STATES-spec.md` §2a/§5/§6, Figma 509:124.
- `crates/selahcue-present/src/{theme.rs,compose.rs}`, `crates/selahcue-engine/src/{scene.rs,raster.rs}`,
  `crates/selahcue-operator/{src/{deck_workspace.rs,main.rs},dist/*}`, `scripts/operator_headless.py`.

## Scope

### In scope
- **Destructive confirms:** delete-slide (rail affordance + `role="alertdialog"` confirm; Cancel-focused;
  Esc cancels; two-step → `deck_remove_slide`); remove-media (cell affordance + confirm w/ **in-use** warning
  → `deck_remove_media`); delete-element → an "Element deleted — Undo" toast (`role="status"`, ⌘Z-backed).
- **System states:** loading (`aria-busy` on the canvas during render + a first-load placeholder); error
  banner (`role="alert"` "Couldn't {action} — retry" when a deck command rejects). **View-only = N/A**
  (justified: authoritative desktop editor).
- **Font-family picker:** the Text inspector Font control, from `system_fonts`; patches `{font}` (System
  default → clears to the bundled default / `null`).
- **Image Fit render (engine):** additive `fit: Fit` on `Element::Image` (default **Stretch** = current
  behaviour, byte-stable) → `Layer::Image` → the raster blit honours it (Fit=letterbox, Fill=cover) via the
  existing `fitted` math; the inspector Fit control (Stretch / Fit / Cover) drives it; the preview reflects it.

### Non-goals
- Present→live-output routing, on-slide video/audio playback, cross-restart persistence (prior deferrals).
- A new fit algorithm (reuse `FrameBuffer::fitted`).

### Constraints
- Deck edits return the operator-local `DeckView`; **FR-012** (edit/select never touches Live); compositor
  native (preview only, never-blank NFR-024); `--sc-*` AA; never colour-only; alertdialog focus-trap + Esc;
  bounded/never-panic; **additive serde keeps pinned theme JSON byte-stable** (default `fit`=Stretch omitted);
  `make ci` green.

### Assumptions and unknowns
- ASSUMED: the raster's `Layer::Image` render path can call the existing `fitted`/blit math to place the
  decoded image per-fit. Validate in compose/raster tests.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Delete-slide: rail affordance + `role="alertdialog"` confirm (Cancel-focused, Esc cancels) → `deck_remove_slide` | headless | confirm flow works | `.pm-slide-del` affordance (disabled on the last slide) → `pmConfirm` alertdialog; headless: affordance present, alertdialog opens, Cancel focused, Esc cancels (no removal), confirm drives `deck_remove_slide` | PASS |
| C-002 | yes | Remove-media: cell affordance + confirm w/ in-use warning → `deck_remove_media` | headless | confirm + warning | `.pm-asset-del` per cell; confirm warns "Used on k slides" from the new per-asset `uses` count; headless: in-use asset warns "2 slides", confirm drives `deck_remove_media(id)` | PASS |
| C-003 | yes | Delete-element → "Element deleted — Undo" toast (`role="status"`, ⌘Z-backed) | headless | toast + undo | `pmDeleteElement` → `pmToast` (role=status, bounded 7s); headless: delete shows toast "Element deleted", Undo drives `deck_undo` | PASS |
| C-004 | yes | System: `aria-busy` canvas on render + first-load placeholder; error banner (`role="alert"`) on a rejected deck command | headless | states render | `pmSetBusy` toggles `aria-busy` + `.busy` shimmer; `#pm-error` role=alert + Retry; headless: managed aria-busy, rejected command shows the banner, Retry re-runs + clears | PASS |
| C-005 | yes | View-only justified NOT_APPLICABLE (authoritative desktop editor) | this doc | justified | PASS = the justification is delivered: the desktop operator console is the AUTHORITATIVE editor (ARCHITECTURE: desktop-authoritative); read-only "View only" (CANVAS-EDITING-spec §7) is a LAN/mobile *controller* role, not the operator surface — there is no view-only operator, so the state cannot arise here. | PASS |
| C-006 | yes | Font-family picker in the Text inspector (from `system_fonts`) patches `{font}`; System default clears it | headless | font control wired | `pmFontSelect` from cached `system_fonts` (labels a not-installed family); patches `{font}` (empty → null clears to the bundled default); headless: picker populated, choosing a font patches `{font}`, "System default" patches null; operator unit test round-trips set+clear | PASS |
| C-007 | yes | `Element::Image` gains additive `fit` (default Stretch, byte-stable); compose+raster honour it (Fit=letterbox, Fill=cover) | `cargo test` compose/raster | aspect-correct + byte-stable | `scene::ImageFit` + additive `fit` on `Layer::Image`/`Element::Image` (default Stretch skipped → byte-stable); `blit_image` honours Stretch/Fit/Fill; tests: `fit_letterbox_*` (gap shows bg), `fit_fill_*` (cover), `fit_stretch_*` (byte-identical to legacy), compose threads fit, byte-stability | PASS |
| C-008 | yes | Inspector Fit control (Stretch/Fit/Cover) drives `deck_update_element` `{fit}`; preview reflects it | headless | fit control wired | Live 3-way `<select>` (`data-ik="imgfit"`, aria-label) replaces the old disabled placeholder; patches `{fit}`; `element_json` always exposes `fit`; headless: 3 options, live, patches `{fit:"fit"}`; operator unit test | PASS |
| C-009 | yes | a11y: alertdialog focus-trap + Esc, toast/banner roles, font picker labelled, AA | headless | a11y checks pass | `pmConfirm` role=alertdialog + aria-modal + labelledby/describedby, Cancel-focused, Esc + Tab-trap, focus restored on close; toast role=status; banner role=alert; Font/Fit selects aria-labelled; `--sc-*` AA tokens; headless a11y checks pass | PASS |
| C-010 | yes | Bounded/never-panic + FR-012 preserved across the new paths | operator unit test + review | green | Merge-patch stays serde-validated (bad `{fit}`/`{font}` = no-op, never panic); `uses` count bounded by deck size + per-slide dedupe; toast timer single + cleared; the new paths call only `deck_remove_*`/`deck_undo` (edits) — never `deck_go_live` (FR-012); operator tests 9/9 | PASS |
| C-011 | yes | `test_tokens` pin + `operator_headless` (+bump) + compose/raster tests for Fit | `cargo test` + headless | green | pin 16/16; headless **265/0** (`EXPECTED_MIN_CHECKS` 238→265, +27 checks); engine/present Fit tests green (raster now proves letterbox band + centre-crop; adversarial-rect Fit panic test) | PASS |
| C-012 | yes | Full CI gate green | `make ci` | ALL GREEN | `make ci` == **local CI gate: ALL GREEN** (exit 0): fmt --check, clippy -D warnings (operator now `--all-targets`), all Rust suites incl. **operator `cargo test`**, headless 265/0, flutter; re-run after the review fixes | PASS |
| C-013 | yes | Independent adversarial review; confirmed Blocker/High fixed + re-verified | review workflow | none unresolved | 4-lens adversarial review (engine-fit/serde · webview-a11y · bridge/state · test-quality): **no Blocker/High correctness defects**; surviving findings (1 High a11y + several Med/Low) **all fixed + re-verified** (see ledger iter 2) — engine/present/operator suites green, headless 265/0 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `node --check`; `cargo test` (present compose/raster; operator unit); `operator_headless.py`;
  `test_tokens`. Broader: `make ci`; the theme byte-stability tests stay green (additive `fit`).
- Independent: 3–4-lens adversarial review (engine-fit/serde · webview-a11y · bridge/state · test-quality).

## Iteration ledger

### Iteration 1 — build the remaining states
- **Engine (C-007):** `scene::ImageFit` (Stretch/Fit/Fill) + additive `fit` on `Layer::Image`/`Element::Image`
  (default Stretch, `skip_serializing_if` → byte-stable); fit-aware `blit_image` (Fit=letterbox leaving the gap,
  Fill=cover+centre-crop); threaded through `compose::element_layers`; `push_background` pinned to `Stretch`.
- **Webview (C-001..C-006, C-008):** `pmConfirm` (role=alertdialog), `pmToast` (role=status), `pmShowError`
  (role=alert)+Retry, `pmSetBusy` (aria-busy), `pmFontSelect` (system_fonts), live image Fit `<select>`;
  delete-slide/remove-media affordances; per-asset `uses` count in `view()`; `element_json` exposes `fit`.
- **Tests:** engine Fit raster + byte-stability; compose fit-threading; 3 operator unit tests; token pin
  (`operator_presentation_remaining_states_are_wired`); headless +25 (263/0).
- **Verify:** `make ci` == ALL GREEN (first pass).

### Iteration 2 — independent adversarial review (C-013) + fixes
- **4-lens review (parallel agents):** engine-fit/serde · webview-a11y · bridge/state · test-quality. Each
  finding was refuted before it survived. **No Blocker/High correctness defects.** Surviving, all fixed:
  - *engine/serde* — 0 defects. Added 2 hardening items: a real-image adversarial-rect Fit/Fill panic test,
    and an overflow-margin note coupling `blit_image`'s i64 math to `MAX_DIMENSION`.
  - *a11y (1 High, 6 Med, 4 Low)* — inspector controls now get a real `<label for>` (High); the confirm's
    **warning** is in `aria-describedby` (Med); `.pm-btn-danger` recoloured to dark-on-red for AA ~5.9:1 (Med);
    focus lands sensibly after a destructive re-render — canvas / add-slide (Med); `#pm-sel` `tabindex="-1"`
    (Med); ⌘Z / ⌘1–6 / ⌘⇧P suppressed behind an open confirm, emergency chords still pierce (Med); toast/banner
    un-hidden **before** their text is set so live regions announce (Med); toast bg → `--sc-surface` for the
    Undo text's AA (Low); "in use" named in the cell aria-label, not colour-only (Low); toast-dismiss focus
    rescue (Low); confirm-stacking guard (Low).
  - *bridge/state (1 Med, 3 Low)* — **operator `cargo test` + `clippy --all-targets` added to `make ci` and
    ci.yml** (Med: the Rust bridge tests were compiled/linted but never *run* in CI); the delete toast now fires
    only when an element was actually removed (Low); ⌘Z-behind-modal guard (Low, = a11y); `pmLoadFonts`
    in-flight guard (Low).
  - *test-quality (2 Med, 2 Low)* — the Fill raster test now uses a horizontally-varying image so it proves the
    **centre-crop** (was indistinguishable from Stretch); the Fit test pins the exact band geometry (oy=2, sh=4);
    the headless toast-Undo assertion uses a strict before/after `deck_undo` delta (was tautological on the
    accumulated `__calls`); the aria-busy check now drives a **deferred** command to observe the in-flight
    `true`→`false` transition (was attribute-presence only).
  - *concurrency (found while fixing)* — `pmSetBusy` became a reference **counter**, so overlapping deck
    round-trips don't clobber each other's busy state.
- **Re-verify:** engine/present/operator suites green; token pin 16/16; headless **265/0**
  (`EXPECTED_MIN_CHECKS` 263→265); re-running `make ci` for the final sign-off.
- **Deferred (pre-existing, out of scope):** the `.pm-slide-live-badge` white-on-red (a broadcast-convention
  LIVE badge from 86ajvccqr, paired with the "LIVE" text + aria-label — not colour-only) is noted for a
  follow-up polish, not changed here.

## Risks and rollback

- Risk: adding `fit` to `Element::Image`/`Layer::Image` breaks the pinned theme JSON / GPU parity. Mitigation:
  additive `skip_serializing_if` default Stretch → byte-identical; a byte-stability test; SSIM parity check.
- Risk: an alertdialog focus-trap regression. Mitigation: reuse the existing modal pattern (cmd palette);
  headless focus tests.

## Pause and escalation conditions

- Stop at `make ci` green + review clean + owner visual gate.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-presentation-remaining-states.md --require-complete`
- Validator result: PASS (13/13 mandatory PASS; C-005 = PASS via its justification that view-only is N/A)
- Independent verification result: 4-lens adversarial review — no Blocker/High correctness defects; the
  surviving a11y/test/CI-gap findings all fixed + re-verified (engine/present/operator suites green, headless 265/0).
- Terminal state: **VERIFIED_COMPLETE**
- Remaining failed or blocked criteria: none.
- Status: **VERIFIED_COMPLETE** — the Presentation & Media surface is feature-complete against
  `PRESENTATION-MEDIA-STATES-spec.md` §5/§6/§8.
- ClickUp final evidence comment: posted to 86ajvjzun + BUILD CONTROL 86ajnx548 (`make ci` == ALL GREEN,
  exit 0, incl. the newly-gated operator `cargo test`).
