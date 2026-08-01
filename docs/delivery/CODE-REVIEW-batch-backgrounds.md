# Code Review — Batch: gradient + image backgrounds (86ajq3225)

- **Scope:** the theme background was a bare solid `Rgba` — a real gap vs. ProPresenter/Pewbeam, where a **gradient** or full-bleed **image** background is a staple design feature (the primary surviving `86ajq3225` scope; fonts already shipped). `Theme.background` becomes an additive **untagged** `Background` enum — `Solid` (byte-identical), a 2-stop linear `Gradient`, or a full-frame `Image` (reusing the built decode foundation). Executed via `/goal` (`TASK-86ajq3225-backgrounds.md`, validator PASS `--require-complete`). Additive — no wire command, no migration.
- **Method:** an adversarial Workflow review `wf_881ab350-9c2` — 3 lenses (engine-gradient-compose · untagged-serde-bounded · frontend-bg-editor) → **per-finding refute-by-default**, each finding checked by two perspective-diverse verifiers (correctness + reproduction). 9 agents. The gradient determinism + the untagged-serde backward-compat were scrutinised hardest.
- **Outcome:** 3 findings raised → **all confirmed (2 MEDIUM + 1 LOW), all fixed.** The **untagged-serde lens found nothing** — an existing solid-background theme is byte-identical and the untagged discrimination is unambiguous (the byte-stability that mattered most).

## What shipped

- **Engine (`selahcue-engine`):** `GradientDirection` (Vertical/Horizontal/DiagonalDown/DiagonalUp) + `Layer::Gradient` + a **deterministic integer** `draw_gradient` (per-pixel `t = pos·1000/span`, `from.lerp(to,t)`); `Rgba::lerp`. The GPU compositor emits only `Fill`, so `Layer::Gradient` is GPU-skipped (like Text/Image/Shape) and `test_parity` is untouched; the CPU raster is the real output.
- **Present (`selahcue-present`):** an untagged `Background { Solid(Rgba), Gradient{from,to,direction}, Image{source: MediaRef} }` (Solid serialises as the bare `{r,g,b,a}`) + `base_color()`. `compose_slide` sets the frame clear to `base_color()` and pushes a full-frame gradient/image layer FIRST (behind band/elements/text) and BEFORE the blank-slide return (so a blank slide shows the designed background). The image reuses the bounded `MediaRef` + size-capped decode cache + missing-media placeholder.
- **Operator (`dist/`):** a background editor — a type selector (Solid/Gradient/Image) + gradient colours/direction + an image path + native picker.

## Findings and dispositions

| # | Lens | Sev | Finding | Verify | Fix |
|---|------|-----|---------|--------|-----|
| 1 | engine | MEDIUM | `draw_gradient` computed its clip + positions in **i32** (`rect.x + rect.w as i32`), violating the file's documented **i64 unvalidated-rect invariant** that the sibling `fill_rect`/`draw_shape` uphold. Not reachable from the shipped full-frame background path, but reachable via the public `render` / a deserialized `Frame` carrying a `Layer::Gradient` with an extreme rect → a debug overflow **panic**, or (for `w > i32::MAX`) a negative cast → early return → the gradient **silently dropped** over the visible frame. | **2/2 REAL** | **Fixed** — the clip + ramp positions are derived in **i64** (mirroring `fill_rect`/`draw_shape`); no raw i32 arithmetic can overflow-panic or mis-clip. Regression `a_gradient_is_bounded_on_extreme_rects_without_panic` (i32::MAX/u32::MAX rects don't panic; a `w > i32::MAX` rect still fills the frame). |
| 2 | frontend | MEDIUM | Switching the background type to **Image** wrote `{source:""}` — a **malformed** `Background` (the host `MediaRef` rejects an empty string), so the whole theme JSON failed to deserialize → the preview silently kept the old frame and Save failed with a generic message. | **2/2 REAL** | **Fixed** — the type selector is **decoupled** from the stored background: switching to Image shows the panel but does NOT commit; the background becomes an image only when a **valid** source is picked/typed (`tdCommitBgImage` rejects empty), so the stored theme is never malformed. Regression: "switching to Image with no source keeps the valid solid bg". |
| 3 | frontend | LOW | The background image picker had **no manual-path fallback** when the native dialog is unavailable (the element picker has one) — the feature would be unreachable on such a build. | 1/2 REAL | **Fixed** — the image panel now has a **manual path input** (type a host-local path) alongside the native picker; the picker falls back to focusing it when no dialog is available. Regression: "the manual path field commits an image source". |

**No HIGH; the untagged-serde/bounded lens found nothing (solid backgrounds byte-identical, discrimination unambiguous, image `MediaRef` bounded).**

## Verification

- **Workspace:** `cargo test --workspace` **504/0** (+9: 4 engine gradient/lerp/extreme-rect, 4 present background, 1 controller); the gradient is deterministic + byte-identical; `test_parity` unchanged (the GPU skips `Layer::Gradient`); an existing solid-background theme + the byte-pinned wire fixtures are unchanged; `--features server` green; fmt/clippy clean (workspace + operator).
- **Operator gates (run on the CI runner):** committed Chrome headless **99/99** (+9: bg type-switch, gradient from/to/direction, image picker + manual path, solid bare-colour, the malformed-source regression) + WebKit smoke **5/5**.
- **3-OS CI:** `<pending — verified by run conclusion>`.
- **Owner on-device QA (optional):** the definitive "a vertical gradient / a photo behind the verse looks right on the real Tauri app" is owner-run; the headless + Rust assertions are the strongest short of the GUI.

## Follow-ups

- Radial / multi-stop (>2) gradients, per-stop positions, gradient on shapes/text; image background fit modes (it FILLS the frame, like the image element); animated/video backgrounds (S8-8); GPU-native gradients. Full `Fit::Paginate` (the other 86ajq3225 sub-scope).
