# SelahCue PRD v1.0 — Stage-3 Pre-Audit Consolidated Review

**Document reviewed:** `docs/product/prds/SelahCue-PRD.md` (v1.0)
**Review stage:** Stage 3 — pre-audit synthesis. This is **not** the formal independent audit; the formal audit is **Stage 4**.
**Role:** Lead independent reviewer, synthesizing four lens reviews (Testability & Completeness; MVP Coherence & Scope; Security/Privacy/Licensing; Reliability/Performance/Accessibility/AI-realism/Traceability).
**Date:** 2026-07-23

---

## Consolidated verdict: PASS WITH CONDITIONS

All four lenses returned **PASS WITH CONDITIONS**. No lens raised a blocker. Every open finding is a *major* or *minor* that is either fixable now (thresholds, annotations, citation fixes, definitions) or explicitly carryable with a recorded deferral. Under the decision rule (FAIL only if a blocker stands; PASS WITH CONDITIONS if only majors/minors that can be fixed now or carried; PASS if only minors/none), the consolidated result is **PASS WITH CONDITIONS**.

- **Blockers:** 0
- **Majors (de-duplicated):** 10
- **Minors (de-duplicated):** 12

The PRD is structurally complete, traceable, and honest about its unknowns. The conditions below are concentrated in three themes: (1) close the remaining brief-mandated coverage gaps or record them as deferrals, (2) make a handful of acceptance criteria and NFRs actually testable (numeric thresholds, reference-hardware tiers, spike-gate parity), and (3) reconcile MVP scope framing and media/codec sequencing with what the MVP FR set actually commits.

### Per-lens verdicts

| Lens | Verdict | Majors | Minors |
|---|---|---|---|
| Testability & completeness (PRD vs brief & discovery) | PASS WITH CONDITIONS | 3 | 6 |
| MVP coherence & scope | PASS WITH CONDITIONS | 2 | 4 |
| Security, privacy & licensing | PASS WITH CONDITIONS | 1 | 0 |
| Reliability, performance, accessibility, AI-realism, traceability | PASS WITH CONDITIONS | 4 | 4 |

