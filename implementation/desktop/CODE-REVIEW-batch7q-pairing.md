# Code Review — batch 7q: mobile pairing (QR + host confirmation) + Flutter client

**Method:** Independent multi-lens adversarial review (5 lenses × find → adversarially
verify, 26 agents, workflow `wvg07j8r0`) + a post-remediation adversarial verification
pass (`w9g29ap5m`). No self-approval. The review ran against the final MVC-structured
mobile app (an earlier run was stopped and relaunched after the user's MVC refine).
**Date:** 2026-07-24
**Scope:** the wire pairing flow (`selahcue-lan`: protocol v2 `Hello`, `complete_pairing`,
approval seam, credential generation, `PairingInvite`), the QR composition
(`selahcue-present/qr.rs`) + controller overlay, the desktop P/Y/N pairing UX + LAN
binding, the CLI `pair`, and the Flutter controller (`implementation/mobile/`, MVC).

## Verdict: PASS after remediation (21 raised → 11 unique defects → all addressed)

The 5 lenses raised **21 findings, all confirmed** by adversarial verifiers — with heavy
cross-lens duplication: three lenses independently found the worst defect, and three the
socket-leak cluster. Deduplicated: **11 unique defects — every one fixed** (none
deferred). Re-verified after fixes: Rust workspace **198** (lan server **50**, incl. 6
pairing E2E + the new `withdraw` regression); clippy clean; `flutter analyze` clean;
**12** Dart tests; `flutter build macos` succeeds.

## Unique defects → fixes

1. **(high ×3 lenses) Approval-slot wedge.** An unanswered pairing prompt (server's 30s
   timeout) left the one-at-a-time `PendingApproval` slot occupied forever — every later
   pairing was silently auto-denied, and pressing Y against the dead prompt printed
   "ALLOWED", granted nothing, and dismissed the QR.
   **Fix:** the approval closure reclaims a slot whose oneshot sender `is_closed()`
   (receiver dropped by the timeout); `resolve_approval` treats a failed send as
   "already expired — nothing granted" (no QR clear, no code forget).
2. **(medium ×3) Cancelled code stayed redeemable.** P-off cleared the QR but the code
   lived on to its 2-minute TTL — exactly when the operator cancels because the QR was
   photographed. **Fix:** `SessionRegistry::withdraw` + the desktop tracks the active
   code and withdraws it on cancel (regression-tested).
3. **(medium ×3, no-leak rule) Dart reconnect abandoned the old session.** Dead
   WebSockets accumulated on phone + host (toward the 128-connection cap).
   **Fix:** `_reconnect` closes the old session (best-effort) before retrying.
4. **(high) Dart handshake failures leaked the socket.** A timeout/reject/malformed
   reply in `pair()`/`connect()` returned without closing. **Fix:** try/catch →
   `ws.close()` + rethrow on every failure path.
5. **(medium) Unbounded poll backlog.** The 1 s poll enqueued regardless of RTT.
   **Fix:** an in-flight guard (`_refreshing`, cleared in `finally`).
6. **(low ×3) No reply correlation.** A timed-out command's late `Ack`/`Denied` could be
   attributed to the next command. **Fix:** `command()` discards correlated replies
   older than the current id; the StreamQueue doc rewritten to state the lockstep
   contract honestly (residual: uncorrelated frames rely on lockstep + the poll guard).
7. **(low ×2, no-leak rule) `prune_expired` had no callers.** Expired offers accumulated
   per P-press. **Fix:** pruned on every offer (desktop) and every pairing pre-check
   (server).
8. **(medium) Loopback fallback QR.** With no LAN-facing interface, the invite silently
   used 127.0.0.1. **Fix:** an explicit warning that only same-machine clients can pair.
9. **(medium) Undisclosed Producer grant.** The prompt never said what approval grants.
   **Fix:** the prompt states it grants **PRODUCER control (go-live/blackout/timers)**;
   READMEs updated.
10. **(medium) Asymmetric cross-language pinning.** Dart pinned every command it sends;
    Rust pinned only a subset. **Fix:** `test_protocol.rs` now pins all of them
    (byte-identical to the Dart fixtures).
11. **(low ×2) Doc drift.** Stale fixture paths (3 places) + a desktop README still
    claiming the mobile client "is a subsequent batch" with 7k-era test counts.
    **Fix:** all corrected.

## What the review found sound (no findings)
Pinned-TLS trust on both sides (Rust verifier; Dart `withTrustedRoots:false` +
`badCertificateCallback` pin check), the pre-check ordering (bad codes never prompt the
operator), single-use/TTL enforcement, server-side RBAC on paired connections,
credential entropy + fail-closed RNG paths, QR composition, and the MVC separation.

## Honest scope
Pairing, decline, replay, expiry, disabled-by-default, and issued-credential reconnect
are **E2E-verified over real TLS** (Rust). The wire contract is **byte-pinned in both
languages**. The Flutter app is verified by `flutter analyze` + unit tests + a
successful **macOS build**; **it has not been run on a physical phone against the host
here** — that is the user's on-device QA (`make output` + `make mobile`). mDNS discovery
is deferred (the QR carries the address). Pairing grants Producer (disclosed); role
choice at offer time is a follow-up.

## Independence statement
Reviewed by 26 fresh-context agents that did not author the code; every finding was
adversarially verified (default `real=false` — all 21 survived, a sharp review). All 11
unique defects were fixed and the fixes adversarially re-verified in a second pass.
