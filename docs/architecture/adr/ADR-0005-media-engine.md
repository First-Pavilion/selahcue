# ADR-0005: Media engine

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** High (engine choice) — with two capability risks carried by validating spikes and a sibling ADR (see Fallback/validation)
- **Validating spike:** S3 (transparent/alpha output end-to-end); cross-references S2 via ADR-0006 (HW-decode→GPU interop)
- **Owner:** Software Architect
- **Related:** ADR-0001 (Rust core), ADR-0002 (wgpu compositor), ADR-0006 (HW-decode→GPU zero-copy interop), ADR-0012 (packaging & updates)

---

## Context

The desktop core must play and composite media into the wgpu output pipeline (ADR-0002). The forces driving the media-engine choice come from the PRD and the feasibility evidence:

1. **Media requirements.** Image display (FR-066), video playback via OS-native/HW decoders (FR-067), audio playback with output-device selection that is never forced onto the transcription-capture path (FR-068), looping motion backgrounds under text (FR-069, R2), a missing-media placeholder so a missing item never blanks the audience screen (FR-070), and media preload with a bounded, LRU-evictable cache ≤1 GB (FR-071 / NFR-013, R2).

2. **Codec-patent safe harbor (hard constraint, not a preference).** CON-4 / OD-08a require that encumbered codecs — H.264/HEVC video **and** AAC and other patented audio codecs — decode only through OS-native/HW decoders, with **no bundled encumbered software encoder/decoder**. FR-073 (promoted to MVP per Stage-3 review C-6) makes this testable: "Build uses platform/HW-decode only for H.264/HEVC; verified in dependency audit." The feasibility note in FEASIBILITY §9 states the media engine "must be constrained to platform/HW-decode elements (exclude gst-libav for encumbered codecs) to preserve the codec-patent safe harbor (OD-08a)." gst-libav wraps FFmpeg's libavcodec, which ships **software** implementations of encumbered codecs — precisely the patent exposure the safe harbor exists to avoid. Encoded/exported media must use royalty-free VP9/AV1+Opus only (FR-072, R2).

3. **Alpha / transparent lower-thirds.** MVP lower-third **content types** (speaker name, sermon title, scripture ref, logo, custom text — FR-049) are composited by the engine as text/graphics. The transparent **alpha-video** lower-third (a keyed, transparent video composited over an external source or motion background) is an R2 output capability (Architecture §7; FR-069). The media engine chosen at MVP must be able to grow into alpha-video decoding without re-platforming — the engine decision is made once, at MVP, for the whole roadmap.

4. **Compositor hand-off.** Decoded frames must reach the wgpu compositor as GPU textures, ideally zero-copy. FEASIBILITY §2/§10 flag HW-decode→GPU zero-copy interop (S2) as the single biggest performance risk; that decision is owned by ADR-0006, not this ADR. This ADR decides *which engine decodes*; ADR-0006 decides *how frames reach the GPU*.

5. **Cross-platform, low-footprint, reliable.** One desktop codebase across Windows/macOS/Linux (CON-1); low CPU/memory (NFR-001..003); 8–12 h soak stability (NFR-010); and output-failure isolation — a decoder fault must never blank or clear live output and must recover out-of-band, holding the last presented frame (NFR-024, FR-160, FR-083).

The brief *suggests* GStreamer, but the feasibility report forbids choosing on that basis alone (FEASIBILITY §Method). The options below are evaluated on the evidence.

## Options considered

### Option A — GStreamer (chosen)

**Pros (grounded in FEASIBILITY §3 [M1][M2][M3], §4):**
- **Uniquely documents the alpha-video handling lower-thirds need.** VP8/VP9-alpha decode via `vp8/vp9alphadecodebin` (alpha muxed as an extra WebM track surfaced as `GstVideoCodecAlphaMeta`) [M2], plus the `alpha` element for keying [M3], with emerging VVC/H.266 alpha work [M4]. This is classified **DOCUMENTED (High)** and is the decisive differentiator versus libmpv.
- **Broad hardware decode** across the three OSes: VA-API/NVDEC/Vulkan video, with 1.28 adding Vulkan AV1/VP9 decode and AMD HIP portable acceleration [M1].
- **Element-level composability directly enforces the safe harbor.** We can assemble pipelines from platform/HW-decode elements only and *exclude* gst-libav and the "bad/ugly" plugin sets — the safe-harbor constraint (FR-073) becomes a build-manifest fact we can prove in the dependency audit, not a runtime hope.
- **Cross-platform, single integration**, with mature Rust bindings (`gstreamer-rs`) that align with the Rust core (ADR-0001), and a GL/texture interop path to feed wgpu.

