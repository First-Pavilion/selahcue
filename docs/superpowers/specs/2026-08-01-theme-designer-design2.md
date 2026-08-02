# Theme Designer — Design 2.0 rewrite (spec)

Status: approved direction (owner Q&A 2026-08-01) · Design source: Figma
`SYQn5hFY8YVQKm3c6rw0eJ` node `317:124` ("Theme Designer — Design 2.0") · Token source:
`docs/design/DESIGN-TOKENS.md` §"Design 2.0" (`--sc-*`, pinned by
`selahcue-present/tests/test_tokens.rs`). Sibling of the Operator Console rewrite
(`2026-08-01-operator-console-design2.md`), which explicitly left the Theme Designer
out of scope (byte-stable except the shared token/button restyle). This spec brings it
to the full Design 2.0.

## 1. Objective

Rewrite the Theme Designer webview surface (`selahcue-operator/dist/index.html`
`#surface-theme-designer` + `app.css`, with targeted `app.js` and a small Rust model
slice) to the full Design 2.0 Theme Designer: a topbar with `Duplicate` /
`Preview on output` / gradient `Save theme`; a two-column body of a **canvas zone**
(add-content toolbar + zoom + slide canvas + a bottom **Templates** strip) and a 360px
**inspector zone** re-sectioned into **BACKGROUND** / **TYPOGRAPHY** / **LAYERS**; and a
new **LAYERS** panel with per-layer drag-reorder and a **real** visibility toggle — while
preserving every behavioural invariant, pinned test needle, and JS id hook.

## 2. Hard invariants (must stay green)

`test_tokens.rs` concatenates `index.html`+`app.css`+`app.js` and pins the Theme
Designer needles. The rewrite preserves ALL of them by **re-homing** ids into the new
layout, never renaming:

- **Pinned ids/classes kept**: `id="surface-theme-designer"`, `td-preview`, `td-apply`,
  `td-region`, `td-bg`, `td-color`, `td-size`, `td-align`, `td-lh`, `td-fit`,
  `td-lbl-align`, `td-canvas-box`, `td-sel`, `td-x`, `td-valign`, `class="td-header"`,
  `td-save`, `td-tab-scriptures`, `td-tab-slides`, `td-lock`, `td-font`, `td-later`; the
  saved-theme library (`td-save-row`, `td-save-name`, `td-save-confirm`, `td-save-cancel`,
  `td-theme-name`, `td-theme-del`); and the font picker stays a real ENABLED control
  (the negative pin `!index.contains('<select id="td-font" class="td-later" disabled>')`).
- **Element-ID contract**: every id `app.js` reads (the element inspector `td-el-*`,
  background `td-bg-*`, `td-x/y/w/h`, `td-region-*`, add-bar `data-add`, shape picker,
  context menu `td-ctx`, canvas overlay handles) is preserved. IDs are the API between
  markup and logic.
- **Behaviour preserved**: canvas element add/select/drag/resize, the element inspector
  (opacity, arrange/z-order, shape fill/border/corner, image replace, text controls),
  region layout (align/valign/x/y/w/h/lock), theme background (solid/gradient/image),
  typography (colour/font/weight/letter-spacing/size/line-height/fit), the saved-theme
  library (save/load/delete named themes), and **Apply to audience output** semantics.
- **WKWebView-safe patterns**: no `window.prompt` (inline forms), inline pickers, custom
  context menu (native menu blocked), physical-key handling, `[hidden]` toggled via a
  class where author `display` would otherwise win.
- **Accessibility**: `aria-pressed` on toggles, `role`/`aria-label` on groups, keyboard
  operability of the new LAYERS rows + zoom, `prefers-reduced-motion` honoured, AA
  contrast (the `--sc-*` Design 2.0 palette is audited by `design2_palette_meets_wcag_aa`).
- **Honest-later affordances**: Import/Export theme FILES and the Slides templates tab
  stay visible-but-disabled `td-later`, never faked.

