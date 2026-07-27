# Code Review — Batch: Image element model (86ajq6j49 backend slice)

- **Scope:** story `86ajq6j49` (Canvas Editing epic) — the **backend model half** of the owner's image vision: add an **`Element::Image`** kind (per-mille rect · `MediaRef` · opacity · z) to the theme's element list and **compose it → `scene::Layer::Image`** (mirroring `Element::Shape → Layer::Fill`), so a theme can carry a positioned, opacity-blended, **z-ordered (behind / in front of the text)** image that renders on the audience output, persists, and recovers. Executed via `/goal` (`TASK-86ajq6j49-image-element-model.md`, validator PASS 4/4). Consumes the S8-6 decode foundation (`Layer::Image` + bounded PNG decode + placeholder). **No wire command, no migration, no RBAC change, no GPU-pipeline change.**
- **Method:** an adversarial Workflow review (`wf_8d0322a5-977`, 3 independent lenses → per-finding adversarial verify). Lenses: model/Copy-ripple/bounded · compose-zorder-opacity-determinism · persistence/recovery/no-drift. Every finding independently confirmed-or-refuted (default REFUTED). No self-approval.
- **Outcome:** **1 raised → 1 CONFIRMED → fixed; 0 refuted.** 0 HIGH; 0 MEDIUM; 1 LOW (test-only). The model/compose/persistence lenses found **no product defect** — the additive serde, lossless round-trip, deterministic recovery, z-order, opacity, `MAX_ELEMENTS` bound, and zero wire/migration/RBAC drift all held.

## What shipped

- **Model (`theme.rs`).** `Element::Image { x/y/w/h_permille: u16, source: MediaRef, opacity: u8, z: i16 }`, reusing the engine's bounded/validated `MediaRef`. `Element` now derives **`Clone` (not `Copy`)** because the image kind carries a heap-backed `MediaRef`; `RegionStyle`/`Band`/`FontName` stay `Copy`. `Element::z()` extended. **The Copy→Clone ripple cost zero extra sites** — `element_layers`/`compose_slide` take `&Element` (no value copy), so the whole workspace + operator compiled unchanged.
- **Compose (`compose.rs`).** An `Element::Image` arm in `element_layers` → `Layer::Image { rect (per-mille→pixel), source: source.clone(), opacity }`. z-order (behind/in-front of the text) + the empty-elements no-op are **inherited unchanged** from `compose_slide`'s existing stable sort — an image slots in exactly like a shape.
- **Persistence.** The image element rides the opaque theme JSON (`"kind":"image"`) — no migration, wire VERSION 2 + `target_version` 12 unchanged, pinned fixtures byte-stable. `MAX_ELEMENTS` (enforced on `set_custom_theme`/`save_theme`/`load_saved_themes`) bounds it; decoded pixels never enter the theme/`Frame` (they live in the engine's bounded cache).
- **Re-export.** `MediaRef` from `selahcue-present`.

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | persistence-nodrift | LOW | **Test helper leaked PNG fixtures into the system temp dir.** The new `temp_image()` test helper wrote an encoded PNG to `$TMPDIR/selahcue_imgel_<pid>_<n>.png` and never deleted it; four of the five new image tests created one, so repeated `cargo test -p selahcue-present` runs accumulated small PNGs until the OS temp reaper cleared them. Test-only, no product/functional impact, but exactly the kind of on-disk growth the project's no-leak norm targets. | **Fixed:** `temp_image()` now returns an RAII `TempImage` guard whose `Drop` removes the file (panic-safe, even on unwind) — tests bind the guard and use `.path()`, so every fixture is deleted when the test ends. No new dependency. |

### Refuted (verified NOT real — 0)

None raised beyond the LOW above; the model/Copy-ripple/bounded and compose-zorder-opacity-determinism lenses returned no findings (the invariants held under adversarial reading).

## Verification

- **Determinism gate (NFR-014):** `make ci` **ALL GREEN** — `cargo test` across present/engine/gpu/app/lan/data + operator + Flutter, incl. **`test_parity`** (SSIM ≥ 0.99, unchanged — the GPU skips `Layer::Image` like `Text`, so the parity set is untouched) + the pinned-render tests. A theme with no image element renders byte-identically to before. `cargo fmt --check` clean (main + operator); `clippy -D warnings` clean.
- **No wire/migration/RBAC change** (constraint): `protocol.rs` VERSION 2 + pinned fixtures byte-stable; `migrations.rs` `target_version` 12; `rbac.rs` unchanged. The image element rides the existing opaque `theme_json` seams.
- **Per-lens:** compose (`test_compose` 24/0) — an image element composes to a `Layer::Image` with the mapped per-mille→pixel rect + opacity; a real red image renders on the output; z<0 composes before the text layers, z>=0 after; a missing source → the non-black placeholder; additive + byte-stable serde + lossless round-trip. controller (`test_controller` 63/0) — a custom theme with an image element applies → the missing-source placeholder reaches the live output → recovers identically; over-cap image elements rejected (`MAX_ELEMENTS`).
- **Deferred with seams (contract non-goals):** all on-canvas authoring UI — add via a file picker, select/drag/resize, **send-to-back / bring-to-front** (interactions `86ajq6j4p`, design `86ajq6j29`, Theme Designer image control); aspect-preserving `Fit` modes (stretch-to-rect this batch); the text element (`86ajq6j64`); other formats + the out-of-process sandbox (S8-6 seams); remote controller→host asset transfer (a `MediaRef` is a host-local path); FR-138 canonicalization.
- **3-OS CI:** pending this push (parity is the determinism gate).
