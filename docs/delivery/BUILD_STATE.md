# SelahCue — Build State

Lightweight pointer only. ClickUp is the delivery source of truth. Do not duplicate the backlog here.

- Product: **SelahCue** (cross-platform church presentation & ministry-assistance app)
- Build Control task: https://app.clickup.com/t/86ajnx548 (`86ajnx548`)
- ClickUp delivery list: `SelahCue — Delivery` (`901327960792`) in folder `SelahCue` (`901318653689`), space `First Pavilion (Engineering)` (`90136583508`)
- Build Goal Contract: `docs/delivery/goals/BUILD-selahcue.md`
- Current stage: **Stage 2 — Product discovery and research** (just started, then PAUSED)
- Stage state: `PAUSED` (user paused 2026-07-23 at the very start of Stage 2)
- Last approved gate: Gate 1 (Stage 1) — user replied `continue`, authorising Stage 2
- Execution engine: `goal`

## Paused position (2026-07-23)

Stage 1 passed its gate; user approved Stage 2 with `continue`, then immediately sent `pause`.
No Stage 2 research has been executed. The only Stage 2 action completed was `git init` + a baseline commit (`d38f6d3`) so the Stage 1 artefacts are version-controlled.
Nothing is in-flight; no subagents were dispatched. Resume by re-entering Stage 2: write the Stage 2 Goal Contract and dispatch the research specialists per `docs/research/RESEARCH-PLAN.md`.

## Key artefacts

- Baseline audit: `docs/product/audits/BASELINE.md`
- Research plan: `docs/research/RESEARCH-PLAN.md`
- Risk register: `docs/delivery/RISK-REGISTER.md`
- Goal Contract validator: `scripts/validate_goal_contract.py`
- Stage 1 Goal Contract: `docs/delivery/goals/STAGE1-bootstrap.md`

## Recovery note

Greenfield build; not yet under git version control (RISK-011). To resume, read the Build Control task and this file, validate the BUILD + active STAGE contracts, then resume at the last unapproved gate (currently the Stage 1 gate).
