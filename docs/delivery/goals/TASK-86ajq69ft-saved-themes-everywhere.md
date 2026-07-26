# Goal Contract — TASK-86ajq69ft-saved-themes-everywhere

## Identity

- Goal ID: TASK-86ajq69ft-saved-themes-everywhere
- Parent goal ID: STAGE8-core-presentation
- Title: Saved themes usable per-item + per-screen (not just global) — with re-sync on library change
- Role: backend-engineer (controller resolution + re-sync) + a thin frontend wire (pickers)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq69ft
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 14
- Independent verification required: yes

## Objective

Let per-item overrides (S8-3d, `86ajq14wn`) AND per-screen themes (`86ajq321k`) accept **saved-library** theme names, not just built-ins — so a custom theme designed + saved in the Theme Designer (`86ajq4xmy`) can be applied to a single plan item or a single Audience screen, not only as the global theme. Add the **re-sync-on-library-change** path the per-screen review flagged, so a cached concrete `Theme` never goes stale when the saved theme is edited or deleted.

## Baseline

Verified from code:
- `set_item_theme` (`controller.rs`) validates the name via `Theme::builtin` (built-in only) and stores it in the plan; reflects on live (`set_live_theme`) + re-stages preview. `stage_slide` resolves `item.theme` via `Theme::builtin`.
- `set_screen_theme` validates via `Theme::builtin` (built-in only; the per-screen review `wf_89bb043f-d79` restricted it precisely to avoid a stale cached theme). `compose_screen` / `load_screen_themes` resolve via `Theme::builtin`.
- The Presenter caches CONCRETE themes: `staged_theme`/`live_theme` (per-item) + `main_screen_theme` (per-screen). These are snapshots resolved from names by the controller.
- `save_theme`/`delete_theme` mutate `self.saved_themes` (the library) + a dirty flag; they do NOT touch the presenter's cached themes or the per-item/per-screen name references.
- `restore()` re-applies the global theme, then re-stages live/staged via `stage_slide` (so per-item themes resolve at restore time). The desktop currently loads `saved_themes`/`screen_themes` AFTER `restore()`.
- Wire: `Command::SetItemTheme{item_id, theme}` + `Command::SetScreenTheme{screen, name}` already carry a name string (no change needed to accept a saved name). Persistence: `plan_item.theme` (v10) + `screen_theme` (v12) already store the name as TEXT (no schema change needed).

## Scope

### In scope

- **Shared resolver:** a `resolve_theme_name(name, &saved_themes) -> Option<Theme>` = a built-in first, else a saved-library name (deserialize its canonical JSON). `set_item_theme`, `set_screen_theme`, `stage_slide`, `compose_screen`, `load_screen_themes` all use it. A truly-unknown name is still rejected (`BadRequest` for the set commands; dropped on load).
- **Re-sync on library change:** `save_theme` (edit — an existing name re-resolves to the new JSON) and `delete_theme` (the name stops resolving) call a `resync_theme_overrides()` that: (a) DROPS dangling references — a plan item / per-screen entry whose theme name no longer resolves is cleared (plan → `None` + `plan_dirty`; screen → removed + `screen_themes_dirty`); (b) RE-APPLIES the currently-displayed overrides — the `main` screen theme, the LIVE item override (`set_live_theme` re-resolved), and re-stages the STAGED item — so an edit reaches the physical live output immediately and a delete falls back to the global theme with no stale frame. Blackout preserved.
- **Recovery order:** the desktop loads the saved-theme library + the per-screen map **before** `restore()` (so a per-item / per-screen saved-theme reference resolves as content is re-staged). `load_screen_themes` before restore is a no-op recompose (nothing staged yet); restore then composes with the loaded overrides.
- **Frontend:** the per-item Theme picker (plan rows) + the per-screen Theme pickers (Screens page) offer **built-ins + saved themes** (from `view.saved_themes`), grouped/labelled so the operator can pick a saved design. The per-screen "◈ Follow global" clear stays; the per-item blank "follow global" stays.

### Non-goals (seams — note)

- Import/export a theme FILE; dynamic Add/Delete virtual screen; per-layer Looks; Mirror/Grouped/Edge-blend. Physical secondary-output (NDI/stream) transport (R-later).

### Constraints

