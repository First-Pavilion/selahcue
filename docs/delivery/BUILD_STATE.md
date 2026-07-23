# SelahCue — Build State

Lightweight pointer only. ClickUp is the delivery source of truth. Do not duplicate the backlog here.

- Product: **SelahCue** (cross-platform church presentation & ministry-assistance app)
- Build Control task: https://app.clickup.com/t/86ajnx548 (`86ajnx548`)
- ClickUp delivery list: `SelahCue — Delivery` (`901327960792`) in folder `SelahCue` (`901318653689`), space `First Pavilion (Engineering)` (`90136583508`)
- Build Goal Contract: `docs/delivery/goals/BUILD-selahcue.md`
- Current stage: **Stage 2 — Product discovery and research** (complete, at gate)
- Stage state: `GATE_REVIEW` (awaiting user gate decision)
- Last approved gate: Gate 1 (Stage 1) — user replied `continue`, authorising Stage 2
- Execution engine: `goal`
- Execution model: **Opus 4.8 (1M context)** — Stage 2+ runs under the current session model.

## Stage 2 outcome (2026-07-23)

Discovery complete. 6 parallel research specialists + a 4-lens independent review workflow (PASS WITH CONDITIONS, 0 blockers) + a follow-up adjacent-product study (condition C1). Integrity conditions resolved; architecture conditions formally deferred with recorded recommendations. Artefacts in docs/research/, docs/business/, docs/security/reviews/. Awaiting Stage 2 gate decision.

Key Stage 2 artefacts: DISCOVERY-REPORT.md, EVIDENCE-REGISTER.md, OPEN-DECISIONS.md, DISCOVERY-REVIEW.md, CONDITION-DISPOSITIONS.md (all under docs/research/); Stage 2 contract docs/delivery/goals/STAGE2-discovery.md.

**Refine (2026-07-23):** user de-scoped **TTS** entirely — removed from roadmap ([DEC-001](../decisions/DECISION-LOG.md)). Discovery artefacts, OPEN-DECISIONS OD-02, risk register RISK-008, and Build Goal Contract non-goals updated. Stage 2 remains at GATE_REVIEW.

## Key artefacts

- Baseline audit: `docs/product/audits/BASELINE.md`
- Research plan: `docs/research/RESEARCH-PLAN.md`
- Risk register: `docs/delivery/RISK-REGISTER.md`
- Goal Contract validator: `scripts/validate_goal_contract.py`
- Stage 1 Goal Contract: `docs/delivery/goals/STAGE1-bootstrap.md`

## Recovery note

Greenfield build; not yet under git version control (RISK-011). To resume, read the Build Control task and this file, validate the BUILD + active STAGE contracts, then resume at the last unapproved gate (currently the Stage 1 gate).
