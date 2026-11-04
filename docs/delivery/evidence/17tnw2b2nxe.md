# WAL contention regression evidence — 17tnw2b2nxe

Task: https://app.clickup.com/t/17tnw2b2nxe. Goal: ../goals/TASK-17tnw2b2nxe.md. Base:6b096771d3d65c1dacf105523a4ee48edc2d4f93. Root owns four independent reviews, actual final-head CI, merge/main verification and QA. The coordinator read this existing ticket live; its actual acceptance requires mechanism assertions and 20 consecutive Windows/macOS passes. That supersedes the preliminary proposal to retain the 500 ms timing gate. ClickUp start/status write initially failed; root explicitly authorized work while repairing UI. No claim it was saved.

## What changed

Production behavior, APIs, dependencies and Cargo.lock are unchanged. A private cfg(test) module directly exercises the existing checkpoint helper with real SQLite/SQLCipher. A reader pins a real WAL snapshot; an unguarded checkpoint must report busy and invoke a thread-local counting handler. The helper must not invoke that handler, proving it disables busy waiting rather than merely returning on a fast host. A second test checks timeout restoration (137ms) and actual zero-length WAL after the reader releases, so a no-op helper cannot pass. Callback state belongs to the calling test thread and is reset around the positive control.

The public transcript regression retains the independent writer thread, original 5 ms overlap pacing, deletion, append_detection/append_segment success and eventual WAL-truncate positive control. Three elapsed-time assertions become one content-free timing diagnostic. Pacing cannot guarantee overlap; the direct helper test provides deterministic mechanism evidence. One timing-policy note in implementation/desktop/CLAUDE.md explains the distinction.

## Diagnosis and causal controls

PR359be13c756 and main6b096 have identical data/test/desktop-lock sources. Its Ubuntu run41767835782 failed whole-delete585.184714ms versus500ms. The ticket records a historical Windows556ms failure. Exact hosted slow phases remain UNKNOWN. The busy=1 checkpoint warning also occurs when the fixed helper succeeds and does not prove a wait.

Before implementation, local original37-test transcript suite passed. An isolated ordinary-writer-lock control took659ms in its transaction and3.139ms in its checkpoint, reproducing the same elapsed assertion. Removing the actual zero-timeout boundary took5.142s in the checkpoint. This demonstrated ambiguous attribution; it did not establish the cause of either hosted failure. Raw diagnosis: /private/tmp/pr359-wal-diagnosis-handoff.md and its logs.

## Local verification (actual macOS, pinned Rust 1.98.0)

- New mechanism target:2 tests pass. Initial wrong-relative-path append wrote nothing and produced an empty-filter run; excluded from evidence. Corrected command ran both tests.
- Actual old-zero-timeout-removal mutation: plaintext lib target fails count1 versus0; restored source.
- Final-source SQLCipher mutation, cargo test --locked -p selahcue-data --features encryption --no-fail-fast -- --nocapture: exit101. Mechanism test fails count1 versus0 (0.20s); retained public concurrent writer test independently fails append_detection with DatabaseBusy (5.52s), with data siblings running. Production file restored byte-for-byte. /private/tmp/17tnw2b2nxe-encrypted-old-mutant.log.
- Actual 20 consecutive local iterations, each running the2 mechanism tests and exact public regression with encryption:40 target invocations, all required tests really executed and passed, no retry or best-of selection. /private/tmp/17tnw2b2nxe-macos20.log and .json.
- Final full encrypted data suite: 187 tests pass across 16 nonempty targets; no test failures. cargo fmt --all --check and cargo clippy --locked -p selahcue-data --all-targets --features encryption -- -D warnings exit0. /private/tmp/17tnw2b2nxe-final-rust.json and individual logs.
- Restored normal workflow self-tests/normal checks, minute self-tests/normal checks, actionlint, git diff --check, Goal structural validation and pinned-toolchain verification all exit0. /private/tmp/17tnw2b2nxe-final-controls.json.

## Actual Windows proof

A temporary branch-only replacement of the existing registered ci workflow was explicitly authorized for the ticket's throwaway Windows proof. Manual branch-ref dispatch only; one Windows data-only job, 15-minute timeout, read-only contents, no persisted checkout credentials, no caches/secrets/installer/deployment operations. Uses the pinned compiler and existing NASM/Perl recipe. Tests enable encryption to match normal workspace SQLCipher feature unification. Each of 20 iterations aborts on either target failure; no retries.

First setup run https://github.com/First-Pavilion/selahcue/actions/runs/41827583650 at d9a500277077ac27908deb3494a607b6a986ff54 FAILED before tests. Git Bash selected incomplete MSYS Perl although pwsh verified Strawberry Perl; OpenSSL Configure could not load Locale/Maketext/Simple.pm. This is a failed setup run with zero completed iterations, not a passing proof. Verified openssl-src supports OPENSSL_SRC_PERL; the proof-only correction persists the verified Windows Perl's absolute path and verifies required modules. No Rust change.

Corrected run https://github.com/First-Pavilion/selahcue/actions/runs/41828208557 at cb583e073711e7851c9a4e3b93f68364167c1e25 PASSED. Independently parsed its completed log: actual START/PASS iterations exactly 1 through 20; one actual COMPLETE marker; 20 named busy-handler tests, 20 timeout-restoration tests and 20 named public regressions passed (40 target invocations). The initial log parser also counted the echoed shell-script completion literal and rejected two markers; anchoring to timestamped output distinguished the single actual marker. No tests rerun. Raw Windows log and count receipt: /private/tmp/17tnw2b2nxe-windows20.log and .json.

The normal ci.yml is restored byte-for-byte from main6b096 before final review. Both final Rust file blobs match the corrected proof head exactly; /private/tmp/17tnw2b2nxe-proof-source-identity.json. Temporary proof revisions remain visible in branch history for audit; no new hosted jobs or permissions remain in final diff. Final normal PR CI and all four independent reviews are still required.

## Limits

No performance guarantee is inferred from20 correctness runs. Local macOS evidence is not Windows or hosted Ubuntu evidence. No actual installer/build release or deployment occurred. PR359 remains frozen until this prerequisite merges and root refreshes it; canary17tnw2b1f2f remains started but queued behind this CI unblock. Four reviews, final-head CI, main verification and QA remain pending.
