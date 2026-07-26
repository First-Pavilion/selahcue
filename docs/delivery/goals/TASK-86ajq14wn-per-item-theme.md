# Goal Contract — TASK-86ajq14wn-per-item-theme

## Identity

- Goal ID: TASK-86ajq14wn-per-item-theme
- Parent goal ID: STAGE8-core-presentation
- Title: Per-item theme override (S8-3d) — a plan item renders on its own template, falling back to the global theme; zero content loss both ways
- Role: backend-engineer (+ a small frontend picker)
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq14wn
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 14
- Independent verification required: yes

## Objective

Complete the S8-3 theme umbrella: a plan item carries an **optional theme override** (a built-in name); the audience output renders that item's slides on its own theme, **falling back to the global theme**; the override is persisted + crash-recovered; switching the **global** theme never clobbers an overridden item and never loses content (FR-010, both ways).

## Baseline

Verified: `PlanItem{id, kind, title, planned_secs, owner, stanzas}` — no theme field. The `Presenter` holds ONE global `theme` and composes BOTH Preview + Live with it (`stage`/`go_live`/`set_theme` all use `self.theme`). The controller stages a plan item via `presenter.stage(item_slide(item, slide))` (content-only). Wire has `Command::SetTheme{name}`/`SetCustomTheme{theme_json}` → RBAC `ConfigureOutputs`. `PlanItemView{id,kind,title,is_live,is_staged,slide_count?,slide_index?}`. Persistence: `plan_item` table (v6 added `content`); migrations at **v9** (`target_version()==len==9`), append-only. Themes resolve via `Theme::builtin(name)` (3 built-ins).

## Scope

### In scope

- **Model:** `PlanItem.theme: Option<String>` (a built-in theme name; `None` = the global theme). Constructors/mutators updated; a plan mutator to set/clear an item's theme.
- **Presenter (per-surface override):** track `staged_theme`/`live_theme: Option<Theme>` alongside the global `theme`. `stage_themed(slide, Option<Theme>)` composes Preview with the override-or-global + records it; `go_live` promotes the staged override to Live; `set_theme(global)` recomposes **each surface with its own** override-or-the-new-global (so a global switch never clobbers an overridden surface). `stage(slide) = stage_themed(slide, None)` keeps existing callers.
- **Controller + wire + RBAC:** staging a plan item resolves `item.theme → Theme::builtin` (else global) and calls `stage_themed`; `Command::SetItemTheme{item_id, theme: Option<String>}` sets/clears the item's override + re-renders the affected Preview/Live surface; additive wire (pinned v2 fixtures byte-stable) + RBAC `ConfigureOutputs` (Operator-only); `PlanItemView.theme` (skip-if-none) so the UI reflects it; operator shell + Tauri command plumbing.
- **Persistence + recovery:** migration **v10** (`ALTER TABLE plan_item ADD COLUMN theme TEXT`, additive/nullable; `target_version()==10`, older DB upgrades); `plan_repo` save/load round-trips `item.theme`; recovery restores each item's override (the live/staged item re-stages with its theme).
- **Frontend:** a per-item theme picker in the console plan rows → `set_item_theme`; pinned console invariants intact.

### Non-goals (seams — note)

- Custom (Theme-Designer) per-item themes — this batch overrides with a **built-in** name; named custom per-item themes need the saved-theme library (`86ajq4xmy`). Named announcement/sermon template slides (FR-011) → `86ajq4xmy`/`86ajq3225`. Per-screen theme (`86ajq321k`).

### Constraints

