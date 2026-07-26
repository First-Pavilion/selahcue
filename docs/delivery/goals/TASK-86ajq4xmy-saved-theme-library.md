# Goal Contract — TASK-86ajq4xmy-saved-theme-library

## Identity

- Goal ID: TASK-86ajq4xmy-saved-theme-library
- Parent goal ID: STAGE8-core-presentation
- Title: Saved-theme library — persist NAMED custom themes (Save changes / delete / apply); the Theme Designer's "Save changes"
- Role: backend-engineer (store/wire/persistence) + frontend-engineer (library UI)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq4xmy
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 14
- Independent verification required: yes

## Objective

Today the Theme Designer edits a working copy and can Apply ONE active custom theme; there is no way to **save a named theme** and pick it later (the Figma "Save changes"). Add a persistent **named-theme library**: save the current design under a name, list the saved themes alongside the built-ins, select one (load it into the editor), delete one, and Apply any of them. Built-ins stay read-only.

## Baseline

Verified: ONE active custom theme is persisted (S8-3c) — the controller tracks `theme_name`/`custom_theme_json` (canonical re-serialized) + `session_state.custom_theme` (migration v9). The Theme Designer sources built-ins from the host (`builtin_themes`, a pure operator fn) into `TD_BUILTINS`; "New (from current)" duplicates; Apply → `set_custom_theme`; "Save changes" is an honest "later" affordance routing here. Pattern (plans): the **controller** holds active state + a `_dirty` flag (`plan_dirty`/`take_plan_dirty`); the **desktop `SessionStore`** owns the repos (`plan_repo`/`session_repo`/`output_repo`) + the save-loop; no wire library-ops exist. Migrations at **v10** (`target_version()==10`), append-only. Themes are canonical serde JSON of a fixed-size `Theme`.

## Scope

### In scope

- **Store (controller):** a `saved_themes: BTreeMap<String, String>` (name → canonical theme_json) + a `saved_themes_dirty` flag + `take_saved_themes_dirty()` + `saved_themes()` + `load_saved_themes(map)` (startup). `SaveTheme{name, theme_json}` validates the JSON (deserialize to `Theme`, store the CANONICAL re-serialized form; reject invalid/empty name) + marks dirty; `DeleteTheme{name}` removes + marks dirty. Bounded (a sane cap on count/name length; no unbounded growth).
- **Wire + RBAC:** `Command::SaveTheme{name, theme_json}` + `Command::DeleteTheme{name}` (additive; pinned v2 fixtures byte-stable) → RBAC `ConfigureOutputs` (Operator-only); `OperatorStateView.saved_themes: Vec<{name, theme_json}>` (skip-if-empty) so the Theme Designer lists + loads them.
- **Persistence:** migration **v11** (`CREATE TABLE saved_theme(name PK, theme_json)`) + a `saved_theme_repo` (`save_all`/`load_all`, transactional); the desktop loads on startup + saves on `take_saved_themes_dirty()` (mirrors `save_plan`).
- **Frontend:** the Theme Designer library — a **Save** control (inline name input, WKWebView-safe) → `SaveTheme` of the current design; the template list shows **built-ins + saved themes** (saved ones selectable → load into the editor; deletable via a ✕); Apply a saved theme = `set_custom_theme` of its JSON. Built-ins read-only. Pinned console invariants intact.

### Non-goals (seams — note)

- Rename (= delete + save under a new name via the UI) and duplicate (= "New (from current)" + Save) are achievable with Save+Delete; a dedicated `RenameTheme` op is deferred. Import/Export a theme FILE (later). Per-item/per-screen use of a saved (named) custom theme (extends S8-3d `86ajq14wn` / `86ajq321k`).

### Constraints

