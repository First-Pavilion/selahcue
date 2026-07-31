# Goal Contract — TASK-86ajtwq28-console-render-fix

## Identity

- Goal ID: TASK-86ajtwq28-console-render-fix
- Parent goal ID: EPIC-86ajp07ce-presentation-slides
- Title: Fix the operator console — true render actually shows, 16:9 panels, plan-item label overlap
- Role: frontend-engineer (webview + a small host command change)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajtwq28
- Created: 2026-07-31
- Independent verification required: yes
- Maximum iterations: 12

## Objective

Owner QA on the real app found the shipped Preview/Live true-render (86ajtwq28) **does not display** — the panels still show the scripture reference text and render **stretched**. Fix three defects: (#3) the render never appears because `render_console` is the only **sync** Tauri command taking `State` + returning a bare `Value` where every working command is `async`→`Result`; (#1) the console panels are **stretched** because `.obs-row`'s default `align-items: stretch` overrides the `.outpanel` `aspect-ratio: 16/9`; (#2) the service-plan `.item .kind` label overflows under the theme dropdown (no truncation). Also **harden the headless test** so the boot-render path is exercised with a real `view` (the prior stub returned `null`, masking #3). Owner refine #4 (real display names) is registered as a separate follow-up.

## Baseline

Verified from code + a focused diagnostic:
- **#3 root cause.** A headless diagnostic (`scratchpad/diag_boot.py`) with a *real* `view` stub → `render_console_called=true, has_render=true`: the JS boot path (`act`→`render`→`syncChrome`→ sig-dedup →`scheduleConsoleRender`→`renderConsole`→`invoke("render_console")`) is **correct**. The failure is host-side: `render_console` (main.rs) is a **sync** `#[tauri::command]` taking `State<'_, AppState>` and returning `serde_json::Value`; every other command is `async fn … -> Result<…, String>`. The prior headless test masked this because its `view` stub returned `null` (so `syncChrome(null)` threw before the render path) and the test triggered the render via a nav-click crutch instead.
- **#1 root cause.** `.obs-row { display:flex }` (app.css:208) has the default `align-items: stretch`; the `.outpanel` (app.css:344) has `aspect-ratio: 16/9` + (in the row) `flex: 1`. `stretch` gives the flex item an explicit cross-size, **overriding** `aspect-ratio`, so the panel height collapses to min-content (~95px) → a short wide strip.
- **#2 root cause.** `.item .title` truncates (`nowrap/overflow/ellipsis`, app.css:247-249); `.item .kind` (app.css:251-254) does **not**, so a long kind label ("ANNOUNCEMENT") overflows the flex-squeezed `.main` (narrowed by the always-reserved `.tools` + the 104px `.item-theme`) and renders *under* the dropdown.
- `render_console`'s body only reads `state.backend.console_thumbnails(…)` (read-only) + base64-encodes; making it `async` is safe (no `.await` while a lock is held — `console_thumbnails` returns owned frames).

**Key design:** (#3) `async fn render_console(max_w, max_h, state) -> Result<serde_json::Value, String>`, returning `Ok(json!(…))`; the existing JS (`await invoke` in try/catch) already handles an `Ok` value / a rejected `Err`. (#1) `.obs-row { align-items: flex-start }` + `.outpanel { max-height: 32vh }` so `aspect-ratio` governs the height (16:9) without overflowing the viewport. (#2) `.item .kind { white-space: nowrap; overflow: hidden; text-overflow: ellipsis }`. Harden the headless test to stub `view` with a real `OperatorView` and assert the boot render fires **without** the nav-click.

## Scope

### In scope

- **Host (`main.rs`):** change `render_console` from `fn … -> serde_json::Value` to `async fn … -> Result<serde_json::Value, String>` returning `Ok(…)`; keep the read-only body + the 480×270 clamp.
- **CSS (`app.css`):** `#1` `.obs-row { align-items: flex-start }` + `.outpanel { max-height: 32vh }` (canvas already `object-fit: contain`, so any residual letterbox is clean); `#2` `.item .kind` truncation.
- **Test (`td_headless.py`):** stub `view` with a real `OperatorView`; assert the boot render fires (`render_console` called + `.has-render` set) with **no** nav-click; assert the plan-item `.kind` computed `white-space === nowrap`; assert a console panel's rendered aspect is ~16:9 (height ≈ width·9/16) with the surface laid out.
- **Follow-up:** register owner refine #4 (Screens page shows real OS display names via Tauri monitor enumeration for the standalone/demo backend) as a new ClickUp story.

### Non-goals (seams)

- Refine #4 itself (real display names — the separate follow-up); streaming true pixels to a REMOTE controller (unchanged seam); any change to what is on air.

### Constraints

- Read-only preview render is preserved (async change does not add any command/tick). No wire/RBAC/migration change. Determinism unaffected (no engine change). Operator fmt/clippy/build + deny clean; headless green; 3-OS CI. **Owner on-device QA required** to confirm #1 + #3 on the real Tauri app (this environment cannot launch the GUI).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `render_console` is `async fn … -> Result<serde_json::Value, String>` (matching the working command pattern); operator + workspace compile; clippy clean | `cargo build` + `clippy` (operator + workspace) | compiles; async+Result | build | PASS |
| C-002 | yes | The boot render path is exercised headlessly with a REAL `view` stub: `render_console` is invoked and `.has-render` is applied WITHOUT any nav-click; the panels compute to ~16:9 (not a collapsed strip) | operator `node --check` + headless | boot render fires; 16:9 panels | headless test | PASS |
| C-003 | yes | The plan-item `.kind` label truncates (computed `white-space:nowrap` + `overflow:hidden`), so it cannot overflow under the theme dropdown | headless computed-style check | kind truncates | headless test | PASS |
| C-004 | yes | Gate: operator build/fmt/clippy/deny clean; independent Workflow review, findings fixed; refine #4 registered as a follow-up; 3-OS CI green | operator + Workflow + ClickUp + CI | all green; review fixed; #4 tracked | CODE-REVIEW-batch-console-render-fix.md; CI run | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo build` (operator + workspace) + `clippy` (async `render_console` compiles). Operator headless: a real `view` stub → the boot render fires (`render_console` called + `.has-render`) with NO nav-click (proves the real boot path); `.item .kind` computes `white-space:nowrap`; a laid-out console panel computes to ~16:9. `node --check`. Independent: adversarial Workflow review (async-command-correctness/no-on-air-change · CSS-layout-regression · test-masking-closed lenses). Broader: operator gate + 3-OS CI. **Owner on-device QA** confirms the render + layout on the real app.
- Required environment: local + CI + owner device.

## Iteration ledger

- Iter 1 (diagnosis): Reproduced/isolated via `scratchpad/diag_boot.py` — with a REAL `view` stub the JS boot path fires `render_console` + applies `.has-render` (`render_console_called=true, has_render=true`), proving the JS is correct and the failure is host-side. Identified `render_console` as the only sync `#[tauri::command]` with `State` returning a bare `Value`. Also discovered the headless harness never loaded `app.css` (the injected `<base>` followed the `<link>`), so CSS-dependent checks passed via UA fallbacks.
- Iter 2 (C-001, #3): Made `render_console` `async fn … -> Result<serde_json::Value, String>` returning `Ok(…)`, body unchanged (read-only). Evidence: operator `cargo build` + `clippy` clean; matches every other (working) command. Result: PASS (owner on-device QA to confirm the real-app render).
- Iter 3 (C-002/C-003, #1+#2): CSS — `.obs-row { align-items: flex-start }` (aspect-ratio now governs the panel height) + `.outpanel { max-height: 32vh }`; `.item .kind` gains `white-space:nowrap; overflow:hidden; text-overflow:ellipsis`. Fixed the headless `<base>` placement so `app.css` loads. Evidence: headless **53/53** with real CSS — `render_console` fires on BOOT (no nav-click), Preview/Live show `.has-render`, the preview panel computes to **16:9 (h/w=0.57)**, and `.item .kind` computes `white-space:nowrap`. A focused `diag2.py` confirmed `panel=331×186`, `panel_ar=16/9`, `panel_display=flex`, `kind_ws=nowrap`. Result: PASS.
- Iter 4 (C-004): Registered owner refine #4 (real display names via Tauri monitor enumeration) as follow-up story **86ajtxnn1**. Independent adversarial Workflow review + operator gate + 3-OS CI: in progress.

## Risks and rollback

- Risks: the async change not being the true host-side cause (mitigated: the JS boot path is proven correct by diagnostic; async+Result matches every working command — the highest-probability fix; owner QA confirms). A CSS layout fix regressing other breakpoints (mitigated: `align-items:flex-start` + `max-height` are localized to `.obs-row`/`.outpanel`; canvas `object-fit:contain` tolerates letterboxing; headless aspect check). The `.kind` truncation hiding useful text (mitigated: it only ellipsises overflow; the full kind is short). Rollback: git; all changes additive/localized.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajtwq28-console-render-fix.md --require-complete`
- Validator result: PASS (4/4; C-001..C-003 PASS, C-004 pending 3-OS CI).
- Independent verification result: adversarial Workflow review `wf_6f0621ff-a01` (3 lenses → refute-by-default verify, ultracode) → **1 raised, 0 confirmed, 1 refuted**. The diagnosis-soundness challenge was refuted with reasoning that corroborates the fix (the centered reference text = `.has-render` absent = render-not-applied = host-side; `cargo check` confirms the async signature). Operator fmt/clippy/build/check + `deny bans·licenses·sources` OK; headless 53/53 with real `app.css` loading. See `docs/delivery/CODE-REVIEW-batch-console-render-fix.md`. **Owner on-device QA required** for the real-app render.
- Terminal state: `GATE_REVIEW` (verifiable work complete; awaiting 3-OS CI + owner on-device QA + the `/build` user gate).
- ClickUp final evidence comment: posted to `86ajtwq28` + BUILD CONTROL `86ajnx548`; follow-up #4 = `86ajtxnn1`.
