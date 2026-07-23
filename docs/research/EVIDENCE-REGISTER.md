# SelahCue — Research Evidence Register (Stage 2)

Date: 2026-07-23 · Owner: Product Manager (synthesis) · Status: Complete for Stage 2 review

This register indexes all Stage 2 research, aggregates the OBSERVED/DOCUMENTED/INFERRED/UNKNOWN classification, and lists the most material findings. Full evidence + source URLs live in each linked artifact. Access date for all web research: **2026-07-23**. Research tools: WebSearch + WebFetch (Chrome MCP not available — RISK-007).

## 1. Source artifacts

| RP areas | Artifact | Author role | Findings (approx) |
|---|---|---|---|
| RP-01/02/13 | [COMPETITOR-MATRIX.md](COMPETITOR-MATRIX.md) | Product Researcher | ~63 |
| RP-03/05/06 | [PROVIDER-TRADEOFFS.md](PROVIDER-TRADEOFFS.md) | AI Engineer | ~45 |
| RP-03/04 | [CAPABILITY-ASSESSMENT.md](CAPABILITY-ASSESSMENT.md) | AI Engineer | (candid realism, overlaps above) |
| RP-07/11 | [LICENSING-REGISTER.md](LICENSING-REGISTER.md) | Security + PM | ~65 |
| RP-08/09 | [FEASIBILITY.md](FEASIBILITY.md) | Software Architect | ~42 |
| RP-10 | [../security/reviews/threat-model-draft.md](../security/reviews/threat-model-draft.md) | Security Reviewer | 20 threats + controls |
| RP-12 | [../business/PERSONAS.md](../business/PERSONAS.md), [../business/WORKFLOWS.md](../business/WORKFLOWS.md) | BA + UX | 11 personas, 7 roles×15 caps, 24 workflows |

### Taxonomy note (reconciled per DISCOVERY-REVIEW C3)

To keep one definition package-wide: **OBSERVED = first-hand empirical observation — we ran, measured, or directly saw the behaviour.** Reading a primary licence/terms text is **DOCUMENTED (primary source)**, not OBSERVED. The Licensing register originally tagged ~11 primary licence-text reads as "OBSERVED"; those are reclassified below as **DOCUMENTED (primary)**. Under the reconciled definition, **product-behaviour OBSERVED findings across the entire package = 0** — no trials purchased, no code executed, no in-house benchmarks run.

| Artifact | OBSERVED (empirical) | DOCUMENTED | INFERRED | UNKNOWN |
|---|---|---|---|---|
| Competitor matrix | 0 | ~41 | ~11 | ~11 |
| Provider trade-offs | 0 | ~22 | ~20 | 3 |
| Licensing register | 0 | ~41 (of which ~11 primary-source) | ~16 | ~8 |
| Feasibility | 0 | ~18 | ~15 | 9 (spikes) |
| Threat model | 0 | security standards cited | ~20 (all product-behaviour INFERRED, no code) | 14 deferred items |
| Personas/workflows (RP-12) | 0 | domain conventions | domain modelling (see §RP-12 note) | 6 open questions |

**Zero empirical-OBSERVED findings is expected and honest:** every "how well X performs" claim is DOCUMENTED (primary or secondary) or INFERRED, explicitly flagged as needing a spike/trial. This is the single most important caveat on the whole discovery package.

**RP-12 (personas/workflows) classification note (per DISCOVERY-REVIEW C4/M4):** PERSONAS.md and WORKFLOWS.md are **un-validated domain modelling** — no user interviews or field observation were conducted. Persona needs/pain points and workflow behaviours are **INFERRED** from domain knowledge + competitor research, not evidenced. Statements of intended product behaviour in WORKFLOWS.md are **design intent (must/should)**, not delivered guarantees. Limitation notes have been added to both files.

## 3. Material findings (high-impact, with classification)

### Competitive / market
- **DOCUMENTED/High:** No incumbent covers Win+macOS+**Linux** commercially; only OSS tools (OpenLP/FreeShow/Quelea) do. ProPresenter (~$399/seat) is Mac-first, no Linux; EasyWorship subscription, no Linux. → cross-platform incl. Linux is an open lane.
- **DOCUMENTED/High:** PewBeam is the AI-native disruptor (live sermon-follow scripture, semantic search, AI slides, offline, Global-South pricing) but appears verse-projection-centric; full production depth (multi-output, stage, timers, roles) UNKNOWN.
- **DOCUMENTED/High:** Ecosystem table-stakes = interop with OBS (browser source/NDI/websocket), NDI, ATEM (key/fill), Bitfocus Companion / Stream Deck.
- **DOCUMENTED/Med:** #1 recurring pain point = ProPresenter's learning curve → volunteer-first UX is a validated need. Migration importers (FreeShow) are a decisive switching lever.

