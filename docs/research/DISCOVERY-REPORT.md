# SelahCue — Product Discovery Report (Stage 2)

Date: 2026-07-23 · Owner: Product Manager · Status: For Stage 2 independent review + gate

Synthesis of Stage 2 research into product-shaping conclusions. Evidence lives in [EVIDENCE-REGISTER.md](EVIDENCE-REGISTER.md) and the linked artifacts; open decisions in [OPEN-DECISIONS.md](OPEN-DECISIONS.md). This report does **not** create requirement IDs or tickets (Stage 3/6).

## 1. Problem & opportunity

Churches run live services on presentation software that forces a trade-off: **power** (ProPresenter — deep, pro AV, but Mac-first, ~$399/seat, steep learning curve, no Linux) vs **accessibility** (OpenLP/FreeShow/Quelea — free, cross-platform incl. Linux, but utilitarian and light on pro AV routing/roles) vs **ease** (EasyWorship — volunteer-friendly, subscription, no Linux). A new AI-native entrant (PewBeam) proves demand for live sermon-follow scripture, semantic search, and AI slides, but appears verse-projection-centric rather than a full production suite.

**Opportunity for SelahCue:** a genuinely cross-platform (Win/macOS/Linux) presentation suite with real mobile operation, volunteer-first UX with opt-in pro depth, first-class ecosystem interop (NDI/alpha, transparent browser-source, Bitfocus Companion/Stream Deck), native role-based collaboration, and **responsible, operator-in-the-loop AI** (auto-cue scripture, transcription, sermon notes) inside a complete production suite — with offline-first reliability as an explicit guarantee.

## 2. Users (11 personas, 7 mobile roles)

Discovery modelled 11 personas — Church Media Operator, Scripture Operator, Worship Leader, Pastor/Preacher, Stage Manager, Livestream Director, Sound Engineer, Service Coordinator, System Administrator, Mobile Remote User, Post-Service Media/Sermon Editor — split across desktop (authoring/operating) and mobile (roaming control). Seven scoped mobile control roles (Observer → Administrator) map to 15 capabilities in a permission matrix ([PERSONAS.md](../business/PERSONAS.md)). 24 workflows are documented ([WORKFLOWS.md](../business/WORKFLOWS.md)) across normal, alternate, and failure-recovery paths.

**Design invariant (non-negotiable, evidence-driven):** the desktop is authoritative; core presentation (slides, local scripture, media, blackout, timers) must remain fully operable with **zero** network, mobile, or AI dependency; no component failure may blank or clear the live output as a side effect; mobile actions are validated per-action by the desktop and stale actions are rejected, not queued.

## 3. What the AI can and cannot realistically do (candid)

This is where a church-AI product most often overpromises. Discovery is deliberately honest ([CAPABILITY-ASSESSMENT.md](CAPABILITY-ASSESSMENT.md)):

- **Live transcription:** works for reasonably clear, close-mic, single-speaker preaching with 1-5s lag; **real-room WER is materially worse than benchmark** (reverb, PA bleed, accents, biblical vocabulary). Whisper **hallucinates coherent false text on silence/music** — a first-order worship-room risk. → VAD gating mandatory; raw transcript is **not** authoritative on-screen text (verbatim display OFF by default); hardware probe + model auto-select.
- **Automatic scripture detection:** **reliable for explicit spoken references, fallible for verbatim quotes, unreliable for paraphrase/allusion.** No credible end-to-end benchmark exists, so no single accuracy number is claimed. → **operator-confirmation default**, deterministic reference parser prioritised over semantic guesses, precision-over-recall, semantic-only matches never auto-fired; auto-display is an advanced opt-in gated to high-confidence explicit references only.
- **Sermon notes:** viable post-service (not latency-critical); local 7-8B model adequate for "tidy transcript → structured notes", cloud better for quality. Always human-gated, editable, labelled AI-generated, never overwriting the source transcript.
- **TTS:** lowest value + highest live-room risk (feedback, mic bleed, output routing) → **defer past MVP**.

**Product consequence:** AI ships as an **operator assist, not an autopilot**, keeping every AI error recoverable before it reaches the congregation.

## 4. Technology feasibility (non-binding; Stage 5 decides)

Discovery confirms the brief's Rust/wgpu/GStreamer/SQLite *components* are individually capable, with one important correction: **Tauri's WebView cannot be the output compositor** (documented WebView GPU limits) — it works for the operator-UI shell, but high-performance multi-output compositing must be **wgpu + native windowing**. The leaning architecture is a **Rust core** (wgpu compositor + GStreamer media→GPU textures + SQLite WAL + LAN control server) with the operator UI in Tauri-WebView or Rust-native (undecided). Nine make-or-break spikes (multi-output 1080p60, HW-decode→GPU zero-copy, transparent alpha output, winit multi-monitor, UI-shell choice, mDNS on church Wi-Fi, 12h soak, transcription/detection latency, mobile background discovery) are the gate to committing the stack in Stage 5. Proposed measurable performance targets are drafted ([FEASIBILITY.md](FEASIBILITY.md) §8) for Stage-5 ratification.

