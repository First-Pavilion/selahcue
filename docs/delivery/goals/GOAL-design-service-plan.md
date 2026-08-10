# Goal Contract — GOAL-design-service-plan

## Identity

- Goal ID: GOAL-design-service-plan
- Parent goal ID: 86ajp072p (EPIC — Service Planning & Library)
- Title: Design the Design-2.0 Service Plan builder (run sheet + item inspector) and the link-Scripture / link-Presentation flows, with every meaningful state, so the Live Console Service Plan panel is real not a placeholder
- Role: ui-ux-designer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxxqtp
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 16
- Independent verification required: yes

## Objective

In Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, produce Design-2.0 high-fidelity frames for the Service Plan builder (Add-item palette · run sheet · item inspector/plan summary), the link-Scripture and link-Presentation modal flows, the inspector link states (unlinked / scripture-linked / presentation-linked), and every meaningful state from UX-STATE-MATRIX §4 — plus a Live Console Service-Plan-panel variant showing linked items — accompanied by a repository handoff that traces every control to a requirement and specifies states, linking, accessibility, and design-system usage precisely enough to implement and QA without guessing.

## Baseline

- The `plan` route is a placeholder; the Live Console left panel (`312:124`) shows a running order but has no builder/link surface.
- Old Service Plan frame `31:2` exists in the file (three-column builder) but is undocumented/superseded; used as visual reference only.
- Presentations library `547:124` provides deck cards for the presentation picker; the console Scriptures browser provides the scripture-ref pattern.
- **`PlanItem` has no content-reference field** (verified in `selahcue-core/src/plan.rs`) — linking is net-new modelling (ADR-0020 follow-up). Design specifies the target and flags it.
- Design 2.0 tokens/components + a proven figma-use helper library carry over from the Settings 2.0 build.

## Inputs and evidence sources

