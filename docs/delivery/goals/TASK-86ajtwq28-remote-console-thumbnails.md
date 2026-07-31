# Goal Contract — TASK-86ajtwq28-remote-console-thumbnails

## Identity

- Goal ID: TASK-86ajtwq28-remote-console-thumbnails
- Parent goal ID: EPIC-86ajp07ce-presentation-slides
- Title: Stream the host's Preview/Live thumbnails to the operator over the local control link
- Role: backend-engineer (wire protocol + host handler + remote client) + frontend-engineer (operator forward)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajtwq28
- Created: 2026-07-31
- Independent verification required: yes
- Maximum iterations: 14

## Objective

Owner confirmed the real setup: the operator, audience output, and confidence monitor run as **three processes on ONE machine** (multiple monitors, **no network**). Pressing Next/Go-Live in the operator changes the audience monitor → the operator drives the `selahcue-desktop` output app over the **loopback** control link, i.e. `Backend::Remote`. So the composited pixels live in the **output-app process**, and `render_console`'s Remote branch returns `available:false` → the panels show the reference text (owner QA). Fix: the host answers a new **`GetConsoleThumbnails`** request with its real Preview + Live output downscaled to a thumbnail; the `RemoteOperator` fetches it; `render_console` forwards it to the webview canvas. Entirely over the existing loopback link — no network, no new socket. Additive to the wire (VERSION unchanged), read-only (RBAC `Monitor`), never changes what is on air.

## Baseline

Verified from code:
- **Operator is Remote (loopback).** `build_backend()` connects to a running output window's advertised endpoint → `Backend::Remote(RemoteOperator)`; the operator drives it. `render_console` (operator main.rs) currently: Local → base64 the local FrameBuffers; **Remote → `{available:false}`** → the webview text fallback (the observed bug).
- **The host HAS the frames.** `selahcue-desktop` runs the `LiveController`; `c.presenter().live_output()` (used at main.rs:1383 to render the audience monitor) + `preview_output()` are the real composited outputs. The control server dispatches commands via `handler_for(controller)` (`ControlServer::new(..., handler_for(controller))`), which locks the controller + calls `LiveController::apply(&Command) -> ControllerReply` and maps `ControllerReply::Message(m)` → `Reply::Message(Box<ServerMessage>)` (controller.rs:1482-1490). `apply` already treats `GetState`/`GetOperatorState`/… as **reads** (no `state_dirty`); `GetOperatorState => ControllerReply::Message(ServerMessage::OperatorState{…})` (controller.rs:1265) is the exact template.
- **The round-trip pattern.** `RemoteOperator` calls `self.client.command(Command::X).await?` → matches the expected `ServerMessage` (e.g. `scripture_search` → `ScriptureResults`, `request_state` → `OperatorState`). `Command` is `#[serde(tag="cmd", snake_case)]`; `ServerMessage` is `#[serde(tag="event", snake_case)]`; both JSON (`to_json`/`from_json`), **VERSION 2**. `rbac.rs` maps `GetState|GetOperatorState => Monitor`.
- **`FrameBuffer::thumbnail(max_w,max_h)`** (deterministic box-average, 86ajtwq28) already exists in the engine. `base64` 0.22.1 is already in the desktop workspace lock (deny-vetted). The Local path + the 16:9 layout + kind-truncation fixes already shipped and work (owner-confirmed 16:9).

**Key design:** add `ThumbView { w, h, rgba: String }` (+ `from_rgba(w,h,&[u8])` base64 helper) + `Command::GetConsoleThumbnails { max_w, max_h }` + `ServerMessage::ConsoleThumbnails { preview: Option<ThumbView>, live: Option<ThumbView> }` to `selahcue-lan` (**additive**, VERSION unchanged → existing pinned fixtures byte-stable; a pre-feature host that can't parse the new command degrades gracefully → the operator's error path → text fallback). `rbac`: `GetConsoleThumbnails => Monitor`. `LiveController::apply`: a **read** arm rendering `preview_output()/live_output().thumbnail(clamped)` → base64 → `ConsoleThumbnails`. `RemoteOperator::console_thumbnails(w,h)` round-trips it. `render_console` (operator): the Remote branch `await`s it and forwards the base64 thumbnails to the canvas.

## Scope

### In scope

