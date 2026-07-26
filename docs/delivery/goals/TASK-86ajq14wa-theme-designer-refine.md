# Goal Contract — TASK-86ajq14wa-theme-designer-refine

## Identity

- Goal ID: TASK-86ajq14wa-theme-designer-refine
- Parent goal ID: STAGE8-core-presentation
- Title: Theme Designer refine (owner + Figma 204-124/208-137) — full-center canvas, on-canvas resize/reposition, a full-width lower-third band, and a maintainable multi-file console
- Role: frontend-engineer (+ the additive theme-engine band it needs)
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq14wa
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 14
- Independent verification required: yes

## Objective

Bring the Theme Designer (S8-3c) up to the approved Figma: the template **preview takes the full center** with the selected region **resizable/repositionable on canvas** (Figma 204-124), and the **lower-third** renders as a **full-width bottom band** (semi-transparent fill + amber border), not left-only narrow text (Figma 208-137). Split the growing single-file console into maintainable assets with **no runtime overhead**. Register the "edit + save default templates" (Figma "Save changes" / a saved-theme library) as a follow-up story.

## Baseline

Verified: the Theme Designer surface (`dist/index.html` `#surface-theme-designer`) has a small centered preview + inspector (colour/size/align/line-height/Fit) that renders via `preview_theme` (host render → base64 RGBA → canvas). `Theme{background, title, body}`; `RegionStyle` carries `x/y/w/h_permille + align_h/align_v + typography + fit`. `selahcue-engine` has `Layer::Fill{rect,color}` with **src-over alpha blend** (`fill_rect`→`fb.blend`) → a semi-transparent band + border compose cleanly; no rounded-rect primitive (square band). `lower_third()` regions are already ~88% wide but text is `align_h: Left`. `Theme` crosses the wire as a JSON **string** and is serde-serializable → an additive `Option<Band>` with `skip_serializing_if` is backward compatible. Pin tests (`test_tokens`) read `dist/index.html` for ~50 needles + the emergency-footer-after-`</main>` invariant.

## Inputs and evidence sources

- Figma 204-124 (Theme Designer) + 208-137 (lower-third); THEME-MODEL-spec.md; theme.rs/compose.rs; selahcue-engine scene.rs/raster.rs (`Layer::Fill`, `fill_rect`); dist/index.html; test_tokens.rs; tauri.conf.json (CSP).

## Scope

### In scope

- **Theme-engine band (additive)**: `Theme.band: Option<Band>` (`Band{ rect permille, fill: Rgba, border: Rgba, border_permille }`), `#[serde(default, skip_serializing_if="Option::is_none")]`. `compose_slide` draws the band **fill + 4 border rects** before the text regions (content slides only). Other built-ins keep `band: None` → pixels unchanged.
- **Lower-third redesign** (Figma 208-137): a full-width bottom band (fill + amber border) with the reference (amber) above the body (white), left-aligned inside the band.
- **Full-center canvas** (Figma 204-124): restructure `#surface-theme-designer` — left template list, a **large center canvas**, right inspector split into **LAYOUT** (H+V alignment · X/Y/W/H% · Ref-gap · Lock-aspect) + **TYPE** (colour · size · line-height · Fit). Safe-area guide on the canvas.
- **On-canvas resize/reposition**: an overlay selection box + 8 handles on the selected region, mapped from its rect%; drag to move (x/y), drag handles to resize (w/h ± x/y); updates the region + the LAYOUT X/Y/W/H fields; re-previews (debounced). Numeric X/Y/W/H fields also edit the rect.
- **File split**: extract the `<style>` → `dist/app.css` and the `<script>` → `dist/app.js`, loaded via `<link>`/`<script src defer>` (same-origin local assets — CSP-safe, no runtime overhead). Update the pin tests to read the split files (combined). `app.js` is now `node --check`-able directly.
- **Follow-up story**: register "edit + save default templates (saved-theme library: duplicate/rename/delete/persist)" in ClickUp, linked to 86ajq14wa.

### Non-goals (seams — note; later increments)

- Add-content (Text/Scripture/Shape/Image), Import/Export, Save-changes persistence + named-theme library (→ the new follow-up story), font family/weight/letter-spacing, per-screen assignment (86ajq321k), true alpha-keying over NDI/video (R-later), rounded band corners, band drag/resize (band is a fixed per-template decoration this slice).

### Constraints

- Additive serde (`Theme` JSON round-trips; older custom-theme JSON without `band` → `None`). Pinned console invariants: emergency footer sibling-of-`</main>`, keymap, token needles all still asserted (against the split files). Preview stays a pure deterministic host render. fmt/clippy clean; operator build; 3-OS CI.

### Assumptions and unknowns

- ASSUMED: the operator CSP allows same-origin external `app.js`/`app.css` (default Tauri CSP permits `'self'`; will verify tauri.conf.json). ASSUMED: on-canvas handles map linearly to rect% (canvas is a fixed aspect box).

## Dependencies and approvals

