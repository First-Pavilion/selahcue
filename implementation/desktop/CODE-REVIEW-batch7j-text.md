# Code Review — batch 7j: glyph text rendering

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context workflow. No self-approval.
**Date:** 2026-07-23
**Scope:** the `Layer::Text` scene variant + `draw_text` glyph rasterizer (engine), the
`compose` integration (present), and the wgpu compositor's Text-skip.

## Verdict: PASS (2 confirmed findings remediated)

8 agents ran (4 review lenses + 4 verify). **4 findings raised → 2 confirmed.** Both fixed
and re-verified: `cargo test` workspace **145/145**, clippy clean.

## Confirmed & fixed

### H1 — `draw_text` did unbounded work for oversized text (CPU-exhaustion hazard)
The glyph block-fill ran `scale²` iterations per lit pixel, bounded only by the layer's
**unvalidated** `rect`/`px`, not by the framebuffer — a `Layer::Text` with `px=100000`,
`rect` 200000×200000 would execute billions of no-op blends and hang the render thread
(and at `px ≥ 2³¹` the `advance` cast wraps negative, defeating the right-edge break).
Not reachable via the normal compose path (which caps `px` at ~819) and there is no
untrusted `Frame` deserialization today — but it is the wrong implementation and a latent
hole against the never-blank guarantee.
**Fix:** the glyph scale is now capped at the framebuffer height (no overflow), and each
block-fill iterates only the **visible intersection of the rect and the framebuffer** —
so total work is bounded by the framebuffer, exactly like `fill_rect`. **Regression test:**
`oversized_text_is_bounded_by_the_framebuffer` (a 100000-px text over a 64×64 frame renders
promptly).

### L1 — stale compositor doc claimed the rect pipeline drives the on-screen surface
`compositor.rs` said "The same pipeline drives an on-screen surface in the desktop shell."
It doesn't — the desktop shell CPU-composites via `selahcue-present` and blits the
framebuffer to its own surface; the rect pipeline renders only `Layer::Fill` and **skips
`Layer::Text`**. Misleading a future dev into wiring the surface to this compositor would
make all slide text silently vanish on screen while the Fill-only SSIM parity test stayed
green. **Fix:** corrected the doc to state the current reality and that the pipeline must
gain glyph rendering before it can drive a surface.

## Dismissed (verified not-a-defect)

- **Huge-`px` hang / `advance` i32-wrap** (glyph lens) — same mechanism as H1, dismissed by
  its verifier as *unreachable* (compose caps `px` at ~819; no untrusted `Frame` deser). The
  H1 fix hardens it anyway (bounded by the framebuffer + scale cap), so both are closed.
- **Compositor silently drops `Text` with no guard** — verified: `render_to_pixels` has
  exactly one caller (the Fill-only parity test); the flash analysis and the desktop window
  both consume the **CPU** rasterizer's output (which draws text correctly), so no reachable
  path loses text. The skip is intentional; the doc fix (L1) removes the trap.

## Notes

Glyph orientation was verified non-mirrored (font8x8 is LSB-first; an 'L'-shape test guards
the bit order). GPU-native glyph rendering (a glyph atlas in the wgpu compositor) remains the
future path so the compositor can drive an on-screen surface directly.

## Independence statement

Reviewed by fresh-context agents that did not author the code, over the listed files, using
the crate's own test/lint tooling. Findings were adversarially verified (default-to-not-real);
the 2 confirmed defects were fixed and re-verified.
