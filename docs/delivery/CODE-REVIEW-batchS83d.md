# Code Review — Batch S8-3d (per-item theme override)

- **Scope:** story `86ajq14wn` (S8-3d, completes the S8-3 theme umbrella): a plan item carries an **optional theme override** (built-in name); the audience output renders that item on its own template, falling back to the global theme; persisted + crash-recovered; a **global** theme switch never clobbers an overridden item (FR-010, both ways). Executed via `/goal` (`TASK-86ajq14wn-per-item-theme.md`), backend-engineer + a small frontend picker.
- **Method:** adversarial Workflow review (`wf_955aa2c9-f57`, 3 lenses → per-finding adversarial verify, 5 agents). Lenses: presenter-per-surface/content-loss · wire-compat/rbac/persistence · frontend/invariant. No self-approval.
- **Outcome:** **2 raised → 2 CONFIRMED → both fixed; 0 noise.** 1 HIGH + 1 MEDIUM — both real defects caught before ship; the presenter-per-surface lens found nothing.

## What shipped

A vertical slice, additive throughout: **`PlanItem.theme: Option<String>`** (a built-in name; `None` = global) → the **Presenter** grew per-surface overrides (`staged_theme`/`live_theme`) so Preview + Live can render different per-item themes at once and a global switch recomposes each surface with its own effective theme (the audience auto-fit `layout_region` is untouched) → the **controller** resolves an item's override on stage/go-live and reflects a `SetItemTheme` on the affected surface → additive wire **`Command::SetItemTheme{item_id, theme}`** (fixtures byte-stable) + RBAC `ConfigureOutputs` (Operator-only) + `PlanItemView.theme` → migration **v10** (`plan_item.theme`, additive/nullable) + `plan_repo` round-trip → a **per-item theme picker** on each console plan row (an active override stays visible; blank = global). Custom (Theme-Designer) per-item themes stay deferred to the saved-theme library (`86ajq4xmy`).

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | wire/persist | **HIGH** | **The override was never persisted → lost on restart.** The override lives only in the plan (`PlanItem.theme`), and the desktop saves the plan only when `take_plan_dirty()` is true — but `set_item_theme` mutated the plan **without** setting `plan_dirty` (every other plan mutator sets it). So a lone `SetItemTheme` reached the model + operator view but never disk; on restart the item rendered on the global theme. The recovery test masked it (it hand-re-applied the override to the recovery controller's plan). | **Fixed:** `set_item_theme` now sets `self.plan_dirty = true` (so the desktop's autosave/exit save persists it — the `plan_repo` round-trip test covers save/load). The controller test now **asserts `take_plan_dirty()` after `SetItemTheme`**, closing the mask. |
| 2 | frontend | **MED** | **An open theme picker was destroyed by the 1s poll.** `render()` rebuilds the whole plan (`plan.innerHTML=""`) on any changed view; a running service timer changes the view every second, tearing out an open `<select>` popup before the operator can choose — so the picker is unusable during a timed segment. The Screens `renderOutputs` already defers a rebuild while its picker holds focus; the plan render had no such guard. | **Fixed:** `render()` now defers the plan rebuild while an `.item-theme` picker holds focus (after `syncChrome`, so emergency/timer chrome stays live), mirroring the outputs deferral. |

### Refuted / clean

- **presenter-per-surface/content-loss** — nothing found: `go_live` promotes the staged override correctly; `set_theme(global)` recomposes each surface with its own override-or-global (verified by `per_item_theme_override_is_independent_per_surface_and_survives_a_global_switch`); `clear_live`/`clear_preview` reset the matching override; `set_live_theme` recomposes from the retained slide (no content loss); the override state is O(1) (no-leak).

## Verification

- Full workspace `cargo test --all-features`, `fmt --check`, `clippy --all-targets` **clean**; operator crate `cargo clippy` + `cargo build` clean.
- Model: `test_plan`; Presenter: `test_present` (per-surface + global-switch-no-clobber + content preserved); controller: `test_controller` (override renders on lower-third, global switch preserves it, unknown item/name rejected, **plan marked dirty**, recovery restores it); wire: `test_protocol` (round-trip + additive skip-if-none fixture) + `test_rbac` (Operator-only); persistence: `test_db` (migration v10 pin + the v9→v10 upgrade) + `test_plan_repo` (round-trip incl. update/duplicate).
- Frontend: headless render of the console plan (`scratchpad/shot-plan-theme.png`) — each row has a theme picker; the live item shows its `lower-third` override; `node --check`; `test_tokens` pins (`set_item_theme`, `item-theme`).
- Deferred with seams (noted): custom (Theme-Designer) per-item themes + saved-theme library (`86ajq4xmy`); named announcement/sermon templates (`86ajq3225`); per-screen theme (`86ajq321k`).
- **3-OS CI:** pending this push.
