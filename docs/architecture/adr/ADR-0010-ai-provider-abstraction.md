# ADR-0010: AI / provider abstraction

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** High (the abstraction pattern: local-first capability interfaces + pluggable consent-gated cloud adapters + isolation from the presentation core). This confidence is about the **architecture**, not about AI accuracy or latency, which are provisional and separately gated by S8/S11 (see Fallback/validation).
- **Validating spike:** S8 (offline transcription + scripture-detection latency on target CPU/GPU); cross-references S11 (AI evaluation-set definition, FR-171)
- **Owner:** Software Architect
- **Related:** ADR-0001 (Rust core / split topology), ADR-0002 (wgpu compositor + output-failure isolation), ADR-0007 (persistence — `provider_consent`, retention, at-rest encryption), ADR-0008 (LAN security — OS secret store, RBAC, audit), ADR-0011 (observability — redacted diagnostics, opt-in telemetry), ADR-0012 (packaging & updates — local-model integrity)

---

## Context

From R3 onward SelahCue gains AI capabilities — speech-to-text transcription (R3), scripture detection built on the transcript (R4), and sermon-note generation (R5). These capabilities are optional assistants layered onto a product whose core value (slides, local scripture, media, timers, blackout/clear, stage/confidence outputs) must remain fully operable with **zero** network, cloud, mobile, or AI (NFR-015, CON-2). The forces that shape how AI is wired in come directly from the PRD and the feasibility evidence:

1. **AI is an assistant, never a gate (a hard architectural invariant).** FR-083 requires that no AI/transcription/provider failure blocks slide, scripture, or timer control; the failure-isolation is carried at MVP by NFR-024 and becomes meaningfully testable at R3 when the AI subsystems land (verified by fault-injection). NFR-024 names AI explicitly as one of the failures that must never blank or clear live output as a side effect. Architecture §1 principle 4 states it plainly: "AI runs out-of-band and is operator-confirmed." This is the single non-negotiable force on the design — it forbids any topology in which the render/output path awaits, shares fate with, or is back-pressured by AI work.

2. **Offline-first by default (privacy and reliability, not just performance).** Transcription must run offline by default (FR-101, "Whisper family," with a hardware probe that auto-selects a real-time-capable model). Sermon audio, transcripts, and notes are sensitive personal data under NDPA 2023 + GDPR (PRD §Privacy); CON-5 requires that no sermon audio/transcript/notes leave the host without explicit user action. A local default is therefore not an optimisation — it is the privacy-preserving and connectivity-independent baseline the product is built around.

3. **Cloud is opt-in, per-provider, consent-gated, and disclosed.** Cloud STT/notes providers must be OFF by default and enabled per provider only after an opt-in that names the provider, states what data is sent, and states that data leaves the local network/jurisdiction (FR-132, NFR-018, CON-5, threat T10). A live "cloud active" indicator must show whenever data is transmitting (FR-133). Keys are user-supplied and stored only in the OS secret store (FR-134). Consent and retention state are persisted, auditable, and Administrator-gated (FR-137). Enabling any cloud provider requires DPA + cross-border-transfer handling (FR-177) and surfaces usage/cost/retention disclosure (FR-136).

4. **Graceful fallback that never interrupts live output.** On cloud error or network loss, the system must fall back to the local provider with bounded retry-with-backoff and a defined failover order for multi-provider configs, degrading transcription quality if necessary but never blanking output (FR-135, CON-2).

5. **Pluggability without touching the core flow.** The product needs a provider abstraction per capability (STT and note-generation) such that switching provider requires no change to the core presentation flow, with the local default always present (FR-131, "local default always present"). This must hold across the whole roadmap (STT R3 → detection R4 → notes R5) so the AI surface can grow without re-platforming.

