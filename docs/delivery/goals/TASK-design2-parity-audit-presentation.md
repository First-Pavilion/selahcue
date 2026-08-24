# Goal Contract — TASK-design2-parity-audit-presentation

## Identity

- Goal ID: TASK-design2-parity-audit-presentation
- Parent goal ID: NONE
- Title: A published parity audit that gives every Presentation-surface component (operator editor/media library and audience output) an evidence-cited verdict against its Design 2.0 Figma frame.
- Role: ui-ux-designer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: NONE — no matching task found by `clickup_search` ("Design 2.0 parity presentation media", 0 results). Pending ClickUp update recorded in the audit doc §Pending ClickUp update.
- Created: 2026-08-23
- Updated: 2026-08-23
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md` exists and, for each of the six named Figma
frames, tables every button, label, badge, icon, input, tab, thumbnail, chip, empty state and error
state with (a) the exact Figma value, (b) the implemented value cited as `file:line`, and (c) a
verdict drawn from MATCH / DRIFT / MISSING / EXTRA / UNSPECIFIED / A11Y-CONFLICT.

## Baseline

- `dist/index.html` `#surface-presentation` (line 752–923) already carries a `pm-*` component set.
- Design 2.0 colour tokens are already adopted in `dist/app.css` `:root` (lines ~4574–4622).
- `docs/design/DESIGN-2.0-HANDOFF.md` (2026-08-01) is stale and omits nodes 509:124, 547:124, 552:124.
- `docs/design/MOBILE-2.0-SPEC.md` §6.1 establishes the measured WCAG precedent that several
  Design 2.0 frame pairings fail AA.

## Inputs and evidence sources

- Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, nodes 329:124, 509:124, 547:124, 552:124, 208:124, 390:124, 317:124, 204:124
- `implementation/desktop/crates/selahcue-operator/dist/{index.html,app.css,app.js}`
- `implementation/desktop/crates/selahcue-present/src/{compose.rs,theme.rs,deck.rs,slide.rs,tokens.rs}`
- `docs/design/{PRESENTATION-MEDIA-STATES-spec.md,PRESENTATIONS-LIBRARY-spec.md,DESIGN-2.0-HANDOFF.md,MOBILE-2.0-SPEC.md,THEME-MODEL-spec.md}`

## Scope

### In scope

- Read-only audit of the Presentation editor, the Presentations library, the media library, and the audience-output element model.
- A specification of the gaps, each numbered `PME-###` (web) or `OUT-###` (Rust).

### Non-goals

- Editing any implementation file.
- Auditing the Theme Designer UI (nodes 317:124 / 204:124 are read as the element-model reference only).
- `implementation/mobile/`, `selahcue-engine/`, `selahcue-present/tests/test_present.rs`.
- Running `make ci` (shared checkout).

### Constraints

- Never guess an implemented value — `NOT FOUND` when absent.
- Never guess a Figma value — `unspecified` when absent, raised as an open question.
- A Figma pairing that fails WCAG AA is `A11Y-CONFLICT`, never `DRIFT`.
- A token *value* change is a four-surface lockstep change (`test_tokens.rs::design2_palette_is_pinned_across_surfaces`) — record as an open question, never a fix.

### Assumptions and unknowns

- ASSUMED: node 329:124 is the flagship and wins over the stale handoff. Validation owner: product owner.
- UNKNOWN: whether the right-panel Media/Inspector tab strip is design-sanctioned. Owner decision.

## Dependencies and approvals

- Owner decision on every `A11Y-CONFLICT` row — blocking for implementation, not for this audit.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The audit document exists at the named path with all five required sections. | `grep -c '^## ' docs/design/DESIGN-2.0-PARITY-AUDIT-presentation.md` | Summary, per-frame tables, state matrix, open questions, build order all present | the file | PASS |
| C-002 | yes | All six audited frames have their own per-frame table. | grep for a heading starting `## Frame` in the audit | six frame sections returned | the file | PASS |
| C-003 | yes | Every `Implemented` cell either cites `file:line` or reads `NOT FOUND`. | manual review of each table | no bare prose values | the file | PASS |
| C-004 | yes | Every state vignette on 509:124 is enumerated separately with its own verdict. | compare the §State coverage matrix row count with the frame's vignette count | 21 rows for 21 enumerable states (4 panels + 2 absent + canvas + 12 gallery + 3 system sub-states, less overlap) | the file, §State coverage matrix | PASS |
| C-005 | yes | Every gap carries a unique `PME-###` or `OUT-###` id. | extract every gap id from the audit, sort, and list duplicates | empty output, meaning no duplicate ids | the file | PASS |
| C-006 | yes | Figma pairings that fail WCAG AA are verdicted `A11Y-CONFLICT` and collected in their own section with measured ratio, mobile precedent and both options. | read §A11Y conflicts | section present, each row has ratio + precedent + options | the file | PASS |
| C-007 | yes | No implementation file was modified. | `git status --porcelain implementation/` | unchanged from the session baseline | git status output | PASS |
| C-008 | yes | The `measure_word` memo-key trap is called out in the build order. | grep for the phrase `memo key` in the audit | at least one hit inside the Rust build-order section | the file | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: re-read each table row against the cited line with `sed -n`.
- Broader regression verification: `git status --porcelain implementation/` proves the audit was read-only.
- Independent verifier: the coordinating session / product owner reviewing the open questions.
- Required environment: local checkout + Figma MCP.

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-008
- Hypothesis: the shipped `pm-*` set covers most of the flagship but the topbar actions, the states board and the audience-output element model carry real gaps.
- Change or investigation: read all six frames via `get_metadata`/`get_design_context`/`get_screenshot`; read the operator `dist/` and `selahcue-present` sources.
- Verifier executed: per-row `sed -n` citation checks; `git status --porcelain implementation/`.
- Result: audit written; 80 gaps numbered PME-001…PME-063 (web) and OUT-001…OUT-017 (audience output). Every file:line citation bounds-checked against the real files; all markdown tables verified well-formed.
- New evidence: see the audit document.
- Decision: complete

## Risks and rollback

- Risks: Figma frames drift after this audit; the audit is a point-in-time record and says so.
- Rollback or recovery: the audit is a new document — delete it to revert.

## Pause and escalation conditions

- Any `A11Y-CONFLICT` requires an owner decision before implementation — escalated in §A11Y conflicts.
- Any token *value* change requires a four-surface story — escalated in §Open questions.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-design2-parity-audit-presentation.md --completion`
- Validator result: OK (structural) and OK (completion).
- Independent verification result: pending owner review of the 14 open questions; 3 of them (Q-02, Q-08, Q-10) block implementation.
- Terminal state: GATE_REVIEW — the audit is complete; the A11Y conflicts and open questions are owner decisions.
- Remaining failed or blocked criteria: none. C-007 verified by `git status --porcelain implementation/` — every modified path is a peer session's pre-existing WIP present in the session-start snapshot; `selahcue-operator/dist/` is untouched.
- ClickUp final evidence comment: pending — no ClickUp task exists for this audit (see §Pending ClickUp update in the audit).
