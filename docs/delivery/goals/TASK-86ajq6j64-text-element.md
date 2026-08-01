# Goal Contract — TASK-86ajq6j64-text-element

## Identity

- Goal ID: TASK-86ajq6j64-text-element
- Parent goal ID: BUILD-selahcue (Canvas Editing epic 86ajq6j01)
- Title: The TEXT element — a free text box on the slide canvas (the last missing `Element` kind)
- Role: backend-engineer (engine `Element::Text` + compose) + frontend-engineer (Theme Designer text authoring)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: story `86ajq6j64` (Canvas Editing epic 86ajq6j01) — confirm/record at finalization (MCP was rate-limited earlier; recovering).
- Created: 2026-08-01
- Independent verification required: yes (adversarial review + determinism/parity + the committed webview gate)
- Maximum iterations: 12

## Objective

The Canvas Editing epic ships an element model with **Shape** + **Image** kinds and a full kind-agnostic on-canvas authoring layer (add/select/drag/resize/arrange/inspector/context-menu/keyboard), but the **`Text` element — a free text box — is the one missing kind**: `Element` has no `Text` variant (the seam is promised at `theme.rs:130-131`) and the Theme Designer's "Text" add button is present but **disabled**. Text is the most common slide element, so this is a glaring hole in the owner's ProPresenter-style "add any element" vision. Add `Element::Text` end-to-end: an engine variant that renders wrapped, auto-fit text in a per-mille rect (reusing the EXISTING region text path), and the Theme Designer authoring for it. Additive — no wire command, no migration.

## Baseline

Verified from code: `Element` is an internally-tagged `#[serde(tag="kind", snake_case)]` enum with `Shape` (theme.rs:141) + `Image` (theme.rs:174) — NO `Text` (the seam noted theme.rs:130-131). `Element::z()` (theme.rs:213) matches only Shape/Image. `element_layers` (compose.rs:270) maps Shape→`Layer::Fill`/`Layer::Shape`, Image→`Layer::Image`; `compose_slide` (compose.rs:397) z-sorts elements + renders `z<0` behind the text, `z>=0` in front. `autofit_layers` (compose.rs:37) is the reusable text-layout engine (lines + rect + typography → `Vec<Layer::Text>`; word-wrap + shrink-to-fit + letter-spacing + weight, bounded by `MAX_WRAP_WORDS`/line-cap) — used by the title/body regions via `layout_region` (compose.rs:209). `RegionStyle` (theme.rs) carries rect + align_h/align_v + size_permille + line_height_permille + color + fit. The raster already renders `Layer::Text`; the GPU already SKIPS `Layer::Text` (documented seam, compose.rs comment) → the parity oracle (`test_parity`, SSIM ≥ 0.99) is Fill-only and untouched. `MAX_ELEMENTS = 64` (theme.rs:209) is enforced at `set_custom_theme` (controller.rs:602), `save_theme` (controller.rs:638), + `load_saved_themes` (controller.rs:694). The Theme Designer add buttons are `index.html:229` (`data-add="text"` disabled); `app.js:1617` skips a disabled add button; `tdAddElement`/`tdAddDefaults` (app.js:1508-1532) build a default element; the element inspector + the kind-agnostic drag/resize/arrange layer already work for Shape/Image.

## Scope

### In scope

- **Engine (`selahcue-present/theme.rs`):** an additive `Element::Text` variant carrying the per-mille rect + `text: String` + `color` + `size_permille` + `line_height_permille` + `align_h` + `align_v` + `fit` + `opacity` + `z`, with optional typography (`font`/`weight`/`letter_spacing_permille`) via the EXISTING `skip_serializing_if` helpers (so a Text element's JSON is compact + a NO-Text theme's JSON is byte-identical — the `elements` vec skip-if-empty is unchanged). `Element::z()` gains a `Text` arm. A **`MAX_TEXT_ELEMENT_LEN`** cap on the text content (no-leak) + a `Theme::elements_bounded()` helper (count ≤ MAX_ELEMENTS **and** each Text element ≤ MAX_TEXT_ELEMENT_LEN).
- **Compose (`selahcue-present/compose.rs`):** an `element_layers` `Text` arm — per-mille → pixel rect (same mapping as Shape/Image), the whole-element `opacity` folded into the text-colour alpha (0 → no layers), then `autofit_layers(text.lines(), rect, cell, line_height, align_h, align_v, color, fit, font, weight, letter_spacing)` → `Vec<Layer::Text>`. z-ordering is the existing `compose_slide` sort (no change). Deterministic (integer per-mille + the existing text layout); a no-Text theme is byte-identical (parity + pinned fixtures green).
- **Controller (`selahcue-app`):** the 3 element-bound validation sites use `Theme::elements_bounded()` (so an over-long Text element is rejected at `set_custom_theme`/`save_theme`/`load_saved_themes`, like the count cap). Recovery restores a Text element with the content re-staged.
- **Operator (`selahcue-operator/dist/`):** the Theme Designer **"Text" add button is enabled** → adds a default Text element (a placeholder string, sensible rect/size/color); the element **inspector** gains a text-content control (a text input/area) + size/color/align, shown when a Text element is selected. The existing add/select/drag/resize/arrange/context-menu/keyboard layer works unchanged for it.
- **Tests:** engine (a Text element rasterizes wrapped/auto-fit text in its rect; a NO-Text theme is byte-identical = additive serde; opacity folds into alpha; z<0 behind / z>=0 in front of the slide text; determinism byte-identical; over-long text is out-of-bounds; empty text draws nothing), compose (`Text` → `Layer::Text` at the right rect; z-order), controller (a custom theme with a Text element applies + recovers; an over-cap Text element is rejected), operator headless (the Text add button is enabled + adds a Text element; the inspector edits the content).

