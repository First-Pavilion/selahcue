# Code Review — batch 7g: presentation rendering (Preview→Live)

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context workflow. No self-approval.
**Date:** 2026-07-23
**Scope:** `selahcue-present` — `slide.rs`, `compose.rs`, `present.rs`, and the `tests/`
suite (built on the `selahcue-engine` seam).

## Verdict: PASS (4 confirmed findings remediated)

10 agents ran (4 review lenses + 6 verify; 0 errors). **6 findings raised → 4 confirmed**
(all low/medium). Re-verified: `cargo test -p selahcue-present` **18/18**, full workspace
**130/130**, clippy clean.

## Confirmed & fixed

### M1 / L1 — `Presenter::new` didn't clamp dimensions → tracked state could lie
Created with a 0×0 or out-of-range resolution (e.g. a headless/not-yet-attached output),
the engine **rejects** the `SetScene`, but `go_live()` returned `true` and `live_slide()`
reported the slide as live — so an operator UI would show "LIVE: Slide 1" while the
audience output was actually **black**.
**Fix:** `Presenter::new` clamps `width`/`height` into the engine's renderable range
(matching `Engine::new`) and composes at the clamped size, so a composed frame is always
accepted; **and** `stage`/`go_live` now inspect the returned `EngineEvent` — on `Rejected`
they don't update the tracked slide and `go_live` returns `false`. Tracked state can no
longer diverge from what actually reached the output. **Test:**
`degenerate_dimensions_keep_tracked_state_consistent`.

### L2 — bottom safe margin not enforced
The top inset was honored but the bottom wasn't, so text could paint into the bottom
overscan band / to the very bottom edge at small render sizes or with a larger configured
safe margin.
**Fix:** compose now stops before a line would cross `height − margin_y`, symmetric with
the top inset. **Test:** `text_never_paints_into_the_bottom_safe_margin`.

### L3 — the slide-trigger latency test was a tautology
The old test measured `frames_until` over two synthetic captures at 60 fps → always
16.7 ms regardless of correctness; a `sleep(5s)` in `go_live` would still have passed.
**Fix:** the test now takes a **real wall-clock measurement** of the synchronous
`go_live()` at 1920×1080 and asserts ≤150 ms — so a genuine latency regression fails it.
**Test:** `go_live_slide_trigger_latency_is_within_budget`.

## Dismissed (grounded in the spec)

- **"go_live/clear defeat an active blackout"** (×2 lenses): reproduced, but **matches the
  documented design** — `UX-STATE-MATRIX` defines the blackout-state transition as
  "Un-blackout (restores prior content, FR-077), *or* stage + GO LIVE new content → new
  content live", and FR-077 only guarantees the toggle-restore contract. Going live is the
  one sanctioned live-changing action; ProPresenter-class tools behave the same. Not a
  defect — a possible future "stage behind black" product mode, out of scope. **No change
  made** (verified against the spec rather than inventing a fix).

## Independence statement

Reviewed by fresh-context agents that did not author the code, over the listed files, using
the crate's own test/lint tooling. Findings were adversarially verified (default-to-not-real)
before being reported; the 4 confirmed defects were fixed and re-verified, and the dismissed
finding was checked against `UX-STATE-MATRIX`/FR-077.
