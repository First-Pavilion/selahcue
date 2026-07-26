# Goal Contract — TASK-86ajq321k-per-screen-theme

## Identity

- Goal ID: TASK-86ajq321k-per-screen-theme
- Parent goal ID: STAGE8-core-presentation
- Title: Per-screen theme map — each Audience-class screen renders its OWN template simultaneously from the same live content (the 86ajq321k engine)
- Role: backend-engineer (engine/model/wire/persistence) + a thin frontend wire (Screens page)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq321k
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 16
- Independent verification required: yes

## Objective

Extend the theme engine from ONE global audience theme to a **per-screen theme map**: each Audience-class screen (`main` projector, a `lower-third` feed, a `stream` feed) renders its OWN theme/template **simultaneously** from the same live content (Screens design §3a). Switching one screen's theme never affects another or loses content; every screen's theme survives restart. This is the prerequisite the Screens page (86ajq321f, already in QA) needs — its per-screen Theme pickers today wire to the GLOBAL `set_theme` as an honest placeholder.

## Baseline

Verified from code:
- **Presenter** (`selahcue-present/src/present.rs`) drives ONE audience surface (`live` + `preview` engines) with a global `theme` + a per-item override (`staged_theme`/`live_theme`, S8-3d). The stage/confidence monitor is composed separately (`StageDisplay`).
- **Controller** (`selahcue-app/src/controller.rs`): `set_theme` recomposes the single audience output; `AssignOutput` rejects any role but `main`/`stage` (line ~1019); `operator_view` reports `outputs`/`displays`.
- **Desktop** (`selahcue-desktop/src/main.rs`): exactly 2 fixed windows (`main` + `stage`); `publish_output_status` hardcodes those two roles; `output_config` table CHECK enforces `main`/`stage`.
- **Wire** (`selahcue-lan/src/protocol.rs`): `Command::SetTheme{name}` / `SetCustomTheme` / `SetItemTheme`; `OperatorStateView` carries `theme`/`themes`; VERSION 2 with pinned cross-language fixtures.
- **Frontend**: the Screens page (`dist/index.html` `#surface-screens`, `app.js` renderOutputs) renders one row per output (main audience + stage); the audience row's Theme picker calls the GLOBAL `set_theme` with an honest "per-screen theme arrives with 86ajq321k" note.
- Migrations at **v11** (`target_version()==11`), append-only. Themes are canonical serde JSON of a fixed-size POD `Theme`.

## Scope

### In scope

- **Model + compose (present + controller):** an Audience-class screen set `{main, lower-third, stream}` (bounded, fixed this batch), each with an optional per-screen theme (`None` = global). Effective theme for screen S = **screen_theme(S) ?? item_theme(S8-3d) ?? global** — so `main` with no per-screen theme is BYTE-IDENTICAL to today. `main` is the physical audience output (existing Presenter live surface, recomposed on its own effective theme). Secondary screens compose **on-demand**: `compose_screen(screen) → FrameBuffer` renders the current live slide with the screen's effective theme (a pure function of live content + theme), proving simultaneous multi-theme rendering. Changing one screen's theme leaves others unchanged; content preserved on assign/switch (content ⟂ theme).
- **Wire + RBAC:** additive `Command::SetScreenTheme{screen, name}` (validates `screen` against the known set + `name` against built-ins/saved; `main` recomposes the live output; a bad screen/name → `BadRequest`) → RBAC `ConfigureOutputs` (Operator-only). `OperatorStateView.screen_themes: Vec<{screen, theme}>` (skip-if-empty) so the Screens page reflects each screen's theme. Additive (VERSION 2; pinned fixtures byte-stable). `SetTheme` (global) retained.
- **Persistence + recovery:** migration **v12** (`CREATE TABLE screen_theme(screen PK, theme_name)`) + a `screen_theme_repo` (save_all/load_all, transactional); the desktop loads on startup + saves on a dirty flag (mirrors `saved_theme`); recovery restores every screen's theme.
- **Frontend (Screens page):** the audience Theme picker per screen → `set_screen_theme{screen, name}` (not the global); reflect each audience screen's current theme; the Screens list shows the Audience-class screens (`main` + `lower-third` + `stream`) with the physical secondary-output delivery kept as an HONEST seam note. Pinned console invariants intact.

### Non-goals (seams — note)

