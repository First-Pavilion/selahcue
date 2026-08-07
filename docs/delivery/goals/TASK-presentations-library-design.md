# Goal Contract — TASK-presentations-library-design

## Identity

- Goal ID: TASK-presentations-library-design
- Parent goal ID: EPIC-86ajp072p (Service Planning & Library) · related EPIC-86ajp07ce (Presentation & Slides)
- Title: Design the Presentations Library + "New Presentation" flow (create / view / manage decks)
- Role: ui-ux-designer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajvpngr
- Created: 2026-08-04
- Updated: 2026-08-04
- Maximum iterations: 8
- Independent verification required: yes (owner /build solution gate — design precedes implementation)

## Objective

Answer "how do we create a new presentation?" and "is there provision to view my presentations?" with
an implementation-ready **design**: a Presentations **Library** (browse/search/sort your decks), a **New
Presentation** create flow, and the manage states (empty, card menu, rename, duplicate, delete) — in Figma,
reusing Design 2.0 tokens/patterns, with a handoff spec precise enough to build without guessing.

## Baseline (Verified)

- The app has **no** create-new / browse-presentations today: the operator boots one hard-coded
  `DeckWorkspace::demo()`; the top-bar "plan chip" is a static label; "Add to plan" is a disabled *later*
  stub. The right panel is the **media-asset** library, not a presentations library.
- Product intent exists: PRD **FR-003** "Presentation library of reusable documents" (MVP); FR-001/005
  service plans. Architecture §8: `service_plan → plan_item → document`; a presentation = one authored deck.
- Backend foundation exists but is **unwired**: `selahcue-data/deck_repo.rs` persists a `deck` library table
  (`save_all`/`load_all`, keyed by name), round-trip tested — a documented "thin follow-up" (ADR-0020 dec. 7).
- No Figma frame for a presentations library / home / new-presentation flow existed before this task.

## Inputs and evidence sources

- PRD `docs/product/prds/SelahCue-PRD.md` (FR-001..008); `docs/architecture/ARCHITECTURE.md` §8;
  ADR-0007, ADR-0020; `docs/design/{PRESENTATION-MEDIA-STATES-spec.md,NAV-IA-spec.md,DESIGN-2.0-HANDOFF.md}`.
- Code: `selahcue-operator/{dist,src}`, `selahcue-present/src/deck.rs`, `selahcue-data/src/deck_repo.rs`.
- Figma file `SYQn5hFY8YVQKm3c6rw0eJ` (Design 2.0 column, `--sc-*` tokens pinned by `test_tokens.rs`).

## Scope

### In scope
- Figma: **Library** screen + **New Presentation** dialog + **Empty / card-menu / delete-confirm** states.
- Handoff spec: IA + entry points, screen anatomy, full state matrix, a11y annotations, content guidance,
  component/token reuse, backend command mapping + the name-keyed→stable-id risk.

### Non-goals (documented for follow-up)
- Implementation (a separate build story once the /build gate approves).
- The Service-Plan browser and the `PlanItem→deck` link (sibling story, ADR-0020 follow-up).
- Templates (shown as an honest disabled "later" option).
- The Loading/Error/No-results/List-view/editor-breadcrumb frames (documented in the spec; a follow-up frame).

### Constraints
- Reuse Design 2.0 `--sc-*` tokens + shipped patterns (confirm dialog, toast, aria-busy, card grid);
  thumbnails via the native compositor (never HTML render, ADR-0002/0003); AA contrast; never colour-only;
  destructive confirm = `role="alertdialog"` focus-trap + Esc; not inventing new backend (wire `deck_repo`).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Verified baseline: no create/view today; backend `deck_repo` exists; PRD FR-003 intent | this doc + 2 investigations | grounded, cited | Baseline above; two evidence-cited investigations | PASS |
| C-002 | yes | Library screen designed (grid, search, sort, New tile, cards w/ thumb+meta+⋯) | Figma screenshot | renders | Figma `547:124` (validated by screenshot) | PASS |
| C-003 | yes | "New Presentation" create flow designed (name, start-from, actions) | Figma screenshot | renders | Figma `552:124` ① | PASS |
| C-004 | yes | Empty + card-menu + delete-confirm (w/ in-plan warning) designed | Figma screenshot | renders | Figma `552:124` ②③ | PASS |
| C-005 | yes | Full state matrix incl. loading/error/no-results/rename/duplicate | spec §6 | complete | `PRESENTATIONS-LIBRARY-spec.md` §6 | PASS |
| C-006 | yes | a11y annotated: roles, keyboard, focus, contrast (AA), not colour-only | spec §7 | testable | spec §7 | PASS |
| C-007 | yes | IA + entry points (nav, editor breadcrumb, plan relationship) | spec §2 | specified | spec §2 | PASS |
| C-008 | yes | Content guidance + component/token reuse (no new tokens) | spec §8/§9 | specified | spec §8/§9 | PASS |
| C-009 | yes | Backend command mapping + name-keyed→stable-id risk flagged | spec §10 | mapped + risk | spec §10 | PASS |
| C-010 | yes | Handoff spec written + Figma nodes linked | spec + this doc | complete | `PRESENTATIONS-LIBRARY-spec.md` | PASS |
| C-011 | yes | ClickUp task created, linked to epic, handoff posted | ClickUp | linked | Task 86ajvpngr under epic 86ajp072p; full handoff in the description | PASS |
| C-012 | yes | Returned to /build solution gate with open decisions surfaced | this doc | GATE_REVIEW | spec §12 open decisions | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Figma frames validated by `get_screenshot` (Library `547:124`, Create & Manage `552:124`) — both render
  correctly on-brand. Spec self-reviewed for placeholders/contradictions/ambiguity.
- Independent: owner **/build solution gate** — approve the deck-library-first sequencing + the 3 open
  decisions (§12) before an implementation story is opened.

## Iteration ledger

### Iteration 1 — investigate + design
- Two evidence-cited investigations established the Verified baseline (no create/view; `deck_repo` exists;
  PRD FR-003; ServicePlan↔deck). Designed 2 Figma frames (Library `547:124`; Create & Manage `552:124`),
  validated by screenshot; wrote the handoff spec (`PRESENTATIONS-LIBRARY-spec.md`).
- Decision: terminal state **GATE_REVIEW** — design + handoff complete; implementation and the 3 open
  decisions belong to the /build gate, so this is not VERIFIED_COMPLETE.

## Risks and rollback

- **Name-keyed deck library** (ADR-0020): rename/duplicate need a stable deck id first, else history orphans.
  Flagged to Architect/Backend (spec §10). Design is unaffected (a rename is a rename regardless of key).
- **Surface ambiguity:** "Presentations" (decks) vs "Plan / Library" (plans). Spec designs the deck library
  and recommends shipping it first; the plan browser is a sibling. Escalated as an open decision (§12).

## Pause and escalation conditions

- Stop at design handoff + /build gate. Do not open an implementation story or write app code under this
  (design) role — hand off to backend/frontend after the gate approves.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-presentations-library-design.md`
- Validator result: PENDING
- Independent verification result: PENDING (owner /build gate)
- Terminal state: **GATE_REVIEW**
- Remaining failed or blocked criteria: none (all 12 PASS). Awaiting the owner /build gate on §12.
- ClickUp final evidence comment: task 86ajvpngr (handoff in the description) under epic 86ajp072p.
