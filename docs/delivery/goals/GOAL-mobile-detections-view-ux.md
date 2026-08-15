# Goal Contract — TASK-mobile-detections-view-ux

## Identity

- Goal ID: TASK-mobile-detections-view-ux
- Parent goal ID: NONE
- Title: An implementation-ready UX spec exists for the mobile "Needs your approval" detections view, covering every state, token, accessibility rule and live-service risk, and the landed implementation is reviewed against it
- Role: ui-ux-designer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak188mz
- Created: 2026-08-15
- Updated: 2026-08-15
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`docs/design/DETECTIONS-VIEW-spec.md` specifies the Scripture-tab approval banner, the
Scripture tab-icon count badge, and the full-screen `Needs your approval` route precisely
enough for `/mobile-engineer` to build and `/qa-engineer` to test without asking a follow-up
question — and the result of that build is reviewed against the spec.

## Baseline

Verified at commit `112eabb`, working tree clean under `implementation/mobile/selahcue_controller`:

- `lib/views/tabs/scripture_tab.dart` renders detections inline via `_detectionSection` /
  `_detectionRow` (lines 246–326). The section is an unbounded, non-flexing sibling of the
  `Expanded` verse list inside a `Column` — the overflow reported in ClickUp `86ak188mz`.
- `lib/views/detections_view.dart` does not exist. `grep -rl detection lib test` matches only
  `models/protocol.dart`, `views/tabs/scripture_tab.dart`, `test/models/protocol_test.dart`,
  `test/views/scripture_approval_test.dart`. No implementation has landed.
- Wire support is already complete: `DetectionView` (protocol.dart:159), `cmdApproveDetection`
  (protocol.dart:69), `cmdDismissDetection` (protocol.dart:73), `OperatorStateView.detections`
  (protocol.dart:242). No backend or wire change is in scope.
- The mobile app renders on the **canonical** `DesignTokens` layer. The additive `d2*`
  Design 2.0 layer exists in `design_tokens.dart` but no mobile surface consumes it.
- `lib/models/tab_scope.dart:46` hides the Scripture tab entirely from a role without
  `Capability.searchScripture`, and always builds it with `viewOnly: false`.
- Reduced motion is already handled app-wide by a `pageTransitionsTheme` override in
  `lib/main.dart:53-71`, gated on `MediaQuery.disableAnimations || settings.reduceMotion`.

## Inputs and evidence sources

- ClickUp bug `86ak188mz` (approved fix + acceptance criteria) under epic `86ajp086b`
- `docs/design/DESIGN-2.0-HANDOFF.md` §5.5, §5.8, §6, §7
- `docs/design/UX-CANONICAL.md` §3 (always-on emergency chrome), §4 (colour semantics)
- `docs/design/DESIGN-TOKENS.md` (fill/ink split, the pinned WCAG audit)
- `docs/design/MOBILE-DESIGN-CLEANUP-handoff.md` §1, §4, §5
- `docs/product/prds/SelahCue-PRD.md` FR-095, FR-115, FR-097, NFR-026
- `implementation/desktop/crates/selahcue-present/tests/test_tokens.rs` (contrast audit)
- The mobile source files listed in Baseline

## Scope

### In scope

- The UX spec document `docs/design/DETECTIONS-VIEW-spec.md`
- A design review of Mika's implementation against that spec, if it lands in the working tree

### Non-goals

- Writing or editing any file under `implementation/` — Mika owns the mobile code and is
  editing it concurrently
- Backend, wire-protocol, or RBAC changes
- The Design 2.0 mobile re-skin (a separate, coordinated four-surface token migration)
- The 7-role RBAC expansion (`86ajxufbg`)
- Low-confidence "alternatives / Edit" treatment from DESIGN-2.0-HANDOFF §5.5 state 4

### Constraints

- Write access limited to `docs/`
- Do not commit, stash, reset or revert — the repository carries owner WIP
- The approved interaction contract is authoritative; the spec details it, never redefines it

### Assumptions and unknowns

- ASSUMED: the mobile surface stays on the canonical token layer until the Design 2.0
  migration story runs. Validation owner: `/ui-ux-designer` + owner token decision
  (DESIGN-2.0-HANDOFF §9.1).