- Physical secondary-audience WINDOW / NDI / SDI / browser-source **transport** (R-later) — secondary screens compose on-demand; only `main` drives a physical window this batch.
- Dynamic **Add / Delete virtual screen** + enable/disable toggle (Screens-page affordance; a bounded fixed set is used now).
- Per-layer **Looks**, **Mirror / Grouped / Edge-blend**, multi-screen groups (design R2).
- Per-screen **Format** (resolution/refresh) editing (read-only today).

### Constraints

- Additive wire (VERSION 2; pinned fixtures byte-stable) + additive migration (new table; older DB opens). Bounded memory (screen map capped to the known set; canonical bounded themes). No-leak / determinism. `main` audience output byte-identical when no per-screen theme is set (S8-3d preserved). fmt/clippy clean; 3-OS CI.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Engine/compose: each Audience screen renders its OWN theme from the SAME live content (main + lower-third + stream = 3 different designs at once); precedence screen ?? item ?? global; `main` byte-identical with no per-screen theme; changing one screen leaves others unchanged; content preserved; bounded | `cargo test -p selahcue-present -p selahcue-app` | per-screen render + isolation + content-preservation | test_present/test_controller | PASS |
| C-002 | yes | Wire + RBAC: `SetScreenTheme{screen,name}` additive (pinned v2 fixtures byte-stable) + RBAC Operator-only; bad screen/name rejected; `OperatorStateView.screen_themes` (skip-if-empty) reports the map | `cargo test -p selahcue-lan -p selahcue-app` | wire additive; rbac gated | test_protocol/test_rbac/test_controller | PASS |
| C-003 | yes | Persistence + recovery: migration v12 (`screen_theme` table; `target_version()==12`, older DB upgrades); `screen_theme_repo` round-trips; desktop loads on startup + saves on dirty; recovery restores every screen's theme | `cargo test -p selahcue-data -p selahcue-app` | per-screen theme survives save/load + recovery | test_db/test_screen_theme_repo/test_controller | PASS |
| C-004 | yes | Frontend + desktop: the Screens page's audience Theme picker sets a PER-SCREEN theme (`set_screen_theme`), reflects each screen's theme; main window renders the `main` screen; secondary delivery an honest seam; pinned console invariants intact | structure test + headless render | Screens page wires per-screen theme | test_tokens + render | PASS |
| C-005 | yes | Full: make ci + operator build + fmt/clippy clean; independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-per-screen-theme.md; CI run 30218357436 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-present` (per-screen compose + isolation + content-preservation + main byte-identical), `-p selahcue-app` (SetScreenTheme validate + map + recovery + operator view), `-p selahcue-lan` (wire additive fixtures + rbac), `-p selahcue-data` (migration v12 + screen_theme_repo round-trip); `test_tokens` (Screens page per-screen-theme wiring pins); a headless render of the Screens page with distinct per-screen themes. Broader: make ci + 3-OS CI. Independent: adversarial Workflow review (engine/compose/isolation · wire-compat/rbac/persistence · frontend/invariant/honesty lenses).
- Required environment: local + CI.

## Iteration ledger

- **Iter 1 — engine (C-001).** `present.rs`: added `main_screen_theme: Option<Theme>` + a private `effective(item)` = `main ?? item ?? global` helper; refactored `stage_themed`/`go_live`/`set_theme`/`set_live_theme` onto it (no behaviour change when `main_screen_theme` is None); added `set_main_screen_theme` (recomposes preview+live), `main_screen_theme()`, and `compose_screen_live(screen_theme)` (on-demand `raster::render(compose_slide(...))` for secondaries; black frame when idle). Re-exported `Rgba` from present. Evidence: 4 new `test_present` tests (byte-identical guard, precedence/global-switch, 3-designs-at-once + isolation, blank→black). **PASS.**
- **Iter 2 — controller + wire + RBAC (C-002).** `controller.rs`: `screen_themes` BTreeMap + dirty flag + `AUDIENCE_SCREENS = [main, lower-third, stream]`; `set_screen_theme` (validate screen + resolve name, main→presenter, empty=clear), `compose_screen` (blackout-aware), `resolve_theme_name` (built-in then saved library), `screen_themes`/`take/mark/load_screen_themes`. Wire: `Command::SetScreenTheme{screen,name}` + `OperatorStateView.screen_themes: Vec<ScreenThemeView>` (skip-if-empty) + rbac `ConfigureOutputs`. Internal `OperatorView.screen_themes: Vec<ScreenThemeView>` (object shape, not tuples). Evidence: `test_protocol` (round-trip + pinned skip-if-empty + populated fixture), `test_rbac`, `test_controller` (3 new: validate/map/recompose-main, compose-3-screens+isolation+clear, bounded+load). **PASS.**
- **Iter 3 — persistence + recovery (C-003).** Migration **v12** `screen_theme(screen PK, theme_name)`; `screen_theme_repo` (save_all DELETE+INSERT one-tx / load_all ordered); desktop loads on startup AFTER `load_saved_themes` + AFTER restore, saves on `take_screen_themes_dirty()` in the autosave loop + clean-exit flush (re-arms on failure). Two pre-existing downgrade tests updated to drop the new table + assert v12. Evidence: `test_db` (v11→v12 upgrade) + `test_screen_theme_repo` (round-trip/replace/reassign) + `test_controller` load/recovery. **PASS.**
- **Iter 4 — frontend + desktop (C-004).** `app.js` renderOutputs: `themePickerFor(screen)` wired to `invoke("set_screen_theme",{screen,name})` (NOT the global) reflecting `screenThemeOf`; the main audience row + virtual `lower-third`/`stream` rows each get one; change-detect key includes `screen_themes`; the honest NDI/stream delivery seam note. `index.html` Screens intro updated. `main.rs` (desktop) renders `main` as today; secondaries persisted + composed on-demand (physical delivery seam). Evidence: `test_tokens` new pin (`set_screen_theme` present, global `set_theme` regression-guarded absent) + a headless Screens render showing main=high-contrast, lower-third=lower-third, stream=classic (3 distinct themes) with stage keeping its layout chips. **PASS.**
- **Iter 5 — gate (C-005).** `cargo fmt --check` clean; `clippy -D warnings` clean (workspace + operator; added `#[allow(clippy::large_enum_variant)]` on `ServerMessage` with rationale — the view push crossed the size threshold, same as `ControllerReply`); `cargo test --workspace` 341/0; operator builds; `node --check dist/app.js` clean. Independent adversarial Workflow review (`wf_89bb043f-d79`, 4 lenses → per-finding verify, 6 agents): **2 raised → 2 confirmed (both MED), both fixed; 0 refuted.** (MED, engine) `main`'s per-screen theme could go stale if it referenced a SAVED-library theme later edited/deleted → restricted `set_screen_theme` to **built-in names only** (like `set_item_theme`); removed `resolve_theme_name`; built-in-only on every per-screen path; added a saved-name-rejected test. (MED, frontend) the picker had no "follow global" option so a per-screen theme couldn't be cleared → added a "◈ Follow global" entry (empty value = the backend clear), selected on map-membership. Re-verified: full gate green (341/0, fmt/clippy clean, operator builds), headless render + scripted picker-selection check. See `docs/delivery/CODE-REVIEW-batch-per-screen-theme.md`. CI green pending this push.

