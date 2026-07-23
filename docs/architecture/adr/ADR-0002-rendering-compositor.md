# ADR-0002 — Rendering / output compositor

- **Status:** Accepted
- **Date:** 2026-07-23
- **Owner:** Software Architect
- **Confidence:** High (for the choice); the *performance envelope* it enables is separately Medium/Low and spike-gated — see §Confidence caveat
- **Validating spikes:** S1 (wgpu multi-output 1080p60) · S2 (HW-decode → GPU zero-copy interop)
- **Related ADRs:** ADR-0001 (Rust core + split render/UI process topology), ADR-0003 (Tauri operator-UI shell + streamed preview), ADR-0004 (winit windowing), ADR-0005 (GStreamer media engine), ADR-0006 (HW-decode → GPU interop — the make-or-break spike S2), ADR-0014 (cosmic-text / HarfBuzz text shaping)

> **Evidence honesty note.** Every finding cited below is **DOCUMENTED** (vendor/framework docs, issue threads, secondary benchmarks) or **INFERRED** (reasoned synthesis). The feasibility report contains **zero OBSERVED findings** — no software was executed in that environment (FEASIBILITY §Method, §10 classification summary). That limitation is exactly why spikes S1/S2 exist and why the performance envelope this decision *enables* is not yet proven.

---

## Context

SelahCue must composite text (lyrics, scripture, lower thirds, timers/TIME UP) over motion backgrounds and hardware-decoded video, on **independent** physical outputs that can each show a **different per-output layout** of one shared live state — e.g. main audience = 4 lyric lines over a motion background; stage/confidence = current/next line + clock + timer; stream = a 2-line lower third (ARCHITECTURE §6; FR-036, FR-037, FR-038, FR-047, FR-049). The rendering path is the product's core value and its single hardest technical constraint (FEASIBILITY §1, §Confidence posture).

The forces the compositor must satisfy:

1. **Independent, per-monitor fullscreen outputs with distinct layouts.** Each output is its own surface + its own scene graph, driven from shared state (ARCHITECTURE §6; FR-036/037/038/046). MVP drives **two** concurrent independent outputs (main + stage/confidence), not one (PRD §30 "Render/media bound", MAJOR-16).
2. **GPU compositing of text over 1080p video.** Text-over-motion at frame rate is the workload (FR-069 motion backgrounds; NFR-004 slide-trigger latency ≤150 ms, goal ≤80 ms). The committed 1080p60 single-output bar (NFR-005) and 2–3 independent 1080p60 outputs (NFR-006) are **R2 and explicitly spike-gated** on S1/S2 (PRD §14, §24, OD-23). MVP has only a Tier-A floor: single-output 1080p30 **or** 720p60 at ≤5% dropped frames (PRD §30).
3. **Output-failure isolation.** No component failure — decoder, GPU device-loss/TDR, audio, network, storage — may blank or clear live output as a side effect; on fault the compositor **holds the last presented frame** and recovers out-of-band, and a whole-device GPU loss must recover affected outputs within a bounded time (≤3 s target) with no content loss or operator rebuild (NFR-024, FR-160; ARCHITECTURE §1 principle 3, §6). This demands precise, owned control of the render loop and surface lifecycle.
4. **Alpha / transparency output** for lower thirds over external video (key/fill, browser-source) — premultiplied-alpha compositing to a transparent OS window (FR-048, FR-052; R2, but the compositor design must not preclude it).
5. **Low, bounded resource use** across an 8–12 h service, on hardware from CPU-only PCs to Apple Silicon (NFR-002/003/010; AS-2 reference tiers).
6. **Seizure-safety** — animated/flashing output bounded to ≤3 flashes/sec (FR-175, WCAG 2.3.1), which the compositor's timeline must be able to enforce.

The product brief *suggests* wgpu, but the feasibility work explicitly forbids choosing on that assumption (FEASIBILITY §Method). The real tension it surfaced is that the brief also suggests **Tauri**, and the natural (wrong) reading is to let Tauri's WebView also be the compositor. The evidence says that specific combination does not hold (FEASIBILITY §1 "single most important desktop finding"; RISK-012). This ADR settles the compositor; ADR-0003 separately settles the operator-UI shell.

---

## Options considered

### Option A — wgpu (native GPU compositor) + native output windows  ✅ CHOSEN

A Rust-native compositor built on wgpu (Vulkan / Metal / DX12 / GL). Each output is an independent wgpu surface on a borderless-fullscreen native window (winit, ADR-0004); decoded video frames are uploaded as GPU textures (zero-copy where ADR-0006/S2 succeeds); text is shaped (cosmic-text/HarfBuzz, ADR-0014) into a glyph atlas and drawn as textured quads; a per-output shader blends the layers; the engine runs its own render loop on a monotonic timeline.