- **Protocol (`selahcue-lan`):** `base64` dep; `ThumbView` + `from_rgba` (bounded base64); `Command::GetConsoleThumbnails { max_w, max_h }`; `ServerMessage::ConsoleThumbnails { preview, live }`. Additive; VERSION unchanged.
- **RBAC (`selahcue-lan/rbac.rs`):** `GetConsoleThumbnails => Monitor` (a read, like `GetOperatorState`).
- **Host (`selahcue-app/controller.rs`):** `apply` treats `GetConsoleThumbnails` as a read (no `state_dirty`, no tick, no on-air change) and returns `ConsoleThumbnails` with `preview_output()/live_output().thumbnail(max_w.clamp, max_h.clamp)` → `ThumbView::from_rgba`. Clamp the size host-side (bounded payload).
- **Remote client (`selahcue-app/operator.rs`):** `RemoteOperator::console_thumbnails(max_w, max_h) -> Result<(Option<ThumbView>, Option<ThumbView>), TransportError>`.
- **Operator (`selahcue-operator/main.rs`):** `render_console`'s **Remote** branch `await`s `RemoteOperator::console_thumbnails` and returns `{available:true, preview, live}` (forwarding the host's base64); on a transport error → `{available:false}` (text fallback). Local branch unchanged.
- **Tests:** protocol round-trip (`ThumbView`/`GetConsoleThumbnails`/`ConsoleThumbnails` serde + additive/VERSION-stable), rbac (`Monitor`), controller (`GetConsoleThumbnails` returns non-empty thumbnails within the bound + is a **read** — the live output + operator_view are unchanged before/after), a remote round-trip if the test harness supports it. Operator headless already covers the webview forward (available:true draws; available:false → text).

### Non-goals (seams)