## 3. Layout → surface mapping (Figma 317:124)

Root `#surface-theme-designer`: column flex — **topbar → body(2-col)**.

- **Topbar** (`.td-header`): logo pill + a divider + "Theme Designer" label on the left;
  a right cluster of `Duplicate` (new — clone the current design into a new unsaved theme,
  reusing the existing new-from-current element/theme clone path), `Preview on output`
  (**re-homes** the pinned `#td-apply` "Apply to audience output" button here — same id,
  same handler, same semantics), and a gradient **`#td-save` "Save theme"** (toggles the
  existing inline save-name form).
- **Canvas zone** (`.td-stage`, flex-1, column):
  - **Add-content toolbar** (`.td-addbar`): `Text` (active pill) / `Shape` / `Image`
    (the pinned `data-add` add buttons; Scripture stays the intrinsic Body region, a
    disabled `td-later`); a spacer; `Audience · 1920×1080`; a **zoom control**
    (`− NN% +`, frontend-only — scales the `#td-canvas-box` preview via a CSS transform /
    width, bounded 25–200%, does not persist or change output resolution).
  - **Canvas** (`.td-canvas-box` / `#td-preview` / `.td-overlay` / `#td-sel`): unchanged
    behaviour; restyled frame.
  - **Templates strip** (bottom): the `#td-themes` list re-homed as a horizontal row of
    thumbnail cards (mini-preview + name), with the pinned `#td-tab-scriptures` /
    `#td-tab-slides` tabs kept as the strip header (Scriptures active; Slides a disabled
    `td-later`), the `#td-new-2` "New (from current)" affordance, and the saved-theme
    inline save form (`#td-save-row` …) kept.
- **Inspector zone** (`.td-inspector`, 360px, column) — re-sectioned with divider rules:
  - **Selection header**: a type chip + the selected region/element name + a one-line
    "… · selected on canvas" subtext (driven by the existing selection state).
  - **BACKGROUND**: the existing `#td-bg-type` (Solid/Gradient/Image) restyled to a
    segmented control, gradient/solid/image sub-controls (`td-bg`, `td-bg-from/to/dir`,
    `td-bg-img-*`) as D2 cards.
  - **TYPOGRAPHY**: font (`#td-font`) + weight (`#td-weight`) row; SIZE (`#td-size`) /
    LINE (`#td-lh`) / SPACING (`#td-letter`) fields; text colour (`#td-color`) + the
    align (`#td-align`) L/C/R segmented control; the Fit control (`#td-fit`).
  - The **region/layout** block (`#td-region` Body/Reference, `#td-align`/`#td-valign`,
    `#td-x/y/w/h`, `#td-lock`) and the **element inspector** (`#td-el-*`) are preserved
    and restyled; they show contextually per the existing selection logic.
  - **LAYERS**: the new panel (see §4).

## 4. New behaviour

**Tier 1 — frontend only:**
- **Zoom control** (`− NN% +`): scales the preview box display only; bounded, keyboard-
  operable, `aria-live` percentage; never changes the 1920×1080 output or persisted theme.
- **Duplicate** (topbar): clones the current `tdTheme` into a new unsaved working theme
  (deep-copy of regions + `elements`), selects it, and marks it unsaved — reuses the
  existing new-from-current clone logic; no backend call.
- **LAYERS panel** — a unified, reorderable list of the two text **regions** (Title =
  Reference/Title region, Body) plus every design **element** (shapes/images/text boxes),
  newest/topmost first. Each row: a drag handle `⋮⋮`, a type glyph (T / ▢ / 🖼 / ●), the
  name + `Kind · z`, and a `👁` visibility toggle.
  - **Select**: clicking a row selects that region/element (drives the existing
    `tdSelEl` / region selection state and the inspector).
  - **Reorder**: drag (pointer) + keyboard (Alt+Arrow) maps to the existing element
    **z-order** commands (bring-forward/backward/front/back) — regions keep their fixed
    band relationship to the text; reorder applies to `elements`. Real, no new model.

