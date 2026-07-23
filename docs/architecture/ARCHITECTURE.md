# SelahCue — System Architecture

Version: 1.0 (Stage 5) · Date: 2026-07-23 · Owner: Software Architect · Status: For independent review + Stage 5 gate

This is the master architecture. Decision detail lives in the ADRs (`docs/architecture/adr/`); UX in `docs/design/`. Every choice is grounded in the PRD (`docs/product/prds/SelahCue-PRD.md`) and the feasibility evidence (`docs/research/FEASIBILITY.md`) — **not** in the brief's suggestions, which are evaluated as options in the ADRs.

## 1. Architectural principles (derived from the PRD)

1. **Desktop-authoritative.** The desktop app owns all live state. Mobile and cloud are assistive and optional (CON-1).
2. **Offline-first core.** Slides, local scripture, media, timers, blackout/clear work with zero network/cloud/mobile/AI (CON-2, NFR-015).
3. **Output-failure isolation.** No component failure may blank/clear live output as a side effect (NFR-024). The render/output path is isolated from control-plane and AI load. **Fault isolation and security isolation are distinct:** untrusted-media/font decode runs out-of-process in a sandbox (ADR-0016), so a decoder crash contains to a placeholder and a decoder exploit cannot compromise the host. The invariant is verifiable via the engine test seam (ADR-0015).
4. **AI is an assistant, never a gate.** AI/provider failures cannot block core controls (FR-083). AI runs out-of-band and is operator-confirmed.
5. **Security by construction.** The LAN control plane is untrusted; every message is encrypted, authenticated, authorised, replay-protected, and validated (§10).
6. **Low, bounded resource use.** Native GPU rendering; bounded queues/caches; lazy model loading (NFR-001..003,010).
7. **Recoverable.** Continuous autosave + crash recovery restore exact live state (FR-074/075).

## 2. Technology decisions (ADR index)

Decisions are recorded as ADRs; the one-line outcomes:

| ADR | Decision | Confidence | Validating spike |
|---|---|---|---|
| ADR-0001 Core language & topology | **Rust** core; split render/UI process topology | High | — |
| ADR-0002 Rendering / compositor | **wgpu** (native GPU) + native output windows; **WebView is NOT the compositor** | High | S1/S2 |
| ADR-0003 Operator-UI shell | **Tauri (WebView)** for the dense operator console; native wgpu windows for outputs + a streamed preview into the UI | Medium | S5 |
| ADR-0004 Windowing / multi-output | **winit** borderless-per-monitor fullscreen; platform-native fallback | Medium | S4 |
| ADR-0005 Media engine | **GStreamer** (alpha for lower-thirds; HW decode); platform/HW-decode elements only (no gst-libav for encumbered codecs) | High | S3 |
| ADR-0006 HW-decode → GPU interop | Per-OS zero-copy (VA-API/NVDEC/Metal IOSurface/D3D11 shared handle); **fallback:** glvideomixer / 1080p30 | Medium-Low | S2 (make-or-break) |
| ADR-0007 Persistence | **SQLite (WAL)** + **SQLCipher** at-rest; media as path-referenced files; versioned migrations | High | — |
| ADR-0008 LAN protocol & security | **WebSocket over TLS 1.3** with QR-pinned self-signed host cert; mDNS + QR-fallback discovery; per-device keypair-bound tokens; nonce+timestamp replay protection; server-side RBAC | High | S6 |
| ADR-0009 Mobile framework | **Flutter** (single codebase; platform channels for mDNS/keystore) | Medium | S9 |
| ADR-0010 AI/provider abstraction | Local-first (whisper.cpp; llama.cpp for notes) behind capability interfaces; pluggable consent-gated cloud adapters; isolated from presentation core | High | S8 |
| ADR-0011 Observability | `tracing`-based structured logs; local rotating logs; redacted diagnostics bundle; telemetry opt-in only | High | — |
| ADR-0012 Packaging & updates | Per-OS installers; code-signing; signed update feed + anti-rollback (heed Sparkle CVE-2025-0509); mobile via app stores | High | — |
| ADR-0013 NDI output | Accept NDI SDK (attribution + License-ID obligations); R2 | Medium | — |
| ADR-0014 Text shaping | **cosmic-text / HarfBuzz** shaping in the wgpu text stack (Latin+diacritics MVP; RTL later) | Medium | S10 |
| ADR-0015 Testable rendering engine | Headless render + pixel readback + deterministic mode + fault-injection hooks + drivable IPC; per-backend GPU CI matrix | High | — |
| ADR-0016 Decode isolation | Out-of-process **sandboxed** media/font decode (fault **and** security isolation) | High | S2 |

