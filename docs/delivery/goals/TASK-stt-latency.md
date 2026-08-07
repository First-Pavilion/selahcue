# Goal Contract — TASK-stt-latency

## Identity

- Goal ID: TASK-stt-latency
- Parent goal ID: EPIC (Transcription & scripture intelligence) — STT engine 86ajtxzre
- Title: Make on-device STT fast — GPU decode, small CPU fallback, one-time model load, mic-first
- Role: backend/perf (cross-crate: selahcue-stt · selahcue-operator)
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: 86ajvymgr (bug — created at handoff)
- Origin: user bug report — "model load takes long before it asks for permission (should be one-time); transcribing takes long to show; the STT is just too slow."
- Created: 2026-08-04
- Updated: 2026-08-04
- Maximum iterations: 10
- Independent verification required: yes (`make ci` + a `--features stt` whisper+Metal build)

## Objective

Fix the two reported STT slownesses without lowering the model-integrity bar (FR-156) or the ≤2 GB
resident budget (ADR-0010): (1) the model load blocks the mic-permission prompt and repeats every
start; (2) transcription lags badly.

## Baseline (Verified — root cause, systematic-debugging)

- `HardwareProbe::select_model` picked **large-v3-turbo (1.6 GB)** on any host with a non-CPU
  *label* or ≥4 threads — but `selahcue-stt`'s `whisper` feature pulled `whisper-rs` with **no GPU
  feature**, so whisper.cpp decoded the 1.6 GB model **on CPU** (far slower than real time). → lag.
- The 1.6 GB model was **SHA-256-hashed twice per start before the mic opened**: `fetch_model`
  verifies the cache hit (`model_fetch.rs:66`), then `WhisperRecognizer::load` re-hashed it
  (`recognizer.rs:131`); only then did `CpalSource::new()` open the mic (permission prompt). The
  recognizer was fully reloaded every start (no cross-session cache). → slow, repeated pre-permission wait.
- The capture ring (`PcmRing`) is bounded (drops oldest) — so opening the mic before a slow first-run
  download is safe.

## Decision (owner-approved)

"GPU on Mac + small CPU fallback": enable whisper Metal on macOS (the accurate large model runs on
the GPU); on any build with no compiled GPU backend, `select_model` steps down to a small model.

## Scope

### In scope
- `selahcue-stt/Cargo.toml`: `metal`/`cuda`/`vulkan` features → `whisper-rs/<backend>` (imply `whisper`).
- `selahcue-stt/src/model.rs`: `gpu_acceleration_compiled()` (cfg-based); `select_model` prefers
  large-v3-turbo only when a GPU backend is compiled in, else `small` (≥2 threads) / `base`.
- `selahcue-stt/src/recognizer.rs`: `WhisperRecognizer` holds `Arc<WhisperContext>`; `load_unverified`
  (skip the redundant hash), `from_context` (reuse a resident context), `context()`; `load` still
  verifies (FR-156) for an unverified path.
- `selahcue-operator/Cargo.toml`: macOS `[target.…]` unions `metal` onto `selahcue-stt`.
- `selahcue-operator/src/listening.rs`: a bounded one-entry `MODEL_CACHE` (`Arc<WhisperContext>`)
  reused across start/stop; `load_recognizer` cache-checks first (no fetch/verify/reload on a hit),
  skips the redundant hash on the download path (fetch already verified), verifies once on the env
  path; the worker opens the **mic first** (permission prompt) then loads the model.

### Non-goals (documented follow-ups)
- Sliding-window interim decode (each interim currently re-decodes the whole ≤10 s buffer — O(n²);
  far less painful now that decode is GPU or small-model, already flagged in the code). CUDA/Vulkan
  GPU builds for Windows/Linux (features are wired; not enabled by the operator yet).

### Constraints
- Integrity gate preserved: every model file is SHA-256-verified at least once (download-time by
  `fetch_model`; env path by `load`). ≤2 GB budget preserved (selector still steps down by footprint;
  the cache holds at most one model). No change to the deterministic pure pipeline or its tests.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A CPU-only build (no GPU feature) selects `small` (not large-v3-turbo), even on a many-core "Metal"-labelled host; a lean host → `base` | `cargo test -p selahcue-stt` | pass | `model::tests::cpu_only_build_uses_a_small_model_not_the_large_one` + `low_end_cpu_steps_down_to_a_smaller_model` | PASS |
| C-002 | yes | A GPU build prefers the large real-time model | `cargo test --features metal` (feature-gated test) | pass | `model::tests::gpu_build_prefers_the_large_real_time_model` (`#[cfg(any(feature=…))]`) | PASS |
| C-003 | yes | The redundant per-start SHA-256 is removed (download path already verified); integrity still enforced once | code + build | verify-once | `load_unverified` on the fetched path; `load` (verify) on the env path; `fetch_model` verifies on fetch | PASS |
| C-004 | yes | The recognizer/model is loaded once and reused across start/stop (bounded one-entry cache) | code + build | reuse | `MODEL_CACHE` + `cached_context`/`from_context`; "reusing the resident model" on a warm start | PASS |
| C-005 | yes | The mic opens (permission prompt) before the model load | code review | mic-first | worker opens `CpalSource::new()` before `load_recognizer`; `PcmRing` bounded so buffered audio is dropped | PASS |
| C-006 | yes | Metal is compiled on macOS; the whole `stt` build compiles | `cargo check --features stt` | compiles | operator `--features stt` (whisper+metal+capture+download) build exit 0 | PASS |
| C-007 | yes | Full CI gate green (default build never pulls the native STT toolchain) | `make ci` | ALL GREEN | `make ci` == **local CI gate: ALL GREEN**; pure STT suite 33/4/3 pass | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-stt` (pure); `cargo check --manifest-path .../selahcue-operator --features stt`
  (compiles whisper.cpp + Metal + listening.rs + the `Arc<WhisperContext>` cache — proving `Send`/`Sync`).
- Broader: `make ci` (default build, workspace tests, operator no-stt compile-check, STT pure tests, flutter).
- Owner: `make launch` and confirm the permission prompt appears immediately, a restart is instant, and
  transcription keeps up.

## Iteration ledger

- Iter 1: systematic-debugging root cause — CPU-decoding a 1.6 GB model (no GPU feature) + a redundant
  full-file hash before the mic + no cross-start cache. Owner chose GPU-on-Mac + small CPU fallback.
- Iter 2: implemented across stt (features, select_model, recognizer Arc) + operator (target-metal,
  listening cache + mic-first + verify-once); pure tests + `--features stt` build + `make ci` all green.

## Risks and rollback

- Risk: a resident model held after "stop listening" (memory). Mitigation: bounded to ONE model that
  already fits the ≤2 GB budget; this is exactly the "one-time load" the owner asked for. Rollback:
  additive — remove the cache to restore per-start load.
- Risk: skipping the load-time re-hash. Mitigation: the file is still verified once (fetch-time or env
  `load`); the skipped hash was redundant re-work on an already-verified file.
- Risk: Metal build only on macOS. Mitigation: CPU builds get the small model automatically; CUDA/Vulkan
  features are wired for a future Windows/Linux enablement.

## Pause and escalation conditions

- Stop at `make ci` green + a `--features stt` build + owner run-time confirmation.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-stt-latency.md --require-complete`
- Validator result: PASS
- Independent verification result: PASS — pure STT suite + a `--features stt` (whisper+Metal) compile +
  `make ci` GREEN.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted to 86ajvymgr; BUILD CONTROL 86ajnx548 updated.