**Tier 2 — model slice (per-layer visibility, real):**
- Regions already carry `visible: bool` (`RegionStyle.visible`, gated in `compose.rs`).
  Add an **additive** `visible: bool` to each `Element` variant (`Shape` / `Image` /
  `Text`) with `#[serde(default = "default_true", skip_serializing_if = "is_true")]` so
  existing theme JSON stays **byte-identical** (the field is omitted when visible) and all
  serde round-trips stay green.
- `compose.rs`: skip drawing an element when `!visible` (the element contributes no layer),
  exactly as regions do. A hidden layer is absent from the composed frame — never a blank
  rect, never affecting the never-blank guarantee (the background + any visible layer still
  render).
- The `👁` toggle flips `visible` on the selected region/element and re-renders the
  preview + (when applied) the output. Regions → existing `.visible`; elements → the new
  field. Truthful: a hidden layer really does not appear on the audience output.
- Tests: `theme.rs`/`test_theme` serde (default-true, omitted-when-true, round-trip with
  `visible:false`), `compose` (a hidden element/region draws nothing; a visible one draws;
  hiding one of several still renders the rest).

## 5. Decisions locked (owner Q&A 2026-08-01)

1. Scope = full Design 2.0 shell **and** wire new behaviour (not skin-only).
2. Per-layer visibility is **fully wired** with a real additive model field (not a fake or
   honest-later toggle).
3. `Preview on output` re-homes the existing `#td-apply` Apply-to-output button into the
   topbar (confirmed by owner).
4. The Templates strip **keeps** the Scriptures/Slides tabs as its header (preserves the
   pinned `td-tab-*` ids) (confirmed by owner).
5. Import/Export theme files + the Slides tab remain honest disabled `td-later`.

## 6. Verification

- `node --check app.js` (WKWebView-safe; no build step for the webview).
- `cargo test -p selahcue-present` (all operator/theme-designer pins in `test_tokens.rs`
  + the Design 2.0 palette WCAG audit + `compose`/`theme` visibility tests).
- `cargo test -p selahcue-present --test test_theme` (element `visible` serde) and any
  `-p selahcue-gpu` parity if the compose path is touched (Shape/Image/Text are documented
  GPU-skip seams — the CPU raster is the render path, so parity is unaffected).
- `cargo check --manifest-path …/selahcue-operator/Cargo.toml` (the excluded Tauri shell)
  and `python3 scripts/operator_headless.py` (headless behavioural check).
- `make ci` (fmt --check + clippy -D warnings + all suites) — the CI gate.
- Independent multi-lens review workflow: `/code-review` + `/qa-engineer` +
  `/performance-engineer` + `/security-reviewer` (owner-requested), adversarially verified.
- Visual QA of the running Tauri webview is owner-run (no in-repo render harness).

## 7. Non-goals / risks

- **Non-goals**: Import/Export theme files; Slides templates; native file pickers (image
  paths stay host-local text like today); persisting the zoom level; per-screen theme;
  changing the theme wire model beyond the additive `visible` field; touching the Live
  Console / Screens / Settings surfaces.
- **Risks**: (a) breaking a pinned needle or a JS id hook — mitigated by the re-homed-id
  contract + running the full pin suite + `node --check`; (b) the additive `visible` field
  rippling through GPU parity or other theme consumers — mitigated by `skip_serializing_if`
  (byte-identical JSON), tracing every `Element` construction/match site first, and the
  GPU-skip-seam documentation; (c) LAYERS reorder desyncing from z-order — mitigated by
  routing reorder through the existing z-order commands rather than a parallel ordering;
  (d) WKWebView quirks (drag-and-drop, `[hidden]` vs author `display`, no `window.prompt`)
  — follow the existing patterns (inline forms, class-based hiding, pointer-based DnD).
