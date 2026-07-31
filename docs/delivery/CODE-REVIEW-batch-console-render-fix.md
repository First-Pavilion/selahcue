# Code Review — Batch: operator console render-fix (86ajtwq28, owner QA)

- **Scope:** owner QA on the **real Tauri app** found the shipped Preview/Live true-render (86ajtwq28) **did not display** — the panels still showed the scripture reference text and rendered **stretched**. Three fixes: (#3) the render never appeared because `render_console` was the only **sync** `#[tauri::command]` taking `State` + returning a bare `serde_json::Value` (every working command is `async`→`Result`); (#1) the panels were stretched because `.obs-row`'s default `align-items: stretch` overrode `.outpanel`'s `aspect-ratio: 16/9`; (#2) `.item .kind` had no truncation and overflowed under the theme dropdown. Plus a **test-integrity fix** (the headless harness never loaded `app.css`). Executed via `/goal` (`TASK-86ajtwq28-console-render-fix.md`, validator PASS 4/4). Operator-only (`src/main.rs` + `dist/app.css`); **no wire/RBAC/migration change**. Owner refine **#4** (real display names) registered as follow-up **86ajtxnn1**.
- **Method:** an adversarial Workflow review (`wf_6f0621ff-a01`, **3 lenses** → refute-by-default verify, ultracode; 4 agents, 268k tokens). Lenses: **async-command correctness / read-only** · **CSS layout regression** · **diagnosis soundness** (adversarially challenging whether the async fix addresses the real cause).
- **Outcome:** **1 raised → 0 confirmed → 1 refuted.** The diagnosis-soundness lens challenged "maybe the async change fixes nothing and it's all CSS"; the verifier **refuted it and corroborated the diagnosis**: per `app.css`, the centered reference text appears **only when `.has-render` is absent** — once a frame draws, the canvas shows and the text demotes to a small overlay chip. So the owner's screenshot (centered "Genesis 1:13") is definitively the **render-not-applied** state (a host-side `render_console` failure), *not* a collapsed-but-rendered panel. The two fixes therefore address **two distinct real symptoms**. `cargo check` on the operator confirmed the async signature is the canonical Tauri v2 pattern.

## Root-cause analysis (how the masking was found)

- The prior headless test gave false confidence: its `view` stub returned **`null`**, so `syncChrome(null)` threw before the render path ever ran — the test reached the render only via a **nav-click crutch**, hiding that the boot render never fired.
- A focused diagnostic (`diag_boot.py`) with a **real `view` stub** → `render_console_called=true, has_render=true`: the **JS boot path is correct** (`act`→`render`→`syncChrome`→ sig-dedup →`scheduleConsoleRender`→`renderConsole`→`invoke`). Therefore the failure is **host-side** — and `render_console` was the sole sync/`State`/bare-`Value` command.
- A second diagnostic (`diag2.py`) exposed that **`app.css` never loaded in headless**: the injected `<base>` was placed *after* `<link rel="stylesheet" href="app.css">`, and a `<base>` only affects URLs that follow it (HTML spec) — so `app.css` resolved against the `/tmp` temp file and 404'd. Every CSS-dependent assertion had been passing via UA/`[hidden]` fallbacks. With the base fixed, the panel measured `331×186` (`aspect-ratio: 16/9`, `display: flex`) and `.item .kind` computed `white-space: nowrap`.

## What shipped

- **#3 (`main.rs`):** `render_console` is now `async fn render_console(max_w, max_h, state: State<'_, AppState>) -> Result<serde_json::Value, String>` returning `Ok(…)` — matching every other command. The body is **unchanged**: read-only `console_thumbnails` (no command, no tick), the 480×270 clamp, base64. Async runs it off the WebView event thread (also moving the ~1.4 MB rasterize+base64 off the sync path); the existing JS (`await invoke` in try/catch) already handles a resolved value / a rejected `Err`.
- **#1 (`app.css`):** `.obs-row { align-items: flex-start }` so each `.outpanel`'s `aspect-ratio: 16/9` governs its height (a stretched flex item gets an explicit cross-size that overrides `aspect-ratio`, collapsing the panel to a ~95 px strip); `.outpanel { max-height: 32vh }` caps the height on very wide windows (canvas `object-fit: contain` → clean letterbox).
- **#2 (`app.css`):** `.item .kind { white-space: nowrap; overflow: hidden; text-overflow: ellipsis }` (like `.title`) so a long kind label can't overflow the flex-squeezed `.main` under the theme dropdown.
- **Test integrity (`td_headless.py`):** the `<base>` now precedes the `<link>` (real `app.css` loads); the `view` stub returns a **real `OperatorView`** so the **boot render path** is exercised with **no** nav-click; new assertions cover the 16:9 panel aspect + the `.kind` truncation.

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | diagnosis | (raised) | "The async fix likely fixes nothing; the CSS strip-collapse is the real defect." | **Refuted — corroborates the diagnosis.** Per `app.css`, the centered reference text shows only when `.has-render` is **absent**; a drawn frame demotes it to a chip. So "still showing the reference" = render-not-applied (host-side), which the async change targets — not a collapsed-but-rendered panel. The two fixes address two distinct real symptoms; `cargo check` confirms the async signature compiles as the canonical Tauri v2 pattern; read-only + clamps preserved. |

**0 confirmed defects.** The async-command lens confirmed no Send/lifetime/deadlock issue (no lock held across an await — `console_thumbnails` returns owned frames) and the read-only invariant holds. The CSS lens confirmed no regression (the fixes move toward the 16:9 design; truncation mirrors `.title`).

## Verification

- **Operator gate:** `cargo build` + `cargo check` clean (async `render_console` compiles), `cargo fmt --check` clean, `clippy -D warnings` clean, **`cargo deny check bans licenses sources` = OK** (no dependency change).
- **Headless interaction check** (Chrome + `window.__TAURI__` stub, **now loading the real `app.css`**): **53/53** — the console render fires on **boot with no nav-click**, both panels show `.has-render`, the preview panel computes to **16:9 (h/w = 0.57)**, `.item .kind` computes `white-space: nowrap`, the read-only path fires no control command, and `available:false` → the text fallback. `node --check` clean.
- **Invariants:** rendering the preview never changes on air (read-only, unchanged body); no wire/RBAC/migration change.
- **Owner on-device QA required:** the real Tauri app + a running WebView can't be exercised in this environment, so the definitive confirmation that the render now appears (and the panels look right) is owner-run. The evidence here (JS boot path proven; async matches every working command; `cargo check` clean; 16:9 layout verified) is the strongest available short of the GUI.
- **CI:** the operator-shell job (macOS/Ubuntu/Windows) — pending this push.

## Follow-ups

- **#4** real OS display names on the Screens page (Tauri monitor enumeration for the standalone/demo backend) → **86ajtxnn1**. Unchanged seams: streaming true pixels to a REMOTE controller; per-output multi-screen thumbnails; the deferred **line** shape kind; #5 fonts (`86ajq3225`), #8 scripture live-follow (`86ajtwq2b`).
