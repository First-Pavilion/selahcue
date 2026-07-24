# Code Review — batch 7n: operator → output-window wiring

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context Workflow (`wwzeesec0`, 8 agents). No self-approval.
**Date:** 2026-07-24
**Scope:** the LAN protocol/RBAC additions (`GetOperatorState`, `OperatorStateView`),
the `RemoteOperator` control client + `LiveController` apply arm (`selahcue-app`), the
endpoint discovery (`selahcue-desktop`), and the Tauri `Backend` (`selahcue-operator`).

## Verdict: PASS (1 confirmed → fixed; 3 dismissed)

**4 findings raised → 1 confirmed → fixed.** Verified after the fix: `selahcue-lan
--features server` 40; `selahcue-app --features server` operator 8 + **remote-operator
2 E2E** + remote 2 E2E; workspace 173; operator `cargo check` + clippy clean; desktop
builds clean.

## Confirmed & fixed

### (integration-security, low) — client had no connect timeout → operator could hang window-less
`ControlClient::connect` awaited TCP + TLS + WebSocket + auth with **no timeout at any
layer**, while the *server* time-boxes the identical pre-auth phase
(`DEFAULT_HANDSHAKE_TIMEOUT`). Because the Tauri operator runs `connect` under
`block_on` in `.setup()`, a peer that accepts TCP but stalls the TLS handshake would
block the main thread **forever** — no window, and the intended graceful fallback to the
local demo never runs. The trigger is realistic: the output window's endpoint file was
never cleaned up, so a stale endpoint pointing at a now-reused loopback port could land on
an accept-but-stall peer.

**Fix (two parts):**
1. **`ControlClient::connect` now wraps the whole attempt in `tokio::time::timeout`
   (`CONNECT_TIMEOUT = 10s`)**, mirroring the server — a stalled peer degrades to
   `TransportError` instead of hanging. This protects every client (operator, CLI,
   future mobile). Existing E2E connect well within the budget (still green).
2. **The output window now removes the endpoint file on clean exit** (best-effort), so a
   later operator shell doesn't attach to a defunct window in the first place.

## Dismissed (3)

- **(protocol-rbac) `GetOperatorState` (Monitor) lets a Viewer read the full plan.**
  Verified accurate but **within scope**: `Monitor` is documented as "observe live/preview
  state", and `Viewer` is the read-only "confidence/state" role whose purpose is to show
  the plan and what's next. Consistent with `GetState`; breaks no spec/test/confidentiality
  boundary. A policy note, not a defect.
- **(integration-security) Silent Local fallback looks identical to Remote.** True that the
  fallback is logged only to stderr and the demo plan matches the desktop plan, but in this
  batch's scope it's a disclosed behavior (start the output window first), not a defect. A
  connection-status indicator in the UI is a reasonable future enhancement (noted below).
- **(integration-security) Predictable `/tmp` endpoint on multi-user Linux.** Re-flags the
  documented demo shortcut; already mitigated (chmod `0600` on unix; per-user `$TMPDIR` on
  macOS) with negligible residual impact on a loopback-only convenience.

## What passed clean (no findings)
- **Conversions:** `OperatorView ↔ OperatorStateView` and `ItemView ↔ PlanItemView` are
  lossless and field-correct (no `is_live`/`is_staged` or `live_index`/`staged_index`
  transposition).
- **Remote client:** `act()` (send mutating command → `GetOperatorState`) tolerates a
  `Denied` reply without erroring (the returned view shows unchanged state — E2E-verified);
  unexpected replies map to `TransportError::Protocol`; `&mut self` serializes calls.

## Follow-ups noted (not blocking)
- A **remote/local connection indicator** in the operator UI/view-model (so the operator
  can see whether it's driving the real output or the standalone demo).
- Bump the wire `VERSION` when the protocol is first deployed to mixed peers (greenfield
  today — all peers build together).

## Independence statement
Reviewed by fresh-context agents that did not author the code. Each finding was
adversarially verified by a separate agent defaulting to `real=false`; the one that
survived was fixed at the transport layer (+ a defense-in-depth cleanup) and re-verified
(lan 40, app E2E green, clippy clean).
