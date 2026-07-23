# Code Review — batch 7f: render-engine test seam (ADR-0015)

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context workflow. No self-approval.
**Date:** 2026-07-23
**Scope:** `selahcue-engine` — `scene.rs`, `raster.rs`, `analysis.rs`, `fault.rs`,
`engine.rs`, and the `tests/` suite. (The wgpu on-screen backend is a later batch and
was out of scope.)

## Verdict: PASS (4 confirmed findings remediated)

12 agents ran (4 review lenses + 8 verify; **1 verify agent errored** on a schema
retry cap — assessed manually). **7 findings raised → 4 confirmed.** This review was
high-value: it caught **two safety-critical flash-analyzer false-passes** and a
**process-abort path that would defeat the never-blank guarantee** — exactly the class
of defect this seam exists to prevent. All 4 are fixed and re-verified: `cargo test -p
selahcue-engine` **28/28**, clippy clean.

## Confirmed & fixed

### H1 — flash rate was a whole-capture average, not the WCAG worst-case 1-second window
A 6 Hz strobe in the first second of a 10 s capture averaged to 0.6 flashes/sec → **false
PASS**. A seizure-inducing burst would have shipped because benign trailing frames diluted
the rate.
**Fix:** the verdict is now the maximum flashes in any **one-second sliding window**, so a
burst can't be averaged away. **Test:** `strobe_burst_then_long_static_still_fails`.

### H2 — unvalidated frame dimensions crashed the engine (defeating never-blank NFR-024)
A `SetScene` with `width=height=1_000_000` (a units bug or hostile input over IPC) drove
`FrameBuffer::filled` to a ~4 TB allocation → process abort → dark output that never
recovers; in debug, a multiply-overflow panic.
**Fix:** `MAX_DIMENSION` + `is_renderable`; `filled` uses a safe fallback and `usize`
index math; `Engine::apply(SetScene)` **rejects** an out-of-range frame (emitting
`EngineEvent::Rejected`) and **holds the last good frame** instead of rendering;
`Engine::new` clamps. **Tests:** `oversized_frame_is_rejected_and_output_is_held`,
`extreme_engine_dimensions_do_not_panic`.

### M1 — whole-frame mean hid a localized strobe below the amplitude gate
A strobe over ~6–9% of the frame produced a whole-frame luminance swing < 10%, so **no
flash was counted** — a false PASS for a localized seizure risk.
**Fix:** each frame is split into an 8×8 tile grid (`FrameBuffer::tile_stats`) and every
tile is analyzed independently; the verdict is the worst tile. **Test:**
`localized_subregion_strobe_fails_despite_small_area`.

### M2 — `/2` integer truncation passed a 3.5 Hz strobe at the boundary
8 frames at 7 fps (3.5 flashes/sec, a >3/sec hazard) truncated to 3.0 → PASS.
**Fix:** flashes are counted **fractionally** (`transitions/2.0`), so a dangling
half-flash still contributes. **Test:** `strobe_just_over_three_hz_fails_at_the_boundary`.

## Dismissed / assessed (not defects)

- **`SetScene` can deliberately blank/resize the output** — correctly dismissed: NFR-024 is
  fault-scoped; `SetScene`/`Blackout`/`Clear` are *deliberate* output changes (the H2 fix
  still hardens the *crash* aspect).
- **`index()` u32 overflow / zero-size engine vacuity** — dismissed as non-reachable
  (allocation-blocked / garbage-in from a deliberate 0×0). The `index()` was switched to
  `usize` anyway as part of H2.
- **IPC messages carry no version field** (errored verify agent, assessed by hand):
  `IPC_VERSION` exists but isn't embedded in the on-wire messages. The engine is in-process
  today; a versioned envelope belongs with the actual IPC transport (the wgpu/out-of-process
  batch). Documented as a follow-up, not a present defect.

## Independence statement

Reviewed by fresh-context agents that did not author the code, over the listed files, using
the crate's own test/lint tooling. Findings were adversarially verified (default-to-not-real)
before being reported; the 4 confirmed defects were fixed and re-verified, and the errored
agent's finding was assessed by hand.
