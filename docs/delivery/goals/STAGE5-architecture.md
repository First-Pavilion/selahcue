# Goal Contract — STAGE5-architecture

## Identity

- Goal ID: STAGE5-architecture
- Parent goal ID: BUILD-selahcue
- Title: Define SelahCue's system architecture and core UX with documented trade-offs (ADRs), covering every approved MVP requirement, and pass independent architecture + UX + security + accessibility + testability reviews
- Role: software-architect
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-07-23
- Updated: 2026-07-23
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Produce the approved-for-implementation architecture and UX design for SelahCue: technology decisions recorded as ADRs with trade-off analysis (not brief assumptions); a system architecture covering desktop apps, mobile controllers, rendering, media, multiple independent outputs, stage displays, scripture, local-network communication, transcription, scripture detection, sermon notes, provider abstractions, offline operation, persistence, crash recovery, security, privacy, packaging, observability, and update strategy; core UX flows with all interface/failure/loading/empty/permission/accessibility/recovery states; and independent reviews that pass before implementation.

## Baseline

PRD v1.1 (177 FR + 27 NFR) has passed the independent audit (PASS). A preliminary, non-binding tech leaning exists in docs/research/FEASIBILITY.md with 11 open spikes (S1-S11) and 8 open ADR decisions. No architecture, ADRs, or UX designs exist yet.

## Inputs and evidence sources

- docs/product/prds/SelahCue-PRD.md; docs/research/FEASIBILITY.md; docs/security/reviews/threat-model-draft.md; docs/business/PERSONAS.md, WORKFLOWS.md; docs/research/OPEN-DECISIONS.md

## Scope

### In scope

- Technology evaluation + ADRs (core language/topology, rendering/compositor, UI shell, windowing, media engine, HW-decode interop, persistence, LAN protocol+security, mobile framework, AI/provider abstraction, observability, packaging/updates, NDI, text shaping).
- System architecture across all listed domains; requirement→component coverage matrix; risk→mitigation plans.
- Core UX flows + interface-state matrix (default/loading/empty/error/permission/offline/recovery) + component specs + interaction models + accessibility annotations.
- Independent architecture, UX, security, accessibility, and testability reviews.

### Non-goals

- Implementation/production code (Stage 7+); ClickUp ticket decomposition (Stage 6); running the code spikes to completion (spikes are executed as validation during foundation — Stage 5 records the decision + fallback + the spike as a gated validation step).
- TTS architecture (non-goal, DEC-001).

### Constraints

- Decisions must be backed by documented trade-offs, not the brief's suggestions.
- Architecture must uphold the reliability invariants (offline core, output-failure isolation, desktop-authoritative) and the security/privacy posture.
- Where a decision cannot be finalised without a code spike, record a provisional decision + explicit fallback + the validating spike.

### Assumptions and unknowns

- ASSUMED: MVP scope per PRD §30. UNKNOWN: spike outcomes (S1-S11) — mitigated by recorded fallbacks.

## Dependencies and approvals

- Stage 4 gate approved (yes). User gate decision at Stage 5 (pending).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S5-001 | yes | Architecture covers all 21 required domains + every approved MVP requirement | Coverage-matrix review | All 84 MVP FRs map to components; all domains addressed | docs/architecture/ARCHITECTURE.md §15 | PASS |
| S5-002 | yes | Significant decisions recorded as ADRs with trade-off analysis | ADR review | 16 ADRs (ADR-0001…0016), each with options/decision/consequences | docs/architecture/adr/ | PASS |
| S5-003 | yes | Technology choices backed by documented trade-offs (not brief assumptions) | ADR review | Trade-offs documented; WebView-compositor assumption explicitly rejected (ADR-0002/0003) | docs/architecture/adr/ | PASS |
| S5-004 | yes | Major technical risks have mitigation plans (incl. spike fallbacks) | Risk review | Each major risk → mitigation/fallback (§16); RISK-014 added | ARCHITECTURE.md §16 | PASS |
| S5-005 | yes | UX flows + all interface/failure/loading/empty/permission/accessibility/recovery states defined | UX review | 12 flows + full state matrix + component specs + canonical rules; **19 Figma frames** covering all app screens (presentation, scripture, theme designer, song/media editors, STT, detection, sermon notes, settings, add-Bible, outputs, devices/roles, service plan, pre-service) | docs/design/, Figma file SYQn5hFY8YVQKm3c6rw0eJ | PASS |
| S5-006 | yes | Architecture + UX independently reviewed (fresh context) before implementation | Review workflow | FAIL (2 blockers, 12 majors) → remediated → re-review PASS WITH CONDITIONS (blockers cleared, 12/14 majors) → remaining M2/M11/NM-1/NM-3 closed | docs/architecture/ARCH-UX-REVIEW-stage5.md | PASS |
| S5-007 | yes | Unresolved decisions escalated | Gate report | Medium-confidence ADRs (0003/0009) + spike-gated items listed for user | Stage 5 gate report | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: coverage matrix maps every MVP FR to a component; ADR completeness check.
- Independent verifier: fresh-context multi-lens review (architecture conformance, security, accessibility, testability, UX) — did not author the architecture.
- Environment: repo.

## Iteration ledger

### Iteration 1

- Target: S5-001..S5-007.
- Hypothesis: an architect-authored architecture spine + parallel ADRs + UX design + independent review satisfies the predicate.
- Change: author ARCHITECTURE.md (spine + coverage + risks + ADR index); fan out ADRs + UX via workflows; independent review; remediate.
- Verifier executed: pending.
- Result: pending.
- Decision: iterate → gate-review.

## Risks and rollback

- Risks: spike outcomes may force architecture change (mitigated by recorded fallbacks + provisional decisions). Rollback: additive under git.

## Pause and escalation conditions

- Escalate any decision that materially changes cost/scope to the user at the gate.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/STAGE5-architecture.md`
- Validator result: PENDING
- Independent verification result: PENDING
- Terminal state: IN_PROGRESS → GATE_REVIEW
- Remaining failed or blocked criteria: all PENDING
- ClickUp final evidence comment: PENDING
