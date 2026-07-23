# SelahCue — Product Research Plan (Stage 2 input)

Date: 2026-07-23 · Owner: Product Manager + Product Researcher · Status: Ready for Stage 2

This plan enumerates the research required before the PRD. Every finding must be classified **OBSERVED / DOCUMENTED / INFERRED / UNKNOWN** with evidence (URL, date, access limits, confidence). No proprietary code/assets/branding/interfaces are copied. Primary research tools: WebSearch, WebFetch, and any available browser MCP (Chrome MCP if present — see RISK-007).

## RQ areas, methods, and outputs

| ID | Research question | Method | Primary output | Owner |
|---|---|---|---|---|
| RP-01 | Reference-product workflows: PewBeam, ProPresenter, OpenLP, FreeShow, EasyWorship, Quelea — service planning, slides, lyrics import, scripture search/present, stage displays, multi-output, lower thirds, timers, templates, permissions, recovery | Public docs, demos, videos, trials where authorised | Competitor workflow matrix + capability comparison | Product Researcher |
| RP-02 | Adjacent production tooling: OBS, vMix, ATEM Software Control, Bitfocus Companion, NDI tools, Stream Deck — output routing, browser source, control surfaces, integrations | Docs + videos | Integration & output-model findings | Product Researcher |
| RP-03 | Transcription platforms & tech: Otter, Descript, Whisper/whisper.cpp/faster-whisper, cloud STT (streaming) — accuracy, latency, CPU/GPU/mem, offline, languages, streaming, cost, licensing | Docs, benchmarks, model cards | Transcription provider trade-off table | Product Researcher + AI |
| RP-04 | Automatic scripture detection feasibility: deterministic spoken-reference parsing, exact/fuzzy quote matching, semantic retrieval, confidence, false-positive/negative rates, accent & noisy-room limits | Literature, embeddings/vector-search options, prototyping notes | Realistic-capability assessment + documented limitations | AI Engineer |
| RP-05 | AI sermon-note generation: local vs cloud LLMs, provider abstraction, cost, data-retention/consent, latency, quality expectations | Provider docs, model cards | AI-provider abstraction requirements + realistic expectations | AI Engineer |
| RP-06 | Text-to-speech: local (OS/platform) vs cloud voices, quality, latency, cost, offline, per-platform voice availability, pronunciation dictionaries, audio routing | Platform/provider docs | TTS trade-off + MVP-vs-later recommendation + routing/feedback-safety notes | AI + Product |
| RP-07 | Scripture licensing: which translations are public-domain (KJV, WEB, etc.) vs licensed (NIV, ESV, NLT…); import formats; attribution/copyright metadata requirements | Publisher/licensing sites, existing open-Bible data projects | Licensing register — bundlable vs user-supplied vs API | Product + Security |
| RP-08 | Cross-platform + offline constraints: desktop frameworks (Tauri/Electron/native/Rust), rendering (wgpu/native/GPU), media (GStreamer/libmpv/platform), multi-window multi-display output, mobile controller stacks, local-network discovery/pairing | Framework docs, feasibility spikes | Feasibility findings feeding Stage 5 ADRs | Software Architect |
| RP-09 | Performance/reliability targets: realistic startup, idle/presentation/model/cache memory, slide-trigger latency, 1080p60, multi-output, transcription/detection/mobile/TTS latency, soak stability | Benchmarks + comparable-product behaviour | Proposed measurable targets | Architect + QA |
| RP-10 | Security & privacy: local-network API security, device pairing/auth, replay protection, rate limiting, secret storage per platform, transcript/audio/note privacy, cloud disclosure, update security | Standards, platform keychains, threat-modelling refs | Early threat model + privacy requirements | Security Reviewer |
| RP-11 | Licensing/compliance beyond scripture: fonts, icons, media codecs (H.264/HEVC/AAC), STT/TTS models, NDI SDK terms, song lyrics (CCLI), app-store distribution, OSS dependency licenses, data protection (GDPR/NDPR) | License texts, store policies | Compliance register | Security + Product |
| RP-12 | Users & jobs-to-be-done: media operator, scripture operator, worship leader, pastor, stage manager, livestream director, sound engineer, service coordinator, sysadmin, mobile user, post-service editor — responsibilities, permissions, pain points, workflows, failure/recovery scenarios | Synthesise from RP-01/02 + domain reasoning | Personas, roles, permission matrix, normal/alternate/failure workflows | Business Analyst + UX |
| RP-13 | Market & positioning: pricing models, deployment (self-host/desktop), differentiation vs incumbents, unmet needs | Market pages, reviews | Positioning & differentiation notes | Product Manager |

## Classification & evidence discipline

- Record for each finding: statement, classification, source URL, access date, access/plan limitation, confidence (High/Med/Low).
- Where a reference product cannot be accessed (paywall/trial limits), mark UNKNOWN — do not infer proprietary internals.
- Capability claims about AI/transcription/detection/TTS must be evidence-backed and must **not** be described as perfectly accurate.

## Deliverables (Stage 2)

- `docs/research/EVIDENCE-REGISTER.md` — all findings, classified, with evidence.
- `docs/research/COMPETITOR-MATRIX.md` — capability comparison.
- `docs/research/PROVIDER-TRADEOFFS.md` — transcription/AI/TTS options.
- `docs/research/LICENSING-REGISTER.md` — translations, voices, models, codecs, fonts, lyrics.
- `docs/business/PERSONAS.md` + permission matrix + workflow inventory.
- `docs/security/threat-model-draft.md` — early threat model.
- `docs/research/OPEN-DECISIONS.md` — unresolved product decisions for the user.
- Independent review of the discovery report before the Stage 2 gate.

## Exit criteria (Stage 2 gate)

Research evidence register complete; required workflow research complete; findings classified correctly; material unknowns documented; discovery report passes independent review.
