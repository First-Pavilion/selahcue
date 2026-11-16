# Hosted native runner — source evidence

Task 2 adds the fixed five-command runner and separately authenticated Rust setup metadata at `scripts/fixtures/macos-native-toolchain.json`. Base: `3343550935691b4194c5f8d23811b28f92fbff69`, branch `codex/hosted-native-proof-20261115`. This is source and inert-test evidence. No native build, native adapter execution, dependency/toolchain installation, archive download, hosted dispatch, provider access or application acceptance occurred.

The accepted amendment and root's additive metadata/state/archive rulings remain authoritative. The sealed Task 1 comparator, four-member fixture root, 29 payloads, seven provenance records, all constructors and historical oracles are unchanged. The deferred UTF-16/32 stdout decoder finding remains for whole-branch review.

## Runner boundary

`admit`, `setup`, `prove`, `finalize`, and `cleanup` expose no configurable source roots, binary, provider, input expectations or toolchain. Normal stages require a verified predecessor bound to the same manual/main hosted run, attempt 1, checkout head, runner/comparator/input identities, workflow/action identities and toolchain metadata. Fixed checkout-relative state/export paths are `.macos-native-proof-state` and `.macos-native-proof-receipts`.

Admission checks Darwin arm64, Python 3.11+, the image identity, OS/Xcode/clang/SDK, normative commit reachability, clean proof-source paths, exclusive destinations, actual APFS clone behavior, at least 8 GiB free disk and 6 GiB physical memory, normal pressure and three paging samples five seconds apart. Setup creates only recorded owned namespaces, checks out detached normative source, stages the allowlist, verifies 102 source hashes and both locks, installs only the three pinned official components, and fetches the locked public crates in a scrubbed job-local HOME/CARGO_HOME. It compares all 56 owner-subset registry tuples, verifies archives against lock hashes, independently derives archive-member hashes and the complete directory inventory, and compares the fetched tree while requiring Cargo’s exact generated `.cargo-ok` marker, then seeds only cache/index/src. Setup shares a 300-second deadline.

The frozen builder stays byte-for-byte unchanged and is invoked once with no builder flags. Its existing `--frozen --jobs 2` remains intact. Network denial is mandatory, with a loopback connect probe that requires EPERM/EACCES rather than accepting a refused or successful connection. The runner invokes `--verify` after compilation and after the eleven sequential comparator batches. Build and proof ceilings are 600 and 120 seconds, with 30 seconds per batch and room reserved for finalization. The stream pump limits directly captured stdout/stderr, kills and reaps only its new process group, and aborts after two consecutive five-second paging increases. It does not bound the frozen builder's internally buffered Cargo output or prevent every instantaneous OOM.

Receipts distinguish build execution, build completion and native adapter execution; successful fake runs remain `native_executed=false`. Raw builder `build.json` and `feature-tree.txt` are preserved. Finalization exports exactly eight receipt members plus `artifact-manifest.json`, with a 20 MiB total ceiling. Missing raw outputs on early failure remain missing/error evidence. Cleanup validates recorded run-bound ownership and no-follow identities, preserves foreign/replaced/symlink paths, and retains state/export through either failed or successful upload until VM disposal.

## Official setup pins

