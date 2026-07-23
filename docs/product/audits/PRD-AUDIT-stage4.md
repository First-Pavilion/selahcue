# SelahCue — Stage-4 PRD Audit (Adjudicated)

**Document:** Formal Stage-4 PRD Audit — Lead Auditor Adjudication
**Product:** SelahCue
**Date:** 2026-07-23
**Adjudicator:** Lead independent auditor
**Inputs:** Five independent Stage-4 auditor reports (recovery/operator-controls; ambiguity/testability/assignability; AI expectations & audio-feedback safety; privacy/licensing/security/accessibility; release scope/performance/offline)

---

## 1. Overall Verdict

# PASS WITH CONDITIONS

**Rationale (against the decision rule):**
- FAIL requires at least one standing **blocker**. Zero blockers were raised by any of the five auditors, and none survives adjudication. → Not FAIL.
- Clean PASS requires **no blocker and no major** findings. Seventeen distinct major findings remain after de-duplication. → Not a clean PASS.
- Therefore the adjudicated verdict is **PASS WITH CONDITIONS**: architecture and planning may begin, but the 17 consolidated majors are conditions that must be resolved (with a re-check) before ticket decomposition. The 16 consolidated minors are advisory and should be batched into the same PRD revision.

**Consolidated finding counts (after de-duplication):**

| Severity | Raw (5 reports) | After de-dup | Standing |
|---|---|---|---|
| Blocker | 0 | 0 | 0 |
| Major | 18 | 17 | 17 |
| Minor | 18 | 16 | 16 (advisory) |

Every one of the five area audits independently returned **PASS WITH CONDITIONS**. There is no contradiction to arbitrate between auditors; the adjudication task is to de-duplicate, confirm no finding should be elevated to blocker, and consolidate the required PRD changes.

---

## 2. Audit Method & Independence Statement

- **Independence:** The adjudicator operated from a fresh context and did **not** author the PRD, the supporting artefacts (WORKFLOWS.md, PERSONAS.md, CAPABILITY-ASSESSMENT.md, LICENSING-REGISTER, threat model), or any of the five source audits. No auditor reviewed their own work; this adjudication reviews the auditors.
- **Method:** Five specialists each audited a bounded area against the SelahCue brief, the FR/NFR tables, §11–§34, and the normatively-referenced companion documents. Each produced a JSON verdict with severity-tagged findings, recommendations, and a strengths register. The adjudicator: (a) applied the fixed decision rule (blocker → FAIL; major → PASS WITH CONDITIONS; minors-only → PASS); (b) de-duplicated findings that multiple auditors raised against the same PRD defect; (c) tested each major against the blocker bar ("does this prevent architecture/planning from starting, or is it an in-place fix?"); and (d) consolidated the exact PRD change required for each surviving major.
- **Blocker bar applied:** A finding is a blocker only if it is a foundational contradiction that makes downstream architecture/planning unsafe to begin. All 17 majors are additive or clarifying edits — new/expanded FR-NFRs, reframed acceptance criteria, corrected counts/ranges, or recorded decisions — resolvable in place without re-baselining. None meets the blocker bar. The auditors' own calibration (notably the explicit "0 blockers" in every area and the borderline-major note on NFR-008) is consistent with this.

---

## 3. Per-Area Verdicts

| # | Audit Area | Verdict | Majors | Minors |
|---|---|---|---|---|
| A | Missing workflows, failure states, recovery weaknesses, operator controls (EPIC-I/Q, FLOW-*, NFR-024) | PASS WITH CONDITIONS | 4 | 3 |
| B | Ambiguous requirements, untestable ACs, hidden assumptions, specialist-assignability | PASS WITH CONDITIONS | 3 | 5 |
| C | Unrealistic AI expectations, audio-feedback risks, AI-safety defaults; TTS de-scope | PASS WITH CONDITIONS | 2 | 2 |
| D | Privacy, Licensing, Security & Accessibility (§16–§25) | PASS WITH CONDITIONS | 6 | 5 |
| E | Oversized release scope, performance risks, offline limitations | PASS WITH CONDITIONS | 3 | 3 |