## 5. Hard constraints (licensing, privacy, security)

- **Licensing:** ship PD Bibles only (KJV ex-UK, WEB, ASV, YLT, BSB, BBE, Darby, Webster); licensed translations are API-only/user-supplied, never bundled; no bundled copyrighted lyrics; OS-native codecs + VP9/AV1+Opus for app-encoded media; NDI attribution obligations; NDPA(2023)+GDPR apply to sermon data ([LICENSING-REGISTER.md](LICENSING-REGISTER.md)).
- **Privacy:** cloud OFF by default, opt-in + visible disclosure + live "cloud active" indicator; no audio/transcript leaves the host without explicit action; configurable retention + reliable delete; API keys only in OS secret stores.
- **Security:** LAN control plane is the top attack surface — MVP must ship TLS 1.3 with QR-pinned host fingerprint, single-use short-TTL QR pairing + host confirmation, per-device revocable keypair-bound tokens, server-side RBAC, per-command replay protection, rate limiting with output-path isolation, and signed updates ([threat-model-draft.md](../security/reviews/threat-model-draft.md)).

## 6. Proposed MVP boundary (carried to Stage 3 PRD)

Grounded in RISK-001 (scope breadth) and the brief's phased plan. **Recommendation** (see OPEN-DECISIONS OD-01/02/03):

**MVP = Presentation foundation (desktop tri-platform + thin mobile controller):** service plans; slide creation/editing; song lyrics (user-supplied + PD hymns); scripture search & display (PD translations); templates/themes; preview & live; main output + stage/confidence display; lower thirds; timers + "TIME UP"; media playback (OS-native decode); emergency clear/blackout; autosave + crash recovery; basic mobile pairing + slide/timer control; pre-service checks + missing-media detection.

**Later releases (phased):** media/output expansion (multi-output, transparent lower thirds, NDI, livestream layouts, diagnostics) → transcription → scripture intelligence → sermon intelligence → production integrations (MIDI/OSC/Companion/Stream Deck) + hardening.

**Non-goal / removed from roadmap:** **TTS** — de-scoped by user decision [DEC-001](../decisions/DECISION-LOG.md) (2026-07-23); it was discovery's lowest-value/highest-live-room-risk feature. Retained as evidence only; not on the roadmap. Stage 11 accordingly becomes "Sermon intelligence" only.

**Explicitly deferred from MVP (but on roadmap):** cloud AI (OD-11), licensed-translation integration (OD-06), per-output permissions (OD-14), advanced macros (OD-17).

## 7. Top risks (register updated)

Reaffirms RISK-001 (scope), RISK-002 (translation licensing — mitigated by PD-only MVP), RISK-003 (detection accuracy — mitigated by operator-confirmation default), RISK-004 (offline transcription perf — spike S8), RISK-005 (live reliability — architecture invariant), RISK-010 (privacy — opt-in cloud), plus new: **Tauri-WebView-compositor tension** (mitigated by wgpu split) and **9 feasibility spikes** as the Stage-5 gate. Whisper hallucination-on-silence added as an explicit design risk.

## 8. Readiness

All RP-01…RP-13 research areas are covered and classified (RP-12 is un-validated domain modelling — no user interviews — and is labelled as such; RP-03's adjacent-product study was added post-review, condition C1); personas/permissions/workflows (incl. failure-recovery) documented as design intent; realistic AI limits stated without overpromising; material unknowns captured as product decisions (OPEN-DECISIONS) and engineering spikes (FEASIBILITY §10). This package does not yet contain requirement IDs, PRD sections, architecture decisions, or tickets — those are Stage 3+.

## 9. Independent review outcome & condition disposition

An independent, fresh-context review (four lenses: completeness, evidence/classification discipline, AI realism, licensing/privacy/security/feasibility gaps — none authored the research) returned **PASS WITH CONDITIONS**: **0 blockers**, 10 majors, 15 minors, all four lenses agreeing ([DISCOVERY-REVIEW.md](DISCOVERY-REVIEW.md)).

Disposition ([CONDITION-DISPOSITIONS.md](CONDITION-DISPOSITIONS.md)): the integrity/honesty conditions were **resolved at the gate** — OBSERVED taxonomy reconciled (C3); RP-12 limitation notes + INFERRED classification (C4); vendor perf figures re-tagged (C5); sermon-note LLM fabrication mode disclosed (C6); scripture auto-display wrong-verse risk + corroboration gate (C7); transcription graceful-degradation rescope (C13); diarization limit + UNKNOWNs section added (C11/C12 portions); adjacent-product workflow study commissioned (C1). The architecture/requirements-shaping conditions were **formally deferred with recorded recommendations** into Stage 3/5 — at-rest datastore encryption (C9→OD-21), text-shaping/RTL MVP scope + spike S10 (C2→OD-22), S1/S2 zero-copy fallback + perf-target gating (C10→OD-23), platform/HW-decode codec constraint (C8→OD-08a), and the remaining minor backlog items (C11/C12/C14). No condition was dropped; none was a blocker; the package's core conclusions are unchanged.

**Net:** the discovery package is honest, internally consistent after the corrections, and ready for the Stage 2 gate.
