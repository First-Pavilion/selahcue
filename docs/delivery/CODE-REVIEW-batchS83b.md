# Code Review — Batch S8-3b (Theme render model + engine, FR-010)

- **Scope:** story `86ajq14vq` (S8-3b) — implement the S8-3a theme model as a real render engine: a slide-design template (background + positioned regions with alignment + typography) applied to the audience output, switchable with **zero content loss**, persisted + recovered. Executed via the `/goal` engine (`TASK-86ajq14vq-theme-engine.md`).
- **Method:** an adversarial Workflow review (`wf_fe4db576-c11`, 5 lenses → per-finding adversarial verify, 10 agents). Lenses: content-loss/zero-loss-switching · compose+alignment correctness · wire-compat/fixture-stability · migration+persistence safety · general correctness/security. No self-approval.
- **Outcome:** **3 raised → 3 CONFIRMED (all LOW) → all fixed/dispositioned; 0 high/med.** The content-loss, wire-compat, and migration lenses found nothing real (empty results after verification).

## What shipped

A **Theme** (`selahcue-present/src/theme.rs`) is now a design template: `Theme{background, title: RegionStyle, body: RegionStyle}` where each `RegionStyle` carries a per-mille rect + H/V alignment + typography (size/line-height/colour). Three built-ins — **classic** (centred navy, amber reference), **high-contrast** (bigger, black), **lower-third** (bottom-left band) — render both scripture (title = reference) and song (title = song title) consistently. The compositor gained **real alignment**: `Layer::Text` has an `align`, and `raster::draw_text` offsets the shaped line by its measured `line_w` (Center/Right), while `compose` lays out each region with V-alignment + per-region typography. `Presenter::set_theme` recomposes Preview + Live from the **retained** slides → zero content loss (content ⟂ theme). Additive `SetTheme` wire command (RBAC `ConfigureOutputs`) + `theme`/`themes` in the operator view (skip-if-empty → v2 fixtures byte-stable) + migration v8 + crash recovery + a console picker + the Dart client. Rendered previews of all three themes (scripture + song) match the S8-3a Figma mocks.

## Findings and dispositions (all LOW)

| # | Lens | Finding | Disposition |
|---|---|---|---|
| 1 | content-loss | `a_theme_switch_preserves_blackout` asserted only the controller **flag**, not the rendered output — a dropped `presenter.blackout()` re-apply (set_theme re-issues SetScene, which resets engine blackout) would un-black the audience output undetected | **Fixed:** the test now also asserts `live_is_black(&c)` before and after the switch (byte-level black), guarding the re-apply line |
| 2 | compose | **lower-third** body fits only ~2 of the 6 capped scripture lines at every resolution, so switching a live 6-line verse to lower-third **visually clips** lines 3-6 (content retained on the `Slide` — a data guarantee, not a visual one) | **Documented as intended** (short-form template; MVP overflow = clip; shrink-to-fit is a later slice) on `Theme::lower_third()`, and **surfaced at the gate** for product confirmation |
| 3 | general | The `TextAlign` enum insertion **reparented** the `Layer` doc comment onto `TextAlign`, leaving `pub enum Layer` undocumented | **Fixed:** moved the `Layer` doc back above its enum |

**Empty (verified nothing real):** content-loss (beyond #1's test-gap), wire-compat/fixture-stability, migration/persistence — the additive skip-if-empty fields keep the pinned v2 fixtures byte-identical, the v8 migration is additive/nullable (v7→v8 upgrade tested), and the `?16`/column-15 binding order round-trips.

## Verification

Full workspace + GPU parity + fmt/clippy **clean**; Flutter **42** green; per-layer tests (theme model, alignment offset, region compose, set_theme zero-loss, wire fixtures + rbac, migration v8 + session round-trip). Deferred with seams (later slices / follow-ups): gradient/image backgrounds, multi-weight/family fonts, custom-font import, pagination, per-role auto-selection + per-item override (S8-3d), the Theme Designer editor UI (S8-3c). **3-OS CI:** pending this push.
