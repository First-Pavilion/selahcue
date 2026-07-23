# ADR-0003 — Operator-UI shell

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** Medium
- **Validating spike:** S5 (Tauri WebView vs Rust-native operator UI + compositor-preview handoff)
- **Owner:** Software Architect
- **Related:** ADR-0001 (Rust core; split render/UI topology), ADR-0002 (wgpu compositor; *WebView is NOT the compositor*), ADR-0004 (winit windowing)
- **Evidence:** `docs/research/FEASIBILITY.md` §1, §2, §9, §10 (S5); findings [T1][T2][A1][A2][R1][R2]

## Decision

Use **Tauri (a system WebView) as the dense operator console** — the editors, service plan, library, command palette, previews, and live-control surface. The console is a **client of the Rust core** (ADR-0001), not the owner of any live state and not the compositor.

Physical **outputs are native wgpu windows** (ADR-0002), never WebViews. To show the operator what is live/staged, the wgpu engine produces **already-composited frames, downscaled, and streams them as a preview into the console UI**. The WebView therefore *displays* a preview raster; it never *composites* one. This is the mechanism that keeps the WebView on the right side of its documented GPU ceiling.

This confirms the "load-bearing correction to the brief" recorded in `ARCHITECTURE.md` §2/§38: the WebView is the *console*; the *compositor* is native Rust + wgpu.

## Context — the forces

The operator console is a **dense, keyboard-first, accessible desktop UI**: service-plan authoring (EPIC-A, FR-001..008), slide/song/scripture editors (EPIC-B/C/D, FR-009..035), a command palette (FR-015), undo/redo (FR-016), Unicode/diacritic text entry (FR-017), current/next preview reflecting live state within **≤100 ms** (FR-013), and full live control (go-live, clear, blackout, timers). It must be operable by keyboard alone (NFR-019/FR-014), meet WCAG 2.1 AA contrast (NFR-020), and expose accessible names/roles on core live controls to platform screen readers (NFR-021). A new operator must reach first-slide in ≤10 min (METRIC-006), which rewards a familiar, rich UI toolkit.

At the same time the app targets **low, bounded resource use**: ≤300 MB idle (NFR-002), <5% memory growth over a 12 h soak (NFR-010), and low idle CPU/GPU (NFR-011) on Tier-A hardware (quad-core, 8 GB, integrated GPU).

Two hard constraints shape the shell choice:

1. **The WebView cannot be the compositor.** FEASIBILITY §1/§2 records (DOCUMENTED, Med) that WebView GPU compositing is limited: CPU-bound canvas/CSS filters, a macOS 60 fps cap with no ProMotion, and no supported native-GPU-under-WebView path [T1]. This is called out as "the single most important desktop finding." The independent-multi-output, per-output-layout, alpha, 1080p60 compositing requirement is therefore owned by wgpu + native windows (ADR-0002), *beside* the shell — not inside it.
2. **Output-failure isolation (NFR-024).** No UI or control-plane stall may blank/clear live output. This forces the shell to be an isolated client of the core (ADR-0001 two-process topology), which is true regardless of which UI toolkit wins — but it also means the shell's job is "editors + control + preview," not live rendering.

FEASIBILITY §9 left this decision **explicitly open**: "Operator UI: either Tauri WebView (rich, fast to build, low memory [T2]) **or** Rust-native egui/iced. Undecided — depends on how much of the compositor preview must live in the same surface. If preview must be GPU-composited in-app, Rust-native reduces the WebView↔GPU handoff problem; if the UI is mostly forms/lists, Tauri wins on velocity." The console is dominated by forms, lists, editors, and a *preview thumbnail* — not by an in-app GPU compositor — which is the condition under which Tauri wins. That is the decision this ADR records, with the residual handoff risk pushed to spike S5.

## Options considered

### Option A — Tauri (system WebView) — **CHOSEN**

*How it fits:* Web front-end (HTML/CSS/JS) for the console; Rust core exposes services over Tauri IPC; outputs are separate native wgpu windows; a downscaled composited-frame preview is streamed into the UI.

