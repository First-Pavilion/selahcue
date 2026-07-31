# Goal Contract — TASK-86ajtwq28-preview-live-render

## Identity

- Goal ID: TASK-86ajtwq28-preview-live-render
- Parent goal ID: EPIC-86ajp07ce-presentation-slides
- Title: Operator Preview/Live panels show the TRUE composited render
- Role: frontend-engineer (console panels) + backend-engineer (thumbnail + render command)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajtwq28
- Created: 2026-07-31
- Independent verification required: yes
- Maximum iterations: 12

## Objective

Owner refine #7 — replace the operator console's **Preview | Live** text placeholders ("Nothing staged" / "Output idle" + title/caption) with the **actual composited output the audience preview and live see** (the same compositor + blackout/timer/live state), drawn to a `<canvas>` like the Theme Designer's `preview_theme` preview, refreshing on state changes with a bounded payload. Rendering the preview must NEVER change what is on air (read-only readback). No wire/RBAC/migration change; the Remote backend (pixels live on a remote host) degrades honestly to the text panel.

## Baseline

Verified from code:
- **Console panels are text-only.** `dist/index.html` `#preview-panel`/`#live-panel` hold `#preview-title`/`#preview-cap` and `#live-title`/`#live-cap`; `dist/app.js` `syncChrome()` calls `setPanel("preview", …)` / `setPanel("live", …)` with a title+caption derived from `OperatorView` indices/refs — **no pixels**.
- **The truth is available locally.** `Backend::Local(OperatorShell)` wraps `Arc<Mutex<LiveController>>`; `LiveController::presenter()` (controller.rs:905) → `Presenter::preview_output()`/`live_output()` (present.rs:267/272) return the **real composited `FrameBuffer`** at the output resolution (demo = **1920×1080**), already reflecting theme / per-item theme / **blackout** / timer / the live scene. Reading them is more faithful than re-composing (which would drop blackout/timer/identify).
- **Remote has no local pixels.** `Backend::Remote(RemoteOperator)` drives an output window over pinned-TLS and receives an `OperatorStateView` (indices/refs) — no framebuffers. True render there is a **wire-streaming seam** (out of scope); degrade to the text panel.
- **The pattern exists.** `preview_theme` (main.rs:394) composites a sample at 480×270 → base64 RGBA → the webview draws it to `<canvas id="td-preview">` via `ImageData`. `FrameBuffer` exposes `bytes()`/`width()`/`height()`/`pixel()` (fields private); no downscale helper yet.

**Key design:** add a deterministic integer **`FrameBuffer::thumbnail(max_w, max_h)`** (box-average downscale, aspect-preserving, bounded, NFR-014) to the engine; `OperatorShell::console_thumbnails(max_w, max_h) -> (FrameBuffer, FrameBuffer)` reads `preview_output()`/`live_output()` and thumbnails them (read-only — no command applied); a host `render_console(max_w, max_h)` command returns base64 RGBA + dims for both (Local) or `{available:false}` (Remote); the webview adds a `<canvas>` to each panel and a **debounced** `renderConsole()` that blits the true frames and keeps the title/caption text for accessibility + as the Remote/empty fallback.

## Scope

### In scope

- **Engine (`raster.rs`):** `FrameBuffer::thumbnail(&self, max_w: u32, max_h: u32) -> FrameBuffer` — deterministic integer **box-average** downscale that fits the source within `max_w×max_h` preserving aspect; returns an equivalent buffer when already within bounds; bounded + total (clamps `max_w`/`max_h` ≥ 1; never panics on 1×1 or extreme inputs). Pure integer → byte-identical cross-OS.
- **App (`operator.rs`):** `OperatorShell::console_thumbnails(&self, max_w, max_h) -> (FrameBuffer, FrameBuffer)` — under the controller lock, tick, then return `(presenter().preview_output().thumbnail(…), live_output().thumbnail(…))`. Read-only: applies NO command (the on-air state is untouched).
- **Operator host (`main.rs`):** `render_console(max_w, max_h, state)` `#[tauri::command]` → `Backend::Local` → `{ available: true, preview: {rgba,w,h}, live: {rgba,w,h} }` (base64 RGBA); `Backend::Remote` → `{ available: false }`. `max_w`/`max_h` clamped to a bounded ceiling (≤ 640×360) so a hostile request can't over-allocate. Registered in `generate_handler!`.
- **Operator webview (`dist/`):** a `<canvas>` in `#preview-panel` + `#live-panel`; a **debounced** `renderConsole()` invokes `render_console` with the panels' pixel size, blits each frame via `ImageData`; on `available:false` / error / empty, hides the canvas and shows the existing text panel. Called from the view-refresh path + on console-surface activation. Blackout (already black in the true frame) + the accessible title/caption are preserved.
- **Tests:** engine (`thumbnail` — averages a known frame, deterministic, aspect-preserved, no-op when smaller, bounded/no-panic on 1×1 + huge max), app (`console_thumbnails` returns two frames within the bound and does NOT change the live output), operator headless (`render_console` invoked with a bounded size; `available:true` draws the canvas; `available:false` keeps the text fallback; the preview refresh applies no control command).

