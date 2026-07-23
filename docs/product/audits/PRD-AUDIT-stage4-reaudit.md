# SelahCue PRD v1.1 — Stage-4 RE-AUDIT (Lead Auditor Adjudication)

- **Document audited:** `docs/product/prds/SelahCue-PRD.md` (PRD v1.1)
- **Scope:** Re-audit of all 17 Stage-4 majors (MAJOR-01 … MAJOR-17)
- **Date:** 2026-07-23
- **Inputs:** Three independent verifier reports (groups: 01/02/03/04/15/16/17; 05/06/07/08; 09/10/11/12/13/14)
- **Adjudication method:** Verifier findings reconciled against the live PRD and its normatively-cited companion docs (`PERSONAS.md`, `WORKFLOWS.md`, `threat-model-draft.md`, `DECISION-LOG.md`, `LICENSING-REGISTER.md`), with independent spot-checks of every new/changed requirement.

## Independence statement

This adjudication was performed with fresh context. The lead auditor did **not** author the SelahCue PRD, did not author the original Stage-4 audit (`PRD-AUDIT-stage4.md`), and did not author any of the three verifier reports. Each discharge claim below was independently corroborated against the primary source (PRD line references given by the verifiers were re-read directly), rather than accepted on the strength of the verifier assertion alone.

## Final verdict: **PASS**

All 17 majors are **discharged**. No verifier reported a new blocker or a new major regression; every new finding is a **minor**, non-normative completeness/traceability item. Under the decision rule (PASS iff all 17 discharged AND no new blocker/major regression), this is a **PASS**. The five minor findings below are recorded as **non-blocking** recommended follow-ups; none is launch-gating and none reopens a major.

- Majors discharged: **17 / 17**
- New blockers: **0**
- New major regressions: **0**
- New minors (advisory): **5**

## Per-major discharge status