**Cross-area convergence — the TTS de-scope is incomplete in the companion documents.** Auditors B and C independently found the same defect: DEC-001/NG-1 is clean in the PRD *body* but not in the two documents the PRD **normatively incorporates by reference** — the PERSONAS.md §2 permission matrix (still carries a live "TTS control" capability row feeding FR-090 and the §16 "15 capabilities" count) and WORKFLOWS.md (still contains TTS flows A8/B8/F4 and TTS routing in the Sound Engineer/Production Operator personas). Auditors A and D confirmed the PRD-body de-scope is otherwise clean. This convergence is consolidated as **MAJOR-07** below.

**Confirmed cross-area strengths (not defects; must not be re-litigated):** the recovery core (display disconnect, mobile loss, provider fallback, crash recovery, missing media, offline) and operator controls (emergency clear/blackout/per-layer clear, pre-service checklist, desktop stage-message authoring); strong AC discipline with numeric bounds; a faithful AI-safety posture (no perfect-accuracy claims, operator-confirmation default, VAD gating, precision-over-recall, non-authoritative diarization, sermon-note safety, AI-never-blocks-core); a well-mapped LAN control-plane threat model (pairing, RBAC, replay/rate-limit, revocable tokens, audit log, secret storage, signed updates, at-rest encryption); PD-only Bible bundle and codec safe-harbor posture; and substantially complete, consistent offline guarantees.

---

## 4. Consolidated Blockers

**None.** No auditor raised a blocker and none is elevated on adjudication. There is no foundational contradiction; the PRD's spine (presentation core, recovery core, AI-safety defaults, offline guarantees, LAN threat mapping) is sound. Architecture and planning may begin in parallel with resolving the conditions below.

---

## 5. Consolidated Majors (conditions to resolve — each with the exact PRD change)

Ordered by theme. IDs are stable references for the resolution re-check.

### Reliability, recovery & operator control

**MAJOR-01 — Storage exhaustion has no MVP coverage.**
*Source: Area A. Refs: FR-081 (R2), NFR-024, §23, §30.*
The only storage requirement (FR-081) is R2 and gated to capture/record; yet MVP autosave/checkpointing (FR-074/075), media import (FR-138), backups and rotating logs all write to disk, and NFR-024's fault-injection list omits storage. A full disk during an 8–12h service (NFR-010) silently breaks checkpoint writes and defeats crash recovery.
**PRD change:** Add an MVP storage-exhaustion FR: pre-write low-disk detection/warning independent of capture/record; a guaranteed checkpoint headroom or a defined graceful-degradation path when autosave/checkpoint writes fail (always surfaced to the operator, never silent); and add "storage exhaustion" to the NFR-024 fault-injection set.

**MAJOR-02 — No crash-loop breaker / resume-decline operator control in MVP.**
*Source: Area A. Refs: FR-075, FR-081 (R2), WORKFLOWS F5.*
FR-075 auto-restores exact prior live state on relaunch, but if the restored state is itself the crash cause (bad plan item, media, theme, config) this produces an unrecoverable resume→crash loop mid-service. The mitigating safe-mode is deferred to R2 (FR-081).
**PRD change:** Make the resume-vs-decline choice an explicit MVP clause in FR-075: after N rapid crashes, do not silently auto-resume — offer "Resume last live state" vs. "Start clean / skip last-loaded item" and disable the suspected offending item. Do not rely on R2 safe-mode for MVP crash-loop protection.

**MAJOR-03 — Transcription capture-device disconnect has no requirement.**
*Source: Area A. Refs: EPIC-K FR-099/104/105 (R3), FR-161, WORKFLOWS F2.*
Mid-transcription loss of the audio **input** device is a named required failure state (WORKFLOWS F2: pause, preserve captured transcript, insert gap marker, resume on device return), but no FR captures it — FR-161 is the audio **output/playback** device, FR-099 only selects input, FR-104 is hardware degradation, FR-105 is app-restart recovery.
**PRD change:** Add an R3 FR (trace WORKFLOWS F2, brief §Reliability): on capture-device disconnect, transcription pauses (not crashes), captured segments preserved, a visible gap marker on reconnect/new-input selection, transcription resumes, slide control unaffected — with measurable acceptance criteria.

