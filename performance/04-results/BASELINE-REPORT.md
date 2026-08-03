# Baseline Report

Revision `dbd040e`, release build, Apple M5 / macOS 26.3. This is the current-`main` baseline; because no
optimisation was applied, it is also the candidate (see `CANDIDATE-REPORT.md`).

## Latency — measured

### Stage→Live compose+render @ 1920×1080 (the audience-visible path)

`scripture_stage_to_live_latency_is_measured`, release, 25 warmed iterations:

```
[AUDIT] scripture stage->live compose+render @1920x1080: median=2.803875ms p90=3.407208ms max=3.648917ms (n=25)
```

| Statistic | Measured | Ceiling | Margin |
| --- | --- | --- | --- |
| median | 2.80 ms | ~300 ms (2× trigger, two full renders) | ~107× |
| p90 | 3.41 ms | ~300 ms | ~88× |
| max | 3.65 ms | ~300 ms | ~82× |

Each iteration does **two** full 1080p compose+renders (Stage→Preview, then GoLive→Live), so a single
trigger is roughly half of these numbers — comfortably inside the 150 ms single-trigger budget.

### Budget gates (release) — PASS

| Test | Budget | Result |
| --- | --- | --- |
| `go_live_slide_trigger_latency_is_within_budget` | 150 ms | PASS |
| `go_live_latency_holds_for_the_longest_verse_auto_fit` (Esther 8:9, longest KJV verse, auto-fit path) | 150 ms | PASS |
| `keyword_search_meets_the_500ms_budget` (full ~31 k-verse worst case) | 500 ms | PASS |

## Render correctness on the fast path — PASS

`selahcue-gpu` `test_parity`: **2 passed** — the wgpu compositor's offscreen readback matches the CPU
rasterizer at **SSIM ≥ 0.99** (plus device-loss recovery). The audience never sees a divergent or blank
frame relative to the CPU reference, upholding never-blank (NFR-024) on the GPU path. This gate **executed**
on the M5's GPU here (independently re-confirmed by the fresh-context reviewer). Caveat: on a box with no
usable GPU, `test_parity` *skips* rather than fails (per `CLAUDE.md`), so the parity signal is
hardware-dependent — it is a genuine PASS only where a GPU is present, as it was for this run.

## Memory bounds — PASS (no leak)

Every buffering site on a hot or long-running path is hard-capped and its flood test passes. Full list in
`BOTTLENECK-ANALYSIS.md` §"Verified well-bounded". Representative:

| Site | Cap | Test | Result |
| --- | --- | --- | --- |
| STT segment sink | `MAX_PENDING_SEGMENTS = 256` | `bounded_segment_queue_caps_when_host_never_polls` | PASS |
| STT PCM ring | `MAX_PCM_SAMPLES` | `bounded_pcm_ring_caps_under_a_flood` | PASS |
| STT utterance | 10 s force-close | `bounded_utterance_accumulator_force_closes_continuous_speech` | PASS |
| Transcript log | 240 segs / 2000 B each | core transcript bounded tests | PASS |
| Detection queue / dedup | 32 / 16 | `engine_ingest_with_quotes_...`, `recent_dedup_ring_is_bounded` | PASS |
| Render text caches | rebuilt every 4096 renders | `text_caches_stay_bounded_over_many_renders` | PASS |
| Image decode cache | bounded | `the_image_decode_cache_stays_bounded` | PASS |
| Presenter state | steady | `presenter_state_is_bounded_over_many_cycles` | PASS |

## Concurrency / streaming — PASS

Feature `server` loopback TLS E2E: `connections_do_not_leak_server_state`,
`stalled_half_open_connections_are_reaped`, `active_sessions_are_hard_capped`, plus the full remote-control
loop (`test_operator_remote`, `test_remote`) — all green. Wire messages capped at 64 KiB.

## At-rest encryption — PASS

`selahcue-data --features encryption` — SQLCipher open/migrate/backup suites green.

## Resource NFRs — measured (owner-run `make nfr`)

Run by the owner on a machine with a display (release build, Darwin arm64 / Apple M5). Both PASS with wide
headroom; this closed the sole prior exception.

| Metric | Threshold | Measured | Result |
| --- | --- | --- | --- |
| Cold start (M19) — launch → control-server-ready | ≤ 3.0 s | **1.56 s** | PASS (~1.9× headroom) |
| Idle RSS (M18) — max RSS over 5 s | ≤ 300 MB | **124.1 MB** | PASS (~2.4× headroom) |
| Slide-trigger (re-confirmed by the harness) | ≤ 150 ms | within budget | PASS |

Harness note: the `Terminated: 15` line in the `make nfr` output is the script sending SIGTERM to the
`selahcue-output` window after it finishes sampling RSS — expected teardown, not a failure. The results
print after it.
