# Run Index

Chronological record of the runs backing this review. Host: Apple M5 / macOS 26.3, rustc 1.97.1,
revision `dbd040e`.

| Run | Suite / command | Profile | Key result |
| --- | --- | --- | --- |
| R1 | `scripture_stage_to_live_latency_is_measured -- --nocapture` | release | median 2.80 ms / p90 3.41 ms / max 3.65 ms (n=25); 1 passed |
| R2 | `selahcue-present --test test_present -- go_live` | release | 4 passed (incl. slide-trigger + long-verse auto-fit ≤150 ms) |
| R3 | `selahcue-scripture --test test_scripture_data keyword_search_meets_the_500ms_budget` | release | 1 passed (<500 ms) |
| R4 | `selahcue-gpu` | release | `test_parity` 2 passed (SSIM ≥ 0.99) |
| R5 | `selahcue-core` (all suites) | release | all green — detection bounded, transcript, dedup |
| R6 | `selahcue-lan --features server` (E2E) | default | server/session/pairing/protocol/rbac/remote green; no state leak, half-open reaped, sessions capped |
| R7 | `selahcue-app --features server` (E2E) | default | controller/operator_remote/operator/quote_detection/remote green |
| R8 | `selahcue-data --features encryption` | default | SQLCipher open/migrate/backup green |
| R9 | `selahcue-stt` (manifest) | default | pipeline + `bounded_memory.rs` + 2 interim-streaming tests green |
| R10 | Independent hot-path / unbounded-collection scan (fresh-context) | n/a | No leak; 6 findings triaged (`BOTTLENECK-ANALYSIS.md`) |
| R11 | Independent artifact/decision verification (fresh-context, tasked to refute) | release + static | Verdict DECISION_SOUND; reproduced median 2.566 ms / p90 2.835 ms / max 3.134 ms; `test_parity` executed+passed on M5 GPU; `leak_refutation: null`; 3 minor non-refuting risks (`REGRESSION-DECISION.md`) |

## Owner-run (completed)

| Run | Command | Result |
| --- | --- | --- |
| R12 | `make nfr` (release, Apple M5, with display) | cold start **1.56 s** (≤3.0), idle RSS **124.1 MB** (≤300), slide-trigger within 150 ms — all PASS |

## Variance notes

- Latency runs are single-invocation but each internally warms caches and reports a 25-sample distribution
  (R1) or worst-case budget gate (R2/R3). The margins (≥80×) far exceed any run-to-run noise, so a single
  release run is decision-sufficient.
- Bounded/E2E runs are deterministic pass/fail; repetition would not change the signal.
