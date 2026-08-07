# Goal Contract — TASK-presentation-media-states-design

## Identity

- Goal ID: TASK-presentation-media-states-design
- Parent goal ID: EPIC-86ajp07ce (Presentation & Slides)
- Title: Presentation & Media — interaction & element-selection state design (node 329:124)
- Role: ui-ux-designer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajvjqw4
- Created: 2026-08-04
- Updated: 2026-08-04
- Maximum iterations: 8
- Independent verification required: yes (design self-review against the role checklist + owner gate)

## Objective

Produce the missing **state designs** for the Presentation & Media surface (Figma 329:124) — every
interaction/system state (element selection incl. image-specific, empty, media, present/live,
transition/auto-advance editing, destructive, loading, error) — as **Figma state frames + a state
spec**, with the owner-chosen **right-side per-element inspector** model, so the surface can be
implemented/verified correctly and the design is the source of truth.

## Baseline

**Verified:**
- Node 329:124 shows a single default state (a text element selected with a selection box + 8 handles);
  no image-selected, empty, media-selection, present/live, or destructive states are designed.
- The shared element-editing state model + a11y already exist in prose: `docs/design/CANVAS-EDITING-spec.md`
  (86ajq6j29) §7 (10-state matrix), §1 (selection overlay), §2/§4 (interactions/add-flow), §8 (a11y),
  and **§11 flags the Figma frames as "the next phase, post-approval."** `docs/design/UX-STATE-MATRIX.md`
  §5 covers the editor's Default/Loading/Empty/Populated/Error/Permission-denied states.
- The surface is **already implemented** (86ajvccqr, QA): on-canvas selection (`#pm-sel` box) + keyboard
  (Tab-cycle, arrows, `[`/`]` z, `H` hide, Delete) + a LIVE badge + media missing/unused — but **no
  right-side inspector**. The owner chose the inspector model → this design leads implementation (rework).
- Design system: `--sc-*` tokens (`app.css`), Design-2.0 language; the Theme Designer already has a
  right inspector to mirror.

## Inputs and evidence sources

- Figma 329:124 + the shipped `dist/` surface (86ajvccqr).
- `docs/design/{CANVAS-EDITING-spec,UX-STATE-MATRIX,COMPONENT-SPECS,THEME-MODEL-spec,DESIGN-TOKENS,UX-CANONICAL}.md`.
- The engine model (ADR-0020; `AuthoredSlide.elements` = Text/Shape/Image; `MediaLibrary`).

## Scope

### In scope

- **State spec** `docs/design/PRESENTATION-MEDIA-STATES-spec.md`: the full state matrix (below) with
  visual · interaction · entry/exit · keyboard/focus · aria/SR · contrast · content, per state; the
  **per-element inspector** design (text/shape/image, incl. image replace/fit) + the **right-panel
  context switch** (Media Library ⟷ Inspector); traceability (state → Figma frame → shipped-impl/rework
  → requirement).
- **Figma frames** under the 329:124 page ("Presentation & Media — States" section): the key state
  frames, annotated, reusing `--sc-*` tokens + existing components.
- A **follow-up implementation task** (add the per-element inspector + right-panel switch to the surface),
  since this design leads the shipped UI.

### States to cover (the matrix)

Element selection: **default/none · text selected · shape selected · image selected** (+ image missing);
Empty: **empty deck · empty slide · empty/filtered media library**; Media: **default · hover · selected ·
missing · unused · importing/loading**; Playback: **present/live**; Editing: **transition open ·
auto-advance open**; Destructive: **delete slide · delete element · remove media (confirm)**; System:
**loading · error/decode-fail · permission-denied (View only)**.

### Non-goals