**Cons:**
- "Complex to embed" [M1]: pipeline construction, `appsink`/GL-interop, and lifecycle handling carry a real learning and maintenance cost.
- Per-OS runtime packaging and plugin curation burden (ADR-0012): we must ship a curated runtime and lock the element allowlist so an encumbered or GPL element is never pulled in accidentally.
- The zero-copy hand-off to wgpu is per-OS and unproven — but that risk is owned by ADR-0006/S2, not resolved here.

### Option B — libmpv

**Pros (FEASIBILITY §3 [M5]):** simplest high-quality player to embed; good HW decode (VA-API/VDPAU/NVDEC/Vulkan AV1, stable ≥0.38).

**Cons:**
- **No documented first-class alpha-video track pipeline** — "primarily opaque playback" [M5]. It cannot satisfy the alpha lower-thirds requirement (FR-049 roadmap / R2 transparent output). This alone disqualifies it as the primary engine.
- HW video-output composition has known failure modes in some environments (e.g., WSL) [M5].
- mpv owns more of the render/output pipeline, giving less granular control over the frame→texture hand-off and over which decoders are linked; a typical libmpv build links FFmpeg/libavcodec (software encumbered codecs included), which *weakens* rather than strengthens safe-harbor control.
- **Verdict:** retain only as a documented fallback for **opaque full-frame backgrounds**, per FEASIBILITY §3's own leaning — not a full replacement.

### Option C — Per-platform native media (AVFoundation / Media Foundation / GStreamer-on-Linux)

**Pros (FEASIBILITY §3, INFERRED Med):** best native HW decode and alpha per OS (e.g., HEVC-with-alpha on Apple); lowest per-OS overhead.

**Cons:**
- **Three separate integrations** — "triples integration + testing" — directly contradicting the single cross-platform desktop goal (CON-1).
- Inconsistent alpha/codec behaviour and error semantics across OSes; higher long-run maintenance and divergence risk.
- **Verdict:** rejected as the primary engine; reserved as a *targeted per-OS fallback* for the specific case where GStreamer's alpha path fails on one platform (see Fallback/validation).

## Decision

Adopt **GStreamer as the single cross-platform media engine**, configured with **platform/HW-decode elements only** (VA-API / NVDEC / Vulkan-video and Media Foundation / D3D11 on Windows and Linux; VideoToolbox / AVFoundation on macOS), and **explicitly excluding gst-libav** and any bundled encumbered software encoder/decoder, to preserve the codec-patent safe harbor (CON-4 / OD-08a / FR-073). Use GStreamer's alpha-video path (VP8/VP9-alpha via `vp8/vp9alphadecodebin` → `GstVideoCodecAlphaMeta`; the `alpha` element) to drive transparent lower-thirds. Decoded frames are handed to the wgpu compositor (ADR-0002) as GPU textures, with the interop mechanism decided in ADR-0006. Audio routes through GStreamer audio sinks with output-device selection (FR-068) and is never placed on the transcription-capture path. Simple images (FR-066) may use a lightweight image-decode path rather than a full pipeline (implementation detail).

**Invariants (build-config facts, not spike-gated):** platform/HW-decode-only element set; **no gst-libav**; no bundled encumbered encoder; curated LGPL base/good plugin manifest (no GPL/AGPL "bad/ugly" sets in the proprietary build); SelahCue-encoded/exported media uses VP9/AV1+Opus (FR-072). All of the above are verified in the CI dependency/SBOM audit (NFR-027), which is exactly the FR-073 acceptance mechanism.

## Consequences

**Positive**
- The only evaluated engine that documents alpha-video handling — so we do **not** re-platform media between the MVP lower-third content types and the R2 alpha-video lower-third; the engine decision holds across the roadmap.
- The safe harbor is enforced *structurally* by omitting the offending elements, and is *provable* in the dependency audit rather than asserted.
- One integration across three OSes; mature Rust bindings fit the Rust core; broad HW decode plus a GL-interop path feeds wgpu.

