# Goal Contract — STAGE3-prd

## Identity

- Goal ID: STAGE3-prd
- Parent goal ID: BUILD-selahcue
- Title: Produce the complete, testable SelahCue PRD with stable requirement IDs, MVP/later boundaries, and traceability, passing the PM artifact validator and an independent multi-lens review
- Role: product-manager
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-07-23
- Updated: 2026-07-23
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Convert the approved discovery package into a complete Product Requirements Document for SelahCue with stable requirement identifiers (FR/NFR/FLOW/RISK/METRIC), measurable and testable acceptance criteria, a coherent MVP-vs-later boundary (TTS a non-goal per DEC-001), all mandatory PRD sections, and a requirement→release traceability structure — verified by a new PM artifact validator and an independent fresh-context review.

## Baseline

Stage 2 discovery complete (PASS WITH CONDITIONS, 0 blockers). No PRD, requirement IDs, or PM artifact validator exist yet (RISK-006). TTS de-scoped (DEC-001). Deferred conditions C2/C8/C9/C10/C14 must be carried into requirements.

## Inputs and evidence sources

- docs/research/* (discovery), docs/business/* (personas/workflows), docs/security/reviews/threat-model-draft.md
- docs/research/OPEN-DECISIONS.md, CONDITION-DISPOSITIONS.md, docs/decisions/DECISION-LOG.md
- product/PRODUCT-BRIEF.md (required PRD outputs list)

## Scope

### In scope

- Complete PRD (all brief-mandated sections); stable IDs; testable acceptance criteria; MVP/later/non-goals; permissions; data lifecycle; AI/provider; offline; reliability; performance; security; privacy; accessibility; licensing; user journeys; risks; metrics; dependencies; open questions; launch criteria; traceability.
- PM artifact validator (scripts/validate_prd.py).

### Non-goals

- Independent PRD audit (Stage 4 — separate fresh-context agent).
- Architecture/ADRs (Stage 5), ClickUp tickets (Stage 6), implementation (Stage 7+).
- TTS requirements (non-goal, DEC-001).

### Constraints

- Requirements must be testable and traceable; MVP must be realistically bounded (RISK-001).
- Carry deferred Stage-2 conditions into requirements; treat licensed translations/cloud AI as later-release; PD Bibles + OS-native codecs for MVP.

### Assumptions and unknowns

- ASSUMED MVP boundary: presentation foundation (desktop tri-platform + thin mobile controller), per OD-01/03. Owner: user (accepted at Stage 2 gate).
- UNKNOWN: final performance-target ratification (Stage 5), legal confirmations (later features).

## Dependencies and approvals

- Stage 2 gate approved (yes). PM artifact validator (to be built this stage). User gate decision (pending).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S3-001 | yes | All mandatory PRD sections exist | validate_prd.py section check | Validator: all 32 required sections present | scripts/validate_prd.py output (PASS) | PASS |
| S3-002 | yes | Every requirement has a stable unique ID (FR/NFR/FLOW/RISK/METRIC) | validate_prd.py ID check | No duplicate/malformed IDs (168 FR, 26 NFR, 10 FLOW, 13 RISK, 10 METRIC) | validator output | PASS |
| S3-003 | yes | Every FR/NFR has a priority (MVP/Rn) and measurable acceptance criteria | validate_prd.py row check | 194 requirement rows each with non-empty Priority + Acceptance | validator output | PASS |
| S3-004 | yes | MVP vs later releases vs non-goals clearly separated; TTS is a non-goal | Review + validator | MVP/R2-R6/Non-goals sections present; TTS = NG-1 | PRD §30/§31/§6 | PASS |
| S3-005 | yes | Permissions, data lifecycle, AI/provider, offline, security, privacy, accessibility, reliability, performance, licensing all specified | validate_prd.py section check | All sections present with requirements | PRD §16-§25 | PASS |
| S3-006 | yes | Known risks and dependencies represented; deferred Stage-2 conditions carried | Review | RISK-* §26 + deferred conditions C2/C8/C9/C10/C14 mapped §28 | PRD §26/§27/§28 | PASS |
| S3-007 | yes | Traceability structure maps requirements to release + source | validate_prd.py traceability check | Every FR appears in traceability + exactly one release | PRD §33 | PASS |
| S3-008 | yes | PM artifact validator succeeds | `python3 scripts/validate_prd.py <prd>` | Exit 0 (PASS) | validator output | PASS |
| S3-009 | yes | Independent fresh-context PRD review (pre-Stage-4) passes | Review workflow (4 lenses) | PASS WITH CONDITIONS (0 blockers); all 10 majors + 12 minors discharged in PRD §34 | docs/product/audits/PRD-REVIEW-stage3.md; PRD §34 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: run validate_prd.py against the PRD.
- Independent verifier: fresh-context multi-lens review (testability/completeness, MVP coherence, security/privacy/licensing, accessibility/reliability/performance/traceability). Note: Stage 4 is the formal independent PRD audit; this Stage-3 review is a pre-audit quality gate.
- Environment: repo.

## Iteration ledger

### Iteration 1

- Target: S3-001..S3-009.
- Hypothesis: authoring a complete table-structured PRD + a real PM validator + independent review satisfies the predicate.
- Change: build validate_prd.py; author PRD; run validator; independent review; remediate.
- Verifier executed: pending.
- Result: pending.
- Decision: iterate → gate-review.

## Risks and rollback

- Risks: oversized MVP (RISK-001) → validator + review check MVP coherence. Rollback: additive under git.

## Pause and escalation conditions

- Pause/abort on user gate instruction. Escalate any feasibility conflict surfaced while writing requirements.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/STAGE3-prd.md` and `python3 scripts/validate_prd.py docs/product/prds/SelahCue-PRD.md`
- Validator result: PASS (contract structural PASS; PRD validator exit 0)
- Independent verification result: PASS WITH CONDITIONS (0 blockers, 10 majors, 12 minors) — all discharged in PRD §34
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ajnx548
