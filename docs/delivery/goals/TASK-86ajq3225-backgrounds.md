# Goal Contract — TASK-86ajq3225-backgrounds

## Identity

- Goal ID: TASK-86ajq3225-backgrounds
- Parent goal ID: BUILD-selahcue (Presentation & Slides — theme enhancements 86ajq3225)
- Title: GRADIENT + IMAGE backgrounds — the theme background becomes an additive `Background` enum
- Role: backend-engineer (engine gradient primitive + `Background` model + compose) + frontend-engineer (Theme Designer background editor)
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: story `86ajq3225` (Theme engine enhancements R-later, EPIC Presentation & Slides 86ajp07ce) — the backgrounds part; confirm/record at finalization.
- Created: 2026-08-01
- Independent verification required: yes (adversarial review + determinism/parity + backward-compat serde + the committed webview gate)
- Maximum iterations: 12

## Objective

A SelahCue theme is a slide-design template (typography + alignment + background + elements), but the **background is a bare solid `Rgba`** — a real gap vs. ProPresenter/Pewbeam, where a **gradient** or a full-bleed **image** background is a staple "make it look designed" feature. This is the primary surviving `86ajq3225` scope (multi-weight fonts already shipped; pagination is separate). Make `Theme.background` an **additive `Background` enum** — `Solid` (the default, byte-identical), a 2-stop linear **Gradient** (deterministic), or a full-frame **Image** (reusing the built decode foundation). Additive — no wire command, no migration; an existing solid-background theme's JSON is byte-identical.

## Baseline

Verified from code: `Theme.background: Rgba` (theme.rs) is the ONLY `Theme`-level background — it flows through `compose_slide` (compose.rs:455) as `Frame::new(w,h).with_background(theme.background)`, and the CPU raster fills the frame with it (raster.rs:541 `FrameBuffer::filled(w,h,frame.background)`) then draws the layers on top. The **stage confidence monitor** uses a SEPARATE `StageTheme.background: Rgba` (stage.rs:20) and `compose_identify` a separate `background` param — so a `Theme.background` change does NOT touch them (contained ripple). The GPU compositor (compositor.rs:167) uses `frame.background` as the wgpu clear colour and **only emits `Layer::Fill` instances** — it already SKIPS `Text`/`Image`/`Shape`, so a new gradient layer is GPU-skipped consistently; the CPU raster (`live_output()`) is the real audience output path. `Layer` (scene.rs:89) = `Fill`/`Text`/`Image`/`Shape`; `ShapeKind`/`TextAlign` live in `scene` (engine) and are re-exported from present. `Layer::Image` (S8-6) already resolves a bounded `MediaRef` through the size-capped decode cache with a missing-media placeholder. The operator `td-bg` is a single colour picker (`tdTheme.background = tdRgb(hex)`, app.js:1239).

## Scope

### In scope

- **Engine (`selahcue-engine`):** a `GradientDirection` enum (`Vertical`/`Horizontal`/`DiagonalDown`/`DiagonalUp`) in `scene` (like `ShapeKind`); an additive `Layer::Gradient { rect, from: Rgba, to: Rgba, direction }`; a **deterministic** integer `draw_gradient` raster (per-pixel `t = pos·1000/span`, per-channel integer lerp `from + (to−from)·t/1000`) — cross-OS byte-identical (NFR-014); the GPU SKIPS `Layer::Gradient` (a documented seam, like `Shape`/`Text`/`Image`). A small `Rgba::lerp` helper.
- **Present (`selahcue-present`):** an additive **untagged** `Background` enum — `Solid(Rgba)` (serialises as the bare `{r,g,b,a}`, so an existing theme is **byte-identical**), `Gradient(GradientBackground { from, to, direction })`, `Image(ImageBackground { source: MediaRef })`. `Theme.background: Background`; built-ins use `Background::Solid`. `compose_slide` builds the frame per case: Solid → `with_background(c)` (unchanged); Gradient → base `with_background(from)` + a full-frame `Layer::Gradient` pushed FIRST (behind band/elements/text); Image → base black + a full-frame `Layer::Image` pushed FIRST. The background layer is pushed **before** the blank-slide early return, so a blank slide shows the gradient/image. Determinism preserved (a solid theme is byte-identical; parity + pinned fixtures green).
- **Controller (`selahcue-app`):** no new command — a gradient/image-background theme rides the existing `SetCustomTheme`/`SaveTheme` (Theme serde). The background `Image`'s `MediaRef` is bounded/validated exactly as an image ELEMENT's (intrinsic to `MediaRef`); a missing/corrupt source draws the placeholder. Recovery restores the background.
- **Operator (`selahcue-operator/dist/`):** the Theme Designer background control becomes a **background editor** — a **type** selector (Solid / Gradient / Image); Solid → the existing colour picker; Gradient → two colour pickers (from/to) + a direction selector; Image → a host-local path (reuse the native `pick_image`). The live preview reflects each.
- **Tests:** engine (a gradient renders a deterministic ramp — the two ends differ + interpolate; byte-identical across runs), present (a Solid background is **byte-identical** to before = additive; a gradient composes + renders a ramp; an image composes to a full-frame `Layer::Image`; a **blank slide** shows the gradient/image background; determinism), controller (a custom theme with a gradient AND an image background applies + recovers identically), operator headless (the background-type selector switches Solid/Gradient/Image and serialises the right `background` shape).

