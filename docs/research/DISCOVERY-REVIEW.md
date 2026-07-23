# SelahCue — Stage 2 Discovery Gate Review (Consolidated)

**Document type:** Lead independent reviewer synthesis
**Stage:** 2 (Discovery) → gate to Stage 3 (Requirements / PRD)
**Date:** 2026-07-23
**Reviewer role:** Lead independent reviewer, synthesizing four lens reviews

---

## 1. Verdict

> ## PASS WITH CONDITIONS

No blocker findings stand. The discovery package is admissible to the Stage 2 gate: it is unusually honest about the absence of hands-on/measured evidence, it makes the correct load-bearing architecture call (Tauri WebView cannot be the compositor), and it is conservative and safe in its recommended AI default modes for live services. However, **10 major findings** and **15 minor findings** must be carried forward as explicit, tracked conditions into Stage 3. Several majors are cross-document *consistency* and *disclosure* gaps (not new research), but two majors — the un-delivered adjacent-product study (RP-03) and the missing text-shaping/RTL feasibility work — represent scope that was planned or mandated and not delivered, and must be closed or formally deferred before Stage 3 locks the corresponding requirements.

All four lenses independently returned **PASS WITH CONDITIONS**. There is no dissent among the lenses and no finding rises to blocker severity.

**Aggregate finding counts (after de-duplication across lenses):** 0 blocker · 10 major · 15 minor.

---

## 2. Reviewer lenses and per-lens verdicts

| # | Lens | Verdict |
|---|------|---------|
| 1 | **Completeness** — is every brief-mandated area (personas, workflows, capability, competitors, licensing, threat model, feasibility) present and delivered against the research plan? | PASS WITH CONDITIONS |
| 2 | **Evidence & classification discipline** — is every finding classified OBSERVED/DOCUMENTED/INFERRED/UNKNOWN, are the classifications honest, do claims carry sources/dates/confidence, and is the package candid about the absence of measured evidence? | PASS WITH CONDITIONS |
| 3 | **AI realism & risk** — honesty of capability/failure-mode descriptions, absence of fabricated/over-optimistic accuracy claims, and safety of recommended default modes for live worship services. | PASS WITH CONDITIONS |
| 4 | **Licensing / privacy / security / feasibility gap audit** — are constraints correct and actionable, and are UNKNOWNs honestly deferred to Stage 5/13 rather than hand-waved? | PASS WITH CONDITIONS |

---

## 3. Consolidated blocker findings

**None.** No finding from any lens rises to blocker severity. Every major finding is a bounded gap that can be resolved inside Stage 3 (requirements) or routed to an existing Stage 5 spike / Stage 13 review, and none invalidates the package's core conclusions.

---

## 4. Consolidated major findings (with recommendations)

The ten majors are distinct across lenses; no two majors collapse into one. They are grouped by theme.

### Scope delivery gaps

#### M1 — Adjacent-product research (RP-03) planned but not delivered (Lens 1)
The brief's mandatory study list includes live transcription/captioning systems and sermon-note platforms, and the team's own RESEARCH-PLAN RP-03 scoped **Otter** and **Descript**. The delivered PROVIDER-TRADEOFFS.md never mentions either (grep = 0) and studies only the underlying tech layer (Whisper variants, cloud STT, sermon-note LLMs, TTS). No product/workflow-level study of any dedicated transcription/captioning/sermon-note application exists, leaving transcript-editing UX, speaker labeling, chapter markers, correction flows, and sermon-note structuring un-benchmarked for two entire release phases (Phase 3, Phase 5).
**Recommendation:** Add a short product/workflow study of Descript + Otter (plus one church-oriented live-captioning tool) capturing transcript-editing, diarization/speaker-label, chapter-marker, and export/publish workflows — **or** explicitly record these categories as UNKNOWN-deferred with rationale — before Stage 3 locks transcription and sermon-note requirements.

