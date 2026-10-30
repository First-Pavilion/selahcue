# Goal Contract — TASK-17tnw2aynax

## Identity

- Goal ID: TASK-17tnw2aynax
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Library snapshots keep plan-linked presentation names and missing status current
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2aynax
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Applying an authoritative presentation-library snapshot updates the shared plan-deck resolution data and its rendered consumers, so library changes do not leave stale names or false missing-presentation chips.

## Baseline

Verified at fresh main9d3febdc56f92560a469fe2a37590a0f4017ff28: planLoadDecks already has planDecksGen/planDecksLatest guards, including superseded return-value behavior, from merged PR100. Task comment1400430000020123 explicitly identifies that part as complete. The remaining pmApplyLibrary function updates only pmLibDecks/open/persistence/restorable and library grid; it never publishes the same snapshot to planDecks. Console render also caches its host-view signature independently of library data.

## Inputs and evidence sources

- Complete original task/comments: wave2-20261029/frontend-qualification/17tnw2aynax-live.json and qualifications.md.
- Current app.js planLoadDecks, pmApplyLibrary, link chips/cards/summary and render signatures.
- Existing operator_headless.py real library interactions and PR100 race/return-value/catch-path controls; root and desktop CLAUDE.md.

## Scope

### In scope

- Remaining library-snapshot publication/invalidation seam, shared plan-deck resolution and dependent render-cache invalidation.
- Behavioral tests of library mutation snapshots, latest-data ordering, stale return values and truthful unknown versus empty states.
- Hosted behavioral RED/GREEN, measured exact count and isolated mutation/restored proof.

### Non-goals

- Reimplementing completed PR100 request-ordering guards, unrelated library request policy, new UI or backend/API contracts.
- Other operator signal/CSS tickets, notes/auth source, new per-mutation network polling or global performance refactors.

### Constraints

- One isolated managed worktree/branch/PR; preserve concurrent agents' work. Ordinary current-main integration before publication.
- No local project runtime/build/benchmark/browser while host is paging. Hosted actual behavioral RED precedes production edits.
- Root delegates own diagnostic refs, feature push and draft PR/attachment/full applicable CI; root retains ClickUp, all four reviews, merge and QA. No force pushes or protected-branch edits.
- Preserve all existing PR100 guards and tests, invalid/failed-load honesty, rendering/focus protections and live-output safety.

### Assumptions and unknowns

- VERIFIED: library mutation handlers already apply LibraryView replies through pmApplyLibrary; the remaining defect is shared resolution state, not a new mutation workflow.
- UNKNOWN: exact remaining runtime failures/count and final review/CI outcomes until hosted execution.

## Dependencies and approvals

- Root explicitly selected the residual pmApplyLibrary gap; comment1400430000020123 preserves the already-complete generation-counter history. No new owner/design decision is required to apply existing library data to existing chips.
- Root owns source review routing and final publication beyond draft/CI, merge and QA.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Library snapshots update plan-deck names, counts and missing/resolved chips without an extra deck-list request or plan-surface visit | Full required operator_headless.py | Real mutation/application and DOM assertions pass after baseline RED | Hosted browser log | PENDING |
| C-002 | yes | A library snapshot supersedes an older in-flight plan load, including returned values and stale failures | Full operator headless existing/new concurrency controls | Latest snapshot remains authoritative; old caller receives latest data; PR100 controls retain passing behavior | Hosted concurrency log | PENDING |
| C-003 | yes | Unknown/malformed library data does not become a false missing snapshot; a genuinely empty known library still marks missing | Full operator headless positive/negative controls | Unknown stays unresolved, empty remains missing; legitimate mutation data remains usable | Hosted controls log | PENDING |
| C-004 | yes | Applicable full CI and isolated publication-hook mutation proof pass | Normal operator CI plus baseline/mutant/restored full headless runs | Required gates green; exact hook mutant causes named assertions; restored source passes measured strict count | Hosted CI/mutation receipts | PENDING |
| C-005 | yes | All independent reviewers approve frozen source | Cody, Quinn, Vera and Shadow | No unresolved blocking findings after remediation/re-review | Root consolidated review | PENDING |

## Verification plan

- Focused verification: full real operator DOM harness with sibling PR100 race controls retained; actual library reply paths and rendered link state.
- Broader regression verification: normal path-filtered operator CI, strict measured headless count and WebKit smoke; no claim of owner-native Tauri or unexecuted OS coverage.
- Independent verifier: root coordinates Cody, Quinn, Vera and Shadow.
- Required environment: isolated hosted Chrome for behavioral diagnostics; full normal pinned operator CI/toolchains and WebKit. Local checks limited to source, structural validation, stdlib AST and Git evidence.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: pmApplyLibrary receives fresh deck data but leaves shared plan resolution and cached rendering unchanged; an earlier held planLoadDecks can also overwrite a newer library mutation unless publication joins the existing generation mechanism.
- Change or investigation: read complete original task/comment and current main; confirm PR100 portion already complete. Prepare tests-only real DOM/ordering regressions and controls against unchanged production.
- Verifier executed: Goal structural validator and static baseline/AST checks; actual hosted RED will precede implementation.
- Result: Pending hosted behavioral evidence. Production unchanged.
- New evidence: frozen tests-only checkpoint and own hosted diagnostic receipt.
- Decision: handoff

## Risks and rollback

- Risks: updating data without render invalidation leaves chips stale; clearing to an empty array invents missing content; failing to supersede old requests restores stale data or return values. Tests exercise each boundary.
- Rollback or recovery: revert this one PR; no persisted data/schema/migration change.

## Pause and escalation conditions

- Stop implementation until actual hosted assertion RED is inspected.
- Escalate a genuine new policy/design or API requirement; do not silently widen the residual ticket or weaken counts/bounds.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2aynax-plandecks-library-invalidation.md
- Validator result: PASS structural validation on 2026-10-30; no local project runtime executed.
- Independent verification result: Pending root-owned reviews.
- Terminal state: ACTIVE, preparing tests-only RED.
- Remaining failed or blocked criteria: C-001 through C-005 pending.
- ClickUp final evidence comment: Root owns delivery updates and persisted QA readback after passing merge gates.