| Major | Title (finding) | Status | Primary evidence (verified) |
|-------|-----------------|--------|-----------------------------|
| MAJOR-01 | Storage-exhaustion detection & graceful degradation | Discharged | New **FR-169** (MVP, EPIC-R) pre-write low-disk detection + reserved checkpoint headroom + graceful/never-silent degradation; NFR-024 lists `storage-exhaustion`; in §30 scope, §32 launch criteria, §33 MVP trace. |
| MAJOR-02 | Crash-loop breaker | Discharged | **FR-075** AC now carries the verbatim crash-loop-breaker clause (after N rapid crashes: offer Resume vs Start-clean/skip, disable offending item; no silent auto-resume). §32 launch criteria include it. No reliance on R2 safe-mode. |
| MAJOR-03 | Transcription capture-device disconnect | Discharged | New **FR-170** (R3): pause-not-crash, segments preserved, gap marker on reconnect, resume, slide control unaffected. Matches WORKFLOWS F2; distinct from FR-161 (audio output). |
| MAJOR-04 | GPU device-loss reframed | Discharged | **FR-160** + **NFR-024** split per-output decoder failure (SW-fallback) vs whole-device GPU/TDR loss (bounded ≤3s recovery, hold-last-frame, no rebuild); physically-infeasible "never blanks" absolute bar removed for whole-device loss. |
| MAJOR-05 | AI benchmark corpora undefined | Discharged | New **FR-171** (R3) defines eval-set artefact (composition/source/size/scoring); FR-102/108/121 reference it by name. FR-102 surface ambiguity also resolved (committed vs verbatim-OFF). |
| MAJOR-06 | FR-108 untestable | Discharged | **FR-108** now: per-term WER metric, ≥20% relative improvement, A/B vs no glossary, on the named FR-171 set. All four required elements present and testable. |
| MAJOR-07 | Live TTS capability removal | Discharged | PERSONAS §2 matrix = exactly **14** capability rows, no TTS-control row; §16 corrected to "7×14 … removed per DEC-001"; WORKFLOWS A8/B8/F4 marked DE-SCOPED. No buildable TTS capability/flow remains. (Residual descriptive TTS prose → minor #4.) |
| MAJOR-08 | Audio-feedback / self-re-transcription | Discharged | New **FR-172** (R3): while app audio (FR-063/068/069) routes to shared output, ingestion suppressed + detection firing gated + operator warned + mic-source guidance. Promotes CAPABILITY-ASSESSMENT §1.2/1.3 to normative. |
| MAJOR-09 | Untrusted-media/font decode hardening | Discharged | New **FR-173** (MVP): safe/maintained decoders, header/type/size validation before decode, sandbox where feasible, patch cadence (deep fuzzing → Stage-13). Trace T12 verified (High). |
| MAJOR-10 | Control-message schema validation | Discharged | New **FR-174** (MVP): strict schema/type/size/range validation, reject unknown/oversized, fail-safe keep-last-good, fuzz/fault-injection AC. Trace T20 verified. |
| MAJOR-11 | LAN transport scope too narrow | Discharged | **FR-088** + **NFR-016** broadened from control-only to control + previews + transcript/caption + media; TLS 1.3 + pinned cert; no plaintext preview/transcript egress AC. Trace T2/T3 verified. |
| MAJOR-12 | Seizure-safety / photosensitivity | Discharged | New **FR-175** (MVP): ≤3 flashes/sec (WCAG 2.3.1) + reduced-motion. **NFR-020** over-claim corrected (AA scoped to contrast; flash safety = FR-175). §32 adds seizure-safety verification. |
| MAJOR-13 | MVP assistive-tech minimums | Discharged | **NFR-021** (core desktop controls: accessible names/roles) and **NFR-026** (mobile: labels + ≥44×44pt) pulled to MVP; §22 reconciles DEC-001 compensating-path claim (present in MVP, not deferred). |
| MAJOR-14 | Compliance deliverables | Discharged | New **FR-176** (MVP: privacy policy in-product + store; App Privacy + Data Safety) and **FR-177** (R3: DPA + cross-border gating cloud opt-in); FR-132 specifics added; §32 gated; §27 assigns accepting authority. Traces LICENSING §4/§5 verified. |
| MAJOR-15 | Scope-vs-capacity sequencing | Discharged | **RISK-001** adds intra-MVP sequencing (presentation-core desktop before mobile control-plane slice); new **AS-6** records the capacity assumption. (Qualitative, not headcount — audit asked only to record it.) |
| MAJOR-16 | MVP dual-output correction | Discharged | §30 corrected to two concurrent independent outputs; new **RISK-014** gates FR-040/041 on spike S4 with borderless-per-monitor fallback (best-effort until S4 passes); RISK-014 in §33. |
| MAJOR-17 | NFR-008 spike-gate parity | Discharged | **NFR-008** now "≤1.5s incremental … (INFERRED-Low; spike-gated S8; provisional pending Stage-5/10 measurement)"; §34 C-7 updated. Parity with NFR-007/METRIC-009 restored. |

## New findings (all MINOR — non-blocking)

| # | Severity | Area | Issue | Suggested fix |
|---|----------|------|-------|---------------|
| 1 | Minor | §23 Reliability prose | Summary still cites only "storage warnings + safe mode (FR-081)" (an R2 item) and omits the new MVP FR-169 and the FR-075 crash-loop-breaker. Confirmed: PRD line 439 contains no FR-169. Non-normative; the normative rows in §30/§32/§33 are correct. | Add FR-169 + crash-loop-breaker to the §23 enumeration. |
| 2 | Minor | Spike register | FR-171 (line 361) points its deliverable at "spike **S11**", but the spike register is S1–S10 only (§27 line 470); S11 is unregistered. | Register S11 in §27 (or repoint FR-171 at an existing spike) so the eval-corpus deliverable has an owning spike. |
| 3 | Minor | Cross-reference truthfulness | FR-171's AC asserts "FR-102/FR-108/FR-121/**METRIC-009** reference it by name", but METRIC-009 (line 506) says only "on the explicit-reference test set" and does not literally cite FR-171. FR-102/108/121 do name it. | Add the FR-171 citation to METRIC-009, or drop the METRIC-009 claim from FR-171's AC. |
| 4 | Minor | TTS cleanup in companion docs | Residual descriptive TTS prose contradicts NG-1/DEC-001: PERSONAS lines 6 & 22 list TTS as a live feature/provider; WORKFLOWS line 22 (Governing Principle #3) and line 302 (bottom-line) list TTS as layered assistance. No buildable capability/flow — MAJOR-07's testable core stands — but they should be struck for a clean TTS-free pass. | Strike the residual TTS mentions from PERSONAS header/provider lines and WORKFLOWS principle/summary. |
| 5 | Minor | §20/§21 summary completeness | §20 Security control list omits the two new MVP controls FR-173 (decode hardening) and FR-174 (control-message validation); §21 Privacy control list omits FR-176/FR-177. §31's R2 "screen-reader" line would read more clearly as "full screen-reader coverage" (already disambiguated by NFR-021/§22). Normative rows exist and are testable — prose/traceability polish only. | Add FR-173/174 to §20 and FR-176/177 to §21; reword §31 R2 line. |

## Verification note

Independent re-reads confirmed the existence and wording of FR-169 through FR-177, the FR-075 crash-loop clause, the NFR-024 storage-exhaustion + GPU-device-loss language, the FR-160 per-output/whole-device split, the NFR-008 spike-gate annotation, RISK-014 and AS-6, the FR-088/NFR-016 transport broadening, the NFR-021/NFR-026 MVP pull, the 14-row PERSONAS capability matrix (no TTS-control row) with §16's "14 capabilities" correction, and threat-model entries T12 and T20. Each of the five minor findings was reproduced against source. No claimed discharge failed corroboration.

## Disposition

**PASS.** The PRD may proceed. The five minor findings are recommended for a documentation-hygiene sweep at the next convenient revision; they do not gate launch and do not reopen any major. Recommend the §32 launch checklist retain its existing gates (crash-loop-breaker, storage-exhaustion, seizure-safety, privacy-policy/store-disclosure) as already written.