### Non-goals

- Rich text (per-run styling, mixed fonts/colours within one box), rotation, vertical text, text-on-path. Multi-select/group, undo/redo (canvas-interaction extensions, R2). New shape kinds, gradients. These are unchanged seams.

### Constraints

- Additive: no wire command, no migration; `Element` is an additive tagged-enum variant; a Text element's optional typography + the theme's `elements` vec use `skip_serializing_if` → a **no-Text theme's JSON is byte-identical** and the pinned theme fixtures stay byte-stable (`target_version`/wire `VERSION` unchanged). **Determinism (NFR-014):** the CPU raster is the real render path; a Text element is deterministic integer layout → byte-identical cross-OS; `test_parity` (SSIM ≥ 0.99) is Fill-only + unchanged (the GPU skips `Layer::Text`). **Bounded (no-leak):** `MAX_ELEMENTS` (count) + `MAX_TEXT_ELEMENT_LEN` (per Text element) enforced at every theme ingress. `make ci` + operator `node --check` + the committed Chrome + WebKit gates + 3-OS CI green (verified by conclusion).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Engine: `Element::Text` added (additive — a no-Text theme's JSON byte-identical); it rasterizes wrapped/auto-fit text in its rect with opacity folded into alpha + z-order; deterministic; bounded (`MAX_TEXT_ELEMENT_LEN`); `test_parity` unchanged | `cargo test -p selahcue-present` (+ `-p selahcue-engine`) | text renders; byte-stable; parity green | test_compose +6 (`a_text_element_renders_its_own_text`, `…opacity_folds…`, `…participates_in_z_ordering`, `…is_deterministic`, `…round_trips_serde…`, `…content_is_bounded`); present 36/0 + engine 21/0 incl. test_parity | PASS |
| C-002 | yes | Controller: a custom theme with a Text element applies + recovers; an over-cap Text element is rejected at every ingress (`elements_bounded`) | `cargo test -p selahcue-app` | applies + recovers; over-cap rejected | test_controller `a_custom_theme_with_a_text_element_applies_recovers_and_is_bounded` (set_custom_theme + save_theme reject over-cap); app green | PASS |
| C-003 | yes | Operator: the Theme Designer "Text" add button is enabled + adds a Text element; the inspector edits its content; `node --check` + the committed headless gate assert add + edit | operator `node --check` + headless | text element added + editable | `node --check` OK; operator build/fmt/clippy clean; headless **89/89** (+8 text) + WebKit 5/5 | PASS |
| C-004 | yes | Gate: make ci + operator gate green; independent adversarial Workflow review, findings fixed; 3-OS CI green (verified by run conclusion) | make-ci + operator + Workflow + CI | all green; review fixed | CODE-REVIEW doc; CI run | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `-p selahcue-present` (Text renders wrapped/auto-fit; no-Text byte-identical; opacity; z-order; determinism; bounded; empty draws nothing), `-p selahcue-engine` (`test_parity` unchanged — GPU skips Layer::Text), `-p selahcue-app` (applies + recovers; over-cap rejected), operator headless (the Text add button enabled + adds; the inspector edits content). Broader: make ci + operator gate + the committed Chrome + WebKit gates + 3-OS CI (verified by conclusion). Independent: adversarial Workflow review (engine text-layout/determinism/parity · model/serde-additive/bounded · frontend-text-authoring).
- Required environment: local + CI.

## Iteration ledger