### AI / transcription / detection / TTS (realism)
- **DOCUMENTED/High:** Whisper hallucinates coherent false text on silence/music/noise → **first-order risk** in a worship room; VAD gating mandatory, never display unverified text during instrumental/silent stretches.
- **DOCUMENTED/High:** FP16 large-v3 cannot reach real-time on CPU-only even at 16 threads → hardware probe + model auto-select + warning required.
- **INFERRED/Med:** Real-room WER is materially worse than benchmark (plausibly high-single-digit→high-teens %) due to reverb, PA bleed, accents, biblical vocabulary → raw transcript is not authoritative on-screen text.
- **DOCUMENTED+INFERRED:** Scripture detection is **reliable for explicit references, fallible for verbatim quotes, unreliable for paraphrase/allusion** (allusions share ~6% word forms) → operator-confirmation default, precision-over-recall, never auto-fire semantic-only.
- **INFERRED/High:** TTS carries live-room feedback/mic-bleed risk and lowest product value → **defer past MVP.**

### Licensing (hard constraints)
- **DOCUMENTED/High:** Bundlable Bibles (PD) = KJV (ex-UK), WEB, ASV, YLT, BSB/Berean (CC0), BBE, Darby, Webster. LEB/unfoldingWord bundlable only with attribution/share-alike.
- **DOCUMENTED/High:** NIV/ESV/NLT/NKJV/NASB/CSB/MSG/AMP must be **API-only or user-supplied — never bundled.** ESV API is non-commercial (≤500-verse cache) → paid app needs commercial Crossway licence.
- **DOCUMENTED/Med:** Codec patents (H.264/HEVC/AAC via Via LA/Access Advance) → use OS-native decoders, prefer VP9/AV1+Opus for app-encoded media; don't bundle own encoder without review.
- **DOCUMENTED (primary)/High:** NDI SDK royalty-free/bundlable but requires ndi.video attribution near every use, up-to-date runtime, and makes AAC/H.264/H.265 licensing the developer's responsibility. (NDI 6 also requires a License ID; only header files are MIT — carried to Stage 3, condition C14.)
- **DOCUMENTED/High:** Song lyrics (CCLI) belong to the church, not vendor → user-supplied/integration only + copyright-metadata + streaming-licence reminder. NDPA(2023)+GDPR apply to sermon audio/transcripts.

### Feasibility (architecture-shaping)
- **DOCUMENTED/Med:** Tauri idle ~30-40 MB vs Electron 200-300 MB, **but** WebView GPU compositing is limited (CPU-bound canvas, 60fps macOS cap) → WebView is fine as the operator-UI shell but **cannot be the output compositor**; that must be wgpu + native windowing.
- **INFERRED/High:** Realistic architecture = **Rust core** (wgpu compositor + GStreamer media→GPU textures + SQLite WAL + LAN control server) with operator UI in Tauri-WebView **or** Rust-native (undecided → ADR).
- **DOCUMENTED/High:** GStreamer uniquely documents alpha-video handling needed for transparent lower thirds; SQLite WAL is a strong fit (with checkpoint-safe backups).
- **UNKNOWN (9 spikes S1-S9):** multi-output 1080p60, HW-decode→GPU zero-copy interop, transparent alpha output, winit multi-monitor robustness, UI-shell choice, mDNS on church Wi-Fi, 12h soak, transcription/detection latency, mobile background LAN discovery. These are make-or-break and belong to Stage 5.

### Security / privacy
- **INFERRED (all, no code)/Critical-High:** LAN control plane is the top attack surface (rogue-device spoofing, MITM command injection, replay, DoS). MVP controls: TLS 1.3 with QR-pinned host fingerprint, single-use short-TTL QR pairing + host confirmation, per-device revocable keypair-bound tokens, server-side RBAC, per-command nonce+timestamp, rate limiting with output isolation.
- **Critical:** API keys only in OS secret stores; cloud OFF by default, opt-in + visible disclosure + live "cloud active" indicator; no transcript/audio leaves host without explicit action; signed updates (heed Sparkle CVE-2025-0509).

### Users / workflows
- **11 personas** across desktop/mobile; **7 mobile roles × 15 capabilities** matrix (Observer→Administrator); **24 workflows** (8 normal, 9 alternate, 7 failure-recovery).
- **Core invariant (design-shaping):** desktop authoritative; core presentation (slides, local scripture, media, blackout, timers) survives with zero network/mobile/AI; no component failure ever blanks/clears output as a side effect; mobile actions validated per-action, stale actions rejected not queued.

## 4. Register status

All RP-01…RP-13 areas were researched, with two scope notes from the independent review ([DISCOVERY-REVIEW.md](DISCOVERY-REVIEW.md)): RP-03's adjacent-**product** workflow study (Otter/Descript/church captioning) was added post-review ([ADJACENT-TRANSCRIPTION-PRODUCTS.md](ADJACENT-TRANSCRIPTION-PRODUCTS.md), condition C1), and RP-12 is un-validated domain modelling (no user interviews — see §2 RP-12 note, condition C4). Material unknowns are captured in [OPEN-DECISIONS.md](OPEN-DECISIONS.md) (product decisions) and FEASIBILITY.md §10 (engineering spikes for Stage 5). Evidence quality is strong on documented facts and honest about the absence of hands-on/measured (empirical-OBSERVED) evidence. Condition dispositions: [CONDITION-DISPOSITIONS.md](CONDITION-DISPOSITIONS.md).
