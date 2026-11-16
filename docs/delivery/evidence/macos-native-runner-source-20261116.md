# Hosted native runner — source evidence

Task 2 adds the fixed five-command runner and separately authenticated Rust setup metadata at `scripts/fixtures/macos-native-toolchain.json`. Base: `3343550935691b4194c5f8d23811b28f92fbff69`, branch `codex/hosted-native-proof-20261115`. This is source and inert-test evidence. No native build, native adapter execution, dependency/toolchain installation, archive download, hosted dispatch, provider access or application acceptance occurred.

The accepted amendment and root's additive metadata/state/archive rulings remain authoritative. The sealed Task 1 comparator, four-member fixture root, 29 payloads, seven provenance records, all constructors and historical oracles are unchanged. The deferred UTF-16/32 stdout decoder finding remains for whole-branch review.

## Runner boundary

`admit`, `setup`, `prove`, `finalize`, and `cleanup` expose no configurable source roots, binary, provider, input expectations or toolchain. Normal stages require a verified predecessor bound to the same manual/main hosted run, attempt 1, checkout head, runner/comparator/input identities, workflow/action identities and toolchain metadata. Fixed checkout-relative state/export paths are `.macos-native-proof-state` and `.macos-native-proof-receipts`.

Admission checks Darwin arm64, Python 3.11+, the image identity, OS/Xcode/clang/SDK, normative commit reachability, clean proof-source paths, exclusive destinations, actual APFS clone behavior, at least 8 GiB free disk and 6 GiB physical memory, normal pressure and three paging samples five seconds apart. Setup creates only recorded owned namespaces, checks out detached normative source, stages the allowlist, verifies 102 source hashes and both locks, installs only the three pinned official components, and fetches the locked public crates in a scrubbed job-local HOME/CARGO_HOME. It compares all 56 owner-subset registry tuples, verifies archives against lock hashes, independently derives archive-member hashes and compares extracted files, then seeds only cache/index/src. Setup shares a 300-second deadline.

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