## Risks and rollback

- Risks: the per-screen vs per-item precedence being surprising (mitigated: one documented rule `screen ?? item ?? global`, tested, preserves S8-3d for `main`); unbounded screen-map growth (mitigated: a fixed known screen set — unknown ids rejected); wire/fixture drift (additive variants + pinned fixtures); migration breaking old DBs (additive new table + upgrade test); a persisted screen theme going stale vs the built-ins/library (mitigated: store the NAME, resolve at load, skip/ignore unknown); the desktop save-loop missing the dirty flag (mitigated: mirror `saved_theme`/`take_*_dirty` + a test); `main` audience output regressing (mitigated: a byte-identical test with no per-screen theme). Rollback: git; additive across crates.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq321k-per-screen-theme.md --require-complete`
- Validator result: PASS (all 5 mandatory criteria PASS).
- Independent verification result: adversarial Workflow review `wf_89bb043f-d79` (4 lenses → per-finding verify, 6 agents) — 2 raised → 2 confirmed (both MED), both fixed; 0 refuted. Re-verified: `cargo test --workspace` 341/0, fmt/clippy clean (workspace + operator), headless Screens render + scripted picker check. 3-OS CI run 30218357436 GREEN (11/11 jobs; Flutter path-skipped). (An earlier run 30218133629 caught an operator-crate `cargo fmt` miss — the operator is a separate workspace; fixed in commit 8d78955.)
- Terminal state: VERIFIED_COMPLETE (story `86ajq321k` handed to QA; not self-marked Done).
- ClickUp final evidence comment: posted on 86ajq321k (comment 90130296736231) + BUILD CONTROL 86ajnx548 (comment 90130296736267); commits `fce0643` + `8d78955`.
