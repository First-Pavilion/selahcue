# ADR-0001: Core language and process topology

- **Status:** Accepted
- **Date:** 2026-07-23
- **Owner:** Software Architect
- **Confidence:** High
- **Validating spike:** None required for *this* decision (language + process shape). The performance envelope *within* the chosen core is gated by downstream spikes S1/S2 (see ADR-0002/ADR-0006) — but no spike outcome reverses this ADR; the fallbacks all stay within a Rust core (see §Fallback / validation).

> Scope note: this ADR decides **(a)** the core implementation language and **(b)** the process topology (split render/UI). It does **not** decide the compositor technology (ADR-0002, wgpu, spike S1/S2), the operator-UI shell technology (ADR-0003, Tauri vs Rust-native, Medium, spike S5), or the windowing layer (ADR-0004, winit, Medium, spike S4). Those are deliberately separated because their confidence is lower and they carry their own fallbacks.

---

## Context

The forces below are drawn from the PRD (`docs/product/prds/SelahCue-PRD.md`) and the feasibility evidence (`docs/research/FEASIBILITY.md`, "RP-08/RP-09"). The decision must satisfy all of them simultaneously; several are in tension.

1. **Single cross-platform desktop codebase (Win/macOS/Linux).** Core presentation behaviour must be identical on all three OSes with a passing tri-platform test matrix (NFR-014, G-2, CON-1). This rules out anything that structurally forces per-OS codebases.
2. **Bespoke GPU compositing of text over motion backgrounds, at 1080p60, across independent multi-output surfaces with per-output layouts** (FR-036/037/038/039, NFR-005/006). FEASIBILITY §2 finds this "not achievable cleanly inside one browser compositor" and that a purpose-built GPU pipeline with independent per-monitor surfaces is the best match. This is called out as *the hardest constraint* (FEASIBILITY §9).
3. **Output-failure isolation as a hard invariant.** No AI / media-decoder / audio / network / display / mobile / storage failure may blank or clear live output as a side effect (NFR-024, FR-083, FR-160). ARCHITECTURE principle 3 makes the render/output path *isolated from control-plane and AI load*. This force drives the **topology**, independent of language: the engine that owns the screen must be insulated from stalls elsewhere.
4. **Low, bounded resource use over long runs.** Idle ≤300 MB (NFR-002), presentation-active ≤1.5 GB (NFR-003), <5% memory growth across an 8–12 h soak (NFR-010), low idle CPU/GPU (NFR-011). FEASIBILITY §1 documents a browser runtime (Electron) at 200–300 MB idle — in direct conflict with NFR-002 before any app state is loaded.
5. **Offline-first core** — all core live functions work with zero network/cloud/mobile/AI (NFR-015, CON-2). Favours a self-contained native core over runtime/service dependencies.
6. **Security by construction over untrusted inputs.** The LAN control plane is untrusted and every message must be validated (FR-174, threat T20); imported media/fonts must decode safely (FR-173, threat T12). A memory-safe language at these boundaries removes a whole vulnerability class rather than mitigating it after the fact (ARCHITECTURE §1.5, §11).
7. **Alpha-capable media feeding GPU textures** — HW-decoded video and VP8/VP9-alpha lower-thirds uploaded as textures (FR-049/069, FR-066/067, ADR-0005). The core must interoperate cleanly with GStreamer and a GPU texture path.
8. **Capacity reality.** A small dedicated engineering team over a multi-month schedule (AS-6). "Build our own compositor" is affordable only if the surrounding language/runtime choice pays for itself elsewhere (footprint, safety, single codebase).

**Evidence caveat (stated honestly):** FEASIBILITY contains **zero OBSERVED findings** — nothing was executed in the discovery environment; all evidence is DOCUMENTED (vendor/framework docs, secondary benchmarks) or INFERRED. High confidence here rests on the individual components being *documented as capable*, not on a measured end-to-end system. The end-to-end performance combination is explicitly Medium-to-low confidence until spikes run (FEASIBILITY §9) — which is why the risky sub-decisions are pushed to their own ADRs.

---

## Options considered

Evaluated against the desktop-framework trade-off table in FEASIBILITY §1. Each option is judged as a *core language + how it satisfies the compositing/topology/footprint forces*.

### Option A — Rust core (CHOSEN)

Rust owning the render/output engine (wgpu compositor, native windows), the media pipeline (GStreamer → GPU textures), persistence (SQLite/WAL), and the LAN control server; the dense operator UI sits beside it (ADR-0003 decides whether that shell is a Tauri WebView or Rust-native).