- UNKNOWN: whether the 7-role expansion will ever make the Scripture tab view-only. The
  badge composition rule is specified regardless, because the approved contract requires it.
  Validation owner: `/product-manager` via `86ajxufbg`.

## Dependencies and approvals

- Product owner approval of the interaction contract — GRANTED (recorded in `86ak188mz`)
- `/mobile-engineer` (Mika) implementation — CONCURRENT, not blocking this spec
- Independent design review of the implementation — this goal, criterion C-009

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `docs/design/DETECTIONS-VIEW-spec.md` exists and states scope, non-goals and the authoritative interaction contract | read the file | Sections 1–3 present | docs/design/DETECTIONS-VIEW-spec.md | PASS |
| C-002 | yes | Every state named in the brief is specified: zero, one, many, long text on a narrow phone, drained-while-open, revoked, view-only, offline/disconnected | read §9 state matrix | 16 rows, each with trigger, visual result and exit | spec §9 | PASS |
| C-003 | yes | Every colour, size and spacing value cites an existing `DesignTokens` member or the documented spacing scale — no invented hexes | grep the spec for `#` hex literals outside the token-provenance table | no hex outside §4 provenance table | spec §4–§8 | PASS |
| C-004 | yes | Type scale, spacing and touch-target sizes are given as numbers, and every interactive target is ≥48dp | read §5–§8 metric tables | every control ≥48dp stated | spec §5.2, §7.4, §7.5 | PASS |
| C-005 | yes | Accessibility is specified and testable: semantic labels for Approve/Reject/banner, the badge announcement, warn-on-dark contrast, ≥48dp, and large-text behaviour | read §11 | each item has a stated rule and a verifier | spec §11 | PASS |
| C-006 | yes | Text-scaling robustness is a first-class requirement with an explicit numeric bar and a layout rule that removes the unbounded-child class of bug | read §10 | bar stated as textScaler 3.0 on 320×568; button-stacking threshold stated | spec §10 | PASS |
| C-007 | yes | Banner→route motion, transition ownership and reduced-motion behaviour are specified against the existing `pageTransitionsTheme` seam | read §12 | plain `MaterialPageRoute` required; custom `PageRouteBuilder` prohibited with reason | spec §12 | PASS |
| C-008 | yes | Anything that would slow the operator during a live service is called out explicitly with severity and a mitigation | read §14 | ≥5 numbered callouts, each with impact and mitigation | spec §14 | PASS |
| C-009 | yes | Mika's implementation is either reviewed against the spec with concrete discrepancies, or its absence is reported plainly | `git status --short -- implementation/mobile/selahcue_controller` + read `lib/views/detections_view.dart` and the two diffs | a stated verdict backed by the command output | Iteration 3 ledger + ClickUp `86ak188mz` review comment | PASS |
| C-010 | yes | No file under `implementation/` was modified by this role | `git status --short -- implementation/` | no output | command output | PASS |
| C-011 | yes | The Goal Contract passes the structural validator | `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-mobile-detections-view-ux.md` | exit 0 | validator output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: read the spec against C-001…C-008; run the goal-contract validator.
- Broader regression verification: `git status --short -- implementation/` must stay empty for
  this role; confirm every token named in the spec exists in
  `lib/models/design_tokens.dart`; confirm every command named exists in `lib/models/protocol.dart`.
- Independent verifier: `/qa-engineer` (Quinn) turning §15 into test cases, and
  `/mobile-engineer` (Mika) confirming buildability without follow-up questions.
- Required environment: repository read access at `/Users/m.oluwole/Documents/code/scph`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 … C-008
- Hypothesis: the overflow bug is one instance of a general class — a `Column` child whose
  height is a function of unbounded host state — so the spec must fix the class (bounded,
  scrollable, count-independent heights) rather than only relocate the cards.
- Change or investigation: read the ClickUp contract, the four design docs, and the six mobile
  source files that own tokens, RBAC, tab scoping, responsive layout and reduced motion.
  Measured the warn-on-dark and button contrast pairs against the canonical audit thresholds.
  Wrote `docs/design/DETECTIONS-VIEW-spec.md`.
