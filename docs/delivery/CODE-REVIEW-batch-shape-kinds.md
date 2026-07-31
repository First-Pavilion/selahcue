# Code Review — Batch: more shape kinds (86ajtwq24)

- **Scope:** owner refine **#2** — "the only shape I can add now is a rectangle; add a picker where I can select the shapes I want." Extends `Element::Shape` from a filled **rectangle** to four **kinds** — rectangle (existing), **ellipse**, **rounded-rectangle**, **triangle** — each an area fill + optional inset-ring border, at the per-mille rect + opacity + z; plus a **shape picker** on the operator's Add Shape and a corner-radius control for rounded. Executed via `/goal` (`TASK-86ajtwq24-shape-kinds.md`, validator PASS 5/5). Engine + present + operator-`dist/` only; **no wire/migration change** (rides the theme JSON).
- **Method:** an adversarial Workflow review (`wf_20e389ba-d6a`, **3 independent lenses** → per-finding refute-by-default verify, ultracode). Lenses: **raster-geometry / determinism / bounded-overflow** · **model / serde / no-drift / compose-routing** · **frontend picker (WKWebView-safety / keyboard / byte-identical)**. Each finder read the diff + full files (204k tokens, 51 tool calls, ~8.8 min).
- **Outcome:** **0 findings raised → 0 confirmed.** A genuine clean pass — each lens analysed its surface thoroughly and found no real defect. The highest-risk invariants were independently re-proven empirically (below), so the clean result is trusted, not assumed.

## What shipped

- **Engine model (`scene.rs`):** `ShapeKind { Rect, Ellipse, RoundedRect, Triangle }` (`Copy`, `Default = Rect`, snake_case serde, `is_rect()`) + additive `Layer::Shape { rect, kind, fill, border, border_px, corner_px }` (`Eq`-preserving; `skip_serializing_if` on zero `border_px`/`corner_px`). Re-exported from `selahcue-engine` + `selahcue-present`.
- **Engine raster (`raster.rs`):** `draw_shape` fills the parametric shape over the **on-screen clipped span** with a per-kind inside-test + an **inset-ring border** (fill where inside the border-shrunk shape, border otherwise). Geometry:
  - **Ellipse** — **fixed-point i64** (`nx² + ny² ≤ SHAPE_FP²`, `SHAPE_FP = 2¹⁵`), clamped so it is **overflow-proof for every `u32` extent** (a degree-4 exact test would overflow even `i128` near `u32::MAX`).
  - **Triangle** — exact **i128** half-width test `2·h·|Δx| ≤ w·(2y+1)` (apex top-centre, base on the bottom edge).
  - **Rounded-rect** — exact **i128** clamp-SDF corner test in doubled coordinates; radius clamped to half the shorter side.
- **Compose (`compose.rs`):** `element_layers` routes a **`Rect` shape → the verbatim-unchanged `Layer::Fill` path** (fill + 4 border edges) and **Ellipse / Rounded / Triangle → one `Layer::Shape`**, folding opacity into the fill/border alpha (as the rect path does) and clamping `border_px`/`corner_px` to half the shorter side.
- **GPU (`compositor.rs`):** the wgpu compositor renders **only `Layer::Fill`**, so `Layer::Shape` is **skipped by construction** — the Fill-only parity oracle (SSIM ≥ 0.99) is untouched. Doc comment updated to name Shape alongside Text/Image.
- **Operator (`dist/`):** Add Shape → a **WKWebView-safe inline picker** (`#td-shape-row`: Rectangle / Ellipse / Rounded / Triangle; keyboard-operable; Esc/Cancel; hides via the shared `.td-save-row[hidden]` guard). A **Rectangle** pick omits `variant` (byte-identical JSON); **Rounded** gets a default `corner_permille` and reveals a **corner-radius** inspector control (`#td-el-corner`, % of the shorter side). The inspector head names the geometry.

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| — | raster-geometry | — | *(none)* — the overflow/determinism/clipping paths hold | — |
| — | model-serde-compose | — | *(none)* — Rect byte-stable; routing correct; GPU skip intact | — |
| — | frontend-picker | — | *(none)* — WKWebView-safe; variants valid; corner control gated | — |

