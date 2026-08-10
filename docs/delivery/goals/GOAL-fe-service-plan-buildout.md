# Goal Contract — GOAL-fe-service-plan-buildout

## Identity

- Goal ID: GOAL-fe-service-plan-buildout
- Parent goal ID: 86ajxxqtp (STORY — Service Plan builder, Design 2.0)
- Title: Build out the backend-independent Service Plan frames in the operator webview — drag/Alt reorder, scripture verse-picker modal, presentation grid picker, inspector deck card + Open in editor — keeping make ci green
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy0hz1
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 20
- Independent verification required: yes

## Objective

Complete the Service Plan frames whose backend data/commands already exist (per `docs/design/SERVICE-PLAN-2.0-HANDOFF.md`, Figma section 614:124), building on the core builder (86ajxxuz9): (11) drag + keyboard Alt+↑/↓ run-sheet reorder; (6) the Link-Scripture modal build-out (chapter nav + verse list with selected range + verses-per-slide + preview); (7) the Link-Presentation grid picker (slide-count pills + New card + Grid/List); (2) the presentation-linked inspector deck card + Open in editor. Preserve the live-cueing invariant and accessibility; `make ci` green.

## Baseline

- Core builder shipped (86ajxxuz9, in review): palette · run sheet · inspector · link modals (basic) · console link chips · empty CTA · link states.
- Backend-ready commands/data for this scope: `move_item` (reorder), `Command::GetChapter` + `scripture_search` + `ContentLinkView.verses_per_slide` (scripture), `deck_list`/`deck_view`/`render_deck_slide` (decks), the Presentation editor surface.
- Out of scope (blocked on backend — 86ajy0hw0/86ajy0hwg/86ajy0hxg): owner/duration render, Plan Summary counts, permission/view-only, publish/change-badge, autosave/restore/recovery/undo, verse-numbers toggle.

## Inputs and evidence sources

- SERVICE-PLAN-2.0-HANDOFF.md §3-7; Figma frames 606:124, 608:124, 610:124, 610:390, 611:820.
- Gap matrix (this session). Operator webview `dist/{index.html,app.js,app.css}`; `operator_headless.py`; `test_tokens.rs`.
- Existing patterns to reuse: console Scriptures browser (`GetChapter`/verse list), Presentations Library grid (`deck_list`).

## Scope

### In scope
- Frame 11: run-sheet drag-and-drop with a drop indicator + keyboard **Alt+↑/↓** reorder; reduced-motion respected; reorder never sends a live-control command.
- Frame 6: Link-Scripture modal — reference + translation + chapter nav + verse list with the selected range highlighted + verses-per-slide footer + gold reference preview; commits via `set_item_content`.
- Frame 7: Link-Presentation modal — deck grid (slide-count pills, optional first-slide thumbnail) + Grid/List toggle + New-presentation card; select-then-confirm; commits `{kind:deck,id}`.
- Frame 2: presentation-linked inspector — deck card (name, slide count) + **Open in editor** (nav to Presentation surface with the deck open) + Change/Unlink.
- Accessibility (keyboard, focus-trap, labels, reduced motion) and the live-cueing invariant.

### Non-goals
- Any backend/wire change (delegated: 86ajy0hw0/86ajy0hwg/86ajy0hxg).
- Backend-dependent frames (Plan Summary, permission, publish, autosave/recovery, owner/duration render, verse-numbers).

### Constraints
- Reuse existing webview patterns + Design-2.0 tokens; no new framework.
- Keep `make ci` green (operator compile-check, `operator_headless.py`, `test_tokens.rs`).
- Preserve the live-cueing invariant + emergency chrome.