**The load-bearing correction to the brief:** ADR-0002/0003 reject using Tauri's WebView as the high-performance compositor (documented WebView GPU limits). The WebView is the operator *console*; the *compositor* is native Rust + wgpu.

## 3. System context

```
        ┌─────────────────────────┐        LAN (TLS 1.3, paired)      ┌────────────────────┐
        │  Mobile controllers      │◀────────────────────────────────▶│  DESKTOP HOST       │
        │  (Flutter; Android/iOS)  │   WebSocket control + preview     │  (authoritative)    │
        └─────────────────────────┘                                    │                    │
                                                                        │  Rust core         │
   Physical outputs ◀── native wgpu windows ── main / stage / lobby /   │  ├─ Engine (wgpu)  │
   NDI / browser-source (R2)                                            │  ├─ Media (GStr)   │
                                                                        │  ├─ Data (SQLite)  │
        ┌─────────────────────────┐   HTTPS (opt-in, consent-gated)    │  ├─ LAN server     │
        │  Cloud AI/STT providers  │◀────────────── R3+ ──────────────▶│  ├─ AI providers   │
        │  (user API keys)         │                                    │  └─ Tauri UI shell │
        └─────────────────────────┘                                    └────────────────────┘
```

## 4. Component architecture (desktop core)

The desktop is a **Rust core** exposing services to a **Tauri operator-UI shell** (web front-end) and driving **native output windows**. Two-process isolation: the render/output engine is insulated so UI or control-plane stalls never affect what's on screen.

| Component | Responsibility | Key PRD refs |
|---|---|---|
| **Engine (render/compositor)** | wgpu scene graph; per-output layout; text shaping; layer compositing; transitions; holds last-good frame on fault | FR-036/037/041/059/160, NFR-004/005/024 |
| **Output manager** | Enumerate/assign/identify displays; borderless-fullscreen windows; reconnection; transparent output; NDI sink (R2) | FR-036/040/041/046/048/140 |
| **Media engine** | GStreamer pipelines; HW decode → GPU textures; alpha video; preload; bounded cache | FR-066/067/069/070/071, NFR-013 |
| **Presentation service** | Slides, lyrics, scripture, templates, preview↔live, undo/redo, command palette | EPIC-A/B/C/D MVP |
| **Scripture service** | Bundled PD Bibles; reference parsing; search; pagination; history/favourites | FR-025..031/035 |
| **Timer service** | Monotonic-clock timers; TIME UP; per-output visibility; audit | EPIC-G, NFR-022 |
| **Data layer** | SQLite (WAL) + SQLCipher; repositories; migrations; integrity; backups | FR-079/154, NFR-017 |
| **Autosave/recovery** | Continuous checkpointing; crash recovery; crash-loop breaker; storage-exhaustion guard | FR-074/075/169, NFR-023 |
| **LAN control server** | WebSocket/TLS; mDNS advertise; pairing; RBAC; replay/rate-limit; message validation; preview streaming | EPIC-J MVP, FR-174 |
| **AI orchestration (R3+)** | Capability interfaces (STT/NoteGen); local + cloud adapters; consent; fallback; feedback guard; isolated from core | EPIC-K/L/M/N |
| **Security/secrets** | OS secret store; device keypairs; token issuance/revocation; audit log; update verification | FR-089/134/150/155/156 |
| **Tauri UI shell** | Operator console (editors, previews, service plan, live control), keyboard-first, accessible; receives streamed preview | EPIC-A/B, NFR-019/020/021 |

## 5. Desktop vs mobile responsibilities

- **Desktop (authoritative):** all live state, rendering, outputs, media, scripture, timers, AI orchestration, persistence, pairing/RBAC decisions. Validates and executes every command.
- **Mobile (controller):** discovery, pairing, role-scoped *requests* (advance/clear/blackout/timer/scripture-approve), preview + live-transcript view, output-health, stage messages. **Holds no authoritative state**; on disconnect the desktop is unaffected; stale requests on reconnect are rejected (FR-097/098).

## 6. Rendering & output architecture

Each physical output is an independent native window with its own wgpu surface and scene, driven from one shared live state so outputs can differ (main = 4 lyric lines over motion background; stage = current/next/clock/timer; stream = 2-line lower third). Text via cosmic-text/HarfBuzz → glyph atlas → textured quads; video frames uploaded (zero-copy where ADR-0006 succeeds) as textures; layers composited per-output. The engine runs its own render loop on a monotonic timeline; **a decoder/GPU fault holds the last presented frame and recovers out-of-band** (FR-160, NFR-024). MVP: main + stage (dual output, spike S4). R2: 3+ outputs, transparent/NDI/browser-source.

## 7. Media architecture