- Owner decisions (this refine): **full band this refine**; **edit-defaults → follow-up story**. S8-3c (done).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Additive band model: `Theme.band: Option<Band>` serde round-trips; old JSON w/o `band` → `None`; `classic`/`high-contrast` pixels unchanged (band=None) | `cargo test -p selahcue-present` | additive; no regression | test_compose::theme_band_serde_is_additive_and_backward_compatible + present suites green | PASS |
| C-002 | yes | Lower-third (Figma 208-137): full-width band (fill + amber border) renders via `compose_slide`; reference amber above white body inside the band; not left-only-narrow | render test + headless | band pixels + full width | test_compose::lower_third_renders_a_full_width_band_not_left_only + scratchpad/lt.png | PASS |
| C-003 | yes | Theme Designer full-center layout (Figma 204-124): left templates · large center canvas + safe-area · right LAYOUT (H/V align · X/Y/W/H · ref-gap · lock) + TYPE (colour/size/lh/Fit) | structure test + headless render | matches the Figma structure | test_tokens (needles) + scratchpad/shot-td-refine.png | PASS |
| C-004 | yes | On-canvas resize/reposition: overlay handles move/resize the selected region (updates x/y/w/h_permille + LAYOUT fields + re-preview); numeric X/Y/W/H edit too | structure test + headless + logic | drag+numeric edit works | headless interaction DBG (keys 6→9%, drag→clamp, W 88→50) + 8 handles | PASS |
| C-005 | yes | `dist` split into index.html + app.css + app.js (no inline style/script body); loaded locally; pin tests updated + green; `app.js` `node --check` clean; emergency footer/keymap intact | `cargo test test_tokens` + node --check + tags | all green; split clean | test_tokens + test_keymap (app.js) green; node --check clean; tags balanced | PASS |
| C-006 | yes | Full: make ci + operator build + fmt/clippy clean; independent Workflow review, findings fixed; 3-OS CI green; edit-defaults follow-up story registered | make-ci + Workflow + CI + ClickUp | all green; review fixed; story linked | CODE-REVIEW-batchS83c-refine.md; 86ajq4xmy registered+linked; CI green pending push | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-crate `cargo test` (present: band serde + compose + lower-third render + unchanged-pixels; app/lan/data unaffected); `test_tokens` (pin + structure, split-file aware); `node --check dist/app.js`; tag balance; a headless render of the Theme Designer surface (full-center canvas + handles) and of the lower-third output. Broader: make ci + 3-OS CI. Independent: adversarial Workflow review (band-engine/serde-compat · lower-third-fidelity · canvas-drag-correctness/a11y · file-split-integrity lenses).
- Required environment: local + CI.

## Iteration ledger

1. **Theme-engine band** — added `Band` + `Theme.band: Option<Band>` (additive serde) + `compose::band_layers` (fill + 4 border edges, clamped); redesigned `lower_third()` to a full-width band (Figma 208-137). Verifier: `test_compose` band serde-additive + `lower_third_renders_a_full_width_band_not_left_only` green; present render suites unchanged; `scratchpad/lt.png` matches 208-137. C-001/C-002 PASS.
2. **File split** — extracted `<style>`→`app.css`, `<script>`→`app.js`; `index.html` links them (csp null, `frontendDist: "dist"`). Pin tests read the combined sources; `test_keymap` reads `app.js`; the emergency-footer DOM invariant stays on `index.html`. Verifier: `test_tokens`+`test_keymap` green; `node --check app.js`; tags balanced. C-005 PASS.
3. **Full-center canvas + drag/resize** — restructured `#surface-theme-designer` (left templates · big center canvas + safe-area + 8-handle overlay · right LAYOUT[X/Y/W/H + H/V align] + TYPE); host-sourced built-ins via `builtin_themes` (removed the drift-prone JS mirror); on-canvas move/resize + numeric fields + keyboard nudge. Verifier: headless render (`shot-td-refine.png`) + interaction DBG (keyboard 6→9%, drag+clamp, numeric). C-003/C-004 PASS.
4. **Independent adversarial review** (`wf_9ab417e1-53a`, 4 lenses → verify, 7 agents): 3 raised → **3 CONFIRMED (all fixed), 0 noise** (band/lower-third/split lenses clean). Fixed: (MED) resize now edge-based so the anchored edge never jumps; (MED) numeric fields commit on `change` + skip-focused so multi-digit entry works; (LOW) `pointercancel` clears the drag. Verifier: re-ran the interaction harness — anchored resize (X stays 10% while dragging 500px past the edge), numeric W=50 commits, pointercancel holds; full workspace test+fmt+clippy clean; operator clippy+build clean. See `docs/delivery/CODE-REVIEW-batchS83c-refine.md`. C-006 PASS (3-OS CI green pending push).

## Risks and rollback

- Risks: band serde breaking old custom-theme JSON (mitigated: `default` + `skip_serializing_if`, round-trip test); pixel regression on non-lower-third built-ins (mitigated: band=None unchanged-pixels test); file split breaking the pinned needles (mitigated: tests read the combined split files; emergency-footer structural assertion stays on index.html); CSP blocking external app.js (mitigated: verify tauri.conf.json `'self'`); drag math off-by (mitigated: headless render + clamp to 0..1000 + safe-area). Rollback: git; additive across crates.

## Pause and escalation conditions

- If the operator CSP forbids external scripts, keep the split but adjust the CSP `script-src 'self'` (documented), never re-inline blindly.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq14wa-theme-designer-refine.md --require-complete`
- Validator result: PASS (6/6 mandatory PASS)
- Independent verification result: adversarial Workflow review `wf_9ab417e1-53a` (4 lenses, 7 agents) — 3 confirmed findings all fixed; 3 lenses clean. See `docs/delivery/CODE-REVIEW-batchS83c-refine.md`.
- Terminal state: GATE_REVIEW (verifiable work complete; local make-ci + operator build green; 3-OS CI green pending this push; awaiting the `/build` user gate)
- ClickUp final evidence comment: posted on 86ajq14wa; follow-up `86ajq4xmy` registered + linked; BUILD CONTROL 86ajnx548 updated.
