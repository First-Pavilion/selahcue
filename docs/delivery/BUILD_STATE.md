# SelahCue — Build State

Lightweight pointer only. ClickUp is the delivery source of truth. Do not duplicate the backlog here.

- Product: **SelahCue** (cross-platform church presentation & ministry-assistance app)
- Build Control task: https://app.clickup.com/t/86ajnx548 (`86ajnx548`)
- ClickUp delivery list: `SelahCue — Delivery` (`901327960792`) in folder `SelahCue` (`901318653689`), space `First Pavilion (Engineering)` (`90136583508`)
- Build Goal Contract: `docs/delivery/goals/BUILD-selahcue.md`
- Current stage: **Stage 5 — Architecture & UX design** (complete, at gate)
- Stage state: `GATE_REVIEW` (awaiting user gate decision)
- Last approved gate: Gate 4 (Stage 4) — user replied `continue`, authorising Stage 5 (then `refine`: add Figma designs)
- Execution engine: `goal`
- Execution model: **Opus 4.8 (1M context)** — Stage 2+ runs under the current session model.

## Stage 2 outcome (2026-07-23)

Discovery complete. 6 parallel research specialists + a 4-lens independent review workflow (PASS WITH CONDITIONS, 0 blockers) + a follow-up adjacent-product study (condition C1). Integrity conditions resolved; architecture conditions formally deferred with recorded recommendations. Artefacts in docs/research/, docs/business/, docs/security/reviews/. Awaiting Stage 2 gate decision.

Key Stage 2 artefacts: DISCOVERY-REPORT.md, EVIDENCE-REGISTER.md, OPEN-DECISIONS.md, DISCOVERY-REVIEW.md, CONDITION-DISPOSITIONS.md (all under docs/research/); Stage 2 contract docs/delivery/goals/STAGE2-discovery.md.

**Refine (2026-07-23):** user de-scoped **TTS** entirely — removed from roadmap ([DEC-001](../decisions/DECISION-LOG.md)). Discovery artefacts, OPEN-DECISIONS OD-02, risk register RISK-008, and Build Goal Contract non-goals updated.

## Stage 3 outcome (2026-07-23)

PRD authored: `docs/product/prds/SelahCue-PRD.md` — 168 FR + 26 NFR + 10 FLOW + 13 RISK + 10 METRIC, all sections, testable acceptance criteria, MVP/R2-R6/non-goal boundary, full traceability. PM artifact validator `scripts/validate_prd.py` built (closes RISK-006) and passes. Independent 4-lens pre-audit review (`docs/product/audits/PRD-REVIEW-stage3.md`): PASS WITH CONDITIONS, 0 blockers; all 10 majors + 12 minors discharged (PRD §34).

## Stage 4 outcome (2026-07-23)

Formal 5-auditor independent PRD audit (`docs/product/audits/PRD-AUDIT-stage4.md`): PASS WITH CONDITIONS, **0 blockers**, 17 majors, 16 minors. All 17 majors discharged (PRD §35, adding FR-169…FR-177, NFR-026/027, RISK-014, AS-6) + material minors. Fresh-context re-audit (`docs/product/audits/PRD-AUDIT-stage4-reaudit.md`): **verdict PASS**, 17/17 discharged, 0 regressions; 5 advisory doc-hygiene minors also folded in. PRD now 177 FR + 27 NFR; validator passes. **PRD has cleared its mandatory independent audit.** Stakeholder report added: `docs/stakeholder/SelahCue-Build-Report.pdf`.

## Stage 5 outcome (2026-07-23)

Architecture spine (`docs/architecture/ARCHITECTURE.md`) + **16 ADRs** (`docs/architecture/adr/`) + UX (`docs/design/`: UX-FLOWS 12 flows, UX-STATE-MATRIX, COMPONENT-SPECS, UX-CANONICAL). Independent 5-lens review: **FAIL** (2 blockers, 12 majors) → remediated (added ADR-0015 testable engine, ADR-0016 decode sandbox, UX-CANONICAL) → re-review **PASS WITH CONDITIONS** (both blockers cleared, 12/14 majors) → remaining M2/M11/NM-1/NM-3 closed. **Figma designs** added to file `SYQn5hFY8YVQKm3c6rw0eJ` (user refine, expanded to full app): **19 frames** — Operator Console, Mobile Controller, Stage/Confidence output, TIME UP output, Design Tokens, Scripture (search & present), Presentation/Slide Editor, Theme/Template Designer, Song/Lyrics Editor, Media & Library, Service Plan builder, Settings (AI & providers), Add Bible (translation import), Displays & Outputs, Devices & Roles (pairing + RBAC), Pre-service Checks, Transcription/STT, Scripture Detection queue, Sermon Notes. PRD validator passes. Awaiting Stage 5 gate. Next: **Stage 6 — ClickUp delivery planning** (gate to begin implementation).

## Key artefacts

- Baseline audit: `docs/product/audits/BASELINE.md`
- Research plan: `docs/research/RESEARCH-PLAN.md`
- Risk register: `docs/delivery/RISK-REGISTER.md`
- Goal Contract validator: `scripts/validate_goal_contract.py`
- Stage 1 Goal Contract: `docs/delivery/goals/STAGE1-bootstrap.md`

## Recovery note

Greenfield build; not yet under git version control (RISK-011). To resume, read the Build Control task and this file, validate the BUILD + active STAGE contracts, then resume at the last unapproved gate (currently the Stage 1 gate).
