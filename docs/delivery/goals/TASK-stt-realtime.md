# Goal Contract — TASK-stt-realtime

## Identity

- Goal ID: TASK-stt-realtime
- Parent goal ID: EPIC (Transcription & scripture intelligence) — STT engine 86ajtxzre
- Title: Make live transcription real-time — decode off the capture thread + sliding-window interims
- Role: backend/perf (cross-crate: selahcue-stt · selahcue-operator)
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: 86ajxemwu (bug — created at handoff)
- Related: 86ajvymgr (the earlier STT model-load/GPU fix — this addresses its documented follow-up)
- Origin: user bug report — "STT does not happen in real time. It sometimes freezes before continuing."
- Created: 2026-08-07
- Updated: 2026-08-07
- Maximum iterations: 10
- Independent verification required: yes (`make ci` + a `--features stt` build + bounded-memory test)

## Objective

Make the live transcript keep up with speech and stop freezing: recognition must not block audio
capture / the level meter, and the per-interim decode cost must stay bounded as an utterance grows.

## Baseline (Verified — root cause, systematic-debugging)

- **Recognition ran synchronously on the capture thread.** `SttEngine::process` (called in the
  operator's single worker loop) calls `emit_interim`/`close_utterance` → `Recognizer::transcribe`
  **inline** (`engine.rs`). While a decode ran, the loop did not drain the mic or emit the level →
  the UI/meter **froze**, and the mic ring dropped audio.
- **Interims re-decoded the whole growing utterance.** Each interim (~0.8 s) re-transcribed the
  entire open buffer (up to the 10 s force-close), so cost grew with the utterance — O(n²) over a
  monologue; the freezes worsened the longer someone talked.
- Constraint discovered: a macOS `cpal::Stream` is `!Send`, so the microphone source cannot be
  moved to another thread — the *source* must stay put and the *engine* (which is `Send`) moves.

## Scope

### In scope
- `selahcue-stt/src/engine.rs`: additive `EngineConfig.interim_max_samples` (default `0` = whole
  utterance, prior behaviour). When set, an interim decodes only the most-recent window (bounded
  work); the final on close still decodes the whole utterance. `emit_interim` windows the buffer
  and aligns the window start to a frame boundary. `bounded_memory.rs` literals updated for the
  new field.
- `selahcue-operator/src/listening.rs`: split the worker into a **source thread** (owns the
  `!Send` cpal stream — drains the mic into a bounded hand-off + emits the level meter, never
  blocks) and a **recognition thread** (owns the engine — runs `transcribe`). A bounded,
  drop-oldest `AudioHandoff` connects them so the source never blocks and the recognizer stays near
  the live edge. The engine config sets `interim_max_samples` to a ~6 s window.

### Non-goals (documented follow-ups)
- True streaming/incremental whisper decode (the window re-decodes recent audio rather than only
  the delta). Coalescing interims at the utterance level. Tuning the window/cadence per model tier.

### Constraints
- No-leak: the `AudioHandoff` is bounded (drop-oldest by sample count) with a bounded-memory test;
  the engine's utterance accumulator bound is unchanged. The pure deterministic pipeline + its
  existing tests are unchanged (the new config defaults to the prior behaviour). CI never builds the
  native STT toolchain (the `stt` feature is off in CI).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | An interim decodes at most the configured window; the final decodes the whole utterance | `cargo test -p selahcue-stt` | pass | `engine::tests::interim_window_bounds_the_decoded_samples_but_the_final_sees_the_whole_utterance` | PASS |
| C-002 | yes | The existing pipeline/behaviour is unchanged when the window is `0` (default) | `cargo test -p selahcue-stt` | pass | all prior engine + bounded_memory + pipeline tests still green (34/4/3) | PASS |
| C-003 | yes | Recognition runs on a separate thread from capture; the source (cpal `!Send`) stays put | code + build | decoupled | `listening.rs` source thread (mic + level) + spawned recognition thread (engine); compiles `--features stt` | PASS |
| C-004 | yes | The source→recognition hand-off is bounded (drop-oldest); never blocks capture | `cargo test --features stt` | bounded | `listening::tests::audio_handoff_is_bounded_drop_oldest` | PASS |
| C-005 | yes | The whole `stt` build compiles (whisper + Metal + the new threading) | `cargo check --features stt` | compiles | operator `--features stt` build exit 0 | PASS |
| C-006 | yes | Full CI gate green | `make ci` | ALL GREEN | `make ci` == **local CI gate: ALL GREEN** | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-stt` (engine window + no-regression); `cargo test --manifest-path
  .../selahcue-operator --features stt audio_handoff` (bounded hand-off); `cargo check --features stt`.
- Broader: `make ci`.
- Owner: `make launch`, Start listening, speak continuously — the meter stays live, the transcript
  updates without multi-second freezes, and a long monologue does not progressively lag.

## Iteration ledger

- Iter 1: systematic-debugging — inline decode on the capture thread (freeze) + O(n²) growing-buffer
  interims; macOS cpal `!Send` forces the source-stays/engine-moves split.
- Iter 2: additive sliding-window interim in the engine + operator source/recognition thread split
  with a bounded drop-oldest hand-off; engine + hand-off tests + `--features stt` build + `make ci` green.

## Risks and rollback

- Risk: the hand-off drops audio if the recognizer falls far behind (a genuinely slow decode).
  Mitigation: bounded ~5 s buffer so only pathological lag drops audio; a fast (GPU/small) model
  keeps up. Rollback: additive — revert to the single-thread worker.
- Risk: a windowed interim shows only recent words. Mitigation: the final on close decodes the whole
  utterance (full accuracy for scripture detection); the window is display/liveness only.

## Pause and escalation conditions

- Stop at `make ci` green + a `--features stt` build + owner run-time confirmation.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-stt-realtime.md --require-complete`
- Validator result: PASS
- Independent verification result: PASS — engine + hand-off bounded-memory tests, `--features stt`
  build, `make ci` GREEN.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted to 86ajxemwu; BUILD CONTROL 86ajnx548 updated.
