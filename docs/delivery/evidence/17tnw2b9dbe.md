# chacha20 lock patch — 17tnw2b9dbe

Task: https://app.clickup.com/t/17tnw2b9dbe. Kenji, isolated branch `codex/17tnw2b9dbe-chacha20-lock`, base `8a66f0ba168e422ef1f60a7b3c8418ae8bb1f2f7`. The separate reviewed hygiene branch is untouched.

## Upstream and exact scope

Fresh official sparse registry metadata from https://index.crates.io/ch/ac/chacha20 confirms:

| Version | Yanked | Published | MSRV | Checksum |
|---|---|---|---|---|
|0.10.1|yes|2026-06-24T13:32:44Z|1.85|d524456ba66e72eb8b115ff89e01e497f8e6d11d78b70b1aa13c0fbd97540a81|
|0.10.2|no|2026-08-27T17:51:13Z|1.85|65c35e4b699c7e15ccbe7ee35c005e4fc0a278d22238a2857e6ce2dadeda1b06|

The crates.io JSON API returned HTTP403, so the official Cargo sparse index was used instead. The installed rand0.10.2 manifest requires chacha20 `0.10.0` (Cargo caret semantics), feature `rng`, default-features false. Both real reverse trees are `rand0.10.2 <- tungstenite0.30 <- tokio-tungstenite0.30 <- selahcue-lan`; the workspace reaches selahcue-app and selahcue-desktop, the operator root reaches selahcue-app and selahcue-operator (including its direct test dependency).
The downloaded0.10.2 upstream changelog identifies a fix for an SSE4.1 intrinsic in the SSE2 backend of RNG/legacy variants (RustCrypto/stream-ciphers#580). This local Apple ARM verification establishes consumer compatibility, not execution of that x86 backend; hosted Linux verification remains a separate gate.

Executed separately in both roots: `cargo update -p chacha20 --precise 0.10.2` with the appropriate manifest path. Both commands exited0. Parsed original and current Cargo.lock with Python3.14 `tomllib`: only each chacha20 package's version and checksum differ. Its other fields/dependencies and every other package object are identical. No manifest, Rust/Dart source, STT lock or dependency-wide update is included. Both `cargo metadata --locked --format-version 1` commands completed exit0 and resolve exactly one chacha20 package, version0.10.2.

## Audit before/after

Baseline actual `cargo audit --json --file <lock>` completed exit0 in both roots, reproducing the allowed yanked warning for chacha20. Head audits also completed exit0. Complete warning-object comparison, after removing only baseline chacha20's yanked warning, is equal in both roots. Both baseline/head vulnerability counts are0.

| Root | Unchanged remaining allowed warnings |
|---|---|
| Desktop workspace | ttf-parser0.25.1 unmaintained, RUSTSEC-2026-0192 |
| Operator | proc-macro-error1.0.4 unmaintained RUSTSEC-2024-0370; ttf-parser0.25.1 unmaintained RUSTSEC-2026-0192; glib0.18.5 unsound RUSTSEC-2024-0429 |

Required `make audit` completed exit0. Its actual output reports PASS for desktop, operator and unchanged selahcue-stt, followed by `OK: every Cargo root passed cargo audit`. Allowed warnings remain visible; this patch does not claim they were fixed. Advisory database snapshot in baseline/head:1403 advisories, commit `965bf9ad083b58e6340d65829d85217b18be9290`, last-updated2026-11-03T21:34:28+01:00.

Local raw receipts under `/private/tmp/17tnw2b9dbe-`: `registry-index.jsonl`, `baseline-{workspace,operator}-audit.json`, `head-{workspace,operator}-audit.json`, `make-audit.log`, `metadata-{workspace,operator}.json`, `rand-{workspace,operator}.txt`. Local paths are not published report links.

## Compatibility verification

Environment: macOS Apple ARM, pinned Rust1.98.0, existing locked dependencies and local Cargo target cache. All commands below completed exit0; no required local verifier remains active. No new tests mirror the lockfile text; registry/audit/parsed lock checks and actual transport/host suites verify the change.

| Command | Result |
|---|---|
| `cargo test --locked -p selahcue-lan --features server -p selahcue-app -p selahcue-desktop` |734 passed,11 ignored,0 failed across44 test/doc binaries |
| `cargo test --locked --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` |455 passed,1 ignored,0 failed |
| `cargo clippy --locked -p selahcue-lan --features server -p selahcue-app -p selahcue-desktop --all-targets -- -D warnings` |exit0 |
| `cargo clippy --locked --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --all-targets -- -D warnings` |exit0 |
| `cargo fmt --all --check --manifest-path implementation/desktop/Cargo.toml` |exit0 |
| `cargo fmt --check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` |exit0 |
| `git diff --check` |exit0 |

Workspace ignored cases comprise10 existing child-process entrypoints and one existing fresh-process translation warmup measurement probe. Operator's one ignored case is its child-process XDG descriptor entrypoint. Parent tests invoke their child helpers; no numerical performance measurement is claimed. The local clippy log contains macOS `MallocStackLogging: can't turn off ... because it was not enabled` notices; they are process-environment messages, not Rust lint failures, and both clippy commands completed0. `make stage-operator-binaries` created only missing ignored compile-check placeholders; it did not download an SDK or package an installer.

Full receipts: `/private/tmp/17tnw2b9dbe-tests-{workspace,operator}.log`, `/private/tmp/17tnw2b9dbe-clippy-{workspace,operator}.log`. The separate hygiene changes are not part of these test counts or this source payload.

## Gates and limits

Root owns four independent reviews, publication under the user's wave instruction, exact-head hosted CI, merge/main verification and QA transition. No installer workflow dispatch, packaging, deployment, secrets/provider operation or live production test occurred. No public publication has been attempted or rejected for this lock payload. This distinct local payload is prepared for all four reviews, then root-owned publication.