Release manifest: [Rust 1.98.0 manifest](https://static.rust-lang.org/dist/channel-rust-1.98.0.toml), 898,637 bytes, SHA-256 `3f7d139b73bbbd0004ef6e58b430831c68cdad2b1f64ee2eb35d54c09199489a`. Its [checksum record](https://static.rust-lang.org/dist/channel-rust-1.98.0.toml.sha256) agrees, and the [dated official manifest](https://static.rust-lang.org/dist/2026-08-20/channel-rust-1.98.0.toml) has identical bytes.

| Component archive | Official HEAD length | Manifest SHA-256, independently matched to its `.sha256` record |
| --- | ---: | --- |
| [rustc](https://static.rust-lang.org/dist/2026-08-20/rustc-1.98.0-aarch64-apple-darwin.tar.xz) | 49,401,680 | `287edbc2e285b9c23ef7b085413b90cb8539909eda9c4b49f2a55ec0b52819d4` |
| [cargo](https://static.rust-lang.org/dist/2026-08-20/cargo-1.98.0-aarch64-apple-darwin.tar.xz) | 8,894,708 | `2c2a8bbf3cba4353c0ca2cf1ba8280603f3ca82ceebb538fee4a1a987147f743` |
| [rust-std](https://static.rust-lang.org/dist/2026-08-20/rust-std-1.98.0-aarch64-apple-darwin.tar.xz) | 29,740,736 | `48c05269ed36fb5f0a8438065156891fe59fcb868d90cfed9b7209540d54b2ce` |

Only manifest/checksum text and archive HEAD metadata were retrieved. No archive bytes were downloaded, hashed locally, unpacked or installed. The exact 1,063-byte metadata file has SHA-256 `91eed188e1eb54de8138868f9c6c72082d4af31d9a0bb1b66706adbf6bb6f7b7`; the runner enforces both this raw identity and a closed schema.

The archive extractor deliberately accepts only regular files/directories. Root's official Rust distribution-source check supports that policy for these components; this is source-based inference, not archive-member observation. Unexpected links/special entries must fail hosted setup before installation/build. No alternate toolchain or automatic retry is authorized.

## Verification

The existing Python 3.14.5 at `/opt/homebrew/bin/python3.14` ran:

- `-B -m unittest scripts.test_macos_native_proof -v`: 59 tests passed, including the unchanged 20 Task 1 tests and 39 orchestration tests.
- `-B scripts/macos_native_fixtures.py --prepare-check`: exit 0; eleven frozen batches, 1,111 frames, 1,116,226 bytes, 47 pure rejections.
- `-B scripts/macos_native_fixtures.py --self-test`: 59 passed, exit 0.
- Standard-library `compile(...)` over the runner/tests only: exit 0; no frozen builder import/execution.
- Working and staged whitespace/diff checks: exit 0.

RED/GREEN work covered absent orchestration, exclusive path/symlink refusal, resource/paging gates, environment scrubbing, unavailable denial enforcement, wrong tool versions/targets, metadata feature/tuple drift, locked-fetch drift, absent cache, immutable predecessor receipts, one build only, native framing/overflow/timeout failures, missing dep-info/generated outputs, stale binary receipts, interrupted finalization, exact artifact closure/size and cleanup after early/setup/proof/upload failures. Direct stream/timeout controls use only small inert Python subprocesses. Stage tests inject an explicit inert host; they do not invoke Cargo, native application code or real network/SDK services.

The first helper RED produced ten expected absence failures; eight stage REDs followed. Later controls exposed and fixed independent archive-versus-extraction checking, unrecorded cleanup authority, explicit network-probe exit validation, failed-command receipts, installed-tool checks, complete run/resource receipts and actual native-execution flags. Earlier failures remain in the task report; they were not relabeled as passes.

Full commands, outputs, exit codes and custody evidence are under `.superpowers/sdd/2026-11-15-hosted-native-proof-plan/task-2-*`. The twelve root-owned untracked documents and all prior Task 1/website inputs remained unchanged. Root's two progress-ledger appends and new Task 3 brief are attributed to root. Broad `make ci` and native/runtime gates were intentionally not run under the explicit local paging hold. Source review, Task 3 workflow/action pins and validators, reviewed main integration, actual hosted admission/setup/build/proof/upload and durable root verification remain separate gates.


## Task 2 fix round 1

Independent Cody review found that the original registry happy-path fixture incorrectly supplied a vendoring `.cargo-checksum.json` that pinned Cargo fetch does not produce (C2-1). The verifier now derives its complete expected file/hash and explicit/implicit directory inventory directly from the same archive bytes authenticated against the lock. Fetched files and directories must match; the sole generated exception is the exact fresh Cargo797e8a9bc seven-byte `.cargo-ok` content `{"v":1}`. Missing/altered/extra/special entries and archive-supplied markers are rejected. No supplemental checksum manifest is generated or trusted. Root supplied an offline copy of the pinned official Cargo registry source to establish this producer format; no Cargo or network fetch ran during the fix.

Cody also found that `SystemHost.command` raised before completed nonzero results reached receipt recording (C2-2). A structured failure now carries the completed bounded result so the outer recorder saves its actual exit code and stdout/stderr identities before retaining failed status. A regression through the real `SystemHost.command` with injected returned results verifies exit37 and signal-style exit-9; timeout and overflow retain distinct failure reasons without fabricated completed exits. Raw diagnostics remain excluded.

Both findings were reproduced RED before the fixes. The focused registry group passes six tests and the completed-result group passes two. The corrected shared suite passes65 tests; existing prepare-check, self-test and source compilation pass. These remain source/inert tests only. The original59-test result is historical evidence that missed these integration defects, not proof of successful Cargo setup. Full fix-round commands, outputs, protected custody and final commit are appended to the Task2 report. Root owns scoped Cody/Shadow re-review; hosted readiness remains unverified.


## Task 3 — exact workflow and policy exception, 2026-11-16

Source-only integration from Task2 head `73f80a1e060a94403068903dcc1c9ba817d12490`. The exact `.github/workflows/macos-native-proof.yml` now has one manual/main-only `native-proof` job on `macos-26`, timeout20, read-only contents permission and non-cancelling `macos-native-proof` concurrency. The first bash step refuses attempts other than1. Checkout uses dispatch SHA, full history and no persisted credentials. Fixed prepare/admit/setup/prove steps retain default success gating; always-finalize, always-upload and always-cleanup follow in order, with no continue-on-error. The cleanup command is exactly `python3 scripts/macos_native_proof.py cleanup`.

The existing policy tools share a closed, type-sensitive schema through `native_proof_workflow_violations` and `native_proof_violations`. No macOS exemption is granted before the complete schema passes. The exact file is validated even when its runner/job is removed; unknown macOS workflows remain rejected. The schema rejects unknown workflow/job/step/action-input keys, action/ref/command/order changes, widened permissions/triggers and runner expressions/matrices. Both self-tests exercise 158 native-policy cases (2 positive on/True controls and 156 negatives), retaining existing Windows/tier/alarm/installer/cache checks. Existing Linux lint now invokes the finite standard-library runner tests, with no new dependency or job.

Official checkout pin: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`; upload pin: `actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9`. Root's official API receipt at06:33:03UTC was reused without worker network access; local retained commit/ref objects and metadata size/SHA256 were independently compared. Both actions use Node24. Upload explicitly names exactly the nine approved `.macos-native-proof-receipts/` files, uses `include-hidden-files:true`, `if-no-files-found:error`, `overwrite:false` and retention7days. The unchanged runner validates the20MiB aggregate before export. No source/cache/frame/binary glob is added.

RED self-tests both exited1 before implementation. The minute checker rejected both valid controls and missed five missing/dynamic/replaced-runner/job mutations. The workflow checker accepted 153 invalid shapes, demonstrating the absent policy. After implementation, both self-tests and real scans exited0: eight workflows/22jobs. The focused runner suite passed65tests in3.605s; `/opt/homebrew/bin/actionlint -color`1.7.12 exited0 with no output. Checks used existing Python3.14.5 and PyYAML6.0.3 via scoped PYTHONPATH, with no install. Full raw outputs, exact argv/cwd/exits/durations and stream hashes are under the native SDD directory as `task-3-red-*` and `task-3-green-*`; action source verification is `task-3-action-pin-verification.json`.

This does not establish hosted Linux validation, macOS admission/setup/build/network denial, actual native comparisons, artifact upload or native acceptance. Root still owns source review, push/merge, final-source hosted Linux observation and the single initial main/manual dispatch after live identity/quota checks. A blocked CI run remains unexecuted evidence. Local compilation hold, Q absence, historical binary/build uncertainties, bridge extraction gates and Tauri/WKWebView/GPU/installer/installed-app acceptance gaps remain unchanged. No runner, sealed fixture, toolchain metadata or protected root document was changed by Task3.
