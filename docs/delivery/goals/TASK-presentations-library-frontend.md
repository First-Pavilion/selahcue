# Goal Contract — TASK-presentations-library-frontend

## Identity

- Goal ID: TASK-presentations-library-frontend
- Parent goal ID: EPIC-86ajp072p (Service Planning & Library)
- Title: Presentations Library UI (browse · new · open · rename · duplicate · delete) in the operator webview
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: 86ajvt8q7
- Design: 86ajvpngr · `docs/design/PRESENTATIONS-LIBRARY-spec.md` · Figma `547:124`,`552:124`
- Backend: 86ajvqxy1 (commands `deck_list/new/open/rename/duplicate/delete` shipped)
- Created: 2026-08-04
- Updated: 2026-08-04
- Maximum iterations: 14
- Independent verification required: yes (adversarial review + `make ci`)

## Objective

Implement the Presentations Library UI in the operator webview so the user can **create a new presentation**
and **view/manage their presentations**, wiring the shipped `deck_*` library commands, matching the design +
reusing the shipped operator patterns (confirm dialog, toast, aria-busy).

## Baseline (Verified)

- Backend commands exist (86ajvqxy1): `deck_list()`→`{decks:[{id,name,slides}],open,persistent}`,
  `deck_new(name)`→DeckView, `deck_open(id)`→DeckView, `deck_rename(id,name)`→LibraryView,
  `deck_duplicate(id)`→LibraryView, `deck_delete(id)`→LibraryView. Registered but **not yet called by the webview**.
- The webview has `#surface-presentation` (the deck editor) with a static `pm-plan-name` chip + a disabled
  `pm-addplan` "later" stub. Reusable: `pmConfirm` (role=alertdialog), `pmToast` (role=status),
  `pmSetBusy`/aria-busy, the `pAct`/`invoke` one-round-trip pattern, the `.pm-asset` card grid CSS.
- `render_deck_slide` renders the OPEN deck only (no per-deck thumbnail command) → the Library uses branded
  placeholder tiles this pass (a `render_deck_thumb(id)` backend command is a documented follow-up).

## Inputs and evidence sources

- `docs/design/PRESENTATIONS-LIBRARY-spec.md`; `selahcue-operator/dist/{index.html,app.css,app.js}`;
  `scripts/operator_headless.py`; `selahcue-present/tests/test_tokens.rs`.

## Scope

### In scope
- A **Library view inside `#surface-presentation`** (not a nav change), entered via the topbar **deck-switcher
  breadcrumb** (`▦ <deck> ▾`, replacing the dead `pm-addplan` stub) and a **‹ Back to editor**.
- Grid of deck cards (branded thumb · name · "N slides" · ⋯) from `deck_list`; a **＋ New presentation** tile.
- **＋ New Presentation** → dialog (name) → `deck_new` → opens the editor.
- Card click / ⋯ **Open** → `deck_open` → opens the editor.
- ⋯ **Rename** (dialog) → `deck_rename`; **Duplicate** → `deck_duplicate`; **Delete** → `pmConfirm` + `deck_delete`
  + "Presentation deleted" toast.
- **Search** + **sort** (client-side over the list); **states**: empty · loading (aria-busy) · error (retry) ·
  **not-persistent** banner (`persistent:false`).
- a11y: grid `role=list`; cards keyboard-operable + labelled; ⋯ menu arrow/Esc; dialogs role=dialog/alertdialog +
  focus-trap; AA `--sc-*`; not colour-only. Reuse `pmConfirm`/`pmToast`/`pmSetBusy`.

### Non-goals (documented follow-ups)
- Per-deck live thumbnails (needs backend `render_deck_thumb(id)`); the service-plan browser; the list view;
  unifying the operator+desktop DB path.

### Constraints
- Compositor stays native (no HTML slide render); `--sc-*` AA; WKWebView-safe; every pinned needle preserved;
  the existing editor + its headless checks stay green; `make ci` green.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Deck-switcher breadcrumb opens the Library; ‹ Back returns to the editor; breadcrumb shows the open deck name | headless | toggles + names | `#pm-deckswitch`→`pmShowLibrary`; `#pm-lib-back`→`pmHideLibrary`; `pm-plan-name` updates; headless: opens/hides (computed display), shows the new deck's name | PASS |