### Non-goals

- Radial / multi-stop (>2) gradients, per-stop positions, gradient on shapes/text (a 2-stop linear background only). Image fit modes (the background image FILLS the frame — same as the image element). Animated / video backgrounds (S8-8). The `StageTheme` background (unchanged). Full `Fit::Paginate` (separate 86ajq3225 sub-scope).

### Constraints

- Additive: no wire command, no migration; `Background` is an **untagged** enum whose `Solid` serialises as the bare `{r,g,b,a}` → an existing solid-background theme's JSON is **byte-identical** and the pinned theme fixtures stay byte-stable (wire `VERSION`/`target_version` unchanged); the gradient/image sub-structs have disjoint field sets (no untagged ambiguity). **Determinism (NFR-014):** the gradient is pure integer per-pixel → byte-identical cross-OS; the CPU raster is the real render path; the GPU skips `Layer::Gradient` so `test_parity` (SSIM ≥ 0.99, Fill-only) is untouched. **Bounded (no-leak):** the image background reuses the bounded `MediaRef` + size-capped decode cache (decoded pixels never ride the theme JSON). `make ci` + operator `node --check` + the committed Chrome + WebKit gates + 3-OS CI green (verified by conclusion).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Engine: `Layer::Gradient` + `GradientDirection` added; a deterministic gradient renders a ramp (ends differ + interpolate) byte-identical across runs; GPU skips it (`test_parity` unchanged) | `cargo test -p selahcue-engine` | ramp renders; deterministic; parity green | test_raster +3 (`rgba_lerp…`, `a_vertical_gradient…`, `a_horizontal_gradient…`); engine 38/0 incl. test_parity | PASS |
| C-002 | yes | Present: `Background` enum (Solid/Gradient/Image); a **Solid** background is byte-identical to before (additive); a gradient composes + renders a ramp; an image composes to a full-frame `Layer::Image`; a blank slide shows the bg | `cargo test -p selahcue-present` | solid byte-stable; gradient + image compose | test_compose +4 (`a_solid_background_is_byte_identical_to_before`, `each_background_kind_round_trips_untagged`, `a_gradient_background_composes_a_ramp…`, `an_image_background_fills_the_frame…`); present green | PASS |
| C-003 | yes | Controller: a custom theme with a gradient AND an image background applies + recovers identically (bounded `MediaRef`) | `cargo test -p selahcue-app` | applies + recovers | test_controller `a_custom_theme_with_a_gradient_or_image_background_applies_and_recovers` (missing image → deterministic placeholder); app green | PASS |
| C-004 | yes | Operator: the Theme Designer background editor switches Solid/Gradient/Image + serialises the right `background` shape; `node --check` + the committed headless gate assert it | operator `node --check` + headless | editor switches + serialises | `node --check` OK; headless **97/97** (+7 bg: type-switch, gradient from/to/dir, image picker, solid bare-colour) + WebKit 5/5 | PASS |
| C-005 | yes | Gate: make ci + operator gate green; independent adversarial Workflow review, findings fixed; 3-OS CI green (verified by run conclusion) | make-ci + operator + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-backgrounds.md (3 confirmed findings fixed; serde lens clean); CI `30699848062` `completed → success` (operator-Linux `=== 99 checks, 0 FAIL ===` + `WebKit smoke: 5 checks, 0 FAIL`) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `-p selahcue-engine` (gradient ramp + determinism + parity unchanged), `-p selahcue-present` (Solid byte-identical; gradient + image compose; blank-slide bg; determinism), `-p selahcue-app` (gradient + image bg applies + recovers), operator headless (the bg-type editor switches + serialises). Broader: make ci + operator gate + the committed Chrome + WebKit gates + 3-OS CI (verified by conclusion). Independent: adversarial Workflow review (engine gradient-determinism/parity · model/untagged-serde-backward-compat/bounded · frontend-bg-editor).
- Required environment: local + CI.

## Iteration ledger