## Dependencies and approvals
- Independent review/QA — owner: code-reviewer/qa. Status: pending.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Keyboard **Alt+↑/↓** reorders the selected run-sheet item (persists via `move_item`; focus follows the moved row) | operator_headless.py | Alt+↓ sends `move_item{to:i+1}`; focus stays on the row | headless "SP2 C-001" PASS | PASS |
| C-002 | yes | Drag-and-drop reorder with a visible drop indicator; reduced-motion respected; sends no live-control command | headless / review | a drag reorders via `move_item`; drop line renders; 0 live-control cmds | headless "SP2 C-002" (drop line, lifted row, drop reorders, cancel no-op, teardown) PASS; screenshot | PASS |
| C-003 | yes | Link-Scripture modal: chapter nav + verse list with the selected range highlighted + verses-per-slide + preview; commit sends `set_item_content{scripture, reference, translation, verses_per_slide}` | headless / review | selecting verses builds the reference; commit payload carries verses_per_slide | headless "SP2 C-003" (picker+nav+verse-select+preview+verses_per_slide; edit-invalidates-stale-chapter) PASS; screenshot | PASS |
| C-004 | yes | Link-Presentation modal is a grid (slide-count pills + New card + Grid/List); select-then-confirm sends `{kind:deck,id}` | headless / review | grid renders; confirm sends the deck link | headless "SP2 C-004" (grid+pills+New card+Grid/List; New-card create+link + double-activation guard) PASS; screenshot | PASS |
| C-005 | yes | Presentation-linked inspector shows a deck card (name + slide count) + Open-in-editor (nav to Presentation surface) + Change/Unlink | headless / review | deck card renders; Open-in-editor activates `#surface-presentation` | headless "SP2 C-005" PASS; screenshot | PASS |
| C-006 | yes | Live-cueing invariant preserved + a11y (keyboard, focus-trap, labels, reduced motion) | headless / review | no plan edit sends Go-Live; modals focus-trap; controls labelled | headless "SP2 C-006" (aria-hidden handle, aria-multiselectable verse list, New card outside listbox) + invariant check (0 live-control) PASS; adversarial a11y lens | PASS |
| C-007 | yes | `make ci` is green (operator check + headless webview + test_tokens + all suites) | `make ci` | exit 0 | final run exit 0: **headless 515 checks/0 FAIL** (REQUIRE=1) + test_tokens 18 + flutter 95; banner "== local CI gate: ALL GREEN ==" | PASS |
| C-008 | yes | ClickUp 86ajy0hz1 carries goal ID, engine, iteration evidence, terminal state | inspect task comments | start + evidence comments present | ClickUp 86ajy0hz1 start + evidence comments | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan
- Focused: `operator_headless.py` (new "SP2" checks per frame); targeted DOM/behaviour inspection; `test_tokens.rs` needles.
- Broader regression: full `make ci`.
- Independent verifier: adversarial multi-agent review (wiring · a11y · invariant · WKWebView · regression · fidelity), as in 86ajxxuz9.

## Iteration ledger

### Iteration 1
- Target criterion: setup (C-008)
- Hypothesis: a gap matrix (design ↔ current FE ↔ wire data) is a prerequisite; the backend-independent frames are 2, 6, 7, 11.
- Change or investigation: dispatched a gap-analysis scout; created backend stories 86ajy0hw0/86ajy0hwg/86ajy0hxg + this FE story; authored this contract.
- Verifier executed: python3 scripts/validate_goal_contract.py
- Result: contract valid
- Decision: iterate

### Iteration 2 — build the four backend-independent frames
- Target criteria: C-001..C-006
- Change: Frame 11 (pointer drag reorder + drop line + Alt+↑/↓ + handle); Frame 2 (`planDeckCard` + Open-in-editor); Frame 7 (`planDeckBody` → Grid/List grid + slide-count pills + New card + select-then-confirm); Frame 6 (`planScriptureBody` → verse picker: chapter nav + verse list + verses-per-slide + gold preview). +CSS. Reused `move_item`/`get_chapter`/`deck_list`/`deck_view`/`pmLibOpen`.
- Verifier executed: `operator_headless.py` (added SP2 checks per frame); `test_tokens`; operator `cargo check`; 3 screenshots.
- Result: 509 checks/0 FAIL; test_tokens 18; compile clean; visuals match the handoff.
- Decision: iterate (independent review).

### Iteration 3 — adversarial review + fixes + closure
- Target criteria: C-003..C-006
- Change/investigation: 5-lens adversarial review (reorder · scripture · deck-grid/card · invariant-a11y · regression-critic), find→verify. 6 confirmed (2 refuted). Fixed: (1) editing the reference invalidates the stale browsed chapter so the typed reference wins; (2) New card aborts if the dialog is dismissed mid-flight; (3) New card double-activation guard; (4) verse list `aria-multiselectable`; (5) inspector Unlink/rename keep row focus; (6) New card moved outside the deck `role=listbox`. Dropped the risky New-deck fallback defensively.
- Verifier executed: `operator_headless.py` (added fix checks); full `make ci`.
- Result: ALL GREEN — **515 checks/0 FAIL**; flutter 95.
- Decision: complete → VERIFIED_COMPLETE; hand off to code review.

## Risks and rollback
- Risks: (1) large plain-JS surgery — regression risk; mitigate incrementally + headless after each step. (2) drag-and-drop in WKWebView — verify pointer events, not just Blink. (3) reuse fidelity vs rebuild — reuse the Scriptures browser + library grid.
- Rollback: dist edits are additive; revert per-hunk.

## Pause and escalation conditions
- Escalate design ambiguity to /ui-ux-designer.
- BLOCKED if a frame needs wire data not yet delivered by 86ajy0hw0/hwg/hxg (it is then out of scope here).

## Final evaluation
- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-fe-service-plan-buildout.md --require-complete
- Validator result: PASS (all 8 mandatory criteria PASS)
- Independent verification result: PASS — 5-lens adversarial review; 6 confirmed findings all fixed + headless-covered, 2 refuted correctly. Not self-certified: C-007 is the objective `make ci` gate.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none. The backend-dependent Service Plan frames (5, 9, 13, 14, 16, 17 + owner/duration render + verse-numbers toggle) are out of scope here and tracked on 86ajy0hw0 / 86ajy0hwg / 86ajy0hxg.
- ClickUp final evidence comment: posted on 86ajy0hz1; task moved to code review.