**Pros (evidence-grounded):**
- **Best match to the actual requirement.** wgpu is purpose-built for custom compositing pipelines with independent surfaces per monitor and full control of per-output layout/scene graph — DOCUMENTED (High) capability (FEASIBILITY §1 Rust-native row, §2 wgpu row).
- **Owns the render loop and surface lifecycle**, which is what output-failure isolation (NFR-024) and "hold last-good frame + out-of-band recovery" (FR-160) actually require — a browser compositor does not expose this level of control (FEASIBILITY §2 web-canvas row: "browser owns the compositor — limited control over independent fullscreen outputs and precise frame timing").
- **Independent per-output layouts** fall out naturally (one surface + one scene each), which is *not* achievable cleanly inside a single browser compositor (FEASIBILITY §4 "not achievable cleanly inside one browser compositor").
- **Low footprint** — no browser runtime — aligns with the idle-memory and 12 h-soak goals (NFR-002/010; FEASIBILITY §1).
- **Documented bandwidth headroom:** CPU-decode + `write_texture` sustains ~249 MB/s ≈ 1080p30, and zero-copy paths reduce CPU→GPU transfer further (FEASIBILITY §2 wgpu row [R1]).

**Cons / risks (evidence-grounded):**
- **We must build the compositor** — scene graph, per-output layout, transitions, text stack (FEASIBILITY §2 wgpu row "Must build the compositor ... ourselves"). This is real, ongoing engineering cost, not a library call.
- **1080p60 across 2–3 outputs is INFERRED (Med), not proven** — it "needs a spike to confirm" (S1) (FEASIBILITY §2, §10 S1).
- **Zero-copy HW-decode→GPU interop is the hard, platform-specific part** and is genuinely limited per backend (S2; ADR-0006, Medium-Low confidence, "make-or-break"). A naïve CPU copy may not hit 60 fps (FEASIBILITY §10 S2).
- **winit multi-monitor *exclusive* fullscreen has documented rough edges** — mitigated by borderless-per-monitor + manual placement (ADR-0004; FEASIBILITY §1 [W1], §10 S4). This is an adjacent risk, not a compositor-choice risk.
- Text shaping is not free: glyphon/wgpu-text draw textured-quad glyphs but do not alone do complex-script shaping — hence the cosmic-text/HarfBuzz layer (ADR-0014, S10).

### Option B — Native framework GPU compositing (Qt RHI / Avalonia Skia / Metal / D3D)

