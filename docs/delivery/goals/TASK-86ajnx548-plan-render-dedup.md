# Goal Contract — TASK-86ajnx548-plan-render-dedup

## Identity

- Goal ID: TASK-86ajnx548-plan-render-dedup
- Parent goal ID: BUILD-selahcue (Stage 8 quality — audit follow-up M1)
- Title: Stop the Live Console plan list rebuilding every second during a countdown (audit M1)
- Role: frontend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: BUILD CONTROL 86ajnx548 (⚠ ClickUp MCP rate-limited — follow-up queued in the audit report §4)
- Created: 2026-07-31
- Independent verification required: yes (focused skeptical review + a headless regression test)
- Maximum iterations: 6

## Objective

Fix audit finding **M1** ([`docs/quality/AUDIT-memory-perf-latency.md`](../../quality/AUDIT-memory-perf-latency.md)): the operator Live Console's plan-render dedup key is `JSON.stringify(view)`, which includes `view.timer`. The host advances `view.timer` every second during a countdown, so the key differs every poll → the plan list is torn down (`plan.innerHTML=""`) and fully rebuilt every second (every row + a per-row theme `<select>` of all built-in + saved themes), even though nothing plan-visible changed. Narrow the dedup key to exactly the fields the plan render reads so it rebuilds only on genuine plan changes — mirroring the console-render sig, which already deliberately excludes `view.timer`. Operator-webview-only; no host/wire/RBAC change.

## Baseline

Verified from code (`dist/app.js`): `render(view)` runs `syncChrome`/`syncSavedThemes`/`syncTranscript`/`syncDetections` (each with its OWN change-key) BEFORE the plan early-returns, then gates the plan rebuild on `key === lastRendered` with `key = JSON.stringify(view)` (app.js:25/37). The plan-build block (app.js:39-170) reads ONLY: `view.plan_name` (39), `view.items` (40/44 — each item's `id`/`is_live`/`is_staged`/`title`/`kind`/`slide_count`/`slide_index`/`theme`), `view.themes` (132), `view.saved_themes` (139). It does NOT read `view.timer`, `view.transcript`, `view.detections`, `view.blackout`, `view.theme` (global), `view.screen_themes`, or output status — those are handled by the sibling syncs. The console-render sig (app.js:262-269) already excludes `view.timer` with a comment; that exclusion was never applied to the plan key.

## Scope

### In scope

- Replace the plan dedup key with `JSON.stringify([view.plan_name, view.items, view.themes, view.saved_themes])` so a poll that changes only `view.timer` (or transcript/detections) does NOT rebuild the plan, while any genuine plan change (items/order/selection/per-item theme, plan name, theme lists) still does.
- A headless regression assertion: a view differing ONLY in `timer` leaves the plan DOM untouched (stable node identity), while a view with changed `items` rebuilds it.

### Non-goals

- The other audit findings (M2–M5, L1–L4) — separate follow-ups.
- Any host/wire/RBAC/persistence change; any change to the sibling syncs (chrome/saved-themes/transcript/detections) which already have correct change-keys.

### Constraints

- Correctness: the narrowed key MUST include every `view.*` field the plan render reads (else the plan renders stale). Verified field set above; a skeptical review must re-confirm no field was dropped. No functional/keyboard/focus regression (the focused-`item-theme` defer stays). `node --check` + headless clean.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The plan dedup key is narrowed to the plan-render field set; a timer-only view delta does not rebuild the plan, an items delta does | headless harness | timer-only → stable DOM; items → rebuild | headless test | PASS |
| C-002 | yes | No dropped-field regression: every `view.*` the plan render reads is in the key; operator `node --check` clean; existing headless checks still pass | skeptical review + `node --check` + headless | review confirms complete field set; all green | review note; headless | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Headless (Chrome + `window.__TAURI__` stub): feed a view, then a second view identical except `timer` incremented → assert the plan container's first-row node is the SAME element (not rebuilt) and `lastRendered` unchanged; then a view with an added/removed item → assert the plan rebuilt. Plus the existing 58 checks stay green.
- Independent: a focused skeptical review challenging whether the narrowed key drops any field the plan render depends on (re-reading app.js:39-170).
- Required environment: local (headless; the real Tauri WebView is owner-run).

## Iteration ledger

- Iter 0 (C-001): enumerated the plan-build field set by reading `app.js:39-170` — the block reads exactly `view.plan_name` (39), `view.items` (40/44, incl. per-item `id`/`is_live`/`is_staged`/`title`/`kind`/`slide_count`/`slide_index`/`theme`), `view.themes` (132), `view.saved_themes` (139); nothing else (timer/transcript/detections/blackout/global-theme/screen_themes are read only by the sibling syncs). Narrowed the key to `JSON.stringify([view.plan_name, view.items, view.themes, view.saved_themes])`. Added 3 headless assertions: a timer-only delta keeps the plan's first-row node identity (no rebuild), an items delta yields 2 fresh rows (rebuild). Evidence: `node --check` OK; headless **61/61** (was 58; +3 M1). Result: PASS.
- Iter 1 (C-002): independent adversarial review `wf_856f033b-706` (2 lenses — completeness + regression → refute-by-default; ultracode). **6 findings, ALL INFO, 0 HIGH/MEDIUM → 0 defects.** Completeness: the narrowed key contains all four top-level fields the plan block reads; no dropped field. Regression: SOUND — the `editing`/`confirmDelete` returns + focused-`item-theme` defer fire BEFORE the key compare (unaffected), and cancelled-edit restore is driven by `act()` zeroing `lastRendered`, not by the timer diffing the key; genuine plan changes rebuild via both the `act()` forced path and the poll key-diff (the reviewer cross-checked `operator.rs` ItemView + `controller.rs` — per-item `is_live`/`is_staged`/`slide_*`/`theme` are nested in each item, so `JSON.stringify(view.items)` captures them); no plan-visible change is carried only by an excluded field; no key collision. Result: PASS.

## Risks and rollback

- Risk: dropping a field the plan render reads → stale plan (e.g. forgetting `saved_themes` → a new saved theme wouldn't appear in row pickers). Mitigated: the field set was enumerated by reading the full plan-build block + a skeptical review re-confirms; a genuine-change headless assertion guards it. Rollback: git; single-key change in one file.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajnx548-plan-render-dedup.md --require-complete`
- Validator result: PASS (run below)
- Independent verification result: adversarial review `wf_856f033b-706` (completeness + regression, refute-by-default) — 6 findings, all INFO, 0 defects; the narrowed key is complete + regression-sound.
- Terminal state: **VERIFIED_COMPLETE** — operator-webview-only dedup narrowing; C-001/C-002 PASS; headless 61/61; 0 review defects; pending only the 3-OS CI run (this push).
- ClickUp final evidence comment: (queued — MCP rate-limited; audit report §4 ticket #4 closed by this commit; BUILD CONTROL `86ajnx548` update queued)