**Negative / costs**
- GStreamer is genuinely complex to embed; expect real effort on pipeline/appsink/GL-interop and on lifecycle/error handling.
- Per-OS runtime packaging and a locked element allowlist add ongoing burden (ADR-0012); the manifest must be guarded so an encumbered or copyleft element is never introduced.
- By excluding software fallback decoders (gst-libav), **unsupported or exotic codecs will simply not play — by design.** This must surface a clear "unsupported format" message and fall back to the missing/unsupported-media placeholder (FR-070), never a black audience screen.
- The zero-copy HW-decode→wgpu performance envelope is **not** settled by this ADR; it is carried by ADR-0006/S2 (Medium-Low), the project's make-or-break interop risk.

**Commitments**
- Ship and package a curated GStreamer runtime per OS; maintain an element allowlist; gate it in CI via the dependency/SBOM audit (FR-073, NFR-027).
- Run media pipelines out-of-band with output-failure isolation: a decoder fault holds the last presented frame, recovers per-output (software-decode where legally permitted) without blanking, and never blocks core controls (FR-160, NFR-024, FR-083).
- Restrict any SelahCue encode/export to VP9/AV1+Opus (FR-072).

## Fallback / validation

- **Confidence in GStreamer as the engine is High.** Its capability is DOCUMENTED (High) [M1][M2][M3], and the safe-harbor element constraint is a build-config invariant that requires no spike. We do **not** overstate this into confidence about the full performance envelope, which depends on the two items below.
- **What S3 must confirm:** the transparent/alpha output end-to-end path on all three OSes — GStreamer alpha decode → premultiplied-alpha compositing → OS transparent fullscreen output (FEASIBILITY §10, S3 [M2][M3]). **Fallback if S3 fails on a given OS:** use the Option C per-platform native alpha path *for that OS only* (e.g., AVFoundation HEVC-with-alpha on Apple), keeping GStreamer for opaque playback elsewhere. Because alpha-video lower-thirds are R2, an S3 shortfall does **not** block MVP.
- **Sibling risk (owned by ADR-0006/S2):** HW-decode→GPU zero-copy interop is the biggest performance risk. If zero-copy fails, ADR-0006's fallback applies — GStreamer `glvideomixer` / CPU-copy at 1080p30 / fewer simultaneous outputs. Note that `glvideomixer` is itself a GStreamer element, so **GStreamer remains the engine in either branch** — a further reason the engine choice is robust to the interop outcome.
- **libmpv** remains a documented fallback for opaque full-frame backgrounds only, should GStreamer embedding prove intractable; it cannot satisfy alpha lower-thirds and is therefore not a full replacement.

## Requirement / PRD references

- **Constraints:** CON-1 (single cross-platform desktop), CON-4 (OS-native/HW decode for encumbered codecs), OD-08a (codec-patent safe harbor), OD-23 (multi-output/perf targets spike-gated).
- **Functional:** FR-049 (lower-third content types, MVP), FR-066 (images), FR-067 (video via OS/HW decoders), FR-068 (audio + device selection), FR-069 (motion backgrounds, R2), FR-070 (missing-media placeholder), FR-071 (preload + bounded cache, R2), FR-072 (VP9/AV1+Opus encode, R2), FR-073 (platform/HW-decode-only, verified in dependency audit — MVP), FR-083 (AI/provider failure never blocks core), FR-160 (GPU/decoder failure recovery).
- **Non-functional:** NFR-001..003 (footprint), NFR-010 (8–12 h soak), NFR-013 (media-cache ≤1 GB, LRU), NFR-024 (output-failure isolation), NFR-027 (SBOM / dependency + license scan in CI).
- **Reviews / decisions:** Stage-3 review C-6 (FR-073 promoted to MVP).
- **Feasibility (FEASIBILITY.md):** §3 media-playback options [M1][M2][M3][M4][M5]; §4 transparent/alpha output feasibility; §9 leaning + the platform-HW-decode-only safe-harbor constraint; §10 spikes S3 (and S2, owned by ADR-0006).
- **Architecture (ARCHITECTURE.md):** §2 ADR index (ADR-0005), §7 Media architecture; components: Media engine (§4).
