# Goal Contract — STAGE4-audit

## Identity

- Goal ID: STAGE4-audit
- Parent goal ID: BUILD-selahcue
- Title: Obtain an exactly-PASS verdict from a fresh-context independent PRD audit; resolve all blocker/major findings and re-audit
- Role: product-manager (remediation) + independent auditor (verification)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-07-23
- Updated: 2026-07-23
- Maximum iterations: 4
- Independent verification required: yes (this stage IS the independent verification)

## Objective

Have a fresh-context auditor (that did not author the PRD) audit `docs/product/prds/SelahCue-PRD.md` against the brief's audit checklist, and drive the verdict to exactly **PASS** by resolving every blocker and major finding and re-auditing. Architecture (Stage 5) and ClickUp planning (Stage 6) may not begin until the verdict is PASS.

## Baseline

PRD v1.0 exists and passes the PM artifact validator. A Stage-3 pre-audit review (PASS WITH CONDITIONS, 0 blockers) already discharged 10 majors + 12 minors. No formal independent audit has run.

## Inputs and evidence sources

- docs/product/prds/SelahCue-PRD.md; product/PRODUCT-BRIEF.md (audit checklist); docs/research/*; docs/business/*; docs/security/reviews/threat-model-draft.md; docs/decisions/DECISION-LOG.md

## Scope

### In scope

- Independent audit for: missing workflows, missing failure states, ambiguous requirements, untestable acceptance criteria, hidden assumptions, unrealistic AI expectations, missing operator controls, privacy/licensing/security/accessibility gaps, performance risks, offline limitations, recovery weaknesses, audio-feedback risks, oversized release scope, requirements not assignable to a specialist. Confirm TTS de-scope is clean.
- Remediation of blocker/major findings; PRD update; re-audit to PASS.

### Non-goals

- Architecture/ADRs (Stage 5), ClickUp tickets (Stage 6), implementation.

### Constraints

- Auditor must be fresh-context (did not author the PRD) and must not rubber-stamp.
- Verdict must be exactly one of FAIL / PASS WITH CONDITIONS / PASS. Only PASS satisfies the predicate.

### Assumptions and unknowns

- ASSUMED: Stage-3 discharge reduced major findings; the formal audit may still find issues requiring remediation.

## Dependencies and approvals

- Stage 3 gate approved (yes). User gate decision at Stage 4 (pending).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S4-001 | yes | Fresh-context independent audit executed against the brief checklist | Audit workflow | Audit report produced with a verdict | docs/product/audits/PRD-AUDIT-stage4.md | PENDING |
| S4-002 | yes | Every blocker and major finding resolved and re-audited | Remediation + re-audit | No open blocker/major findings | audit report (final round) | PENDING |
| S4-003 | yes | Final audit verdict is exactly PASS | Audit adjudication | Verdict == PASS | audit report | PENDING |
| S4-004 | yes | PRD still passes the PM artifact validator after remediation | validate_prd.py | Exit 0 | validator output | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Independent verifier: fresh-context audit panel (5 auditors across the checklist slices + adjudicator), none authored the PRD.
- Focused: re-run validate_prd.py after each remediation round.
- Bounded: max 4 audit/remediation rounds; if not PASS by then, report FAILED_LIMIT with the smallest blocker.

## Iteration ledger

### Iteration 1

- Target: S4-001..S4-004.
- Hypothesis: a rigorous fresh-context audit + remediation of blocker/major findings reaches exactly PASS.
- Change: run audit workflow; remediate; re-audit until PASS.
- Verifier executed: pending.
- Result: pending.
- Decision: iterate → gate-review.

## Risks and rollback

- Risks: audit finds a structural scope problem requiring escalation (→ scope-change to user at gate). Rollback: additive under git.

## Pause and escalation conditions

- Escalate to user at the gate if a finding requires a scope/requirement change beyond documented engineering judgement.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/STAGE4-audit.md` + `python3 scripts/validate_prd.py docs/product/prds/SelahCue-PRD.md`
- Validator result: PENDING
- Independent verification result: PENDING
- Terminal state: IN_PROGRESS → GATE_REVIEW
- Remaining failed or blocked criteria: all PENDING
- ClickUp final evidence comment: PENDING
