# Code Review — Batch 8b (Text shaping: cosmic-text replaces font8x8, S8-2)

- **Scope:** story `86ajpzha7` (S8-2) — replace the ASCII-only `font8x8` glyph path with real shaping per ADR-0014. Executed via the `/goal` engine (`TASK-86ajpzha7-text-shaping.md`).
- **Method:** a 3-lens insertion-point map (`wf_247548a0-429`) before editing, then a 4-lens **adversarial review** (`wf_6640e4b1-bf5`, 19 agents, each finding verified). No self-approval.
- **Outcome:** **15 raised → 9 confirmed → all fixed; 6 refuted.** (The 9 confirmed dedupe to 3 root defects + 1 low — several agents surfaced the same descender-crop and cache-growth from different lenses.)

## What shipped

`selahcue-engine::raster::draw_text` now shapes each `Layer::Text` line with **cosmic-text + rustybuzz** (pure-Rust HarfBuzz over ttf-parser) and rasterizes glyphs with **swash**, over a single **bundled OFL font** (Noto Sans, Latin subset, 127 KB, `assets/fonts/`), blended into the FrameBuffer. System fonts are never loaded (a thread-local `FontSystem` over only the bundled bytes), so text shapes/rasterizes **identically on every OS** (NFR-014) with a **memory-safe** parser (FR-173, no C FFI). The old path skipped every non-ASCII char; now "María" renders the í and Yoruba/Igbo tonal marks shape correctly (FR-017). The GPU compositor renders Fill only and CPU-rasterizes text via this path, so all output text is fixed; the GPU SSIM oracle (Fill) is unaffected.

## Findings and fixes (deduped)

| Sev | Defect | Fix |
|---|---|---|
| **high** | **Text work was not frame-bounded.** `Buffer::draw` rasterized EVERY glyph with no off-screen culling (`set_size(None,None)`), so a long/pasted line did O(text_len × font_size²) work regardless of rect — stalling every preview frame (a regression: the old bitmap path `break`-ed at `clip_right`). Empirically a 4000-char line = ~2 s/frame | Replaced `Buffer::draw` with a manual `layout_runs`/`with_pixels` loop that **breaks once a glyph starts past `clip_right`** and skips glyphs wholly left of the rect → work bounded to VISIBLE glyphs. Test: a 5000-glyph line and a short overflowing line render byte-identical visible pixels |
| **med** ×4 | **Descenders + Yoruba/Igbo dot-below marks (ẹ/ọ/ṣ/ị) were cropped.** `line_height == font_size == rect.h` but Noto's glyph box is ~1.36 em, so cosmic-text centred a taller box and the clip shaved the below-baseline zone — undercutting the exact FR-017 marks | `font_size = 0.72·px` in a `px`-tall line box, so the full glyph box (incl. descenders/dot-below) fits the cell. Test: descender/dot-below ink renders in the lower cell |
| **med** | **Unbounded cache growth (no-leak).** The thread-local `FontSystem` + `SwashCache` never evicted; a long session at many distinct sizes could grow without bound | The whole context is **rebuilt from scratch every 4096 renders** (cheap — reloads the 127 KB font — and fully frees both caches). The app's `px` is fixed by output resolution (a few values) so this is belt-and-suspenders. Test: 9000 renders across 30 distinct sizes stays fast + deterministic |
| low | Non-saturating arithmetic in the per-pixel closure could i32-overflow-panic for extreme rect origins | `saturating_add` on the pixel coords (the clip discards them anyway) |

**Refuted (6):** cross-OS byte-parity is *validated* (3-OS CI) not *guaranteed by construction* — accepted framing, not a defect; the overscan/OOB/panic lens **verified safe** (text cannot paint into the safe margin); "no font-fallback chain" is by-design (single bundled font, out-of-set glyph → `.notdef`, honest for the MVP Latin+diacritic set); the diacritic test's ink assertion is a reasonable proxy; the GPU Fill-only claim + permissive-licence claim verified correct.

## Verification

- **16 raster tests** (ASCII legibility, diacritic coverage, byte-determinism, glyph-not-mirrored, **offscreen-cull bound**, **descender non-crop**, **bounded-cache**) + the compose/stage/present suites updated to antialiasing-robust ink oracles (the safe-margin overscan invariant is now *stronger*). **Full workspace (48 suites) + GPU parity green; fmt + clippy clean; `--features server` E2E green.**

## BLOCKED — CI cannot run (owner action)

C-003's **3-OS byte-parity**, C-005 (**dependency-audit + supply-chain/license** for the new cosmic-text deps + the OFL font), and C-006's **CI-green** are all CI-gated and **currently BLOCKED**: GitHub Actions is not dispatching jobs — every job (including the Rust-independent Flutter job) completes with **zero steps and no logs** (runs 30160556745, 30161697707), the classic signature of a **repo-level Actions outage** (exhausted minutes/spending limit, or Actions disabled). This is not caused by batch 8b (which compiles + passes every check locally). The new deps are MIT/Apache and the font is OFL (all in `deny.toml`'s allowlist by inspection); the `cargo audit` job tolerates unmaintained advisories — but the **jobs must actually run** to confirm. **Owner: check GitHub → Settings → Billing & plans / Actions.** Once restored, re-run to close C-003/005/006.
