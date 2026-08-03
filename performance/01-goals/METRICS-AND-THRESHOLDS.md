# Metrics and Thresholds

Every metric below has an explicit **threshold**, a named **verifier**, and an **evidence** location.
Percentiles are release-build measurements at audience resolution unless noted.

| ID | Outcome | Boundary | Threshold | Percentile / aggregation | Verifier | Evidence | Result | Severity if failed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | Slide/cue trigger not perceptibly laggy | `Presenter::go_live()` compose+raster @1080p | ≤ 150 ms | worst single trigger | `go_live_slide_trigger_latency_is_within_budget` (release) | `04-results/BASELINE-REPORT.md` | PASS | High |
| M2 | Stage→Live from operator action | `LiveController::apply(Stage)`+`apply(GoLive)` @1080p | ≤ ~300 ms (2× trigger, two full renders) | median / p90 / max, n=25 | `scripture_stage_to_live_latency_is_measured` (release) | `04-results/BASELINE-REPORT.md` | PASS — median 2.8 ms, p90 3.4 ms, max 3.6 ms | High |
| M3 | Long-verse auto-fit path | Esther 8:9 (longest KJV verse) trigger @1080p | ≤ 150 ms | worst | `go_live_latency_holds_for_the_longest_verse_auto_fit` (release) | `04-results/BASELINE-REPORT.md` | PASS | High |
| M4 | Scripture keyword search responsive | `search()` full-scan worst case (~31k verses) | < 500 ms | worst | `keyword_search_meets_the_500ms_budget` (release) | `04-results/BASELINE-REPORT.md` | PASS | Medium |
| M5 | GPU output matches CPU reference (no divergent/blank frame) | Offscreen wgpu readback vs CPU raster | SSIM ≥ 0.99 | per frame | `selahcue-gpu` `test_parity` (release) | `04-results/BASELINE-REPORT.md` | PASS (2/2) | High |
| M6 | STT segment queue bounded | `SegmentSink` under host-never-polls flood | ≤ `MAX_PENDING_SEGMENTS` (256) | cap | `bounded_segment_queue_caps_when_host_never_polls` | `04-results/BOTTLENECK-ANALYSIS.md` | PASS | High |
| M7 | STT audio ring bounded | `PcmRing` under sample flood | ≤ `MAX_PCM_SAMPLES` | cap | `bounded_pcm_ring_caps_under_a_flood` | `04-results/BOTTLENECK-ANALYSIS.md` | PASS | High |
| M8 | Continuous speech can't grow the utterance buffer without bound | Utterance accumulator, no silence | force-closed at 10 s | cap | `bounded_utterance_accumulator_force_closes_continuous_speech` | `04-results/BOTTLENECK-ANALYSIS.md` | PASS | High |
| M9 | Transcript log bounded | `TranscriptLog` ring | ≤ `MAX_TRANSCRIPT_SEGMENTS` (240), text ≤ 2000 B | cap | core transcript bounded tests | `04-results/BOTTLENECK-ANALYSIS.md` | PASS | Medium |
| M10 | Detection queue + dedup bounded | `DetectionQueue`, `recent_refs` | ≤ 32 / ≤ 16 | cap | `engine_ingest_with_quotes_is_bounded_under_a_flood_of_candidates`, `recent_dedup_ring_is_bounded` | `04-results/BOTTLENECK-ANALYSIS.md` | PASS | Medium |
| M11 | Operator transcript view bounded per poll | `operator_view()` transcript tail | ≤ `OPERATOR_TRANSCRIPT_TAIL` (60) | cap | `operator_transcript_log_is_client_capped` | `04-results/BOTTLENECK-ANALYSIS.md` | PASS | Low |
| M12 | Render text caches bounded | `raster` `SwashCache`/`FontSystem` | rebuilt every `RESET_EVERY` (4096) renders | cap | `text_caches_stay_bounded_over_many_renders` | `04-results/BOTTLENECK-ANALYSIS.md` | PASS | Medium |
| M13 | Image decode cache bounded | media decode cache | bounded cap | cap | `the_image_decode_cache_stays_bounded` | `04-results/BOTTLENECK-ANALYSIS.md` | PASS | Medium |
| M14 | Connections don't leak server state | LAN server, many connect/disconnect | steady state | invariant | `connections_do_not_leak_server_state` | `03-suite/TEST-INVENTORY.md` | PASS | High |
| M15 | Half-open connections reaped | Stalled TLS handshakes | reaped within timeout | invariant | `stalled_half_open_connections_are_reaped` | `03-suite/TEST-INVENTORY.md` | PASS | High |
| M16 | Active sessions hard-capped | Session registry under flood | ≤ hard cap | cap | `active_sessions_are_hard_capped` | `03-suite/TEST-INVENTORY.md` | PASS | High |
| M17 | Presenter state bounded over long runs | Many stage/live cycles | steady state | invariant | `presenter_state_is_bounded_over_many_cycles` | `04-results/BOTTLENECK-ANALYSIS.md` | PASS | Medium |
| M18 | Idle memory | Live process at idle | ≤ 300 MB RSS | steady state | `scripts/measure_nfr.sh` | owner-run | APPROVED EXCEPTION — needs display | Medium |
| M19 | Cold start | Launch → first frame | ≤ 3 s | wall-clock | `scripts/measure_nfr.sh` | owner-run | APPROVED EXCEPTION — needs display | Medium |

## Notes on measurement boundary

- M1–M3 time **compose + CPU rasterize**, the deterministic part of the trigger. GPU present/OS swap is
  covered for correctness by M5 (parity), not timed — consistent with the desktop-authoritative,
  never-blank design where the CPU frame is always ready before present.
- No metric is reported as an average alone; M2 is a distribution (median/p90/max). Budget metrics are
  worst-case pass/fail, which is stricter than a percentile for a single-operator app.
