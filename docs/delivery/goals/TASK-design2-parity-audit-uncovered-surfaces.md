# Goal Contract — TASK-design2-parity-audit-uncovered-surfaces

## Identity

- Goal ID: TASK-design2-parity-audit-uncovered-surfaces
- Parent goal ID: NONE (Phase B of the "SelahCue desktop UI — Figma parity audit reconciliation +
  gap-closing tickets" plan; Phase A reconciles the three existing audits, Phase B2 covers mobile,
  Phase C designs Transcripts — all independent, parallel efforts not tracked by this contract)
- Title: Published parity audits that give every component on the six previously-uncovered Design 2.0
  desktop surfaces (Theme Designer, Service Plan builder, Pre-service Check, Remote Control · Devices,
  Settings, the Offline download modal) an evidence-cited verdict against its Figma frame, matching the
  format and rigour of the three existing `DESIGN-2.0-PARITY-AUDIT-{console,presentation,stage}.md`.
- Role: ui-ux-designer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: NONE — pending ClickUp update. Ticket creation is Phase D of the parent plan and is
  explicitly out of scope for this docs-only audit round.
- Created: 2026-09-20
- Updated: 2026-09-20
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Six documents exist under `docs/design/`:

- `DESIGN-2.0-PARITY-AUDIT-theme-designer.md`
- `DESIGN-2.0-PARITY-AUDIT-plan.md`
- `DESIGN-2.0-PARITY-AUDIT-preservice.md`
- `DESIGN-2.0-PARITY-AUDIT-remote.md`
- `DESIGN-2.0-PARITY-AUDIT-settings.md`
- `DESIGN-2.0-PARITY-AUDIT-download-modal.md`

Each tables its surface's components against the exact Figma value (`get_metadata`/`get_design_context`
evidence) and the implemented value (real `file:line` citations, or `NOT FOUND`), with a verdict drawn
from **MATCH / DRIFT / MISSING / EXTRA / UNSPECIFIED / INTENTIONAL-DEVIATION / A11Y-CONFLICT /
A11Y-DEFECT** — the same taxonomy the three existing audits use (confirmed against
`DESIGN-2.0-PARITY-AUDIT-console.md`, which uses the full eight-verdict set).

## Baseline

- Three existing audits (`docs/design/DESIGN-2.0-PARITY-AUDIT-{console,presentation,stage}.md`, dated
  2026-08-23) already cover the console, presentation/media, and stage surfaces in this same format.
- Grep-confirmed at planning time: none of `317:124`/`319:124`/`325:124` (Theme Designer),
  `614:124` (Service Plan), `344:124` (Pre-service Check), or `359:124` (Remote Control) appear in any
  of the three existing audits beyond one incidental read of `317:124` as the audience-output
  element-model reference in the Presentation audit.
- `docs/design/SETTINGS-2.0-HANDOFF.md`, `SERVICE-PLAN-2.0-HANDOFF.md`, `PLAN-SECTIONS-DURATIONS-spec.md`,
  and `DOWNLOAD-MODAL-handoff.md` already exist as design specs for four of the six surfaces and were
  read as companion documents, not treated as a substitute for direct Figma/code verification.
- PRD RISK-205/NFR-204 (shipped console contrast is the source of truth over a stale Figma frame) governs
  every A11Y verdict — established practice from the three existing audits, applied identically here.

## Inputs and evidence sources

- Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, page `0:1`, nodes: `317:124`, `319:124`, `319:152`, `325:124`,
  `325:131`, `325:154`, `325:189`, `563:201` (investigated, ruled out), `614:124` (19 sub-frames),
  `344:124`, `359:124`, `338:124`, `618:124` (59 sub-frames), `396:124`.
- `implementation/desktop/crates/selahcue-operator/dist/{index.html,app.css,app.js,preservice.js,
  remote.js,settings.js}`.
- `implementation/desktop/crates/selahcue-present/src/theme.rs` (built-in theme names, cross-checked
  against the Theme Designer templates strip).
- `docs/design/{SETTINGS-2.0-HANDOFF.md,SERVICE-PLAN-2.0-HANDOFF.md,PLAN-SECTIONS-DURATIONS-spec.md,
  DOWNLOAD-MODAL-handoff.md,DESIGN-2.0-PARITY-AUDIT-{console,presentation,stage}.md}`.
- `docs/product/prds/SelahCue-PRD.md:396` (NFR-020, the contrast bar every A11Y verdict is measured
  against).

## Scope

### In scope

- Read-only audit of the six named surfaces' web/Rust implementation against their Figma frames.
- A specification of every gap, numbered per-surface (`TD-###`, `PLN-###`, `PSC-###`, `RCD-###`,
  `SET-###`, `DLM-###`).
