# Goal Contract — GOAL-be-presentation-search

## Identity

- Goal ID: GOAL-be-presentation-search
- Parent goal ID: 86ajvpngr (Presentations Library)
- Title: Global presentation search — ⌘/Ctrl+S opens a search modal that finds presentations by NAME and SLIDE CONTENT (operator-local deck library), and opens the chosen deck in the editor
- Role: backend-engineer (+ frontend-engineer for the modal)
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: TBD — link to the Presentations Library epic on next ClickUp sync
- Created: 2026-08-12
- Updated: 2026-08-12
- Maximum iterations: 10
- Independent verification required: yes

## Objective

A global keyboard-triggered (⌘/Ctrl+S) search modal that matches presentation names AND the text on their slides across the operator-local deck library, and opens the selected presentation in the Presentation editor — reusing the existing deck library, slide-text extraction, and the command-palette accessible-modal pattern.

## Baseline

Verified: presentations/decks are operator-owned (`selahcue-operator`, `deck_library.rs` `DeckLibrary` of `SlideDeck`s; Tauri `deck_*` commands in `main.rs`). `deck_list` returns only `{id, name, slide-count}` — no slide text — so content search needs a new command. Slide text is cheaply extractable via `AuthoredSlide::confidence_slide().body: Vec<String>` (visible text boxes in reading order; already used for picker labels, `deck_library.rs:292`). `⌘S` is currently unbound (browser default = Save). A ⌘K command palette + `pm-lib-q` library filter already exist; this adds a dedicated global presentation search. Owner has concurrent WIP in the same files (main.rs/app.js/index.html — undo/redo, STT), no search overlap.

## Inputs and evidence sources

- `deck_library.rs` (`DeckLibrary`, `DeckMeta`, `list`, `get`, `slide_list`), `deck_workspace.rs`, `main.rs` (`deck_*` Tauri commands)
- `selahcue-present` `deck.rs` (`SlideDeck::slides`, `AuthoredSlide::confidence_slide -> Slide { body: Vec<String> }`)
- `dist/app.js` command-palette modal (`wireCommandPalette`) + global keydown capture handler; `dist/index.html` `#cmd-palette`; `dist/app.css` `.cmd-*`
- `scripts/operator_headless.py` (behavioural check); `PRESENTATIONS-LIBRARY-spec.md`

## Scope

### In scope

- `DeckLibrary::search(query, limit) -> Vec<SearchHit>` — case-insensitive substring match on deck name + each slide's `confidence_slide().body` lines; bounded (total cap + one hit per matching slide); deterministic order (name-sorted decks, name-match before content-match).
- `deck_search` Tauri command wrapping it, returning JSON hits (`deck_id, name, slide_id?, slide_index?, snippet?, kind`).
- Global ⌘/Ctrl+S handler (capture, `preventDefault` the browser save) → opens the search modal from ANY surface.
- Search modal (dialog/listbox, a11y: roving/active option, ↑/↓, Enter, Esc, aria-modal) — debounced `deck_search`; renders name + matched-slide snippet; empty/no-result states.
- Select a result → `deck_open` → `showSurface("presentation")` with the deck loaded.

### Non-goals

- Searching scripture / plan items / settings (this is presentation-only)
- Server/host-side search (decks are operator-local, DEC — deck-library-is-operator-owned)
- Fuzzy ranking beyond substring + name-before-content ordering
- Staging/going live from the result (open-in-editor only, per the product answer)

### Constraints

- Bounded results (no unbounded scan/allocation): a hard result cap; snippet length-capped.
- `confidence_slide()` is cheap (no pixel render) — safe across all decks.
- Untrusted slide text → `textContent` in the modal, never `innerHTML`.
- ⌘S must not blank live output / must be inert while a modal or the app menu is open.
- Additive only: no change to `deck_list`/existing deck commands; operator stays compile-checked (CI) + headless-checked.

### Assumptions and unknowns

- ASSUMED: "presentation" = a deck in the operator library (confirmed by product answer: names + slide content).
- ASSUMED: open-in-editor on select (product answer); staging is out of scope.

## Dependencies and approvals