- **No new wire command and no new migration** (names already flow over `SetItemTheme`/`SetScreenTheme` and persist as TEXT) — pinned v2 fixtures + `target_version()` **unchanged**; assert this. Bounded memory (the library is already capped; overrides reference names, not copies). Zero content loss (content ⟂ theme). No-leak / determinism. `main`/live/preview byte-identical when no saved theme is used (built-in path unchanged). fmt/clippy clean; 3-OS CI.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Resolution: `set_item_theme` + `set_screen_theme` accept a SAVED-library name (and built-ins); `stage_slide`/`compose_screen`/`load_screen_themes` resolve saved names; a truly-unknown name is rejected; built-in path byte-identical | `cargo test -p selahcue-app` | saved themes assignable per-item + per-screen | test_controller | PASS |
| C-002 | yes | Re-sync on library change: EDITING a saved theme used by the live item / `main` screen re-renders it live; DELETING it drops the reference (plan item → None, screen entry removed) and the output falls back to global with no stale frame; the staged item re-stages; blackout preserved | `cargo test -p selahcue-app` | no stale cached theme after edit/delete | test_controller | PASS |
| C-003 | yes | Recovery: a per-item AND per-screen SAVED theme resolves after a restart (library + per-screen map loaded before `restore()`); desktop load order updated | `cargo test -p selahcue-app` | saved overrides survive recovery | test_controller | PASS |
| C-004 | yes | Frontend: the per-item + per-screen Theme pickers offer built-ins + saved themes; a saved theme is selectable per-item and per-screen; pinned console invariants intact | structure test + headless render | pickers offer saved themes | test_tokens + render | PASS |
| C-005 | yes | Full: make ci + operator build + fmt/clippy clean; NO wire/migration change (fixtures byte-stable, `target_version` unchanged); independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-saved-themes-everywhere.md; CI run 30220206582 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-app` — resolver accepts built-in + saved + rejects unknown; per-item + per-screen assign a saved theme (live output reflects it); re-sync on edit (live re-renders) + delete (falls back, plan/screen reference dropped) + staged re-stage; recovery load-order (load saved_themes then restore → per-item saved theme resolves); `test_tokens` (pickers offer saved themes; no wire/migration pins broken). Broader: make ci + 3-OS CI. Independent: adversarial Workflow review (resolution/re-sync/no-stale-cache · recovery-order · frontend/invariant lenses).
- Required environment: local + CI.

## Iteration ledger

- **Iter 1 — resolution (C-001).** Added a free `resolve_theme_name(name, &saved_themes)` (built-in ∪ saved-library JSON) + a `&self` `resolve_theme` wrapper. `set_item_theme`, `set_screen_theme`, `stage_slide`, `compose_screen`, `load_screen_themes` all resolve via it — accept a built-in OR a saved name; a truly-unknown name is rejected/dropped. The built-in path is unchanged (`Theme::builtin` first). Evidence: `test_controller::a_saved_theme_is_assignable_per_item_and_per_screen` + the updated per-screen validate test (a saved name is now Ack). **PASS.**
- **Iter 2 — re-sync (C-002).** `resync_theme_overrides()` called at the end of `save_theme` (edit) + `delete_theme` (delete): drops plan-item / per-screen references whose name no longer resolves (→ `plan_dirty`/`screen_themes_dirty`), then re-applies the `main` screen theme, the LIVE item override, and re-stages the STAGED item (blackout re-asserted). Collect-then-mutate with a local `&self.saved_themes` avoids partial-borrow conflicts. Evidence: `editing_a_saved_theme_re_renders_every_place_it_is_used` (live re-renders in place) + `deleting_a_saved_theme_drops_references_and_falls_back_to_global` (references dropped, dirty flags set, live == the global-theme reference). **PASS.**
- **Iter 3 — recovery (C-003).** Desktop `main.rs`: `load_saved_themes` + `load_screen_themes` moved BEFORE `restore()`/first-run, so a per-item / per-screen saved-theme reference resolves as `restore()` re-stages. Evidence: `a_saved_per_item_theme_resolves_on_recovery_only_with_the_correct_load_order` — library-before-restore reproduces the saved-themed live output; restore-before-library falls back (order matters). **PASS.**
- **Iter 4 — frontend (C-004).** `app.js`: the per-item picker (plan rows) + the per-screen pickers (`themePickerFor`) list built-ins + a "Saved" optgroup from `view.saved_themes`; the Screens change-detect key now includes `view.saved_themes`. Evidence: `test_tokens::operator_webview_offers_saved_themes_per_item_and_per_screen` + a headless render — both pickers show the Saved group and reflect the current saved selection (per-item Brand; per-screen main Brand). **PASS.**
- **Iter 5 — gate (C-005).** `cargo fmt --check` clean (main + operator workspaces — the operator is separate); `clippy -D warnings` clean on **every target this batch touches** (libs + `test_controller` + `test_tokens` + desktop bin + operator); `cargo test --workspace` all pass, 0 fail; operator builds; `node --check dist/app.js` clean. **No wire/migration change** — `protocol.rs`/`migrations.rs`/`rbac.rs` untouched, `target_version()` still 12, pinned fixtures byte-stable. Independent adversarial Workflow review (`wf_d2389630-37f`, 3 lenses → per-finding verify, 4 agents): **1 raised → 1 confirmed (LOW), fixed; 0 refuted.** (LOW) a saved theme named exactly like a built-in was silently shadowed (built-ins resolve first) → `save_theme` now rejects a built-in name (mirrored client-side) + a test. Re-verified: full gate green, 384/0 workspace tests. **Note:** the tree also contains an unrelated in-progress QA test-programme (`86ajq67q2`) with untracked WIP test files carrying their own clippy lints — those are excluded from this commit; the committed tree + CI are unaffected. See `docs/delivery/CODE-REVIEW-batch-saved-themes-everywhere.md`. CI green pending this push.

## Risks and rollback

- Risks: a cached concrete `Theme` going stale after a library edit/delete (mitigated: the `resync_theme_overrides` path re-applies + drops dangling refs; tests on edit + delete + staged); a deleted saved theme leaving a dangling name reference (mitigated: dropped to None/removed + a test); recovery resolving a saved name against an empty library (mitigated: load library + map BEFORE restore + a load-order test); borrow-checker friction re-resolving while mutating the plan/map (mitigated: a free `resolve` taking `&saved_themes` + collect-then-mutate); accidentally changing the built-in path (mitigated: a byte-identical guard); wire/migration drift (mitigated: NONE expected — assert fixtures + `target_version` unchanged). Rollback: git; additive controller/frontend only.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq69ft-saved-themes-everywhere.md --require-complete`
- Validator result: PASS (all 5 mandatory criteria PASS).
- Independent verification result: adversarial Workflow review `wf_d2389630-37f` (3 lenses → per-finding verify, 4 agents) — 1 raised → 1 confirmed (LOW), fixed; 0 refuted. 3-OS CI run 30220206582 GREEN (11/11 jobs; Flutter path-skipped).
- Terminal state: VERIFIED_COMPLETE (story `86ajq69ft` handed to QA; not self-marked Done).
- ClickUp final evidence comment: posted on 86ajq69ft (comment 90130296740211); commit `b7e7a19`.
