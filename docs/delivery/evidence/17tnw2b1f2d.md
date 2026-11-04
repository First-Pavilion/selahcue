# NDI sidecar link-free check/lint gate

Ticket: https://app.clickup.com/t/17tnw2b1f2d

## Approved approach

Root approved the existing Linux Rust job after inspection found the tested minute invariant forbids always-on literal Windows runners (ticket comment 1400430000278273). This meets the ticket's at-least-one-OS criterion without weakening runner policy. The committed `vendor/ndi/windows/include` headers are documented as identical across platforms and contain Linux/macOS declarations. They are copied unchanged; no header stub is generated.

`grafton-ndi` 2.0.0's `build.rs` calls real bindgen on these headers and `select_library` requires an existing platform library path even for Cargo check. The helper creates an empty library-selection placeholder in a private temporary directory, exposes its path only in child command environments, and removes the entire directory after success/failure. Linux gets `lib/x86_64-linux-gnu/libndi.so`; local macOS gets `lib/macOS/libndi.dylib`. This is not a runtime or usable link library. The helper accepts only fixed `cargo check` and `cargo clippy` commands, never build/test/run/package commands. No SDK/runtime download, application link, installer dispatch, package or artifact upload is performed.

The existing Linux Rust job installs libclang-dev alongside its existing platform build dependencies, then invokes the helper after default Clippy under `!cancelled()` so an earlier gate failure does not silently skip NDI. Existing desktop/scripts/vendor/workflow path filters cover it; existing Rust alarm dependency covers its failure. Runner matrices, minute rules, permissions and installer workflow are unchanged.

## Actual local verification

Environment: macOS Apple Silicon, pinned Rust 1.98.0. Dedicated NDI source worktree, existing primary Cargo target cache reused only as a build cache; no primary tracked source touched.

`CARGO_TARGET_DIR=<existing cache> python3 scripts/check_ndi.py --mutation-proof` completed exit 0:

1. `cargo check --locked -p selahcue-desktop --features ndi --all-targets`: exit 0, 41.83s reported. Real grafton-ndi 2.0.0 generated bindings; selahcue-desktop's real NDI module typechecked.
2. `cargo clippy --locked -p selahcue-desktop --features ndi --all-targets -- -D warnings`: exit 0, 16.89s reported.
3. Temporarily appended an `#[cfg(feature = "ndi")]` function to actual `video_sink.rs` assigning the marker string `NDI_GATE_TYPE_MUTATION` to u8. Real Cargo check exits nonzero with E0308 at that exact source line and marker. The helper requires both that diagnostic code and marker, rejecting unrelated prerequisite failures as proof.
4. Source restored byte-for-byte in finally; repeated Cargo check exits 0, 13.18s reported. No tracked desktop source diff or lock change remains. The complete helper exited 0; no local process remains running.

Raw log: `/private/tmp/wave10-ndi-local.log` (task-owned local diagnostic, not a hosted result). Reported times are local tool durations with cache and competing system work, not a CI budget or performance guarantee.

## Controls and limits

- `python3 scripts/check_ndi.py --self-test`: four grouped controls pass. Private 0700 staging/copy/empty-library checks on Linux/macOS layouts; directory cleanup on success and exception; build/test/run/package command refusal; unrelated mutation failure refused and original source restored.
- `actionlint .github/workflows/ci.yml`: exit 0.
- Workflow controls: 118 cases pass; six workflows/19 jobs checked.
- Minute controls: self-tests and current six workflows pass unchanged; no macOS runners, Windows only through tier, existing three matrix jobs remain known to alarm.
- Diff checks confirm vendor headers, manifests/locks, installer workflow and application source unchanged.

Required hosted Linux check/clippy/mutation and all four independent reviews remain pending until their actual results are recorded. Local macOS verification does not establish Linux success. This is debug-profile type/lint coverage of the real `ndi` feature, not release code generation, link correctness, NDI discovery/broadcast, SDK licensing readiness or Windows packaging acceptance. Real release installers continue to require their own approved runtime/import library and manual/main-only packaging path.
