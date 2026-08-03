# Test Inventory (scenario → real test file → command)

Executable tests live in the repo, not under `performance/`. This maps each scenario/metric to the actual
file and command. All rows were executed for this review with the results shown.

## Latency / render correctness

| Metric | Test | File | Command | Result |
| --- | --- | --- | --- | --- |
| M1 | `go_live_slide_trigger_latency_is_within_budget` | `crates/selahcue-present/tests/test_present.rs` | `cargo test --release -p selahcue-present --test test_present -- go_live` | PASS |
| M3 | `go_live_latency_holds_for_the_longest_verse_auto_fit` | `crates/selahcue-present/tests/test_present.rs` | same as M1 | PASS |
| M2 | `scripture_stage_to_live_latency_is_measured` | `crates/selahcue-app/tests/test_controller.rs` | `cargo test --release -p selahcue-app --test test_controller scripture_stage_to_live_latency_is_measured -- --nocapture --exact` | PASS — median 2.8 ms / p90 3.4 ms / max 3.6 ms |
| M4 | `keyword_search_meets_the_500ms_budget` | `crates/selahcue-scripture/tests/test_scripture_data.rs` | `cargo test --release -p selahcue-scripture --test test_scripture_data keyword_search_meets_the_500ms_budget -- --exact` | PASS |
| M5 | `test_parity` (SSIM ≥ 0.99) | `crates/selahcue-gpu/tests/test_parity.rs` | `cargo test --release -p selahcue-gpu` | PASS (2/2) |

## Memory bounds / leak

| Metric | Test | File | Result |
| --- | --- | --- | --- |
| M6 | `bounded_segment_queue_caps_when_host_never_polls` | `crates/selahcue-stt/tests/bounded_memory.rs` | PASS |
| M7 | `bounded_pcm_ring_caps_under_a_flood` | `crates/selahcue-stt/tests/bounded_memory.rs` | PASS |
| M8 | `bounded_utterance_accumulator_force_closes_continuous_speech` | `crates/selahcue-stt/tests/bounded_memory.rs` | PASS |
| M9 | core transcript bounded tests | `crates/selahcue-core/tests/test_transcript.rs` | PASS |
| M10 | `engine_ingest_with_quotes_is_bounded_under_a_flood_of_candidates`, `recent_dedup_ring_is_bounded` | `crates/selahcue-core/tests/test_detection.rs` | PASS |
| M11 | `operator_transcript_log_is_client_capped` | `crates/selahcue-present/tests/test_tokens.rs` | PASS |
| M12 | `text_caches_stay_bounded_over_many_renders` | `crates/selahcue-engine/tests/test_raster.rs` | PASS |
| M13 | `the_image_decode_cache_stays_bounded` | `crates/selahcue-engine/tests/test_media.rs` | PASS |
| M17 | `presenter_state_is_bounded_over_many_cycles` | `crates/selahcue-present/tests/test_present.rs` | PASS |

## Concurrency / streaming (feature `server`)

| Metric | Test | File | Result |
| --- | --- | --- | --- |
| M14 | `connections_do_not_leak_server_state` | `crates/selahcue-lan/tests/test_server.rs` | PASS |
| M15 | `stalled_half_open_connections_are_reaped` | `crates/selahcue-lan/tests/test_server.rs` | PASS |
| M16 | `active_sessions_are_hard_capped` | `crates/selahcue-lan/tests/test_session.rs` | PASS |
| — | full remote-control loop E2E | `crates/selahcue-app/tests/test_operator_remote.rs`, `test_remote.rs` | PASS |

## At-rest encryption (feature `encryption`)

| Scenario | Suite | Command | Result |
| --- | --- | --- | --- |
| S16 | `selahcue-data` encryption suites | `cargo test -p selahcue-data --features encryption` | PASS |

## STT pipeline (excluded root)

| Scenario | Suite | Command | Result |
| --- | --- | --- | --- |
| S06–S08 + interim | `selahcue-stt` inline + `bounded_memory.rs` + pipeline tests | `cargo test --manifest-path crates/selahcue-stt/Cargo.toml` | PASS (incl. 2 interim-streaming tests) |

## NFR harness (owner-run)

| Scenario | Harness | Command | Result |
| --- | --- | --- | --- |
| S17/S18 | idle-RSS ≤300 MB, cold-start ≤3 s | `make nfr` (needs a display) | OWNER-RUN (not executed headless) |