- Additive wire (VERSION 2; pinned fixtures byte-stable) + additive migration (new table; older DB opens). Bounded memory (a cap on saved themes; canonical bounded JSON). No-leak / determinism. fmt/clippy clean; 3-OS CI.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Controller store: `SaveTheme` validates + stores the CANONICAL theme (invalid JSON / empty name / over-cap rejected); `DeleteTheme` removes; `saved_themes()` + dirty flag; `load_saved_themes`; bounded | `cargo test -p selahcue-app` | store works + bounded | test_controller | PASS |
| C-002 | yes | Wire + RBAC: `SaveTheme`/`DeleteTheme` additive (pinned v2 fixtures byte-stable) + RBAC Operator-only; `OperatorStateView.saved_themes` (skip-if-empty) reports the library | `cargo test -p selahcue-lan` | wire additive; rbac gated | test_protocol/test_rbac | PASS |
| C-003 | yes | Persistence: migration v11 (`saved_theme` table; `target_version()==11`, older DB upgrades); `saved_theme_repo` save_all/load_all round-trips; desktop loads on startup + saves on dirty | `cargo test -p selahcue-data` | library survives save/load | test_db/test_saved_theme_repo | PASS |
| C-004 | yes | Frontend: Theme Designer library — Save (named) the current design, list built-ins + saved, select a saved theme (load), delete a saved theme, Apply; pinned console invariants intact | structure test + headless render | library UI works; invariants intact | test_tokens + render | PASS |
| C-005 | yes | Full: make ci + operator build + fmt/clippy clean; independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-saved-themes.md; CI run 30215838572 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-app` (SaveTheme/DeleteTheme validate + bound + dirty), `-p selahcue-lan` (wire additive fixtures + rbac), `-p selahcue-data` (migration v11 + saved_theme_repo round-trip); `test_tokens` (pin + structure); a headless render of the Theme Designer with a saved theme in the list. Broader: make ci + 3-OS CI. Independent: adversarial Workflow review (store/validation/no-leak · wire-compat/rbac/persistence · frontend/invariant lenses).
- Required environment: local + CI.

## Iteration ledger

- **Iter 1 — store (C-001).** Added `saved_themes: BTreeMap<String,String>` + `saved_themes_dirty` + consts `MAX_SAVED_THEMES=256`/`MAX_THEME_NAME_LEN=64` + `save_theme`/`delete_theme`/`saved_themes`/`take_saved_themes_dirty`/`mark_saved_themes_dirty`/`load_saved_themes` to `controller.rs`; canonical re-serialize on save; new-name-past-cap rejected; `load_saved_themes` filters invalid/over-cap without dirtying. Evidence: 3 new tests in `test_controller.rs` (54 pass). **PASS.**
- **Iter 2 — wire + RBAC (C-002).** `Command::SaveTheme{name,theme_json}` + `Command::DeleteTheme{name}`; `OperatorStateView.saved_themes: Vec<SavedThemeView{name,theme_json}>` (serde default + skip-if-empty); rbac → `ConfigureOutputs`. Pinned fixtures unchanged when empty + a new populated `saved_themes` fixture pinned. Evidence: `test_protocol`/`test_rbac` green (12+10). **PASS.**
- **Iter 3 — persistence (C-003).** Migration v11 `CREATE TABLE saved_theme(name PK, theme_json)`; `target_version()==11`; `saved_theme_repo` `save_all` (DELETE+INSERT, one tx) / `load_all` (ordered); desktop loads on startup + saves on `take_saved_themes_dirty()` in the autosave loop and the clean-exit flush (re-arms on failed write). Two pre-existing downgrade tests updated to drop the new table. Evidence: `test_db` (v10→v11 upgrade) + new `test_saved_theme_repo` round-trip/replace/overwrite. **PASS.**
- **Iter 4 — frontend (C-004).** Theme Designer library UI: real "Save changes" inline name form (no `window.prompt`; WKWebView-safe), template list = built-ins (read-only, tagged) + saved themes (load / two-click delete), wired to host `save_theme`/`delete_theme`; `syncSavedThemes` folds `view.saved_themes` per poll (guards a focused save-name field). New Tauri command wrappers + `OperatorShell`/`RemoteOperator` methods. **Caught in headless render:** `.td-save-row{display:flex}` defeated the `[hidden]` attribute → added `.td-save-row[hidden]{display:none}`. Evidence: `test_tokens` structure pin (7 pass) + headless render + scripted Save→list→delete interaction (all assertions green). **PASS.**
- **Iter 5 — gate (C-005).** `cargo fmt --check` clean, `clippy -D warnings` clean (workspace + operator), `cargo test --workspace` 329/0, operator crate builds. Independent adversarial Workflow review (`wf_f5b8ac93-041`, 4 lenses → per-finding verify, 9 agents): **5 raised → 3 confirmed (2 MED + 1 LOW, all frontend), all fixed; 2 refuted.** Fixes: (MED) fake-success on a host-DENIED save (a DENY resolves Ok with the unchanged view) → verify the returned view actually contains the name + reject an over-64-**byte** name client-side (matching the host cap); (MED) two-click delete-confirm defeated by a mid-confirm list rebuild → clear `tdConfirmDel` on every `tdList()` rebuild; (LOW) a saved theme sharing a built-in's name double-highlighted → key selection by `{kind, name}`. **Plus a defect the review missed, caught by the batch's own headless render:** the internal `OperatorView.saved_themes` serialized as `[[name,json]]` tuples, not the `{name,theme_json}` objects the webview reads → switched the internal view to `Vec<SavedThemeView>` (identical to the wire type) + pinned the serialized shape with a `serde_json::to_value` assertion. Re-verified: full gate green (329/0, fmt/clippy clean, operator builds), headless render + scripted interaction confirm all fixes. See `docs/delivery/CODE-REVIEW-batch-saved-themes.md`. CI green pending this push.

## Risks and rollback

- Risks: unbounded growth of the library (mitigated: a cap on count + name length; canonical bounded JSON); wire/fixture drift (additive variants + pinned fixtures); migration breaking old DBs (additive new table + upgrade test); a saved theme's JSON going stale vs the Theme model (mitigated: store canonical re-serialized; deserialize-on-load tolerates/skips corrupt entries); the desktop save-loop missing the dirty flag (mitigated: mirror `save_plan`/`take_plan_dirty` + a test asserting the flag). Rollback: git; additive across crates.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq4xmy-saved-theme-library.md --require-complete`
- Validator result: PASS (all 5 mandatory criteria PASS).
- Independent verification result: adversarial Workflow review `wf_f5b8ac93-041` (4 lenses → per-finding verify, 9 agents) — 5 raised → 3 confirmed (2 MED + 1 LOW), all fixed; 2 refuted; + 1 serialization defect caught by the batch's headless render, fixed + pinned. Re-verified: `cargo test --workspace` 329/0, fmt/clippy clean (workspace + operator), headless render + scripted interaction. 3-OS CI run 30215838572 GREEN (11/11 jobs; Flutter path-skipped).
- Terminal state: VERIFIED_COMPLETE (story `86ajq4xmy` handed to QA; not self-marked Done).
- ClickUp final evidence comment: posted on 86ajq4xmy (comment 90130296730617) + BUILD CONTROL 86ajnx548 (comment 90130296730685); commit `8b7a54b`.
