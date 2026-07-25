# Goal Contract — TASK-stage8-planning-prep

## Identity

- Goal ID: TASK-stage8-planning-prep
- Parent goal ID: BUILD-selahcue
- Title: A gate-ready Stage-8 (Core presentation) plan exists: draft Stage Goal Contract, proposed story breakdown, batch sequence, critical path, and parallel tracks — grounded in the existing ClickUp epics
- Role: delivery-manager
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 4
- Independent verification required: yes

## Objective

While the owner's Stage-7 on-device QA runs, prepare the Stage-8 plan for gate approval. No implementation; no ClickUp story creation before approval (no shadow backlog — the proposal lives in the draft contract and is created in ClickUp only on `continue`).

## Baseline

Verified from ClickUp (2026-07-25): Presentation & Slides `86ajp07ce` (1 story, complete — foundation rendering); Media Playback `86ajp0815` (0 stories); Service Planning `86ajp072p` (CRUD complete; missing-media `86ajp0az9` open, blocked on media existing); Timers `86ajp07nr` (2 complete; epic remainders: pause/resume UI, per-output visibility, timer types, FR-175 analyzer); plus tracked deferrals that become real in Stage 8: per-layer clearing `86ajpy59e` (needs layers), library surface (`86ajpzbxf` item 3). Foundation: 44 batches, V2 demo score 2·7·0·0.

## Inputs and evidence sources

- ClickUp epics/stories above; STAGE7-foundation.md; FOUNDATION-DEMO-REVIEW.md V2; ADR-0014 (text shaping), ADR-0016 (decode sandbox), ADR-0002 (compositor); PRD FR-001..024, FR-054..073, FR-138/139, FR-173/175.

## Scope

### In scope

- `docs/delivery/goals/STAGE8-core-presentation.md` (Status: **DRAFT**) with the stage completion predicate + the proposed story breakdown + batch sequence/critical path/parallel tracks.
- A Build Control comment presenting the plan.

### Non-goals

- Implementation; creating the stories in ClickUp (post-approval); changing product scope (PM owns acceptance).

### Constraints

- Stories map 1:1 to existing epic scope lines (no invented scope); every proposed story names its epic, owner role, and requirements.

### Assumptions and unknowns

- ASSUMED: the Build Control stage list's "8. Core presentation implementation" maps to the epics above. UNKNOWN: owner priority between songs-first vs media-first (presented as a gate choice with a recommendation).

## Dependencies and approvals

- Stage-8 opening + the story creation require the gate `continue`.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | STAGE8 draft contract exists with a finite stage predicate + proposed stories (each: epic, owner role, requirements, acceptance sketch) | validator (structure) + doc review | validator PASS on the draft | STAGE8-core-presentation.md (validator PASS; 10 proposed stories, each mapped to its epic scope text) | PASS |
| C-002 | yes | Batch sequence + critical path + safe parallel tracks + the biggest-risk spike identified | doc review | present + grounded in epic dependencies | STAGE8 §Proposed batch sequence (critical path 8a→8d; S2 spike de-risks 8h; conflict surfaces named) | PASS |
| C-003 | yes | No ClickUp mutations beyond comments (no shadow backlog; stories created only post-gate) | ClickUp check | only comments added | no tasks/statuses mutated this batch (comments only) | PASS |
| C-004 | yes | The plan presented at the gate with the songs-first vs media-first choice + recommendation | gate report | choice + recommendation present | gate presents songs-first (recommended) vs media-first | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: validator on both contracts; cross-check each proposed story against its epic's scope text.
- Independent verifier: the gate itself (owner) + the epic-text cross-check.
- Required environment: repo + ClickUp.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004
- Hypothesis: the epic scope texts decompose cleanly into ~10 stories across 7 batches with songs-first as the lowest-risk entry.
- Change or investigation: author the draft; validate; present.
- Verifier executed: both validators PASS; each proposed story cross-checked against its epic's scope text (no invented scope).
- Result: all 4 criteria PASS — STAGE8 draft (10 stories, 10 batches, critical path, parallel tracks, biggest-risk spike) ready for the gate.
- New evidence: STAGE8-core-presentation.md (DRAFT).
- Decision: gate-review

## Risks and rollback

- Risks: none beyond planning rework. Rollback: docs-only.

## Pause and escalation conditions

- Owner priority decision at the gate.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-stage8-planning-prep.md --require-complete`
- Validator result: PASS (4/4)
- Independent verification result: epic-text cross-check + the gate itself
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ajnx548
