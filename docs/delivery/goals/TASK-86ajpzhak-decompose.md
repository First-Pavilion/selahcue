# Goal Contract — TASK-86ajpzhak-decompose

## Identity

- Goal ID: TASK-86ajpzhak-decompose
- Parent goal ID: STAGE8-core-presentation
- Title: Decompose the Themes + templates story (S8-3, FR-010) into gated, dependency-ordered sub-stories in ClickUp — design-first — with no implementation
- Role: delivery-manager
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajpzhak
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 4
- Independent verification required: no (planning artefact; the gate is the user)

## Objective

Story 86ajpzhak (Themes + templates, S8-3) is a whole subsystem — FR-010 "Reusable templates and themes (fonts, colours, safe areas, positions) — applying a theme restyles a slide group without losing content; theme editable centrally" — flagged for decomposition in PRD-REVIEW-stage3. A theme is a ProPresenter/Pewbeam-style slide-design template the audience output uses to render scriptures/songs/lower-thirds (memory: themes-are-design-templates). The story mandates designing the Theme Designer in Figma FIRST (via /ui-ux-designer). Split it into gated sub-stories with one owner + acceptance + dependencies each, ordered design→build, so each is independently gated.

## Baseline

Verified from ClickUp:
- Epic 86ajp07ce (Presentation & Slides) UX names "Presentation Editor, **Theme Designer**, Song Editor (Figma)"; acceptance "theme applies without content loss".
- Sibling stories under the epic: S8-1 songs (86ajpzha3, qa), S8-2 shaping (86ajpzha7, qa — DONE + CI-green), **S8-4 editor (86ajpzhan)** — owns FR-011/014/021/022 (layered editor, undo/redo ≥20, command palette) and **depends on S8-3**. So FR-015/016 (palette/undo) belong to S8-4, NOT this story; S8-3 = FR-010 (themes/templates + Theme Designer), FR-017 shaping already delivered by S8-2.
- Repo spec: FR-009/FR-010 (PRD lines 115–116); COMPONENT-SPECS.md (§ editor `applying-template`, "Template dropdown restyles the whole group without losing content — FR-010"; per-output scripture template FR-011/029).
- A first (reverted, uncommitted) implementation attempt modelled a theme as a colour scheme — corrected on 2026-07-25; the tree is clean at commit 07468a9.

## Inputs and evidence sources

- Story 86ajpzhak + epic 86ajp07ce + sibling S8-4 86ajpzhan (ClickUp); FR-009/010 (PRD); COMPONENT-SPECS.md; ProPresenter Themes docs + the Pewbeam Theme Designer screenshot (owner-supplied); memory themes-are-design-templates.

## Scope

### In scope

- Create sub-stories of 86ajpzhak (subtasks; codes S8-3a..S8-3d), each with one owner, actionable scope, acceptance, tests, and dependencies:
  - **S8-3a DESIGN** (/ui-ux-designer): the Theme Designer UI flow + the theme MODEL spec in Figma — fonts, colours, safe-areas, positions/regions; per-role layouts for scripture / song / lower-third; the template concept; per-item override; New/Import/Export + Scriptures/Slides tabs + element inspector (Layout/Alignment/Position/Dimension/Typography). Design-gated before build.
  - **S8-3b ENGINE** (/backend-engineer + frontend integration): the theme render model + apply to the audience output — a themed scripture/song/lower-third renders per the design; switching restyles with ZERO content loss; persistence + recovery. Depends on S8-3a + S8-2.
  - **S8-3c DESIGNER UI** (/frontend-engineer): the in-console Theme Designer per S8-3a — create/edit/duplicate/import/export + live preview. Depends on S8-3a + S8-3b.
  - **S8-3d TEMPLATES + OVERRIDE** (/frontend-engineer + backend): reusable template slides + per-item theme/template override, applied without content loss; recovery preserves the per-item choice. Depends on S8-3b.
- Dependency links (design blocks build); keep the S8-2 dependency; the parent story becomes the umbrella (description updated: FR-010 focus, FR mapping corrected).
- Update BUILD CONTROL 86ajnx548.

### Non-goals

- Any implementation, Figma design work, or code (later batches). Changing epic/story acceptance owned by Product (only correcting the imprecise FR line with evidence). Adding statuses/fields or restructuring the workspace.

### Constraints

- No duplicates (search first — done); reuse existing hierarchy + statuses; one accountable owner each; acyclic dependency graph; no repository shadow backlog (ClickUp is source of truth; this contract is execution evidence only).

### Assumptions and unknowns

- ASSUMED: sub-stories as subtasks of 86ajpzhak (natural decomposition, not a workspace restructure). ASSUMED: S8-3a can start with no hard code dependency (leverages the shipped console + design system). VALIDATION: the gate.

## Dependencies and approvals

- The user gate approves which sub-story becomes the next batch (recommended: S8-3a design). S8-2 (shaping) done.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | ClickUp searched for existing theme sub-stories — no duplicates created | clickup_search | no dup; decomposition is net-new | search done (only 86ajpzhak + S8-4 exist) | PASS |
| C-002 | yes | 4 sub-stories exist under 86ajpzhak, each with one owner, scope, acceptance, tests, and requirement link (FR-010) | clickup task reads | 4 sub-stories created, schema-complete | S8-3a 86ajq14ud, S8-3b 86ajq14vq, S8-3c 86ajq14wa, S8-3d 86ajq14wn | PASS |
| C-003 | yes | Dependencies set: S8-3b→S8-3a, S8-3c→(S8-3a,S8-3b), S8-3d→S8-3b; S8-2 dependency retained; graph acyclic; design blocks build | dependency review | acyclic; design-first ordering | 3b→3a; 3c→3a,3b; 3d→3b (all waiting_on); acyclic; S8-2 via umbrella | PASS |
| C-004 | yes | Parent story 86ajpzhak reframed as the umbrella (FR-010 focus; imprecise FR-015/016 line corrected with the S8-4 evidence) | task read | description updated | 86ajpzhak reframed as umbrella; FR-015/016→S8-4 corrected | PASS |
| C-005 | yes | BUILD CONTROL 86ajnx548 updated with the decomposition + recommended first batch | task comment | comment posted | BUILD CONTROL comment 90130296642632 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Read back each created sub-story + the dependency links; confirm the parent umbrella + BUILD CONTROL updates. Environment: ClickUp.

## Iteration ledger

### Iteration 1

- Target: C-001..C-005
- Change: searched ClickUp (no dups); read epic 86ajp07ce + sibling S8-4 86ajpzhan (carved the theme/editor boundary); created 4 sub-stories under 86ajpzhak; wired the dependency graph (design blocks build); reframed the parent umbrella + corrected the FR-015/016 mapping to S8-4; updated BUILD CONTROL.
- Result: all 5 criteria PASS.
- Decision: gate-review (user selects the next batch; recommended S8-3a design).

## Risks and rollback

- Risk: over-decomposition. Mitigated: 4 coherent slices matched to owners (design / engine / designer-UI / templates+override), not micro-tasks. Rollback: sub-tasks can be merged/closed with approval.

## Pause and escalation conditions

- The user gate selects the next batch; no build until S8-3a design is gated.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajpzhak-decompose.md --require-complete`
- Validator result: PASS --require-complete (5/5)
- Terminal state: GATE_REVIEW (decomposition done; user selects the next batch)
- ClickUp final evidence comment: BUILD CONTROL 90130296642632 + story 86ajpzhak reset comment
