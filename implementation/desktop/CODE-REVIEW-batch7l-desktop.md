# Code Review — batch 7l: desktop output window ← remote control

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context Workflow (`wag2rpohk`, 8 agents). No self-approval.
**Date:** 2026-07-24
**Scope:** `selahcue-desktop` (`main.rs` — shared `LiveController` driven by local keys
AND a background Tokio control server), `selahcue-lan` (`CertPin::from_hex` + the
`remote` example CLI), with `selahcue-app` `LiveController::apply` as context.

## Verdict: PASS — 0 confirmed findings

**4 findings raised → 4 dismissed on adversarial verification (0 confirmed).** The
security lens found nothing. The two concurrency findings and the wiring finding are
three framings of one real-but-immaterial mechanism; the parser/CLI finding is a
cosmetic nit. Verified: workspace `cargo test` 155/155; `selahcue-lan --features server`
40 (incl. the new `from_hex` unit test) + `remote`/`demo` examples build; `selahcue-app
--features server` 10 unit + 2 E2E; clippy clean on all changed crates incl. examples.

## Raised → verified → dismissed

### (concurrency + wiring, ×2 framings) — UI mutex held across the vsync-blocking GPU present
**Real mechanism.** In `RedrawRequested`, the `MutexGuard` is held across the whole
`renderer.render(c.presenter().live_output())` call — the returned `&FrameBuffer`
borrows from the guard — including `get_current_texture()` / `present()` under
`PresentMode::Fifo`. A contending `handler_for` `controller.lock()` can therefore wait
up to ~one frame.

**Why dismissed (adversarial verify, both lenses independently `real=false`):**
1. Impact is **bounded to ≤1 frame (~8–16 ms)** — no deadlock, no indefinite starvation
   (the guard is released every frame). Commands are human-paced slide control, for which
   a sub-frame acquire delay is imperceptible.
2. On-screen latency is **vsync-gated by Fifo regardless** — narrowing the critical
   section would not measurably improve command-to-screen latency (the batch's actual goal).
3. The server runs on a **multi-thread runtime** with a single pre-paired loopback
   Producer — one worker parking ≤16 ms starves nothing.
4. The documented lock discipline ("std Mutex, no `.await` held across the lock in
   `handler_for`") **is preserved**; the finding invented a stronger "network handler is
   never blocked" property that was never promised.

**Disposition — acknowledged non-blocking nit (not fixed, by design):** the two safe
"fixes" are each net-negative — cloning the framebuffer under the lock adds ~8 MB/frame
memcpy churn to solve a non-problem; splitting `render()` into upload-under-lock +
present-after introduces a **stale-bind-group-on-resize** correctness trap in GPU code
that **cannot be runtime-verified in this build env** (no display). The current path is
user-confirmed working (batch 7j). The observation dissolves naturally when GPU-native
compositing lands (ADR-0002), where compose and present are already separate stages.
Recorded here rather than papered over.

### (parser-cli) — unknown-command exits 1 without echoing the command list
**Verified `real=false`.** The behavior is internally **consistent**: a structural
arg-count precondition failure exits 2 (and prints usage + commands); the three
value-validation errors (bad address, bad pin, unknown command) all route through the
same `Err`/`?` path and exit 1. The only residue is that the unknown-command message
doesn't re-echo the command list — a trivial polish gap in a hand-run, explicitly-
documented foundation-demo CLI whose real counterpart is a Flutter client. No
correctness/crash/security/resource impact.

### (security) — no findings
The lens confirmed: the server binds **`127.0.0.1:0` (loopback only)**, not `0.0.0.0`;
the pinned-TLS + device-auth + RBAC path is preserved (the CLI and window use the same
authenticated server path); `run_server` failures are surfaced via `eprintln!` and only
**disable remote control** rather than crashing the app; the printed banner exposes only
what a local operator needs. The fixed demo token + pre-paired Producer are the
documented, loopback-scoped demo shortcut (real QR + host-confirmation pairing is the
mobile-client batch) and break no guarantee in that threat model.

## Notes
- `CertPin::from_hex` is byte-indexed (`bytes[i*2] as char` → `to_digit(16)`), so
  non-ASCII/multibyte and odd-length inputs are rejected without panic; it accepts both
  cases and round-trips `to_hex` (unit test `pin_hex_round_trips`).
- The window reads `presenter().live_output()` (already-composed; not recomposed on
  read), so blackout/clear/go-live are reflected on the next repaint. `about_to_wait`
  drives continuous vsync-paced repaint so a **remote-only** change (not a winit event)
  appears within a frame.
- The control loop itself (remote command → server → controller → presenter output)
  remains E2E-verified in `selahcue-app/tests/test_remote.rs`; batch 7l is the desktop
  packaging of that verified loop plus a runnable client.

## Independence statement
Reviewed by fresh-context agents that did not author the code, over the listed files,
using the crate's own test/lint tooling. Each finding was adversarially verified by a
separate agent defaulting to `real=false`; none survived. No code change was warranted.
