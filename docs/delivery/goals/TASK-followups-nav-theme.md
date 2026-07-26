# Goal Contract — TASK-followups-nav-theme

## Identity

- Goal ID: TASK-followups-nav-theme
- Parent goal ID: STAGE8-core-presentation
- Title: Register the recommended follow-up stories (nav/Screens impl · per-screen theme · theme-engine enhancements) in ClickUp so they are not lost — planning only
- Role: delivery-manager
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 3
- Independent verification required: no (planning artefact; gate is the user)

## Objective

Several recommendations surfaced across the recent design/engine batches (86ajq1n14 nav/Screens design; 86ajq14vq S8-3b theme engine) are not yet tracked and would be lost. Register them as gated backlog stories in the correct epics with one owner + acceptance + dependencies each.

## Baseline

Verified from ClickUp: epics **86ajp08bx** (Accessibility & Design System) and **86ajp07ce** (Presentation & Slides); design story **86ajq1n14** (nav/Screens, code-review — the design is done); **86ajq14vq** S8-3b theme engine (done); **86ajq14wn** S8-3d per-item override; **86ajpzhbc** S8-6 sandboxed decode. No existing stories cover the app-menu/Screens implementation, per-screen theme, or the theme-engine enhancement seams.

## Inputs and evidence sources

- ClickUp epics/stories above; NAV-IA-spec.md + Figma 212:124/217:124; THEME-MODEL-spec.md §4 (deferred seams); the S8-3b review (per-screen theme + shrink-to-fit outcomes).

## Scope

### In scope

- Create 3 stories (search first; no dups): (1) App menu + Screens page IMPLEMENTATION — /frontend-engineer, epic 86ajp08bx, depends on 86ajq1n14; (2) Per-screen theme (engine) — /backend-engineer, epic 86ajp07ce, depends on 86ajq14vq, relates to 86ajq14wn; (3) Theme engine enhancements (R-later, grouped: gradient/image bg, multi-weight/custom fonts, pagination) — /backend-engineer, epic 86ajp07ce.
- Set dependencies; update BUILD CONTROL 86ajnx548.

### Non-goals

- Any implementation or design. Changing product acceptance. Restructuring the workspace.

### Constraints

- No duplicates (search first); reuse existing epics + statuses; one owner + acceptance + deps each; acyclic; no repo shadow backlog.

### Assumptions and unknowns

- ASSUMED: the 3 enhancement seams group into ONE R-later story (they share an owner + release band); split later if prioritised. VALIDATION: the gate.

## Dependencies and approvals

- None blocking. The stories are backlog; sequencing is the user's at future gates.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | ClickUp searched; no duplicate stories created | clickup_search | net-new | clickup_search — no dups (existing S8-3c/d are distinct) | PASS |
| C-002 | yes | 3 stories created with one owner + scope + acceptance + requirement/epic link each | task reads | 3 schema-complete stories | 86ajq321f (nav impl) · 86ajq321k (per-screen theme) · 86ajq3225 (enhancements R-later) | PASS |
| C-003 | yes | Dependencies set (nav-impl→86ajq1n14; per-screen-theme→86ajq14vq; graph acyclic) | dependency review | acyclic; correct | 321f→86ajq1n14; 321k→86ajq14vq; 3225→86ajq14vq (all waiting_on); acyclic | PASS |
| C-004 | yes | BUILD CONTROL 86ajnx548 updated with the new backlog + the recommended sequencing | task comment | comment posted | BUILD CONTROL comment posted | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Read back the created stories + dependency links; confirm the BUILD CONTROL update. Environment: ClickUp.

## Iteration ledger

### Iteration 1

- Target: C-001..C-004.
- Change: searched ClickUp (no dups); created 3 stories — 86ajq321f (App menu + Screens IMPL, frontend, epic 86ajp08bx), 86ajq321k (Per-screen theme engine, backend, epic 86ajp07ce), 86ajq3225 (Theme engine enhancements R-later: backgrounds/fonts/pagination, backend, epic 86ajp07ce); wired dependencies (321f→86ajq1n14 design; 321k + 3225 → 86ajq14vq S8-3b); updated BUILD CONTROL.
- Result: all 4 criteria PASS.
- Decision: complete.

## Risks and rollback

- Risk: over-granular backlog. Mitigated: the enhancement seams are grouped into one R-later story. Rollback: stories can be closed/merged with approval.

## Pause and escalation conditions

- The user gate chooses which backlog story to pull next.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-followups-nav-theme.md --require-complete`
- Validator result: PASS --require-complete (4/4)
- Terminal state: VERIFIED_COMPLETE (3 stories registered + wired)
- ClickUp final evidence comment: BUILD CONTROL 86ajnx548