- Product decisions RESOLVED (2026-08-12): scope = names + slide content; on select = open in editor.
- Concurrent-WIP coordination: owner editing the same files (additive, distinct regions) — stage only this feature's hunks.
- Independent review (code-reviewer) before VERIFIED_COMPLETE.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `DeckLibrary::search` matches name + slide content, bounded, deterministic | `cargo test --manifest-path .../selahcue-operator/Cargo.toml search` | name-only match, content match with snippet, no-match empty, result cap respected | deck_library.rs + its unit test | PASS |
| C-002 | yes | `deck_search` Tauri command exposes the search and is registered | operator `cargo check` + grep the invoke_handler | command compiles + is in the handler list; returns JSON hits | main.rs | PASS |
| C-003 | yes | Global ⌘/Ctrl+S opens the search modal from any surface, preventing the browser save; inert while a modal/menu is open | headless: dispatch ⌘S keydown, assert modal open + defaultPrevented | modal opens; not while palette/menu open | scripts/operator_headless.py | PASS |
| C-004 | yes | Modal searches (deck_search) + renders results (name + slide snippet) with dialog/listbox a11y (↑/↓/Enter/Esc, aria-modal) | headless: type a query, assert result rows + roles + keyboard nav | results render; roles present; Esc closes | scripts/operator_headless.py; index.html; app.js | PASS |
| C-005 | yes | Selecting a result opens the deck (deck_open) + switches to the Presentation surface | headless: click/Enter a result, assert deck_open called + surface-presentation active | deck_open(id) invoked; surface switches | scripts/operator_headless.py | PASS |
| C-006 | yes | Operator compile-check + full headless suite pass; no regression; deck_list + existing commands unchanged | `cargo check --manifest-path .../Cargo.toml` + `python3 scripts/operator_headless.py` | compile OK; headless all-pass (≥ prior count); no existing-deck-command change | CI evidence | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` (search unit test); `python3 scripts/operator_headless.py` (modal behaviour).
- Broader regression verification: `cargo check --manifest-path .../selahcue-operator/Cargo.toml` (operator compiles); full headless suite must not shrink.
- Independent verifier: code-reviewer before VERIFIED_COMPLETE; the implementer may not self-approve.
- Required environment: Rust (operator manifest, excluded from workspace) + headless Chrome (`operator_headless.py`).

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002 (backend search + command)
- Hypothesis: `DeckLibrary::search` over `confidence_slide().body` + a thin `deck_search` command delivers name+content search without touching `deck_list`.
- Change or investigation: implement `DeckLibrary::search` + `SearchHit`, register `deck_search`, add a unit test.
- Verifier executed: pending.
- Result: pending.
- Decision: iterate to the modal (C-003..C-005), then C-006 + code-review gate.

## Risks and rollback

- Risk: unbounded scan on a huge library. Mitigation: hard result cap + per-slide single hit + cheap text extraction; bounded-result assertion in the test.
- Risk: ⌘S collides with the browser save / concurrent keymap edits. Mitigation: capture-phase preventDefault, gated (menu/modal open) like the other global keys; edit a distinct keymap region.
- Risk: concurrent-WIP conflict in main.rs/app.js/index.html. Mitigation: additive, distinct regions; stage only this feature's hunks.
- Rollback: purely additive (new command + new modal + new keybind) — reverting removes them with no change to existing deck commands or surfaces.

### Iteration 2 — boot-break resolved (it was NOT the owner's index.html)

- Investigated the "app never booted" blocker (user asked to fix it). Instrumented the real working
  tree: BOOTSTATE `calls=488 tdbg=true`, no uncaught errors — the webview BOOTS FINE. Root cause was a
  harness **boot-wait timing race**: `tries>60` (1.8s) gave up before the async boot completed under
  Chrome `--virtual-time-budget`, now that the DOM grew (owner's dl-modal + this feature's modal).
  HEAD index.html booted within the window; the larger current one didn't. Fix: `tries>60` → `tries>300`.
- Verifier: `python3 scripts/operator_headless.py` → **612 checks, 0 FAIL** (incl. 14 gsearch tests).
  `cargo test ...selahcue-operator search` (unit) + `cargo check`/`clippy`/`fmt` clean.
- Result: C-001..C-006 PASS. Remaining: independent code-review + the commit decision.
