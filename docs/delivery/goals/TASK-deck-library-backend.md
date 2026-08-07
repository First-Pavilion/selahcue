# Goal Contract — TASK-deck-library-backend

## Identity

- Goal ID: TASK-deck-library-backend
- Parent goal ID: EPIC-86ajp072p (Service Planning & Library)
- Title: Deck library persistence + commands (deck_list/new/open/rename/duplicate/delete)
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajvqxy1
- Design source: 86ajvpngr · `docs/design/PRESENTATIONS-LIBRARY-spec.md` §10
- Created: 2026-08-04
- Updated: 2026-08-04
- Maximum iterations: 14
- Independent verification required: yes (adversarial review + `make ci`)

## Objective

Wire the existing-but-unwired deck persistence (`selahcue-data::deck_repo`) into the operator and add the
deck-library commands the Presentations Library / New-Presentation UI needs, with a **stable deck id** so
rename/duplicate are safe — implementing the design handoff (86ajvpngr §10).

## Baseline (Verified)

- `selahcue-data::deck_repo::{save_all(&Database,&[(String,String)]), load_all(&Database)->Vec<(String,String)>}`
  exist + round-trip tested; table `deck(name PK, deck_json)` at schema v16 (unconditional). `deck_json` = serde
  of `selahcue_present::SlideDeck` (`{name,slides,next_id}`). `Database::{open(path),open_in_memory()}` (WAL).
- `SlideDeck` has `pub name` + private `slides`/`next_id`; **no top-level deck id**.
- Operator is **Tauri v2**; `AppState{ backend, deck: Mutex<DeckWorkspace> }` seeded `DeckWorkspace::demo()`;
  **no `selahcue-data` dep, no DB, no persistence**. `with_deck` returns `ws.view()`.
- OS-data-dir + `selahcue.db3` open pattern exists in `selahcue-desktop` (to mirror).

## Inputs and evidence sources

- `crates/selahcue-present/src/deck.rs`; `crates/selahcue-data/src/{deck_repo.rs,db.rs,lib.rs}`;
  `crates/selahcue-operator/{Cargo.toml,src/{main.rs,deck_workspace.rs}}`; `selahcue-desktop/src/main.rs`
  (`data_dir()`). Design: `PRESENTATIONS-LIBRARY-spec.md`.

## Scope

### In scope
- `selahcue-present`: `DeckId` newtype + additive `SlideDeck.id` (serde `default` → library self-heals a
  missing/zero/duplicate id, mirroring slide `mint_id`); `deck.id()` accessor. Byte-stable when default.
- `selahcue-data`: **additive** `deck_repo::save_one(&Database,name,deck_json)` (INSERT OR REPLACE) +
  `delete_one(&Database,name)`. Keep `save_all`/`load_all`. No schema migration, no signature break.
- `selahcue-operator`: add `selahcue-data` dep; a `DeckLibrary` owning the deck set + a best-effort
  `Database` (opened at `<app_data_dir>/selahcue.db3`; **in-memory fallback** on failure, surfaced
  non-fatally); **unique deck ids + unique display names**; load at startup, autosave the open deck on edit
  (`save_one`), persist library ops. Commands `deck_list/new/open/rename/duplicate/delete` → a `LibraryView`.
- Tests + `make ci`.

### Non-goals (documented)
- At-rest **encryption coordination** for the shared DB (only the `encryption` build) — follow-up.
- `PlanItem→deck` link, templates, the frontend UI (separate stories).

### Constraints
- Domain invariants: bounded (no unbounded growth); never-panic (clippy::unwrap_used=warn); additive serde
  keeps existing deck JSON byte-stable; FR-012 (deck edits never touch Live) preserved; persistence is
  best-effort + recoverable (never blocks editing); unique-name enforcement so `save_all`/PK never collide.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `SlideDeck` gains additive `DeckId` (default-stable serde; library self-heals missing/dup ids) | `cargo test` present | byte-stable + self-heal | `deck_id_is_additive_byte_stable_and_round_trips` (unassigned → no `id` key; assigned round-trips); heal tested in the operator | PASS |
