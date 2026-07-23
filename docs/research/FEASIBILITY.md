# SelahCue — Cross-Platform / Offline / Performance Feasibility (RP-08, RP-09)

Stage: 2 (Discovery) · Date: 2026-07-23 · Owner: Software Architect
Status: **Feasibility EVIDENCE ONLY — NON-binding.** Final stack selection is a Stage 5 ADR decision. Nothing here chooses the stack; it maps trade-offs and identifies spikes.

## Method & classification discipline

Every finding is classified **OBSERVED / DOCUMENTED / INFERRED / UNKNOWN** with source URL, access date (2026-07-23), limitation, and confidence (High/Med/Low).

- **OBSERVED** = I directly ran/measured it. *No OBSERVED findings exist in this report* — no software was executed in this environment; all evidence is documentary or reasoned. This is itself a limitation and the reason several spikes are proposed.
- **DOCUMENTED** = stated in vendor/framework/official docs, benchmarks, or reputable secondary sources.
- **INFERRED** = my synthesis/reasoning from documented facts + domain knowledge; not directly sourced.
- **UNKNOWN** = not resolvable from available evidence; needs a spike.

The brief *suggests* Rust / Tauri / wgpu / GStreamer / SQLite but forbids choosing on that assumption alone. This report evaluates that suggested stack against alternatives and flags where the brief's suggestion has a real tension (notably Tauri's WebView vs. the GPU-compositing requirement).

---

## 1. Desktop-framework trade-off table

Requirements driving this: multi-window + multi-display fullscreen output control; GPU-accelerated compositing of text over motion backgrounds at 1080p60 on **independent** outputs with per-output layouts; media playback; per-OS packaging/code-signing; maturity.