#### M2 — No text-shaping / RTL / Unicode / font-coverage feasibility (Lens 1)
The brief requires (unqualified) "Unicode and multiple languages" for scripture and "right-to-left language support where practical," and the org is Nigeria-based with cited multilingual transcription (Yoruba/Hausa/Igbo/French/Spanish). No artifact addresses complex-script shaping, bidi/RTL layout, or font fallback (grep: RTL = 0). FEASIBILITY names glyphon/wgpu-text as textured-quad glyph rendering only, and none of spikes S1–S9 covers non-Latin/RTL text layout — a genuine open risk for a custom GPU text stack that could invalidate the leaning renderer choice.
**Recommendation:** Add a text-shaping / RTL / font-coverage spike (or confirm cosmic-text / HarfBuzz-class shaping in the chosen renderer) and state the MVP language/script scope. If RTL/complex scripts are out of MVP, record that as an explicit scoped-later decision rather than leaving the requirement uncovered.

### Evidence & classification integrity

#### M3 — Inconsistent definition of OBSERVED undermines the headline honesty claim (Lens 2)
The four-level scale is defined three different ways: COMPETITOR-MATRIX = "directly seen on a page/video"; PROVIDER-TRADEOFFS / CAPABILITY-ASSESSMENT / FEASIBILITY / threat-model = "we ran/measured/verified it ourselves"; LICENSING-REGISTER = "seen directly in a primary licence text." Under the licensing definition ~7 findings are tagged OBSERVED/High (ESV terms, API.Bible, SIL OFL, NDI SDK) that are document *reads*, not measurements — colliding with the package's headline "Zero OBSERVED... no code executed, no benchmarks run," a collision propagated into the top-level index (EVIDENCE-REGISTER §3 promotes NDI licence terms to OBSERVED/High a few lines above the "zero OBSERVED" footnote).
**Recommendation:** Adopt one shared definition of OBSERVED (recommend: first-hand empirical observation — you ran/measured/saw the behaviour). Relabel licence-text reads as DOCUMENTED (primary source), or rename the tag (e.g. PRIMARY-DOC) if a primary/secondary distinction is wanted, and correct EVIDENCE-REGISTER §3 and the totals table.

#### M4 — RP-12 (personas/workflows) is entirely unclassified and overclaims completeness (Lens 2)
PERSONAS.md and WORKFLOWS.md carry no OBSERVED/DOCUMENTED/INFERRED/UNKNOWN tags, no sources, no dates, no confidence — the whole RP-12 body is exempt from the discipline applied everywhere else. They assert user pain points, "what churches want," permission defaults, and failure-recovery behaviours with no evidence basis and, critically, **no statement that no primary user research (interviews/field observation) was conducted** — the RP-12 analogue of the "no code/no benchmarks" disclosure made elsewhere. Meanwhile DISCOVERY-REPORT and EVIDENCE-REGISTER claim "All RP-01…RP-13 research is complete and classified" while the totals table leaves the personas/workflows row as "—".
**Recommendation:** Add an explicit limitation note to both files (no interviews/field observation; personas, pains and workflow behaviours INFERRED from domain knowledge and competitor research, not validated). Classify persona needs/pains and workflow behaviours as INFERRED. Soften the "complete and classified" / "evidence-driven" claims to reflect that RP-12 is un-validated domain modelling.

#### M5 — Overclaimed confidence on uncorroborated vendor performance figures (Lens 2)
COMPETITOR-MATRIX §2.1 tags PewBeam's self-reported performance ("detection in ~2 seconds," "under 80 ms") as DOCUMENTED/High, sourced only to the vendor's marketing page — while the document's own convention says "how well X works" findings should be INFERRED/UNKNOWN, and §6 UNKNOWN #8 itself lists PewBeam real-world latency as UNKNOWN. The matrix simultaneously rates the figure DOCUMENTED/High and UNKNOWN: an internal contradiction and a confidence overclaim on marketing numbers.
**Recommendation:** Re-tag vendor-stated performance as "vendor-claimed / uncorroborated" at Low confidence (or: DOCUMENTED that the *claim exists*, explicitly separated from confidence the claim is *true*), consistent with the doc's own convention and §6 #8. Apply the same to any other performance number sourced solely to vendor marketing.

