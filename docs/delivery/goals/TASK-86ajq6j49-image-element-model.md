# Goal Contract — TASK-86ajq6j49-image-element-model

## Identity

- Goal ID: TASK-86ajq6j49-image-element-model
- Parent goal ID: EPIC-86ajq6j01-canvas-editing
- Title: Image element model + compose (86ajq6j49 backend slice) — a theme can carry a positioned, opacity-blended, z-ordered image
- Role: backend-engineer (theme model + compositor)
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq6j49
- Created: 2026-07-27
- Independent verification required: yes
- Maximum iterations: 12

## Objective

Connect the S8-6 image decode foundation to the theme model: add an **`Element::Image`** kind (per-mille rect + `MediaRef` + opacity + z) to the theme's element list and **compose it → `scene::Layer::Image`** (mirroring how `Element::Shape → Layer::Fill`), so a theme can carry a positioned, opacity-blended, **z-ordered (behind / in front of the text)** image that renders on the audience output, persists in the theme JSON, and recovers. A missing/corrupt/unsupported source draws the missing-media placeholder (already handled by the engine). This is the **model half** of the owner's image vision (`86ajq6j49`); the on-canvas authoring UI (add/drag/resize/**send-to-back**) is the follow-up interactions story.

## Baseline

Verified from code:
- `present::theme::Element` (theme.rs:132-153) is an internally-tagged (`#[serde(tag="kind")]`) enum with only `Shape` today, deriving **`Copy`** (all-scalar). Its doc already reserves the seam: "the `Image` … kind lands in the dependent stories without a wire break." `Theme.elements: Vec<Element>` is additive + `skip_serializing_if` empty + bounded by `MAX_ELEMENTS = 64` (theme.rs:157, 196). `Theme` is already `Clone` (not `Copy`).
- `compose::element_layers(&Element, w, h) -> Vec<Layer>` (compose.rs:238-293) maps a `Shape` to `Layer::Fill` rects via a per-mille→pixel `map`. `compose_slide` (compose.rs:310-352) **stable-sorts the elements by `z` and renders `z < 0` BEHIND the text, `z >= 0` IN FRONT** — a new `Element::Image` slots into this sort with no further z-logic. A no-element theme is a no-op (determinism).
- The engine already provides `scene::Layer::Image { rect, source: MediaRef, opacity }` + a bounded, deterministic, panic-contained decode + a non-black missing-media placeholder + GPU-skip (S8-6, ADR-0018). `MediaRef` is a bounded, validated reference (scene.rs) — **reuse it**; decoded pixels live in the engine cache, never in the scene/theme.
- Persistence: elements ride in the theme JSON (`custom_theme` / `saved_theme` / per-item / per-screen) — **no migration**; wire VERSION stays 2, `target_version` stays 12. `controller` rejects `elements.len() > MAX_ELEMENTS` on `set_custom_theme` / `save_theme` / `load_saved_themes` — an image element counts the same (bounded).

**Key finding:** `Element::Image` must carry a `MediaRef` (heap-backed), so **`Element: Copy → Clone`** (RegionStyle/Band/FontName stay `Copy`). The ripple is small — `element_layers`/`compose_slide` take `&Element` (no value copy), so the change is the derive + `Element::z()` + the new `element_layers` arm + compiler-guided fixes.

## Scope

### In scope

- **Model (`theme.rs`):** add `Element::Image { x/y/w/h_permille: u16, source: MediaRef, opacity: u8, z: i16 }`. `Element` derives `Clone` (not `Copy`); `RegionStyle`/`Band`/`FontName` stay `Copy`. Extend `Element::z()`. Reuse the engine's `MediaRef`. Bounded by the existing `MAX_ELEMENTS`.
- **Compose (`compose.rs`):** an `Element::Image` arm in `element_layers` → `Layer::Image { rect (per-mille→pixel), source: source.clone(), opacity }`. z-order (behind/in-front of the text) + the empty-elements no-op are inherited from `compose_slide`'s existing sort — no change there.
- **Copy→Clone ripple:** fix every compiler-flagged site (present/controller/tests) preserving behaviour.
- **Persistence + recovery:** the image element rides the theme JSON — **no migration**, VERSION/`target_version` unchanged, pinned fixtures byte-stable. A custom theme with an image element applies → renders → recovers.
- **Re-exports:** `MediaRef` from `selahcue-present` (so consumers/tests can name it).

### Non-goals (seams — note)

- All **on-canvas authoring UI**: add via a file picker, select/drag/resize, **send-to-back / bring-to-front** controls — the interactions story `86ajq6j4p` + design `86ajq6j29`, and the Theme Designer image control. This batch is the model + compose + persistence (exercised via tests), NOT the Designer UI.
- Aspect-preserving **`Fit`** modes (contain/cover) — the image fills its rect (stretch) this batch; fit is a later slice.
- The **text** element kind (`86ajq6j64`); other image formats (JPEG/WebP/GIF/BMP → placeholder, S8-6 seam); the out-of-process sandbox (ADR-0016 end-state); **remote controller→host asset transfer** (a `MediaRef` is a host-local path resolved on the render host — a real image can't ride the 64 KB control frame); FR-138 import-path canonicalization.

### Constraints

- Determinism preserved (NFR-014): a theme with no image element renders **byte-identical** to today (parity + pinned tests are the guard); an image renders via the engine's deterministic decode+blit; the GPU skips `Layer::Image`, so parity (SSIM ≥ 0.99) is unchanged. Additive serde (byte-stable default) + **no migration/wire/RBAC change**. Bounded (`MAX_ELEMENTS` + bounded `MediaRef` + the engine's bounded decode cache). Only `Element` loses `Copy`. fmt/clippy clean; 3-OS CI.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Model + ripple: `Element::Image { per-mille rect, source: MediaRef, opacity, z }`; `Element` is `Clone` (RegionStyle/Band/FontName stay `Copy`); `MediaRef` reused + re-exported; the whole workspace + operator compile with the Copy→Clone ripple fixed | `cargo build --workspace` + operator; `cargo test -p selahcue-present` | compiles; Element Clone; Image variant | test_compose | PASS |
| C-002 | yes | Compose z-order + opacity: an `Element::Image` composes to a `Layer::Image` with the per-mille→pixel rect + opacity; `z < 0` renders behind the text, `z >= 0` in front; a theme with NO image element is byte-identical to today (determinism); a missing source renders the non-black placeholder end-to-end | `cargo test -p selahcue-present -p selahcue-engine` | image layer + z-order; default byte-identical; placeholder | test_compose | PASS |
| C-003 | yes | Persistence + recovery + bounded: the image element round-trips in the theme JSON (`"kind":"image"`); additive (NO migration, VERSION 2 + `target_version` 12 unchanged, pinned fixtures byte-stable); a custom theme with an image element applies → renders → recovers; over-cap rejected | `cargo test -p selahcue-app -p selahcue-lan -p selahcue-data` | persists + recovers; no wire/migration drift; bounded | test_controller / test_protocol / test_db | PASS |
| C-004 | yes | Full: make ci + operator build + fmt/clippy clean; determinism preserved (parity + pinned green); independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed; parity holds | CODE-REVIEW-batch-image-element.md; CI run | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-present` (an image element composes to a `Layer::Image` with the mapped rect + opacity; `z<0` behind / `z>=0` in front of the text; a real image renders on the composed output; a missing source → the non-black placeholder; a no-image-element theme byte-identical; additive + byte-stable serde), `-p selahcue-engine` (no regression, parity), `-p selahcue-app` (a custom theme with an image element applies + recovers + bounded), `-p selahcue-lan`/`-p selahcue-data` (no wire/migration drift; VERSION 2 / `target_version` 12). Broader: make ci + 3-OS CI (parity is the determinism gate). Independent: adversarial Workflow review (model/ripple/bounded · compose-zorder-opacity-determinism · persistence/no-drift lenses).
- Required environment: local + CI.

## Iteration ledger

- **Iter 1 — model + ripple (C-001).** `theme.rs`: added `Element::Image { x/y/w/h_permille, source: MediaRef, opacity, z }` (reusing the engine's bounded `MediaRef`); `Element` derives `Clone` (dropped `Copy`); extended `Element::z()`; updated the Shape/Theme doc comments. `MediaRef` re-exported from `selahcue-present`. **The Copy→Clone ripple was ZERO extra sites** — `element_layers`/`compose_slide` take `&Element` (no value copy), so the whole workspace + operator compiled unchanged. **PASS.**
- **Iter 2 — compose z-order + opacity (C-002).** `compose.rs`: an `Element::Image` arm in `element_layers` → `Layer::Image { rect (per-mille→pixel), source: source.clone(), opacity }`; z-order (behind/in-front of the text) + the empty-elements no-op are inherited from `compose_slide`'s existing sort. Evidence: `test_compose` (5 new — composes to a `Layer::Image` with the mapped rect+opacity; a real red image renders on the output; z<0 before / z>=0 after the text layers; a missing source → the non-black placeholder; additive+byte-stable serde) + engine/gpu green (determinism, parity unchanged — GPU skips `Layer::Image`). **PASS.**
- **Iter 3 — persistence + recovery + bounded (C-003).** The image element rides the theme JSON (`"kind":"image"`); no migration (`protocol.rs`/`migrations.rs`/`rbac.rs` untouched, VERSION 2 + `target_version` 12, pinned fixtures byte-stable). Evidence: `test_controller` (a custom theme with an image element applies → the missing-source placeholder reaches the live output → recovers identically; over-cap image elements rejected via `MAX_ELEMENTS`). lan/data green (no drift). **PASS.**
- **Iter 4 — gate (C-004).** `cargo fmt --check` clean (main + operator); `clippy -D warnings` clean; `make ci` **ALL GREEN** (workspace test incl. `test_parity` + operator + Flutter). Independent adversarial Workflow review launched (`wf_8d0322a5-977`).
- **Iter 5 — review fixed (C-004).** Review `wf_8d0322a5-977` (3 lenses, per-finding adversarial verify): **1 raised → 1 confirmed (LOW, test-only) / 0 refuted.** The model/compose/persistence lenses found no product defect (additive serde, lossless round-trip, deterministic recovery, z-order, opacity, `MAX_ELEMENTS`, zero wire/migration/RBAC drift all held). The LOW: the `temp_image()` test helper wrote PNG fixtures to the temp dir and never deleted them (on-disk growth against the no-leak norm). **Fixed:** `temp_image()` returns an RAII `TempImage` guard whose `Drop` removes the file (panic-safe); call sites use `.path()`. Re-verified `make ci` **ALL GREEN**; `test_compose` 24/0. **PASS.**
- **Iter 6 — 3-OS CI green (Windows fix) (C-004).** First CI run (`30245106735`, `7961afc`) FAILED **rust (windows-latest) only** — the serde test `an_image_element_is_additive_serde_and_round_trips` substring-matched the raw temp-file path against the theme JSON, but Windows escapes path backslashes (`C:\\Users\\…`), so the raw path isn't a substring (macOS/Ubuntu forward-slash paths were green; local `make ci` couldn't see it). **Test-only fix** (`2645d6a`): assert the `"kind":"image"` tag + a `"source"` field, and rely on the existing round-trip equality (`from_str == t`) for value correctness — separator-independent. The shipped `Element::Image` serde is unchanged. Re-run **`30245521111` (commit `2645d6a`): SUCCESS** — rust + operator shell on all 3 OSes (parity holds), audit/SBOM green. **PASS.**

## Risks and rollback

- Risks: the `Copy → Clone` ripple on `Element` breaking present/controller/test sites (mitigated: compiler-guided; `element_layers`/`compose_slide` take `&Element`, so no value-copy break; behaviour preserved). A non-empty-elements default changing the byte-stable theme JSON (mitigated: `skip_serializing_if` + a byte-identical test). Unbounded growth (mitigated: `MAX_ELEMENTS` + bounded `MediaRef` + the engine's bounded decode cache). z-order/opacity wrong (mitigated: behind/front + opacity render tests). Wire/migration drift (mitigated: NONE — rides the theme JSON; assert fixtures + VERSION/`target_version`). A remote operator's host-local image path not resolving on the render host (documented seam — remote asset transfer). Rollback: git; additive across the theme/compose layer.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq6j49-image-element-model.md --require-complete`
- Validator result: PASS (4/4 mandatory criteria PASS)
- Independent verification result: adversarial Workflow review `wf_8d0322a5-977` (3 lenses) — 1 confirmed (LOW, test-only temp-file leak) / 0 refuted; fixed (RAII guard). See `docs/delivery/CODE-REVIEW-batch-image-element.md`. **3-OS CI run `30245521111` (commit `2645d6a`): SUCCESS** — rust + operator shell on macOS/Ubuntu/Windows (test_parity holds), RustSec audit + SBOM green; Flutter skipped. (A prior run caught + fixed a Windows-only test-escaping bug — see iter 6.)
- Terminal state: GATE_REVIEW (verifiable work complete; paused at the /build user gate)
- ClickUp final evidence comment: posted on 86ajq6j49 (→ qa) + BUILD CONTROL 86ajnx548
