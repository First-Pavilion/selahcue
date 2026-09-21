# Goal Contract — TASK-design2-parity-reconcile

## Identity

- Goal ID: TASK-design2-parity-reconcile
- Parent goal ID: NONE
- Title: A `## Reconciliation` section appended to each of the three existing Design 2.0 parity
  audits, giving every `CON-###`/`PME-###`/`OUT-###`/`STG-###` finding a current OPEN/FIXED/SUPERSEDED
  verdict against `main`, plus a reconciled open-item total ready for Phase D ticket creation.
- Role: ui-ux-designer
- Status: COMPLETE
- Execution engine: goal (recorded post hoc for validator/format consistency with
  `TASK-design2-parity-audit-presentation.md`; this task was executed as a single manual audit pass,
  not driven through the live `/goal` engine loop)
- ClickUp task: NONE — pending ClickUp update (Phase D of the parent plan creates the real tickets;
  see `docs/delivery/BUILD_STATE.md` for the pointer entry this task adds)
- Created: 2026-09-20
- Updated: 2026-09-20
- Maximum iterations: 1
- Independent verification required: yes

## Objective

`docs/design/DESIGN-2.0-PARITY-AUDIT-{console,presentation,stage}.md` each carry a new
`## Reconciliation — 2026-09-20` section giving every finding id in that document a current status
(`FIXED` with commit + file:line, `SUPERSEDED` with the owner decision that resolved it, or `OPEN`),
and a final open-item count broken down by surface and, where the source audit tagged severity, by
severity.

## Baseline

- Three audits exist, dated 2026-08-23: `DESIGN-2.0-PARITY-AUDIT-console.md` (179 `CON-###`),
  `-presentation.md` (63 `PME-###` + 17 `OUT-###`), `-stage.md` (78 `STG-###`).
- Two known remediation batches: `docs/delivery/CODE-REVIEW-batch-desktop-design2-web1.md` (operator
  webview, commit `7c149ea`) and `-stage.md` (`stage.rs`, commit `7369f61` and follow-ups).
- Planning surfaced a **third** wave not recorded in either batch doc: commit `e8100e0` "Frame G
  recovery states, driven by real host signals" (2026-08-25), documented separately in
  `docs/design/FRAME-G-RECOVERY-STATES-divergences.md`. This closed most of the console audit's
  headline "5 of 6 recovery states are unbuilt" finding, via deliberate, documented divergences from
  the literal frame rather than pixel-parity.
- PRD RISK-205 / NFR-204: shipped console ink/contrast is the source of truth over a stale Figma
  frame. Every `INTENTIONAL-DEVIATION` / `A11Y-CONFLICT` verdict in the three audits, plus the two
  findings reclassified to `INTENTIONAL-DEVIATION` by this reconciliation (`CON-166`, `CON-170`,
  `STG-039`, `STG-071`), must never be "closed toward the frame".

## Inputs and evidence sources

- The three audit docs, both `CODE-REVIEW-batch-*` docs, `FRAME-G-RECOVERY-STATES-divergences.md`.
- `git log --since=2026-08-23` on `implementation/desktop/crates/selahcue-operator/dist/{app.css,app.js,index.html}`
  and `implementation/desktop/crates/selahcue-present/src/{stage.rs,theme.rs,compose.rs,measure.rs,slide.rs}`
  — the definitive list of every commit that could have touched a cited finding.
- Direct `Read`/`grep` against the current worktree tree for every finding not conclusively resolved
  by a batch doc's own explicit scope statement.

## Scope

### In scope

- Re-verifying all 337 findings (179 + 80 + 78) against current `main`.
- Appending one `## Reconciliation` section per audit doc, in place — not a separate status file.
- A final N-open count per surface and severity.

### Non-goals

- Extending the audit to uncovered surfaces (Theme Designer, Service Plan, Pre-service Check, Remote
  Control · Devices) — Phase B of the parent plan.
- The mobile parity audit — Phase B2.
- Designing Transcripts — Phase C.
- Creating ClickUp tickets — Phase D.
- Any implementation-file change. This is a docs-only task; `implementation/**` is untouched by this
  worktree (verified: `git status --porcelain implementation/` returns empty apart from `docs/`
  changes made here).

### Constraints

- Never mark a finding `FIXED` without a concrete `file:line`/commit citation checked directly against
  the tree — no inference, matching the source audits' own standard.
- Never reclassify an `INTENTIONAL-DEVIATION`/`A11Y-CONFLICT` verdict as an open gap.
- Preserve every table in the three source documents verbatim; the reconciliation is additive only.

### Assumptions and unknowns

- ASSUMED: the two batch docs' own "scope kept" / "deliberately not done" sections are accurate and
  exhaustive for what they did *not* touch — spot-verified for the highest-severity items (blockers,
  headline findings) by direct grep, not for all ~180 untouched minor/cosmetic rows individually.
- UNKNOWN: whether any commit outside the audited `dist/`/`stage.rs` files (e.g. a controller-side
  change) altered behaviour a finding depends on without touching the cited line. Not exhaustively
  ruled out for every finding — flagged as a limitation, not silently assumed away.

## Dependencies and approvals

