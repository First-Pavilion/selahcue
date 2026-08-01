# Goal Contract — TASK-86ajtxzre-offline-stt-engine

## Identity

- Goal ID: TASK-86ajtxzre-offline-stt-engine
- Parent goal ID: TASK-86ajtxuwr-live-transcript-scripture-detection
- Title: Offline on-device STT engine (`selahcue-stt`) behind the `TranscriptProvider` seam
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajtxzre
- Created: 2026-08-01
- Updated: 2026-08-01
- Maximum iterations: 12
- Independent verification required: yes

## Objective

A new, isolated `selahcue-stt` crate provides an offline speech-to-text engine that
implements `selahcue_core::transcript::TranscriptProvider` and can be pumped into
`LiveController::ingest_transcript` out-of-band — with the whisper.cpp backend and cpal
audio capture behind Cargo features, the whole pure-Rust pipeline (audio framing, VAD,
feedback guard, model integrity, hardware probe, provider, pump) deterministic and
bounded-memory tested green with zero native dependencies and no model file, and **no
change to `selahcue-core`, `-lan`, `-app`, `-operator`, or any UI**.

## Baseline

- The seam exists: `selahcue-core::transcript::TranscriptProvider { label(); poll() -> Vec<ProviderSegment> }`
  with the deterministic `ManualProvider` default (transcript.rs:147). `ProviderSegment`
  carries `{ text, start_ms, end_ms, is_final }`.
- Plug-in point: `LiveController::ingest_transcript` / `transcript_engine()` (controller.rs:565,571).
  No code drains a provider today — the host pump loop is the missing piece.
- No audio/STT code or dependency exists anywhere in the workspace (verified by search).
- `selahcue-operator` is already excluded from the default workspace as the pattern for a
  heavy-toolchain crate.

## Inputs and evidence sources

- ClickUp 86ajtxzre (scope), 86ajtxuwr (seam), epic 86ajp08py
- ADR-0010 (provider abstraction), ADR-0019 (seam realisation), ADR-0012 (model integrity FR-156)
- `selahcue-core/src/transcript.rs`, `selahcue-app/src/controller.rs`
- `docs/superpowers/specs/2026-08-01-offline-stt-engine-design.md`

## Scope

### In scope

- New `selahcue-stt` crate (excluded from the default workspace).
- `AudioSource` trait + `FakeAudioSource`; `CpalSource` behind feature `capture`.
- Fixed-ratio resample to 16 kHz mono f32 (pure Rust).
- `Vad` trait + `EnergyVad` (energy/ZCR gate, FR-102).
- `Recognizer` trait + `FakeRecognizer`; `WhisperRecognizer` behind feature `whisper` (whisper-rs).
- Model integrity: SHA-256 verify-before-load (FR-156); hardware probe + model select (FR-101).
- `FeedbackGuard` audio-feedback suppression (FR-172).
- `SttProvider` implementing `TranscriptProvider`; `pump()` host loop (closure sink).
- Deterministic + bounded-memory tests; `deny.toml` + `cargo deny` license gate.

### Non-goals

- Model download/update path (ADR-0012 → Stage-13); transcript persistence/retention;
  cloud STT + consent; speaker labels / custom vocab; wiring the pump into the desktop
  host or operator (host/UI); Vosk backend; verified whisper accuracy/latency (spike-gated S8/S11).

### Constraints

- Offline-first; AI never gates the render path (FR-083/NFR-024).
- No heavy dep in `selahcue-core`; no change to core/wire/controller/UI.
- Bounded memory, deterministic tested path; permissive-only licenses (`cargo deny`).

### Assumptions and unknowns

- ASSUMED: `whisper-rs` (MIT) and `cpal` (Apache-2.0) pass `deny.toml` — validated by C-010.
- UNKNOWN: real whisper accuracy/latency on target hardware — spike-gated (S8/S11), owner: Architect/QA.

## Dependencies and approvals

- Design approved by owner (o.majiyagbe) in session, 2026-08-01.
- Independent review: code-reviewer + qa-engineer + performance-engineer (this session, user-requested).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The `selahcue-stt` crate builds on the default (no-feature) profile and is excluded from the default workspace | `cargo build --manifest-path implementation/desktop/crates/selahcue-stt/Cargo.toml` | Compiles with no errors | build log | PASS |
| C-002 | yes | `SttProvider` implements `TranscriptProvider`; the fake pipeline (audio→VAD→fake recognizer→provider) yields the expected segments in order | `cargo test --manifest-path .../selahcue-stt/Cargo.toml pipeline` | test passes | test output | PASS |
| C-003 | yes | `EnergyVad` gates non-speech (silence frames produce no utterance/segment) | `cargo test --manifest-path .../selahcue-stt/Cargo.toml vad` | test passes | test output | PASS |
| C-004 | yes | `FeedbackGuard` suppresses ingestion while output is active (FR-172) | `cargo test --manifest-path .../selahcue-stt/Cargo.toml guard` | test passes | test output | PASS |
| C-005 | yes | Model integrity: matching SHA-256 loads, mismatch refuses (FR-156) | `cargo test --manifest-path .../selahcue-stt/Cargo.toml model` | test passes | test output | PASS |
| C-006 | yes | Bounded memory: flooding the PCM ring and segment queue keeps both at cap (no-leak) | `cargo test --manifest-path .../selahcue-stt/Cargo.toml bounded` | test passes | test output | PASS |
| C-007 | yes | `pump()` drains a provider into a sink; each final segment arrives exactly once | `cargo test --manifest-path .../selahcue-stt/Cargo.toml pump` | test passes | test output | PASS |
| C-008 | yes | `HardwareProbe::detect()` returns a model+thread selection within the ≤2 GB budget (FR-101) | `cargo test --manifest-path .../selahcue-stt/Cargo.toml probe` | test passes | test output | PASS |
| C-009 | yes | fmt + clippy clean on the default build | `cargo fmt --manifest-path .../selahcue-stt/Cargo.toml -- --check && cargo clippy --manifest-path .../selahcue-stt/Cargo.toml -- -D warnings` | no diffs, no warnings | command output | PASS |
| C-010 | yes | Dependency licenses (incl. feature deps whisper-rs/cpal) pass the permissive-only policy | `cargo deny --manifest-path .../selahcue-stt/Cargo.toml check licenses` | advisories/licenses OK (no denied license) | deny output | PASS |
| C-011 | yes | No change to core/wire/controller/operator/UI — additive crate only | `git diff --name-only main -- implementation/desktop/crates/selahcue-core implementation/desktop/crates/selahcue-lan implementation/desktop/crates/selahcue-app implementation/desktop/crates/selahcue-operator` | empty output | diff | PASS |
| C-012 | yes | Independent review + QA + performance verification pass with evidence | code-reviewer + qa-engineer + performance-engineer skills | no unresolved high/critical findings; memory bounded, no lag in render path | review/QA/perf reports | PASS |
| C-013 | no | `WhisperRecognizer` + `CpalSource` compile under their features on a machine with the toolchain/model | `cargo build --manifest-path .../selahcue-stt/Cargo.toml --features whisper,capture` | compiles (env-dependent; spike-gated) | `--features capture` type-checks (cpal, this host); `whisper` needs cmake (absent) | BLOCKED |