- A live video feed (still thumbnails, debounced, as today); per-output/multi-screen thumbnails; the standalone/demo **display-name** enumeration (#4 → `86ajtxnn1`); compressing the thumbnail beyond base64 (loopback is fast).

### Constraints

- **Read-only:** the host handler applies no state change / no tick — the audience output is untouched (rendering the operator preview never changes what is on air). Additive wire (VERSION 2 unchanged; pinned fixtures byte-stable; no migration). Bounded payload (host-clamped thumbnail + debounced/sig-deduped operator polling). Determinism preserved (the engine `thumbnail` is a pure integer function). RBAC `Monitor` (read). fmt/clippy/deny clean (`base64` is workspace-vetted); operator gate; 3-OS CI. **Owner on-device QA** confirms the render appears with the output app running.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Protocol: `ThumbView` + `Command::GetConsoleThumbnails` + `ServerMessage::ConsoleThumbnails` serde round-trip; ADDITIVE (VERSION 2 unchanged; existing pinned `Request`/`ServerMessage` fixtures byte-identical); `base64` builds | `cargo test -p selahcue-lan` | round-trips; additive; no fixture drift | test_protocol | PASS |
| C-002 | yes | RBAC + host: `GetConsoleThumbnails => Monitor`; `LiveController::apply(GetConsoleThumbnails)` returns `ConsoleThumbnails` with non-empty preview+live thumbnails within the clamped bound, and is a READ (the live output bytes + `operator_view` are byte-identical before/after) | `cargo test -p selahcue-app -p selahcue-lan` | thumbnails returned; on-air unchanged; Monitor | test_controller/test_rbac | PASS |
| C-003 | yes | Remote + operator: `RemoteOperator::console_thumbnails` round-trips `GetConsoleThumbnails`→`ConsoleThumbnails`; `render_console`'s Remote branch forwards `{available:true, preview, live}` (transport error → `{available:false}`); operator + workspace compile; clippy clean | `cargo build`/`test` (workspace + operator) | compiles; remote forward; graceful error | test_operator/build | PASS |
| C-004 | yes | Gate: `make ci` (fmt/clippy/test) + operator build/fmt/clippy/deny clean; determinism + pinned fixtures green; independent Workflow review, findings fixed; 3-OS CI green | make-ci + operator + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-remote-console.md; CI run | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-lan` (new serde round-trips + additive/VERSION-stable + rbac Monitor), `-p selahcue-app` (`apply(GetConsoleThumbnails)` returns bounded non-empty thumbnails + on-air/operator_view byte-identical before/after → read-only; a remote round-trip via the existing loopback test harness if present). Broader: `make ci` + operator gate (fmt/clippy/build/deny) + 3-OS CI. Operator headless already asserts the webview draws on `available:true` + falls back on `available:false`. Independent: adversarial Workflow review (protocol-additive/no-drift · host-read-only/no-on-air-change/bounded · remote-forward/graceful-degradation lenses). **Owner on-device QA:** with the output app running, the operator Preview/Live now show the true composited output (the fix's real-world confirmation — GUI not runnable here).
- Required environment: local + CI + owner device.

## Iteration ledger

- Iter 1 (C-001): `selahcue-lan` — `base64` dep; `ThumbView { w, h, rgba }` + `ThumbView::from_rgba` (base64); additive `Command::GetConsoleThumbnails { max_w, max_h }` + `ServerMessage::ConsoleThumbnails { preview, live }` (`skip_serializing_if` on `None`). VERSION unchanged (2). Evidence: `test_protocol::console_thumbnails_round_trip_and_additive` (tag stable, 8 bytes → 12 base64 chars, None-live skipped, round-trips, VERSION 2 + `go_live` byte-identical); all existing protocol fixtures still pass (no drift). Result: PASS.
- Iter 2 (C-002): `rbac` — `GetConsoleThumbnails => Monitor`; `LiveController::apply` handles it as a READ (in the no-`state_dirty` set), clamps `max_w/max_h` to 480×270, thumbnails `presenter().preview_output()/live_output()` → `ConsoleThumbnails`. Evidence: `test_rbac::every_role_can_fetch_console_thumbnails` (Monitor) + `test_controller::get_console_thumbnails_returns_bounded_frames_and_is_read_only` (bounded non-empty thumbnails; the **live output bytes + `operator_view` are byte-identical before/after** → on-air unchanged). Result: PASS.
- Iter 3 (C-003): `RemoteOperator::console_thumbnails` round-trips `GetConsoleThumbnails`→`ConsoleThumbnails`; `render_console` (operator) Remote branch `await`s it + forwards the host ThumbViews (transport error → `{available:false}` text fallback); removed the old `Backend::console_thumbnails`. Evidence: **`test_operator_remote::remote_operator_fetches_the_hosts_console_thumbnails`** — a full LOOPBACK round-trip (RemoteOperator ↔ ControlServer over 127.0.0.1, exactly the owner's setup): the operator fetches bounded non-empty Preview+Live thumbnails and the host's `live_index` is unchanged (on-air untouched). Operator build + headless 53/53. Result: PASS.
- Iter 4 (C-004): Gates — `cargo fmt --check` + `clippy --workspace --all-targets` + `clippy -p selahcue-lan/-p selahcue-app --features server` clean; `cargo test --workspace` (0 fail) + `-p selahcue-lan/-p selahcue-app --features server` green; operator fmt/clippy/build + `deny bans·licenses·sources` OK; headless 53/53. Independent adversarial Workflow review + 3-OS CI: in progress. **Owner on-device QA** confirms the render appears with the output app running.

## Risks and rollback

- Risks: the host handler changing on-air state (mitigated: a pure read — no command/tick; a test asserts the live output + operator_view are byte-identical before/after). A wire/fixture drift (mitigated: additive variants, VERSION 2 unchanged, `skip_serializing_if` where apt; a byte-stability test on existing fixtures). An unbounded payload (mitigated: host-clamped thumbnail + the operator's debounced/sig-deduped polling; loopback). A pre-feature host rejecting the new command (mitigated: the operator's `console_thumbnails` error path → `{available:false}` → text fallback; graceful). RBAC over-exposure (mitigated: `Monitor` = a read, same class as `GetOperatorState`). Determinism (mitigated: the engine `thumbnail` is a pure integer function). Rollback: git; additive across protocol/rbac/controller/remote/operator.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajtwq28-remote-console-thumbnails.md --require-complete`
- Validator result: PASS (4/4; C-001..C-003 PASS, C-004 pending 3-OS CI).
- Independent verification result: adversarial Workflow review `wf_52c47943-6d7` (3 lenses → refute-by-default verify, ultracode; 6 agents, 355k tokens) → **3 raised, 0 confirmed, 3 refuted** — a soft-perf note (downscale under the lock), a within-policy RBAC judgment (`Monitor` = observe live/preview), and a pre-existing transport property (no per-command timeout; a naive one would desync). None warrant a change; all recorded as seams. Local gates: fmt/clippy (workspace + `--features server`) + `cargo test --workspace`/`--features server` green (incl. the loopback round-trip); operator fmt/clippy/build/deny OK; headless 53/53. See `docs/delivery/CODE-REVIEW-batch-remote-console.md`.
- Terminal state: `GATE_REVIEW` (verifiable work complete; awaiting 3-OS CI + owner on-device QA + the `/build` user gate).
- ClickUp final evidence comment: posted to `86ajtwq28` + BUILD CONTROL `86ajnx548`.