### AI failure-mode honesty

#### M6 — Undisclosed LLM fabrication failure mode in sermon notes (RP-05) (Lens 3)
The package is candid about ASR hallucination and scripture-detection fallibility, but sermon-notes coverage never names the LLM's own first-order risk: note generation can **fabricate or misattribute** content — invented supporting scripture references, fabricated "important quotations," imagined illustrations, wrong people/books — compounding on top of a transcript the same package says has materially-elevated real-room WER on exactly the tokens notes depend on (names, numbers, quotations). Mitigations exist (human-gated, editable, labelled AI-generated) but the failure mode itself is absent from the "candid" narrative, inconsistent with the honesty standard applied to the other three capabilities.
**Recommendation:** Add an honest failure-mode paragraph stating notes can fabricate/misattribute scripture references, quotes, and illustrations; that this compounds with upstream ASR error; and that any auto-extracted scripture reference must be **verified against the local Bible index and flagged unverified until matched** before export. Keep human-review-before-export and AI-generated labelling as the stated safety net.

#### M7 — Scripture auto-display opt-in: residual wrong-verse risk not disclosed (Lens 3)
CAPABILITY-ASSESSMENT §2.7 permits an advanced opt-in that auto-stages/auto-displays "high-confidence explicit parsed references" with no operator confirmation. But §2.4 warns number/proper-noun errors are especially damaging, and the parser is text-based so ASR errors upstream are the limiter. A mis-heard digit ("3:16" → "3:6") yields a fully-parsed, high-parse-confidence but **wrong** reference auto-fired onto the congregation screen — the exact error the doc calls the most publicly damaging. The one mode that removes the operator safety net is the one whose residual failure path is undisclosed. (Default operator-confirmation mode is safe, so this is scoped to the opt-in.)
**Recommendation:** Disclose in §2.7 that high parse-confidence ≠ correct reference under ASR number/name errors. Require a corroboration gate before any auto-display (cross-check surrounding transcript context / verse text, or require the reference repeated); keep semantic-only matches permanently barred from auto-display; frame auto-display as **strongly discouraged** rather than a routine opt-in.

### Licensing / privacy / feasibility consistency

#### M8 — Codec-patent safe harbor undermined by GStreamer software decoders (Lens 4)
The licensing register's codec-patent safe harbor depends on delegating decode to OS-native/platform decoders (§2.1, INFERRED/Med, itself UNKNOWN #5). But FEASIBILITY §3/§9 commits to GStreamer **without constraining it to platform/HW-decode elements**. GStreamer's default software decoders (gst-libav `avdec_h264`/`avdec_h265`) do **not** inherit the OS vendor's patent licence — shipping them re-exposes the distributor to the Via LA / Access Advance H.264/HEVC/AAC liability the register warns against. OD-08 compounds this by calling codecs "non-blocking for MVP" on the basis of an unconfirmed legal assumption plus an un-adopted architectural constraint. Video-background decode is squarely in the presentation-only MVP, so this path is load-bearing, not deferrable.
**Recommendation:** Add a build constraint that the media engine use only platform/HW-decode GStreamer elements (d3d11/va/vtdec/nvdec) and exclude gst-libav for encumbered codecs; make it a Stage 5 ADR input. Downgrade OD-08 to conditional pending register UNKNOWN #5 (legal confirmation that OS-native decode delegates patent liability). Note that VP9/AV1+Opus preference covers only SelahCue-generated media, not user-imported H.264 backgrounds.