**MAJOR-04 — GPU device-loss recovery guarantee is physically infeasible as worded.**
*Source: Area A. Refs: FR-160, NFR-024.*
FR-160/NFR-024 promise GPU device-loss recovery "without blanking other outputs" absolutely, but a device-wide reset (Windows TDR / driver restart) drops the swapchain of **every** output on that GPU simultaneously — including MVP main + stage/confidence when they share one GPU. The requirement conflates isolated per-output decoder failure with whole-device GPU loss and sets an unachievable bar.
**PRD change:** Reframe FR-160/NFR-024 for the device-wide case: guarantee no content loss / no operator rebuild and a **bounded recovery-time target** (affected outputs hold last presented frame where possible and recover within N ms/s), rather than "never blanks." Distinguish per-output decoder failure (isolated) from whole-device GPU loss (transient across all shared-GPU outputs) in acceptance criteria and fault-injection tests.

### AI testability & expectations

**MAJOR-05 — Normative AI acceptance criteria reference benchmark corpora that do not exist.**
*Source: Area B. Refs: FR-102, FR-121, METRIC-009 (§13 EPIC-K/L, §31).*
FR-102 cites "the standard non-speech test set" and FR-121/METRIC-009 cite "the explicit-reference test set"; neither corpus's composition, source, size, or scoring protocol is defined anywhere (CAPABILITY-ASSESSMENT §4 lists both as UNKNOWN spikes). The "provisional, ratified after Stage-10" note covers only the threshold *number*, not the *existence of the corpus*, so QA cannot verify "≤1% / ≤5% on <undefined set>." FR-102 also leaves the measured "displayed text" surface ambiguous given verbatim display is OFF by default (FR-166).
**PRD change:** Add a spike deliverable (or requirement) defining each test set's composition, source, size, and pass/fail protocol, and make FR-102/FR-121/METRIC-009 reference that named artefact. Clarify in FR-102 which surface is measured.

**MAJOR-06 — FR-108 "added terms measurably reduce their error" is untestable.**
*Source: Area B. Refs: FR-108 (§13 EPIC-K).*
No error metric, no minimum improvement magnitude, no evaluation corpus — "measurably reduce" admits any non-zero delta and points to no harness, so it can neither reliably pass nor fail.
**PRD change:** Specify the metric (e.g. per-term/keyword error rate), a minimum required improvement or an explicit A/B protocol with a threshold, and the named evaluation set (tie to the MAJOR-05 corpus work).

### De-scope cleanliness

**MAJOR-07 — TTS de-scope is incomplete in the PRD's normatively-cited companion documents.**
*Sources: Areas B and C (same defect, independently found — merged). Refs: §16 Permissions + FR-090 via PERSONAS.md §2; §11 via WORKFLOWS.md A8/B8/F4.*
The PRD body honours DEC-001/NG-1 (no residual TTS FR, RISK-008 retired), but: (a) PERSONAS.md §2 — declared authoritative by §16 ("7 roles × 15 capabilities") — still contains a live "TTS control" capability row (Production Operator ✅, Administrator ✅, Scripture Operator ⚠️), which FR-090's deny-by-default command→role allowlist is built and QA-verified against; and (b) WORKFLOWS.md — cited by §11 for full narrative flows — still contains complete TTS flows A8 (read passage to output), B8 (TTS-to-file) and F4 (TTS-provider-failure handling), plus TTS routing in the Sound Engineer persona and the Production Operator note. An architect/QA taking §16 and the cited docs as normative would build/verify a permission and workflows for a removed feature.
**PRD change:** Strike the "TTS control" row from PERSONAS.md §2 (matrix becomes 7 roles × **14** capabilities); correct the PRD §16 count from **15 to 14**; remove "TTS" from the Production Operator note and prune TTS output-routing from the Sound Engineer persona; mark WORKFLOWS.md A8/B8/F4 as de-scoped (DEC-001) or move them to a historical/retained appendix. Preserve the distinction between legitimately-retained TTS *research* artefacts (CAPABILITY-ASSESSMENT/PROVIDER-TRADEOFFS/LICENSING/FEASIBILITY/threat-model) and PRD-normative sources (PERSONAS matrix, WORKFLOWS), which must be TTS-free.