- Iter 0 (C-001, engine): `GradientDirection { Vertical, Horizontal, DiagonalDown, DiagonalUp }` + `Layer::Gradient { rect, from, to, direction }` (scene.rs); `Rgba::lerp(other, t_permille)` (deterministic per-channel integer, `t` clamped, exact downward ramp); `draw_gradient` raster (per-pixel `t = pos·1000/span` along the direction, `from.lerp(to,t)` blended src-over; clip-stable spans; span-guarded /0; no float). The GPU compositor only emits `Fill` → `Layer::Gradient` is GPU-skipped (test_parity untouched). Tests +3 (lerp integer/clamp/downward; a vertical black→white ramp is monotonic + byte-identical; a horizontal ramp). engine 38/0 incl. test_parity. Result: PASS.
- Iter 1 (C-002, present): an **untagged** `Background { Solid(Rgba), Gradient(GradientBackground{from,to,direction}), Image(ImageBackground{source: MediaRef}) }` + `base_color()`; `Theme.background: Background`; the 3 built-ins use `Background::Solid`. `compose_slide` builds the frame — base `with_background(bg.base_color())` + `push_background` (Solid: none; Gradient: a full-frame `Layer::Gradient`; Image: a full-frame `Layer::Image`) pushed FIRST (behind band/elements/text) and BEFORE the blank-slide return (so a blank slide shows it). `TextAlign`/`GradientDirection`/`Background`/… re-exported. Tests +4: a Solid bg serialises as the bare `{r,g,b,a}` + old bare-colour JSON deserialises → Solid (byte-identical); each kind round-trips untagged; a gradient composes a ramp visible on a blank slide (deterministic); an image bg fills the frame behind the text. present green. Result: PASS.
- Iter 2 (C-003, controller): a gradient AND an image background theme applies via `SetCustomTheme` + recovers identically; a missing image resolves to the deterministic missing-media placeholder (no crash). The image `MediaRef` is bounded/validated intrinsically. Test: `a_custom_theme_with_a_gradient_or_image_background_applies_and_recovers`. Result: PASS.
- Iter 3 (C-004, operator): the Theme Designer background control becomes a **background editor** — a type selector (Solid/Gradient/Image) + sub-controls (Solid: colour; Gradient: from/to colours + direction; Image: a `pick_image` picker). `tdBgType` discriminates by shape; `tdSyncBg` shows + populates the right controls; the type-switch converts the background (carrying the solid colour across); the handlers guard the gradient shape before mutating. `tdSync` now calls `tdSyncBg` (no `tdHex` on a non-colour bg). Evidence: `node --check` OK; committed headless **97/97** (+7 bg) + WebKit 5/5. Result: PASS.
- Gate prep (C-005): full workspace `cargo test` **503/0** + `--features server` green; fmt/clippy clean. Independent adversarial review (`wf_881ab350-9c2`, 3 lenses → per-finding refute-by-default, 9 agents): **3 raised → all confirmed (2 MEDIUM + 1 LOW), all fixed; the untagged-serde/bounded lens found NOTHING** (solid backgrounds byte-identical, discrimination unambiguous, image `MediaRef` bounded). (MEDIUM, engine) `draw_gradient` clipped in i32, breaking the file's documented i64 unvalidated-rect invariant (panic / silent mis-clip on an extreme `Layer::Gradient` rect via the public `render`) → **derive the clip + ramp positions in i64** (mirror `fill_rect`/`draw_shape`) + a regression (`a_gradient_is_bounded_on_extreme_rects_without_panic`). (MEDIUM, frontend) switching the bg type to Image wrote a malformed `{source:""}` (host-rejected → stale preview + unsaveable) → **decouple the type selector from the stored bg** (Image commits only a valid source; the stored theme is never malformed). (LOW, frontend) no manual-path fallback for the bg image → **a manual path input** + a picker fallback. Re-verified: headless **99/99** + WebKit 5/5; fmt/clippy clean. See `docs/delivery/CODE-REVIEW-batch-backgrounds.md`. 3-OS CI pending (verified by conclusion).

## Risks and rollback

- Risks: untagged-serde AMBIGUITY (mitigated: disjoint field sets — `{r,g,b,a}` vs `{from,to,direction}` vs `{source}`; Solid tried first so an existing solid bg stays byte-identical; a round-trip + byte-stability test). Determinism/parity drift (mitigated: the gradient is pure integer per-pixel; the GPU skips `Layer::Gradient` so `test_parity` is Fill-only + untouched; a solid theme is byte-identical). An unbounded image background (mitigated: reuses the bounded `MediaRef` + size-capped decode cache + placeholder). Rollback: git; additive across engine/present/app/operator; no wire/migration change.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq3225-backgrounds.md --require-complete`
- Validator result: PASS (5/5 mandatory criteria PASS)
- Independent verification result: adversarial review `wf_881ab350-9c2` (3 lenses → per-finding refute-by-default, 9 agents) — 3 raised, all confirmed (2 MEDIUM + 1 LOW) fixed; the untagged-serde/bounded lens found nothing; + the committed Chrome 99/99 + WebKit 5/5 CI gates run on the runner.
- Terminal state: GATE_REVIEW (verifiable work complete; paused for the `/build` user gate).
- ClickUp final evidence comment: POSTED (comment `90130299953313`) — STORY `86ajq3225` (umbrella: backgrounds/fonts/pagination) set to **in progress** with the backgrounds-increment evidence; backgrounds + fonts done, **pagination remains** (a candidate to split). BUILD CONTROL `86ajnx548` gate comment posted.