## Verification plan

- Focused verification: per-criterion `cargo test` filters on the `selahcue-stt` crate.
- Broader regression verification: `cargo test` on the default workspace stays green (crate is excluded → unaffected); C-011 proves no seam files changed.
- Independent verifier: code-reviewer + qa-engineer + performance-engineer (user-requested this session).
- Required environment: Rust stable; default build needs no native toolchain/model. C-013 needs whisper.cpp toolchain + a model (not in CI).

## Iteration ledger

### Iteration 1 — scaffold + full pipeline (C-001..C-011)

- Target criteria: C-001..C-011.
- Change: created `selahcue-stt` (excluded from the workspace); implemented audio/resample/VAD/recognizer/model-integrity/guard/provider/pump with FakeAudioSource + FakeRecognizer; whisper-rs/cpal behind features; deny.toml (+`Unlicense`, public-domain class); deterministic + bounded-memory tests.
- Verifiers executed: build ✓, 32 tests ✓, fmt ✓, clippy -D ✓, deny licenses ✓, seam-diff empty ✓.
- Evidence: commit `ec59eeb`.
- Decision: handoff to independent review (C-012).

### Iteration 2 — independent review/QA/perf + fixes (C-012)

- Target criterion: C-012.
- Investigation: three independent subagents (code-review, QA, performance) reviewed `ec59eeb`. No blockers; no memory leaks (16.7 h soak plateaued ~6.7 MB RSS); no render-path lag (`poll()` decoupled from capture/recognition). Findings: H1 vacuous test; M1 VAD ZCR inert; M2 verify-before-load convention-only; M3 budget not runtime-enforced; perf 30 s latency + buffer churn + O(n²) catch-up; L1/L2/L3/S1.
- Change: fixed all of the above (see commit `d993a9f`): ZCR default 0.02 + tests, `WhisperRecognizer::load` enforces `verify_model`, `select_model` enforces the ≤2 GB budget, buffer reuse + `VecDeque` frame_buf, 10 s force-close, sub-4 kHz rate clamp, `Send` assertion, strengthened the accumulator test.
- Verifiers executed: 35 tests ✓, fmt ✓, clippy -D ✓, deny licenses ✓, `--features capture` type-checks ✓, seam-diff empty ✓.
- Evidence: commit `d993a9f`.
- Decision: complete (all mandatory criteria PASS).

## Risks and rollback

- Risks: native feature deps (whisper-rs/cpal) may pull a denied transitive license (mitigated by C-010, run early); cpal on Linux needs alsa headers (mitigated: feature-gated, default off).
- Rollback or recovery: the crate is fully additive and outside the workspace; deleting the crate directory + spec/contract fully reverts with zero impact on the shipping app.

## Pause and escalation conditions

- If `cargo deny` flags a copyleft/denied transitive license on whisper-rs/cpal → pause, escalate dependency choice to Architect (do not weaken `deny.toml`).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajtxzre-offline-stt-engine.md --require-complete`
- Validator result: PASS (all 12 mandatory criteria PASS).
- Independent verification result: code-review (no blockers), QA (READY, all mandatory criteria PASS), performance (no memory leaks, no render-path lag) — all findings addressed in `d993a9f`.
- Terminal state: **VERIFIED_COMPLETE** (crate scope). Commits: `ec59eeb` (engine) + `d993a9f` (review fixes) on `main`.
- Remaining failed or blocked criteria: C-013 (non-mandatory) — `--features capture` type-checks on this host; the `whisper` native build needs cmake (absent) and its accuracy/latency stay spike-gated (S8/S11).
- Open follow-ups (documented non-goals, not blockers): host pump→`LiveController` wiring + `FeedbackGuard` set by the output subsystem; ratify `Unlicense` into the root/operator `deny.toml`; streaming interims for full ≤2 s latency; Vosk backend; model delivery/update path (Stage-13).
- ClickUp final evidence comment: posted to 86ajtxzre.