### Audio-feedback safety

**MAJOR-08 — Residual audio-feedback / self-re-transcription path unaddressed after TTS removal.**
*Source: Area C. Refs: §18/EPIC-K FR-099/102/068, EPIC-L FR-111; DEC-001.*
DEC-001 removed the TTS feedback-safety subsystem, but the app still emits room audio: media playback (FR-068), looping motion backgrounds (FR-069), and the TIME UP audible cue (FR-063). With app audio routed to the house PA and a live R3 transcription mic open, the mic re-ingests the app's own audio — polluting the transcript and (worse) letting speech-bearing media, e.g. a testimony video quoting John 3:16, trigger false scripture detections (FR-111) and misattributions in sermon notes (FR-122). FR-068's internal-loopback guard does not prevent acoustic re-capture; FR-102 VAD passes speech-active media audio.
**PRD change:** Add an R3/R4 FR (with testable AC) to suppress/pause transcription ingestion and gate scripture-detection firing during app-initiated media/alert audio routed to shared/house outputs (half-duplex analogue of the removed TTS guard), plus a visible operator warning and documented mic-source guidance. Promote the CAPABILITY-ASSESSMENT §1.2/§1.3 PA-bleed/self-re-transcription mitigation from prose into a normative FR.

### Security & privacy controls

**MAJOR-09 — Malicious-media decode hardening is uncovered.**
*Source: Area D. Refs: §20, FR-138, FR-160, threat T12 (High, RCE via malformed media).*
FR-138 covers import **path** safety and FR-160 covers decoder **failure** recovery, but no requirement covers decode-time **exploitation** of a crafted image/video/font. MVP ships user-imported media (FR-066/067) and fonts (FR-017), so the primary RCE surface into the authoritative host is unrequired.
**PRD change:** Add an MVP security FR (EPIC-P) requiring untrusted-media/font decode via memory-safe or actively-maintained decoders, header/type/size validation before full decode, isolation/sandboxing of the decode path where platform-feasible, and a stated patch cadence; trace to T12. (Deep fuzzing may remain Stage-13.)

**MAJOR-10 — Control-message schema/input validation is missing.**
*Source: Area D. Refs: FR-091, §20, threat T20.*
FR-091 covers only replay + rate-limiting; FR-090 covers RBAC. No requirement mandates strict schema/type/size/range validation or rejection of unknown/oversized fields on LAN control messages, so a malformed message crashing the host parser mid-service (T20) is unaddressed — a live-service availability risk on the highest-impact asset (live output).
**PRD change:** Add an MVP FR (or extend FR-091) requiring strict schema/type/size/range validation of every control message with fail-safe behaviour (reject + keep last-good output rendered), traced to T20; add a fuzz/fault-injection AC for the control parser.

**MAJOR-11 — Encrypted-transport requirement is scoped to "control traffic" only.**
*Source: Area D. Refs: FR-088, NFR-016, FR-092/164/096, threat T3.*
FR-088/NFR-016 mandate TLS 1.3 for "control traffic," but mobile also receives slide/next previews (FR-092), a live transcript view (FR-164), and output-health/stage content. As worded, a separate preview/transcript/media channel would carry sensitive personal data (transcripts) in cleartext on untrusted church WiFi (T3, High).
**PRD change:** Broaden FR-088/NFR-016 from "control traffic" to "all LAN traffic to/from controllers — control, previews, transcript/caption streams, and media" over the pinned TLS 1.3 (or authenticated app-layer) channel; add an AC asserting no plaintext preview/transcript egress.

### Accessibility