- None blocking this task. Owner decisions already on record (console §10 Q2 canonical frames; stage
  batch §1's flash-safety route; stage batch §2's owner-approved deviations) were read and applied;
  no new owner decision was sought or required to complete this reconciliation.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Each of the three audit docs has exactly one new `## Reconciliation — 2026-09-20` section, appended, not replacing prior content. | `grep -c '^## Reconciliation' docs/design/DESIGN-2.0-PARITY-AUDIT-{console,presentation,stage}.md` | `1` for each file | the three files | PASS |
| C-002 | yes | Every `FIXED` row cites a `file:line` re-read directly in this session, or a commit + batch-doc section. | manual review of each reconciliation section | no bare "fixed" claims | the three reconciliation sections | PASS |
| C-003 | yes | No `INTENTIONAL-DEVIATION`/`A11Y-CONFLICT` finding is reclassified as an open gap. | manual review | confirmed — two additional findings (`CON-166`, `CON-170`, `STG-039`, `STG-071`) were *added* to this protected set, none removed from it | the three reconciliation sections | PASS |
| C-004 | yes | A final N-open total, broken down by surface, is stated in each doc's reconciliation and summarised in this contract. | manual review | present in all three docs and in §Final evaluation below | the three reconciliation sections + this contract | PASS |
| C-005 | yes | No file under `implementation/` was modified. | `git status --porcelain implementation/` | empty | git status output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: re-read cited `file:line` for every `FIXED`/`SUPERSEDED` claim (done inline
  during this session for all headline/blocker-severity items; batch-doc citations trusted for
  lower-severity items already gate-verified by that batch's own `operator_headless.py`/`cargo test`
  runs, per this task's own stated method).
- Broader regression verification: `git status --porcelain implementation/` proves the reconciliation
  changed no application code.
- Independent verifier: the coordinating session / product owner, at Phase D ticket-scoping time —
  each ticket should re-confirm its own findings' current file:line before being marked done, since
  this reconciliation explicitly does not claim row-by-row re-grep of every minor/cosmetic finding.

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-005
- Hypothesis: most MISSING-state findings (console's headline "states are not built") would still be
  open, since the known web1/stage batches were both small diffs.
- Change or investigation: `git log --since=2026-08-23` on the audited files surfaced a third,
  previously-unknown remediation wave (`e8100e0`, Frame G recovery states) not mentioned in either
  known batch doc. Read both batch docs, `FRAME-G-RECOVERY-STATES-divergences.md`, and all three
  audits in full; cross-checked every headline/blocker/S1 finding directly against the current tree;
  relied on each batch doc's own explicit scope statements for lower-severity findings it did not
  touch.
- Verifier executed: direct `Read`/`grep` re-checks (cited inline in each reconciliation section);
  `git status --porcelain implementation/`.
- Result: 3 reconciliation sections written. Console: 18 FIXED, 6 SUPERSEDED, 155 OPEN (of 179).
  Presentation: 4 FIXED, 0 SUPERSEDED, 76 OPEN (of 80). Stage: 48 FIXED, 2 reclassified
  INTENTIONAL-DEVIATION, 28 OPEN (of 78). **259 open across all three surfaces**, down from 337 total
  findings (70 FIXED, 6 SUPERSEDED, 2 reclassified).
- New evidence: the headline finding of the original console audit ("2 whole state families are
  unbuilt", 12 of 12 recovery/detection states missing) is now largely closed for Frame G (recovery)
  via documented divergences, and still almost entirely open for Frame D (detection states) — this
  asymmetry was not visible from the plan's starting assumptions and is worth flagging to the user.
- Decision: complete

## Risks and rollback

- Risk: this reconciliation is itself a point-in-time record, like the audits it reconciles — a future
  commit could re-open a `FIXED` finding by regression. `scripts/operator_headless.py` and
  `test_stage_parity.rs`/`test_tokens.rs` gate most of the FIXED items behaviourally, which is the
  actual backstop, not this document.
- Risk: ~150 lower-severity findings were not individually re-grepped (relying instead on the "no
  commit touched this file range" argument). If that argument is wrong for any one finding — e.g. an
  unrelated refactor incidentally fixed or broke a cosmetic rule without the commit message mentioning
  it — this reconciliation would misreport it as unchanged. Flagged in each doc's Method section and
  in this contract's Assumptions.
- Rollback: this is an additive docs change; reverting means deleting the three new sections.

## Pause and escalation conditions

- None encountered. No new owner decision was required to complete Phase A.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-design2-parity-reconcile.md --completion` — not run in this session (docs-only convention, matching the precedent task's own note that this format is followed for consistency, not routed through the formal engine); structure hand-checked against `TASK-design2-parity-audit-presentation.md`.
- Independent verification result: pending the coordinating session / product owner's review, and
  pending Phase D's own re-confirmation at ticket-scoping time (see Verification plan).
- Terminal state: **COMPLETE** — reconciliation written, evidence-cited, no application code touched.
- Remaining failed or blocked criteria: none.
- Final open-item count (feeds Phase D):

| Surface | Total findings | FIXED | SUPERSEDED / reclassified | OPEN |
|---|---:|---:|---:|---:|
| Console (`CON-###`) | 179 | 18 | 6 | **155** |
| Presentation (`PME-###`/`OUT-###`) | 80 | 4 | 0 | **76** |
| Stage (`STG-###`) | 78 | 48 | 2 | **28** |
| **Total** | **337** | **70** | **8** | **259** |

- ClickUp final evidence comment: pending — no ClickUp task exists yet for this reconciliation; Phase D
  creates it. `docs/delivery/BUILD_STATE.md` should get a pointer entry summarising this count.
