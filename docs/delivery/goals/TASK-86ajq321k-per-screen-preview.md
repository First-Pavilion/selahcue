# Goal Contract — TASK-86ajq321k-per-screen-preview

## Identity

- Goal ID: TASK-86ajq321k-per-screen-preview
- Parent goal ID: BUILD-selahcue (Stage 8 — per-screen theme follow-up)
- Title: Make the per-screen themed renders VISIBLE — a GetScreenFrame wire command + a Screens-page per-screen preview
- Role: backend-engineer (wire + controller) + frontend-engineer (Screens preview)
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: BUILD CONTROL 86ajnx548 (⚠ ClickUp MCP rate-limited — story 86ajq321k follow-up)
- Created: 2026-08-01
- Independent verification required: yes (adversarial review + wire round-trip + the committed webview gate)
- Maximum iterations: 10

## Objective

The per-screen theme engine (86ajq321k) already renders each Audience screen (`main`/`lower-third`/`stream`) under its OWN theme from the same live content — `LiveController::compose_screen(screen)` produces a themed `FrameBuffer` per screen. But that method is **called only by tests**: there is no wire command to fetch a secondary screen's frame and no operator UI shows it, so an operator can set a `lower-third`/`stream` theme yet **cannot see the result** (those screens have no physical output — NDI is R-later). Expose the already-built render so each screen's design is **visible + verifiable** at design time, WITHOUT the R-later transport: a `GetScreenFrame` wire command (mirroring `GetConsoleThumbnails`) + a small per-screen preview canvas on the operator Screens page.

## Baseline

Verified from code: `LiveController::compose_screen(screen) -> Option<FrameBuffer>` (controller.rs:572) renders any of `AUDIENCE_SCREENS = ["main","lower-third","stream"]` under `screen_themes[screen]` (resolved via `resolve_theme`, built-in OR saved), blackout-aware; only tests call it. `screen_themes` + `SetScreenTheme` + persistence are shipped. The wire already has the `GetConsoleThumbnails { max_w, max_h } → ConsoleThumbnails { preview, live }` pattern (I added it) with a `ThumbView { w, h, rgba }` + `ThumbView::from_rgba` (base64) and RBAC `GetConsoleThumbnails => Monitor`. The operator console renders those thumbnails to a `<canvas>` (`drawConsoleFrame` + `b64ToBytes`). The Screens page (`renderOutputs`, app.js) shows per-screen theme pickers (`themePickerFor`) but no rendered preview.

## Scope

### In scope

- **Wire (`selahcue-lan/protocol.rs` + `rbac.rs`):** `Command::GetScreenFrame { screen: String, max_w: u32, max_h: u32 }` → `ServerMessage::ScreenFrame { screen: String, frame: Option<ThumbView> }` (additive; `skip_serializing_if` where apt; reuse `ThumbView`). RBAC `GetScreenFrame => Monitor` (read-only, like `GetConsoleThumbnails`).
- **Controller (`selahcue-app`):** `apply(GetScreenFrame { screen, max_w, max_h })` → `compose_screen(screen)` → downscale-clamp to `max_w×max_h` (reuse the console thumbnail scaling) → `ThumbView::from_rgba`; `None` for an unknown screen. Read-only (no command/tick/state change). Operator-shell + Remote plumbing (mirror `console_thumbnails`).
- **Operator (`selahcue-operator/dist/`):** the Screens page shows a small **live preview canvas** per audience screen (main/lower-third/stream), fetched via `GetScreenFrame` (debounced, signature-deduped, Screens-surface-gated — like the console render), blitted with the existing `b64ToBytes`. So the operator SEES that the three screens render different designs.
- **Tests:** controller (each screen composes a distinct themed frame via the command; blackout blacks all; unknown screen → `None`; read-only — no control command fired), wire (a `GetScreenFrame`/`ScreenFrame` round-trip + RBAC-denied for a Viewer/below-Monitor), operator headless (the Screens page fetches + shows a per-screen preview; 3 screens differ).

### Non-goals

- Physical secondary-output delivery (NDI/stream transport) — R-later, unchanged. Add/delete virtual screen. Per-screen preview on the mobile client. Streaming secondary frames to a Remote controller over the wire beyond the loopback `ThumbView` already used.

### Constraints

