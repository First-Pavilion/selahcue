# Test Plan

## Strategy

Reuse the repository's existing performance-relevant suites — they already encode the product budgets and
memory invariants as deterministic pass/fail tests and run in `make ci`. Layer on top: (a) an exhaustive
independent static hot-path scan for anything the tests don't assert, and (b) release-build re-runs of the
latency/parity suites to capture real numbers at audience resolution.

## Test classes and how each owner concern is exercised

### 1. Lag / latency (owner: "no lags")

- **Slide-trigger budget** — `go_live_slide_trigger_latency_is_within_budget` (release, 150 ms).
- **Long-verse auto-fit** — `go_live_latency_holds_for_the_longest_verse_auto_fit` (release, 150 ms).
- **Stage→Live distribution** — `scripture_stage_to_live_latency_is_measured` (release, n=25, median/p90/max).
- **Keyword search** — `keyword_search_meets_the_500ms_budget` (release, 500 ms).
- **Render correctness on the fast path** — `selahcue-gpu` `test_parity` (SSIM ≥ 0.99).

### 2. Memory leaks (owner: "no memory leaks")

- **Flood every buffering site** — segment queue, PCM ring, utterance accumulator, transcript log,
  detection queue, dedup ring, operator transcript tail, text caches, image decode cache, presenter state.
- **Concurrency leak checks** — connections don't leak server state; half-open reaped; sessions capped.
- **Static confirmation** — independent hot-path scan confirms each cap corresponds to real code and that
  no hot/long-running collection is uncapped.

### 3. Performance issues generally (owner: "no performance issues")

- **Hot-path CPU/allocation audit** — one finding per genuine hot spot, ranked by product impact, each with
  `file:line` evidence and a cheaper alternative.
- **Lock-contention audit** — render-thread ↔ control-thread interactions on the critical path.

## Execution profile

- Latency/parity: `--release` (product NFRs are release budgets).
- Bounded/E2E/encryption/STT: default profile, feature-gated where required (`server`, `encryption`).
- Warm-up: each latency test warms glyph caches/buffers before timing steady state.
- Repetition: stage→live uses 25 warmed iterations; budget tests use worst-case single triggers.

## Out of plan (with reason)

- Hosted load / spike / soak against a server — no hosted surface exists.
- Live-process RSS / cold-start — deferred to owner-run `make nfr` (needs a display).
- Sampling-profiler flamegraphs — not decision-relevant at this gate; queued behind follow-ups #1/#2.
