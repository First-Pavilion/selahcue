# Code Review — batch 7o: timers on the output

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context Workflow (`wgymksqae`, 7 agents). No self-approval.
**Date:** 2026-07-24
**Scope:** the timer overlay composition (`selahcue-present` `compose.rs`/`present.rs`),
the `LiveController` timer + `tick` (`selahcue-app`), the `TimerSnapshot` wire type
(`selahcue-lan`), the desktop tick, and the operator/CLI timer triggers.

## Verdict: PASS (2 confirmed → both fixed; 1 dismissed → improved anyway)

**3 findings raised → 2 confirmed → 2 fixed.** The **safety-critical blackout lens found
nothing** — the per-second recompose provably preserves an operator blackout (dedicated
test). Verified after fixes: workspace **181** tests; `selahcue-present` timer overlay +
blackout-preservation; `selahcue-app` timer lifecycle + **ceil** + **restart** regressions
+ a remote `start_timer` E2E; operator `cargo check` + clippy clean.

## Confirmed & fixed

### (timer-correctness, low) — countdown floored instead of ceiled
`TimerView::from_timer` derived `remaining_secs` via `Duration::as_secs()` (floor), so the
start value ("5:00") flashed for a single frame, the display read one second ahead all run,
and during the entire final second the bar showed **"0:00" while `time_up` was still false**
(internally inconsistent) with amber warn engaging ~1 s early.
**Fix:** ceil the remaining seconds — the start value now holds for the full first second
and `0:00`/`TIME UP` lands exactly at expiry (broadcast convention). Regression test
`countdown_display_ceils_seconds` ticks at sub-second offsets (which the original
integer-second test never exercised).

### (integration-staleness, low) — restarting a running timer reported a stale snapshot
`operator_view()` read the displayed fields from the cached `last_timer_view` but `running`
from the live `self.timer`; `StartTimer` replaced `self.timer` without resetting
`last_timer_view` (only `StopTimer` did). Restarting a running timer therefore returned the
**old remaining value + `running=false`** until the next tick.
**Fix:** `StartTimer` now clears `last_timer_view` (mirroring `StopTimer`), so the snapshot
is `None` between the restart and the next tick rather than an inconsistent mix. Regression
test `restarting_a_running_timer_does_not_report_stale_state`.

## Dismissed → improved anyway

### (timer-correctness) — overrun re-rasterized an identical frame every second
Verified accurate but immaterial (bounded, byte-identical, no leak): during TIME-UP overrun
`elapsed_secs` advanced each second, changing the recompose key and re-rendering the same
"TIME UP" frame. Since it's a trivially clean improvement, the recompose key now **ignores
`elapsed_secs` once timed up** (the label is the fixed "TIME UP"), so overrun sits truly
idle — no needless per-second work.

## What passed clean (no findings)
- **Blackout invariant (safety-critical):** every traced path — `blackout(true)`→tick,
  `go_live` (reveals), `clear`, un-blackout with a running timer, `StopTimer` while blacked
  out, key-quantized skipped recompose — preserves the blackout. The presenter tracks
  `live_blackout` and stamps `frame.blackout` on every recompose. Test
  `blackout_is_preserved_across_a_timer_recompose`.
- **Seizure-safety (FR-175):** the small (7% height) bottom bar, the one-way green→amber→red
  transition, and the solid (non-flashing) TIME-UP bar introduce no luminance flash hazard.
- **Bounded memory:** timer state is O(1) (`Option<Timer>` + `Option<TimerView>`); the
  continuous tick + per-second recompose accumulate nothing.

## Honest scope
The timer LOGIC is verified by unit + E2E tests; the on-screen rendering + Tauri UI are
compile/prior-verified (headless env). In the standalone (Local) operator fallback there is
no render loop, so the timer does not tick there — the real path is Remote (the output
window ticks each frame). Documented, not a defect.

## Independence statement
Reviewed by fresh-context agents that did not author the code. Each finding was
adversarially verified by a separate agent defaulting to `real=false`; the two that
survived were fixed with regression tests and re-verified (181/181, clippy clean).
