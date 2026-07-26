# Code Review — Batch S8-3c refine 2 (shrink-to-fit width fix + Figma 204-124 honest-shell alignment)

- **Scope:** story `86ajq14wa` refine 2 (owner): **(1)** fix shrink-to-fit — long scriptures still clipped; **(2)** align the Theme Designer to Figma 204-124 (header, Scriptures/Slides tabs, Add-content, CANVAS, 9-point alignment grid, Lock-aspect, Ref-gap, Font/Weight/Letter) with **honest "later" affordances** (owner decision) for the deferred features, **keeping the 3 built-ins** (owner). Executed via `/goal` (`TASK-86ajq14wa-theme-designer-refine2.md`).
- **Method:** adversarial Workflow review (`wf_01c8ca19-a5a`, 3 lenses → per-finding adversarial verify, 5 agents). Lenses: shrink-fit-correctness · design-honesty/no-fake-controls · a11y/regression. No self-approval.
- **Outcome:** **2 raised → 2 CONFIRMED → both fixed; 0 refuted-as-noise.** 0 HIGH/MED; 2 LOW (both a11y). The shrink-fit and design-honesty lenses found **nothing real**.

## What shipped

**Shrink-to-fit now fits WIDTH, not only height (the owner bug).** Root cause: `layout_region` sized the cell so all lines fit `rect.h` (vertical) but never checked line **width**, and `draw_text` shapes each line unwrapped (`set_size(fs, None, None)`) — so a line wider than the region clipped on the right. Fix: added `raster::measure_line_width(text, px)` (mirrors `draw_text`'s font sizing) and, in `layout_region`, after the vertical-fit cell, a bounded loop (≤4 passes) scales the cell by `rect.w / max_line_width` (with a `scaled>=cell → cell-1` progress guard) so the widest line also fits. A long 2 Corinthians verse now renders fully — verified in a render (`scratchpad/long.png`) and `shrink_to_fit_scales_a_wide_line_to_fit_the_region_width` (which also asserts the line *would* have overflowed at the design size, proving the shrink was necessary). Shrinking for width only makes more vertical room, so the line-count guarantee holds.

**Theme Designer aligned to Figma 204-124 (honest shell).** Added: the **header** (`New` wired · `Import`/`Export`/`Save changes` → honest aria-live status routing to the library story `86ajq4xmy`, never fake success); **Scriptures/Slides tabs** (Scriptures live; Slides an honest not-yet placeholder); the **Add-content** toolbar (Text/Scripture/Shape/Image → honest status); the **CANVAS** label; the **9-point alignment icon grid** (functional — the icon buttons keep `data-a`/`data-v`, so they still drive `align_h`/`align_v` with `aria-pressed`); **Lock-aspect** (functional — a locked resize preserves the region's w:h ratio, verified 2.00→2.00 locked vs 0.86 unlocked); Ref-gap + Font/Weight/Letter present but **`disabled` + honestly labelled** ("arrives with 86ajq3225"); Fit reordered to Shrink/Paginate/Clip. Deferred features are visibly dimmed (`.td-later`), not fake. All prior functional wiring (drag/resize/preview/apply/host-builtins/emergency footer) intact.

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | a11y | LOW | **`Save changes` failed WCAG-AA contrast.** `#td-save` used `golive` (white-on-green) **+** `.td-later{opacity:.55}`, compositing to ~3.3:1 (< 4.5:1). It's an *enabled* control (fires an aria-live status), so the disabled-control exemption doesn't apply; the token AA test measures full opacity and missed it. | **Fixed:** dropped `golive` from `#td-save` — it's a deferred affordance, not the primary action (Apply stays green). The dimmed label is now grey-on-panel (~5.2:1, like Import/Export) and passes AA, and the real primary Apply is visually distinct. |
| 2 | a11y | LOW | **Slides tab was an incomplete ARIA tabs widget.** `role=tablist`/`role=tab` with **no** `tabpanel`, no `aria-controls`, and the not-available Slides tab had no `aria-disabled` — announced as a working two-panel widget that has no panels. | **Fixed:** wrapped the templates in `#td-panel role="tabpanel" aria-labelledby="td-tab-scriptures"`, added `aria-controls="td-panel"` to the Scriptures tab, and `aria-disabled="true"` to the Slides tab (a truthful "not yet available" placeholder; its click still gives the honest status). |

### Refuted (verified NOT real — 2 lenses clean)

- **shrink-fit-correctness** — the loop converges (each pass scales toward `rect.w`; the `cell-1` guard forces progress; exits ≤4 passes or at `cell≤1` for a degenerate single ultra-long token, no underflow since the `cell<=1` break precedes `cell-1`); the vertical guarantee holds (smaller cell ⇒ more room); `measure_line_width` is deterministic (bundled shaper) and its `tick()` is the same bounded no-leak counter `draw_text` uses; Clip/Paginate untouched.
- **design-honesty/no-fake-controls** — every deferred affordance sets a truthful "arrives with <story>" status and mutates nothing; the disabled fields carry the real `disabled` attribute; the 9-point grid + Fit + Lock-aspect are genuinely functional (verified by interaction).

## Verification

- Full workspace `cargo test --all-features`, `fmt --check`, `clippy --all-targets` **clean**; operator crate `cargo clippy` + `cargo build` **clean**.
- Backend: `shrink_to_fit_scales_a_wide_line_to_fit_the_region_width` + the existing shrink/compose/render suites; a rendered long verse (`scratchpad/long.png`) — no right-edge clip.
- Frontend: headless render of the aligned surface (`scratchpad/shot-td-aligned.png`) — matches the Figma shell; a headless **interaction** test proving Lock-aspect preserves the ratio (2.00 locked) and releases it unlocked (0.86); `node --check app.js`; tags balanced; `test_tokens` (split-aware pins + the new shell needles) + `test_keymap` green.
- Deferred with seams (honest "later" affordances → their stories): saved-theme library / Save-changes / Import-Export (`86ajq4xmy`), multi-font family/weight/letter-spacing + reference-gap (`86ajq3225`), Slides (non-scripture) templates, on-canvas Add-content.
- **3-OS CI:** pending this push.
