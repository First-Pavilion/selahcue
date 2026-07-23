# ADR-0004: Windowing / multi-output layer

- **Status:** Accepted
- **Date:** 2026-07-23
- **Confidence:** Medium
- **Validating spike:** S4 — *multi-monitor independent fullscreen robustness (incl. hot-plug + DPI) across Windows/macOS/Linux* (FEASIBILITY §10)
- **Owner:** Software Architect
- **Related ADRs:** ADR-0001 (Rust core + split render/UI topology), ADR-0002 (wgpu compositor + native output windows), ADR-0003 (Tauri operator-UI shell), ADR-0006 (HW-decode→GPU interop)

> **Decision in one line:** Use **winit** to drive one **borderless, per-monitor fullscreen** output window per physical display, each backing its own wgpu surface, with a **platform-native fallback** reserved for any OS-specific gap that spike S4 exposes.

---

## Context

SelahCue must drive multiple physical outputs from one desktop host, where each output is an **independent** fullscreen window with its own layout and scene (main audience, stage/confidence, and later lobby/stream/transparent lower-third). The architecture (ARCHITECTURE.md §6) makes each output "an independent native window with its own wgpu surface and scene, driven from one shared live state," so the windowing layer's job is to **enumerate, assign, identify, place, fullscreen, and reconnect** those windows — not to composite (that is ADR-0002/wgpu).

The forces from the PRD and feasibility evidence:

1. **Independent per-monitor fullscreen output.** FR-036 (main audience, fullscreen per-monitor at native resolution) and FR-037 (stage/confidence) require at least **two concurrent independent outputs** in MVP — main + stage — not a single output (PRD Scope: "Render/media bound (C-5, MAJOR-16)"). R2 adds ≥3 independent outputs (FR-039, NFR-006) with per-output configuration (FR-038).
2. **Windowed *and* fullscreen without restart.** FR-046 requires any output to switch between windowed and fullscreen operation live.
3. **Display identification and assignment.** FR-040 ("Identify" shows a number on each physical display; outputs assignable to displays) requires the windowing layer to enumerate monitors and map output→monitor.
4. **Hot-plug reconnection with isolation.** FR-041 / FLOW-009: unplug/replug an output → **no other output blanks**, and content auto-restores on reconnect. This is a hard invariant of NFR-024 (output-failure isolation): a display disconnect must not clear live output as a side effect.
5. **Cross-platform parity.** NFR-014 requires identical core presentation behaviour on Windows, macOS, and Linux (test matrix passes on all three) from a single desktop codebase (CON-1).
6. **Must sit beneath the wgpu compositor (ADR-0002).** The windowing layer's chosen output windows must present wgpu surfaces cleanly and independently per monitor; it is coupled to the Rust core (ADR-0001) and the wgpu render path.
7. **Low, bounded footprint** (NFR-001…003 principle) — no browser runtime in the output path.
8. **Transparent output windows (R2).** FR-052/FR-048/FR-141 (dedicated transparent lower-third / browser-source) need OS-level transparent, keyable fullscreen windows — the windowing layer must support alpha-capable surfaces (end-to-end validated separately by spike S3).

