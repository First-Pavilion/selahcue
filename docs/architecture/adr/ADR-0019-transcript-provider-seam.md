# ADR-0019: Transcript-provider seam + scripture-detection engine (R3/R4 realisation)

- **Status:** Accepted
- **Date:** 2026-07-31
- **Confidence:** High (the seam shape + determinism/bounded invariants are structural and test-verified). This is **not** a claim about STT/detection *accuracy or latency*, which stay provisional and spike-gated (S8/S11), exactly as ADR-0010 records.
- **Owner:** Backend Engineer (delivery slice), under Software Architect's ADR-0010.
- **Realises:** ADR-0010 (AI/provider abstraction — the governing decision). **Related:** ADR-0008 (LAN/RBAC), ADR-0007 (persistence — the deferred retention seam), ADR-0015 (injected-clock determinism).
- **ClickUp:** story 86ajtxuwr. **Goal Contract:** `docs/delivery/goals/TASK-86ajtxuwr-live-transcript-scripture-detection.md`.

---

## Context

ADR-0010 decided *that* SelahCue has a local-first, out-of-band, operator-confirmed `STTProvider` abstraction with scripture detection built on the transcript. This ADR records the **concrete realisation** of the R3 (live transcript) + R4 (scripture detection → approval queue) vertical slice, and the specific engineering decisions made — the ones a future maintainer needs to understand the seam and its deliberate limits. The operator's `Live transcript` panel and `Recent detections` placeholder were stubs; this slice makes them a working, end-to-end feature.

## Decisions

1. **The transcript-provider seam lives in `selahcue-core::transcript` as the `TranscriptProvider` trait** (`fn poll(&mut self) -> Vec<ProviderSegment>` + `label()`), producing bounded, timestamped `TranscriptSegment`s into a hard-capped `TranscriptLog`. Core stays pure and I/O-free (it reads no clock — timestamps are injected), so the whole engine is exhaustively unit-testable and deterministic (ADR-0015 spirit; NFR-014).

2. **The always-present default provider is `ManualProvider`** — a deterministic queue of operator/host-injected text. This is the offline, zero-dependency baseline ADR-0010 requires ("local default always present"), and it is what the tests and the standalone operator use. **No heavy STT model/runtime is wired into core or the build.**

3. **Real on-device STT (whisper.cpp / Vosk) is a documented pluggable follow-up behind the same trait** — it implements `TranscriptProvider` and the host pumps it into the controller's engine out-of-band, with **no change to the wire, the controller command surface, or the presentation core**. This is the ADR-0010 pluggability property, demonstrated by the `ManualProvider` seam. Follow-up ticket tracks the on-device engine (packaging, model integrity FR-156, VAD FR-102, the audio-feedback guard FR-172).

4. **Detection reuses the existing parser — it does not reinvent reference parsing.** `selahcue-core::detection::detect` normalises spoken language (spelled-out numerals incl. hundreds → digits; "chapter"/"verse" filler dropped; "X through Y" ranges joined) into candidate token windows and hands each to `selahcue_core::scripture::parse_one`. The parser *is* the book-name authority (unknown leading book → rejected), so non-references never survive; a ≥3-alphabetic-char precision floor suppresses the parser's two-letter typing aliases (`is`/`so`/`am`) firing on ordinary speech (precision over recall, FR-121). Detection is a **pure function** → deterministic.

5. **Bounded everything (no-leak invariant).** `TranscriptLog` (cap `MAX_TRANSCRIPT_SEGMENTS`, per-segment text cap), the cross-segment dedup ring, and the `DetectionQueue` (cap `MAX_DETECTIONS`) are all hard-capped ring structures; the operator view carries only a bounded tail. Bounded-memory tests assert a flood cannot grow any of them.

6. **Operator-confirmed, never auto-live (FR-115).** A detection surfaces in an approval queue; `ApproveDetection` stages the verse in **Preview** (the operator Goes Live when ready) via the *existing* scripture-slide path; `DismissDetection` drops it. The AI path is strictly out-of-band: ingesting transcript — even a 500-segment flood — leaves the Live output byte-identical (verified), honouring FR-083 / NFR-024 ("AI never blanks Live").

7. **Wire is additive and VERSION-stable (v2).** New `Command::{IngestTranscript,ApproveDetection,DismissDetection}` and additive `OperatorStateView.{transcript,detections}` all use `skip_serializing_if`, so the pinned cross-language v2 fixtures stay byte-identical. A new `Permission::Transcribe` gates ingestion (Operator/Producer); approve/dismiss reuse `SearchScripture` (staging privilege). No migration, no VERSION bump.

## Deliberate non-goals / seams (carried honestly)

- **On-device STT engine** (whisper/Vosk) — the pluggable provider (decision 3); this slice ships the `ManualProvider` default + injected feed.
- **Transcript persistence + retention/deletion** (ADR-0007, FR-153) — the transcript + queue are **in-memory only** this slice (not in the crash-recovery snapshot). Sensitive-data-at-rest, retention, and reliable deletion are a follow-up on the persistence seam.
- **Cloud STT adapters + consent gating** (FR-132/133/134/135), **audio-feedback guard** (FR-172), VAD/custom-vocabulary/speaker-labels, verbatim captioning to audience (FR-166), and **confidence scoring / evaluation corpora** (S11/FR-171) — all remain ADR-0010 seams, unchanged.

## Consequences

- The operator gets a working live-transcript panel + one-tap scripture approval queue **today**, offline, deterministic, and bounded — with the automatic on-device STT slotting in behind a stable trait later, no re-platforming.
- Detection quality is bounded by the parser + normaliser (spoken numerals to ~999, the 66-book canon, precision floor); it is intentionally precision-biased and operator-confirmed, so false positives are dismissed, never displayed.
- Because everything is additive and in-memory, the slice carries **zero** wire/persistence-compat risk; reverting the branch fully restores the prior honest-empty panels.