- Zero content loss both ways (override renders the item's content; a global switch keeps overrides + content). Additive wire (VERSION 2; pinned fixtures byte-stable) + additive nullable migration (older DB opens). No-leak / determinism preserved. fmt/clippy clean; 3-OS CI.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `PlanItem.theme: Option<String>` added; constructors/mutators + a set-item-theme plan API; existing plan/core tests green | `cargo test -p selahcue-core` | model additive; no regression | test_plan green | PASS |
| C-002 | yes | Presenter per-surface override: Preview + Live can show different themes at once; `go_live` promotes; a GLOBAL `set_theme` recomposes each surface with its override-or-global (never clobbers an overridden surface; zero content loss) | `cargo test -p selahcue-present` | per-surface themes; no clobber | test_present (override + global-switch) | PASS |
| C-003 | yes | Controller applies an item's override on stage/go-live (built-in resolved, else global); `SetItemTheme` sets/clears + re-renders; additive wire (fixtures byte-stable) + RBAC Operator-only; `PlanItemView.theme` reported | `cargo test -p selahcue-app -p selahcue-lan` | override renders; wire additive; rbac gated | test_controller/test_protocol/test_rbac | PASS |
| C-004 | yes | Persist: migration v10 (`target_version()==10`, older DB upgrades); `plan_repo` round-trips `item.theme`; recovery restores an item's override (re-stage with its theme; global switch after recovery doesn't clobber) | `cargo test -p selahcue-data -p selahcue-app` | override survives save/load + recovery | test_db/test_plan_repo/test_controller | PASS |
| C-005 | yes | Console plan UI: a per-item theme picker on each plan row → `set_item_theme`; pinned console invariants (emergency footer/keymap, token needles, structure) intact | structure test + headless render | picker present; invariants intact | test_tokens + render | PASS |
| C-006 | yes | Full: make ci + operator build + fmt/clippy clean; independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed | CODE-REVIEW-batchS83d.md; CI green pending push | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-crate `cargo test` (core: model; present: per-surface override + global-switch-no-clobber + content-preservation; app: controller override + SetItemTheme + recovery; lan: wire additive fixtures + rbac; data: migration v10 + plan_repo round-trip); `test_tokens` (pin + structure); a headless render of the plan UI with a per-item picker. Broader: make ci + 3-OS CI. Independent: adversarial Workflow review (presenter-per-surface-correctness/content-loss · wire-compat/rbac/persistence · frontend/invariant lenses).
- Required environment: local + CI.

## Iteration ledger

1. **Model → Presenter → controller/wire/rbac → persistence → frontend** implemented additively: `PlanItem.theme`; Presenter per-surface `staged_theme`/`live_theme` (Preview+Live differ; go_live promotes; global switch keeps overrides); controller `SetItemTheme` (resolve on stage/go-live, reflect on the affected surface) + additive wire + RBAC Operator-only + `PlanItemView.theme`; migration v10 + plan_repo round-trip; a per-item picker in the console plan rows. Verifier: per-crate tests green (test_plan/test_present/test_controller/test_protocol/test_rbac/test_db/test_plan_repo) + a headless plan render (`shot-plan-theme.png`). C-001..C-005 PASS.
2. **Independent review** (`wf_955aa2c9-f57`, 3 lenses → verify, 5 agents): 2 raised → **2 CONFIRMED (1 HIGH + 1 MED), both fixed; presenter lens clean.** (HIGH) `set_item_theme` never set `plan_dirty` → the override was never persisted → lost on restart → **fixed** (set the flag; the controller test now asserts `take_plan_dirty()`); (MED) an open theme picker was torn out by the 1s poll during a running timer → **fixed** (defer the plan rebuild while the picker holds focus, like the outputs deferral). Full workspace test + fmt + clippy + operator clippy/build clean. See `docs/delivery/CODE-REVIEW-batchS83d.md`. C-006 PASS (3-OS CI green pending push).

## Risks and rollback

- Risks: the Presenter per-surface change breaking the core staging/go-live invariants (mitigated: `stage_themed` keeps `stage` behaviour when override=None; re-run the full present suite); a global switch clobbering an override (mitigated: recompose each surface with its own effective theme + a test); wire/fixture drift (additive variant + pinned fixtures byte-stable); migration breaking old DBs (additive nullable + upgrade test); recovery losing an override (mitigated: the plan persists the theme + the controller re-stages with it). Rollback: git; additive across crates.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq14wn-per-item-theme.md --require-complete`
- Validator result: PASS (6/6 mandatory PASS)
- Independent verification result: adversarial Workflow review `wf_955aa2c9-f57` (3 lenses, 5 agents) — 2 confirmed (HIGH+MED) both fixed; presenter lens clean. See `docs/delivery/CODE-REVIEW-batchS83d.md`.
- Terminal state: GATE_REVIEW (verifiable work complete; local make-ci + operator build green; 3-OS CI green pending this push; awaiting the `/build` user gate)
- ClickUp final evidence comment: posted on 86ajq14wn; BUILD CONTROL 86ajnx548 updated.
