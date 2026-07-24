# Code Review — batch 7p: stage/confidence second window (+ refine: timer → stage)

**Method:** Independent multi-lens adversarial review across two passes (find → adversarially
verify), fresh-context Workflows. No self-approval.
**Date:** 2026-07-24
**Scope:** the `StageDisplay` in the `LiveController` + `stage_output` (`selahcue-app`), the
`FrameBuffer` re-export (`selahcue-present`), and the two-window desktop (`selahcue-desktop`).
Includes the **refine** (timer moved from the audience output to the stage/confidence
monitor) and the resulting loop fixes.

## Verdict: PASS (2 confirmed → both fixed; across 2 review passes)

- **Pass 1** (`we7hbankn`, 5 agents — stage-correctness · two-window · memory-perf ·
  regression): **1 raised → 1 confirmed → fixed.**
- **Pass 2** (`wt28silw6`, confirmatory after the refine — paced-loop · timer-placement):
  **1 raised → 1 confirmed → fixed.** The timer-placement lens found **nothing** (the refine
  is clean).

Verified: workspace **181** tests; clippy clean (present/app/desktop/operator); both binaries
build.

## The refine — timer belongs on the stage/confidence monitor
A countdown is a **speaker aid**, so per the user's refine it now renders **only on the
stage/confidence monitor**, not the audience/program output. Removed the entire live-timer
overlay (`Presenter::show_timer`/`recompose_live`/`live_timer`, `compose_live`/
`timer_bar_layers`) and reverted `go_live`/`clear_live`/`blackout` to the clean audience
behavior. The timer still flows to the `StageDisplay` and the operator view (operators/CLI
still trigger and see it). Tests now assert the **stage shows the timer** (green/red) and the
**audience output never shows a timer**.

## Confirmed & fixed

### (two-window, low) — continuous-redraw had no throttle when a window can't present
Under `ControlFlow::Wait`, `about_to_wait` re-requested redraws on both windows every
iteration; the *only* pacing was the Fifo present block inside `render()`. When a surface
can't present (minimized/occluded — e.g. Windows DXGI occluded fast-return — or a
persistently lost surface), nothing throttled the loop → it **busy-spun a CPU core**. The
second window increased exposure.

### (paced-loop, low) — a naive deadline fix would starve on continuous input
The first fix (deadline-paced loop) as initially written recomputed `WaitUntil(now + FRAME)`
on every wake, but ticked/repainted only on `ResumeTimeReached`/`Init`. A stream of sub-16ms
input events (`WaitCancelled` — mouse-over, drag/resize) kept sliding the deadline so
`ResumeTimeReached` never fired → **both windows + the countdown froze until input stopped**
(self-healing within ~1 frame, no clock drift).

### The fix (both, combined)
A **fixed-schedule** paced loop:
- `next_frame: Option<Instant>` on `App`, advanced **only when a frame fires**.
- `new_events` fires a frame (tick + `request_redraw` on both windows) when the fixed
  deadline is reached (`ResumeTimeReached`/`Init`, or a `WaitCancelled` at/after the
  deadline), then sets `next_frame = now + FRAME`.
- `about_to_wait` sets `WaitUntil(next_frame)` — a **fixed** deadline, so continuous input
  can't push it forward, and the loop idles (no spin) when a window can't present.
- `render()`'s surface-lost path no longer self-requests a redraw (the paced frame retries).

## What passed clean (no findings)
- **Stage correctness:** `tick` refreshes the monitor only when the timer's displayed value
  changed or a command marked it dirty (`stage_dirty`), so it's not every frame; the idle
  timer view keeps the monitor non-blank; `stage_output` is a distinct surface from the
  audience output (tested).
- **Memory:** the gated recompose + the per-refresh slide clone are bounded; stage state is
  O(1); no growth.
- **Regression:** moving the tick into the paced loop keeps the countdown advancing, blackout
  intact, and the operator/remote path unchanged.
- **Timer placement (pass 2):** the audience output is free of the timer; `go_live`/`clear`/
  `blackout` match the pre-timer audience behavior; the operator view still carries the timer.

## Honest scope
The two windows + on-screen rendering are **compile-verified** (headless env, no display);
each `Renderer` uses its own wgpu device (fine for the walking skeleton). The stage/timer
**logic** is unit-tested. The paced-loop timing was additionally traced and adversarially
re-verified against winit 0.30 semantics.

## Independence statement
Reviewed across two fresh-context passes by agents that did not author the code; each finding
was adversarially verified (default `real=false`). Both confirmed defects were fixed and
re-verified (181/181, clippy clean); the second fix implements the reviewer's exact
prescription (fixed-schedule pacing) and was re-checked.