### Non-goals (seams)

- **Per-output multi-screen** thumbnails; a **live video feed** (this is a periodic still render). **Remote true pixels** (streaming framebuffers over the LAN wire — a protocol change). Bilinear/gamma-correct downscaling (integer box-average is the deterministic thumbnail).

### Constraints

- **Read-only:** rendering the preview/live thumbnail applies NO command — the on-air state and preview⟂live isolation are untouched. Determinism (NFR-014): `thumbnail` is a pure integer function. Bounded: thumbnail size is clamped host-side; the payload is a small still, refreshed debounced. No wire/RBAC/migration change (VERSION/`target_version` unchanged). fmt/clippy/deny clean; 3-OS CI.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Engine: `FrameBuffer::thumbnail(max_w,max_h)` downscales deterministically (byte-identical), box-averages, preserves aspect within the bound, is a no-op when already smaller, and is bounded (no panic on 1×1 / huge max); `cargo test -p selahcue-engine` passes | `cargo test -p selahcue-engine` | thumbnail correct + deterministic + bounded | test_raster | PASS |
| C-002 | yes | App: `OperatorShell::console_thumbnails` returns the preview + live frames thumbnailed within the requested bound and applies NO control command (the live output is byte-identical before/after) | `cargo test -p selahcue-app` | two frames; on-air unchanged | test_operator/test_controller | PASS |
| C-003 | yes | Host: `render_console` returns `{available:true, preview, live}` (base64 RGBA + dims) for Local within the clamped size; `{available:false}` for Remote; registered; operator + workspace compile | `cargo build` (operator + workspace) | compiles; both backends handled | build | PASS |
| C-004 | yes | Frontend: the console Preview/Live panels draw the true frames to a `<canvas>` (bounded, debounced refresh); the text caption + blackout state are preserved; `available:false`/error falls back to text; WKWebView-safe + keyboard/a11y intact | operator `node --check` + headless | canvas drawn on available; text fallback otherwise; no control command fired | headless test | PASS |
| C-005 | yes | Gate: make ci + operator build/fmt/clippy/deny clean; determinism green; independent Workflow review, findings fixed; 3-OS CI green | make-ci + operator + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-preview-live.md; CI run 30609825939 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-engine` (thumbnail: box-average of a known 4×4→2×2, determinism, aspect within bound, no-op when smaller, 1×1 + huge-max no-panic), `-p selahcue-app` (console_thumbnails returns two bounded frames + the live output bytes are unchanged after a render call). Broader: `cargo build` operator + workspace; make ci + operator gate + 3-OS CI. Operator headless: `render_console` invoked with a bounded size, `available:true` draws the canvas, `available:false` keeps the text fallback, and a preview refresh fires no control command. Independent: adversarial Workflow review (thumbnail-determinism/bounded · read-only-no-onair-change · frontend-canvas/perf/a11y/remote-fallback lenses).
- Required environment: local + CI.

## Iteration ledger

- Iter 1 (C-001): Added `FrameBuffer::thumbnail(max_w,max_h)` to engine `raster.rs` — a deterministic integer **box-average** downscale (each destination pixel = the integer mean of its source block), aspect-preserving, never-upscale, `max` clamped to `1..=MAX_DIMENSION`, `u64` channel sums (a 1×1 target covers the whole image). Evidence: `test_raster` — `thumbnail_box_averages_a_known_frame` (2×2→1×1 = the exact mean), `thumbnail_preserves_aspect_within_the_bound_and_is_deterministic` (byte-identical + aspect), `thumbnail_never_upscales_and_is_bounded` (no-op when smaller; 1×1/`u32::MAX` no-panic; uniform frame averages to itself). Result: PASS.
- Iter 2 (C-002): `OperatorShell::console_thumbnails(w,h)` (app `operator.rs`) reads `presenter().preview_output()`/`live_output()` and thumbnails them — **read-only** (no command, no tick). Evidence: `test_operator::console_thumbnails_return_the_bounded_frames_and_never_touch_on_air` — both frames within the bound (160×90 for a 16:9 source) and the full-res live readback is byte-identical before/after a render call (on-air unchanged). Result: PASS.
- Iter 3 (C-003): host `render_console(max_w,max_h)` command (`main.rs`) → `Backend::Local` base64 RGBA + dims for both frames (clamped to 480×270), `Backend::Remote` `{available:false}`; registered in `generate_handler!`. Evidence: operator + workspace `cargo build` clean. Result: PASS.
- Iter 4 (C-004): webview `dist/` — a `<canvas>` per panel; `renderConsole()` (debounced 120 ms, console-surface-gated) invokes `render_console` at the panel size, blits via `ImageData` with a `bytes.length === w*h*4` guard, sets `.has-render`; `available:false`/error/exception → `setConsoleRender(false)` text fallback; a sig-dedup skips re-fetching an identical frame on the 1 s poll; `showSurface('console')` always renders; canvas `aria-hidden` (title/cap carry the a11y label). Evidence: `node --check` clean; headless **51/51** (6 new #7: render_console invoked, both panels show the render, canvas at frame size, read-only fires no control command, available:false → text fallback). Result: PASS.
- Iter 5 (C-005): Gates — `cargo fmt --check` + `clippy --workspace --all-targets` clean; `cargo test --workspace` green (0 fail); operator fmt/clippy/build + `cargo deny check bans licenses sources` = OK (no dep change; gtk3 `unmaintained` = accepted RISK-011). Independent adversarial Workflow review `wf_53f55c83-4ca` = 2 raised / 0 confirmed / 2 refuted (one pre-fixed, one efficiency insight applied — `view.timer` dropped from the console sig). Commit `cd08515` → **3-OS CI run 30609825939 GREEN** (rust ×3 OS, operator-shell ×3 OS, launch-smoke ×2, RustSec, licenses+SBOM all success; flutter skipped). Result: PASS. Terminal state `GATE_REVIEW` — awaiting the `/build` user gate.

## Risks and rollback

- Risks: a preview render mutating on-air state (mitigated: read-only readback — no command applied; a test asserts the live bytes are unchanged). Non-deterministic downscale breaking NFR-014 (mitigated: pure integer box-average; a determinism test). Payload/perf (mitigated: host-clamped thumbnail size + debounced refresh + still, not video). Remote showing stale/blank pixels (mitigated: `available:false` → honest text fallback; a documented wire seam). Overflow/panic on extreme sizes (mitigated: clamp + i64/bounded arithmetic + a no-panic test). Rollback: git; additive across engine/app/operator.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajtwq28-preview-live-render.md --require-complete`
- Validator result: PASS (5/5; C-001..C-004 PASS, C-005 pending 3-OS CI).
- Independent verification result: adversarial Workflow review `wf_53f55c83-4ca` (3 lenses → refute-by-default verify, ultracode) → **2 raised, 0 confirmed, 2 refuted**. #1 (sig omits `view.items`) was already fixed proactively (verifier confirmed `view.items` present); #2 (`view.timer` forcing redundant re-renders) refuted as a sub-defect but acted on (timer is a stage-monitor-only overlay per `controller.rs` `tick` → removed from the console signature). Local gates: `cargo fmt --check` + `clippy --workspace --all-targets` + `cargo test --workspace` (0 fail); operator fmt/clippy/build + `deny bans·licenses·sources` OK; headless 51/51. See `docs/delivery/CODE-REVIEW-batch-preview-live.md`.
- Terminal state: `GATE_REVIEW` (verifiable work complete; awaiting 3-OS CI green + the `/build` user gate).
- ClickUp final evidence comment: posted to `86ajtwq28` (→ qa) + BUILD CONTROL `86ajnx548`.