- Re-specifying the shared element-editing model (reference CANVAS-EDITING-spec, don't duplicate).
- Redesigning the base 329:124 layout beyond the right-panel inspector context.
- Mobile (the editor is desktop-only, UX-STATE-MATRIX §5).
- Implementing the inspector (that is the follow-up build task).

### Constraints

- Reuse `--sc-*` tokens (WCAG-AA); never colour-only state; keyboard-operable + SR-announced per state;
  Preview→Live isolation (FR-012) preserved in every editing state; compositor stays native (canvas is a
  preview). Design references, not duplicates, the existing specs.

### Assumptions and unknowns

- ASSUMED: the right panel toggles between Media Library (default) and the per-element Inspector (on
  selection) within the existing 360px column — no 4th column. Validate in the spec.

## Dependencies and approvals

- Owner scope decisions (deliverable form + inspector model) — approved this session.
- Figma MCP available for authoring. If unavailable → spec ships + frames become a BLOCKED sub-item.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The state spec covers EVERY state in the matrix, each with visual · interaction · entry/exit · a11y · content | self-review vs the matrix | one row/section per state; none missing | `PRESENTATION-MEDIA-STATES-spec.md` §3–§6 cover all matrix states | PASS |
| C-002 | yes | The per-element **inspector** is designed for text/shape/image (incl. image replace/fit) + the right-panel **context switch** (Media ⟷ Inspector) | spec section + Figma | inspector variants + switch specified | §2/§2a (switch + 3 inspector variants incl. Image Replace/Fit) + Figma 510:126/511:124/511:158/512:124 | PASS |
| C-003 | yes | Figma state frames authored under the 329:124 page, annotated; node ids returned + a screenshot | `use_figma` + `get_screenshot` | frames exist; screenshot shows them | States board **509:124** (below 329:124): 4 inspector panels + canvas selection + 12-tile gallery; screenshot verified | PASS |
| C-004 | yes | a11y per state: focus order, roles, aria, live-region announcements, keyboard, contrast — testable | self-review | a11y column complete + AA | spec §10 + per-state aria/SR columns; `--sc-*` AA (test_tokens-pinned); never colour-only | PASS |
| C-005 | yes | Content/copy for empty · error · missing · delete-confirm · permission-denied | spec | copy present + action-oriented | §5/§6 carry the copy (empty/missing/relink/confirm/View-only) | PASS |
| C-006 | yes | Traceability: each state → Figma frame + shipped-impl-or-rework + requirement; the design↔impl inspector divergence documented + a follow-up build task linked | spec table + ClickUp | mapping complete; follow-up created | §7 traceability table + §8 delta; follow-up **86ajvjtax** created | PASS |
| C-007 | yes | Reuses the design system + references (not duplicates) CANVAS-EDITING-spec / UX-STATE-MATRIX | self-review | tokens + cross-refs; no duplication | uses the `SelahCue Color` vars / `--sc-*`; references CANVAS-EDITING-spec §1/§2/§7/§8 + UX-STATE-MATRIX §5 | PASS |
| C-008 | yes | Goal Contract validates; handoff posted; design story + frames linked in ClickUp | validator + handoff | PASS + comment | validator PASS; handoff posted to 86ajvjqw4 + BUILD CONTROL | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Self-review against the role quality checklist (all states designed; a11y testable; copy clear;
  references precise enough to implement without guessing) + the state matrix (nothing missing).
- Independent verifier: owner design gate (visual) + the QA/build role reading the spec for the rework.
- Required environment: repo (docs) + Figma MCP (authoring).

## Iteration ledger

### Iteration 1 — state spec + Figma states board
- Grounded the gap: 329:124 shows one state; the element-editing state *prose* already exists
  (CANVAS-EDITING-spec §7/§11, UX-STATE-MATRIX §5) but the **visual states** + the Presentation-specific
  states + the owner's **inspector model** were undesigned.
- Wrote `docs/design/PRESENTATION-MEDIA-STATES-spec.md`: the right-panel **Media⟷Inspector context switch**,
  the **per-element inspector** (Text/Shape/Image incl. **image Replace/Fit + Missing→Relink**), the full
  state matrix (selection · empty · media · present/live · transition/auto-advance · destructive · system),
  per-state a11y + copy, the §7 traceability table, and the §8 design↔impl delta.
- Authored the Figma **"Presentation & Media — States" board (509:124)** below 329:124: ① 4 right-panel
  variants, ② the canvas selection schematic (box + 8 handles + z-badge), ③ a 12-tile state gallery — all
  on the file's `SelahCue Color` variables; screenshot-verified.
- Created the implementation-rework follow-up **86ajvjtax** (the inspector model leads the shipped UI).
- **Decision:** complete — all 8 criteria PASS; owner design gate is the final visual check.

## Risks and rollback

- Risk: the inspector model diverges from the shipped UI → rework. Mitigation: an explicit follow-up
  build task + a documented design↔impl delta; the shipped on-canvas+keyboard model stays valid as the
  interim. Rollback: the spec/frames are additive design artefacts.
- Risk: duplicating CANVAS-EDITING-spec. Mitigation: reference + extend, don't restate.

## Pause and escalation conditions

- Stop at the owner design gate. Escalate if the inspector model needs a base-layout change beyond the
  right panel (that would be a broader redesign decision).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-presentation-media-states-design.md --require-complete`
- Validator result: PASS (8/8 mandatory PASS)
- Independent verification result: design self-review vs the role checklist + the state matrix (no state
  missing); owner design gate is the final visual check.
- Terminal state: **VERIFIED_COMPLETE**
- Remaining failed or blocked criteria: none.
- ClickUp final evidence comment: posted to 86ajvjqw4 + BUILD CONTROL 86ajnx548; follow-up 86ajvjtax created.
