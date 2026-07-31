# Code Review — Batch: plan-render dedup narrowing (audit M1, 86ajnx548)

- **Scope:** audit follow-up **M1** ([`docs/quality/AUDIT-memory-perf-latency.md`](../quality/AUDIT-memory-perf-latency.md) §2). The operator Live Console's plan-render dedup key was `const key = JSON.stringify(view)`, which includes `view.timer`; the host advances `view.timer` every second during a countdown, so the whole plan list (every row + a per-row theme `<select>` of all built-in + saved themes) was torn down (`plan.innerHTML=""`) and rebuilt **every poll** even though nothing plan-visible changed — the exact churn the console-render sig already guards against by excluding `view.timer`. Fix: narrow the key to exactly the fields the plan render reads. Executed via `/goal` (`TASK-86ajnx548-plan-render-dedup.md`, validator PASS 2/2 `--require-complete`). **Operator-webview only** (`dist/app.js`); no host/wire/RBAC/persistence change.
- **Method:** an adversarial Workflow review (`wf_856f033b-706`, **2 lenses** → refute-by-default verify, ultracode): **completeness** (does the narrowed key drop any field the plan render reads?) and **regression** (does narrowing break the focus-defer / in-flight-click protection / any plan-visible change / key collision?).
- **Outcome:** **6 findings raised → all INFO → 0 confirmed defects.** No change needed; the fix is complete and regression-sound.

## What shipped

```js
// before
const key = JSON.stringify(view);
// after
const key = JSON.stringify([view.plan_name, view.items, view.themes, view.saved_themes]);
```

The plan-build block reads exactly four top-level `view.*` fields — `plan_name`, `items` (each item carries `is_live`/`is_staged`/`title`/`kind`/`slide_count`/`slide_index`/`id`/`theme`), `themes`, `saved_themes` — all four are in the new key. Fields excluded (`timer`, `live_index`/`staged_index`, scriptures, global `theme`, `screen_themes`, `blackout`, `transcript`, `detections`) are read only by the sibling syncs (`syncChrome`/`syncSavedThemes`/`syncTranscript`/`syncDetections`) which run **before** the plan early-return and each carry their own change-key.

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | completeness | INFO | The narrowed key contains every top-level `view.*` the plan-build block reads (plan_name/items/themes/saved_themes); per-item fields ride inside `items` | **Complete — no dropped field, no stale-render path.** |
| 2 | regression | INFO | `editing`/`confirmDelete` returns + focused-`item-theme` defer fire before the key compare and never read the key; cancelled-edit restore is `act()`-driven (`lastRendered=""`), not timer-diff-driven | **Unaffected by the narrowing.** |
| 3 | regression | INFO | Genuine plan changes rebuild via both the `act()` forced path (local ops) and the poll key-diff (remote) — every such change mutates one of the four keyed fields | **Rebuild preserved.** (Reviewer cross-checked `operator.rs` ItemView + `controller.rs` — per-item flags are nested in each item, so `JSON.stringify(view.items)` captures select/advance/reorder/rename/add/remove/per-item-theme/slide-advance.) |
| 4–6 | regression | INFO | No plan-visible change carried only by an excluded field; no two distinct plan states collide on the key; the per-second teardown is eliminated | **Sound.** |

**0 confirmed defects.** The narrowing removes rebuilds **only** where none of the four keyed fields changed — precisely the running-countdown case. In-flight click protection improves (fewer rebuilds racing a click).

## Verification

- **Headless** (Chrome + `window.__TAURI__` stub): **61/61** (was 58; +3 M1). Drives `render()` directly with crafted view deltas: a timer-only delta leaves the plan's first-row node identity **stable** (no rebuild); an items delta yields **2 fresh rows** (rebuild). `node --check dist/app.js` clean.
- **Invariant:** no host/wire/RBAC/persistence change; the sibling syncs (chrome/saved-themes/transcript/detections) are untouched and keep their own change-keys.
- **Owner on-device QA (optional):** the definitive "the console no longer flickers/churns while a countdown runs" is owner-visible in the real Tauri app; the headless node-identity assertion is the strongest proof short of the GUI.
- **CI:** operator-shell (macOS/Ubuntu/Windows) — pending this push.

## Follow-ups

- Closes audit ticket **#4** (queued in the audit report §4). Remaining audit follow-ups unchanged: M2 `ServicePlan.items` cap, M3 LAN session cap, M4 transcript DOM client cap, M5 console RGBA decode, plus the LOW cluster (L1/L3 + optional hardening).
