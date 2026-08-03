# Goal Contract — TASK-design-right-panel-tabs

## Identity

- Goal ID: TASK-design-right-panel-tabs
- Parent goal ID: NONE
- Title: Design a tabbed right panel (Service Timer | Detected Scriptures) so ≥3 detected scriptures show at once
- Role: ui-ux-designer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: 86ajtxuwr (Live transcript + scripture auto-detection — R3/R4 slice)
- Created: 2026-08-03
- Updated: 2026-08-03
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Redesign the operator console's right column so the Detected Scriptures list is no longer cramped: tab the Service Timer and Detected Scriptures into one full-height panel, showing at least three scripture cards at once, newest first — designed in Figma before implementation.

## Baseline

- **Verified (Figma `312:124`):** the right column `320:201` stacks Service Timer (`323:124`, ~437px) above Detected Scriptures (`323:151`, ~397px); the detection area fits only ~2 cards, so scriptures scroll out of view as they arrive.
- Design 2.0 language is established (surface `#14161d`, primary `#6e5cf0`, gold `#f2b84b`, Inter).

## Inputs and evidence sources

- Figma console `312:124` (right column, timer, detection cards); the user request (tab the two; ≥3 scriptures; Figma first).

## Scope

### In scope

- A Figma design of the tabbed right panel: 2-tab header (Timer · Detected Scriptures + count), both tab states, ≥3 detection cards newest-first, and an implementation-notes/handoff spec.

### Non-goals

- The code implementation (frontend-engineer follow-up), and the newest-first data ordering (repo change, tracked separately).

### Constraints

- Reuse Design 2.0 tokens + the existing detection/timer DOM hooks; keep FR-115 (operator-confirmed) and the client transcript/detection caps.

### Assumptions and unknowns

- ASSUMED: auto-switching to the Detected tab on a new detection is an optional nicety, not required. Owner: product.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A Figma SPEC frame for the tabbed right panel exists | get_screenshot `430:124` | frame present | Figma `430:124`; scratchpad `tabs-full.png` | PASS |
| C-002 | yes | A 2-tab header (Timer · Detected Scriptures + count) with a clear active state is designed, both tab states shown | Visual review | Detected tab `431:124` + Timer tab `434:124`, active underline | Figma nodes | PASS |
| C-003 | yes | The Detected Scriptures tab shows ≥3 scripture cards at once, newest first, with match-% and Stage/Approve/Dismiss | Visual review | 3 cards (Isaiah 61:5, Psalm 23:1, Romans 8:28), newest on top | Figma `431:124` | PASS |
| C-004 | yes | Accessibility (tablist semantics, keyboard, announcements, contrast) is specified | Review notes panel + handoff | role=tablist/tab/tabpanel, ←/→, count announced, AA | Figma `435:124`; handoff | PASS |
| C-005 | yes | A written handoff spec exists for the frontend-engineer | File exists | `docs/design/RIGHT-PANEL-TABS-handoff.md` | repo path | PASS |
| C-006 | yes | Goal Contract is structurally valid | `python3 scripts/validate_goal_contract.py <this> --require-complete` | exit 0 | command output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: screenshots of `430:124` / `431:124` / `434:124`; goal-contract validator.
- Broader: confirm no existing console frames were mutated (only new nodes `430:124`+ created).
- Independent: frontend-engineer at implementation; product on the auto-switch nicety.
- Required environment: Figma MCP + repo.

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-006.
- Hypothesis: tabbing Timer/Detected into one full-height panel gives the detection list room for 3+ cards without losing the timer.
- Change or investigation: built SPEC frame `430:124` — Detected tab (3 cards, newest-first), Timer tab, and a 4-column notes panel; wrote the handoff spec.
- Verifier executed: get_screenshot (renders correctly); validator.
- Result: PASS.
- Decision: complete → VERIFIED_COMPLETE. Hand to frontend-engineer for implementation.

## Risks and rollback

- Risk: tabbing hides the timer while on the Detected tab (and vice-versa) — mitigated by the count badge + optional auto-switch; emergency controls are unaffected (separate footer).
- Rollback: additive Figma nodes only; delete `430:124` to revert.