| C-002 | yes | `deck_list` renders a card grid (name · N slides · ⋯) + a New tile; count/sort/search wired | headless | grid renders | `pmLibLoad`/`pmRenderLibGrid`; headless: 3 cards + New tile + count + open flag + search filters | PASS |
| C-003 | yes | ＋ New Presentation dialog → `deck_new(name)` → opens the editor on the new deck | headless | new→editor | `pmLibNew`→`pmPrompt`→`deck_new`; headless: `deck_new("Fresh Deck")` → editor + chip name | PASS |
| C-004 | yes | Card open → `deck_open(id)` → opens the editor on that deck | headless | open→editor | `pmLibOpen`; headless: card click → `deck_open` → editor | PASS |
| C-005 | yes | ⋯ Rename→`deck_rename`, Duplicate→`deck_duplicate`, Delete→`pmConfirm`+`deck_delete`+toast | headless | commands fire | `pmLibOpenMenu` + `pmLibRename/Duplicate/Delete`; headless: each command fires; Delete via role=alertdialog | PASS |
| C-006 | yes | States: empty · loading (aria-busy) · error (retry) · not-persistent banner | headless | states render | grid `aria-busy`; `#pm-lib-error` (role=alert) + retry; `#pm-lib-nopersist` (persistent:false); `#pm-lib-empty`; headless: banner + error+retry exercised | PASS |
| C-007 | yes | a11y: list/listitem, keyboard-operable cards + ⋯ menu, dialog roles + focus, AA, not colour-only | headless | a11y checks | grid role=list; cards = open-button + labelled ⋯; menu role=menu (arrows/Esc); `pmPrompt` role=dialog + trap; OPEN flag (not colour-only); `--sc-*` AA | PASS |
| C-008 | yes | `test_tokens` pin (Library needles) + `operator_headless` (+bump) | `cargo test` + headless | green | `operator_presentations_library_is_wired` pin (18/18); headless **303/0** (`EXPECTED_MIN_CHECKS` 279→303, +24) | PASS |
| C-009 | yes | Existing editor checks stay green (Library is additive) | headless | no regressions | all prior PM/editor checks still pass in the 303/0 run; Library is an additive view-mode | PASS |
| C-010 | yes | Full CI gate green | `make ci` | ALL GREEN | `make ci` == **local CI gate: ALL GREEN** (exit 0) | PASS |
| C-011 | yes | Independent adversarial review; confirmed Blocker/High fixed + re-verified | review workflow | none unresolved | 3-lens review done (state/bridge · a11y/UX · test-quality). State/bridge: **no Blocker/High/Medium**. a11y Findings 1–3 (focus lost to body after mutating/view-swap actions → `pmHideLibrary`+`pmLibFocusDeck` restore; ⋯ menu Tab/orphan → Tab-closes + `showSurface` dismiss; invisible focus-visible → real outline) **FIXED**. Test F1–F4 (id-crossing for open/delete, empty-state, search-no-results, ⌘N, delete-of-open switch) **STRENGTHENED** (headless 303→310). Finding 4 (shared `--sc-text-muted` sub-AA — an app-wide design-token decision, not this UI) logged as a follow-up. Re-verified: headless **310/0**, token pin **20/20**, `make ci` GREEN | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `node --check`; `operator_headless.py`; `test_tokens`. Broader: `make ci`.
- Independent: 3-lens adversarial review (state/bridge · a11y/UX · test-quality).

## Iteration ledger

- Iter 1–N: built the Library view (deck-switcher, card grid, New/Open/Rename/Duplicate/Delete,
  search/sort, empty/loading/error/not-persistent states), wired the six `deck_*` commands, added
  the `operator_presentations_library_is_wired` token pin + 24 headless checks. `make ci` GREEN.
- Iter final (2026-08-04): 3-lens adversarial review (state/bridge · a11y/UX · test-quality).
  Applied a11y fixes — focus restoration on view-swap/mutation (`pmHideLibrary` → deck-switcher,
  `pmLibFocusDeck` → affected card), ⋯ menu Tab-closes + dismiss on surface switch, visible
  menu focus outline; strengthened tests — id-crossing assertions for open/delete, empty-state,
  search-no-results, ⌘N, delete-of-open editor switch (headless 303→310, +2 a11y token needles).
  Finding 4 (shared-token contrast) logged as an app-wide follow-up. Re-verified all green.

## Risks and rollback

- Risk: the Library view breaks the existing editor toggle/tests. Mitigation: Library is an ADDITIVE view mode
  inside `#surface-presentation`; the editor stays the default; existing checks unchanged. Rollback: additive.
- Risk: no per-deck thumbnail command → placeholder tiles. Mitigation: branded placeholders + a documented
  `render_deck_thumb` follow-up (not blocking).

## Pause and escalation conditions

- Stop at `make ci` green + review clean + owner visual gate.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-presentations-library-frontend.md --require-complete`
- Validator result: PASS
- Independent verification result: PASS — 3-lens adversarial review; state/bridge clean, a11y
  Findings 1–3 fixed, tests F1–F4 strengthened, Finding 4 (shared-token contrast) is a logged
  app-wide follow-up. Re-verified: headless 310/0, token pin 20/20, `make ci` GREEN.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted to 86ajvt8q7 (moved to QA); BUILD CONTROL 86ajnx548 updated.