A mature framework scene graph with custom shaders (Qt Quick/RHI over Vulkan/Metal/D3D12; or Avalonia's Skia renderer).

**Pros:** Mature, battle-tested in broadcast AV; **less to build** than raw wgpu; direct video-texture compositing is feasible (FEASIBILITY §1 Qt row, §2 native-GPU row — DOCUMENTED Med). Avalonia claims large FPS gains on complex scenes (FEASIBILITY §1 [A1]).

**Cons:** **Ties the whole engine to that framework's language/runtime** (C++/Qt or C#/.NET), which conflicts with the Rust-core decision (ADR-0001) and would fragment the codebase or force a language boundary through the hottest path. **Alpha-video compositing "varies"** by framework and is less turnkey than the wgpu path for our transparent-lower-thirds requirement (FEASIBILITY §1 Avalonia row "no first-class alpha-video pipeline"; §2 native-GPU row). Qt adds a **commercial-vs-LGPL licensing compliance item** (FEASIBILITY §1 Qt row). Net: a strong technical fit in isolation, but it imports a runtime/licensing/language cost that ADR-0001 already decided against. **Not chosen — but this is the credible fallback family** if the wgpu path fails a spike (see Fallback).

### Option C — Web-canvas / WebGL / WebGPU inside a WebView (Tauri or Electron)  ❌ REJECTED

Composite in the page (Canvas2D / WebGL / WebGPU), i.e. make the operator-UI WebView also the output compositor — the naïve reading of the brief's "Tauri" suggestion.

**Rejected on documented evidence — this is the load-bearing correction to the brief (RISK-012; ARCHITECTURE §2 note):**
- **Tauri/WebKit GPU compositing is inconsistent:** CSS filters / canvas can fall back to **CPU, not GPU** (tauri issues #4891/#8246, discussion #11944 [T1]); macOS Tauri is **capped at 60 fps with no ProMotion**; **native-GPU-under-WebView compositing is still only an open feature request** (FEASIBILITY §1 Tauri row, §2 web-canvas row — DOCUMENTED Med). The feasibility report calls the WebView GPU limit "**the single most important desktop finding**" (FEASIBILITY §1 Framework takeaways).
- **The browser owns the compositor**, so we lose control over independent fullscreen outputs and precise frame timing (FEASIBILITY §2 web-canvas row) — directly contradicting forces 1 and 3 (per-output layouts + output-failure isolation / hold-last-frame).
- **Electron's Chromium canvas/WebGPU is better GPU-accelerated than WebKit** but carries a **200–300 MB idle footprint** that conflicts with the low-resource and 12 h-soak goals (NFR-002/010; FEASIBILITY §1 Electron row [T2]), and it is *still* a browser compositor, not a bespoke pipeline. The feasibility leaning: web-canvas is acceptable "only if a spike shows Chromium/WebGPU (Electron) meets 1080p60 multi-output — **unlikely to beat native** for independent-output control" (FEASIBILITY §2 Leaning).

Rejecting the WebView **as compositor** does not reject Tauri **as the operator console** — that is ADR-0003's separate decision. The WebView is the dense operator UI; it receives a downscaled, streamed texture preview of the native compositor's output. The compositor itself is native Rust + wgpu (ARCHITECTURE §2 note, §4).

---

## Decision

**Adopt wgpu (native GPU) as the SelahCue rendering compositor, driving native per-output windows. The WebView is explicitly NOT the compositor.**

Each physical output is an independent native window with its own wgpu surface and per-output scene, driven from one shared live state. The compositing pipeline is: HW-decoded video frame → GPU texture (zero-copy where ADR-0006 succeeds) · cosmic-text/HarfBuzz-shaped glyphs → glyph atlas → textured quads (ADR-0014) · per-output shader blend of the layers. The engine runs its own render loop on a monotonic timeline, and on a decoder/GPU fault it **holds the last presented frame** and recovers out-of-band (ARCHITECTURE §6; NFR-024, FR-160). The operator UI (ADR-0003) consumes a streamed preview of this output; it does not composite live output.

This keeps the brief's Rust/wgpu leaning where the evidence supports it and rejects, on documented grounds, the one place the brief's suggestion collides with reality — the WebView-as-compositor (FEASIBILITY §1/§9; RISK-012).

---

## Confidence caveat (do not overstate)

The **High** confidence attaches to the *choice*: "native GPU compositor via wgpu; WebView is not the compositor." That is well-grounded — the WebView GPU limits are DOCUMENTED and the wgpu compositing capability is DOCUMENTED (High) (FEASIBILITY §2).

It does **not** attach to the *performance envelope* the choice must eventually hit. Whether wgpu sustains **1080p60 across 2–3 independent outputs on modest church hardware** is INFERRED (Med) and unproven (S1), and it depends on **zero-copy HW-decode→GPU interop**, which is Medium-Low confidence and per-OS (S2; ADR-0006, "make-or-break"). The feasibility posture is explicit: high confidence the components are *individually* capable; **medium-to-low confidence they combine** to hit 1080p60 multi-output + alpha + 12 h soak on modest hardware without the S1/S2 spikes (FEASIBILITY §Confidence posture). Accordingly NFR-005/006 remain R2 and spike-gated (OD-23); MVP commits only to the Tier-A floor (1080p30 or 720p60 single-output, PRD §30).

---

## Consequences

**Positive:**
- Full control of independent per-output surfaces, layouts, and the render loop — the only option that cleanly satisfies per-output layouts (FR-038) *and* output-failure isolation / hold-last-frame (NFR-024, FR-160).
- Lowest footprint (no browser runtime) — supports NFR-002/003/010 and the 12 h soak.
- Portable across Vulkan/Metal/DX12/GL, serving cross-platform parity (NFR-014) from one Rust codebase (ADR-0001).
- A native transparent-window + premultiplied-alpha path is available for R2 lower thirds and browser-source/NDI (FR-048/052; ARCHITECTURE §6).
- The monotonic render timeline can enforce the ≤3-flashes/sec seizure-safety bound (FR-175).

**Negative / costs:**
- We **own** the compositor: scene graph, per-output layout, transitions, glyph atlas, text-shaping integration — sustained engineering cost and a bug surface a framework would otherwise absorb (FEASIBILITY §2 wgpu row).
- The hardest sub-problem — zero-copy HW-decode→GPU interop — is pushed into ADR-0006 (S2) and is the project's biggest single technical risk (Medium-Low).
- Text correctness (Unicode, diacritics, fallback) is now our responsibility via ADR-0014/S10, not a browser's.
- The operator UI cannot render live output directly; it requires a preview-streaming bridge (ADR-0003/S5) with its own fidelity/latency risk.

**What it commits us to:**
- ADR-0001 split render/UI process topology (render engine insulated from UI/control-plane stalls).
- ADR-0004 winit borderless-per-monitor windowing (not exclusive fullscreen), with platform-native fallback.
- ADR-0005 GStreamer feeding GPU textures, and ADR-0006 per-OS zero-copy interop.
- ADR-0014 cosmic-text/HarfBuzz shaping in the wgpu text stack.
- ADR-0003 streamed-preview bridge into the WebView console.
- Treating NFR-005/006 as R2 spike-gated commitments, not MVP guarantees (OD-23).

---

## Fallback & validation

**This decision to use a *native GPU compositor* is not contingent on the spikes** — the WebView-as-compositor rejection stands on documented evidence regardless of S1/S2 outcomes. What the spikes gate is the **performance envelope and the interop approach within the native path**, not the native-vs-WebView choice.

- **S1 — wgpu multi-output 1080p60:** build a wgpu multi-window compositor, feed HW-decoded frames + composited text, measure fps/CPU/GPU on mid-range church hardware (FEASIBILITY §10 S1). Gates NFR-005/006 promotion from "proposed" to "committed" (OD-23).
- **S2 — HW-decode → GPU zero-copy interop per OS** (VA-API/NVDEC/Metal IOSurface/D3D11 shared handle → wgpu texture): the biggest perf risk; a naïve CPU copy may miss 60 fps (FEASIBILITY §10 S2; ADR-0006).

**Fallback if S1/S2 fail on any OS** (fallback is *within the native path*, never back to the WebView) — per FEASIBILITY §9 and ADR-0006 / RISK-013/014:
1. Use GStreamer `glvideomixer` (GPU compositing inside the media pipeline) instead of hand-rolled zero-copy upload; **or**
2. Accept a reduced envelope — **1080p30**, or **fewer simultaneous outputs** — and keep NFR-005/006 out of MVP; **or**
3. If native wgpu compositing itself proves untenable on a platform, fall back to the **Option B family** (a mature native framework GPU compositor — Qt RHI / Skia) for that platform, accepting the language/runtime/licensing cost documented above.

The media engine is additionally constrained to **platform / HW-decode elements only** (no gst-libav for encumbered codecs) to preserve the codec-patent safe harbor (ADR-0005; FR-073; OD-08a) — orthogonal to the compositor choice but binding on the frames it consumes.

---

## Requirement / PRD references

- **Principles:** ARCHITECTURE §1 (principle 3 output-failure isolation, principle 6 native GPU rendering), §2 (ADR index + "load-bearing correction to the brief"), §4 (Engine component), §6 (Rendering & output architecture).
- **Functional:** FR-036 (main output), FR-037 (stage/confidence), FR-038 (independent per-output config, R2), FR-041 (display-reconnect restores exact content), FR-046 (windowed/fullscreen), FR-047 (livestream layout, R2), FR-048 (transparent/browser-source, R2), FR-049 (lower thirds), FR-052 (transparent lower-third output, R2), FR-059 (per-output TIME UP), FR-069 (motion backgrounds, R2), FR-073 (platform/HW-decode-only), FR-160 (GPU/decoder failure recovery), FR-175 (seizure-safety ≤3 flashes/sec).
- **Non-functional:** NFR-004 (slide-trigger latency), NFR-005 (1080p60 single output, R2 spike-gated), NFR-006 (2–3 independent outputs, R2 spike-gated, OD-23), NFR-002/003/010 (memory + 12 h soak), NFR-014 (cross-platform parity), NFR-024 (output-failure isolation).
- **Scope / risk:** PRD §30 (MVP render/media bound: two outputs; Tier-A video floor), §24 (Performance spike-gating), RISK-012 (Tauri-WebView-as-compositor tension), RISK-013 (multi-output 1080p60 feasibility), RISK-014 (dual-output robustness / S4), OD-23 (NFR-005/006 spike gate), OD-08a (codec safe harbor).
- **Feasibility evidence:** FEASIBILITY §1 (framework trade-off + takeaways, [T1]/[T2]), §2 (rendering options + leaning, [R1]/[R2]), §4 (independent outputs / alpha), §9 (split-architecture leaning + S2 presupposition), §10 (spikes S1/S2/S4/S10; classification summary), §Confidence posture.
