# Performance Risk Matrix

Risks ranked by product impact. "Never-blank" (NFR-024) makes render-path stalls a correctness risk, so
they rank above pure efficiency concerns even when currently within budget.

| ID | Risk | Likelihood | Impact | Exposure | Mitigation / current state | Residual |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | A render-path lock stalls the control thread, delaying a go-live/blackout during service | Low | High | Medium | Controller mutex is held across the wgpu present for up to one vsync (`main.rs:1432`→`:1454`, Fifo); tokio mutex on remote path never blocks an OS thread | Accept (LOW finding #6/#4); optional split documented |
| R2 | STT interim re-transcription saturates CPU on a weak host, starving other work | Medium | Medium | Medium | Runs on a dedicated worker thread, out-of-band from render; bounded by 10 s force-close; cannot blank output | Accept as MEDIUM follow-up #1; sliding-window optimisation designed |
| R3 | An unbounded queue/cache grows during a long service and exhausts memory | Low | High | Low | Every hot/long-running collection is hard-capped with a bounded test (M6–M17); independent scan found none uncapped | Closed |
| R4 | Slide/cue trigger drifts over budget as themes/auto-fit grow | Low | High | Low | Release budget tests (M1, M3) gate this in CI; measured ~2.8 ms vs 150 ms | Closed (huge margin) |
| R5 | GPU compositor diverges from CPU reference and shows a wrong/blank frame | Low | High | Low | SSIM ≥ 0.99 parity oracle (M5) gates every frame shape | Closed |
| R6 | Fuzzy quote matcher spikes CPU/allocations on a pathological transcript | Low | Medium | Low | Bounded by `MAX_CANDIDATES` (5000) + discriminative-token thresholds; runs at final-segment cadence, off the render path | Accept as MEDIUM follow-up #2 |
| R7 | Idle memory / cold start exceed NFR on the real GUI build | — | Medium | — | Measured via owner-run `make nfr`: idle RSS 124.1 MB (≤300), cold start 1.56 s (≤3) | Closed — both PASS with wide headroom |
| R8 | LAN peer floods connections/sessions to exhaust the operator | Low | High | Low | Half-open reaping, hard session cap, 64 KiB message cap (M14–M16) | Closed |
| R9 | Manual/host-injection provider (`ManualProvider.pending`) grows if a caller submits without polling | Low | Low | Low | Test/host-injection path only, not a production ingest source | Accept (minor note); one-line bound if it ever backs real ingest |

## Risk-acceptance summary

- **Closed** (verified mitigated): R3, R4, R5, R7, R8.
- **Accepted follow-ups** (non-blocking, owned): R1, R2, R6, R9.