#### M9 — No at-rest encryption for the primary datastore; three documents inconsistent (Lens 4)
The licensing posture (§4) promises "encrypt at rest and in transit," and transcripts/audio/notes are NDPA/GDPR personal data that may include congregation PII. But the threat model mandates encryption only for **backups** (T15); T9 covers only API keys in the OS secret store. The primary SQLite store and captured audio on the booth PC have no described at-rest confidentiality control, and Persistence §7 treats SQLite as plaintext (no SQLCipher). On an unattended AV-booth PC (theft, shared machine, local malware) this contradicts the stated posture.
**Recommendation:** Define an at-rest control: either app-level DB encryption (SQLCipher) with a key-custody model tied to the OS secret store, **or** an explicit decision to require + verify OS full-disk encryption (FileVault/BitLocker/LUKS) as a documented deployment prerequisite. Reconcile register §4, threat-model T15, and Persistence §7 into one coherent PRD requirement.

#### M10 — Make-or-break spike S2 committed as architecture with no fallback (Lens 4)
S2 (zero-copy HW-decode → wgpu texture interop per OS) is correctly called "the biggest technical risk," yet §9 commits firmly to "wgpu compositor fed by GStreamer GPU textures" with **no fallback if S2 fails**. wgpu's external/HW-texture import is genuinely limited and per-backend (VA-API surface / NVDEC / Metal IOSurface / D3D11 shared-handle are not first-class cross-platform paths). Naive `write_texture` is ~498 MB/s for one 1080p60 stream before compositing, so zero-copy is not optional for the target. If S2 fails on any of the three OSes the whole topology needs rework, yet the PRD risks lifting "2–3 independent 1080p60 outputs" (target #8, INFERRED/Low) into a hard requirement without contingency.
**Recommendation:** State an explicit fallback architecture for the S1/S2 failure case (GStreamer glvideomixer / per-OS native compositors / accept 1080p30 or fewer outputs) and **gate** the multi-output + 1080p60 promises on spike results before they enter the PRD as committed requirements. Note in §9 that the leaning presupposes S2 success.

---

## 5. Minor findings

Carry into the Stage 3 requirements backlog; none blocks the gate.