De-duplication note: two findings recurred across lenses — audio-device-loss recovery (raised minor by Lens 1, major by Lens 4 → consolidated as **major**) and accessibility contrast measurability (raised minor by Lens 1, folded into Lens 4's broader accessibility major → consolidated as **major**). All spot-checked claims were independently verified against the PRD (see Reviewer independence).

---

## Consolidated blockers

**None.** No finding, at any lens, rises to blocker severity. Nothing in the PRD is unfixable-in-place or forces a re-baseline; the reliability/output-isolation spine, traceability, and phasing are sound.

---

## Majors (with recommendations)

Ten distinct majors after de-duplication. Each is tagged with the lens(es) that raised it.

### MAJ-1 — GPU/renderer + decoder device-loss recovery is uncovered
*(Lens 1)* The brief lists "GPU or decoder failure" as a reliability requirement, but no FR addresses GPU device-loss/reset (e.g. Windows TDR) recovery, and NFR-024's isolation list (line 364) enumerates only AI/media/network/display/mobile — GPU/renderer is absent and decoder failure is only implicitly folded into "media failure." For the leaning wgpu-compositor path (RISK-012), a device-loss blanks **every** output at once, directly threatening G-1 and METRIC-001 (zero unintended blanks).
**Recommendation:** Add an EPIC-I FR requiring detection of and recovery from GPU device-loss/reset and decoder failure without blanking live output (re-init compositor / software or last-good-frame fallback), and extend NFR-024's failure list to include GPU/renderer and decoder failure.

### MAJ-2 — Audio-output-device-loss recovery is asserted but undefined; a launch gate points at behaviour no FR specifies
*(Lens 4 major + Lens 1 minor)* FR-068 (line 202) specifies only audio-device **selection** ("Audio plays to a chosen device; never forced onto the transcription-capture path") — no failover, no reconnect-restore. Yet §23 (line 401) claims audio disconnection is "handled gracefully (FR-041/068/097/135)" and §32 makes "audio-loss recovery tests pass" an MVP launch gate. There is no audio analogue to FR-041 (display reconnect restores content), and NFR-024 omits audio-device failure. A launch gate therefore points at a behaviour no requirement defines.
**Recommendation:** Add an MVP FR mirroring FR-041: on audio-device disappearance, fail over or mute-safely without crashing or blanking video; on reconnect, restore routing; surface loss in the pre-service checklist (FR-008) and output-health view. Add "audio-device" to NFR-024 and trace it into the §32 gate.

### MAJ-3 — AI safety/accuracy acceptance criteria have no testable threshold
*(Lens 1)* Three ACs guarding AI safety cannot be pass/failed as written: METRIC-009 target is "≤ agreed ceiling (set from Stage-4/10 measurement)" (line 466) — no number; FR-121 inherits it ("below an agreed ceiling", line 275); FR-102 — the mandatory VAD hallucination gate the discovery report calls a first-order worship-room risk — requires "hallucination-on-silence rate near zero" (line 251), which is subjective.
**Recommendation:** Set at least a provisional numeric ceiling for METRIC-009/FR-121 (revisable after Stage-10) and replace FR-102's "near zero" with a concrete cap (e.g. ≤N false segments per hour of silence/music on the defined test set). Measure-then-ratify is fine, but an interim number is needed for the AC to be verifiable at requirement freeze.

### MAJ-4 — Transcription language / accent selection has zero FR coverage
*(Lens 1)* The brief lists "Language selection" and "Accent and dialect considerations" under live transcription, and the product positions for multilingual congregations (Yoruba/Hausa/Igbo/French/Spanish per FR-017/NG-6). No FR in EPIC-K (FR-099–110) or the provider framework (EPIC-N) provides transcription-language selection; FR-017 covers only on-screen text rendering, not choosing the spoken language to transcribe.
**Recommendation:** Add an R3 FR for selecting/auto-detecting transcription language (and accent/model variant) with a testable AC (selected language persists and constrains recognition; auto-detect fallback defined), or record an explicit deferral in §28/§31.

### MAJ-5 — MVP "thin controller" framing contradicts the MVP content (two hardened subsystems)
*(Lens 2)* AS-1/OD-01 and RISK-001 characterise the MVP as a "thin mobile controller" + "realistically bounded" foundation, but the MVP is ~75 FRs across five platforms and packs two hard subsystems into one release: a from-scratch GPU-composited presentation engine (editor, layered compositing, scripture parser+search+pagination, timer engine, GStreamer media, crash-recoverable live state) **and** a production-grade secured mobile control plane (EPIC-J: mDNS discovery, QR pairing + host confirmation, TLS 1.3 pinned cert, per-device keypair-bound revocable tokens, seven-role server-side RBAC, replay protection, rate limiting). §30 itself calls this "full LAN security + RBAC" — a direct internal contradiction of the "thin" label.
**Recommendation:** Reconcile framing with content — either drop "thin" and state the MVP delivers two hardened subsystems (adjusting timeline/risk expectations), or reduce the MVP mobile-security surface to a genuine thin controller (e.g. defer per-device keypair revocation FR-089 and full seven-role RBAC to a mobile-hardening slice; keep pairing+TLS+basic roles), and/or honour OD-01(b) by staging desktop-first with the controller as a true fast-follow.

### MAJ-6 — MVP media/render quality and memory bounds are deferred to R2, but the MVP ships live render + video and a 12h-soak commitment
*(Lens 2)* MVP includes a live audience output (FR-036) and H.264/HEVC playback (FR-067), yet the only render-quality NFR (NFR-005 sustained 60fps/<5% dropped/1 output) is R2 (line 345) and the media-cache bound (FR-071 / NFR-013 ≤1GB) is R2. FR-067's AC only requires play/pause/seek to "work"; FR-084's generic "no unbounded growth" does not supply the media-specific ceiling that governs soak behaviour. Meanwhile MVP commits to 12h memory stability with <5% growth (NFR-010/METRIC-003) — silently dependent on an R2 bound.
**Recommendation:** Promote a minimal MVP render-quality bar (fps/frame-health AC) and an MVP media-memory bound for the single main output; OR explicitly scope MVP media to still-images + best-effort video with **no** fps/soak guarantee until R2, so METRIC-003 is not dependent on a deferred requirement.

### MAJ-7 — Codec safe-harbor: platform-only decode (FR-073) lands a release after MVP H.264/HEVC playback (FR-067)
*(Lens 3)* MVP ships H.264/HEVC via FR-067 (line 201), but FR-073, which constrains decode to platform/HW elements (no gst-libav for encumbered codecs), is R2 (line 207). The MVP would therefore play encumbered codecs before the requirement that keeps that path inside the licensing safe harbor is in force. Note FR-073 is the carrier of deferred Stage-2 condition **C8** (line 436), so this also affects a condition disposition.
**Recommendation:** Promote FR-073 to MVP so the platform-only-decode constraint is in force wherever FR-067's MVP playback ships; reflect the C8 carry accordingly.

### MAJ-8 — Spike-gating is inconsistent: NFR-005 (and NFR-007/012) read as committed while prose says they are gated
*(Lens 4)* §24 states "Multi-output + 1080p60 targets are spike-gated (S1/S2, OD-23)" and §27 (line 431) states spikes S1–S10 gate committing NFR-005/006 — but only NFR-006 carries the "(spike-gated)" marker in the §14 table; NFR-005 (line 345) does not. Given RISK-012/013 flag the render path as unproven, single-output 1080p60 is genuinely unproven yet reads as a committed R2 target. NFR-007 (transcription latency ≤2s) and NFR-012 (model resident memory) have the same gap versus RISK-004 / spike S8.
**Recommendation:** Annotate NFR-005 (S1/S2, OD-23) and NFR-007/012 (S8) as spike-gated in the §14 table, for parity with NFR-006 and consistency with §24/§27.

### MAJ-9 — Performance NFRs are untestable: "reference hardware" / "per-tier" is never defined
*(Lens 4)* NFR-001 (line 341) states "Cold start ≤3s; warm ≤1s on reference hardware"; AS-2 (line 63) says targets are "per-tier (§26)" — but §26 enumerates no hardware tiers or reference-machine specs, and the memory/CPU NFRs (NFR-002/003/010/011) inherit the ambiguity. "On reference hardware" is not a measurable pass condition without tier definitions, contradicting the §29 measurability convention.
**Recommendation:** Define reference-hardware tiers with concrete specs in §26 (min CPU-only, modest GPU, Apple Silicon), bind them to the RP-09 benchmark harness, and state which tier each performance NFR target applies to.

### MAJ-10 — Accessibility: no measurable contrast target, MVP ships with no screen-reader support, mobile a11y is entirely absent
*(Lens 4 major, subsuming Lens 1 minor on contrast)* (1) NFR-020 (line 360) requires "high-contrast configuration" with no ratio and scopes only stage/confidence **output** legibility, not the operator control surface — "readable/high-contrast" is subjective and untestable. (2) Screen-reader support (NFR-021) is R2 and desktop-only, so MVP ships with no SR accessibility. (3) The mobile controller is MVP (EPIC-J) yet no requirement addresses mobile a11y (VoiceOver/TalkBack, dynamic type, touch-target size). No WCAG reference, focus-indicator, or reduced-motion requirement exists anywhere.
**Recommendation:** Add a cited WCAG AA contrast ratio (e.g. 4.5:1 / 3:1, or a stated higher stage-lighting ratio) covering both operator UI and stage output plus a minimum configurable text size; make an explicit, justified decision on MVP screen-reader scope (at minimum accessible names/roles for core live controls in MVP); and add a mobile-controller accessibility requirement since mobile control is MVP.

---

## Minors

Twelve distinct minors after de-duplication. All are carryable; several are near-zero-cost fixes worth batching now.

1. **Per-output frame-rate config missing** *(Lens 1)* — brief lists frame rate as a per-output parameter; FR-038/FR-044 omit it (NFR-005/006 are global). Add to FR-038's configurable list or note frame rate as deliberately global.
2. **Mobile-control coverage gaps** *(Lens 1)* — brief-listed mobile lower-third control, read-only transcript viewing, and sermon-note status have no FR (FR-092–098 don't cover them). Add R2+/R5 FRs or record deferrals.
3. **Sermon-note content-type gaps** *(Lens 1)* — FR-122's AC omits three brief-requested sections: announcements mentioned, referenced people/books/topics, closing prayer/conclusion. Add to FR-122/FR-126.
4. **Manual fuzzy/semantic scripture search scope** *(Lens 1)* — brief lists operator-initiated fuzzy + semantic search; only FR-113 (R4 live auto-detect) covers fuzzy/semantic, and FR-028 is exact-only. Clarify scope or add an FR.
5. **Desktop stage-message authoring path** *(Lens 2)* — FR-037 (MVP confidence display) lists stage messages, but the only stage-message authoring FR is FR-096 (mobile, R2). Add an MVP desktop stage-message FR or expand FR-037's AC.
6. **Traceability citation defects** *(Lens 2)* — FR-061 traces to FR-100 (R3) but its real MVP dependency is FR-094 (mobile timer/TIME UP, which back-references FR-061); FR-064 traces to non-existent FR-160 (set ends at FR-159), likely FR-144 (macros) or FR-150 (audit log). Verified against lines 190/193/238. Citation errors, not real ordering errors — but audit-visible. Fix both.
7. **Seven-role RBAC with dormant roles** *(Lens 2)* — FR-090 enforces all seven mobile roles in MVP, but Scripture Operator's defining capability is R4 (FR-095) and Worship Leader's stage-message half is R2 (FR-096). Annotate dormant capabilities in §16/§30 or scope MVP enforcement to roles with MVP capability.
8. **Composite MVP FRs mask effort** *(Lens 2)* — FR-009 (layered slide editor) and FR-010 (templates/themes engine) are whole subsystems under one ID. Flag for Stage-6 decomposition so estimates reflect true size.
9. **Verbatim-ASR audience projection default not a requirement** *(Lens 4)* — CAPABILITY-ASSESSMENT §1.6 makes verbatim on-screen display OFF-by-default / advanced opt-in, but no FR captures this guardrail for the most publicly-damaging ASR failure mode. Add an R3 FR (verbatim audience projection disabled by default, advanced opt-in with hallucination-risk disclosure).
10. **Deferred-condition carry completeness** *(Lens 4)* — §28 carries C2/C8/C9/C10/C14, but the C11 (m1–m4) and C12 backlog portions per CONDITION-DISPOSITIONS are not explicitly carried or discharged. Add a one-line §28 note mapping them to discharging requirements (reliability→EPIC-I, outputs→EPIC-E, accessibility→NFR-019/020/021) or to the Stage-3 backlog.
11. **Timer restoration semantics ambiguous** *(Lens 4)* — FR-075 restores "running timers" but does not state whether a running countdown is wall-clock-corrected for downtime or resume-from-checkpoint, making the recovery test non-deterministic. Specify in FR-075/METRIC-008 and add a forced-shutdown-mid-countdown case.
12. *(Minor already elevated)* — audio-device-disconnection (Lens 1's FR-068 minor) and accessibility contrast (Lens 1's NFR-020 minor) are consolidated into MAJ-2 and MAJ-10 respectively; listed here only for traceability.

---

## Conditions (for clearing at/before Stage-4 formal audit)

Fix-now items are low-cost edits; carry items require an explicit recorded decision if not fixed.

- **C-1 (MAJ-1, fix-now):** Add GPU/renderer device-loss/reset + decoder-failure recovery FR under EPIC-I and extend NFR-024's failure list to include GPU/renderer and decoder failure.
- **C-2 (MAJ-2, fix-now):** Add an MVP audio-output-device loss/reconnect FR mirroring FR-041; add audio-device to NFR-024; align the §32 launch gate to a defined requirement.
- **C-3 (MAJ-3, fix-now):** Set interim numeric thresholds — a provisional METRIC-009/FR-121 ceiling and a concrete FR-102 cap replacing "near zero" — revisable after Stage-10.
- **C-4 (MAJ-5, decide/carry):** Reconcile the MVP "thin controller" framing with its two-hardened-subsystem content, or reduce the MVP mobile-security surface; update RISK-001/AS-1/OD-01 and timeline/risk expectations.
- **C-5 (MAJ-6, decide/fix):** Commit an MVP render-quality bar + media-memory bound for the single main output, or explicitly scope MVP video as best-effort with no fps/soak guarantee until R2 — so METRIC-003 is not silently dependent on R2.
- **C-6 (MAJ-7, fix-now):** Promote FR-073 (platform-only decode) to MVP alongside FR-067; reflect the C8 condition carry.
- **C-7 (MAJ-8, fix-now):** Annotate NFR-005 (S1/S2, OD-23) and NFR-007/012 (S8) as spike-gated in the §14 table.
- **C-8 (MAJ-9, fix-now):** Define reference-hardware tiers with concrete specs in §26, bound to RP-09, and state which tier each performance NFR applies to.
- **C-9 (MAJ-10, fix-now + decide):** Add a cited WCAG AA contrast ratio and minimum text size for operator UI and stage output; make an explicit MVP screen-reader-scope decision; add a mobile-controller accessibility requirement.
- **C-10 (MAJ-4 + coverage minors, fix-or-carry):** Add transcription language/accent-selection FR (or deferral); resolve the coverage minors (per-output frame-rate, mobile lower-third/transcript/sermon-note-status, sermon-note content types, manual fuzzy/semantic scripture search, desktop stage-message authoring, verbatim-ASR opt-in default) by adding FRs or recording explicit §28/§31 deferrals.
- **C-11 (traceability minors, fix-now):** Correct the two citation typos (FR-061→FR-094; FR-064→FR-144 or FR-150) and add the §28 note mapping the C11/C12 deferred-condition backlog to discharging requirements.

None of these conditions requires re-baselining; all can be discharged as PRD edits or recorded decisions before the Stage-4 audit.

---

## Strengths (synthesized, de-duplicated)

- **Complete, clean traceability.** Two lenses independently (one programmatically) verified all 159 FRs map 1:1 to exactly one release, with bucket counts summing exactly (MVP 75 + R2 28 + R3 25 + R4 15 + R5 9 + R6 7 = 159) — no missing, extra, or double-mapped requirement; §13 per-row priorities equal the §33 lists and the §30/§31 prose.
- **Full brief coverage.** All 32 brief-mandated PRD outputs are present as discrete sections; the overwhelming majority of FR/NFR ACs are genuinely measurable (concrete numbers, explicit state transitions, observable behaviour) per the §29 convention.
- **TTS handled correctly as a non-goal everywhere** (NG-1, §12, §18, §22, RISK-008 retired, §30, OD-02/DEC-001) with no residual TTS FR anywhere — the correct way to close a mandated-but-descoped area with retained evidence.
- **Exemplary, fully-traced AI-realism.** Operator-in-the-loop defaults (FR-115/119/083), explicit no-perfect-accuracy stance (FR-120), fabrication disclosure + mandatory local-Bible verification of extracted refs (FR-123/125/128 ← C6), auto-display corroboration gate with semantic-only permanently barred (FR-116 ← C7), VAD hallucination gating (FR-102), and non-authoritative diarization labels (FR-109) — all traced to the candid CAPABILITY-ASSESSMENT.
- **Strong output-isolation spine.** NFR-024 + FR-083 + METRIC-001 (zero unintended blanks) + recovery flows FLOW-008/009/010 with METRIC-008 (100% forced-shutdown restore) and METRIC-005 (≤5s work loss) — the reliability core is self-contained and does not depend on any R3+ AI/provider capability.
- **Correct phasing with no true ordering errors.** Every MVP feature is buildable from MVP-only capabilities; the typed reference parser (FR-027, MVP) is cleanly extended by R4 spoken detection (FR-111/112) with no reverse dependency; §11 FLOW priorities are consistent with their underlying FRs.
- **LAN control-plane threats map to testable MVP FRs** (FR-086–091), and deferred Stage-2 conditions C2/C8/C9/C10/C14 are carried into the PRD as concrete requirements.
- **Honest spike-gating posture stated up front** (§14 header, §24, §27 S1–S10, RISK-012/013) — the render/multi-output targets are framed as Stage-5-ratified and fallback-gated rather than committed; the NFR-005/007/012 table-marking slips (MAJ-8) are the exception, not the rule.

---

## Reviewer independence statement

This synthesis was produced by a lead reviewer independent of the PRD's authors. The four underlying lens reviews were conducted by non-author reviewers. To avoid rubber-stamping the lens summaries, the load-bearing claims were **independently verified against the source PRD** (`docs/product/prds/SelahCue-PRD.md`), not merely aggregated:

- FR-061 → "FR-100" citation and its real MVP dependency FR-094 (lines 190, 238) — confirmed citation typo.
- FR-064 → non-existent "FR-160" (line 193; requirement set ends at FR-159) — confirmed.
- FR-067 MVP H.264/HEVC (line 201) vs FR-073 platform-only decode at R2 (line 207) and its C8 carry (line 436) — confirmed sequencing gap.
- FR-068 selection-only AC (line 202) vs the §23/§32 audio-recovery claims (line 401) — confirmed undefined-behaviour gate.
- NFR-005 R2 with no spike-gate marker (line 345) vs §27 gating prose (line 431) — confirmed inconsistency.
- NFR-024 failure list omitting GPU and audio-device (line 364) — confirmed.
- METRIC-009 / FR-121 / FR-102 undefined thresholds (lines 466/275/251) — confirmed.
- "Reference hardware" / "per-tier" without §26 tier definitions (lines 341/63) — confirmed.

The consolidated verdict, severity assignments, and de-duplication decisions are the lead reviewer's own and were not influenced by the PRD authors. This is a Stage-3 pre-audit product; it does not substitute for, and is subordinate to, the **Stage-4 formal independent audit**.
