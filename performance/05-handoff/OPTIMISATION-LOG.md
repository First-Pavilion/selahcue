# Optimisation Log

This was a **review**, not an optimisation engagement. No production code was modified, so no optimisation
is recorded as applied. This log states that explicitly and captures the *designed* (not-yet-applied)
optimisations so a future engineer can pick them up with a clear acceptance bar.

## Applied optimisations

None. Review-only scope.

## Designed / queued optimisations (not applied)

| ID | Change | Expected effect | Risk | Verification before/after |
| --- | --- | --- | --- | --- |
| PERF-1 | STT interim transcribes a fixed trailing window / newly-appended tail instead of the whole buffer | Per-utterance transcription work drops from ~6–7× real-time to ~1× + a small constant | Interim text could shift at window boundaries — must preserve segment semantics | RTF micro-benchmark; the two interim-streaming tests stay green |
| PERF-2 | Precompute per-verse token `BTreeSet` in `QuoteIndex` at build time | Removes up to 5000 `Vec`+`BTreeSet` allocations per final segment on a spike | Slightly larger resident index (bounded, already holds postings) | Allocation count before/after; match results identical (`test_quote_match`, `test_quote_detection`) |
| PERF-3 | Dirty-flag the framebuffer; skip `write_texture`+redraw when unchanged | Eliminates ~1 GB/s of idle upload across two windows on a static slide | Must still upload on resize/first-frame/content change | Parity + never-blank preserved; idle GPU/CPU drop visible in `make nfr` |
| PERF-4 | Separate lock/connection for read-only thumbnail/state polls | Control commands no longer queue behind a laggy poll | Two channels to manage | Latency of go-live under concurrent polling before/after |
| PERF-6 | Copy `live_output()` locally and drop the controller lock before `present()` | Removes up-to-one-vsync control stall | Extra frame copy per present (cheap) | Remote-command latency under continuous redraw before/after |

## Rationale for not applying now

- Every measured budget passes with a very large margin; none of these are needed to meet a current NFR.
- The owner asked for a **review** ("go through … and review the application performance"), and production
  fixes are owned by the domain engineers (ai / backend / graphics) per the performance-engineer role
  boundaries. Applying them here would silently expand scope and cross ownership.
- Each is filed as an owned follow-up in `DEFECTS-AND-FOLLOWUPS.md` with an acceptance bar, ready to schedule.
