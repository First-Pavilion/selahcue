# Code Review — Batch: Saved themes usable per-item + per-screen (86ajq69ft)

- **Scope:** story `86ajq69ft` — let per-item overrides (S8-3d, `86ajq14wn`) AND per-screen themes (`86ajq321k`) accept **saved-library** theme names, not just built-ins, so a custom theme designed + saved in the Theme Designer (`86ajq4xmy`) can be applied to a single plan item or a single Audience screen (previously it could only be the global theme). Adds the **re-sync-on-library-change** path the per-screen review flagged. Executed via `/goal` (`TASK-86ajq69ft-saved-themes-everywhere.md`, validator PASS). Mostly controller + a thin frontend wire — **no wire command or migration change** (names already flow over `SetItemTheme`/`SetScreenTheme` and persist as TEXT).
- **Method:** an adversarial Workflow review (`wf_d2389630-37f`, 3 independent lenses → per-finding adversarial verify, **4 agents**, 245k tokens). Lenses: re-sync/no-stale-cache · resolution/recovery-load-order · frontend-pickers. Every finding independently confirmed-or-refuted by a separate skeptic (default REFUTED). No self-approval.
- **Outcome:** **1 raised → 1 CONFIRMED → fixed; 0 refuted.** 0 HIGH; 0 MEDIUM; 1 LOW (a validation gap).

## What shipped

- **Resolution (`controller.rs`).** A free `resolve_theme_name(name, &saved_themes)` = a built-in (`Theme::builtin`) **first**, else a saved-library name (its canonical JSON) — a free fn so callers can re-resolve while holding a mutable borrow of another field. A `&self` `resolve_theme` wrapper. `set_item_theme`, `set_screen_theme`, `stage_slide`, `compose_screen`, `load_screen_themes` all resolve via it — accept a built-in OR a saved name; a truly-unknown name is rejected (`BadRequest`) / dropped (load). The built-in path is unchanged.
- **Re-sync on library change (`resync_theme_overrides`).** Called at the end of `save_theme` (edit) + `delete_theme` (delete). It (1) DROPS plan-item / per-screen references whose name no longer resolves (a deleted theme → `plan_dirty` / `screen_themes_dirty`); (2) RE-APPLIES the `main` screen theme, the LIVE item override (`set_live_theme` re-resolved), and re-stages the STAGED item; (3) re-asserts blackout. So an edit reaches the physical live output immediately and a delete falls back to the global theme with **no stale frame**. Collect-then-mutate with a local `&self.saved_themes` avoids partial-borrow conflicts.
- **Recovery order (`desktop/main.rs`).** `load_saved_themes` + `load_screen_themes` now run **before** `restore()`/first-run, so a per-item / per-screen saved-theme reference resolves as `restore()` re-stages content.
- **Frontend (`app.js`).** The per-item picker (plan rows) + the per-screen pickers (Screens page `themePickerFor`) now list built-ins **plus a "Saved" optgroup** from `view.saved_themes`, wired to `set_item_theme` / `set_screen_theme`; the Screens change-detect key includes `view.saved_themes` so the picker rebuilds when the library changes.

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | re-sync | LOW | **A saved theme named exactly like a built-in was silently shadowed.** `resolve_theme_name` resolves built-ins first, but `save_theme` did not reject a name equal to a reserved built-in (`classic`/`high-contrast`/`lower-third`). An operator could save a branded design as "classic" (Ack), the pickers would list "classic" twice, and assigning it would resolve to the **plain built-in** — the custom design unreachable by name forever, with every reply a success `Ack`. This became reachable only in this batch, because saved themes are now applied **by name** (previously only via JSON/global, where the collision was harmless). | **Fixed:** `save_theme` now rejects a built-in name (`Theme::builtin(name).is_some() → BadRequest`), so built-in names stay reserved + unambiguous. Mirrored client-side in `tdDoSave` (a clear "that's a built-in template name — choose a different name" message instead of a silent backend deny). New `test_controller` assertion: saving under `classic`/`high-contrast`/`lower-third` is denied and never dirties. |

### Clean lenses

- The **resolution/recovery** and **frontend-pickers** lenses raised **no findings** — the built-in-first resolution is correct (and now unambiguous after the fix), the recovery load-order reproduces saved overrides (tested both orders), and both pickers list + reflect saved themes wired to their own commands (verified headlessly).

## Verification

- `cargo test --workspace` **all pass, 0 fail** (my batch's crates; the tree also contains an unrelated in-progress QA test-programme — see note); `cargo fmt --check` clean (main **and** the separate operator workspace); `clippy -D warnings` clean on **every target this batch touches** (libs + `test_controller` + `test_tokens` + desktop bin + operator); `node --check dist/app.js` clean.
- **No wire/migration change** (C-005 constraint): `protocol.rs`/`migrations.rs`/`rbac.rs` untouched, `target_version()` still 12, pinned v2 fixtures byte-stable.
- Per-layer: resolver accepts built-in + saved + rejects unknown, and rejects a built-in name (`test_controller`); per-item + per-screen assign a saved theme, live output reflects it; re-sync on edit (live re-renders in place) + delete (references dropped, output falls back to global, dirty flags set); recovery load-order (library-before-restore reproduces the saved-themed live output; restore-first falls back); the pickers pin (`test_tokens`).
- Frontend: a **headless render** confirming both pickers list a "Saved" optgroup and reflect the current saved selection (per-item **Brand**; per-screen main **Brand**).
- **Note — unrelated in-progress work in the tree:** a separate QA test-programme batch (`86ajq67q2`) has untracked WIP test files (`test_concurrency`/`test_security`/`test_reliability`/`test_resilience`/`test_scripture_fuzz`/`test_timer_drift`, `quality/`) that a parallel process is actively developing; those carry their own (unrelated) clippy lints and are **excluded from this commit**. This batch's committed tree is clean; CI (which runs on the committed tree) is unaffected.
- **Deferred with seams (contract non-goals):** import/export a theme FILE; dynamic Add/Delete virtual screen; per-layer Looks; physical secondary-output (NDI/stream) transport (R-later).
- **3-OS CI:** pending this push.