- Confirming or ruling out `563:201` as the Theme Designer templates strip (ruled out — it documents an
  unrelated Live Console Stage sub-tab; recorded as an open question rather than acted on further).
- A lighter, page-level pass for Settings (per the brief: full audit of the two built pages, page-level
  `MISSING` for the seven unbuilt ones, no manufactured component drift against pages that don't exist).
- A short, focused pass for the Download modal (closing the gap between "incidentally noted" in the
  console audit's appendix and "actually audited").

### Non-goals

- Editing any implementation file (`implementation/**` is untouched — verified below).
- Renaming Figma nodes. Several target nodes (`319:124`, `325:124`, and ~20 other page-wide nodes) are
  generically named "Frame"; renaming them is recorded as an open question for a page-wide hygiene pass,
  not done piecemeal by this audit.
- ClickUp ticket creation (Phase D of the parent plan).
- Auditing Transcripts (Phase C), the mobile controller (Phase B2), or re-auditing the three
  already-covered desktop surfaces (Phase A reconciles those against `main`, a separate effort).
- `PLAN-SECTIONS-DURATIONS-spec.md`'s own target (the Live Console's `#plan-wrap` section-grouping
  headers, Figma `965:124`) — a different surface from the Service Plan builder route this audit covers;
  cited only where the two share a data model.

### Constraints

- Never guess an implemented value — `NOT FOUND` when absent.
- Never guess a Figma value — `unspecified` when absent, raised as an open question.
- A Figma pairing that fails WCAG AA is `A11Y-CONFLICT`, never `DRIFT`; an implementation-side failure is
  `A11Y-DEFECT` regardless of what the frame shows.
- A deliberate, non-accessibility departure from the frame (e.g. Remote Control's real RBAC role names
  vs. Figma's illustrative mock labels) is `INTENTIONAL-DEVIATION`, not `DRIFT` — and is never "fixed"
  toward the frame.
- Every numbered finding id must be unique within its document and form a gapless sequence matching the
  document's own "N numbered findings" claim (verified mechanically below, after an initial authoring
  pass produced non-sequential ids that were caught and renumbered during this same session).

### Assumptions and unknowns

- ASSUMED: `618:124` is the live node for the Settings 8-page section despite `SETTINGS-2.0-HANDOFF.md:4`
  naming it `593:124` — confirmed by direct `get_metadata` read returning exactly the content the
  handoff describes. Recorded as an open documentation-hygiene question (SET-OQ-1), not silently
  corrected in the handoff itself (out of scope for a read-only audit).
- UNKNOWN: whether the inline (non-modal) Service Plan link flows (PLN-001/PLN-002) and the Providers &
  Privacy TTS/BYOK omissions (SET-008) are final, ratified decisions or simply undocumented departures —
  recorded as open questions for the product owner.

## Dependencies and approvals

- Owner decision on every `INTENTIONAL-DEVIATION` and open product question raised across the six
  documents — blocking for any future implementation ticket, not for this audit.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | All six audit documents exist at their named paths with the required sections (Summary, per-frame sections, Accessibility, Open questions). | `grep -l '^# Summary' docs/design/DESIGN-2.0-PARITY-AUDIT-{theme-designer,plan,preservice,remote,settings,download-modal}.md` plus a manual section-heading read of each | all six files present; each has Summary/frame-sections/Accessibility/Open-questions | the six files | PASS |
| C-002 | yes | Every "Implemented" cell either cites `file:line` or reads `NOT FOUND`/`Not found`. | manual review of every table | no bare, uncited prose values | the six files | PASS |
| C-003 | yes | Every gap carries a unique id within its document, forming a gapless sequence that matches the document's own "N numbered findings" claim. | `python3` regex extraction + gap check per document (run during this session) | zero gaps, zero mismatches across all six documents | shell output, this session (see Iteration ledger) | PASS |
| C-004 | yes | Each document's `§ Accessibility` section explicitly checks against NFR-020 (`docs/product/prds/SelahCue-PRD.md:396`) and classifies every colour-contrast finding as A11Y-DEFECT, A11Y-CONFLICT, or explicitly-compliant/classified. | grep for "NFR-020" and the verdict tokens in each Accessibility section | present in all six | the six files | PASS |
| C-005 | yes | Each document has an `§ Open questions` section naming only real product/owner decisions, not implementation choices Uma or Farah could make unilaterally. | manual review | present, and every entry names why it isn't this audit's call | the six files | PASS |
| C-006 | yes | `563:201` is investigated and its actual content recorded, rather than assumed to be the Theme Designer templates strip as the brief's working hypothesis suggested. | `DESIGN-2.0-PARITY-AUDIT-theme-designer.md` §"`563:201` — confirmed NOT part of this surface" | section present, cites the real `get_metadata` content | the file | PASS |
| C-007 | yes | No implementation file was modified. | `git status --porcelain implementation/` | empty (docs-only change set) | git status output | PASS |
| C-008 | yes | The Settings audit gives page-level `MISSING` verdicts for the seven unbuilt pages rather than manufacturing component-level drift against them. | `DESIGN-2.0-PARITY-AUDIT-settings.md` §"Page-level coverage" | 7 page-level MISSING findings (SET-001…SET-007), no per-component tables for unbuilt pages | the file | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: re-read a sample of cited `file:line` locations directly against the current
  tree for each document (done during authoring — every citation in this session was read from the live
  file at the time it was written, not recalled from memory).
- Finding-id integrity: a `python3` regex pass over all six documents confirming every `<PREFIX>-###` id
  forms a gapless sequence matching the document's own summary claim — this caught and fixed three
  numbering errors during this same session (Theme Designer, Service Plan, Pre-service Check each
  originally claimed a higher "numbered findings" count than the ids actually used; Remote Control had a
  malformed six-cell table row from an early draft). All six now pass.
- Broader regression verification: `git status --porcelain implementation/` proves the audit is
  read-only.
- Independent verifier: the coordinating session / product owner reviewing the open questions and
  `INTENTIONAL-DEVIATION` verdicts before any implementation ticket is cut from these findings.
- Required environment: local checkout + Figma MCP (`figma-design-to-code` skill loaded before every
  `get_design_context`/`get_metadata` call, per its mandatory-prerequisite rule).

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-008
- Hypothesis: the six surfaces would show a mix of close matches (the more recently touched/self-
  documented ones) and real structural gaps (older or less-maintained frames), plus at least one
  systemic accessibility pattern recurring across surfaces given the Presentation audit already found
  one (the gradient/white-text contrast defect).
- Change or investigation: `get_metadata` on every target node (several exceeded the inline response
  limit and were parsed from saved files with `python3`); full reads of `preservice.js`, `remote.js`,
  targeted reads of `app.js`'s `td*`/`plan*` functions and `settings.js`; cross-reads of the four
  existing handoff docs; hex/contrast verification against the shipped `--sc-*` token file.
- Verifier executed: per-document finding-id gap check (see Verification plan); `git status --porcelain
  implementation/`.
- Result: six audit documents written, 57 numbered findings total (TD 12, PLN 9, PSC 10, RCD 9, SET 9,
  DLM 8). The recurring gradient/white-text A11Y defect (first identified in the Presentation audit)
  reappeared on four of the six surfaces (Theme Designer's `.td-save-cta`, Preservice's `.ps-start`,
  the Download modal's `.dl-btn-primary:hover`, and is notably **absent** on Remote Control and
  Settings — recorded explicitly as the one clean surface pair). `563:201` confirmed NOT to be the
  Theme Designer templates strip (it documents an unrelated Live Console Stage sub-tab spec) — the
  real templates strip is `319:152`.
- New evidence: see the six audit documents.
- Decision: complete

## Risks and rollback

- Risks: Figma frames and `dist/` both move; every document states it is point-in-time and should be
  re-run before acting on a row older than a week (same caveat the three existing audits carry).
- Rollback or recovery: the six documents and this goal contract are new files — delete them to revert.

## Pause and escalation conditions

- Every `INTENTIONAL-DEVIATION` verdict requires an owner decision before any future implementation
  ticket "fixes" it toward Figma — escalated per-document in each `§ Open questions`.
- The `SET-OQ-1` node-id documentation discrepancy (`593:124` vs. `618:124`) should be resolved by
  whoever next edits `SETTINGS-2.0-HANDOFF.md`, not silently by this audit.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-design2-parity-audit-uncovered-surfaces.md --completion`
- Validator result: `OK (completion): docs/delivery/goals/TASK-design2-parity-audit-uncovered-surfaces.md satisfies the Goal Contract schema and all mandatory criteria PASS`
- Independent verification result: pending owner review of the open questions and
  `INTENTIONAL-DEVIATION` verdicts across all six documents; none block the audit itself.
- Terminal state: GATE_REVIEW — the six audits are complete; the open questions and deviations they
  surface are owner decisions, and ticket creation (Phase D of the parent plan) is a separate,
  subsequent effort.
- Remaining failed or blocked criteria: none.
- ClickUp final evidence comment: pending — no ClickUp task exists for this audit round yet (see the
  parent plan's Phase D, and each document's own "Pending ClickUp update" note).