**Completeness (Lens 1)**
- **m1 — Uncovered reliability failure modes.** No failure-recovery flow for a media decoder failing mid-playback (software-decode fallback); no storage-space warnings (grep = 0); no safe mode (grep = 0); diagnostic reports / log rotation only lightly implied. (Relates to M8's decoder question.)
- **m2 — Missing feature-inventory items.** Command palette, undo/redo, operator multiview (core presentation); translation comparison, scripture history, favourites, verse-number formatting (scripture); transcript export formats (txt/md/json/srt/webvtt/pdf).
- **m3 — Multiple-output configuration depth.** Per-output delay (broadcast/lip-sync), recording output, lobby/overflow displays, test patterns, mirroring/rotation/cropping/safe-areas not individually addressed as SelahCue capabilities.
- **m4 — Accessibility research absent.** No treatment of keyboard-only operation, screen-reader support, or high-contrast/large-text legibility for confidence/stage displays under stage lighting, despite the brief expecting an Accessibility PRD section and TTS-as-accessibility.

**AI realism (Lens 3) + Completeness (Lens 1)**
- **m5 — Diarization candor + coverage gap (merged).** Whisper does not diarize natively and CAPABILITY-ASSESSMENT omits the limitation; live-room diarization (roving mics, overlapping speech, PA bleed) is unreliable and speaker-attributed timestamps in notes inherit those errors. Add a one-line "multiple speakers where practical / labels editable, not authoritative" note and pick this up in the Stage 3 feature inventory.
- **m9 — Cloud→local STT fallback assumes local viability the package denies elsewhere.** The "never let a live service go dark" fallback promises seamless local takeover, but §1.1/1.3 establish some church PCs cannot sustain real-time local Whisper (FP16 large-v3 RTF 1.26 on CPU). Reword to scope the guarantee to the *presentation output* (protected by the AI-never-blocks-slides invariant) and state transcription **degrades gracefully** (pause / reduced model / "transcription degraded" status) on insufficient hardware.
- **m10 — Dangling "(see UNKNOWNs)" cross-reference.** CAPABILITY-ASSESSMENT repeatedly points to a UNKNOWNs section that does not exist in the file; the real spikes live in FEASIBILITY (S8, §10). Add a UNKNOWNs section or link enumerating the unmeasured items (real-room WER by mic/room/accent, end-to-end explicit-reference detection rate, semantic false-positive rate, local-model real-time headroom).

**Evidence discipline (Lens 2)**
- **m6 — Confidence calibration on single secondary/personal-blog sources.** FEASIBILITY §2 tags a single personal-blog benchmark (wgpu "~249 MB/s") DOCUMENTED/High while the same doc's closing note says treat such sources as "directional… DOCUMENTED-secondary"; similar High tags on PROVIDER-TRADEOFFS pricing/latency. Downgrade to Med / DOCUMENTED-secondary; reserve High for primary or corroborated figures.
- **m7 — Unsourced/unclassified prose + declarative phrasing.** PewBeam founder/origin/launch stated with no citation/class; DISCOVERY-REPORT restates INFERRED/Med estimates ("1–5s lag," "materially worse WER") in bold declarative voice without qualifiers; WORKFLOWS describes unbuilt behaviour in present-tense indicative ("SelahCue restores the exact prior live state") reading as a delivered guarantee. Source/tag the stray facts, keep INFERRED qualifiers in the executive report, phrase unbuilt workflows as must/should design intent.
- **m8 — External-source verifiability and dating.** Uniform access date (2026-07-23) for every source; publication dates only sporadic; the reviewer could not verify external URLs from within the environment. Spot-check load-bearing citations (Whisper hallucination papers, allusion-overlap stat, WER/latency benchmarks, ESV/API.Bible/NDI terms) for existence and accuracy and add key publication dates before the gate; treat numeric claims as pending that check.

**Licensing / security / feasibility (Lens 4)**
- **m11 — iOS mDNS multicast entitlement dependency.** Since iOS 14, custom mDNS/Bonjour discovery requires `NSLocalNetworkUsageDescription` **and** the `com.apple.developer.networking.multicast` entitlement (explicit Apple approval) — a discrete third-party dependency that can block zero-config discovery, not just a tuning problem. Add it as a named dependency in the mobile ADR/S9 and design a QR-only pairing fallback independent of multicast.
- **m12 — KJV UK exposure not operationally realizable.** The register recommends bundling KJV "outside UK" (UK Crown/CUP copyright is UNKNOWN #4), but a globally downloadable desktop app has no described geo-exclusion mechanism. Either drop KJV (WEB/ASV/BSB are worldwide-PD and cover the need) or make UK exposure an explicit accepted-risk decision; do not carry "bundle KJV" into the PRD unresolved.
- **m13 — NDI inconsistency + omitted License-ID.** The register (§2.6) says the redistributable "may be bundled for free or commercial products" but omits the NDI-6 License-ID requirement that FEASIBILITY §4 raises ("NDI 6 needs a License ID; only header files are MIT"). Reconcile: the authoritative register should own the License-ID obligation and the header-vs-binary distinction, confirmed against the current 6.x EULA (register UNKNOWN #8).
- **m14 — Bottom-line overstates conditions for CC BY-SA and SongSelect.** The register lists unfoldingWord (CC BY-SA 4.0) as bundlable "with share-alike caveats" while the adaptation/share-alike risk for reflowed verse text in a proprietary app is a genuine open question (UNKNOWN #3); and "authorized SongSelect integration" is presented as a clean option without noting it requires a CCLI partner/API agreement (not a public API). Keep unfoldingWord conditional on UNKNOWN #3 (or bundle only the fully-PD set for MVP); annotate SongSelect as requiring a CCLI agreement.
- **m15 — mDNS deferral rationale + MVP-vs-post-MVP control delineation.** (1) mDNS spoofing/enumeration is deferred to Stage 13 while FEASIBILITY makes mDNS a core discovery path — defensible because QR-delivered host-fingerprint pinning defeats spoofed hosts even on first pair, but the threat model never states that rationale, so it reads as an unexamined gap. (2) Controls are tagged "(MVP unless noted)" but there is no consolidated MVP-control-set vs post-MVP-control-set view, risking either over-scoping MVP or silently dropping the cloud/consent/congregation-notice apparatus when AI lands. Add the pinning rationale and an explicit MVP-vs-post-MVP control table in the PRD.

---

## 6. Conditions to carry into Stage 3

Tracked, closable conditions. Each maps to the finding(s) above. The gate PASS is contingent on these being carried as visible backlog items, and on **C1–C10** being resolved or formally deferred with rationale before Stage 3 locks the corresponding requirement area.

1. **C1 (M1)** — Deliver the adjacent-product workflow study (Descript + Otter + one church live-captioning tool), or record those categories as UNKNOWN-deferred with rationale, before Stage 3 locks transcription and sermon-note requirements.
2. **C2 (M2)** — Add a text-shaping / RTL / Unicode / font-coverage feasibility spike (or confirm HarfBuzz/cosmic-text-class shaping in the chosen renderer) and state the MVP language/script scope; record RTL/complex-script deferral explicitly if out of MVP.
3. **C3 (M3)** — Adopt one package-wide definition of OBSERVED; relabel licensing licence-text reads as DOCUMENTED/PRIMARY-DOC; correct EVIDENCE-REGISTER §3 and the totals table.
4. **C4 (M4)** — Add limitation notes to PERSONAS.md and WORKFLOWS.md (no interviews / field observation; behaviours INFERRED, not validated); classify persona needs/pains and workflow behaviours as INFERRED; soften the "complete and classified" / "evidence-driven" claims.
5. **C5 (M5)** — Re-tag vendor-stated performance figures (PewBeam latency and any marketing-sourced numbers) as vendor-claimed/uncorroborated at Low confidence; resolve the DOCUMENTED-vs-UNKNOWN contradiction.
6. **C6 (M6)** — Add an honest sermon-notes fabrication failure-mode paragraph; require auto-extracted scripture references to be verified against the local Bible index and flagged unverified until matched before export.
7. **C7 (M7)** — Disclose the residual wrong-verse risk in the scripture auto-display opt-in; require a corroboration gate; keep semantic-only matches barred from auto-display; frame auto-display as strongly discouraged.
8. **C8 (M8)** — Add a media-engine build constraint (platform/HW-decode GStreamer elements only; exclude gst-libav for encumbered codecs) as a Stage 5 ADR input; downgrade OD-08 to conditional pending legal confirmation (register UNKNOWN #5).
9. **C9 (M9)** — Define an at-rest confidentiality control for the primary datastore (SQLCipher with documented key custody, or verified OS full-disk encryption as a deployment prerequisite); reconcile register §4 / threat-model T15 / Persistence §7 into one PRD requirement.
10. **C10 (M10)** — State an explicit fallback architecture for the S1/S2 failure case and gate the multi-output + 1080p60 performance promises on spike results before they enter the PRD as committed requirements.
11. **C11 (m1–m4, m5)** — Carry the reliability (GPU/decoder recovery, storage warnings, safe mode), feature-inventory, output-configuration, accessibility, and diarization gaps into the Stage 3 requirements backlog; add the Whisper-no-native-diarization limitation to the capability assessment.
12. **C12 (m6–m8, m10)** — Downgrade single-blog/secondary figures to Med/DOCUMENTED-secondary; source or tag stray prose facts; preserve INFERRED/UNKNOWN qualifiers in the executive report; phrase unbuilt workflow behaviours as design intent; add the missing UNKNOWNs section/link; spot-check load-bearing citations and add publication dates before the gate.
13. **C13 (m9)** — Rescope the cloud→local STT fallback guarantee to the presentation output and state that transcription degrades gracefully (pause / reduced model / visible "degraded" status) on hardware that cannot sustain local real-time.
14. **C14 (m11–m15)** — Add the iOS multicast entitlement as a named dependency with a QR-only pairing fallback; resolve KJV geo-exclusion; fold the NDI-6 License-ID into the authoritative register; tighten the CC BY-SA / SongSelect bottom-line; document the mDNS-pinning rationale and an MVP-vs-post-MVP control-set table.

---

## 7. Noted strengths

Aggregated across all four lenses (de-duplicated):

- **Exemplary candor about the absence of measured evidence.** Repeated, explicit "zero OBSERVED / no code executed / no benchmarks run / no source present" disclosures across every document, called out as "the single most important caveat." Access limitations (Chrome MCP unavailable, no paid trials, no source for the threat model) are named, not buried.
- **Correct load-bearing architecture call.** Tauri's WebView cannot be the GPU output compositor is identified and resolved with a defensible split (Rust core + wgpu compositor + native output windows; WebView/egui only for operator UI). Bandwidth/capacity numbers are internally consistent (1080p RGBA8 ~8.3 MB/frame × 30 ≈ 249 MB/s) and the zero-copy interop is honestly named the make-or-break risk.
- **Genuinely honest AI capability assessment.** Refuses to state an end-to-end scripture-detection accuracy number ("any single accuracy number would be fabricated"); decomposes into reliable-for-explicit / fallible-for-quotes / unreliable-for-paraphrase; treats every benchmark as a floor with real-room degradation named; flags Whisper hallucination-on-silence as a first-order risk with a mandatory VAD gate and caption-OFF-by-default.
- **Conservative, safe default modes for live services.** Operator-confirmation default, precision-over-recall bias, deterministic parser prioritized over semantic guesses, semantic-only matches never auto-fired, offline-first with consent-gated opt-in cloud, TTS correctly deferred with feedback/mic-bleed/self-re-transcription hazards mitigated.
- **Strong licensing/compliance rigor.** PD-vs-licensed Bible split, codec-patent exposure mapped (Via LA / Access Advance, LGPL-does-not-grant-patents, VP9/AV1/Opus preference), interchange-format-vs-text-copyright distinction ("bundling a SWORD module does not launder a copyrighted translation"), the catch that Free Use Bible API's MIT covers code not translations, NDPA-2023/GDPR alignment.
- **Solid early STRIDE threat model.** Mutual auth with QR-delivered host-fingerprint pinning, per-command monotonic nonce+timestamp replay protection, deny-by-default server-side RBAC (never trusting client-asserted role), per-device revocable keypair-bound tokens, OS-secret-store-only credentials, visible cloud indicator, path-traversal/zip-slip handling, and signed-update/anti-rollback with specific Sparkle CVE-2025-0509 awareness.
- **Disciplined structure.** All 11 personas with a 7-role × 15-capability permission matrix and a clear enforcement invariant; all three workflow classes internally consistent (8 + 9 + 7 = 24) with every audited failure state covered; nine concrete named spikes (S1–S9); OPEN-DECISIONS OD-01…OD-20 each with a recommended default so the gate is not blocked while UNKNOWNs stay surfaced.

---

## 8. Reviewer independence

This consolidated review was produced by a lead independent reviewer operating in **fresh context**. The reviewer **did not author** any part of the SelahCue discovery package (PERSONAS, WORKFLOWS, COMPETITOR-MATRIX, CAPABILITY-ASSESSMENT, PROVIDER-TRADEOFFS, LICENSING-REGISTER, threat-model-draft, FEASIBILITY, OPEN-DECISIONS, EVIDENCE-REGISTER, DISCOVERY-REPORT) and had no role in the four upstream lens reviews being synthesized. The synthesis judges the material on its own evidence and internal consistency; where the underlying package cites external sources, those citations could not be independently fetched or verified from within this environment (see finding m8), and the associated numeric claims are treated as pending that verification rather than confirmed. No finding in this review depends on privileged or prior knowledge of the authors' intent.

---

*End of Stage 2 discovery gate review.*