**MAJOR-12 — No seizure-safety / reduced-motion requirement (WCAG 2.3.1).**
*Source: Area D. Refs: §22, FR-050, FR-059, NFR-020.*
FR-059 offers a "flash" TIME UP state and FR-050 offers entry/exit animations, both routable to audience/livestream outputs, yet nothing implements WCAG 2.3.1 (≤3 flashes/sec, a Level A criterion) or a reduced-motion affordance. NFR-020 claims "WCAG 2.1 AA contrast" while the flash/focus criteria are absent — a photosensitive-seizure health/safety and WCAG-A gap on public displays.
**PRD change:** Add an MVP accessibility FR bounding any flashing/animated output to ≤3 flashes/sec (WCAG 2.3.1) with a reduced-motion option, and correct the NFR-020/§22 framing so "WCAG 2.1 AA" is not asserted beyond contrast unless the flash/focus criteria are added.

**MAJOR-13 — MVP operator UI and mobile controller ship with zero assistive-technology support.**
*Source: Area D. Refs: NFR-021, NFR-026, §22, §30, DEC-001.*
Full desktop screen-reader support (NFR-021) and **all** mobile-controller accessibility (NFR-026 — accessible labels, ≥44×44pt targets) are deferred to R2, yet both surfaces ship in MVP; keyboard operability (NFR-019) without accessible names/roles is unusable by a screen-reader operator. Compounding this, DEC-001 justifies TTS removal partly by citing "screen-reader compatibility" as the compensating path — which is R2, so the named compensation is absent in MVP.
**PRD change:** Pull the low-cost minimums into MVP — accessible names/roles for core live desktop controls, and accessible labels + minimum touch-target size for the MVP mobile controller. Keep full screen-reader coverage at R2 if justified, and reconcile the DEC-001 rationale so it does not rely on an R2 capability.

### Compliance deliverables

**MAJOR-14 — No requirement/launch criterion for privacy policy, store disclosures, DPA, or cross-border handling.**
*Source: Area D. Refs: §21, §25, §32, LICENSING-REGISTER §4/§5.*
The MVP mobile controller ships via app stores (which reject apps lacking a privacy policy for network/PII access) and R3 cloud processing creates a processor/cross-border relationship (NDPA 2023 + GDPR). FR-132/136 disclose retention/opt-in but not a published privacy policy, App Privacy / Data Safety disclosures, a DPA, or cross-border transfer.
**PRD change:** Add requirements and launch-criteria items for: a privacy policy shipped/linked in-product and in each store listing; App Store/Play data-disclosure completion for the MVP mobile app; a DPA + cross-border-transfer disclosure gating cloud-provider opt-in (R3); and make FR-132's "visible disclosure" specify that it names the provider, what is sent, and that data leaves the local network/jurisdiction.

### Release scope & performance

**MAJOR-15 — RISK-001 (two-product MVP surface) is under-mitigated (process-only).**
*Source: Area E. Refs: §30, RISK-001, AS-1.*
The MVP couples a from-scratch cross-platform GPU-compositing suite (5 target OSes), a fully hardened LAN control plane, 7-role RBAC, and hard real-time reliability guarantees (~79 FRs + ~18 NFRs) on an unproven, spike-gated architecture. AS-1 concedes the mobile piece alone is "two full hardened subsystems." RISK-001's mitigation only draws the boundary; it neither sequences nor milestones the two-product surface nor states a delivery-capacity assumption.
**PRD change:** Strengthen RISK-001 with explicit intra-MVP sequencing (e.g. a shippable presentation-core desktop sub-release before the mobile control-plane slice AS-1 earmarks for Stage 7) and record the team-size/duration assumption the bounded MVP presumes. Do not treat the hardened mobile control plane as free within "presentation foundation."

**MAJOR-16 — MVP dual concurrent outputs are mis-described and rest on an un-risk-registered spike.**
*Source: Area E. Refs: §30, FR-036/037/040/041, FEASIBILITY §10 / spike S4.*
MVP requires two concurrent independent surfaces (main FR-036 + stage/confidence FR-037) plus multi-display assignment (FR-040) and hot-plug reconnection without blanking (FR-041) — all depending on robust independent multi-monitor exclusive-fullscreen windowing, which FEASIBILITY §10 flags UNKNOWN (spike S4). Yet §30 reasons only about "the MVP single main output" and no RISK entry gates the MVP dependence on S4.
**PRD change:** Correct §30 to state MVP drives two concurrent independent outputs (main + stage), not a single output; add a RISK-register entry (and explicit S4 acknowledgment) for MVP multi-display windowing + hot-plug robustness, with the FEASIBILITY-recommended borderless-per-monitor fallback noted as the mitigation, so FR-040/FR-041 are not committed ahead of the spike.