The **key open force** is robustness, not capability. FEASIBILITY classifies independent multi-monitor fullscreen as **DOCUMENTED (Med)** capability but **robustness UNKNOWN → spike** (§4), and specifically flags that **winit multi-monitor *exclusive*-fullscreen has documented rough edges** [W1: rust-windowing/winit discussions #2030/#2808, issue #3628], so "borderless-per-monitor + manual placement is the reliable path" (§1 Rust-native row). No finding in the feasibility report is OBSERVED — nothing was executed — so this decision rests on documentary evidence plus reasoning, and is gated on S4.

---

## Options considered

### Option A — winit (Rust-native windowing) — CHOSEN

winit exposes each display as a `MonitorHandle`; the reliable pattern is one borderless window sized/positioned to a monitor's bounds (not OS *exclusive* fullscreen), each carrying its own wgpu surface.

**Pros**
- **Idiomatic companion to wgpu (ADR-0002).** winit is the canonical surface provider for wgpu; each output = winit window → wgpu surface, with no cross-runtime handoff. This preserves the ADR-0001 Rust-core topology and avoids introducing a second GUI runtime beside wgpu (FEASIBILITY §1 Rust-native row: "wgpu = ... purpose-built for custom compositing pipelines ... best match to the requirement").
- **Single cross-platform codebase** (Vulkan/Metal/DX12/GL via wgpu underneath), directly serving NFR-014 without per-OS forks.
- **Borderless-per-monitor is the documented-reliable path** [W1], sidestepping the winit exclusive-fullscreen rough edges rather than fighting them.
- **Very low footprint** — no browser runtime in the output path (FEASIBILITY §1: "Very low; no browser runtime").
- **Per-window isolation** aligns with NFR-024: each output window is a separate surface, so one display's loss need not touch another's render loop.
- **Ecosystem alignment with ADR-0003.** Tauri's window layer (`tao`) is a winit-derived fork, so the operator-UI shell and the output windows share lineage and mental model.

**Cons / risks**
- **Robustness is UNKNOWN, not proven.** Independent multi-monitor fullscreen robustness — including **hot-plug and DPI changes** — is exactly the S4 unknown [W1]; this is the make-or-break for FR-040/041 (RISK-014). Evidence is DOCUMENTED-secondary, not OBSERVED.
- **We own the output-manager logic ourselves.** winit gives windows and monitor handles, but display *assignment*, *identify* overlays, *reconnection/restore*, and DPI handling are ours to build — no framework does it for us.
- **Exclusive-fullscreen avoided.** The lowest-latency, tear-free exclusive path has rough edges [W1], so we rely on borderless windows, which on some OSes are compositor-mediated (vsync/latency behaviour is per-backend and must be measured against NFR-004/005 in S1/S4).
- **Transparent-window fidelity varies per backend.** Alpha-capable fullscreen output (FR-052, R2) is feasible in principle (FEASIBILITY §4, DOCUMENTED Med) but "needs a spike" (S3) — winit does not guarantee uniform behaviour across Win/mac/Linux.

### Option B — Qt (Qt Quick / RHI)

**Pros**
- **Full, battle-tested control of windows/displays/fullscreen; used across broadcast AV** (FEASIBILITY §1 Qt row) — the most mature multi-display story of the three, with the most-proven hot-plug/DPI handling.
- Framework-provided scene graph reduces some window-management build effort.

**Cons / risks**
- **Runtime/language impedance with the chosen core.** Introduces a C++/Qt runtime and QML into an otherwise Rust core (ADR-0001) whose compositor is wgpu (ADR-0002). Using Qt *only* for windowing while compositing in wgpu is an awkward split (Qt's RHI scene graph vs an external wgpu surface); using Qt for compositing too would displace the ADR-0002 decision.
- **Licensing is a compliance item.** FEASIBILITY §1 explicitly flags "Qt licensing (commercial vs LGPL) is a compliance item"; the proprietary-build dependency policy (PRD §Licensing: "no GPL/AGPL in the proprietary build") makes this a gating review, not a footnote.
- **Heavier footprint** than a Rust-native windowing layer, working against the low-idle / 12h-soak principle.

### Option C — Platform-native windowing per OS (Metal/DirectComposition + Win32, AppKit, Wayland/X11)

**Pros**
- **Best-in-class per platform** (FEASIBILITY §1 SwiftUI/WinUI row: "Best-in-class per platform (Metal/DirectComposition)"): the highest-fidelity hot-plug, DPI, exclusive-fullscreen, and transparent-window behaviour, and the lowest overhead.

**Cons / risks**
- **Two-plus separate desktop codebases** for the windowing layer — FEASIBILITY §1 rejects the all-native approach as primary precisely because it "contradicts [the] single cross-platform desktop goal" and is "Rejected as primary; useful as reference for platform APIs."
- **Triples integration + test surface** against NFR-014, for a layer (window placement) that is not itself the product's differentiator.
- Highest effort and slowest to a working two-output MVP.

---

## Decision

Adopt **winit** as the windowing / multi-output layer, driving **one borderless, per-monitor fullscreen window per physical display**, each backing an independent wgpu surface and scene (ADR-0002). Deliberately use **borderless-per-monitor placement rather than OS exclusive fullscreen**, because that is the path the evidence documents as reliable and it sidesteps the winit exclusive-fullscreen rough edges [W1]. Build the **output manager** (enumerate → assign → identify → place → fullscreen/window → monitor hot-plug → restore) on top of winit's `MonitorHandle` API.

Reserve a **platform-native fallback** — a targeted, per-OS shim (not a full native rewrite) — for any specific capability where S4 shows winit is not robust enough on a given OS (e.g. native display-enumeration / hot-plug events, DPI-change handling, or a transparent output surface).

This choice is **Medium confidence**: the individual capability is documented, but the cross-OS robustness (multi-monitor + hot-plug + DPI) is an UNKNOWN that only spike **S4** can confirm. We are choosing the option that best preserves the Rust-core / wgpu topology (ADR-0001/0002) and the single-codebase goal (NFR-014), while keeping an explicit, bounded exit if S4 fails on a platform.

---

## Consequences

### Positive
- **Native, zero-handoff integration with wgpu** — each output window presents its own wgpu surface, so the output path is Rust-native end to end (ADR-0001/0002) with no second GUI runtime.
- **Single cross-platform codebase** for windowing, serving NFR-014 directly and keeping the low-footprint principle (no browser runtime in the output path).
- **Per-window isolation supports NFR-024** — each output is a separate window/surface with its own render loop, so a display disconnect or per-output fault is contained by construction (the compositor holds the last-good frame per ADR-0002 §6).
- **Avoids Qt licensing exposure** and the C++/Qt runtime split.
- **Borderless-per-monitor** sidesteps the documented winit exclusive-fullscreen bugs [W1] from day one.
- **Ecosystem alignment** with the Tauri UI shell (ADR-0003), whose `tao` window layer shares winit lineage.

### Negative
- **We own the hard parts.** Display assignment, the FR-040 "identify" overlay, FR-041 reconnection/restore, and DPI/scale handling are our code, not a framework's — more surface to build, test, and keep correct across three OSes.
- **Robustness is unproven until S4.** winit multi-monitor + hot-plug + DPI is a documented rough-edge area [W1]; MVP dual-output is best-effort until S4 passes (PRD RISK-014).
- **Borderless (not exclusive) fullscreen** may incur compositor-mediated vsync/latency on some OSes; this must be measured against NFR-004 (slide-trigger ≤150ms) and NFR-005 (1080p60) in S1/S4, not assumed.
- **Transparent-window output (FR-052, R2)** behaviour is per-backend and not guaranteed uniform; it carries its own validation (S3) and may itself trigger the native fallback on one OS.
- **A native-shim budget must be carried** — the fallback is bounded but non-zero engineering cost that only materialises after S4.

### What this commits us to
- A **Rust-native windowing stack coupled to wgpu** (ADR-0001/0002) — reversing it later means revisiting the compositor decision, not just swapping a library.
- Building and owning an **Output manager** component (ARCHITECTURE.md §4): enumerate/assign/identify/place/reconnect, with a **manual-placement fallback UX** (drag/assign a window to a monitor) for environments where automatic per-monitor fullscreen misbehaves.
- A **per-OS test matrix** for windowing (NFR-014), including monitor hot-plug and DPI-change cases.
- Treating **S4 as a gate** before committing FR-040/FR-041 (RISK-014); NFR-005/006 remain spike-gated on S1/S2 (RISK-013/OD-23) and are out of scope for this ADR's windowing decision.
- Keeping a **targeted platform-native fallback path** available per OS, rather than assuming winit is sufficient everywhere.

---

## Fallback / validation

**Validating spike — S4 (blocking for FR-040/041; RISK-014):** Build a multi-window winit + wgpu output test that runs **two-plus independent borderless-fullscreen outputs** across Windows, macOS, and Linux and exercises **monitor hot-plug (unplug/replug) and DPI/scale changes**, asserting that (a) each output stays independent, (b) disconnecting one output never blanks another (NFR-024/FR-041/FLOW-009), and (c) content auto-restores on reconnect. Latency/frame behaviour of the borderless path is measured here and in S1 against NFR-004/005.

**Fallback ladder if S4 fails on a platform:**
1. **Manual-placement fallback (first line, already committed as UX).** Operator drags/assigns each output window to its target monitor and toggles fullscreen manually (FR-046) — the "borderless per-monitor + manual placement is the reliable path" position from FEASIBILITY §1/§4. MVP dual-output remains best-effort under this fallback (PRD Scope bound).
2. **Targeted platform-native shim (Option C, scoped).** For the specific failing capability on the specific OS — e.g. native monitor enumeration/hot-plug notifications, native DPI handling, or a native transparent output surface — drop to a per-OS native call behind the output-manager interface, keeping winit everywhere else.
3. **Per-OS native windowing for that platform only (worst case).** If an entire OS proves unworkable through winit, replace the windowing layer *for that OS only* with native windowing, accepting the higher test cost on that platform while the other two stay on winit.

**Adjacent validations (not gating this ADR but touching the same layer):** S3 (end-to-end transparent/alpha fullscreen output for FR-052/048, R2), S1/S2 (1080p60 multi-output + HW-decode→GPU interop; NFR-005/006, RISK-013, ADR-0006). If S2 fails, the number of simultaneous outputs may be reduced regardless of windowing (ADR-0006 fallback), which relaxes — not tightens — the demand on this layer.

---

## Requirement / PRD references

- **MVP outputs:** FR-036 (main audience fullscreen per-monitor), FR-037 (stage/confidence), FR-040 (display identification & assignment), FR-041 (reconnection restores exact content, no other output blanks), FR-046 (windowed *and* fullscreen without restart).
- **R2 output expansion:** FR-038 (independent per-output configuration), FR-039 (≥3 independent outputs), FR-042 (output health), FR-043 (test patterns), FR-044 (per-output transforms), FR-045 (multiview), FR-047 (livestream layout), FR-048/FR-052 (transparent/browser-source & dedicated alpha lower-third output), FR-140/FR-141 (NDI / browser-source endpoints).
- **NFRs:** NFR-014 (cross-platform parity Win/mac/Linux), NFR-024 (output-failure isolation), NFR-004 (slide-trigger latency) and NFR-005/NFR-006 (1080p60 single/multi-output — spike-gated S1/S2, out of scope here).
- **Flows / constraints / risks:** FLOW-009 (display reconnection), CON-1 (desktop authoritative), CON-2 (offline core), RISK-014 (MVP dual-output windowing robustness → S4), RISK-013 / OD-23 (multi-output perf → S1/S2).
- **Feasibility evidence:** FEASIBILITY §1 (framework trade-off table — Rust-native, Qt, per-OS native rows), §4 (multiple independent outputs; winit borderless-per-monitor guidance), §9 (split-topology leaning), §10 spikes **S4** (windowing robustness), S1/S2 (perf/interop), S3 (transparent output); source **[W1]** github.com/rust-windowing/winit discussions #2030/#2808 & issue #3628 (accessed 2026-07-23). No OBSERVED evidence exists — all findings are DOCUMENTED/INFERRED, which is why S4 gates this decision.
