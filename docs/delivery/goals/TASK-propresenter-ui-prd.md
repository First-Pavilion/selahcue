# Goal Contract — TASK-propresenter-ui-prd

## Identity

- Goal ID: TASK-propresenter-ui-prd
- Parent goal ID: BUILD-selahcue
- Title: Cited ProPresenter-UI research report + designer-actionable adopt/adapt/reject Operator UI PRD exist, validate, and are handed to the owner gate
- Role: product-manager
- Status: COMPLETE — awaiting owner gate (GATE_REVIEW)
- Execution engine: goal
- ClickUp task: NONE (owner-commissioned directly; Diego creates the delivery tickets from the approved PRD — creating them now would pre-empt the gate)
- Created: 2026-08-28
- Updated: 2026-08-28 (final)
- Maximum iterations: 8
- Independent verification required: yes (PRD structural validator + owner gate; ticket creation is explicitly deferred to Diego)

## Objective

The owner can read (1) a traceable, cited research report on the ProPresenter user interface and its category context, and (2) a PRD that tells a designer exactly which ProPresenter capabilities SelahCue adopts, adapts, or rejects — with interaction patterns, IA implications, states, RBAC/offline/accessibility notes, and testable acceptance criteria — without any ClickUp ticket having been created.

## Baseline

- Prior ProPresenter research exists (`docs/research/COMPETITOR-MATRIX.md` §2.2, `docs/research/LIBRARY-ORGANISATION-RESEARCH.md` §2.1) but covers capability inventory + library organisation only, not the operator UI anatomy.
- No `docs/research/PROPRESENTER-UI-RESEARCH.md` and no operator-UI PRD exist (verified by directory listing 2026-08-28).
- The shipped operator console (`implementation/desktop/crates/selahcue-operator/dist/`) already has: app menu + surfaces, transport (Prev/GO LIVE/Next/Blackout), service plan, live transcript, preview/live monitors, scripture browser + slides tab, timer/stage/detections right rail, Screens registry page, Theme Designer with canvas/inspector/templates, emergency footer.

## Inputs and evidence sources

- Owner-supplied screenshot descriptions (two ProPresenter screenshots, including a deliberate annotation on the slide-grid view-density cluster)
- Rowan (product-researcher) web evidence run started 2026-08-28
- `docs/product/prds/SelahCue-PRD.md`, `docs/design/*`, `docs/architecture/ARCHITECTURE.md` + ADRs, `docs/research/*`, `docs/delivery/BUILD_STATE.md`, shipped `dist/`

## Scope

### In scope

- `docs/research/PROPRESENTER-UI-RESEARCH.md` (Rowan's cited report)
- `docs/product/prds/SelahCue-Operator-UI-PRD.md` (adopt/adapt/reject PRD, ticket-shaped headings)
- `docs/decisions/DECISION-LOG.md` — one appended PROPOSED entry (no owner decision fabricated)
- Report-back to the dispatching agent with headline counts, top recommendations, open questions

### Non-goals

- No ClickUp epics/stories/tasks (Diego's step, post-approval)
- No implementation code; no `implementation/` changes
- No self-approval of the PRD; readiness verdict stops at the owner gate
- No pixel-for-pixel copying of ProPresenter UI (PRD NG-4)

### Constraints

- Docs only, shared checkout on `main`: no commit/stage/stash/revert of any session's work
- SelahCue theme = slide-design template, never a colour mode
- ADR-0002/0003: WebView is console-only; audience output never renders in the WebView
- Staging never changes Live; only Go Live does; offline-first; no failure blanks output
- Mobile enforces 4 roles today (7 designed) — flag, never assume 7
- Do not regress shipped accessible ink (GO LIVE/BLACKOUT/primary contrast)

### Assumptions and unknowns

- ASSUMED: owner screenshot descriptions are accurate primary evidence (validation owner: owner, at gate)
- UNKNOWN: several ProPresenter behaviours are version-dependent (6 vs 7 vs 7.x) — Rowan flags per claim
- UNKNOWN: which adopt/adapt items the owner will approve — every contested call raised as an open question

## Dependencies and approvals

- Rowan research agent run — dispatched 2026-08-28, in flight
- Owner gate approval of the PRD — required before Diego creates tickets (pending)

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `docs/research/PROPRESENTER-UI-RESEARCH.md` exists with an evidence register (URL + access date per claim), version caveats, comparator baseline, and the owner-screenshot findings incl. the flagged view-density emphasis | manual review of the file | all listed sections present; every external claim cited | the file | PASS |
| C-002 | yes | The PRD contains an adopt/adapt/reject table covering the notable ProPresenter UI capabilities, each row with a rationale | grep/manual review | table present; rejects carry reasons | `docs/product/prds/SelahCue-Operator-UI-PRD.md` | PASS |
| C-003 | yes | Every adopt/adapt item carries: user problem, interaction pattern, IA implication, states/edge cases, RBAC, offline, accessibility, and testable acceptance criteria | manual review | all eight facets present per item | PRD requirement sections | PASS |
| C-004 | yes | The PRD has prioritisation (must/should/could + sequence), explicit out-of-scope, and a gap analysis vs the shipped product | manual review | sections present and grounded in the audited baseline | PRD | PASS |
| C-005 | yes | `python3 scripts/validate_prd.py docs/product/prds/SelahCue-Operator-UI-PRD.md` exits 0 | command | exit code 0 | command output | PASS |
| C-006 | yes | Owner-decision items are raised as open questions, not silently decided; DECISION-LOG gains one appended PROPOSED entry without touching other sessions' content | `git diff` review | only additive log change; PRD open-questions section lists them | log diff + PRD §Open questions | PASS |
| C-007 | yes | No ClickUp item created and no `implementation/` file changed | `git status` + session review | zero implementation diffs; zero ClickUp writes | session record | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Iteration ledger

| # | Date | Increment | Result |
|---|---|---|---|
| 1 | 2026-08-28 | Dispatched Rowan; audited PRD/design/architecture/research/console baseline; contract authored | baseline established |
| 2 | 2026-08-28 | PRD drafted (validator PASS first run); Rowan report landed at 710 lines/42-source register after a mid-run coordinator false-alarm (second Rowan stood down without writing — no collision) | research + draft complete |
| 3 | 2026-08-28 | PRD reconciled against the evidence: version house rule (v21.x), click-to-live tension raised as OQ-8, FR-222/223 added from sentiment findings, citations + evidence grades added; validator PASS (28 rows, all 32 sections); DEC-016 appended (PROPOSED, additive-only 98(+)/0(-)) | all criteria PASS; GATE_REVIEW |
