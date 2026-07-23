# SelahCue — Build State

Lightweight pointer only. ClickUp is the delivery source of truth. Do not duplicate the backlog here.

- Product: **SelahCue** (cross-platform church presentation & ministry-assistance app)
- Build Control task: https://app.clickup.com/t/86ajnx548 (`86ajnx548`)
- ClickUp delivery list: `SelahCue — Delivery` (`901327960792`) in folder `SelahCue` (`901318653689`), space `First Pavilion (Engineering)` (`90136583508`)
- Build Goal Contract: `docs/delivery/goals/BUILD-selahcue.md`
- Current stage: **Stage 1 — Bootstrap and verified baseline**
- Stage state: `GATE_REVIEW` (awaiting user gate decision)
- Last approved gate: none yet (Stage 1 is the first gate)
- Execution engine: `goal`

## Key artefacts

- Baseline audit: `docs/product/audits/BASELINE.md`
- Research plan: `docs/research/RESEARCH-PLAN.md`
- Risk register: `docs/delivery/RISK-REGISTER.md`
- Goal Contract validator: `scripts/validate_goal_contract.py`
- Stage 1 Goal Contract: `docs/delivery/goals/STAGE1-bootstrap.md`

## Recovery note

Greenfield build; not yet under git version control (RISK-011). To resume, read the Build Control task and this file, validate the BUILD + active STAGE contracts, then resume at the last unapproved gate (currently the Stage 1 gate).
