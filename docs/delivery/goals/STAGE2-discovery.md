# Goal Contract — STAGE2-discovery

## Identity

- Goal ID: STAGE2-discovery
- Parent goal ID: BUILD-selahcue
- Title: Complete SelahCue product discovery & research — classified evidence register, personas/permissions/workflows, provider & licensing trade-offs, early threat model, and open product decisions, passing independent review
- Role: product-manager
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-07-23
- Updated: 2026-07-23
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Execute the RESEARCH-PLAN (RP-01…RP-13) to produce a complete, evidence-classified discovery package for SelahCue: reference-product & adjacent-tool findings, realistic AI/transcription/scripture-detection/TTS capability assessment, cross-platform/offline/performance feasibility, licensing & compliance register, early security/privacy threat model, personas + permission matrix + normal/alternate/failure workflows, and an open-decisions list — then pass an independent discovery review before the Stage 2 gate.

## Baseline

Greenfield; only the Stage 1 baseline, research plan, and risk register exist. No research executed yet (build was paused at Stage 2 start, now resumed on Opus 4.8 1M). No Bible/provider/licensing decisions made.

## Inputs and evidence sources

- product/PRODUCT-BRIEF.md; docs/research/RESEARCH-PLAN.md; docs/delivery/RISK-REGISTER.md
- WebSearch / WebFetch (public docs, model cards, license texts, product videos/pages). Chrome MCP not confirmed (RISK-007).

## Scope

### In scope

- All RP-01…RP-13 research areas; classification of every finding as OBSERVED/DOCUMENTED/INFERRED/UNKNOWN with source URL, access date, limitation, confidence.
- Personas, roles, permission matrix, jobs-to-be-done, normal/alternate/failure-recovery workflows.
- Realistic capability assessment for AI/transcription/detection/TTS (no perfect-accuracy claims).
- Licensing/compliance register; early threat model; open-decisions list.

### Non-goals

- Writing the PRD or assigning requirement IDs (Stage 3).
- Choosing the final technology stack (Stage 5 ADRs) — only feasibility evidence and trade-offs.
- Any implementation or ClickUp ticket decomposition.

### Constraints

- No copying of proprietary code/assets/branding/interfaces. Inaccessible proprietary internals → UNKNOWN.
- Every capability claim evidence-backed; document limitations honestly.

### Assumptions and unknowns

- ASSUMED: full platform scope (Win/macOS/Linux + Android/iOS/iPadOS) pending Stage 3 bounding.
- UNKNOWN: licensable translations, provider costs/quality, offline transcription performance on target hardware.

## Dependencies and approvals

- WebSearch/WebFetch availability (available). User answers to open product decisions (collected at gate).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S2-001 | yes | Reference-product & adjacent-tool research complete and classified | Review EVIDENCE-REGISTER + COMPETITOR-MATRIX | RP-01/02/13 covered; findings classified with sources | docs/research/COMPETITOR-MATRIX.md, EVIDENCE-REGISTER.md, ADJACENT-TRANSCRIPTION-PRODUCTS.md | PASS |
| S2-002 | yes | Realistic AI/transcription/scripture-detection/TTS capability & provider trade-offs documented | Review PROVIDER-TRADEOFFS + CAPABILITY-ASSESSMENT | RP-03/04/05/06 covered; limitations stated; no perfect-accuracy claims | docs/research/PROVIDER-TRADEOFFS.md, CAPABILITY-ASSESSMENT.md | PASS |
| S2-003 | yes | Licensing & compliance register complete | Review LICENSING-REGISTER | RP-07/11 covered; bundlable vs user-supplied vs API classified | docs/research/LICENSING-REGISTER.md | PASS |
| S2-004 | yes | Cross-platform/offline/performance feasibility documented with proposed targets | Review FEASIBILITY report | RP-08/09 covered; tech options + trade-offs; measurable target proposals | docs/research/FEASIBILITY.md | PASS |
| S2-005 | yes | Early security/privacy threat model documented | Review threat-model-draft | RP-10 covered; assets, threats, controls, privacy requirements | docs/security/reviews/threat-model-draft.md | PASS |
| S2-006 | yes | Personas, permission matrix, and normal/alternate/failure workflows documented | Review PERSONAS + WORKFLOWS | RP-12 covered (un-validated domain modelling, labelled); 11 roles; permission matrix; failure-recovery flows | docs/business/PERSONAS.md, WORKFLOWS.md | PASS |
| S2-007 | yes | Findings correctly classified OBSERVED/DOCUMENTED/INFERRED/UNKNOWN with evidence | Register spot-check | Every finding has classification + source/limitation/confidence | docs/research/EVIDENCE-REGISTER.md | PASS |
| S2-008 | yes | Material unknowns & open product decisions documented with owners | Review OPEN-DECISIONS | Unresolved decisions listed with recommended options | docs/research/OPEN-DECISIONS.md | PASS |
| S2-009 | yes | Discovery report passes independent review (fresh context) | Independent reviewer agent (4-lens workflow) | Verdict PASS WITH CONDITIONS (0 blockers); integrity conditions resolved, architecture conditions formally deferred with rationale | docs/research/DISCOVERY-REVIEW.md, CONDITION-DISPOSITIONS.md | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: each research artefact reviewed for coverage of its RP items and correct classification.
- Independent verifier: a fresh-context reviewer agent (did not author the research) audits the discovery package for completeness, correct classification, unrealistic AI claims, missing workflows/failure states, and undocumented unknowns → DISCOVERY-REVIEW.md.
- Required environment: web research tools.

## Iteration ledger

### Iteration 1

- Target criterion: S2-001…S2-008 (parallel research), then S2-009 (review).
- Hypothesis: six role-scoped research agents writing classified artefacts, synthesised into an evidence register + open decisions, then independently reviewed, satisfies the Stage 2 predicate.
- Change or investigation: dispatch parallel research specialists (competitor/adjacent; AI/transcription/detection/TTS; licensing/compliance; cross-platform/offline/perf; security/privacy; personas/workflows), synthesise EVIDENCE-REGISTER + OPEN-DECISIONS + DISCOVERY-REPORT, run independent review.
- Verifier executed: pending.
- Result: pending.
- New evidence: docs/research/*, docs/business/*, docs/security/reviews/*.
- Decision: iterate → gate-review.

## Risks and rollback

- Risks: inaccessible proprietary product internals (RISK-007) → mark UNKNOWN; overpromising AI accuracy (RISK-003) → capability assessment enforces honest limits.
- Rollback: additive artefacts under git; no production state.

## Pause and escalation conditions

- Pause/abort on user gate instruction. Escalate material licensing/feasibility blockers at the gate.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/STAGE2-discovery.md`
- Validator result: PASS (structural)
- Independent verification result: PASS WITH CONDITIONS (0 blockers, 10 majors, 15 minors) — DISCOVERY-REVIEW.md; integrity conditions resolved, architecture conditions deferred with rationale (CONDITION-DISPOSITIONS.md)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ajnx548
