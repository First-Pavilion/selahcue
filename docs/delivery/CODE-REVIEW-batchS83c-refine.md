# Code Review — Batch S8-3c refine (Theme Designer: full-center canvas · drag/resize · lower-third band · file split)

- **Scope:** story `86ajq14wa` refine (owner + Figma 204-124/208-137): (1) the preview takes the **full center**; (2) **on-canvas resize/reposition** of text regions (drag handles + numeric X/Y/W/H); (4) the **lower-third** becomes a **full-width band** (semi-transparent fill + amber border) per 208-137; (5) split the single `dist/index.html` into **index.html + app.css + app.js** with no runtime overhead. Point (3) "edit/save default templates" → registered as a **follow-up story** (`86ajq4xmy`). Executed via `/goal` (`TASK-86ajq14wa-theme-designer-refine.md`).
- **Method:** adversarial Workflow review (`wf_9ab417e1-53a`, 4 independent lenses → per-finding adversarial verify, 7 agents). Lenses: band-engine/serde-compat · lower-third-fidelity · canvas-drag-correctness/a11y · file-split-integrity/host-builtins. No self-approval.
- **Outcome:** **3 raised → 3 CONFIRMED → all 3 fixed; 0 refuted-away-as-noise (3 lenses found nothing real).** 0 HIGH; 2 MEDIUM + 1 LOW, all in the drag/resize interaction.

## What shipped

**Theme-engine band (additive).** `Theme.band: Option<Band>` (`Band{ rect permille, fill, border, border_permille }`, `#[serde(default, skip_serializing_if)]`). `compose_slide` draws the band **fill + 4 border edge rects** (via `Layer::Fill`, src-over alpha) before the text — full-screen themes keep `band: None` (pixels unchanged). The **lower-third** is redesigned to a full-width bottom band (x 3%–97%) with a translucent fill + amber border, reference (amber) above body (white) inside the band — matching 208-137, and the shrink-to-fit guarantee is preserved.

**Full-center Theme Designer (Figma 204-124).** The surface is restructured to left **Templates** · a **large center canvas** (16:9, with a 5% safe-area guide) · right inspector split into **LAYOUT** (region · X/Y/W/H% · horizontal + vertical alignment) and **TYPE** (background/text colour · size · line-height · Fit). The selected region shows an **8-handle selection box** overlaid on the canvas; **drag** moves it, **handles** resize it, and **numeric X/Y/W/H** edit it — all clamped to the frame and re-previewed live (host render). It is **keyboard-operable** (focus + arrows nudge, Shift+arrows resize). Built-ins are now **sourced from the host** (`builtin_themes`) so the editor previews/applies the real `theme.rs` themes (incl. the lower-third band) — the hand-mirrored JS copy that would drift is gone.

**File split.** `dist/index.html` (structure) + `dist/app.css` (styles) + `dist/app.js` (logic), served locally from `frontendDist: "dist"` (csp `null`, relative paths). No runtime overhead; `app.js` is now `node --check`-able directly. The pin tests read the **combined** sources; the emergency-footer-after-`</main>` DOM invariant stays checked on `index.html`; `test_keymap` reads `app.js`.

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | canvas-drag | **MED** | **Resize jumped the anchored edge.** `tdSetRect` applied a *move-style* clamp (size then position), but W/N/corner handles change both x and w — so at the 20‰ minimum or the frame edge the **opposite (anchored) edge jumped** instead of the dragged edge stopping. | **Fixed:** resize is now **edge-based** — each handle moves only its own edge, clamped to `[oppositeEdge ± MIN, frame]`; the anchored edge is preserved. Verified: east-handle dragged 500px past the frame → X stays 10%, W clamps to 90% (no jump). Keyboard resize anchored the same way. |
| 2 | canvas-drag | **MED** | **Numeric X/Y/W/H couldn't take multi-digit input.** The `oninput` handler called `tdSyncLayout()` which rewrote the focused field to its normalized `.toFixed(1)` value on every keystroke, so "50" collapsed back to "5.0". | **Fixed:** numeric fields commit on **`change`** (blur/Enter), not per-keystroke; `tdSyncLayout` **skips the focused field**; W/H clamp keeps the origin anchored. Verified: typing W=50 sets W=50% with X unchanged. |
| 3 | canvas-drag | LOW | **No `pointercancel` handler.** A cancelled pointer (touch palm-reject / OS gesture) releases capture without firing `pointerup`, leaving `tdDrag` set — a later hover would move the region with no button held. | **Fixed:** `pointercancel → tdPointerUp` clears `tdDrag`. Verified: cancel + no-button hover leaves the rect unchanged. |

### Refuted (verified NOT real — 3 lenses found nothing)

- **band-engine/serde-compat** — the `Option<Band>` is additive (`default` + `skip_serializing_if`); old custom-theme JSON without `band` → `None` (tested); `band_layers` border math clamps `bt.min(w).min(h)` and only draws when `border_permille>0 && a>0`; classic/high-contrast are `band: None` (pixels unchanged; the existing render suites pass).
- **lower-third-fidelity** — the band is genuinely full-width (the render test asserts amber at both the far-left AND far-right edges); title/body sit inside the band bounds; shrink-to-fit is preserved.
- **file-split-integrity/host-builtins** — `frontendDist: "dist"` bundles all three files; no dangling reference to the removed `TD_REG`/`TD_BUILTINS`; `builtin_themes` returns `[{name, theme}]` (the serialized `Theme`, incl. the band) exactly as the JS consumes; the pin tests cover the moved needles + the structural invariants.

## Verification

- Full workspace `cargo test --all-features`, `fmt --check`, `clippy --all-targets` **clean**; operator crate `cargo clippy` + `cargo build` **clean**.
- Backend: `test_compose` band serde-additive + full-width-band render; the present render suites (classic/high-contrast unchanged); a rendered lower-third (`scratchpad/lt.png`) matches 208-137.
- Frontend: headless render of the full-center Theme Designer (`scratchpad/shot-td-refine.png`) — templates + big canvas + 8-handle selection box + LAYOUT/TYPE inspector + emergency footer; a headless **interaction** test proving keyboard nudge, pointer drag (with clamp), the anchored resize, multi-digit numeric entry, and pointercancel; `node --check app.js`; tags balanced; `test_tokens` (split-aware pins) + `test_keymap` (app.js) green.
- Deferred with seams (noted / follow-ups): edit + save default templates / saved-theme library (**`86ajq4xmy`**), Add-content (Text/Scripture/Shape/Image), Import/Export, font family/weight/letter-spacing, per-screen assignment (`86ajq321k`), true NDI alpha-keying, rounded band corners, on-canvas band drag.
- **3-OS CI:** pending this push.
