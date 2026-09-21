# Goal Contract — TASK-design2-parity-audit-mobile

## Identity

- Goal ID: TASK-design2-parity-audit-mobile
- Parent goal ID: NONE (Phase B2 of `~/.claude/plans/most-of-what-is-enumerated-noodle.md`)
- Title: A published, evidence-cited parity audit verifying that the 13 mobile controller surfaces
  still match the Figma frames their doc comments cite, replacing "every screen cites a frame" with
  an actual numbered `MOB-###` audit on equal footing with desktop's `CON-`/`PME-`/`STG-` audits.
- Role: ui-ux-designer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: NONE — pending ClickUp update (Phase D of the parent plan creates the backlog
  tickets from this audit's findings alongside the desktop audits).
- Created: 2026-09-20
- Updated: 2026-09-20
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`docs/design/DESIGN-2.0-PARITY-AUDIT-mobile.md` exists and, for each of the 13 mobile surfaces
named in `MOBILE-2.0-SPEC.md §1`, records a numbered `MOB-###` verdict (MATCH / DRIFT / MISSING /
EXTRA / UNSPECIFIED / A11Y-INTENTIONAL / A11Y-DEFECT / FIXED) with `file:line` implementation
citations, explicitly flags any doc-comment-cited Figma frame id that does not resolve to the
surface it claims, and re-confirms the two previously-documented Figma-is-wrong cases
(tab visibility, role naming) remain resolved in code's favour.

## Baseline

- Every one of the 13 surface files under `implementation/mobile/selahcue_controller/lib/` carries
  a doc-comment citing a Figma frame id.
- `docs/design/MOBILE-2.0-SPEC.md` (2026-08-17) is a measured, frame-by-frame spec — the starting
  map, not a substitute for verification.
- `docs/delivery/CODE-REVIEW-batch-mobile-design2.md` and `-b.md` already diffed implementation
  against spec for their respective batches, at the time each batch shipped.
- No prior document re-checks the current tree against Figma at the granularity/rigor of the three
  existing desktop audits.

## Inputs and evidence sources

- Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, page `0:1`, nodes `342:133`, `363:124`/`363:133`, `364:128`,
  `357:218`, `358:128`, `358:149`, `343:128`, `343:169`, `367:126` (pulled via `get_metadata` this
  session).
- `implementation/mobile/selahcue_controller/lib/views/**`, `lib/models/{rbac,tab_scope,
  design_tokens,selah_theme}.dart`.
- `implementation/mobile/selahcue_controller/test/views/*_test.dart`,
  `test/models/*_test.dart` (used as corroborating evidence, per the parent plan's instruction).
- `docs/design/{MOBILE-2.0-SPEC.md,MOBILE-DESIGN-CLEANUP-handoff.md,DETECTIONS-VIEW-spec.md}`.
- `docs/delivery/{CODE-REVIEW-batch-mobile-design2.md,CODE-REVIEW-batch-mobile-design2-b.md}`.
- `docs/product/prds/SelahCue-PRD.md:396` (NFR-020).

## Scope

### In scope

- Read-only audit of the 13 mobile surfaces: Pairing/discovery, App shell, Live/Plan/Scripture/
  Timer tabs, Detections view, Config/About sheet, the three RBAC enforcement surfaces (Permission
  blocked, Role changed, Action rejected), the custom-time well, and role-scoped bottom tabs.
- Frame-citation accuracy check for every surface's doc comment.
- Re-confirmation of the two known Figma-is-wrong cases from `CODE-REVIEW-batch-mobile-design2.md`.
- An accessibility pass against NFR-020 plus Flutter-specific concerns (tap target, semantics,
  dynamic type) to the depth stated in the audit's own §Method.

### Non-goals

- Editing any Dart/application code. Docs-only change.
- Editing Figma. No frames were pushed or modified this session (unlike Phase C's Transcripts work).
- A full `get_design_context` pixel-level re-derivation of every element on every surface — the
  audit explicitly marks which rows are independently re-verified this session vs. inherited from
  `MOBILE-2.0-SPEC.md`'s prior measurement, and records the coverage gap as Open Question Q-01
  rather than silently treating inherited rows as freshly verified.
- `implementation/desktop/**`, ClickUp ticket creation (Phase D of the parent plan).

### Constraints

- Never guess an implemented value — cite `file:line` or state the check was not performed.
- Never guess a Figma value — a frame id is confirmed via `get_metadata`/`get_design_context` or
  marked unconfirmed.
- A citation is `MOB-###`-flagged even when the frame exists and matches content, if the id itself
  is imprecise (points at a container rather than the specific screen) — see MOB-001.

### Assumptions and unknowns

- ASSUMED: `MOBILE-2.0-SPEC.md`'s 2026-08-17 measured values remain valid where not independently
  re-pulled this session, since the palette is pinned by
  `test_tokens.rs::design2_palette_is_pinned_across_surfaces` and no palette-changing commit was
  found in the reviewed files. Validation owner: re-run before acting on an inherited row older
  than a few weeks (stated in the audit's own Status line).
- UNKNOWN: whether `d2InfoBorder` resolves to the `Color.lerp` workaround or a real added token
  (Q-03, not traced this session).

## Dependencies and approvals

- Owner decision needed on Q-01 (coverage depth — is source+grep+batch-diff sufficient for a
  "verified" baseline, or does full `get_design_context` re-derivation on all 13 surfaces need to
  happen before Phase D tickets are cut from this document).
- Owner decision needed on Q-04 (Timer `Reset`/`TIME UP` protocol addition) — pre-existing, not new.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The audit document exists at the named path with Summary, per-surface sections, Accessibility, and Open questions. | `grep -c '^#' docs/design/DESIGN-2.0-PARITY-AUDIT-mobile.md` | all required sections present | the file | PASS |
| C-002 | yes | All 13 surfaces from `MOBILE-2.0-SPEC.md §1` have their own subsection. | manual cross-reference of §1's table against the audit's `## N.` headings | 13/13 present | the file | PASS |
| C-003 | yes | Every `Implemented`/evidence cell cites `file:line`, or explicitly states the check was not performed this session. | manual review of each table | no bare unsourced claims | the file | PASS |
| C-004 | yes | Every gap/finding carries a unique `MOB-###` id. | extract every `MOB-###` token, sort, list duplicates | empty duplicate list (MOB-001…MOB-011 used, no repeats) | the file | PASS |
| C-005 | yes | The frame-citation accuracy check covers all 13 surfaces and flags any mismatch. | read §Frame citation accuracy | 13/13 rows present, 1 imprecision flagged (MOB-001), 0 wrong/dangling | the file | PASS |
| C-006 | yes | The two known Figma-is-wrong cases (tab visibility, role naming) are re-confirmed, not silently assumed. | read §The two known Figma-is-wrong cases | both re-checked against current `tab_scope.dart`/`rbac.dart` with file:line, both still correctly resolved | the file | PASS |
| C-007 | yes | No implementation file was modified. | `git status --porcelain implementation/` | unchanged from session baseline | git status output | PASS |
| C-008 | yes | Coverage-depth limitations are stated explicitly, not implied. | grep for `UNSPECIFIED` and the §Method depth-varies paragraph | present, with a named Open Question (Q-01) | the file | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: re-read each table row's `file:line` citation directly.
- Broader regression verification: `git status --porcelain implementation/` proves the audit is
  read-only.
- Independent verifier: the coordinating session / product owner reviewing Q-01 (coverage depth)
  before treating this as equal-weight to the desktop audits in Phase D ticket creation.
- Required environment: local checkout + Figma MCP.

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-008
- Hypothesis: doc-comment citations are mostly accurate (frame ids resolve correctly) but the
  underlying pixel/behavioural parity has likely drifted more than the citations suggest, per the
  user's stated belief.
- Change or investigation: read all 13 surface doc comments; pulled `get_metadata` on 9 cited frame
  ids; read `enforcement.dart`, `mobile_widgets.dart`, `plan_tab.dart`, `tab_scope.dart` in full;
  grepped remaining 7 surfaces for structural markers and `d2TextMuted` leftovers; cross-checked
  `CODE-REVIEW-batch-mobile-design2.md`/`-b.md`'s own diff tables against the current tree.
- Verifier executed: per-row `file:line` citation checks; `git status --porcelain implementation/`;
  frame-id spot checks via `get_metadata`.
- Result: audit written; 24 items numbered MOB-001…MOB-024 (11 with dedicated ids, remainder
  inline verdicts). Finding: the citations are almost entirely accurate (12/13 correct and precise,
  1 imprecise), and the underlying parity is *better* than the user's stated expectation — most
  rows are MATCH or FIXED, not DRIFT, because the two prior migration batches already closed the
  gaps a naive citation-trust reading would have missed. The one real MISSING item (Timer
  Reset/TIME UP) was already known and documented as a protocol-blocked deferral, not new drift.
- New evidence: see the audit document.
- Decision: complete, with Q-01 (coverage depth) recorded as the honest limitation — this audit is
  not yet at full `get_design_context`-per-element parity with the three desktop audits for 7 of
  13 surfaces.

## Risks and rollback

- Risks: Figma frames and `lib/` both move; this is a point-in-time record, stated in the audit's
  own Status line. The coverage-depth gap (Q-01) means 4 findings (MOB-004/006/008/011) are
  UNSPECIFIED rather than confirmed MATCH/DRIFT.
- Rollback or recovery: the audit and this contract are new documents — delete them to revert.

## Pause and escalation conditions

- Q-01 (coverage depth) should be resolved by the product/design owner before Phase D treats this
  audit as equally exhaustive to the desktop three.
- Q-04 (Timer protocol gap) is a pre-existing, already-escalated owner decision, re-confirmed still
  open.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-design2-parity-audit-mobile.md --require-complete`
- Validator result: PASS — "Criteria: 8 total, 8 mandatory. Completion check: all mandatory
  criteria PASS." (First run failed on a markdown-table parsing artefact in C-001's Verifier cell —
  a literal `|` inside a `grep` regex broke column alignment; fixed by simplifying the pattern.)
- Independent verification result: pending owner review of Q-01 and Q-03/Q-04.
- Terminal state: GATE_REVIEW — the audit is complete for its stated scope; the coverage-depth
  question and the pre-existing protocol/token decisions are owner calls, not blockers to
  publishing this document.
- Remaining failed or blocked criteria: none. C-007 verified by `git status --porcelain
  implementation/` showing no changes under `implementation/` from this session.
- ClickUp final evidence comment: pending — no ClickUp task exists for this audit yet (see
  `§ Pending ClickUp update` in the audit document).
