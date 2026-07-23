# SelahCue — Stage 2 Review Condition Dispositions

Date: 2026-07-23 · Owner: Product Manager · Source: [DISCOVERY-REVIEW.md](DISCOVERY-REVIEW.md) (PASS WITH CONDITIONS, 0 blockers, 10 majors, 15 minors)

How each of the 14 tracked conditions is handled at the Stage 2 gate. **Integrity/honesty conditions are resolved now** (Stage-2 package-quality fixes). **Architecture/requirements-shaping conditions are formally deferred** into Stage 3/5 with a recorded recommendation, per the review's own guidance ("resolved or formally deferred with rationale before Stage 3 locks the corresponding requirement area").

| Cond | Finding | Disposition | Where |
|---|---|---|---|
| **C1** | M1 — adjacent-product (Otter/Descript) workflow study not delivered | **RESOLVED** — commissioned a dedicated adjacent-product workflow study | [ADJACENT-TRANSCRIPTION-PRODUCTS.md](ADJACENT-TRANSCRIPTION-PRODUCTS.md) |
| **C2** | M2 — no text-shaping/RTL/Unicode feasibility | **DEFERRED (Stage 5 spike + MVP scope stated)** — recommendation recorded; RTL/complex-script explicitly scoped past MVP | OD-22; FEASIBILITY §10 (new spike S10) |
| **C3** | M3 — inconsistent OBSERVED definition | **RESOLVED** — one package-wide definition; licence-text reads relabelled DOCUMENTED(primary); totals corrected | EVIDENCE-REGISTER §2 taxonomy note + §3 |
| **C4** | M4 — RP-12 unclassified + overclaimed completeness | **RESOLVED** — limitation notes added; persona/workflow behaviours classified INFERRED; "complete" claim softened | PERSONAS.md, WORKFLOWS.md, EVIDENCE-REGISTER §2 RP-12 note, §4 |
| **C5** | M5 — vendor perf figures over-tagged DOCUMENTED/High | **RESOLVED** — re-tagged vendor-claimed/uncorroborated (Low); claim-exists vs claim-true separated | COMPETITOR-MATRIX §2.1 |
| **C6** | M6 — undisclosed sermon-note LLM fabrication mode | **RESOLVED** — fabrication failure-mode section added; auto-extracted refs must verify against local Bible index | CAPABILITY-ASSESSMENT §2.9 |
| **C7** | M7 — auto-display residual wrong-verse risk undisclosed | **RESOLVED** — risk disclosed; corroboration gate required; semantic-only barred; auto-display "strongly discouraged" | CAPABILITY-ASSESSMENT §2.7 |
| **C8** | M8 — GStreamer software decoders undermine codec safe harbor | **DEFERRED (Stage 5 ADR input)** — platform/HW-decode-only build constraint recorded; OD-08 codec item now conditional | OD-08a |
| **C9** | M9 — no at-rest encryption for primary datastore | **DEFERRED (Stage 3 NFR)** — SQLCipher-or-FDE recommendation recorded; three docs to reconcile into one requirement | OD-21 |
| **C10** | M10 — S2 committed with no fallback | **DEFERRED (Stage 5)** — fallback architecture + perf-target gating recommendation recorded | OD-23; FEASIBILITY §9 leaning presupposes S2 |
| **C11** | m1–m5 — reliability/feature/output/accessibility/diarization gaps | **PARTLY RESOLVED + DEFERRED** — diarization limitation added now (CAPABILITY §2.8); rest → Stage 3 requirements backlog | CAPABILITY §2.8; Stage 3 backlog |
| **C12** | m6–m8,m10 — confidence calibration, sourcing, UNKNOWNs section | **PARTLY RESOLVED + DEFERRED** — UNKNOWNs section added now (CAPABILITY §4); citation spot-check + secondary-figure downgrades → Stage 3 | CAPABILITY §4; Stage 3 |
| **C13** | m9 — cloud→local STT fallback overpromised | **RESOLVED** — guarantee rescoped to presentation output; transcription "degrades gracefully" note added | CAPABILITY §4 note |
| **C14** | m11–m15 — iOS multicast entitlement, KJV geo, NDI License-ID, CC BY-SA/SongSelect, mDNS-pinning + MVP-control table | **PARTLY RESOLVED + DEFERRED** — KJV→OD-24, NDI License-ID noted in register; iOS entitlement/SongSelect/mDNS-rationale/MVP-control-table → Stage 3/5 | OD-24; EVIDENCE-REGISTER §3; Stage 3/5 |

## Net position

- **Resolved at the gate (integrity/honesty):** C3, C4, C5, C6, C7, C13, plus the now-portions of C11 and C12, plus C1 (new study).
- **Formally deferred with recorded recommendations (architecture/requirements):** C2, C8, C9, C10, and the backlog portions of C11, C12, C14 — each pre-loaded in [OPEN-DECISIONS.md](OPEN-DECISIONS.md) so Stage 3/5 closes them without re-deriving.
- No condition is dropped; none is a blocker; the discovery package's core conclusions stand unchanged.
