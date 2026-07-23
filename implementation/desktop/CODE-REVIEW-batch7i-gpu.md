# Code Review — batch 7i: wgpu compositor + parity oracle + native window

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context workflow. No self-approval.
**Date:** 2026-07-23
**Scope:** `selahcue-gpu` (compositor + parity test), the engine `ssim`/`from_rgba`
additions, and `selahcue-desktop` (native window, compile-only).

## Verdict: PASS (6 confirmed findings remediated)

16 agents ran (4 review lenses + 12 verify; 1 verify agent errored — its lens's other
findings were covered). **11 findings raised → 6 confirmed.** The **parity-fidelity lens
was the point** — it found the SSIM oracle could pass a *broken* compositor. All confirmed
findings are fixed and re-verified: `cargo test -p selahcue-gpu` (GPU parity) passes with
the strengthened suite; workspace 141/141; clippy clean.

## Confirmed & fixed

### Parity-oracle gaps (M/M/L — the oracle could pass a broken compositor)
- **No alpha blending exercised** — every parity scene was opaque, so a blend-mode /
  premultiplication / sRGB regression would score SSIM ~1.0 and ship. **Fixed:** added a
  translucent `Fill` (a=128) over a contrasting background, forcing the GPU alpha-blend and
  CPU src-over to actually mix.
- **Readback row-padding path was dead** — all widths (320/256/128) were 256-byte-row
  aligned, so `padded_row == unpadded_row` and the strip loop was never distinguished from
  identity. **Fixed:** added a **300×130** scene (1200 B/row → padded 1280), exercising the
  stride math.
- **SSIM compared luminance only** — a chroma-only divergence (channel swap / iso-luminant
  hue error) scored ~1.0. **Fixed:** `analysis::ssim` now computes SSIM **per R/G/B channel
  and takes the minimum**, so a hue error can't pass. The GPU still matches the CPU per
  channel to ≥0.99 (verified).

### Desktop window (L/nit)
- **Surface-loss freeze** — on `Outdated`/`Lost` (sleep, HDMI re-negotiation) the render
  path reconfigured but never `request_redraw`'d, so under `ControlFlow::Wait` the live
  output could freeze on black until the next keypress. **Fixed:** reconfigure on
  `Outdated`/`Lost` and always `request_redraw()` so the recovered surface repaints.
- **Blackout key case-sensitive** — only lowercase `"b"` fired the documented `B`.
  **Fixed:** `eq_ignore_ascii_case("b")`.

## Dismissed (verified not-a-defect)

- **`map_async` failure discarded → panic on device-loss** — `render_to_pixels` returns
  `Vec<u8>` (panic-on-error by signature); device loss is an exceptional unrecoverable
  event, and the panic is loud, not silent corruption. Acceptable for the offscreen path;
  not reachable on the tested GPU.
- **No initial `request_redraw` in `resumed()`** — on macOS (this batch's Metal target)
  the OS drives the first paint via `drawRect:`/`RedrawRequested`; the hypothetical failure
  is on an unsupported backend only.

## What is verified vs compile-only

- **Verified on the real Metal GPU:** the offscreen compositor renders the engine's scenes
  to **SSIM ≥ 0.99** vs the CPU rasterizer across opaque, translucent, overlapping, blackout,
  and non-aligned-width frames — the ADR-0015 cross-backend parity oracle.
- **Compile-only (needs a display):** the `selahcue-desktop` on-screen window
  (`winit` + wgpu surface). Runnable on a Mac via `cargo run -p selahcue-desktop`.

## Independence statement

Reviewed by fresh-context agents that did not author the code, over the listed files, using
the crate's own test/lint/build tooling (GPU present). Findings were adversarially verified
(default-to-not-real); the 6 confirmed defects were fixed and re-verified.
