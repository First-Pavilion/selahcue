# Performance Goal Contract — PERF-REVIEW-2026-08

## Objective

Produce an evidence-backed verdict on whether current `main` (HEAD `dbd040e`) is free of memory leaks,
audience-visible lag, and material performance issues, sufficient to gate release.

## Baseline

Measured, not guessed — see `00-intake/SYSTEM-BASELINE.md`. Release build on Apple M5 / macOS 26.3.

## Scope

- Desktop Rust workspace: core, scripture, data, lan, engine, present, gpu, desktop, app, and the two
  excluded roots (operator, stt).
- Render/cue latency, memory bounds, concurrency/session lifecycle, at-rest encryption, STT real-time cost.

## Non-goals

- No production/hosted load testing (no hosted surface exists).
- No production-code optimisation (review-only; findings handed off with owners).
- No changes to the concurrent Design-2 workstream.

## Completion criteria (Boolean)

Each criterion has a verifier and an evidence location. All are `MET` unless marked as an approved exception.

| # | Criterion | State | Verifier | Evidence |
| --- | --- | --- | --- | --- |
| C1 | No unbounded collection on any hot or long-running path | MET | Independent hot-path scan + ~65 bounded/flood tests | `04-results/BOTTLENECK-ANALYSIS.md`, bounded suites |
| C2 | Slide/cue trigger latency within the release budget (150 ms) | MET | `go_live_slide_trigger_latency_is_within_budget` (release) | `04-results/BASELINE-REPORT.md` |
| C3 | Stage→Live at 1080p within the two-render ceiling (~300 ms) | MET (2.8 ms median) | `scripture_stage_to_live_latency_is_measured` (release) | `04-results/BASELINE-REPORT.md` |
| C4 | Longest-verse auto-fit still within trigger budget | MET | `go_live_latency_holds_for_the_longest_verse_auto_fit` (release) | `04-results/BASELINE-REPORT.md` |
| C5 | Keyword search within 500 ms | MET | `keyword_search_meets_the_500ms_budget` (release) | `04-results/BASELINE-REPORT.md` |
| C6 | GPU compositor matches CPU rasterizer (SSIM ≥ 0.99) | MET | `selahcue-gpu` `test_parity` (release) | `04-results/BASELINE-REPORT.md` |
| C7 | Concurrency: connections/sessions do not leak; half-open reaped; sessions capped | MET | `selahcue-lan --features server` E2E | `03-suite/TEST-INVENTORY.md` |
| C8 | STT real-time path bounded (segment queue, PCM ring, utterance force-close, backpressure drop) | MET | `selahcue-stt` bounded + pipeline tests | `04-results/BOTTLENECK-ANALYSIS.md` |
| C9 | Idle RSS ≤ 300 MB and cold start ≤ 3 s | APPROVED EXCEPTION (owner-run) | `scripts/measure_nfr.sh` (`make nfr`, needs display) | `05-handoff/RELEASE-RECOMMENDATION.md` |
| C10 | Findings triaged with severity + owner; none Critical/High | MET | This review | `05-handoff/DEFECTS-AND-FOLLOWUPS.md` |

## Independent verification

A fresh-context reviewer re-checked the conclusions against the actual test files and source, confirming:
the bounded-memory claims correspond to real caps and passing tests; the latency numbers are release-build
measurements; and the six findings are correctly characterised as non-blocking. See
`04-results/REGRESSION-DECISION.md` for the verification record. The exhaustive hot-path scan that seeded
the findings was itself an independent pass, separate from the reviewer that authored these artifacts.

## Evidence locations

- Latency / parity numbers: `04-results/BASELINE-REPORT.md`
- Memory / hot-path analysis: `04-results/BOTTLENECK-ANALYSIS.md`
- Test→scenario mapping + commands: `03-suite/TEST-INVENTORY.md`, `03-suite/EXECUTION-COMMANDS.md`

## Iteration / abort

- Maximum iterations: 1 review pass (no optimisation loop authorised).
- Abort conditions: discovery of a Critical/High leak or an over-budget audience-path latency would flip
  the terminal state to `FAILED` and open a blocking defect. Neither occurred.

## Terminal state

VERIFIED_COMPLETE — with one approved exception (C9, owner-run GUI NFRs). Decision recorded in
`05-handoff/RELEASE-RECOMMENDATION.md`.
