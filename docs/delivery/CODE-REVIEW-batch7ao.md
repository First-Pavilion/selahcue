# Code Review — Batch 7ao (Android MulticastLock for mDNS discovery)

- **Scope:** story `86ajp0b0t` recorded remainder — acquire a `WifiManager.MulticastLock` while the pure-Dart `multicast_dns` browse runs, so Nearby-hosts discovery actually receives multicast on Android (the OS filters it otherwise). Executed via the `/goal` engine against `docs/delivery/goals/TASK-86ajp0b0t-android-multicastlock.md` (5 mandatory criteria, all PASS).
- **What shipped:** a Dart `MulticastLock` abstraction + best-effort `PlatformMulticastLock` (`selahcue/multicast` channel, Android-only); `DiscoveryController.refresh()` holds the lock across the browse and always releases it; a Kotlin `MainActivity` channel handler (non-ref-counted lock, `isHeld`-guarded, released on destroy); 3 lock-lifecycle unit tests; and a `flutter build apk --debug` CI step that compile-verifies the Kotlin.
- **Method:** independent adversarial review via the Workflow tool (run `wf_96cabb67-4a5`, 2 lenses — lock-lifecycle, android-native — each finding verified to refute). No self-approval.
- **Raised → confirmed → fixed:** **3 → 1 → fixed** · 2 refuted.

## Findings and dispositions

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | med | **`refresh()` had no `catch`** — a throwing browse would propagate out, skipping the `_searching=false` reset, so `_searching` stayed true forever: every future `refresh()` silently no-ops and the loading spinner never clears (permanent discovery lockout). Masked in production only because `_mdnsBrowse` swallows internally — but that invariant was undefended (`MDnsClient()` before the try, `client.stop()` in a finally can throw) | `refresh()` now **catches** browse errors (best-effort — never throws; `_searching` and the UI always recover). The lock was already released on every path (finally). The test rewritten to assert no-throw + `searching` reset + a subsequent refresh still runs |

## Refuted (correctly)

- "acquire()/release() sit outside the try; `PlatformMulticastLock` depends on `dart:io Platform`" — self-conceded low/hardening, not a live defect on the current targets.
- "acquire() sits outside the try/finally (latent stuck-state)" — a variant of A about `acquire()` specifically; doesn't reproduce from the shipped code (`acquire()` is best-effort and, in production, never throws).

## Verification after remediation

- `flutter analyze` clean; **39 tests** (3 lock-lifecycle: acquire→browse→release ordering, best-effort no-wedge on browse error, no double-acquire on a concurrent refresh).
- CI: the flutter job runs `flutter analyze` + `flutter test` + **`flutter build apk --debug`** (JDK 17) — the Kotlin `MulticastLock` channel **compiles** on the runner.

## Design notes

- **Best-effort throughout:** a lock hiccup (no channel on an older build, a platform error) is swallowed — discovery just may find nothing; the QR / manual-paste paths are unaffected.
- **No leak:** the lock is released in `refresh()`'s `finally` and on Activity `onDestroy`; non-ref-counted + `isHeld` guards avoid the `MulticastLock under-locked` runtime exception.
- **Testability:** the mDNS browse is extracted behind an injectable seam so the lock lifecycle is unit-tested hermetically (no real sockets).

## Residual / owner QA

- **On-device discovery** — that a real Android phone, holding the lock, actually finds a running host over mDNS — is **owner QA** (not automatable in CI; the runtime multicast behaviour needs a device on a real Wi-Fi). QA steps posted on `86ajp0b0t`.