- Additive: no wire `VERSION` change (new command/event via serde tags); RBAC exhaustive-match updated (no wildcard). Read-only (a preview never changes the audience output — determinism + the console-render read-only invariant). Bounded (the thumbnail is resolution-capped like the console one). `make ci` + operator `node --check` + the committed Chrome + WebKit gates green; 3-OS CI green (verified by conclusion).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Wire: `GetScreenFrame`/`ScreenFrame` added (additive, `Monitor` RBAC); a round-trip + an RBAC-denied test pass; VERSION unchanged | `cargo test -p selahcue-lan` (+ `--features server`) | round-trip ok; denied for < Monitor | test_protocol (`screen_frame_round_trips_and_is_additive`) + test_rbac (viewer Monitor) | PASS |
| C-002 | yes | Controller: `apply(GetScreenFrame)` returns a themed thumbnail per screen (distinct for distinct themes; blackout blacks all; unknown → None), read-only | `cargo test -p selahcue-app` | per-screen frames; read-only | test_controller (`get_screen_frame_command_returns_a_themed_thumbnail_per_screen`) | PASS |
| C-003 | yes | Operator: the Screens page shows a per-screen preview via `GetScreenFrame`; `node --check` + the committed headless gate assert 3 per-screen previews render | operator `node --check` + headless | previews render; screens differ | `node --check` OK; headless **70/70** (+4 per-screen: 3 canvases, one per screen, main red, three differ) | PASS |
| C-004 | yes | Gate: make ci + operator gate green; independent adversarial Workflow review, findings fixed; 3-OS CI green (verified by run conclusion) | make-ci + operator + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-per-screen-preview.md (3 lenses SOUND, 0 findings); CI `30689037612` `completed → success` (operator log `=== 70 checks, 0 FAIL ===` + `WebKit smoke: 5 checks, 0 FAIL`) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `-p selahcue-lan` (round-trip + RBAC-denied + VERSION unchanged), `-p selahcue-app` (per-screen themed thumbnails; blackout; unknown; read-only), operator headless (the Screens page fetches + blits a per-screen preview; 3 screens differ). Broader: make ci + operator gate + the committed Chrome + WebKit gates + 3-OS CI (verified by conclusion). Independent: adversarial Workflow review (read-only / additive-no-drift / RBAC / the preview is bounded + debounced + doesn't disturb the audience output).
- Required environment: local + CI.

## Iteration ledger

- Iter 0 (C-001/C-002, backend): additive wire — `Command::GetScreenFrame { screen, max_w, max_h }` + `ServerMessage::ScreenFrame { screen, frame: Option<ThumbView> }` (`protocol.rs`, skip-if-none frame, VERSION unchanged); RBAC `GetScreenFrame => Monitor` (exhaustive, read). Controller `apply(GetScreenFrame)` → the EXISTING `compose_screen(screen)` → host-clamped thumbnail → `ThumbView::from_rgba` (mirrors the console read; added to the read-only command list so it never dirties state). `OperatorShell::screen_frame` (Local) + `RemoteOperator::screen_frame` (wire) + a `render_screen` Tauri command (Local FrameBuffer→base64 / Remote ThumbView), registered. Tests: `screen_frame_round_trips_and_is_additive` (round-trip + skip-if-none + VERSION 2), `viewer_can_only_monitor` extended (a Viewer CAN GetScreenFrame — a Monitor read), `get_screen_frame_command_returns_a_themed_thumbnail_per_screen` (3 distinct themed thumbnails; blackout blacks all → identical; unknown→None; read-only — the audience output never changes). Result: PASS.
- Iter 1 (C-003, frontend): `dist/app.js` — refactored `drawConsoleFrame` to share `blitFrame(cv, frame)`; added `renderScreenPreviews`/`scheduleScreenPreviews` (fetch `render_screen` per audience screen, debounced 120ms, gated on the Screens surface being active) + `screenPreviewFor(screen)` canvas in `renderOutputs` for main/lower-third/stream; triggered from `showSurface("screens")`, the end of `renderOutputs`, and the live-content/theme change signal. `dist/app.css` — a 16:9 `.screen-preview`. Evidence: `node --check` OK; operator build/fmt/clippy clean; committed headless **70/70** (+4: 3 preview canvases render with `has-render`, one per main/lower-third/stream, main shows its red themed frame, the three DIFFER). Result: PASS.
- Gate prep: full workspace + `--features server`/`encryption` test + independent adversarial review (`wf_0e5dc9b9-0cb`, read-only + additive-rbac + frontend lenses) running.
- Iter 2 (C-004, gate): workspace `cargo test` 476/0 (+`server`/`encryption`); fmt/clippy clean; operator build/`node --check` clean; committed Chrome headless **70/70** + WebKit smoke **5/5**. Independent review: the read-only + frontend lenses returned **SOUND** from `wf_0e5dc9b9-0cb`; the additive/RBAC lens errored twice on the workflow harness's StructuredOutput retry cap (`wf_bad5a7b6-636`) so it was performed **directly** — VERSION stays 2 (`protocol.rs:15`, asserted by `screen_frame_round_trips_and_is_additive`); `GetScreenFrame`/`ScreenFrame` additive serde variants with skip-if-none `frame`; `required_permission` exhaustive with **no wildcard** and `GetScreenFrame { .. } => Monitor` (`rbac.rs:120`, pinned by `viewer_can_only_monitor` + the clean build); `RemoteOperator::screen_frame` rejects a non-`ScreenFrame` reply (`operator.rs:789`). **3 lenses SOUND — 0 findings**; nothing to fix. 3-OS CI `30689037612` `completed → success` (verified by conclusion; operator log `=== 70 checks, 0 FAIL ===` + `WebKit smoke: 5 checks, 0 FAIL`). Result: PASS. Deliverable: `docs/delivery/CODE-REVIEW-batch-per-screen-preview.md`.

## Risks and rollback

- Risks: the preview disturbing the audience output (mitigated: `compose_screen` is a pure read of the current live content; no command/tick; the console-render read-only test pattern). A per-poll fetch storm (mitigated: debounce + signature-dedup + Screens-surface-gate, like the console render). RBAC drift (mitigated: exhaustive match + a denied test). Wire drift (mitigated: additive serde tags, VERSION unchanged, pinned fixtures). Rollback: git; additive across lan/app/operator.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq321k-per-screen-preview.md --require-complete`
- Validator result: PASS (4/4 mandatory criteria PASS)
- Independent verification result: 3 adversarial lenses (read-only · additive/RBAC · frontend) SOUND — 0 findings (2 via `wf_0e5dc9b9-0cb`, the additive/RBAC lens direct after the harness errored twice); + the committed Chrome 70/70 + WebKit 5/5 CI gates on the runner.
- Terminal state: GATE_REVIEW (verifiable work complete; paused for the `/build` user gate).
- ClickUp final evidence comment: pending — MCP rate-limited (~21h) all session; queued for BUILD CONTROL 86ajnx548 + story 86ajq321k follow-up.
