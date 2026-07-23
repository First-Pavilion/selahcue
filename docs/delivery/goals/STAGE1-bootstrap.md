# Goal Contract — STAGE1-bootstrap

## Identity

- Goal ID: STAGE1-bootstrap
- Parent goal ID: BUILD-selahcue
- Title: Establish the verified baseline, Build Control task, Build Goal Contract, research plan, and initial risk register for SelahCue
- Role: build
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-07-23
- Updated: 2026-07-23
- Maximum iterations: 3
- Independent verification required: no

## Objective

Bootstrap the `/build` initiative: document a verified repository/ClickUp/tooling baseline, create the ClickUp Build Control task, create a structurally valid Build Goal Contract, produce a complete product research plan and an initial risk register, and identify material blockers — then stop at the Stage 1 gate.

## Baseline

Greenfield repository (no git, no code, no tests, no infra); only `product/PRODUCT-BRIEF.md` and `.claude/` scaffolding. ClickUp MCP accessible; empty `SelahCue` folder present. See docs/product/audits/BASELINE.md.

## Inputs and evidence sources

- product/PRODUCT-BRIEF.md; .claude/team/*; ClickUp workspace First Pavilion (Engineering)

## Scope

### In scope

- Repo/MCP/ClickUp inspection; Build Control task; Build Goal Contract; verified baseline; research plan; initial risk register; material-unknown identification.

### Non-goals

- Any research execution, PRD, architecture, design, ticket decomposition, or implementation (later stages).

### Constraints

- No ClickUp status/field/list creation beyond the user-approved delivery list; stop at the Stage 1 gate.

### Assumptions and unknowns

- ASSUMED: product name SelahCue (user-confirmed). UNKNOWN: final platform scope + tech stack (later stages).

## Dependencies and approvals

- ClickUp MCP (available). User gate decision (pending).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S1-001 | yes | Repository baseline is documented with verified facts | Read baseline audit | Baseline audit exists and is accurate | docs/product/audits/BASELINE.md | PASS |
| S1-002 | yes | ClickUp Build Control task exists and links contract + pointer | ClickUp task fetch | Task 86ajnx548 present with links | https://app.clickup.com/t/86ajnx548 | PASS |
| S1-003 | yes | Build Goal Contract passes structural validation | validate_goal_contract.py | Exit 0, VALIDATION: PASS | scripts/validate_goal_contract.py output | PASS |
| S1-004 | yes | Product research plan is complete | Review research plan | All brief research areas covered as tasks | docs/research/RESEARCH-PLAN.md | PASS |
| S1-005 | yes | Initial risk register exists with material risks | Review risk register | >=1 risk per major domain, owners assigned | docs/delivery/RISK-REGISTER.md | PASS |
| S1-006 | yes | Material blockers/unknowns identified | Review gate report | Blockers + unknowns listed | Stage 1 gate report + RISK-REGISTER | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: run `python3 scripts/validate_goal_contract.py` against BUILD and STAGE1 contracts; confirm ClickUp task via fetch.
- Independent verifier: none required for bootstrap; user gate review is the check.
- Required environment: local repo + ClickUp MCP.

## Iteration ledger

### Iteration 1

- Target criterion: S1-001..S1-006.
- Hypothesis: producing baseline + contracts + plan + register + Build Control task satisfies Stage 1.
- Change or investigation: inspected repo/MCP/ClickUp; created list, Build Control task, BUILD + STAGE1 contracts, validator, baseline, research plan, risk register, BUILD_STATE.
- Verifier executed: validate_goal_contract.py (both contracts).
- Result: PASS (see gate report).
- New evidence: files listed above; ClickUp 86ajnx548.
- Decision: gate-review.

## Risks and rollback

- Risks: missing PM artifact validator (RISK-006). Rollback: none needed (additive artefacts).

## Pause and escalation conditions

- Pause/abort on user instruction at gate.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/STAGE1-bootstrap.md`
- Validator result: PENDING run
- Independent verification result: N/A (user gate)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: to be posted on 86ajnx548