**Pros (evidence-based):**
- **Richest, fastest path for a dense operator console.** FEASIBILITY §1 records that egui/iced are "neither as rich as web UI for dense operator screens" [A2]; the web toolkit gives mature layout, editing, and virtualised-list ergonomics for EPIC-A/B/C/D authoring, the command palette (FR-015), and undo/redo (FR-016) with the least custom UI engineering.
- **Very low footprint.** Tauri idle memory ~30–40 MB vs Electron 200–300 MB; installers <10 MB (DOCUMENTED, High) [T2]. This sits comfortably inside NFR-002 (≤300 MB idle, shared with media/render engines) and helps the NFR-010 soak and NFR-011 idle-CPU budgets.
- **Mature platform accessibility.** A DOM/ARIA UI has a well-established keyboard and screen-reader story, supporting NFR-019 (keyboard-only), NFR-020 (WCAG contrast), and NFR-021 (accessible names/roles on core live controls). *(INFERRED, grounded in the maturity gap FEASIBILITY notes between web UI and immediate-mode toolkits — not a directly measured claim; carried into S5's acceptance bar.)*
- **Alignment.** Tauri 2.0 shipped late 2024 with per-OS bundling and a growing ecosystem [T2]; keeps the codebase Rust-centric (core + Tauri host) while honouring the brief's Rust/wgpu leaning without rubber-stamping the WebView-as-compositor part.

**Cons / risks (evidence-based):**
- **The WebView↔GPU preview handoff is unproven.** Because the WebView cannot composite [T1], the live/staged preview must arrive as a *downscaled raster stream* from the wgpu engine over IPC. Delivering that stream at adequate fidelity and within the FR-013 ≤100 ms reflect-live target, at bounded CPU/bandwidth, is the open question — the reason confidence is **Medium** and the reason S5 exists (`ARCHITECTURE.md` §16 risk row; RISK-012). The macOS 60 fps WebView cap [T1] bounds preview refresh (acceptable for a preview, but a ceiling nonetheless).
- **Cross-platform WebView inconsistency.** WebKitGTK (Linux) vs WebView2 (Windows) vs WKWebView (macOS) have documented font/CSS differences requiring per-OS testing [T2] — a cost against NFR-014 parity.
- **New coupling surface.** Introduces an IPC preview-streaming path that must be strictly bounded and must never back-pressure or share fate with the output path (NFR-024).

*(Electron was excluded up front: 200–300 MB idle and >100 MB installers [T2] conflict directly with NFR-002/NFR-010, and its Chromium compositor is still browser-bounded, not a bespoke multi-output pipeline.)*

### Option B — Rust-native egui / iced (+ winit + wgpu) — **FALLBACK**

**Pros (evidence-based):**
- **Eliminates the handoff risk.** A wgpu-native UI can GPU-composite the preview in the **same** surface family as the outputs, removing the WebView↔GPU boundary entirely [R1][R2]. FEASIBILITY §1 calls a hybrid "the natural resolution" and this is its clean form when the preview must be GPU-composited in-app.
- **Single language/runtime end-to-end** (Rust): shares types with the core, no JS bridge, no browser runtime, very low memory, and reuses the winit borderless-fullscreen path already chosen for outputs (ADR-0004) [W1 lineage].

**Cons (evidence-based):**
- **Weaker for a dense console.** FEASIBILITY §1: egui/iced "matured but egui simplest, iced still improving, neither as rich as web UI for dense operator screens" [A2] → more custom UI engineering for editors, palette, and layout; slower velocity against METRIC-006.
- **Weaker accessibility maturity.** Immediate-mode (egui) / still-evolving (iced) toolkits have a less mature screen-reader story than the DOM, a real risk against NFR-021.

**Why fallback, not primary:** it trades the console's richness, velocity, and accessibility maturity to buy away a preview-handoff risk that a *downscaled raster stream* may well retire cheaply. We keep it as the S5-gated fallback rather than paying that cost pre-emptively.

### Option C — Avalonia (.NET / C#) — **REJECTED**

**Pros (evidence-based):** Multi-window/multi-display supported; Skia renderer over OpenGL/Vulkan with deferred composition and Avalonia 12 FPS gains on complex scenes [A1]; a genuinely rich UI toolkit (richer than egui/iced); mature adoption (JetBrains, Unity, GitHub, Schneider) [A1]; a good productivity/GPU balance.

**Cons (evidence-based):**
- **Adds a managed .NET runtime beside the Rust core** — a second language/runtime boundary and a heavier footprint than Tauri or egui [A1], in tension with NFR-002/NFR-010.
- **Team-skill dependency:** "team must be C#-fluent" [A1]; the core is Rust, so Avalonia adds a language the team must staff, and Rust↔.NET interop for core services is more friction than Rust↔JS (Tauri IPC) or Rust-native.
- **No decisive win on the actual problem:** its GPU/compositing strengths are largely moot because compositing lives in wgpu (ADR-0002), not the UI toolkit; its video-over-GPU path is "less turnkey than Qt/wgpu" with "no first-class alpha-video pipeline" [A1]; and it still crosses a cross-runtime boundary to reach the wgpu engine — so it does **not** resolve the preview handoff any better than Tauri while costing more footprint and a new language.

## Consequences

**Positive**
- Fastest route to a rich, keyboard-first, accessible operator console (EPIC-A/B/C/D; FR-013/014/015/016; NFR-019/020/021).
- Low idle footprint and installer size protect NFR-002/NFR-010/NFR-011.
- Keeps compositing where the evidence says it belongs (wgpu, ADR-0002); the shell stays a thin, replaceable client.

**Negative / costs**
- Commits us to building and hardening a **downscaled composited-frame preview stream** from the wgpu engine into the WebView, bounded so it never shares fate with the output path (NFR-024). Its fidelity/latency (FR-013 ≤100 ms) is unproven until S5.
- Per-OS WebView testing burden (WebKitGTK/WebView2/WKWebView) for NFR-014 parity; a macOS 60 fps preview-refresh ceiling [T1].
- Two UI technologies exist in principle (WebView primary, Rust-native fallback) until S5 settles the choice — a small parallel-prototype cost.

**What it commits us to**
- The shell owns **no authoritative state**; all live-critical logic stays in the Rust core, so a WebView stall cannot blank output (NFR-024; ADR-0001 two-process isolation). The console is a LAN-less local peer of the same command/preview surface the mobile controller uses.
- A **bounded** IPC preview channel (downscaled frames, back-pressure-safe, cancellable) — never an unbounded queue (NFR-010/FR-084).
- Cross-platform WebView parity testing in CI (NFR-014).
- Holding the line from ADR-0002: the WebView must **never** regress into compositing live outputs.

## Fallback & validation

- **Validating spike: S5** (FEASIBILITY §10). Build parallel thin prototypes — Tauri WebView vs Rust-native egui/iced — and **measure GPU-preview fidelity, latency (against FR-013 ≤100 ms), memory, and the keyboard/screen-reader accessibility bar (NFR-019/021)** for the operator console.
- **Fallback = Option B (Rust-native egui/iced + winit + wgpu).** Trigger the fallback if S5 shows the downscaled preview stream cannot meet fidelity/latency at acceptable CPU/bandwidth in the WebView, **or** the WebView cannot meet the operator-UI keyboard/accessibility bar. The fallback dissolves the handoff by compositing the preview in the same wgpu surface family as the outputs [R1][R2], at the documented cost of console richness/velocity/accessibility maturity [A2]. Avalonia (Option C) is a secondary alternative only, not the fallback, for the footprint/language reasons above.
- **Confidence is Medium precisely because S5 has not run.** No component here is individually doubtful; the unproven part is the WebView↔GPU preview handoff. This ADR is Accepted with that risk explicitly recorded and a concrete fallback, consistent with `ARCHITECTURE.md` §17 escalating ADR-0003 as a Medium-confidence, spike-gated decision.

## Requirement / PRD references

- **Console scope:** EPIC-A (FR-001..008), EPIC-B (FR-009..017), EPIC-C (FR-019/020/021/024), EPIC-D MVP (FR-025..031/035); command palette FR-015; undo/redo FR-016; Unicode/diacritics FR-017; stage-message authoring FR-162.
- **Preview / live control:** FR-012 (preview vs live), **FR-013 (current/next reflect live ≤100 ms)** — the binding latency target for the preview stream.
- **Accessibility:** NFR-019 (keyboard-only), NFR-020 (WCAG contrast), NFR-021 (screen-reader on core controls); METRIC-006 (time-to-first-slide ≤10 min).
- **Footprint / reliability:** NFR-002 (idle ≤300 MB), NFR-010 (12 h soak <5% growth), NFR-011 (idle CPU/GPU), NFR-014 (cross-platform parity), **NFR-024 (output-failure isolation)**, FR-084 (bounded queues/caches).
- **Architecture linkage:** ADR-0001 (split topology), **ADR-0002 (WebView is not the compositor)**, ADR-0004 (winit windowing); RISK-012 (Tauri-WebView-as-compositor tension), `ARCHITECTURE.md` §16 risk row (WebView↔engine preview fidelity → S5; Rust-native fallback), §17 (escalated Medium-confidence ADR).
- **Feasibility evidence:** FEASIBILITY §1 (framework trade-off table: Tauri, Avalonia, Rust-native rows), §2 (rendering options — WebView compositor limits), §9 (undecided operator-UI leaning), §10 spike **S5**; findings [T1] WebView GPU limits, [T2] Tauri/Electron footprint & packaging, [A1] Avalonia, [A2] egui/iced richness, [R1][R2] wgpu preview compositing.