**MAJOR-17 — NFR-008 is the sole unproven performance target carrying neither spike-gate nor provisional caveat; C-7 discharge is incomplete.**
*Source: Area E. Refs: NFR-008 vs NFR-007/012, §34 C-7 discharge.*
NFR-008 (scripture-detection latency ≤1.5s, R4) rests on an INFERRED (Low) feasibility basis and is covered by the same spike S8 as transcription latency, yet — unlike NFR-007 (spike-gated) and the provisional FR-102/FR-121/METRIC-009 — it carries no gate or caveat. The §34 C-7 discharge claims parity via "NFR-005/007/012 annotated" but omits NFR-008.
**PRD change:** Annotate NFR-008 as spike-gated (S8) and/or mark it provisional pending Stage-5/Stage-10 measurement, matching NFR-007 and METRIC-009; correct the C-7 discharge note to include NFR-008.

---

## 6. Minors (advisory — batch into the same PRD revision)

These do not gate the verdict. Listed de-duplicated.

1. **Timer-restore semantics after downtime** (Area A; FR-075/FLOW-008/F7): define wall-clock-anchored countdowns vs. accumulated count-up on recovery; add ACs for a <5s checkpoint gap and a multi-minute power-loss gap.
2. **Manual re-push when auto-restore fails** (Area A; FR-041/FLOW-009/F1): add an AC/clause for a one-action re-assign/re-push of current live state to a recovered or newly-selected output.
3. **Provider retry/backoff + alternate-provider failover** (Area A; FR-135/F4): require bounded retry-with-backoff before dropping to local, and a defined failover order for multi-provider configs.
4. **FR-154 FDE alternative untestable** (Area B; §17/§21): either commit to app-managed encryption (SQLCipher) as the acceptance path, or define per-OS FDE-verification and the app's behaviour when FDE is unconfirmed; make the assumption explicit in §9/§21.
5. **Subjective/unenumerated ACs cluster** (Areas B and C — FR-063 flagged by both): enumerate FR-066 image formats; set an FR-042 dropped-frame threshold; express FR-013 as a millisecond bound; restate NFR-011 as a measurable GPU-idle criterion; and define FR-063's "routed safely" concretely (default-exclude audience/house outputs; audible cue requires explicit per-output selection + confirmation, mirroring FR-062).
6. **Unbounded rejection/suppression windows** (Area B; FR-091/FR-114): state the replay/clock-skew and suppression-cooldown window values (or a defaulted range), or mark them design-time-TBD with the deciding artefact referenced.
7. **Legal/compliance assignability gap** (Area B; FR-158/146/034/140/021/022): designate a legal/compliance reviewer (outside the engineering roster) as the accepting authority, note it in §27 per requirement, and rewrite FR-158's AC to an observable state (exact setting/notice and where it surfaces).
8. **§33 traceability omits NFR-026** (Areas B and D — merged; also NFR-026 out of sequence in the §14 table): reorder the NFR table and correct §33 to "NFR-001…NFR-026" so mobile accessibility is traced to a release.
9. **FR-102 VAD AC bounds the wrong surface** (Area C): reword FR-102's "≤1% of non-speech seconds produce displayed text" to bound the **emitted/committed** transcript the detection (FR-111) and notes (FR-122) pipelines consume, since verbatim display is OFF by default (FR-166).
10. **Dependency-security / supply-chain has no testable requirement** (Area D; threat T16): add an NFR requiring SBOM generation and automated dependency/CVE + license (GPL/AGPL exclusion) scanning in CI with a defined patch cadence.
11. **KJV bundling (OD-24) unresolved** (Area D; FR-025): resolve OD-24 — drop KJV from the FR-025 bundle (register-recommended; WEB/ASV/BSB already satisfy ≥4 translations) or record UK exposure as an explicit accepted-risk decision; if left open, list OD-24 in §28.
12. **Codec safe-harbor omits AAC** (Area D; CON-4/FR-067/068): extend the platform/HW-decode-only constraint to name AAC (and other encumbered audio codecs) alongside H.264/HEVC, and verify in the dependency audit.
13. **Retention default (OD-09) has no value** (Area D; FR-153): set a provisional numeric default (e.g. raw audio purged after N days unless explicitly kept), revisable post-measurement, so FR-153's "conservative default" is testable; keep OD-09 tracked.
14. **No MVP video-smoothness floor** (Area E; FR-067 vs NFR-005): add a modest testable MVP playback floor on Tier A (e.g. single-output 1080p30 or 720p60 with a dropped-frame ceiling) so "best-effort" is not untestable; keep the full 1080p60/<5% guarantee at R2.
15. **METRIC-003 (and METRIC-006) missing from §32 launch criteria** (Area E): add METRIC-003 (12h soak memory stability) explicitly to §32 so the reliability soak is an unambiguous launch gate; back METRIC-006 (time-to-first-slide) with an NFR or add it to §32 if it is meant to gate launch.
16. **FR-083 vacuously satisfiable at MVP** (Area E): reframe FR-083 as a cross-cutting architectural invariant whose meaningful acceptance begins at R3 (when AI subsystems land), or note in §30/§18 that NFR-024 carries the MVP-relevant failure-isolation.