- Figma: Live Console `312:124`, old builder `31:2`, Presentations library `547:124`, Presentation/Media editor `329:124`.
- docs/product/prds/SelahCue-PRD.md (FR-001..008, 012/013, 019-021, 026/029, 070/071, 074/075, 138/139)
- docs/design/UX-FLOWS.md §1-2, UX-STATE-MATRIX.md §4-6, NAV-IA-spec.md, DESIGN-2.0-HANDOFF.md, PRESENTATIONS-LIBRARY-spec.md
- docs/architecture/ARCHITECTURE.md §8, docs/architecture/adr/ADR-0020
- Implemented code: selahcue-core/src/plan.rs (PlanItem/ItemKind), selahcue-lan/src/protocol.rs (AddItem/PlanItemView/OperatorStateView), selahcue-app/src/controller.rs (slide_for_item/scripture_slide_in), operator dist (#plan-wrap), selahcue-data/src/deck_repo.rs
- Research report (this session)

## Scope

### In scope

- Service Plan builder default + inspector variants (unlinked/scripture-linked/presentation-linked) + plan-summary panel.
- Link-Scripture modal (reference + translation + verses-per-slide + search/verse list) and link-Presentation modal (deck grid picker).
- Every meaningful state (UX-STATE-MATRIX §4): empty, loading, running/live, item-selected/staged, reorder/drag, missing-content validation, error+restore, permission (view-only), delete-confirm (deck-linked warning), recovery/autosave, published change-badge.
- A Live Console Service-Plan-panel variant showing linked Presentation + Scripture items in the running order.
- Accessibility annotations, content/copy, and a repository handoff with per-frame node IDs + FR trace.

### Non-goals

- Designing the deck editor (`329:124`), the Presentations library page (`547:124`), or the Scriptures browser (they are reused/linked, not redesigned).
- Implementing the PlanItem content-reference model/wire (flag + follow-up task only).
- Redesigning the rest of the Live Console.

### Constraints

- Match Design 2.0 tokens + existing component primitives; introduce no new pattern language.
- Preserve the live-cueing invariant: staging/selecting never changes Live; only Go Live commits (FR-012).
- Deferred behaviours shown as honest "later" affordances; admin/role-gated controls hidden (not greyed) for non-permitted roles.
- Additive Figma writes; existing frames untouched.

### Assumptions and unknowns

- ASSUMED: full high-fidelity in the same Figma file (owner confirmed scope + linking pattern this session).
- UNKNOWN: final PlanItem content-reference model. Owner: architect/backend (ADR-0020 follow-up). Design specifies the target + flags it.

## Dependencies and approvals

- Figma MCP (desktop) — connected.
- ClickUp MCP — connected (task 86ajxxqtp).
- Independent design-QA pass — owner: qa/code-reviewer subagent. Status: pending.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The Service Plan builder default frame exists with Add-item palette, run sheet (typed items + link status + duration/owner), and the item inspector | get_screenshot of the builder frame | Builder renders all three regions at Design-2.0 fidelity | Figma node + screenshot | PASS |
| C-002 | yes | Link-Scripture and link-Presentation modal flows each exist as frames | get_screenshot of each modal frame | Scripture-ref picker + deck-grid picker render as focused modals over the builder | Figma nodes + screenshots | PASS |
| C-003 | yes | Inspector link states exist: unlinked (scripture), scripture-linked, unlinked (presentation), presentation-linked | get_screenshot of each | Each variant clearly shows its link state + affordance | Figma nodes + screenshots | PASS |
| C-004 | yes | Every meaningful UX-STATE-MATRIX §4 state has its own frame (empty, loading, running/live, reorder, missing-content, error+restore, permission, delete-confirm, recovery/autosave, published change-badge) | State matrix in handoff maps each → node; get_screenshot confirms | 100% of enumerated states have a frame rendering the delta | Handoff state matrix + screenshots | PASS |
| C-005 | yes | A Live Console plan-panel variant shows linked Presentation + Scripture items in the running order | get_screenshot | Console panel populated (not placeholder), reflecting links | Figma node + screenshot | PASS |
| C-006 | yes | Every control traces to a requirement (FR/doc/code) or is labelled Assumed | Traceability table in handoff | No untagged control; Assumed items marked | docs/design/SERVICE-PLAN-2.0-HANDOFF.md | PASS |
| C-007 | yes | The live-cueing invariant (staging never changes Live; Go Live via Enter) is honoured and annotated | Review frames + handoff | Preview/staged vs Live are distinct; Go Live is the only commit; annotated | Screenshots + handoff | PASS |
| C-008 | yes | The PlanItem content-reference gap is flagged (design specifies target; model change is a follow-up) | handoff note + linked ClickUp follow-up | Flag present; follow-up task linked | Handoff + ClickUp | PASS |
| C-009 | yes | Accessibility specified/testable (contrast, keyboard incl. Alt+↑/↓ reorder + Enter Go-Live, focus/SR roles tree/treeitem/dialog, ≥44px, reduced motion) | Review handoff a11y section + annotations | Each surface has explicit a11y annotations | Handoff a11y section | PASS |
| C-010 | yes | Design-system primitives reused; no invented pattern language | Review vs Design-2.0 components | Every control maps to a specced primitive; deviations justified | Handoff design-system section | PASS |
| C-011 | yes | Repository handoff exists, precise enough to implement + QA, with per-frame node IDs | File exists; review | docs/design/SERVICE-PLAN-2.0-HANDOFF.md present + complete | Handoff file | PASS |
| C-012 | yes | Independent design-QA review confirms coverage with no critical/major gaps unresolved | Independent reviewer checks frames + handoff vs state matrix + FRs | No unresolved critical/major | QA report appended to handoff / ClickUp | PASS |
| C-013 | yes | ClickUp task 86ajxxqtp carries goal ID, engine, iteration evidence, node IDs, terminal state | Inspect task comments | Start + final evidence comments present | ClickUp task 86ajxxqtp | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-frame `get_screenshot` reviewed against the per-state spec + state matrix; handoff traceability cross-checked.
- Broader regression verification: confirm no existing frame mutated; confirm Design-2.0 tokens/contrast; confirm the live-cueing invariant reads correctly on running/live/staged frames.
- Independent verifier: qa/code-reviewer subagent performs a design-QA pass against UX-STATE-MATRIX §4 + the epic FRs; the implementing role does not self-certify C-012.
- Required environment: Figma desktop app via MCP; repository working tree.

## Iteration ledger

### Iteration 1

- Target criterion: setup (C-013)
- Hypothesis: research + contract + task are prerequisites to a grounded build.
- Change or investigation: researched requirements + linking model; created task 86ajxxqtp; authored this contract.
- Verifier executed: python3 scripts/validate_goal_contract.py (pending)
- Result: pending
- New evidence: task 86ajxxqtp; research report
- Decision: iterate

### Iteration 2 — build + QA + fixes

- Target criteria: C-001..C-012
- Change: built 18 frames (builder + 4 inspector variants + 2 link modals + 10 state frames + populated console panel) reusing Design-2.0 tokens/components; wrapped in section 614:124; wrote SERVICE-PLAN-2.0-HANDOFF.md; created backend (86ajxxuye) + frontend (86ajxxuz9) follow-ups. Ran an independent 5-reviewer design-QA (0 critical, 4 major, 20 total); fixed all 4 major + the systemic seed-data/copy minors; re-verified reorder + others by screenshot.
- Verifier executed: per-frame get_screenshot; design-QA workflow wf_cb0e80b6-299; targeted re-screenshots.
- Result: no outstanding critical/major; coverage complete.
- New evidence: QA report + fix log in handoff §9.
- Decision: complete

## Risks and rollback

- Risks: (1) linking is net-new modelling — design may over/under-specify; mitigate by grounding in ADR-0020 + flagging the model gap. (2) two surfaces (builder + console) risk inconsistency; mitigate by reusing tokens + the console reference. (3) large frame count; build + verify incrementally.
- Rollback or recovery: additive frames; any faulty frame deletable without touching existing designs; handoff version-controlled.

## Pause and escalation conditions

- Escalate the PlanItem content-reference model to architect/backend (follow-up task) — does not block the design.
- Pause if Figma MCP disconnects (BLOCKED with the requirement).
- Escalate scope changes (redesigning the deck editor / library) rather than absorbing silently.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-design-service-plan.md --require-complete
- Validator result: PASS (all mandatory criteria PASS)
- Independent verification result: 5-reviewer design-QA (0 critical, 4 major); all major + systemic minors fixed and re-verified.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted to task 86ajxxqtp
