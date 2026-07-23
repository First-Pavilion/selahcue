# Code Review — batch 7e: TLS-pinned WebSocket transport (`server` feature)

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), fresh-context workflow. No self-approval.
**Date:** 2026-07-23
**Scope:** `selahcue-lan` `server` feature — `pinning.rs`, `tls.rs`, `server.rs`,
`client.rs`, `wire.rs`, `Cargo.toml`, and `tests/test_server.rs`.

## Verdict: PASS (4 confirmed findings remediated; TLS lens clean)

15 agents ran (4 review lenses + 11 verify; **3 verify agents errored** on a schema
retry cap — assessed manually below). **8 findings raised → 4 confirmed.** The
**TLS-security lens found nothing** — the pinning verifier is sound (it delegates the
handshake-signature check to the crypto provider and does a full-length pin compare, so
a MITM replaying the public cert without its private key is rejected; the custom
verifier fully replaces CA/hostname validation). All 4 confirmed findings are **pre-auth
resource-exhaustion / DoS** issues — the unbounded-growth class the no-leak requirement
targets — and all are fixed and re-verified: `cargo test --features server` **39/39**
(incl. 5 E2E), clippy clean.

## Confirmed & fixed (all in `server.rs`)

### M1 — accept loop died permanently on any `accept()` error (fd-exhaustion DoS)
`listener.accept().await?` propagated an `io::Error` (e.g. EMFILE under fd exhaustion)
out of `run()`, permanently stopping the operator from accepting **any** further
controllers until the app restarted.
**Fix:** the accept loop now matches on the result — on error it backs off briefly and
continues, never returns. Accept errors can no longer kill the server.

### M2 / M3 — no handshake/auth timeout and no connection cap (slowloris → task/fd/counter leak)
Any LAN host could open connections and either stall the TLS ClientHello or complete TLS
but never send the first `AuthRequest`; each parked a task, socket, per-connection
buffers, and a `ConnGuard` increment **forever** (pre-auth, no token needed) —
`active_connection_count()` climbed without bound. This is exactly the unbounded-growth
leak the user's requirement forbids.
**Fix:** the pre-auth phase (TLS + WS handshake + first auth frame) is wrapped in
`tokio::time::timeout` (default 10s), so stalled peers are dropped and their
task/socket/slot reclaimed; and `run()` gates spawns with an `Arc<Semaphore>` (default
128) that bounds concurrent connections (fds/tasks/memory) with natural backpressure.
**Regression test:** `stalled_half_open_connections_are_reaped` opens 8 raw TCP
connections that never begin TLS and asserts `active_connection_count()` returns to 0.

### L1 — default 64 MiB WebSocket message size allowed large pre-auth buffering
`accept_async` used tungstenite's 64 MiB default `max_message_size`, so a peer could
force 64 MiB of buffering with its first frame (multiplied per connection).
**Fix:** `accept_async_with_config` with `max_message_size`/`max_frame_size` bounded to
64 KiB — ample for the tiny JSON control frames.

## Errored verify agents — assessed manually

Three verify agents hit the structured-output retry cap and produced no verdict. I read
their raw review-phase findings and assessed each:

- **"No test proves the handshake *signature* is verified"** (test-adequacy): the code is
  correct — the TLS-security lens independently confirmed `verify_tls13_signature`/
  `verify_tls12_signature` delegate to the provider. A unit test of this is not
  constructible (a malicious server presenting the pinned cert would need its private key
  to complete the handshake, which by definition it lacks — so the pin already rejects
  it). Documented as a known limitation; not a code defect.
- **"Client ignores request_id correlation"** (transport-correctness): the current client
  is a simple request→response client on an in-order connection with no unsolicited
  server pushes, so the next frame *is* the response. Correlating by `request_id` matters
  once the server pushes unsolicited events (future work); noted, not a present defect.

## Dismissed (verified not-a-defect)

- "command before auth" and "malformed frame" test gaps — the invariants are enforced by
  control flow (`request_loop` is reachable only after `authenticate()?`); correct,
  deliberately-chosen branches, missing only a test.
- "leak-guard covers only clean close" — `ConnGuard`'s decrement is in `Drop`, so it fires
  on every exit path (error, abrupt drop, panic, cancellation); verified correct.
- "wrong-pin test asserts only `is_err()`" — the reviewer showed the suggested fix is
  actually wrong (the error surfaces as `TransportError::Io`, not `Tls`), and the test
  already fails for the right reason (pin mismatch at TLS).

## Independence statement

Reviewed by fresh-context agents that did not author the code, over the listed files,
using the crate's own test/lint tooling. Findings were adversarially verified
(default-to-not-real) before being reported; the 4 confirmed defects were fixed and
re-verified, and the 3 unverifiable (agent-errored) findings were assessed by hand.
