# System Baseline (measurement environment)

## Build / source under assessment

| Field | Value |
| --- | --- |
| Repository | SelahCue (`implementation/desktop` Rust workspace) |
| Revision | `dbd040e` (`feat(stt): real-time streaming transcription (interim results)`) — tip of `main` |
| Build profile for latency numbers | `--release` (product NFRs are release-build budgets) |
| Toolchain | rustc 1.97.1 (8bab26f4f 2026-07-14) |
| Working tree | clean at measurement time |

## Hardware / OS (local measurement host)

| Field | Value |
| --- | --- |
| Machine | Apple M5 |
| CPU | 10 cores — 4 performance + 6 efficiency |
| Memory | 16 GB unified |
| OS | macOS 26.3 (Darwin 25.3.0) |
| Display | Headless for this session (no attached display) — bounds the GUI-dependent NFRs |

## Dataset / configuration

- Bundled public-domain scripture (WEB) — ~31 k verses, decoded once and cached (`selahcue-scripture`).
- Full-HD audience resolution (1920×1080) used for all render-path timing — the real audience size, not
  the 320×180 test helper (raster cost scales with pixel count).
- STT interim cadence as shipped: `interim_interval_frames = 40` (~0.8 s), utterance force-close at 10 s.
- Injected clocks throughout timing/animation code keep runs deterministic.

## Variance / method notes

- Latency figures are the **release** build's measured percentiles over 25 warmed iterations at 1080p
  (the `scripture_stage_to_live_latency_is_measured` audit), plus pass/fail budget tests in `selahcue-present`.
- Debug builds intentionally carry a generous latency tripwire (1500 ms single-slide, 2000 ms stage→live)
  because oversubscribed CI shared runners measure the runner, not the product; **release** enforces the
  real budgets (150 ms trigger, ~300 ms two-render stage→live). This review reports the release numbers.
- Bounded-memory and E2E suites are deterministic pass/fail and were run to completion, not sampled.

## What this baseline does and does not cover

- **Covers:** render/cue latency, render correctness (GPU↔CPU parity), memory bounds under flood,
  concurrency/session lifecycle, at-rest encryption, STT pipeline behaviour.
- **Does not cover (owner-run):** steady-state idle RSS and cold-start wall-clock — both require an
  attached display and are measured by `scripts/measure_nfr.sh` (`make nfr`).