GStreamer pipelines per media item: `platform-HW-decoder → (zero-copy) → wgpu texture`. Encumbered codecs (H.264/HEVC/AAC) use **platform/HW-decode elements only** (no gst-libav) to preserve the codec-patent safe harbor (ADR-0005, FR-073). Alpha video (VP8/VP9-alpha) for transparent lower-thirds (R2). Bounded, LRU-evictable cache (NFR-013); next-item preload; missing media → placeholder, never black (FR-070). **Untrusted media/font decode runs out-of-process in a per-platform sandbox (ADR-0016)** so a decoder crash neither blanks outputs (restarts to a placeholder) nor compromises the host (contained RCE surface, threat T12).

## 8. Persistence & data model

SQLite in WAL mode (`synchronous=NORMAL`, `busy_timeout`), encrypted at rest with SQLCipher (FR-154); large media stored as files referenced by path (not BLOBs). Core entities: `service_plan`, `plan_item`, `document`(slide/song/scripture-set), `song`+`section`, `scripture_set`, `media_ref`, `template`/`theme`, `output_profile`, `device_pairing`, `role_grant`, `audit_log`, `provider_consent`, `transcript`(raw immutable + correction layer, R3), `detection`(R4), `sermon_note`(R5). Versioned forward-migrations with a documented rollback/backup step; `integrity_check` + checkpoint-safe backups (FR-079). Autosave writes a rolling checkpoint of live state + plan position + timers.

## 9. Local-network protocol

WebSocket over TLS 1.3; host presents a self-signed cert whose fingerprint is delivered in the QR pairing payload and pinned by the client (defeats LAN MITM without a CA). Discovery via mDNS with a QR-only fallback when multicast is blocked (FR-085). Pairing: single-use, short-TTL QR (host fingerprint + ephemeral secret) + host-side confirmation (FR-086). Sessions: per-device token bound to a device keypair (proof-of-possession); every command carries a monotonic nonce+timestamp (replay window ±30s) authenticated under the session key; strict schema/type/size validation (FR-174); per-device+global rate limits with output-path isolation (FR-091). RBAC enforced server-side per command against the device's granted role (FR-090). All traffic — control, previews, transcript, media — is encrypted (FR-088, NFR-016). **Multi-controller arbitration (OD-20, resolved):** the host **totally orders** incoming commands and applies **deterministic last-writer-wins**; when two controllers contend, the losing device receives a "contested — another operator acted" response (never a silent divergent state). **Protocol-spec deliverable (M5):** the versioned message schema, the command→role authorisation matrix, and the replay/nonce algorithm are produced as a single source-of-truth spec **before the mobile control path is implemented (Stage 7)** — not deferred to Stage 13 — and drive host/mobile contract tests, RBAC tests, and parser fuzzing.

## 10. AI / provider architecture (R3+)

Capability interfaces `STTProvider` and `NoteGenProvider`; a **local implementation is always present and the default** (whisper.cpp; llama.cpp-class notes). Cloud adapters are pluggable, **off by default, consent-gated per provider**, with a live "cloud active" indicator and user-supplied keys in the OS secret store. Graceful fallback to local on cloud/network error, never interrupting live output. The whole subsystem runs out-of-band from the render/output path (FR-083) and includes the **audio-feedback guard** (pause ingestion / gate detection while app audio plays to a shared output — FR-172). Scripture detection: deterministic parse → exact → fuzzy → semantic → confidence → dedup → **operator confirmation (default)**; auto-display is a discouraged, corroboration-gated opt-in (FR-115/116). AI evaluation sets defined by FR-171 / spike S11.

## 11. Security architecture

Assets, boundaries, and controls per the threat model (`docs/security/reviews/threat-model-draft.md`). Highlights: pinned-TLS LAN transport; single-use QR pairing + host confirmation; revocable keypair-bound device tokens; server-side deny-by-default RBAC; per-command replay protection + rate limiting; OS-secret-store-only secrets; append-only audit log; safe import (path-traversal/zip-slip) + untrusted-media decode hardening (FR-138/173); signed updates + anti-rollback (FR-155); SBOM + CVE/license scanning in CI (NFR-027); at-rest encryption + retention/deletion (FR-153/154); cloud opt-in + disclosure (FR-132/133/177); out-of-process sandboxed decode (ADR-0016). **Linux secret-storage fallback (OD-19, resolved):** where no Secret Service is present, secrets are encrypted in a local vault with a key derived from a user passphrase (Argon2id) — **never stored in plaintext**; this invariant holds for MVP on Linux.

## 12. Reliability & crash recovery

