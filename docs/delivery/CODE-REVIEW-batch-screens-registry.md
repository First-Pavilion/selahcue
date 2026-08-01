# Code Review — Batch: dynamic screen registry (enable/add/delete virtual screens)

- **Scope:** the Screens page shipped its shell (app-menu, role badges, per-screen theme pickers + previews) but the screen set was a **fixed const** (`AUDIENCE_SCREENS`), and the UI advertised enable/disable + add/delete as "arrive next". This batch delivers that: a **bounded, persisted, deterministically-ordered `ScreenRegistry`** (`{ id, role, enabled, deletable }`) so an operator can **enable/disable** any screen (mute the lower-third mid-service; black the confidence monitor) and **add/delete** a virtual audience feed (a second stream). Additive wire (VERSION stays 2), RBAC `ConfigureOutputs`, migration **v13**, disabled→safe-black compose, delete-virtual-only enforced server-side, recover-to-default on load. Executed via `/goal` (`TASK-screens-registry-enable.md`, validator PASS `--require-complete`). NDI/SDI/stream physical DELIVERY stays an honest R-later affordance.
- **Method:** an adversarial Workflow review `wf_4b25b9c4-6ff` — 4 lenses (registry-invariants · additive-wire/RBAC · data-migration/recovery · frontend) → **per-finding refute-by-default**, each finding checked by two perspective-diverse verifiers (correctness + reproduction). 12 agents.
- **Outcome:** 4 findings raised → **3 confirmed (1 HIGH + 2 MEDIUM), all fixed; 1 refuted.**

## What shipped

- **Registry (`selahcue-app`):** `ScreenRole { Main, LowerThird, Stream, Stage }`, `Screen { id, role, enabled, deletable }`, `ScreenRegistry` (a `Vec` for stable order) with `MAX_SCREENS = 16` (no-leak), `with_builtins` / `from_persisted` (recover-to-default) / `add_virtual` (mints `role-N`, caps) / `remove` (delete-virtual-only) / `set_enabled` / `is_enabled`. Controller handlers `set_screen_enabled`/`add_screen`/`remove_screen`; `compose_screen` registry-aware (disabled/blackout→safe-black); `operator_view.screens`.
- **Wire (`selahcue-lan`):** additive `SetScreenEnabled`/`AddScreen`/`RemoveScreen` (snake_case tags) → `ConfigureOutputs` (exhaustive, no wildcard); `ScreenView` + `OperatorStateView.screens` (skip-if-empty). VERSION unchanged (2).
- **Data (`selahcue-data`):** migration **v13** `screen` table + `screen_repo`; desktop loads registry-before-themes, persists on mutation, blacks the physical main/stage window when its screen is disabled.
- **Operator (`dist/` + `src/main.rs`):** registry-driven Screens rows — per-row Enable toggle, "+ Add screen", Delete-on-virtual-only; 3 Tauri commands.

## Findings and dispositions

| # | Lens | Sev | Finding | Verify | Fix |
|---|------|-----|---------|--------|-----|
| 1 | frontend | **HIGH** | The Enable checkbox sent its already-flipped native value and never reset on failure — a **rejected** `set_screen_enabled` (RBAC-denied for a non-Operator, older host, transport error — the exact case this batch introduces) left the checkbox **lying permanently** (the 1s poll skips the rebuild because the registry didn't change). Operator believes a screen is muted (safe-black) when it is still live. | **2/2 REAL** | **Fixed** — the `onchange` reverts the optimistic flip to the authoritative value BEFORE the round trip (mirroring the assign-output `<select>`): a success re-renders with the new state; a rejection leaves the true, unchanged state. Headless: "a REJECTED enable-toggle reverts to authoritative". |
| 2 | registry | MEDIUM | The operator console **Live** monitor (labelled "main output", contract "the true pixels the audience sees") built from `live_output()` with **no `is_screen_enabled("main")` gate** — so on a main disable the physical window + Screens preview went black, but the console Live monitor kept showing airing content (on-air-confusion risk). | 1/2 REAL (split: one verifier called it a program-monitor design choice) | **Fixed** — the Live thumbnail (both `GetConsoleThumbnails` and the local `console_thumbnails`) blacks when `main` is disabled, equal to the blackout frame; **Preview** (the staged feed) is deliberately unaffected. Test: `disabling_main_blacks_the_console_live_monitor_not_preview`. Took the honest reading — the panel *is* the main output monitor, so it must agree with the physical window. |
| 3 | frontend | MEDIUM | Narrowing the picker guard to `<select>`-only meant a focused **checkbox/button** was destroyed by the `innerHTML` rebuild, **dropping keyboard focus to `<body>`** on every Enable/Delete/Add activation (and whenever a 1s-poll rebuild hit a focused control) — a keyboard operator had to re-traverse the tree each time. | **2/2 REAL** | **Fixed** — `renderOutputs` now saves the focused control's identity (screen id + control class) before the rebuild and **restores focus** to its rebuilt equivalent. Headless: "keyboard focus is restored to the toggle after the rebuild". |
| 4 | frontend | LOW | Claimed the Screens page wouldn't reflect a registry change from another client until a plan field changed. | **Refuted** | Premise wrong — `view.screens` (the registry) is included in the `outputsKey`, so another client's registry change *does* rebuild the page on the next poll. |

**No false-pass survived. No HIGH/MEDIUM left open.**

## Verification

- **Workspace:** `cargo test --workspace` **488/0** (+12 over baseline: wire round-trip + RBAC, 6 registry-invariant tests, migration + screen_repo, the console-live-monitor test); `--features server` green; fmt/clippy clean (workspace + operator).
- **Operator gates (run on the CI runner):** committed Chrome headless **81/81** (incl. the 3 fix regressions — reject-reverts, focus-restore, and the 9 registry-UI checks) + WebKit smoke **5/5**.
- **3-OS CI:** run `30695958783` `completed → success` (verified by conclusion) — rust + operator on macOS/Windows/Linux all green; the operator-Linux logs show `=== 81 checks, 0 FAIL ===` (Chrome) + `=== WebKit smoke: 5 checks, 0 FAIL ===`.
- **Owner on-device QA (optional):** the definitive "disable the lower-third mid-service; add a second stream; the muted main window is black" is owner-run on the real Tauri app; the headless + Rust assertions are the strongest short of the GUI.

## Follow-ups

- Physical NDI/SDI/stream secondary-output **delivery** (R-later) — a virtual screen composes + previews on-demand but does not stream yet; the Output-target + Format selectors stay honest "arrives later". Mirror/Grouped/Edge-blend types; per-layer Looks; a second confidence monitor; real OS display enumeration for the demo backend (`86ajtxnn1`).
