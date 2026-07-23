# ADR-0006 — Hardware-decode → GPU zero-copy interop

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** Medium-Low
- **Validating spike:** S2 — HW-decode → GPU zero-copy interop per OS (**make-or-break**; FEASIBILITY §10)
- **Owner:** Software Architect
- **Related:** ADR-0002 (wgpu compositor), ADR-0005 (GStreamer media engine), ADR-0004 (winit windowing)
- **Risk register:** RISK-013, RISK-014 · **Open decision:** OD-23 (multi-output/1080p60 spike-gate)

---

## Context

SelahCue's core value proposition is compositing text over motion backgrounds on independent per-monitor outputs. The render path is native Rust + wgpu (ADR-0002), fed by GStreamer media pipelines (ADR-0005). The single unresolved question this ADR settles is the **frame hand-off**: once a hardware decoder has produced a video frame, how does that frame reach a wgpu texture for compositing?

The forces at play:

1. **Encumbered codecs must use platform/HW decoders.** H.264/HEVC/AAC decode is constrained to OS-native/HW-decode GStreamer elements — no `gst-libav` — to preserve the codec-patent safe harbour (CON-4, OD-08a, FR-067, FR-073, ADR-0005). This means the decoded surface originates inside a vendor/OS decode stack (VA-API, NVDEC, VideoToolbox, Media Foundation/D3D11), **already resident in GPU memory**, not in a CPU buffer we control.

2. **The bandwidth ceiling of the naive path is real and low.** FEASIBILITY §2 [R1] documents that a CPU-decode + `write_texture` upload path sustains only **~249 MB/s ≈ 1080p30** for a single output. A 1080p RGBA frame is ~8.3 MB; at 60 fps that is ~497 MB/s **per output**, and the MVP already targets two concurrent outputs (main + stage/confidence, §30/MAJOR-16), with R2 targeting 2–3. Routing decoded GPU frames down to the CPU and back up via `write_texture` multiplies both a readback and an upload across every output every frame — it does not fit the 1080p60 multi-output envelope on the reference hardware.

3. **Zero-copy is the documented enabler but is per-backend and unproven here.** FEASIBILITY §2 classifies wgpu's compositing *capability* as DOCUMENTED (High) but explicitly flags that "**zero-copy HW-decode→GPU interop is the hard part and is platform-specific**," and that 1080p60 across 2–3 outputs is only INFERRED (Med) "— needs a spike to confirm." GStreamer's HW-decode breadth (VA-API/NVDEC/Vulkan video) is DOCUMENTED (High) [M1], but the *hand-off* to wgpu is not something any cited source demonstrates end-to-end. There are **zero OBSERVED findings** in the feasibility report; nothing was executed.

4. **This is the project's biggest single technical risk.** FEASIBILITY §9 states the whole compositor topology "**presupposes spike S2 succeeds**" and that "if S2 fails on any OS, a **fallback architecture is required**." The confidence posture (§10) is explicit: Medium-to-low confidence the individually-capable components combine to hit 1080p60 multi-output on modest church hardware without the interop and multi-window spikes — "those are the make-or-break unknowns."

5. **Reference hardware is modest.** Tier A (minimum) is a quad-core, 8 GB, integrated-GPU machine that must carry all MVP single-output presentation NFRs; Tier B (recommended, 6-core+/16 GB/discrete GPU or Apple Silicon) is where multi-output and 1080p60 are targeted (PRD §26, NFR-005/006). The MVP video floor is deliberately lower — **single-output 1080p30 or 720p60, ≤5% dropped frames on Tier A** (§30) — precisely because the 60 fps multi-output bar is spike-gated.

The decision must therefore choose a hand-off mechanism **and** commit, up front, to a fallback that keeps the MVP shippable if the zero-copy path fails on any one OS.

---

## Options considered

### Option A — Per-OS zero-copy interop into wgpu (CHOSEN)

Keep each decoded frame in GPU memory and import the vendor/OS surface directly as a wgpu texture, using each backend's external-memory / shared-surface mechanism:

| OS / stack | Decoder | Zero-copy mechanism into wgpu |
|---|---|---|
| Linux (Intel/AMD) | VA-API | Export decoder surface as **DMABuf** → import as external-memory image on the wgpu **Vulkan** backend |
| NVIDIA (any OS w/ Vulkan/CUDA) | NVDEC | CUDA/NVMM surface → Vulkan external-memory / CUDA-Vulkan interop |
| macOS | VideoToolbox | `CVPixelBuffer` backed by **IOSurface** → wrap as an `MTLTexture` on the wgpu **Metal** backend |
| Windows | Media Foundation / D3D11 | D3D11 decode texture → **shared handle (keyed mutex)** → import on the wgpu **D3D12/Vulkan** backend |

