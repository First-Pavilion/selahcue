# Code Review — batch 7r: CI + test infrastructure (per-OS matrix, NFR evidence)

**Method:** Independent multi-lens adversarial review (3 lenses × find → adversarially
verify, 8 agents, workflow `wdbqc81qc`) + a dedicated GitLab-runner verifier (stopped as
moot once the user chose GitHub). No self-approval.
**Date:** 2026-07-24
**Scope:** `.github/workflows/ci.yml`, the `make ci` local gate, `scripts/measure_nfr.sh`
(+ the one-time `cargo fmt` normalization of both Rust workspaces).

## Verdict: PASS after remediation (5 raised → 4 confirmed → all fixed; 1 dismissed)

## What was verified for real (not just authored)
- **`make ci` ran end-to-end here — ALL GREEN**: fmt gates, clippy `-D warnings`
  (workspace + lan/app server features + operator), the full test suite (198), the LAN/app
  E2E over real TLS, the SQLCipher encryption tests, the operator check, and Flutter
  analyze + test. This is the exact gate the CI file enforces.
- **NFR evidence measured on the release build** (Darwin arm64, hardened harness):
  cold start (to control-server-ready) **1.13 s** vs 3 s budget — PASS; idle memory
  (max RSS, both windows composited) **121.5 MB** vs 300 MB — PASS.
- Both Rust workspaces normalized with `cargo fmt` (one-time mechanical churn); tests +
  clippy re-verified green afterwards, so the fmt gate starts enforceable.
- The GPU-parity tests were confirmed to **skip gracefully** without an adapter, so the
  CI matrix cannot false-fail on adapterless runners; ubuntu installs Mesa lavapipe so
  parity actually executes there.

## Confirmed & fixed

1. **(medium ×2 lenses) The NFR harness could fabricate a PASS.** If the app wrote its
   endpoint (cold-start PASS) then crashed, every `ps` sample came back empty, the guard
   silently skipped them, and `0.0MB PASS` with exit 0 was reported — false evidence from
   the very script whose job is evidence (one verifier reproduced the mechanism live).
   **Fix:** per-sample `kill -0` liveness check (die → FAIL + the app's last log lines,
   now captured instead of discarded), and zero-samples → FAIL.
2. **(low) `cancel-in-progress` applied to main pushes**, so a superseded main commit
   kept a permanent "cancelled" status — bad for revert/bisect/audit trails. **Fix:**
   cancel only PR runs (`github.event_name == 'pull_request'`); group de-doubled.
3. **(low) The NFR kill bypassed the app's own endpoint cleanup**, leaving a stale
   endpoint file after every measurement. **Fix:** the harness removes it on all exits.

Dismissed (1): "audit job installs no toolchain" — runner images preinstall cargo; the
install-action only adds cargo-audit. Verified not a failure.

## Hosting decision (user, 2026-07-24)
**GitHub.** Recorded rationale: the free tier runs the full Linux/macOS/Windows matrix
this project's acceptance requires (GitLab Free has no macOS runners; Windows is
bare-beta). A complete `.gitlab-ci.yml` variant was authored, adversarially scoped to
Free-tier reality, and removed after the decision — it lives in git history.

## Honest scope
The workflow is **authored + structurally validated + local-parity-verified** (`make ci`
green); it has **not executed on hosted runners** — the repo has no remote yet, and no
GitHub credentials exist in this environment. Activation is a one-time user action
(create the private repo + push), after which every push runs the matrix. The NFR
figures are from one macOS/arm64 machine; per-OS CI figures come once CI is live.

## Independence statement
Reviewed by fresh-context agents that did not author the files; findings adversarially
verified (one empirically reproduced); all confirmed defects fixed and the hardened
harness re-run green (1.13 s / 121.5 MB PASS).
