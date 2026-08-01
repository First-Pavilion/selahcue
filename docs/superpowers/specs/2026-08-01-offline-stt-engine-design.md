# Design — Offline speech-to-text engine (`selahcue-stt`)

- Date: 2026-08-01
- ClickUp: [86ajtxzre](https://app.clickup.com/t/86ajtxzre) — On-device STT provider behind `TranscriptProvider` seam
- Epic: [86ajp08py](https://app.clickup.com/t/86ajp08py) — R3 · Transcription (STT)
- Governing ADRs: ADR-0010 (AI/provider abstraction), ADR-0019 (transcript-provider seam), ADR-0012 (model integrity, FR-156)
- Goal Contract: `docs/delivery/goals/TASK-86ajtxzre-offline-stt-engine.md`

## Problem

The live-transcript panel is fed by the `selahcue-core::transcript::TranscriptProvider`
seam, whose only implementation today is the deterministic `ManualProvider`. Build the
real **offline, on-device** STT engine behind the same trait, pumped into
`LiveController::ingest_transcript` out-of-band — with **no change to core, wire,
controller, or any UI** (ADR-0019 decision 3).

## Non-negotiable constraints (from ADRs/PRD)

- **Offline-first**, no cloud (ADR-0010 / FR-101). Runs with the network disabled.
- **AI is an assistant, never a gate** (FR-083 / NFR-024): the STT pipeline shares no
  fate with the render/output path; ingesting a flood leaves Live byte-identical.
- **No heavy STT dependency in `selahcue-core`** (ADR-0019 decision 2) → new isolated crate.
- **Bounded memory / no-leak** everywhere, asserted by tests.
- **Deterministic** core logic (no clock, no RNG in the tested path).
- **Model integrity** (FR-156 / ADR-0012): local model verified by pinned hash **before
  load**; mismatch refuses to load. Model file is **not committed**; delivery/update path
  is deferred (ADR-0012 → Stage-13).
- **Permissive-only licenses** (`deny.toml`): every new dependency must pass `cargo deny`.

## Architecture

New crate **`selahcue-stt`**, depending only on `selahcue-core`, **excluded from the
default workspace** (mirrors `selahcue-operator`) so the heavy native toolchain never
slows the green core tree.

### Pipeline (render-path-isolated)

```
mic ──cpal callback thread──▶ [bounded PCM ring (SPSC)]
                                     │  worker thread
                                     ▼
       resample → 16 kHz mono f32 → Vad gate (FR-102) → utterance accumulator
                                     │   (FeedbackGuard gates here, FR-172)
                                     ▼
                          Recognizer::transcribe(utterance) → segments
                                     ▼
                            [bounded segment queue]
                                     ▲
     TranscriptProvider::poll() ─────┘   (non-blocking drain by the host pump loop)
```

Every buffer is a hard-capped ring: a mic that never stops cannot grow memory. The
recognizer never blocks `poll()`; the render path never awaits STT.

### Interfaces (all trait-seamed so the whole pipeline is fake-testable)

| Trait / type | Real impl | Test double |
|---|---|---|
| `AudioSource` | `CpalSource` (feature `capture`) | `FakeAudioSource` (fixture PCM) |
| `Vad` | `EnergyVad` (pure Rust, energy/ZCR) | deterministic by construction |
| `Recognizer` | `WhisperRecognizer` (feature `whisper`, `whisper-rs`) | `FakeRecognizer` (canned) |
| `SttProvider: TranscriptProvider` | drains the segment queue in `poll()` | driven by fakes |
| `pump(provider, sink: FnMut(ProviderSegment))` | the missing host loop | fake sink |

- **Model integrity**: `verify_model(path, expected_sha256)` — SHA-256 the file, compare,
  refuse on mismatch. Pure Rust (`sha2`), tested with a tiny fixture.
- **Hardware probe** (FR-101): `HardwareProbe::detect()` reports acceleration
  (Metal/CUDA/Vulkan/CPU) + cores/RAM and selects a model variant + thread count within
  the ≤2 GB budget. Probe logic is unit-tested; the whisper backend consumes it.
- **Feedback guard** (FR-172): `FeedbackGuard(Arc<AtomicBool>)`; when the host signals app
  audio is on a shared output (`set_output_active(true)`), the worker drops captured audio
  so the app never transcribes itself. Guard + gate + tests now; the host *setting* the
  flag is a documented seam (host code, not UI).

### Threading & isolation

cpal callback → bounded SPSC PCM ring. A worker thread drains it, resamples, VAD-gates,
accumulates utterances, runs the recognizer, and pushes `ProviderSegment`s into a bounded
output queue behind a `Mutex`/channel. `poll()` non-blockingly drains that queue. The
recognizer running long or the model being absent never blocks or back-pressures the host.

## Features / dependencies

- Features: `capture` (cpal), `whisper` (whisper-rs); **default = none** → pure-Rust fakes,
  fast green CI. `sha2` (integrity) is always on.
- `cargo deny` gate: verify `whisper-rs`, `cpal`, `sha2`, and transitive licenses against
  the permissive-only allowlist. Its own `deny.toml` mirrors the operator crate.

## Testing (CI-green with zero native deps / no model)

- Deterministic pipeline: `FakeAudioSource` (speech + silence fixtures) → `EnergyVad` →
  `FakeRecognizer` → `SttProvider::poll()` yields the expected segments in order.
- VAD gates silence (non-speech frames produce no utterance).
- FeedbackGuard suppresses ingestion while output is active.
- Model integrity: correct hash loads, wrong hash refuses.
- Bounded-memory: flood the PCM ring and the segment queue → caps hold (no-leak).
- Pump loop: fake provider + fake sink → segments arrive exactly once.
- Whisper accuracy/latency stays **honestly spike-gated (S8/S11)** — not claimed here.

## Explicit non-goals (honest seams)

Model download/update path (ADR-0012 → Stage-13); transcript persistence/retention
(ADR-0007/FR-153); cloud STT + consent (FR-131–137); speaker labels / custom vocab
(FR-108/109); wiring the pump into `selahcue-desktop`/operator (host integration — would
touch host/UI); the Vosk backend (whisper.cpp is the primary).
