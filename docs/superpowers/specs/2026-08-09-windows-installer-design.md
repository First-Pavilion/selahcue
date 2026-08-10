# Windows installer — one-click, full-featured (NDI + STT) — design

- **Date:** 2026-08-09
- **Status:** Approved design (pending spec review) → next step: implementation plan
- **Owner decisions captured below** (from the brainstorming session)

## Goal

Produce a **single downloadable Windows installer** that a non-technical user (church tech
volunteer) can double-click to install SelahCue and test it end-to-end. The installer bundles
**both** desktop binaries and both native features:

- `selahcue-operator.exe` — the Tauri operator console (built `--features stt`)
- `selahcue-output.exe` — the native audience output window (built `--features ndi`)
- `Processing.NDI.Lib.x64.dll` — the NDI runtime, beside the output exe
- WebView2 bootstrapper (Tauri NSIS default)

**The end user never installs Rust or any toolchain** — they download the `-setup.exe`, run it,
click through the SmartScreen prompt (unsigned), and use the app. All building happens once, on
GitHub Actions.

## Decisions (settled)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Scope | One installer bundling **both** binaries |
| 2 | Launch UX | **One-click auto-launch** — operator spawns the output window and connects |
| 3 | Features | **NDI (output) + STT (operator) both ON** |
| 4 | Build machine | **GitHub Actions `windows-latest`** (no toolchain on the owner's side; no Rust for end users) |
| 5 | NDI SDK provisioning | **Owner supplies the Windows NDI SDK once**; committed via **Git LFS**; CI builds `--features ndi` |
| 6 | NDI redistribution licence | **Approved for this internal test build** — ship the DLL, keep the attribution, don't rename the library |
| 7 | STT model | **Download on first use** (already implemented — no new code) |
| 8 | NDI runtime DLL | **Bundled in the installer** (not downloaded at runtime — see rationale) |

## Why bundle the NDI DLL instead of downloading it

`grafton-ndi` 1.0.0 (verified from its `build.rs`) **link-binds** the NDI import library on
Windows (`cargo:rustc-link-lib=static=Processing.NDI.Lib.x64`) and runs bindgen over the SDK
headers. Consequences:

1. The **build** cannot compile `--features ndi` without the SDK headers + `Processing.NDI.Lib.x64.lib`
   present at compile time. There is no headers-only/dynamic-load mode. This is why the SDK must be
   on the build machine (CI), and why it cannot be downloaded unattended (licence-gated).
2. The **runtime DLL is load-time-linked** — `selahcue-output.exe` will not start if the DLL is
   absent. Downloading it "on first use" would (a) be too late (the exe must load it at startup),
   and (b) make an optional broadcast feature able to block the **core audience display** from
   launching, violating the never-blank principle (NFR-024). Bundling the small (~few MB) DLL beside
   the exe is therefore both simpler and safer.

STT is different: the whisper.cpp engine is **compiled into** the operator exe; only the *model*
(pure data, SHA-256-verified) is fetched at runtime — so "download on first use" is correct there
and already implemented.

## Runtime behaviour

1. User launches **SelahCue Operator** (Start Menu / desktop shortcut).
2. Operator's Tauri `setup` hook detects the sibling `selahcue-output.exe`, deletes any stale
   endpoint file, spawns the output window, polls (bounded) for the freshly-written endpoint
   descriptor, then connects over pinned-TLS (`RemoteOperator`). One click → both windows up and
   connected.
3. **STT:** first "Start listening" downloads the small whisper model into the per-user cache
   (needs internet once), then transcribes live. Already wired in
   `crates/selahcue-operator/src/listening.rs`.
4. **NDI:** Screens page → enable "NDI OUTPUT" → the output window broadcasts (DLL present).
5. On operator quit, the spawned output window is terminated (no orphan process).

## Changes

### 1. Packaging — `crates/selahcue-operator/tauri.conf.json`

- `bundle.active: true`
- `bundle.targets: ["nsis"]`
- `bundle.externalBin: ["binaries/selahcue-output"]` — the bundler places
  `selahcue-output.exe` beside `selahcue-operator.exe` in the install root.
- `bundle.resources` — place `Processing.NDI.Lib.x64.dll` in the install root (sibling of both
  exes). Exact Tauri v2 resource mapping to be confirmed against the produced installer (see
  Verification); the DLL **must** end up next to `selahcue-output.exe`, not in a nested subdir.

### 2. Auto-launch — `crates/selahcue-operator/src/main.rs` (`setup` hook, ~L2421)

Before `build_backend()`:

- Resolve `current_exe().parent()?.join("selahcue-output.exe")`.
- **If it exists (packaged install):** remove any stale
  `temp_dir()/selahcue-operator-endpoint.json`; spawn the output window with
  `std::process::Command`; keep the `Child` in Tauri-managed state; poll for the endpoint file
  (bounded, ~10 s, ~150 ms interval); then `build_backend()` reads it and connects.
- **If it does not exist (dev `cargo run` / `make run`):** skip the spawn — today's behaviour is
  unchanged (the operator connects to a separately-launched output window, else the demo backend).
  The operator crate builds to its own `target/`, so a dev run never has the sibling exe — this is
  the clean dev/prod gate.
- Terminate the child on `RunEvent::ExitRequested` / window close.
- No new Tauri plugin or capability — plain `std::process`. Respect `clippy::unwrap_used = warn`
  (no unwraps; every failure degrades gracefully to the no-spawn/demo path with an honest log).

### 3. NDI vendoring — `implementation/desktop/vendor/ndi/windows/` + Git LFS

- Owner-supplied files land at:
  - `vendor/ndi/windows/include/Processing.NDI.*.h`
  - `vendor/ndi/windows/lib/x64/Processing.NDI.Lib.x64.lib`
  - `vendor/ndi/windows/lib/x64/Processing.NDI.Lib.x64.dll`
  (matching the layout `fetch_ndi_sdk.sh` / the vendor README already expect.)
- Add `.gitattributes` LFS rules for the binary payload (`*.lib`, `*.dll`); un-ignore
  `vendor/ndi/windows/` in `vendor/ndi/.gitignore`.
- The normal CI matrix and `make ci` remain **native-free** (they never pass `--features ndi`), so
  committing the SDK does not change existing builds.

### 4. CI — new `.github/workflows/windows-installer.yml` (`workflow_dispatch`)

Manual "Run workflow" button, so it never slows the normal push/PR matrix. On `windows-latest`:

1. `actions/checkout@v4` with `lfs: true`.
2. `dtolnay/rust-toolchain@stable`; `Swatinem/rust-cache@v2`.
3. Ensure build deps for whisper-rs STT: `cmake` (preinstalled) and LLVM/libclang for bindgen
   (set `LIBCLANG_PATH`); fail fast with a clear message if absent.
4. `NDI_SDK_DIR = implementation/desktop/vendor/ndi/windows`.
5. Build output window: `cargo build --release -p selahcue-desktop --features ndi`.
6. Stage the sidecar: copy `target/release/selahcue-output.exe` →
   `crates/selahcue-operator/binaries/selahcue-output-x86_64-pc-windows-msvc.exe`.
7. Stage the NDI DLL where the tauri `resources` mapping expects it.
8. Install the Tauri CLI (v2); `cargo tauri build --features stt` in the operator crate.
9. `actions/upload-artifact@v4` with `target/release/bundle/nsis/*-setup.exe`.

## Verification

I **cannot build or run any of this from macOS** (no Windows target, no NDI SDK, no MSVC). Verified
evidence will come from:

- The CI job compiling `--features ndi` (output) and `--features stt` (operator) green, and
  producing the `-setup.exe`.
- A manual check that the installer's payload contains **both** exes and the NDI DLL as siblings in
  the install root (the DLL placement is the highest-risk detail for a blind build).
- Owner smoke test on a real Windows machine: install → launch operator → output window appears and
  connects → "Start listening" downloads the model and transcribes → NDI enable broadcasts.

Local (macOS) checks that still apply: `cargo check`/`clippy`/`test` on the operator (default,
no-feature) for the auto-spawn code, plus `cargo fmt --check` and `python3 scripts/operator_headless.py`.

## Risks & coverage gaps

- **Blind build** — auto-spawn, DLL placement, and feature linking are only verifiable via the CI
  build + owner smoke test, not from this Mac. Highest-risk item: NDI DLL landing next to the exe.
- **Unsigned** — SmartScreen "Windows protected your PC" → *More info* → *Run anyway*. Expected for
  an internal test build; code signing is a follow-up.
- **whisper-rs build** — needs cmake + libclang on the runner; the workflow checks these up front so
  a missing dep fails fast (never a silent no-op).
- **STT first run** needs internet (model download). NDI needs the SDK committed (owner-provided).
- **Quit semantics** — quitting the operator terminates the output window; acceptable for a bundled
  test app (documented, revisit if it conflicts with service resilience expectations).

## Out of scope / follow-ups

- Code signing / notarization (removes SmartScreen warning).
- MSI target (only NSIS for now).
- Bundling the STT model for fully-offline first run.
- Committing the NDI runtime DLL into a *released* (non-internal) build — needs product/legal sign-off
  beyond this internal test.
