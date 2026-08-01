# Code Review — Batch: per-screen preview (86ajq321k follow-up)

- **Scope:** the per-screen theme engine (`86ajq321k`) already renders each Audience screen (main/lower-third/stream) under its own theme (`compose_screen`), but that method was **called only by tests** — an operator could set a lower-third/stream theme yet not *see* it (those screens have no physical output; NDI is R-later). Expose the built render so each screen's design is **visible + verifiable** at design time: a `GetScreenFrame` wire command + a Screens-page per-screen preview canvas, mirroring the console `GetConsoleThumbnails`/`render_console` read-only preview. Executed via `/goal` (`TASK-86ajq321k-per-screen-preview.md`, validator PASS `--require-complete`). Additive; no wire `VERSION` / RBAC-wildcard / migration change.
- **Method:** an adversarial Workflow review (read-only/determinism · additive/RBAC/no-drift · frontend-preview → refute-by-default) `wf_0e5dc9b9-0cb` **plus** the committed Chrome + WebKit CI gates. The read-only + frontend lenses returned SOUND from the workflow; the additive/RBAC lens **errored twice** on the harness's StructuredOutput retry cap (`wf_bad5a7b6-636`) with no valid output, so it was performed **directly** (source read of `protocol.rs`/`rbac.rs`/`operator.rs` + the three pinning tests) rather than trusting a flaky agent.
- **Outcome:** **all three lenses SOUND — 0 findings.**

## What shipped

- **Wire (`protocol.rs` + `rbac.rs`):** additive `Command::GetScreenFrame { screen, max_w, max_h }` (tag `get_screen_frame`) → `ServerMessage::ScreenFrame { screen, frame: Option<ThumbView> }` (event `screen_frame`, `skip_serializing_if` on frame). `GetScreenFrame => Monitor` (a read; exhaustive match). VERSION unchanged (2).
- **Controller (`controller.rs` + `operator.rs`):** `apply(GetScreenFrame)` → the existing `compose_screen(screen)` → host-clamped thumbnail (`≤480×270`) → `ThumbView::from_rgba`; added to the read-only (non-`state_dirty`) command set — it dispatches no command, runs no tick, and cannot change the audience output. `OperatorShell::screen_frame` (Local) + `RemoteOperator::screen_frame` (wire) + a `render_screen` Tauri command.
- **Operator (`dist/app.js` + `app.css`):** the Screens page shows a small live preview `<canvas>` per audience screen, filled by `renderScreenPreviews` via `render_screen` (debounced 120 ms, gated on the Screens surface being active, refreshed on a live-content/theme change). `drawConsoleFrame` refactored to share `blitFrame`.

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | read-only | INFO | `GetScreenFrame` is a genuine **read-only, deterministic, bounded** preview — `compose_screen` is a `&self` pure read, no command/tick/`state_dirty`, blackout blacks all screens, unknown id → `None`, doubly host-clamped to `≤480×270`; the audience output can never change. The controller test asserts `live_output()` bytes are unchanged after a preview + blackout blacks all three. | No change — sound. |
| 2 | frontend | INFO | The preview is **debounced + Screens-surface-gated** (no per-poll fetch storm), the ≤3 canvases are recreated only on an `outputsKey` rebuild after `innerHTML=""` (no canvas/listener growth), `blitFrame` is byte-identical to the old blit + guards a malformed payload, and a Remote/older host without `render_screen` → the fetch `continue`s (leaves the placeholder, no crash). The async fetch loop is un-reentrancy-guarded but bounded + benign (mirrors the console prior art). | No change — sound. |
| 3 | additive-rbac *(direct)* | INFO | Additive wire — `VERSION` stays **2** (`protocol.rs:15`); `GetScreenFrame`/`ScreenFrame` are new serde-tagged variants; `frame` carries `#[serde(default, skip_serializing_if="Option::is_none")]` (pinned fixtures byte-stable). `Command::GetScreenFrame { .. } => Monitor` sits in an **exhaustive** `required_permission` match with **no `_ =>` wildcard** (`rbac.rs:120`) — a new command that forgot its arm would fail the build. `RemoteOperator::screen_frame` matches `ScreenFrame { frame, .. } => Ok(frame)` and rejects any `other` reply with `TransportError::Protocol` (`operator.rs:789`). | No change — sound. Pinned by `screen_frame_round_trips_and_is_additive` (asserts VERSION 2 + skip-if-none) + `viewer_can_only_monitor` + the clean exhaustive-match build. |

**No HIGH; no false-pass.**

## Verification

- **Workspace:** `cargo test --workspace` **476/0** (+3: the wire round-trip, the controller `GetScreenFrame`, the RBAC extension); `--features server`/`encryption` green; fmt/clippy clean (workspace + operator); operator build clean.
- **Both CI gates run** on the runner: CI `30689037612` `completed → success`; the operator-Linux logs show `=== 70 checks, 0 FAIL ===` (Chrome — incl. `per-screen: the three screens render DIFFERENT designs at once`) **and** `=== WebKit smoke: 5 checks, 0 FAIL ===`.
- **Owner on-device QA (optional):** the definitive "the lower-third/stream previews look right on the real Tauri app" is owner-run; the headless assertions (3 canvases render + differ, one per screen) are the strongest short of the GUI.

## Follow-ups

- Physical secondary-output delivery (NDI/stream transport) — R-later, unchanged. Add/delete virtual screen + enable/disable. Streaming secondary frames to a Remote controller beyond the loopback `ThumbView` already used.