- **Pros:** Only path with documented headroom for 1080p60 and 2–3 independent outputs [R1][R2]; eliminates the per-frame readback+upload entirely; keeps GStreamer's DOCUMENTED-High HW-decode breadth [M1] while honouring the platform-only-decode constraint (FR-073); aligns with the ADR-0002 wgpu compositor and the single-render-codebase goal.
- **Cons / risks:** Interop is **per-backend and outside wgpu's safe portable API** — it requires the `wgpu-hal` unsafe escape hatches (import-external-texture / create-texture-from-hal) which differ per backend and can break across wgpu version bumps. Four distinct code paths, each with its own failure modes (DMABuf modifier/format negotiation on Linux; keyed-mutex synchronisation on D3D; NV12↔sampler colour-conversion and premultiplied-alpha handling everywhere). **Unproven here** — INFERRED (Med) at best, no OBSERVED evidence. Feasibility differs by OS, so it may succeed on two platforms and fail on a third.

### Option B — CPU readback + `write_texture` upload (REJECTED)

Copy each decoded frame from GPU/decoder memory to a CPU buffer, then upload with `wgpu::Queue::write_texture`.

- **Pros:** Single portable code path; no unsafe HAL interop; trivially correct; useful as a universal software-decode **fallback for FR-160** (isolated per-output decoder failure) where correctness beats throughput.
- **Cons:** **Too slow for the target.** Documented at **~249 MB/s ≈ 1080p30 single output** [R1]; 1080p60 needs ~497 MB/s per output and MVP/R2 want 2–3 outputs — this path cannot sustain the 60 fps multi-output envelope, and on a CPU-only Tier-A box the readback also fights the decoder for memory bandwidth. **Rejected as the primary path** for exactly the reason named in the decision summary. Retained only as an emergency per-output correctness fallback at reduced frame rate.

### Option C — GStreamer GL compositing (`glvideomixer` / shared GL context) (FALLBACK, not primary)

Do the video compositing inside GStreamer's own GL pipeline (`glupload`/`glvideomixer`), sharing a GL context with — or handing a GL texture to — the render layer, rather than importing raw decoder surfaces into wgpu.

- **Pros:** Keeps frames GPU-resident without hand-writing four external-memory paths; `glvideomixer` is a mature, shipped GStreamer element; a proven degradation target. This is the fallback named in FEASIBILITY §9 and ARCHITECTURE §16.
- **Cons:** Cedes compositor control back to GStreamer's GL graph, weakening wgpu's precise per-output scene-graph/layout/timing control (the reason ADR-0002 chose wgpu); GL↔wgpu context sharing has its own portability caveats; a second compositing model to maintain alongside the wgpu path. **Not the primary design** because it dilutes the ADR-0002 architecture — but explicitly accepted as the **fallback** if Option A fails.

### Option D — Per-OS native compositors bypassing wgpu (REJECTED)

Composite natively per platform (Metal / Direct3D / VA-API-GL) with no shared wgpu compositor.

- **Pros:** Best raw per-OS performance and native alpha handling (FEASIBILITY §3 platform-media row).
- **Cons:** **Triples the compositor implementation** and directly contradicts ADR-0002's single wgpu render engine and the cross-platform-desktop goal (mirrors why FEASIBILITY §1 rejected SwiftUI/WinUI as primary). Rejected; retained only as a conceptual reference for the individual interop mechanisms Option A reuses.

---

## Decision

Adopt **Option A — per-OS zero-copy hardware-decode → wgpu interop** as the primary frame hand-off:

- **Linux:** VA-API → DMABuf → Vulkan external-memory import.
- **NVIDIA:** NVDEC → CUDA/NVMM → Vulkan/CUDA interop.
- **macOS:** VideoToolbox → CVPixelBuffer/IOSurface → Metal `MTLTexture` wrap.
- **Windows:** Media Foundation/D3D11 → shared handle (keyed mutex) → wgpu import.

Decode remains constrained to platform/HW-decode GStreamer elements (no `gst-libav`) per ADR-0005/FR-073. **Option B (CPU `write_texture`) is rejected as the primary path** on the documented ~1080p30 ceiling, and retained only as a low-rate per-output software-decode correctness fallback (FR-160).

**The fallback is committed as part of this decision, not deferred:** if spike **S2** fails to demonstrate robust zero-copy on any target OS, that OS degrades to **Option C (GStreamer `glvideomixer` / GL compositing)** and/or accepts **1080p30 / fewer simultaneous outputs** on that platform. The guaranteed 1080p60 (NFR-005) and 2–3-output (NFR-006) targets remain **R2 and spike-gated (OD-23)** and are not committed until S1/S2 results land.

---

## Consequences

### Positive

- The only hand-off with documented headroom for the 1080p60 / multi-output value proposition [R1][R2]; avoids per-frame readback+upload on every output.
- Preserves the ADR-0002 wgpu compositor and its per-output scene-graph/layout/timing control, and the ADR-0005 platform-only HW-decode posture (FR-073, safe harbour).
- Zero-copy lowers CPU and memory-bandwidth pressure, directly serving the low-resource NFRs and the 8–12 h soak stability target (NFR-010, METRIC-003).
- Because the fallback is pre-committed, a per-OS S2 failure degrades gracefully rather than blocking the MVP.

### Negative / costs