---

## 7. What Must Be Resolved to Reach PASS

To move from **PASS WITH CONDITIONS** to a clean **PASS**, all **17 majors (MAJOR-01 … MAJOR-17)** must be discharged in a PRD revision, then re-checked. Concretely, the PRD revision must:

1. **Close the four recovery gaps** — add MVP requirements for storage exhaustion (MAJOR-01) and a crash-loop breaker/resume-decline control (MAJOR-02); add the R3 transcription capture-device-disconnect FR (MAJOR-03); and reframe the GPU device-loss guarantee to a bounded-recovery target (MAJOR-04).
2. **Make the AI acceptance criteria verifiable** — define the two benchmark corpora and reference them from FR-102/FR-121/METRIC-009 (MAJOR-05); give FR-108 a metric, threshold, and named set (MAJOR-06).
3. **Complete the TTS de-scope in the normative companion docs** — strike the TTS-control capability (PERSONAS §2 → 14 capabilities), correct the §16 count to 14, and de-scope WORKFLOWS A8/B8/F4 + persona TTS routing (MAJOR-07).
4. **Add the audio-feedback guard** — an R3/R4 FR gating transcription/detection during app-emitted room audio (MAJOR-08).
5. **Add the two missing security controls and broaden transport** — malicious-media decode hardening (MAJOR-09), control-message schema validation (MAJOR-10), and TLS coverage extended to preview/transcript/media streams (MAJOR-11).
6. **Add the accessibility minimums** — seizure-safety / reduced-motion (MAJOR-12) and MVP AT accessible names/roles + mobile labels/touch-targets, reconciling the DEC-001 rationale (MAJOR-13).
7. **Add the compliance deliverables** — privacy policy, store data-disclosures, DPA, and cross-border handling as requirements and launch criteria (MAJOR-14).
8. **Firm up scope and performance framing** — strengthen RISK-001 with intra-MVP sequencing + capacity assumption (MAJOR-15); correct §30 to dual-output and risk-register the S4 dependency (MAJOR-16); and spike-gate/mark-provisional NFR-008 with a corrected C-7 discharge (MAJOR-17).

The 16 minors are advisory and should be folded into the same revision but do not block a PASS.

**Sequencing note:** because none of the majors is a blocker, architecture/planning and the Stage-5 ADRs/spikes (S1–S10) may proceed in parallel; the resolutions above must land **before ticket decomposition** so each recovery path, security control, accessibility item, and AI acceptance criterion carries a requirement, a measurable AC, and a test.

---

*End of adjudicated Stage-4 PRD audit.*