6. **Realistic-capability posture and operator-in-the-loop.** AI must not claim perfect accuracy (FR-120); scripture detection defaults to operator-confirmation (FR-115), precision-over-recall (FR-121); note generation must disclose fabrication risk (FR-128). The abstraction must make it structurally easy to keep a human in the loop and to keep AI output off the audience screen unless explicitly opted in (verbatim captioning OFF by default, FR-166).

7. **Subsystem-internal safety: the audio-feedback guard.** While app-emitted media/alert audio (FR-063/068/069) is routed to a shared/house output, transcription ingestion must be suppressed/paused and scripture-detection firing gated, or the app will transcribe its own output and self-trigger (FR-172, MAJOR-08). This is a concern the AI subsystem owns internally; it must have the hooks to observe app-audio state without coupling to the render path.

8. **Resource discipline.** Models load lazily and are bounded (Architecture §1 principle 6; NFR-003). The transcription model must stay resident within budget (~≤2 GB; whisper large-v3 Turbo is ~1.6 GB INT8 per FEASIBILITY §8 #4 / [W2]).

**Evidence base.** FEASIBILITY §9 leans (non-binding) to "whisper.cpp (cross-platform, Metal/CUDA/Vulkan/CPU) [W2] ... as local defaults with provider abstraction (RP-03/05/06)." §8 records whisper large-v3 Turbo at ~1.6 GB INT8 (#4, DOCUMENTED Med) and streaming latency "0.5–2 s behind live" (#9, DOCUMENTED Med [W2]); scripture-detection incremental latency (#10) is INFERRED (Low). The AI accuracy targets themselves (FR-102 ≤1% non-speech committed; FR-121/METRIC-009 ≤5% false-positive) are **provisional**, unverifiable until the FR-171 evaluation corpora exist (S11), and ratified only after Stage-10 measurement. FEASIBILITY records **zero OBSERVED findings** — nothing was executed in the discovery environment — which is precisely why S8 exists. The confidence in this ADR is therefore deliberately scoped to the abstraction pattern, which is a well-established, low-risk architectural idiom, and **not** extended to the AI quality numbers.

> **Note on scope.** This ADR decides the *provider abstraction and isolation* for the AI subsystem. It does **not** ratify the AI accuracy/latency thresholds (those are PRD/Stage-10 items gated by S8/S11), nor the local NoteGen model family beyond "llama.cpp-class local LLM" (an R5 concern; see below). TTS is out of scope entirely — it is a non-goal (NG-1); FEASIBILITY's mention of Piper [TT1] is not adopted.

## Options considered

### Option A — Local-first capability interfaces with pluggable consent-gated cloud adapters (chosen)

Define capability interfaces `STTProvider` and `NoteGenProvider`. A **local implementation is always present and is the default** (whisper.cpp for STT; a llama.cpp-class local LLM for NoteGen). Cloud adapters implement the same interfaces, are OFF by default, and are enabled per provider only through consent gating. The whole subsystem runs out-of-band from the render/output path behind an operator-confirmation surface.

**Pros (grounded in the evidence):**
- **Directly satisfies the hard invariant (FR-083 / NFR-024).** Because a local provider is always present and the subsystem is isolated behind the AI-orchestration component (Architecture §4/§10), a provider (local or cloud) that stalls, errors, or is disabled cannot block core controls or blank output — there is always a resident local path, and the render loop never awaits it.
- **Offline by default, for free (FR-101, CON-2, NFR-015).** The default path requires no network; whisper.cpp is cross-platform (Metal/CUDA/Vulkan/CPU) and fits the resident-memory budget (~1.6 GB INT8 [W2], within the ≤2 GB target #4). Church deployments with hostile/absent Wi-Fi still get transcription.
- **Privacy is the default posture, not a bolt-on (CON-5, NFR-018, FR-132).** No sermon data leaves the host unless a user explicitly opts a provider in — the abstraction makes "stays local" the zero-configuration state, satisfying the NDPA/GDPR posture structurally rather than by policy alone.
- **Consent gating and fallback have a natural home (FR-132/133/134/135/137).** Cloud adapters share one interface, so per-provider consent, the "cloud active" indicator, key handling via the OS secret store, retry-with-backoff → local failover, and Administrator-gating are implemented once at the boundary and apply uniformly to every current and future cloud provider.
- **Pluggable without core churn (FR-131).** Swapping or adding a provider is an adapter change behind a stable interface; the presentation flow never changes — exactly the FR-131 acceptance criterion.
- **Keeps the human in the loop cheaply (FR-115/120/128/166).** Because the AI surface is operator-confirmed and off-screen by default, the abstraction lets detection/notes flow to a *confirmation surface* the operator consumes, not to the audience output — the precision-over-recall, operator-confirmation, and fabrication-disclosure defaults are enforced at the seam.
- **Isolation localises the audio-feedback guard (FR-172).** The guard (pause ingestion / gate detection while app audio hits a shared output) lives inside the isolated subsystem and observes app-audio state through a one-way signal, with no coupling back into the render/output path.

**Cons / costs:**
- We must build and maintain the interface layer, the consent/indicator/fallback machinery, and two local runtimes (whisper.cpp; a llama.cpp-class LLM) with lazy loading and bounded resource use — real, ongoing engineering effort.
- Cross-platform native model runtimes (whisper.cpp / llama.cpp with GPU backends) add per-OS build, packaging, and model-integrity-verification burden (FR-156, ADR-0012).
- **The local NoteGen quality is the softest spot.** FEASIBILITY evaluates whisper.cpp for STT [W2] but does **not** directly benchmark a local LLM for note generation; "llama.cpp-class notes" is an INFERRED extension of the same local-first pattern. Local note quality, fabrication rate, and resource cost are R5 unknowns carried by FR-128 (fabrication disclosure) and human-review defaults, not by feasibility measurement. We do not overstate this.
- AI *accuracy/latency* remain provisional and spike-gated (S8/S11) regardless of how clean the abstraction is — the pattern removes coupling risk, not model-quality risk.

### Option B — Cloud-only

All STT/notes go to a hosted provider; no meaningful local capability.

**Pros:** highest raw accuracy today; near-zero local compute/packaging burden; no local model runtimes to maintain.

**Cons (decisive against):**
- **Violates the offline-first default outright (FR-101, NFR-015, CON-2).** Transcription would be unavailable exactly when church Wi-Fi is absent or AP-isolated — the very networks FEASIBILITY §6 flags as unreliable [L1][L2].
- **Violates the privacy posture (CON-5, NFR-018, FR-132/177).** Sending sermon audio off-device by default is precisely what the NDPA/GDPR posture and CON-5 forbid without explicit, per-provider, disclosed consent.
- **Cannot honour graceful fallback (FR-135).** With no local provider present, a network loss ends transcription mid-service — there is nothing to fall back to. This also strains FR-083/NFR-024: while core controls would still run, the AI feature simply dies on connectivity loss rather than degrading.
- **No always-present default (FR-131 acceptance says "local default always present").** Option B cannot meet the criterion as written.
- **Verdict:** rejected as the architecture. Cloud is retained strictly as an *opt-in adapter* under Option A, for users who explicitly accept the trade-off.

### Option C — Local-only (no cloud adapters at all)

Ship only the local whisper.cpp / llama.cpp-class providers; never offer cloud.

**Pros:** simplest possible privacy story (nothing ever leaves the host); no consent/indicator/DPA/cross-border machinery to build; smallest attack surface.

**Cons (why not chosen, though it is the closest runner-up):**
- **Forecloses a legitimate, user-chosen quality path.** Some churches will want higher-accuracy cloud STT or stronger cloud note generation and are willing to accept the disclosed trade-off. A local-only architecture cannot offer it *even with consent*, and retrofitting cloud later would mean introducing the very interface boundary Option A builds now — re-platforming the AI seam mid-roadmap.
- **Discards the low marginal cost of doing it right.** Because Option A already isolates providers behind an interface, adding a *disabled-by-default, consent-gated* adapter slot costs little beyond the consent/fallback machinery — machinery the product needs anyway for the "cloud active"/retention/DPA obligations if cloud is ever offered.
- **Does not match the PRD.** FR-131/132/133/134/135/136/137/177 explicitly specify pluggable cloud adapters with consent gating; local-only would drop a scoped requirement set (R3), not satisfy it.
- **Verdict:** rejected as the standing architecture, but noted as the **de-facto runtime posture** — with no provider opted in, the running system *is* local-only, which is the default and the fallback. Option A is a strict superset: it *is* Option C until a user consents to a cloud provider.

## Decision

Adopt **Option A: local-first capability interfaces with pluggable, consent-gated cloud adapters, isolated from the presentation core.**

- Define capability interfaces **`STTProvider`** (R3) and **`NoteGenProvider`** (R5), with scripture detection (R4) built on the transcript surface. A **local implementation is always present and is the default**: **whisper.cpp** for STT (cross-platform Metal/CUDA/Vulkan/CPU; hardware-probe model auto-select per FR-101; resident within the ~≤2 GB budget); a **llama.cpp-class local LLM** for NoteGen.
- **Cloud adapters are pluggable, OFF by default, and consent-gated per provider** (FR-131/132). Enabling a provider requires an opt-in that names the provider, states what data is sent, and states that data leaves the local network/jurisdiction (FR-132/177); it is Administrator-gated and audited (FR-137, FR-150); it surfaces usage/cost/retention (FR-136); and a **live "cloud active" indicator** shows whenever data transmits (FR-133). User-supplied keys live **only** in the OS secret store (FR-134; ADR-0008); "remove key" purges them.
- **Graceful fallback to local, never interrupting live output** (FR-135): bounded retry-with-backoff, a defined failover order for multi-provider configs, then drop to the resident local provider — transcription may degrade, output never blanks.
- **The whole subsystem runs out-of-band from the render/output path** (FR-083, NFR-024, Architecture §1 principles 3/4, §10). The AI-orchestration component communicates with the core through bounded, cancellable, one-way channels; the render loop never awaits AI work and never shares fate with it. AI output reaches the operator through a **confirmation surface**, not the audience screen, by default (FR-115 operator-confirmation default; FR-166 verbatim captioning OFF by default; FR-121 precision-over-recall; FR-120/128 realistic-capability + fabrication disclosure).
- **Subsystem-internal safety:** the **audio-feedback guard** (FR-172) lives inside this subsystem — while app-emitted audio routes to a shared/house output, ingestion is paused and detection firing gated, with an operator warning; it observes app-audio state via a one-way signal and never couples back to render/output.
- **Model integrity:** local model files are verified by pinned hash/signature before load (FR-156; ADR-0012); a mismatch refuses to load.
- **Persistence & privacy:** consent/retention state, transcripts (raw immutable + correction layer), detections, and notes persist through the encrypted datastore (ADR-0007; FR-154 SQLCipher default); retention is configurable with reliable deletion of all copies incl. derived artifacts (FR-153); diagnostics bundles carry no secrets/transcripts (ADR-0011; FR-082).

**Invariants (not spike-gated — they hold regardless of AI quality):** a local provider is always present and default; cloud is off until per-provider consent; keys only in the OS secret store; the render/output path never awaits or shares fate with AI; AI output is operator-confirmed and off-screen by default. These are architectural facts, verified by fault-injection (NFR-024) and dependency/consent audits, independent of measured model accuracy.

## Consequences

**Positive**
- The FR-083 / NFR-024 invariant is satisfied *by construction*: an always-present local default plus strict out-of-band isolation means no provider state — disabled, erroring, slow, or absent — can block core controls or blank output. This is the property the whole product is built to guarantee.
- Offline and private is the **zero-configuration default** (FR-101, CON-2, NFR-015, CON-5): the running system is effectively local-only until a user deliberately opts a cloud provider in.
- Consent gating, the "cloud active" indicator, secret-store key handling, retry→local fallback, retention/DPA disclosure, and Administrator-gating are implemented **once at the interface boundary** and apply uniformly to every current and future provider (FR-131..137, FR-177).
- The roadmap grows without re-platforming: STT (R3) → detection (R4) → notes (R5) all sit behind the same seam; adding or swapping a provider is an adapter change, not a core change (FR-131).
- Human-in-the-loop and off-screen-by-default are enforced at the seam, matching the realistic-capability posture (FR-115/120/121/128/166) and containing the accuracy risk RISK-003/004 flag.

**Negative / costs**
- Two local model runtimes (whisper.cpp; llama.cpp-class LLM) plus GPU backends must be built, packaged, integrity-verified, and lazily loaded across three OSes — real per-platform effort (ADR-0012; FR-156; NFR-003).
- The consent/indicator/fallback/retention/DPA machinery is non-trivial and must be correct on the privacy-critical path — a bug here is a data-egress or compliance incident (T10/T17), not a cosmetic defect.
- **Local NoteGen quality is under-evidenced.** Unlike whisper.cpp for STT [W2], no feasibility benchmark backs a local LLM for notes; local note accuracy/fabrication/cost are R5 unknowns held only by FR-128 disclosure and human-review defaults. We carry this honestly rather than claim confidence we do not have.
- AI *accuracy and latency* stay provisional and spike-gated (S8/S11) — the clean abstraction removes coupling risk but not model-quality risk; the FR-102/FR-121/METRIC-009 thresholds are ratified only after Stage-10 measurement.

**What it commits us to**
- Always ship and load a resident local provider per capability; never let the render/output path await, back-pressure on, or share fate with any provider (verified by fault-injection, NFR-024/FR-083).
- Keep cloud OFF by default; gate every enable behind per-provider consent + disclosure + Administrator approval + audit + "cloud active" indicator, with keys only in the OS secret store, and DPA/cross-border handling before any egress (FR-132/133/134/136/137/177, FR-150).
- Implement bounded retry-with-backoff → deterministic local failover that degrades quietly without blanking output (FR-135).
- Verify local model integrity before load (FR-156); keep transcripts/notes out of logs/diagnostics (FR-082); honour configurable retention + reliable deletion incl. derived artifacts (FR-153); host the audio-feedback guard inside the subsystem (FR-172).
- Deliver the FR-171 evaluation corpora (S11) before Stage-10, and treat all AI accuracy/latency numbers as provisional until measured.

## Fallback / validation

- **Confidence in the abstraction pattern is High** and requires no spike: local-first capability interfaces + pluggable adapters + out-of-band isolation is a well-understood idiom, and the invariants above are architectural facts verified by fault-injection and consent/dependency audits, not by AI measurement. We explicitly do **not** launder this into confidence about AI quality.
- **What S8 must confirm:** that offline transcription (whisper.cpp large-v3 Turbo streaming) and scripture-detection latency meet the provisional targets (#9 ≤2 s behind live; #10 detection incremental latency) on target church CPU/GPU (FEASIBILITY §10, S8; §8 #4/#9/#10 [W2]). **Fallback if S8 falls short:** FR-101's hardware-probe auto-select drops to a smaller/faster Whisper model with graceful degradation (FR-104), and detection/notes run further behind live or in a lower-fidelity mode. Because AI is assistive and operator-confirmed, an S8 shortfall degrades the *assist*, never the core — FR-083/NFR-024 hold regardless. Cloud STT remains an opt-in accuracy path for users who accept the disclosed trade-off, but is never required to meet the baseline.
- **What S11 must deliver:** the FR-171 evaluation-set artefact (composition, source, size, scoring protocol for the non-speech and explicit-reference corpora) that FR-102/FR-108/FR-121/METRIC-009 reference by name. **Until S11 lands, the AI thresholds are unverifiable** and remain provisional; they are ratified only after Stage-10 measurement. This is a limitation we record, not a gap we paper over.
- **Local NoteGen (R5) validation is deferred to its release** and is not covered by S8. Its acceptance rests on FR-128 fabrication disclosure + human-review-before-publish defaults; if a local LLM proves inadequate, the same interface accepts a consent-gated cloud NoteGen adapter — the abstraction is chosen partly so this choice stays open without re-platforming.
- **Degenerate-configuration behaviour:** with no provider opted in, the system runs as local-only (Option C) — the intended default and the ultimate fallback. Option A is a strict superset of Option C, so the "safe" state is always reachable and is the shipping default.

## Requirement / PRD references

- **Constraints / goals:** CON-2 (offline core), CON-5 (cloud opt-in, per-provider, no sermon data leaves without explicit action), NG-1 (TTS is a non-goal), G-1/G-3, RISK-003 (detection accuracy), RISK-004 (offline transcription performance).
- **The invariant:** FR-083 (no AI/provider failure blocks core control), NFR-024 (output-failure isolation, AI named), NFR-015 (offline operation).
- **Provider abstraction & cloud consent:** FR-131 (STT/NoteGen abstraction, local default always present), FR-132 (cloud OFF by default, opt-in + disclosure), FR-133 ("cloud active" indicator), FR-134 (keys in OS secret store), FR-135 (graceful local fallback, never interrupts output), FR-136 (usage/cost/retention visibility), FR-137 (consent/retention persisted + Administrator-gated), FR-156 (local-model integrity verification), FR-177 (DPA + cross-border transfer), NFR-018 (cloud data-egress control).
- **Transcription / detection / notes:** FR-099 (audio input select + level), FR-100 (start/pause/resume/stop), FR-101 (offline default + hardware model auto-select), FR-102 (VAD gating, ≤1% non-speech committed — provisional), FR-104 (graceful degradation), FR-108 (custom vocabulary), FR-109 (non-authoritative speaker labels), FR-115 (operating modes; operator-confirmation default), FR-116 (auto-display corroboration gate), FR-120 (documented accuracy limits), FR-121/METRIC-009 (precision-over-recall, ≤5% FP — provisional), FR-128 (fabrication-risk disclosure), FR-166 (verbatim captioning OFF by default), FR-171 (evaluation-set definition — S11), FR-172 (audio-feedback / self-re-transcription guard).
- **Privacy / persistence / security:** FR-082 (no secrets/transcripts in logs), FR-150 (append-only audit incl. consent changes), FR-153 (retention + reliable deletion), FR-154 (at-rest encryption / SQLCipher — ADR-0007), threat T10 (cloud egress), T13 (model integrity), T17 (retention).
- **Non-functional:** NFR-003 (lazy model loading / bounded resource use), NFR-010 (8–12 h soak).
- **Feasibility (FEASIBILITY.md):** §8 performance targets #4 (model resident ~1.6 GB [W2], DOCUMENTED Med), #9 (transcription latency ≤2 s behind live, DOCUMENTED Med), #10 (detection latency, INFERRED Low); §9 leaning (whisper.cpp local default + provider abstraction; Piper/TTS explicitly not adopted per NG-1); §10 spikes S8 (transcription + detection latency) and S11 (evaluation-set definition); §Method (zero OBSERVED findings — the reason S8 exists).
- **Architecture (ARCHITECTURE.md):** §2 ADR index (ADR-0010), §1 principles 2/3/4, §4 AI-orchestration component (R3+), §10 AI/provider architecture; components AI orchestration and Security/secrets (§4).
- **Reviews / decisions:** Stage-4 audit MAJOR-05/06 (eval corpora → FR-171), MAJOR-08 (audio-feedback guard → FR-172), MAJOR-14 (compliance → FR-177); OD-09 (retention defaults, provisional).