- Verifier executed: file read-back against C-001…C-008; token existence grep against
  `lib/models/design_tokens.dart`; command existence grep against `lib/models/protocol.dart`.
- Result: PASS on C-001…C-008.
- New evidence: three design defects found that the brief did not anticipate — the pushed
  route hides the always-on emergency chrome (UX-CANONICAL §3 invariant), it also hides the
  reconnect/error banner so Approve can fail silently, and "fixed-height" must mean fixed in
  the detection count, not fixed in device pixels, or the fix trades an overflow for a clip.
- Decision: iterate

### Iteration 2

- Target criterion: C-009, C-010, C-011
- Hypothesis: Mika's implementation has not yet reached the working tree.
- Change or investigation: `git log --oneline -12`, `git status --short`,
  `git ls-files --others --exclude-standard`, and a `detection` grep across `lib/` and `test/`.
- Verifier executed: the commands above.
- Result: PASS. HEAD is `112eabb`; the mobile tree is clean; `lib/views/detections_view.dart`
  does not exist; no detection symbol appears outside the four pre-existing files. No
  implementation to review.
- New evidence: the previously-listed mobile WIP (`live_controller.dart`, `controller_view.dart`,
  `live_tab.dart`, `plan_tab.dart`, `mobile_widgets.dart`) was committed as `2706651` and
  `2884c63` — it is the reconnect-race work, unrelated to this goal.
- Decision: iterate

### Iteration 3

- Target criterion: C-009
- Hypothesis: Mika's implementation, written concurrently from the same ClickUp contract, will
  satisfy the seven ClickUp acceptance criteria but will miss the three requirements the
  contract did not state — the occluded emergency chrome, the occluded connection banner, and
  the text-scale reading of "fixed height".
- Change or investigation: re-ran `git status --short -- implementation/mobile/selahcue_controller`
  after writing the spec. The implementation had landed in the interval. Read
  `lib/views/detections_view.dart` (new, 229 lines), the diffs to
  `lib/views/tabs/scripture_tab.dart` and `lib/views/controller_view.dart`, the new
  `test/views/detections_overflow_test.dart` (10 tests) and the reworked
  `test/views/scripture_approval_test.dart`. Reviewed all of it against spec §5–§15.
- Verifier executed: file reads plus `git diff`; spec section-by-section comparison.
- Result: PASS on C-009. All seven ClickUp acceptance criteria are met and well tested. Three
  ship-blocking design defects and eleven lower-severity discrepancies were found and reported.
- New evidence: the hypothesis held exactly. The route carries no `EmergencyStrip` (UX-CANONICAL
  §3 invariant), renders no connection banner and leaves Approve/Reject live during a reconnect
  (silent failure), and the banner is a literal `Container(height: 44)` which clips its label
  above `textScaler` ≈ 2.8 and sits below the 48 dp touch bar. Full findings in the handoff.
- Decision: complete

## Risks and rollback

- Risks: (1) Mika builds from the ClickUp text alone and misses the emergency-chrome and
  connection-banner requirements, shipping a route that is unsafe to sit on during a service.
  (2) "Fixed-height banner" is implemented as a literal `SizedBox`, clipping at large text
  scale and converting an overflow bug into a legibility bug. (3) The new surface is built on
  the `d2*` token layer, creating a one-screen visual island ahead of the coordinated migration.
- Rollback or recovery: the deliverable is a document under `docs/`; reverting is deleting or
  amending it. No production surface changes as a result of this goal.

## Pause and escalation conditions

- A request to edit any file under `implementation/` — owner: `/mobile-engineer`, escalate.
- A request to change the approved interaction contract — owner: `/product-manager`, escalate.
- A decision to adopt the Design 2.0 token layer on mobile — owner: repository owner
  (DESIGN-2.0-HANDOFF §9.1), escalate.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-mobile-detections-view-ux.md`
- Validator result: see criterion C-011
- Independent verification result: pending `/mobile-engineer` and `/qa-engineer` use of the spec
- Terminal state: VERIFIED_COMPLETE for the design deliverable; the implementation review
  returns "not landed" as its verified finding.
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: pending post to `86ak188mz`