Continuous autosave (≤5s loss); crash recovery restores exact live state; **crash-loop breaker** offers resume-vs-clean after N rapid crashes (FR-075); **storage-exhaustion guard** warns before writes fail and reserves checkpoint headroom (FR-169); output-failure isolation (NFR-024); graceful handling of display/audio/mobile/network/provider loss; bounded queues/caches + cancellable background work; structured logs + diagnostics; 8–12h soak stability (NFR-010). **Testability seam (ADR-0015):** the render engine ships a headless/offscreen render path with pixel readback, a deterministic mode, and fault-injection hooks (device-loss, decoder fault, IPC stall, disk-full), so NFR-024/FR-160/FR-175 and cross-platform parity are verifiable in CI — including a per-backend GPU CI matrix (VA-API/NVDEC/Metal/D3D11) with a deterministic device-loss recovery assertion; wgpu is pinned and upgrades gated on re-running it.

## 13. Observability

`tracing` structured spans/events → local rotating log files (size-capped); redacted diagnostics bundle export (no secrets/transcripts — FR-082/T19); optional, opt-in telemetry only. Per-output health (connected/resolution/dropped-frames R2); provider usage/cost surfacing (R3). **Accessible live state (MVP):** the engine emits a **structured live-scene text payload** (current/next content, active layers, timer, on-air state) to the operator UI, which renders it into an **aria-live** region so a screen-reader operator can hear what is on air — realising the NFR-021 MVP baseline for non-visual live driving.

## 14. Packaging & updates

Per-OS installers: Windows (MSI/NSIS, Authenticode-signed), macOS (notarised DMG/pkg), Linux (AppImage + deb/rpm + Flatpak). Signed update feed with signature verification of the full artifact and anti-rollback (min-version), keys off the distribution host (heed Sparkle CVE-2025-0509). Mobile controller via App Store / Play (with the FR-176 privacy policy + data-safety disclosures). CI builds and signs per platform (Stage 7).

## 15. Requirement coverage (MVP → components)

Every MVP epic maps to owning components; all **84** MVP FRs are covered.

| MVP epic (FRs) | Owning component(s) |
|---|---|
| A Service planning (FR-001..008) | Presentation service + Data layer + Autosave |
| B Slides & editing (FR-009..017) | Presentation service + Tauri UI + Engine |
| C Songs & lyrics (FR-019/020/021/024) | Presentation service + Data layer |
| D Scripture MVP (FR-025..029/031/035) | Scripture service + Engine |
| E Outputs MVP (FR-036/037/040/041/046) | Output manager + Engine |
| F Lower thirds (FR-049) | Engine + Output manager |
| G Timers/TIME UP (FR-054..062/065) | Timer service + Engine |
| H Media MVP (FR-066/067/068/070/073) | Media engine |
| I Recovery MVP (FR-074..079/083/084) | Autosave/recovery + Data layer |
| J Mobile MVP (FR-085..094/097/098) | LAN control server + Security + Mobile app |
| O Import/export MVP (FR-138/139) | Data layer + Security |
| P Admin MVP (FR-147/148/150/151/155) | Security/secrets + Data layer |
| Q Audit-discharge MVP (FR-160/161/162/169/173/174/175/176) | Engine + Media + Security + Autosave + UI |
| Cross-cutting NFRs | All components per §1 principles |

## 16. Risk → mitigation

| Risk | Mitigation | Owner |
|---|---|---|
| Zero-copy HW-decode→GPU (S2) fails on an OS | Fallback: glvideomixer / accept 1080p30 / fewer outputs (ADR-0006; RISK-013/014) | Architect |
| Multi-monitor fullscreen robustness (S4) | Borderless-per-monitor + manual placement fallback | Architect |
| WebView↔engine preview fidelity (S5) | Downscaled texture-stream preview; Rust-native UI as fallback | Architect |
| iOS background mDNS (S9) | QR-only pairing fallback; foreground-discovery | Mobile |
| Real-room AI accuracy (S8/S11) | Operator-confirmation default; provisional thresholds; eval sets (FR-171) | AI |
| 12h soak stability | Bounded caches/queues; soak harness (Stage 12) | Architect + QA |

## 17. Escalated open decisions (for the gate)

- **ADR-0003 (UI shell)** and **ADR-0009 (mobile framework)** are Medium-confidence — recorded with fallbacks and validating spikes; flagged for your awareness.
- **NDI (ADR-0013)** and **licensed-translation APIs** carry licensing obligations gating those (later) features — legal confirmation tracked (OD-06/08).
- Performance NFRs and AI thresholds remain provisional pending spikes/measurement (as in the PRD).

Full ADRs: `docs/architecture/adr/`. UX: `docs/design/`. Independent review: `docs/architecture/ARCH-UX-REVIEW-stage5.md`.
