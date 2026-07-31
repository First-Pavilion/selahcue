# Goal Contract — TASK-86ajtwq24-shape-kinds

## Identity

- Goal ID: TASK-86ajtwq24-shape-kinds
- Parent goal ID: EPIC-86ajq6j01-canvas-editing
- Title: More shape kinds — ellipse / rounded-rectangle / triangle (+ a shape picker)
- Role: backend-engineer (engine raster + model + compose) + frontend-engineer (picker)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajtwq24
- Created: 2026-07-31
- Independent verification required: yes
- Maximum iterations: 14

## Objective

Owner refine #2 — extend `Element::Shape` from a filled **rectangle** to multiple **kinds**: rectangle (existing), **ellipse**, **rounded-rectangle**, **triangle** — each an area fill with an optional border/outline, at the per-mille rect + opacity + z; add a **shape picker** to the operator's Add Shape. Deterministic (NFR-014), bounded, backward-compatible (existing rectangle shapes render + serialize **byte-identically**), no wire/migration change, GPU-skip-consistent (like `Text`/`Image`). Line/star/polygon are noted seams.

## Baseline

Verified from code:
- `present::theme::Element::Shape { x/y/w/h_permille, fill, border, border_permille, opacity, z }` (theme.rs:141-154) — the enum is `#[serde(tag = "kind")]` (tag = `"shape"`/`"image"`), so the geometry sub-kind CANNOT reuse `kind`; a new field (`variant`) is needed. `compose::element_layers` (compose.rs:238-291) maps a Shape to `Layer::Fill` rects (fill + 4 border edges).
- `scene::Layer = Fill{rect,color} | Text{…} | Image{…}` (scene.rs), derives **`Eq`** (a new variant's fields must be `Eq`). `raster::render` (raster.rs:357-382) matches each `Layer`; `fill_rect` (integer clip + `blend` src-over) is the fill primitive; the CPU raster is a **pure integer function → byte-identical cross-OS** (NFR-014). The **GPU** compositor SKIPS non-Fill layers (`Text`/`Image`), and `test_parity` (SSIM ≥ 0.99) uses **Fill-only** `scenes()`.
- `Theme.elements` rides the theme JSON (`SetCustomTheme`/`SaveTheme`), bounded `MAX_ELEMENTS = 64`; no wire/migration for element internals.

**Key design:** add `variant: ShapeKind` (+ `corner_permille` for rounded) to `Element::Shape` via `#[serde(default, skip_serializing_if)]` so a **Rect** shape omits both fields → **byte-stable**. `ShapeKind { Rect, Ellipse, RoundedRect, Triangle }` lives in the **engine** (`scene.rs`, so both `Layer::Shape` and `Element::Shape` share it). Compose routes **Rect → `Layer::Fill`** (UNCHANGED) and the others → a new additive **`Layer::Shape { rect, kind, fill, border, border_px, corner_px }`** that `raster::draw_shape` fills per-kind with deterministic integer per-pixel tests (ellipse inside-test; rounded-rect clamp-SDF; triangle half-width test) + an inset-ring border. The GPU SKIPS `Layer::Shape` (documented seam). Opacity is pre-multiplied into fill/border alpha in compose as today.

## Scope

### In scope

- **Engine (`scene.rs`):** `ShapeKind` enum (Copy, `Default = Rect`, snake_case serde) + `is_rect()`; additive `Layer::Shape { rect: Rect, kind: ShapeKind, fill: Rgba, border: Rgba, border_px: u32, corner_px: u32 }` (Eq-preserving). Existing `Fill`/`Text`/`Image` fixtures byte-stable.
- **Engine (`raster.rs`):** a `Layer::Shape` arm → `draw_shape` — per-pixel over the CLIPPED rect (bounded, no panic on extreme rects), fill where inside the shape, border where inside the outer shape but outside the inset (border_px) shape; integer arithmetic (i64, deterministic). Ellipse / rounded-rect / triangle geometry.
- **Model (`theme.rs`):** `Element::Shape` gains `#[serde(default, skip_serializing_if = "ShapeKind::is_rect")] variant: ShapeKind` + `#[serde(default, skip_serializing_if)] corner_permille: u16`; reuse the engine `ShapeKind`. `Element` stays `Clone`.
- **Compose (`compose.rs`):** `element_layers` Shape arm — `variant.is_rect()` → the existing `Layer::Fill` logic (UNCHANGED); else → one `Layer::Shape` (per-mille→pixel rect, opacity applied to fill/border, `border_px`, `corner_px = min(w,h)·corner_permille/1000` clamped to half the min side).
- **Re-exports:** `ShapeKind` from `selahcue-engine` + `selahcue-present`.
- **Frontend (`selahcue-operator/dist/`):** Add Shape → a small **shape picker** (Rectangle / Ellipse / Rounded / Triangle) → an `Element::Shape` with the chosen `variant` (rounded gets a sensible default `corner_permille`); the shape inspector gains a **corner-radius** control (shown for rounded).
- **Tests:** engine (each kind rasterizes correctly — an ellipse is round NOT square, rounded corners are cut, a triangle; a **Rect shape is byte-identical to before** = backward-compat; determinism; bounded/no-panic on extreme rects; additive serde), compose (Rect→Fill unchanged, others→Shape), controller (an ellipse theme applies+recovers), operator headless (the picker adds the chosen kind).

### Non-goals (seams)

- **Line / star / arrow / polygon** kinds; arbitrary rotation; per-shape gradients (R2). **GPU-native** shapes (the GPU skips `Layer::Shape` — later, with GPU glyphs/images). True uniform-inset borders (the inset-ring approximation is used).

### Constraints

- Determinism (NFR-014): every shape fill is a pure integer function → byte-identical cross-OS; a RECT shape + a no-shape scene render byte-identical to today (parity + pinned tests guard). Additive serde (Rect byte-stable) + **no wire/migration change** (VERSION/`target_version` unchanged, pinned fixtures byte-stable). Bounded (per-pixel over the clipped rect; extreme rects clip, never panic; `MAX_ELEMENTS`). `Eq` preserved. GPU skips `Layer::Shape` → parity set unchanged. fmt/clippy/deny clean; 3-OS CI.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Model: `ShapeKind` (engine) + `Layer::Shape` (additive, Eq); `Element::Shape` gains `variant`/`corner_permille` (`serde(default, skip_if)`); a Rect shape's JSON is byte-identical to before; workspace + operator compile | `cargo build --workspace` + operator; `cargo test -p selahcue-engine` | compiles; additive; Rect byte-stable | test_scene | PASS |
| C-002 | yes | Raster: `draw_shape` renders ellipse (round, not the bounding square), rounded-rect (corners cut), triangle — each fill + border, opacity-blended, deterministic (byte-identical) + bounded (extreme rects clip, no panic); a `Layer::Fill` render is unchanged | `cargo test -p selahcue-engine` | shapes render correctly + deterministically; no panic | test_raster | PASS |
| C-003 | yes | Compose + persistence: `Element::Shape{Ellipse/Rounded/Triangle}` → `Layer::Shape`; `Rect` → `Layer::Fill` (unchanged); rides the theme JSON (NO migration, VERSION 2 + `target_version` 12 + pinned fixtures byte-stable); an ellipse theme applies → renders → recovers; GPU skips `Layer::Shape` (parity SSIM ≥ 0.99 unchanged) | `cargo test -p selahcue-present -p selahcue-app -p selahcue-lan -p selahcue-data -p selahcue-gpu` | routes correctly; persists+recovers; no drift; parity green | test_compose/test_controller/test_parity | PASS |
| C-004 | yes | Frontend: the operator Add Shape opens a shape picker; adds an `Element::Shape` with the chosen `variant`; a corner-radius control for rounded; WKWebView-safe + keyboard | operator `node --check` + headless | picker adds the kind; inspector adapts | headless test | PASS |
| C-005 | yes | Gate: make ci + operator build/fmt/clippy/deny clean; determinism (parity + pinned) green; independent Workflow review, findings fixed; 3-OS CI green | make-ci + operator + Workflow + CI | all green; review fixed; parity holds | CODE-REVIEW-batch-shape-kinds.md; CI run | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-engine` (each kind: an ellipse pixel at a corner of the bbox is background but the centre is fill; rounded-rect corners cut; triangle apex/base; a Rect shape byte-identical; determinism; extreme-rect no-panic; additive serde), `-p selahcue-present` (Rect→Fill unchanged, Ellipse/…→Shape), `-p selahcue-gpu` (parity unchanged — Shape skipped), `-p selahcue-app`/`-lan`/`-data` (ellipse theme applies+recovers; no wire/migration drift). Broader: make ci + operator gate + 3-OS CI. Operator headless: the shape picker adds the chosen kind. Independent: adversarial Workflow review (raster-geometry/determinism/parity · model/serde-no-drift/bounded · frontend-picker lenses).
- Required environment: local + CI.

## Iteration ledger

- Iter 1 (C-001): Added `ShapeKind {Rect,Ellipse,RoundedRect,Triangle}` (Copy, Default=Rect, snake_case, `is_rect()`) + additive `Layer::Shape {rect,kind,fill,border,border_px,corner_px}` (Eq, `skip_serializing_if` on zero border/corner) to engine `scene.rs`; `Element::Shape` gained `variant`/`corner_permille` (`serde(default, skip_if)`) in present `theme.rs`; re-exported `ShapeKind` from both crates. Evidence: `test_scene` — `shape_layer_is_additive_and_tag_stable` (Fill JSON byte-unchanged; kind snake_case; zero border/corner skipped) + `shape_kind_default_is_rect_and_serde_snake_case`; workspace + operator compile. Result: PASS.
- Iter 2 (C-002): Added `draw_shape` + `ellipse_inside` (fixed-point i64, overflow-proof), `triangle_inside` / `rounded_inside` (exact i128), `shape_inside`, and the `render()` Shape arm to `raster.rs`. Inset-ring border via the shrunk-shape test. Evidence: `test_raster` — ellipse round-not-square, triangle apex/base, rounded corners cut, border rings the edge, opacity blends, determinism, and `shapes_are_bounded_on_extreme_rects_without_panic` (i32::MIN/u32::MAX rects + u32::MAX border/corner → no panic). Result: PASS.
- Iter 3 (C-003): `compose::element_layers` routes `Rect` → the UNCHANGED `Layer::Fill` path (verbatim) and Ellipse/Rounded/Triangle → one `Layer::Shape` (opacity folded into fill/border alpha; border_px + corner_px clamped to half the shorter side). GPU compositor already skips non-Fill (doc updated). Evidence: `test_compose` (Rect→Fill only, non-rect→one Shape of its kind, ellipse leaves corners as bg, Rect JSON byte-identical) + `test_controller` (`a_custom_theme_with_an_ellipse_element_applies_and_recovers`) + full `-p selahcue-gpu`/`-lan`/`-data` green (no wire/migration drift; parity unchanged). Result: PASS.
- Iter 4 (C-004): Operator `dist/` — `#td-shape-row` picker (Rectangle/Ellipse/Rounded/Triangle, WKWebView-safe via the shared `.td-save-row[hidden]` guard, Esc/Cancel); `tdAddDefaults`/`tdAddElement` thread `variant` (rect omits it → byte-identical) + a default `corner_permille` for rounded; inspector `#td-el-corner` control shown only for rounded; head names the geometry. Evidence: `node --check` clean; headless 45/45 (10 new C-004 checks: picker opens/closes, each kind's variant, corner control show/edit, Rectangle omits variant, Cancel adds nothing). Result: PASS.
- Iter 5 (C-005): Gates — `cargo fmt --check` clean, `cargo clippy --workspace --all-targets` clean, `cargo test --workspace` green (0 fail); operator fmt/clippy/build clean + `cargo deny check bans licenses sources` = OK (no dep change; the gtk3 `unmaintained` advisory is the pre-existing accepted RISK-011, Tauri-blocked). Independent adversarial Workflow review + 3-OS CI: in progress.

## Risks and rollback

- Risks: a non-deterministic shape fill (float / SIMD) breaking NFR-014 (mitigated: pure i64 integer per-pixel; determinism + parity + pinned tests). A Rect shape changing byte-output (mitigated: Rect routes to the UNCHANGED `Layer::Fill` path; `variant`/`corner` skip-if-default; a byte-identical test). Overflow/panic on an extreme rect (mitigated: clip to the framebuffer first; i64 arithmetic bounded by ≤ MAX_DIMENSION; a no-panic test). Serde/Eq breakage (mitigated: `skip_serializing_if` + Eq-only fields; fixture byte-stability test). Wire/migration drift (mitigated: NONE — rides the theme JSON). Rollback: git; additive across scene/raster/theme/compose.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajtwq24-shape-kinds.md --require-complete`
- Validator result: PASS (5/5 mandatory criteria; C-001..C-004 PASS, C-005 pending 3-OS CI).
- Independent verification result: adversarial Workflow review `wf_20e389ba-d6a` (3 lenses — raster-geometry/determinism/bounded · model/serde/no-drift/compose · frontend-picker — each per-finding refute-by-default) → **0 findings raised, 0 confirmed** (genuine clean pass; 204k tokens / 51 tool calls). Highest-risk invariants independently re-proven: no debug-overflow panic on `i32::MIN`/`u32::MAX` rects under `-C overflow-checks=on`; byte-identical rectangle serialization + green `selahcue-data` migration suite. Local gates: `cargo fmt --check` + `clippy --workspace --all-targets` + `cargo test --workspace` (0 fail); operator fmt/clippy/build + `deny bans·licenses·sources` OK; headless 45/45. See `docs/delivery/CODE-REVIEW-batch-shape-kinds.md`.
- Terminal state: `GATE_REVIEW` (verifiable work complete; awaiting 3-OS CI green + the `/build` user gate — does not authorise the next batch).
- ClickUp final evidence comment: posted to `86ajtwq24` (→ qa) + BUILD CONTROL `86ajnx548`.