- **Pros:**
  - **Best match to the hardest constraint.** FEASIBILITY §1 (Rust-native row) and §2 rate wgpu (Vulkan/Metal/DX12/GL) as "purpose-built for custom compositing pipelines," giving independent surfaces per monitor and full control of per-output layout/scene graph and frame timing [R1][R2] — exactly force #2.
  - **Very low footprint; no browser runtime** [T2] — directly serves NFR-002/003/010/011 (force #4).
  - **Single cross-platform codebase** via portable crates (wgpu/winit/GStreamer bindings) — force #1, without the per-OS split of Option E.
  - **Memory safety at the untrusted boundaries** (LAN parser FR-174, media/font decode FR-173) — force #6, satisfied by construction rather than by after-the-fact hardening.
  - Preserves the brief's Rust/wgpu/GStreamer/SQLite leaning where the evidence actually supports it (FEASIBILITY §9), without rubber-stamping the WebView-as-compositor part of the brief (rejected in ADR-0002).
- **Cons (honest):**
  - **Weakest option for the *dense operator UI*.** FEASIBILITY §1 (row Rust-native) and [A2] find egui/iced "matured but … neither as rich as web UI for dense operator screens." This is real and unresolved *here* — it is precisely why the UI-shell choice is deferred to ADR-0003 (Medium, spike S5), and why a hybrid with a WebView shell is the likely resolution.
  - **We must build the compositor** (scene graph, layout, transitions, text stack) ourselves — more engineering than adopting Qt/Avalonia's scene graph. Bounded against AS-6 capacity.
  - **Rust talent pool is smaller** than C#/JS; borrow-checker ramp cost.
  - The zero-copy HW-decode→GPU interop is per-backend and genuinely hard (ADR-0006, Medium-Low, spike S2) — but this is a property of the *requirement*, not of Rust (any native compositor faces it), and it has a documented fallback.

### Option B — C++ / Qt

- **Pros:** Full control of windows/displays/fullscreen; battle-tested across broadcast AV; Qt Quick/RHI (Vulkan/Metal/D3D12) + custom shaders make direct video-texture compositing feasible; low-moderate, tunable footprint; Qt Multimedia can use a GStreamer backend (FEASIBILITY §1). Strongest *mature* technical fit — least to build for the scene graph.
- **Cons:** **Qt licensing is a compliance item** (commercial vs LGPL review — FEASIBILITY §1), which the PRD's GPL/AGPL-exclusion dependency policy (NFR-027) makes non-trivial. **C++ carries the memory-safety burden manually** at exactly the untrusted parsing/decoding boundaries where forces #6 and FR-173/174 demand safety — the opposite of Rust's by-construction guarantee. Larger long-term maintenance/safety cost for a small team (AS-6). Net: technically strong, but loses on safety-by-construction and licensing clarity.

### Option C — .NET / Avalonia (C#)

- **Pros:** Multi-window/multi-display supported; Skia renderer over OpenGL/Vulkan with deferred composition and Avalonia 12 FPS gains on complex scenes [A1]; good productivity/GPU balance; mature adopters (JetBrains, Unity, GitHub) (FEASIBILITY §1).
- **Cons:** **Video-over-GPU compositing is "less turnkey than Qt/wgpu"** and there is **"no first-class alpha-video pipeline"** (LibVLCSharp/platform media) [A1] — a direct miss against force #7 and the alpha lower-thirds requirement (FR-049/052). Managed-runtime footprint is moderate (heavier than native — pressure on NFR-002/010). Requires a C#-fluent team. Reasonable general choice, weaker on the two things SelahCue most needs (bespoke multi-output compositing + alpha).

### Option D — Electron / Node (Chromium)

- **Pros:** Mature, consistent Chromium multi-window/multi-display everywhere; Chromium's canvas/WebGL/WebGPU is well GPU-accelerated (better than WebKit per the Tauri issue thread [T1]); mature signing tooling (FEASIBILITY §1).
- **Cons:** **Footprint disqualifies it against the NFRs** — 200–300 MB idle and >100 MB installers [T2] conflict with NFR-002 (≤300 MB idle *before* app state) and the 8–12 h soak goal (NFR-010), force #4. **The browser owns the compositor**, so independent fullscreen outputs and precise frame timing are constrained (FEASIBILITY §2) — a miss against force #2. Viable but heavy; the compositing remains browser-bounded, not bespoke.

### Option E — Per-OS native (SwiftUI/WinUI + platform toolkits)

- **Pros:** Best-in-class per platform (Metal/DirectComposition), lowest footprint, native HW decode + alpha, native store/signing (FEASIBILITY §1).
- **Cons:** **Two-plus separate desktop codebases** — FEASIBILITY §1 rejects this as primary because it "contradicts the single cross-platform desktop goal" (force #1, NFR-014, G-2). Triples build/test/maintenance against AS-6 capacity. Retained only as a *reference* for platform APIs (e.g. per-OS zero-copy interop in ADR-0006), never as the primary stack.

### Topology sub-decision — split render/UI process vs single process

Independently of language, force #3 (output-failure isolation, NFR-024/FR-083) argues for a **two-process split**: the render/output engine runs in its own process with its own render loop on a monotonic timeline, insulated so that UI, control-plane, or AI stalls (or an operator-UI crash) can never blank or freeze what is on the physical outputs (ARCHITECTURE §4/§6). A single-process design would couple UI-thread or IPC stalls to the presentation surface and make the NFR-024 invariant a best-effort discipline rather than a structural guarantee. The split is chosen. (This is the *process* shape; the UI-shell *technology* remains ADR-0003.)

---

## Decision

**Adopt a Rust core with a split render/UI process topology.**

- **Language:** Rust for the entire core — render/compositor engine, output manager, media engine (GStreamer bindings), presentation/scripture/timer services, data layer (SQLite/WAL + SQLCipher), autosave/recovery, LAN control server, and (R3+) the AI-orchestration adapters.
- **Topology:** a dedicated **render/output engine process** owning the wgpu surfaces and native output windows, structurally isolated from a separate **control/UI plane** (operator-UI shell + LAN server + AI orchestration). They communicate over a validated IPC boundary; a stall or crash on the control/UI side holds the last presented frame on every output (NFR-024, FR-160).

Rust wins because it is the only option that satisfies *all* of forces #1, #2, #4, and #6 at once: single cross-platform codebase, a purpose-built GPU compositor for independent multi-output, minimal footprint, and memory safety at the untrusted boundaries. Qt and Avalonia are technically credible but lose on safety-by-construction / licensing (Qt) or on turnkey multi-output alpha compositing (Avalonia). Electron is excluded on footprint and browser-bounded compositing; per-OS native is excluded for contradicting the single-codebase goal.

The split topology is adopted because output-failure isolation (NFR-024) must be a structural property, not a coding convention.

---

## Consequences

### Positive

- The NFR-024/FR-083 output-failure-isolation invariant becomes **structural**: control-plane, AI, and UI faults are on the far side of a process boundary from the surface that drives physical outputs.
- A single Rust codebase covers Windows/macOS/Linux (NFR-014, G-2), with wgpu/winit/GStreamer supplying the portable primitives.
- The bespoke wgpu compositor gives per-output scene graphs and independent fullscreen surfaces — the capability FEASIBILITY §2 says a browser compositor cannot provide cleanly (FR-036/037/038/039).
- No browser runtime → the footprint budget (NFR-002/003/010/011) starts far below Electron's baseline [T2].
- Memory safety at the LAN and media/font decode boundaries (FR-173/174) removes a class of vulnerabilities by construction, aligning with the security posture (ARCHITECTURE §11, NFR-027).

### Negative / costs

- **The dense operator UI is Rust's weakest area** [A2]. This ADR does not resolve it; it forces the follow-on ADR-0003 (Tauri WebView vs Rust-native, Medium, spike S5) and accepts the resulting WebView↔engine preview-fidelity problem (RISK-012; ARCHITECTURE §16).
- **We own the compositor.** Scene graph, layout, transitions, and the text-shaping stack (ADR-0014, cosmic-text/HarfBuzz, spike S10) are ours to build and maintain against AS-6 capacity — more than adopting Qt/Avalonia's scene graph.
- **A process boundary adds IPC and preview-streaming complexity** (streaming a downscaled compositor preview into the UI — spike S5) that a single-process design would avoid.
- **Rust staffing/ramp cost** and a smaller talent pool than C#/JS.
- The hardest technical risk — zero-copy HW-decode→GPU interop per OS (ADR-0006, Medium-Low, spike S2, "make-or-break") — is inherited by this topology. It is not *caused* by Rust (any native compositor faces it) and has a documented fallback, but it is a real, unproven dependency (RISK-013).
- winit multi-monitor *exclusive* fullscreen has documented rough edges [W1] (ADR-0004, spike S4, RISK-014) — mitigated by borderless-per-monitor + manual placement, not eliminated.

### What this commits us to

- A native Rust core owning the wgpu compositor, GStreamer media, SQLite persistence, and the LAN server, driving native output windows, with the operator UI on the other side of an IPC boundary.
- The split-process topology from day one — a structural assumption that ADR-0002 (compositor), ADR-0003 (UI shell), and ADR-0004 (windowing) all build on.
- Rust-capable engineering staffing and the associated ramp.
- Running the downstream validating spikes that confirm the *pieces* inside this topology: S1 (multi-output 1080p60), S2 (zero-copy interop), S4 (multi-monitor fullscreen), S5 (UI-shell/preview).

---

## Fallback / validation

This decision (language + process shape) is **High-confidence and needs no validating spike of its own.** FEASIBILITY §9's confidence posture is explicit: high confidence the Rust/wgpu/GStreamer/SQLite *components are individually capable*; the uncertainty is whether they *combine* to hit 1080p60 multi-output + alpha + 12 h soak on modest hardware — and that uncertainty lives in ADR-0002/0006, not here.

The important honesty point: **no spike outcome reverses this ADR.**

- If the make-or-break zero-copy interop spike **S2 fails** on an OS, the fallback is **not** to abandon Rust. It is to fall back the *compositor path within the same Rust core* — GStreamer `glvideomixer` / a per-OS native compositor, or accepting 1080p30 or fewer simultaneous outputs (ADR-0006; RISK-013/014; OD-23). The multi-output 1080p60 targets (NFR-005/006) are already spike-gated and not yet committed.
- If the operator-UI spike **S5** shows the WebView shell cannot carry an adequate GPU-composited preview, the fallback (a Rust-native egui/iced shell — ADR-0003) still lives **inside the same core language**, reinforcing rather than reversing this ADR.
- If **S4** shows winit multi-monitor fullscreen is not robust, the fallback is borderless-per-monitor + manual placement (ADR-0004) — again within the Rust core.

In every branch the language and the split topology hold; only the performance envelope and the peripheral technology choices flex. That is *why* this ADR is rated High while ADR-0002/0003/0004/0006 are rated lower — this ADR deliberately decides only the parts that have a safe fallback within themselves.

---

## Requirement / PRD references

- **Goals / constraints:** G-1 (never blank output), G-2 (genuine Win/macOS/Linux), CON-1 (desktop-authoritative), CON-2 (offline core), AS-3 (stack chosen in Stage-5 ADRs; leaning is spike-gated), AS-6 (small-team capacity assumption).
- **Functional:** FR-036/037/038/039 (main + stage + independent per-output outputs), FR-049/052/069 (alpha lower-thirds / motion backgrounds), FR-066/067 (media / HW decode), FR-083 (AI/provider failure never blocks core control), FR-160 (GPU device-loss & decoder recovery), FR-173 (untrusted media/font decode hardening), FR-174 (control-message schema/input validation).
- **Non-functional:** NFR-002/003 (idle/active memory), NFR-005/006 (1080p60 / multi-output — spike-gated S1/S2, OD-23), NFR-010/011 (soak stability / idle CPU-GPU), NFR-014 (cross-platform parity), NFR-015 (offline), NFR-024 (output-failure isolation), NFR-027 (dependency/SBOM + GPL/AGPL exclusion — bears on the Qt-licensing con).
- **Feasibility evidence:** FEASIBILITY §1 (desktop-framework trade-off table; footprint [T2]; WebView GPU limits [T1]; Rust-native / GUI maturity [A2]), §2 (rendering options; wgpu [R1][R2]), §3 (GStreamer alpha), §9 (Rust-core split-topology leaning + confidence posture), §10 (spikes S1/S2/S4/S5; classification summary — 0 OBSERVED).
- **Risk register:** RISK-001 (scope breadth), RISK-012 (Tauri-WebView-as-compositor tension), RISK-013 (multi-output 1080p60 feasibility), RISK-014 (dual-output fullscreen robustness).
- **Related ADRs:** ADR-0002 (wgpu compositor; WebView is *not* the compositor), ADR-0003 (operator-UI shell, Medium, S5), ADR-0004 (winit windowing, Medium, S4), ADR-0005 (GStreamer media), ADR-0006 (HW-decode→GPU zero-copy interop, Medium-Low, S2 make-or-break), ADR-0014 (cosmic-text/HarfBuzz text shaping, S10).