| Framework | Multi-window / multi-display fullscreen | GPU compositing (text over 1080p60 video) | Memory / CPU footprint | Media playback | Packaging / signing | Maturity | Net fit for SelahCue |
|---|---|---|---|---|---|---|---|
| **Tauri (Rust + WebView)** | Multi-window supported; borderless fullscreen per-monitor achievable. But output windows are WebViews. | ⚠️ **Key risk.** WebView canvas/CSS GPU-acceleration is inconsistent; documented Tauri bug: CSS filters/canvas can hit CPU not GPU [T1]. macOS Tauri capped at 60fps, no ProMotion [T1]. Native GPU-under-WebView compositing is an open feature request [T1]. | ✅ Very low: ~30–40 MB idle vs 200–300 MB Electron; installers <10 MB [T2]. | Via `<video>` (WebView codecs vary per platform) or a Rust sidecar (GStreamer/mpv) into a separate window. | Tauri bundler does per-OS packaging; still need OS certs. Cross-OS WebKitGTK font/CSS differences require testing [T2]. | 2.0 shipped late 2024; adoption +35% YoY [T2]. | Great shell/UI + control app; **compositing engine cannot live in the WebView** — needs a native/wgpu render path beside it. |
| **Electron (Chromium)** | Mature multi-window/multi-display; consistent Chromium everywhere. | ✅ Chromium canvas/WebGL/WebGPU is well GPU-accelerated (better than WebKit for canvas/3D per Tauri issue thread [T1]). Still a browser compositor, not a bespoke pipeline. | ❌ High: 200–300 MB idle, >100 MB installers [T2]. | `<video>` + WebCodecs/WebGPU; consistent. | Mature signing tooling (electron-builder) [S1]. | Very mature. | Viable but heavy; footprint conflicts with the 8–12h soak + low-idle goals. Compositing still browser-bounded. |
| **Native Qt / C++** | Full control of windows/displays/fullscreen; battle-tested in AV. | ✅ Qt Quick/RHI (Vulkan/Metal/D3D12) + custom shaders; direct video-texture compositing feasible. | ✅ Low-moderate, tunable. | Qt Multimedia (can use GStreamer backend). | Per-OS toolchains; Qt licensing (commercial vs LGPL) is a compliance item. | Extremely mature; used across broadcast AV. | Strong technical fit; cost = C++ effort + Qt licensing review. |
| **.NET / Avalonia (C#)** | Multi-window multi-display supported. | ✅ Skia renderer over OpenGL/Vulkan; deferred composition; Avalonia 12 claims large FPS gains on complex scenes [A1]. Video-over-GPU compositing is less turnkey than Qt/wgpu. | ✅ Moderate (managed runtime). | LibVLCSharp / platform media; no first-class alpha-video pipeline. | .NET single-file + per-OS signing. | Mature; used by JetBrains, Unity, GitHub, Schneider [A1]. | Good balance of productivity + GPU; team must be C#-fluent. |
| **SwiftUI / WinUI (per-OS native)** | Best-in-class per platform (Metal/DirectComposition). | ✅ Native, excellent. | ✅ Lowest. | AVFoundation / Media Foundation, hardware decode + alpha. | Native store/signing. | Mature. | ❌ **Two+ separate desktop codebases** — contradicts single cross-platform desktop goal. Rejected as primary; useful as reference for platform APIs. |
| **Rust-native (egui / iced / winit + wgpu)** | winit gives borderless fullscreen per `MonitorHandle`; multi-window works. Caveat: winit multi-monitor *exclusive* fullscreen has documented rough edges — borderless-per-monitor + manual positioning is the reliable path [W1]. | ✅ **Best match to the requirement.** wgpu = Vulkan/Metal/DX12/GL, purpose-built for custom compositing pipelines; glyphon/wgpu-text for text; video frames uploaded as textures [R1][R2]. | ✅ Very low; no browser runtime. | Not built-in — pair with GStreamer/libmpv, upload decoded frames to wgpu textures [R1]. egui/iced are immediate/retained-mode UI, less rich than HTML for complex operator UI. | cargo + per-OS packaging + OS certs. | wgpu mature; egui/iced "matured but egui simplest, iced still improving, neither as rich as web UI for dense operator screens" [A2]. | ✅ Best for the **render/output engine**; ⚠️ weaker for the dense operator UI. Hybrid (web/Tauri UI + wgpu output) is the natural resolution. |

Sources: [T1] github.com/tauri-apps/tauri issues #4891/#8246 & discussion #11944; en.wikipedia.org/wiki/Tauri_(software_framework); [T2] raftlabs.com/blog/tauri-vs-electron-pros-cons; [A1] github.com/AvaloniaUI/Avalonia, avaloniaui.net; [A2] rust-pc.github.io/rust-windows-gui.html, an4t.com/rust-gui-libraries-compared; [R1] ginokent.github.io/en/posts/2026-03-04-wgpu-video-playback-pipeline; [R2] docs.rs/wgpu, wgpu.rs; [W1] github.com/rust-windowing/winit discussions #2030/#2808, issue #3628; [S1] electronjs.org/docs/latest/tutorial/code-signing. All accessed 2026-07-23.

**Framework takeaways**
- **DOCUMENTED (High):** Tauri idle memory ~30–40 MB vs Electron 200–300 MB [T2].
- **DOCUMENTED (Med):** Tauri/WebView GPU compositing is limited: CPU-bound canvas filters, 60fps macOS cap, no native-GPU-under-webview yet [T1]. **This is the single most important desktop finding** — it means the brief's Tauri suggestion works for the *UI/controller shell* but **not** as the high-performance *output compositor*.
- **INFERRED (High):** The realistic architecture is a **split**: a Rust core owning a wgpu compositor + native output windows, with the operator UI either in a WebView (Tauri) or Rust-native (egui/iced). This preserves the brief's Rust/wgpu leaning while sidestepping the WebView compositing ceiling.
- **UNKNOWN:** Whether winit multi-monitor independent fullscreen output is robust enough on all three desktop OSes for production — **spike required** [W1].

---

## 2. Rendering options (compositing text over motion backgrounds, 1080p60, independent outputs, per-output layouts)

| Option | How it composites | Strengths | Weaknesses / risks | Classification |
|---|---|---|---|---|
| **wgpu (native GPU)** | Decoded video frame → GPU texture; text via glyphon/wgpu-text as textured quads; shader blends layers per output. | Portable (Vulkan/Metal/DX12/GL), purpose-built; independent surfaces per monitor; full control of per-output layout/scene graph. Documented that CPU-decode + `write_texture` sustains ~249 MB/s ≈ 1080p30, and zero-copy paths reduce CPU→GPU transfer further [R1]. | Must build the compositor (scene graph, layout, transitions) ourselves. Zero-copy HW-decode→GPU interop is the hard part and is platform-specific. | **DOCUMENTED (High)** capability; **INFERRED (Med)** that 1080p60 across 2–3 outputs is achievable with HW decode + zero-copy — **needs a spike to confirm** [R1][R2] |
| **Native GPU compositing (Qt RHI / Avalonia Skia / Metal / D3D)** | Framework scene graph + shaders. | Mature, less to build than raw wgpu. | Ties us to that framework's language/runtime; alpha-video compositing varies. | **DOCUMENTED (Med)** [A1] |
| **Web-canvas / WebGL / WebGPU (Electron/Tauri WebView)** | Canvas/WebGPU in the page. | Fast to build; familiar. | WebKit (Tauri) canvas/CSS GPU-accel inconsistent + 60fps macOS cap [T1]; Chromium better but heavy; browser owns the compositor — limited control over independent fullscreen outputs and precise frame timing. | **DOCUMENTED (Med)** [T1] |

**Leaning (non-binding):** wgpu for the output compositor; web-canvas acceptable only if a spike shows Chromium/WebGPU (Electron) meets 1080p60 multi-output — unlikely to beat native for independent-output control. **INFERRED (Med).**

---

## 3. Media-playback options (codecs, hardware decode, alpha for lower-thirds, cross-platform)

| Option | HW decode | Alpha / transparency | Cross-platform | Notes | Classification |
|---|---|---|---|---|---|
| **GStreamer** | Broad: VA-API/NVDEC/Vulkan video; 1.28 adds Vulkan AV1/VP9 decode, AMD HIP portable accel [M1]. | ✅ VP8/VP9 alpha via `vp8/vp9alphadecodebin` (alpha muxed as extra WebM track → `GstVideoCodecAlphaMeta`) [M2]; `alpha` element for keying [M3]; VVC/H.266 alpha work emerging [M4]. | ✅ Win/mac/Linux; pluggable. | Most capable for alpha lower-thirds; complex to embed; plugin licensing (H.264/HEVC) is a compliance item. | **DOCUMENTED (High)** [M1][M2][M3] |
| **libmpv** | VA-API/VDPAU/NVDEC/Vulkan AV1 (stable ≥0.38) [M5]. | ⚠️ No documented first-class alpha-video track pipeline like GStreamer's; primarily opaque playback. | ✅ but HW video-output composition has known failure modes in some environments (e.g., WSL) [M5]. | Simplest high-quality player embed; weaker for alpha overlays. | **DOCUMENTED (Med)** [M5] |
| **Platform media (AVFoundation / Media Foundation / GStreamer-on-Linux)** | Best native HW decode + alpha (e.g., HEVC w/ alpha on Apple). | ✅ per-platform. | ❌ 3 separate integrations. | Lowest overhead per OS but triples integration + testing. | **INFERRED (Med)** |

**Leaning (non-binding):** GStreamer as the cross-platform media engine feeding GPU textures (aligns with brief), *because* it uniquely documents alpha-video handling needed for lower-thirds. libmpv is the fallback for opaque full-frame backgrounds. **DOCUMENTED (High) for GStreamer alpha; INFERRED (Med) for the texture-handoff design.**
Sources: [M1] linuxiac.com/gstreamer-1-28-multimedia-framework-released; [M2] discourse.gstreamer.org/t/gstreamer-transparency/1070; [M3] gstreamer.freedesktop.org/documentation/alpha/index.html; [M4] fluendo.com/blog/alpha-channel-for-vvc; [M5] mpv docs via cavecreekcoffee.com/reviews/best-linux-video-player-2026 & github.com/microsoft/wslg issue #1381.

---

## 4. Multiple independent outputs & transparent / browser-source / NDI feasibility

| Capability | Feasibility | Evidence | Classification |
|---|---|---|---|
| **Multiple independent fullscreen outputs, per-output layout** | Feasible with native windowing (winit per-`MonitorHandle`, Qt, native). Each output = own surface + own scene; not achievable cleanly inside one browser compositor. winit multi-monitor exclusive-fullscreen has rough edges → use borderless per-monitor + manual placement. | [W1] | **DOCUMENTED (Med)** capability; robustness **UNKNOWN** → spike |
| **Transparent / alpha output (lower thirds over external video / key)** | Feasible: GStreamer alpha pipelines + premultiplied-alpha compositing to a transparent output window (OS-level transparent windows on all three platforms). | [M2][M3] | **DOCUMENTED (Med)**; end-to-end transparent-window output **needs a spike** |
| **NDI output** | Feasible & royalty-free SDK, but **distribution obligations**: must link to ndi.video near every NDI use, in docs, on website; NDI 6 needs a License ID; only header files are MIT for OSS inclusion (the SDK binaries are under the NDI license). | [N1] | **DOCUMENTED (High)** for terms; integration effort **INFERRED (Med)** |
| **Browser-source style output (for OBS/vMix ingestion)** | Feasible via NDI, or by exposing an output as a virtual camera / an HTTP/WebRTC surface. Common in the OBS/vMix ecosystem (RP-02). | (RP-02 adjacency) | **INFERRED (Med)** |

Sources: [N1] docs.ndi.video/all/developing-with-ndi/sdk/licensing & /software-distribution; downloads.ndi.tv NDI License Agreement PDF (Nov 2024). [W1] as above.

**Compliance flag:** NDI license attribution + License-ID requirements feed RP-10/RP-11 registers. **DOCUMENTED (High).**

---

## 5. Mobile-controller options (LAN remote, not cloud)

| Stack | LAN/WebSocket suitability | Perf | Native LAN/mDNS access | One codebase both OS | Classification |
|---|---|---|---|---|---|
| **Flutter** | Isolates parallelize message parsing; secondary source claims ~2.7× faster WS message handling vs RN, avoids JS-thread saturation [MO1]. Fastest startup; steady memory [MO1]. | High | Good via plugins (mDNS, sockets). | ✅ | **DOCUMENTED (Med)** — perf multipliers are from a secondary blog, treat as directional |
| **React Native** | New Architecture removed bridge jank; strong native-module ecosystem for BLE/NFC/network [MO1]. Memory grows more; needs iOS tuning [MO1]. | Med-High | Excellent native-module access. | ✅ | **DOCUMENTED (Med)** |
| **Native (Swift + Kotlin)** | Best raw control (NWListener/NSD, Bonjour first-class). Lowest memory [MO1]. | Highest | Best (Bonjour/NSD native). | ❌ two codebases. | **DOCUMENTED (Med)** |

"By mid-2026 both Flutter & RN closed historic perf gaps; equivalent for standard apps" [MO1]. A LAN remote is a *standard* app (lists, buttons, a socket) → developer velocity + one codebase matter more than raw perf.
**Leaning (non-binding):** Flutter or React Native (single codebase) for the controller; native only if deep OS integration (e.g., reliable background Bonjour) proves necessary in a spike. **INFERRED (Med).**
Source: [MO1] synergyboat.com/blog/flutter-vs-react-native-vs-native-performance-benchmark-2025; videosdk.live/developer-hub/websocket/websocket-react-native.

---

## 6. LAN discovery / pairing / protocol options

| Concern | Option | Evidence | Classification |
|---|---|---|---|
| **Discovery** | mDNS / DNS-SD (Bonjour). RFC 6763 DNS-SD over mDNS (UDP 5353); zero-config LAN discovery, no central server [L1][L2]. Limitation: single LAN/VLAN only; multicast can be blocked on guest/AP-isolated church Wi-Fi. | [L1][L2] | **DOCUMENTED (High)**; church-network reliability **INFERRED (Med)** |
| **Pairing** | QR code carrying host + port + one-time pairing token/public key → controller scans, establishes trust. (QR-with-mDNS specifics not found in a single authoritative source.) | [L1] + INFERRED | **INFERRED (Med)** — pairing token design needs a spike |
| **Transport** | WebSocket (simplest, bidirectional, works everywhere) vs gRPC (typed, streaming, heavier) vs plain HTTP (request/response only). WS is the pragmatic default for command + live state. | (RP synthesis) | **INFERRED (Med)** |
| **Security** | LAN traffic is not private by default. Mitigations: TLS (self-signed cert pinned at pairing), authenticated pairing token, replay protection (nonce/sequence), rate limiting. DNS-SD security refs: DNSSEC/DoT, SRP for authenticated registration [L1]. | [L1] | **DOCUMENTED (Med)** — feeds RP-10 threat model |

Sources: [L1] dns-sd.org & RFC 6763 (hackmd.io/@thesuburbanboy mDNS/DNS-SD intro); [L2] apps.microsoft.com mDNS discovery.
**Security flag:** pairing/auth/replay/rate-limit design is a Stage-5 + RP-10 item; do **not** ship an unauthenticated LAN control channel.

---

## 7. Persistence notes (SQLite)

- **DOCUMENTED (High):** SQLite in WAL mode: readers + writer concurrent; on crash only uncommitted WAL txns are lost, DB integrity preserved [P1][P2]. Recommended prod config: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000` [P2].
- **DOCUMENTED (High):** Integrity via `PRAGMA integrity_check`; **backups must include `.db` + `-wal` (+ `-shm`)**, or checkpoint first with `PRAGMA wal_checkpoint(TRUNCATE)` then copy [P2][P3].
- **DOCUMENTED (Med):** Naive `fs.copyFile` of a WAL-mode DB **can corrupt** backups — use the SQLite online backup API or checkpoint-then-copy [P3].
- **INFERRED (High):** SQLite is well-suited to SelahCue: single-user desktop, offline-first, library/playlist/settings storage, no server. Store large media as files referenced by path, not BLOBs.
- **Suitability = strong.** Add: periodic `integrity_check`, WAL checkpointing, crash-safe backups, schema migrations, and a corruption-recovery path (RP-01 "recovery").

Sources: [P1] micrologics.org/blog/sqlite-in-production...; [P2] oneuptime.com/blog/post/2026-02-02-sqlite-production-setup; [P3] scottspence.com/posts/sqlite-corruption-fs-copyfile-issue.

---

## 8. Proposed measurable performance targets (NON-binding; to be ratified in Stage 5)

Targets are proposals grounded in comparable-product behaviour (ProPresenter reqs [PP1]) and framework capabilities. All are **INFERRED** unless a cited doc gives the number. Each needs a benchmark harness (spike) to validate.

| # | Metric | Proposed target | Basis | Classification |
|---|---|---|---|---|
| 1 | Cold startup (app ready) | ≤ 3 s cold; ≤ 1 s warm | Tauri <0.5 s / Electron 1–2 s launch [T2]; add app init | INFERRED (Med) |
| 2 | Idle memory | ≤ 300 MB | Tauri idle 30–40 MB [T2] + media/render engines | INFERRED (Med) |
| 3 | Presentation-active memory (1 output) | ≤ 1.5 GB | ProPresenter min 8 GB / rec 16 GB system RAM [PP1] | INFERRED (Med) |
| 4 | Transcription model resident | ≤ 2 GB | whisper large-v3 Turbo ~1.6 GB INT8 [W2] | DOCUMENTED (Med) |
| 5 | Media-cache memory ceiling | ≤ 1 GB, bounded + evictable | — | INFERRED (Low) |
| 6 | Slide-trigger latency (input→on screen) | ≤ 150 ms (target ≤ 80 ms) | perceptual immediacy; AV control norms | INFERRED (Med) |
| 7 | 1080p60 render | sustained 60 fps, <5% dropped frames, 1 output | wgpu 1080p bandwidth headroom w/ zero-copy [R1] | INFERRED (Med) |
| 8 | Multi-output | 2–3 independent 1080p60 outputs, ≥55 fps each | ProPresenter multi-screen; dedicated GPU >4 HD [PP1] | INFERRED (Low) |
| 9 | Transcription latency (behind live speech) | ≤ 2 s (goal ≤ 1 s) | faster-whisper/whisper.cpp "0.5–2 s behind live" [W2] | DOCUMENTED (Med) |
| 10 | Scripture-detection latency (after transcript) | ≤ 1.5 s incremental | detection runs on streamed transcript (RP-04) | INFERRED (Low) |
| 11 | Mobile-command latency (tap→desktop acts) | ≤ 200 ms on same LAN | WS RTT on LAN | INFERRED (Med) |
| 12 | TTS latency (text→first audio) | ≤ 1 s local | Piper RTF ~0.20, real-time on Pi-class HW [TT1] | DOCUMENTED (Med) |
| 13 | Long-run (8–12 h soak) memory stability | < 5% growth over 12 h; no unbounded leak | church-service duration; RN memory-growth caution [MO1] | INFERRED (Med) |
| 14 | Background CPU/GPU (idle, no presentation) | CPU < 3%, no needless GPU wake | battery/thermals [T2] | INFERRED (Low) |

Sources: [PP1] support.renewedvision.com min-system-requirements; [W2] codersera.com/blog/faster-whisper-vs-whisper-cpp-2026; [TT1] github.com/rhasspy/piper, localaimaster.com/blog/piper-tts-setup-guide; others as above.

---

## 9. Preliminary (NON-binding) architecture leaning

**Leaning: a Rust core with a split render/UI topology.**

- **Rust core** owning: wgpu compositor (text-over-motion, per-output scene graph), GStreamer media pipeline feeding GPU textures, SQLite (WAL) persistence, and the LAN control server (WebSocket + mDNS + authenticated QR pairing). Rationale: the GPU-compositing + independent-multi-output + alpha requirement is the hardest constraint and is best served by wgpu + native windowing, *not* a WebView.
- **Operator UI**: either Tauri WebView (rich, fast to build, low memory [T2]) **or** Rust-native egui/iced. **Undecided** — depends on how much of the compositor preview must live in the same surface. If preview must be GPU-composited in-app, Rust-native reduces the WebView↔GPU handoff problem; if the UI is mostly forms/lists, Tauri wins on velocity.
- **Output windows**: native wgpu surfaces per monitor (borderless fullscreen), transparent-capable for lower thirds; NDI as an additional output sink.
- **Mobile controller**: single-codebase Flutter or React Native, LAN-only, mDNS discovery + QR pairing + TLS/token over WebSocket.
- **AI (transcription/TTS)**: whisper.cpp (cross-platform, Metal/CUDA/Vulkan/CPU) [W2] and Piper (offline TTS) [TT1] as local defaults with provider abstraction (RP-03/05/06).

**Why this respects the brief without rubber-stamping it:** it keeps Rust/wgpu/GStreamer/SQLite where the evidence supports them, but explicitly **rejects using Tauri's WebView as the compositor** (the one place the brief's suggestion collides with documented WebView GPU limits [T1]).

> **This leaning presupposes spike S2 succeeds (per DISCOVERY-REVIEW C10/M10).** The wgpu-compositor-fed-by-GStreamer-GPU-textures topology depends on zero-copy HW-decode→wgpu interop (S2), which is genuinely limited and per-backend. If S2 fails on any OS, a **fallback architecture is required** — GStreamer `glvideomixer` / per-OS native compositor, or accepting 1080p30 or fewer simultaneous outputs. The "2–3 independent 1080p60 outputs" target (#8, INFERRED/Low) must be **gated on S1/S2 results** before it becomes a committed PRD requirement (OD-23). The media engine must also be constrained to **platform/HW-decode elements** (exclude gst-libav for encumbered codecs) to preserve the codec-patent safe harbor (OD-08a).

### What Stage 5 MUST decide via ADR
1. **Operator-UI shell:** Tauri WebView vs Rust-native (egui/iced) vs Avalonia/Qt — trade velocity vs GPU-preview integration.
2. **Windowing/output layer:** winit vs Qt vs platform-native for robust independent multi-monitor fullscreen [W1].
3. **Media engine:** GStreamer vs libmpv vs per-platform — decided by the alpha-lower-thirds + HW-decode-to-GPU spike [M2][M5].
4. **HW-decode→wgpu zero-copy interop** approach per OS (the biggest technical risk) [R1].
5. **Mobile framework:** Flutter vs React Native vs native (background-discovery reliability) [MO1].
6. **LAN protocol + security model:** WS vs gRPC; pairing/auth/replay/rate-limit (with RP-10) [L1].
7. **NDI inclusion & licensing** obligations acceptance [N1].
8. **Ratification of the §8 performance targets** against benchmark-harness results.

---

## 10. Key feasibility UNKNOWNs / spikes needed

| # | UNKNOWN | Spike | Why it's blocking |
|---|---|---|---|
| S1 | Can wgpu sustain **1080p60 across 2–3 independent outputs** with HW-decoded video + composited text on mid-range church hardware? | Build a wgpu multi-window compositor; feed HW-decoded frames; measure fps/CPU/GPU. | Core value prop; targets #7/#8 unproven [R1][W1] |
| S2 | **HW-decode → GPU zero-copy interop** per OS (VA-API/NVDEC/Metal/D3D → wgpu texture) | Prototype GStreamer→wgpu zero-copy on Win/mac/Linux. | Biggest perf risk; naive CPU copy may not hit 60fps [R1] |
| S3 | **Transparent/alpha output window** end-to-end (GStreamer alpha → premultiplied compositing → OS transparent fullscreen output) | Lower-third over external source demo on all 3 OS. | Lower-thirds requirement [M2][M3] |
| S4 | **winit (or chosen) multi-monitor independent fullscreen** robustness | Multi-display output test across OSes incl. hot-plug/DPI. | Documented winit multi-monitor rough edges [W1] |
| S5 | **Tauri WebView vs Rust-native** for operator UI + compositor preview | Parallel thin prototypes; measure GPU-preview fidelity + memory. | Decides the UI shell ADR [T1][T2] |
| S6 | **mDNS reliability on real church Wi-Fi** (AP isolation, multicast filtering) + QR pairing/auth | LAN discovery + pairing test on isolated/guest networks. | Remote is useless if discovery fails [L1] |
| S7 | **12-hour soak** memory/GPU stability with looping media + live transcription | Automated soak harness. | Target #13; church services run hours [MO1] |
| S8 | **Transcription + scripture-detection latency** on target CPU/GPU offline | Bench whisper.cpp large-v3 Turbo streaming + detection. | Targets #9/#10; #10 currently Low confidence [W2] |
| S9 | **Mobile framework** background LAN discovery reliability (iOS especially) | Flutter vs RN vs native background-Bonjour test. | Decides mobile ADR [MO1] |
| S10 | **Text shaping / Unicode / font coverage** for the custom GPU text stack (added per DISCOVERY-REVIEW C2/M2) — glyphon/wgpu-text render textured-quad glyphs but do not, alone, do complex-script shaping/bidi | Confirm a HarfBuzz / cosmic-text-class shaping layer for the cited languages (Yoruba/Hausa/Igbo/French/Spanish are LTR Latin+diacritics); prototype font-fallback. | Unicode is an unqualified brief requirement; RTL/complex-script (Arabic/Hebrew) proposed **scoped past MVP** (OD-22) — but Latin+diacritic shaping must be confirmed for MVP |
| S11 | **AI evaluation-set definition** (added per Stage-4 audit MAJOR-05/06; realises PRD FR-171) — the "non-speech" and "explicit-reference" benchmark corpora referenced by FR-102/FR-108/FR-121/METRIC-009 do not yet exist | Define each set's composition, source, size, and scoring protocol; assemble representative church-room audio (accents, PA bleed, silence/music) and a labelled explicit-reference set. | AI acceptance criteria are unverifiable until the corpora exist; must be delivered before Stage-10 measurement |

### Classification summary
- **OBSERVED:** 0 (nothing was executed here — the reason S1–S9 exist).
- **DOCUMENTED:** ~18 findings (Tauri/Electron footprint, WebView GPU limits, wgpu capability, GStreamer alpha, mpv HW decode, SQLite WAL, NDI terms, mDNS, whisper/Piper latency, ProPresenter reqs, code-signing).
- **INFERRED:** ~15 (split-architecture leaning, most §8 targets, protocol/pairing design, texture-handoff design).
- **UNKNOWN:** 9 spikes (S1–S9).

### Confidence posture
High confidence the suggested Rust/wgpu/GStreamer/SQLite *components* are individually capable. **Medium-to-low confidence** they combine to hit 1080p60 multi-output + alpha + 12h soak on modest church hardware **without the zero-copy interop and multi-window spikes** — those are the make-or-break unknowns Stage 5 must resolve before committing.

---

*All URLs accessed 2026-07-23. Secondary blog/benchmark sources (perf multipliers, footprint figures) are directional, not authoritative measurements; treat as DOCUMENTED-secondary and re-verify in spikes. No proprietary internals of any reference product were copied.*