- Commits us to **four backend-specific unsafe interop paths** via `wgpu-hal`, outside wgpu's stable safe API — a real maintenance and wgpu-version-upgrade tax, and a surface for hard-to-reproduce, GPU/driver-specific bugs.
- **Confidence is Medium-Low and honestly so:** no OBSERVED evidence exists (FEASIBILITY §10); the combined-system claim is INFERRED (Med). Feasibility may split across OSes, forcing a mixed primary/fallback posture in production.
- Per-backend correctness hazards must each be handled: DMABuf format/modifier negotiation (Linux), keyed-mutex cross-API synchronisation (Windows), NV12→RGB sampling and premultiplied-alpha correctness (all), and colour-space/HDR metadata pass-through.
- The interop path must not violate output-failure isolation: an interop/device fault must **hold the last presented frame and recover out-of-band**, never blank live output (NFR-024, FR-160). This raises the bar on the interop layer's error handling.

### What this commits us to

- Running spike **S2** on Windows, macOS, and Linux (incl. an NVIDIA target) **before** committing NFR-005/006 and before the "2–3 independent 1080p60 outputs" target becomes a firm requirement (OD-23, RISK-013).
- Implementing and maintaining the GStreamer `glvideomixer` / GL-compositing **fallback path** (Option C) and the CPU software-decode per-output fallback (Option B) as first-class, tested degradation targets — not afterthoughts.
- Keeping the MVP Tier-A video floor (single-output 1080p30 or 720p60, ≤5% dropped) as the committed bar until S1/S2 lift it (§30, NFR-005/006 spike-gated).
- Pinning/qualifying the `wgpu` version against the HAL interop surface and re-validating interop on each wgpu upgrade.

---

## Fallback & validation

- **Validating spike (make-or-break): S2** — Prototype GStreamer → wgpu zero-copy on Windows, macOS, and Linux (VA-API/NVDEC/Metal/D3D → wgpu texture); measure sustained fps, dropped-frame %, CPU and GPU utilisation, and memory bandwidth against the §26 targets on Tier-A and Tier-B hardware. Paired with **S1** (multi-window wgpu compositor) and **S3** (transparent/alpha output). Reference: FEASIBILITY §10 S1/S2/S3.
- **Fallback if S2 fails on an OS:** (1) GStreamer `glvideomixer` / GL-shared-context compositing for that platform (Option C); and/or (2) accept **1080p30** and/or **fewer simultaneous outputs** on that platform. Per-OS mixed outcomes are acceptable — the fallback can apply to only the failing backend. (ARCHITECTURE §16; FEASIBILITY §9; RISK-013.)
- **Gate:** NFR-005 (1080p60, R2) and NFR-006 (2–3 outputs, R2) stay **spike-gated** and are ratified only after S1/S2 (OD-23). MVP does not depend on the 60 fps multi-output bar.
- **Related risk RISK-014 (spike S4):** independent multi-monitor fullscreen robustness is a *separate* windowing risk (ADR-0004); it is adjacent to but not resolved by S2 — both must pass for the full multi-output story.

---

## Requirement / PRD references

- **Functional:** FR-066 (image display, MVP), FR-067 (video via OS/HW decoders, MVP), FR-069 (motion backgrounds, R2), FR-070 (missing-media placeholder — never a black screen, MVP), FR-071 (preload + bounded evictable cache, R2), FR-073 (platform/HW-decode-only, MVP), FR-160 (GPU/decoder failure recovery, MVP), FR-083 (no media/AI failure blocks core control, MVP).
- **Non-functional:** NFR-004 (slide-trigger latency, MVP), **NFR-005 (1080p60 render, R2 — spike-gated S1/S2, Tier-B)**, **NFR-006 (2–3 independent outputs, R2 — spike-gated S1/S2)**, NFR-013 (media-cache ≤1 GB LRU, R2), **NFR-024 (output-failure isolation, MVP)**, NFR-010 (8–12 h soak), METRIC-003 (soak).
- **Constraints:** CON-4 / OD-08a (OS-native/HW decoders for encumbered codecs), reference hardware tiers Tier A/Tier B (PRD §26), MVP render/media bound §30 (MAJOR-16; single-output 1080p30/720p60 floor).
- **Risks / open decisions:** **RISK-013** (multi-output 1080p60 feasibility — fallback architecture required before committing), **RISK-014** (MVP dual-output independent-fullscreen robustness — spike S4), **OD-23** (multi-output/1080p60 spike-gate before commitment).
- **Feasibility evidence:** FEASIBILITY §1 [R1] (CPU `write_texture` ~249 MB/s ≈ 1080p30), §2 (wgpu capability DOCUMENTED-High; zero-copy interop the hard part, INFERRED-Med, needs spike) [R1][R2], §3 [M1] (GStreamer HW-decode breadth), §9 (S2 presupposition + fallback requirement), §10 **S2** (make-or-break spike), confidence posture (Medium-to-low combined-system).
- **Architecture:** ARCHITECTURE §2 (ADR-0006 row), §6 (render/output), §7 (media, `platform-HW-decoder → (zero-copy) → wgpu texture`), §16 (risk → fallback).