**0 raised, 0 confirmed, 0 refuted** (no finding reached the verify stage). Prior batches' hardest bugs (overflow panic, `display:flex` vs `[hidden]`, sync-command deadlock) had **no analogue here** — this batch added a dependency-free integer raster + a client-side picker over the exact patterns those fixes established.

## Independent re-proof of the high-risk invariants

Because a clean review is only as good as its riskiest unchecked assumption, the two subtlest guarantees were re-proven with concrete evidence, not left to reviewer confidence:

- **No debug-overflow panic for ANY rect (NFR bounded):** `test_raster::shapes_are_bounded_on_extreme_rects_without_panic` renders every kind with `Rect::new(i32::MIN, i32::MIN, u32::MAX, u32::MAX)` (and other extremes) **plus `border_px = corner_px = u32::MAX`**. Re-run under an **explicit `RUSTFLAGS="-C overflow-checks=on"`** build (and the default `test` profile already enables overflow checks) → **passes**. A debug overflow would panic, so this is a hard proof the arithmetic is bounded.
- **Determinism (NFR-014):** `shape_opacity_blends_and_render_is_deterministic` asserts byte-identical `render(&f).bytes()` across runs; every geometry test is pure integer. Cross-OS parity is guaranteed by the same property the rest of the raster relies on.
- **Byte-identical rectangle (backward-compat):** `test_compose::a_rect_shape_element_json_is_byte_identical_to_before` asserts a `Rect` `Element::Shape` emits neither `variant` nor `corner_permille`; `test_scene::shape_layer_is_additive_and_tag_stable` asserts the `Layer::Fill` encoding is byte-unchanged. The full `selahcue-data` migration suite (target_version 12) is green → no pinned-fixture drift.

## Verification

- **Rust:** `cargo fmt --check` clean · `cargo clippy --workspace --all-targets` clean · **`cargo test --workspace` green (0 failures)**, incl. new `test_scene` (2), `test_raster` (7 shape tests), `test_compose` (4 routing/serde tests), `test_controller` (ellipse applies+recovers) and unchanged `selahcue-gpu` parity.
- **Operator gate:** `cargo fmt --check` clean · `cargo clippy` clean · `cargo build` clean (no Rust change — `dist/` only) · **`cargo deny check bans licenses sources` = OK** (no dependency change). The `unmaintained` gtk-rs GTK3 advisory is the **pre-existing accepted RISK-011** (glib unsoundness, Tauri-blocked), unchanged by this batch.
- **Headless interaction check** (Chrome + `window.__TAURI__` stub): **45/45** — all prior canvas regressions + **10 new C-004 checks**: the picker opens/closes, each kind serialises its `variant`, a Rectangle omits `variant`, the corner control shows only for rounded and edits `corner_permille` (20 % → 200 ‰), and Cancel adds nothing. `node --check` clean.
- **Invariants:** editing stays preview-only (only Apply calls `set_custom_theme`); no wire/migration change (VERSION 2, `target_version` 12); `Eq`/`Clone` preserved; GPU parity set unchanged.
- **CI:** the 3-OS Rust matrix + operator-shell + audit/SBOM/deny gate — pending this push.

## Follow-ups (unchanged, still queued)

- **#7** real Preview/Live render → `86ajtwq28` · **#8** scripture live-follow ("only when already live") → `86ajtwq2b` · **#5** font weight/letter-spacing → `86ajq3225`. **Seams noted this batch:** line / star / arrow / polygon kinds; per-shape gradients; rotation; **GPU-native shapes** (with GPU glyphs/images); true uniform-inset borders (the inset-ring approximation is used).