| C-002 | yes | `deck_repo::{save_one,delete_one}` additive; round-trip + upsert-by-name tested | `cargo test -p selahcue-data` | green | `save_one_upserts_by_name_without_touching_others` + `delete_one_removes_a_single_deck_and_is_idempotent` (16/16) | PASS |
| C-003 | yes | Operator `DeckLibrary`: load/new/open/rename/duplicate/delete; unique ids+names; bounded | operator unit tests | green | 8 `deck_library` tests (create/store/rename/duplicate/delete/self-heal/adopt) | PASS |
| C-004 | yes | Persistence round-trip: library survives reopen (in-memory `Database` test); best-effort fallback never panics | operator unit test | survives + safe | `library_survives_a_reopen_of_the_same_db_file` + `in_memory_library_is_not_persistent`; `persist_one`/`delete_persisted` swallow DB errors | PASS |
| C-005 | yes | Commands `deck_list/new/open/rename/duplicate/delete` registered; return a `LibraryView`; open switches the editor | operator compile + unit | wired | 6 commands + `library_view` + `with_deck_and_library`; registered in `generate_handler!`; `load_deck_switches_the_open_deck_and_resets_the_session` | PASS |
| C-006 | yes | FR-012 preserved (library ops + open never set Live); autosave never blocks/loses edits | review + unit | green | `load_deck` clears Live (asserted); autosave = best-effort upsert; deadlock-free (deck→library order) | PASS |
| C-007 | yes | Operator compiles + clippy clean (`cargo check`+`clippy --all-targets`) | operator check | clean | `clippy --all-targets -- -D warnings` clean; operator tests 19/19 | PASS |
| C-008 | yes | Full CI gate green | `make ci` | ALL GREEN | `make ci` == **local CI gate: ALL GREEN** (exit 0), incl. operator `cargo test` + selahcue-data build | PASS |
| C-009 | yes | Independent adversarial review; confirmed Blocker/High fixed + re-verified | review workflow | none unresolved | 3-lens review: model/serde+repo **SOLID (0 findings)**; persistence **1 Med + 2 Low**; commands **0 substantive (nits)**. **No Blocker/High.** Fixes applied + tested (mint_id self-heal, atomic rename_one, uniquify totality, deck_view read-only, deck_open guard) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-present -p selahcue-data`; operator `cargo test` (DeckLibrary CRUD +
  persistence round-trip on `Database::open_in_memory`); `cargo check`+`clippy --all-targets` operator.
- Broader: `make ci` (now runs operator `cargo test`). Existing pinned deck/theme JSON stays byte-stable.
- Independent: 3-lens adversarial review (model/serde · persistence/recovery · library-state/commands).

## Iteration ledger

### Iteration 1 — implement
- `selahcue-present`: additive `DeckId` + `SlideDeck.id` (byte-stable when unassigned; accessors). `selahcue-data`:
  additive `deck_repo::{save_one, delete_one}` (later `rename_one`). `selahcue-operator`: `selahcue-data` dep;
  `DeckLibrary` (best-effort SQLite, self-heal, unique ids+names); startup wiring (adopt demo if empty);
  `with_deck` autosave; the 6 commands + `LibraryView`; `DeckWorkspace::{open_deck,load_deck,set_open_name}`.
- Tests: model byte-stability; repo round-trip; DeckLibrary CRUD + self-heal + persistence round-trip;
  `load_deck` reset. `make ci` == ALL GREEN (first pass).

### Iteration 2 — adversarial review (C-009) + fixes
- 3-lens review. **No Blocker/High.** model/serde+repo SOLID (0 findings); persistence 1 Medium + 2 Low;
  commands 0 substantive (nits). **Fixed:**
  - *[Med]* `mint_id` now self-heals past every existing id (mirrors `SlideDeck::mint_id`), so `adopt`'s
    keep-id branch can't make a later mint collide. + regression test.
  - *[Low→hardening]* rename is now **atomic** via a new `deck_repo::rename_one` (drop-old + upsert-new in one
    transaction) — a crash mid-rename can't lose the on-disk row; `store` uses it too. + repo test.
  - *[Low]* `uniquify` searches unbounded (total + collision-free) instead of a 10k cap + fallible last-resort.
  - *[nit B]* `deck_view` is now a read-only path (no autosave write on a read).
  - *[nit D]* `deck_open` early-returns when the target is already open (no needless session reset).
  - *[finding A]* the commands are intentionally not yet called by the webview — the **frontend Library UI is a
    separate story** (per the design handoff). Documented, not a defect.
  - *[nit C]* startup opens the demo on its first slide (not slide[1]) — cosmetic, accepted.
- Re-verify: present/data/operator suites green; clippy `--all-targets` clean; re-running `make ci`.

## Risks and rollback

- **Shared-DB encryption:** a desktop-encrypted `selahcue.db3` can't be read by the default (non-SQLCipher)
  operator → best-effort in-memory fallback (documented follow-up). Rollback: persistence is additive; the
  in-memory path is the current behaviour.
- **save_all whole-set replace + name PK:** mitigated by `save_one` upsert + library unique-name enforcement.
- **Concurrent migrations** (operator + desktop both open the DB): WAL + busy_timeout; both run the same
  append-only idempotent migrations. Rollback: operator can open its own DB file if contention appears.

## Pause and escalation conditions

- Stop at `make ci` green + review clean. Escalate if the shared-DB/encryption coordination proves to need
  an architecture decision beyond best-effort fallback.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-deck-library-backend.md --require-complete`
- Validator result: PASS (9/9 mandatory PASS)
- Independent verification result: 3-lens adversarial review — no Blocker/High; 1 Medium + several Low all
  fixed + re-verified (mint_id self-heal, atomic rename_one, uniquify totality, deck_view read-only, deck_open
  guard). Frontend Library UI is a separate story (design handoff).
- Terminal state: **VERIFIED_COMPLETE**
- Remaining failed or blocked criteria: none.
- ClickUp final evidence comment: posted to 86ajvqxy1.