- Iter 0 (C-001, engine): `Element::Text { rect, text, color, size_permille, line_height_permille, align_h, align_v, fit, opacity, z, font?, weight?, letter_spacing_permille? }` (additive tagged-enum variant; optional typography `skip_serializing_if`). `Element::z()`/`within_bounds()` arms; `Theme::elements_bounded()` (count ≤ MAX_ELEMENTS AND each Text ≤ `MAX_TEXT_ELEMENT_LEN=2000`). Compose: an `element_layers` `Text` arm → per-mille rect + opacity folded into the text-colour alpha (0 → no layers) → `autofit_layers(text.lines(), rect, cell, lh, align_h, align_v, color, fit, font, weight, ls)` (the SAME title/body path); z via the existing `compose_slide` sort. **Raster fix:** `draw_text` now folds the layer text-colour ALPHA into the glyph coverage (`(c.a()*color.a + 127)/255`) so the Text element's opacity works — **byte-IDENTICAL for opaque text** (`(c*255+127)/255 == c` exactly for all c, proven + every existing test green), dimming only a translucent element; the GPU skips `Layer::Text` so `test_parity` is untouched. `TextAlign` re-exported from `selahcue_present`. Tests +6 (renders, opacity folds, z-order, determinism, serde round-trip + skip-default, bounded). present 36/0, engine 21/0 (incl. parity). Result: PASS.
- Iter 1 (C-002, controller): the 3 element-bound ingress sites (`set_custom_theme`, `save_theme`, the startup `load_saved_themes` filter) use `Theme::elements_bounded()` — an over-cap Text box is rejected everywhere (no unbounded design growth). Test: `a_custom_theme_with_a_text_element_applies_recovers_and_is_bounded` (applies + recovers byte-identical; over-cap rejected at set_custom_theme + save_theme). Result: PASS.
- Iter 2 (C-003, operator): `index.html` — the **Text add button enabled** + a `td-el-text` inspector block (content textarea, colour, size, alignment). `app.js` — `tdAddDefaults` text branch (a default "Text" box, opaque white, sensible rect/size/align), the add-button `text` handler → `tdAddElement("text")`, `tdSyncEl` kind detection (text/shape/image) + the text inspector binding + hidden toggles + the "Text" head/aria label (`tdElLabel` helper fixes the select/paste announcements), and the `td-el-text-*` control handlers (content/colour/size/align → `tdActive()` + preview). The kind-agnostic add/select/drag/resize/arrange/copy-paste/delete layer works unchanged for it. Evidence: `node --check` OK; operator build/fmt/clippy clean; committed headless **89/89** (+8: button enabled, adds a text element, inspector shows + hides shape/image, head names Text, edits content, size%→permille, alignment) + WebKit 5/5. Result: PASS.
- Gate prep (C-004): full workspace `cargo test` **495/0** + `--features server` green; fmt/clippy clean (workspace + operator). Independent adversarial review (`wf_027265e3-52b`, 3 lenses → per-finding refute-by-default, 7 agents): **2 raised → both confirmed (1 MEDIUM + 1 LOW), both fixed; engine + serde/bounded lenses found NOTHING** (the risky raster alpha-fold is byte-identical for opaque text; the additive/bounded model is sound). (MEDIUM+LOW, same root, frontend) the content textarea had no client-side length bound → an over-cap Text box made Apply falsely report success + Save misdiagnose → **fixed at the root**: `maxlength="2000"` + a slice-to-cap content handler, so the UI can never author an over-cap element. Headless +1 (over-cap paste truncated). Re-verified: headless **90/90** + WebKit 5/5. See `docs/delivery/CODE-REVIEW-batch-text-element.md`. 3-OS CI pending (verified by conclusion). Follow-up recorded: Apply-handler should verify host acceptance (a pre-existing gap, not element-specific).

## Risks and rollback

- Risks: an unbounded Text string (mitigated: `MAX_TEXT_ELEMENT_LEN` + `elements_bounded` at every ingress + a bounded test; `autofit_layers` already bounds the render via `MAX_WRAP_WORDS`/line-cap). Determinism/parity drift (mitigated: the CPU raster is a pure integer function reusing the proven title/body text path; the GPU skips `Layer::Text` so `test_parity` is untouched; a no-Text theme is byte-identical). Serde drift (mitigated: additive tagged-enum variant + `skip_serializing_if` typography; pinned fixtures byte-stable). Rollback: git; additive across present/app/operator; no wire/migration change.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq6j64-text-element.md --require-complete`
- Validator result: (pending)
- Independent verification result: (pending)
- Terminal state: (pending)
- ClickUp final evidence comment: (pending — story 86ajq6j64, Canvas Editing epic 86ajq6j01)
