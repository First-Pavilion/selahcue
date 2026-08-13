# Windows Installer (one-click, NDI + STT) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a single downloadable Windows NSIS installer that bundles the SelahCue operator console + native output window (with NDI broadcast and on-device STT), where launching the operator auto-starts and connects to the output window — built entirely by GitHub Actions so neither the owner nor end users install any toolchain.

**Architecture:** The operator (Tauri v2) ships the output window (`selahcue-output.exe`) as an `externalBin` sibling and the NDI runtime DLL as a bundled resource. On startup the operator spawns the sibling output window, waits for its loopback endpoint file, then connects over pinned-TLS (`RemoteOperator`) — preserving the ADR-0002/0003 two-process model. A `workflow_dispatch` CI job on `windows-latest` builds the output window `--features ndi`, stages it + the DLL, then `cargo tauri build --features stt` and uploads the `-setup.exe`.

**Tech Stack:** Rust (MSVC), Tauri v2 (NSIS bundler), grafton-ndi (NDI 6 SDK, link-time), whisper-rs (whisper.cpp, needs cmake + libclang), GitHub Actions `windows-latest`.

## Revision note (2026-08-09, during execution)

The NDI developer SDK proved un-downloadable unattended (licence-gated, HTTP 403). Owner chose
**CI self-provisioning from public sources** instead of supplying the SDK. Net changes vs. the
original Tasks 5–6:
- Only the NDI **headers** are committed (`vendor/ndi/windows/include/`, copied from the identical
  macOS set). No `.lib`/`.dll` committed → **Git LFS dropped** (root `.gitattributes` removed).
- CI (Task 6) fetches the **public NDI runtime redistributable** (`ndi.link/NDIRedistV6`) for the
  DLL, **generates the import lib** from it (`dumpbin` → `.def` → `lib`, via `ilammy/msvc-dev-cmd`),
  assembles a scratch `NDI_SDK_DIR`, and builds `--features ndi`. No manual SDK step.
- The two Windows-only steps (DLL extraction, import-lib generation) are **verified only by the
  first CI run** — untestable from macOS.

Tasks 1–2 (operator auto-launch wiring) remain deferred until `operator/main.rs` WIP settles.

## Revision note (2026-08-13, deferral closed)

Tasks 1–2 are **now implemented** (`src/autolaunch.rs` + the `setup`-hook wiring). The deferral
shipped an installer whose only entry point was the console: nothing spawned the bundled
`selahcue-output.exe`, so `build_backend()` found no endpoint file, fell back to
`Backend::Local(demo_shell())` — a controller whose `display_status` is empty because only
`selahcue-desktop` ever calls `set_output_status` — and the Screens surface honestly reported
"No display assigned" for Audience and Stage. Runtime-verified on macOS by staging a real sidecar
beside the operator's debug exe: the console spawned it, waited for the endpoint, and logged
`connected to output window at 127.0.0.1:<port>`. Any installer built before this change needs a
rebuild.

## Global Constraints

- Operator crate lint: `clippy::unwrap_used = "warn"` — no `.unwrap()`; degrade gracefully. (`.expect()` is allowed; only `unwrap_used` is set.)
- CI/local gate includes `cargo fmt --check` — every Rust change must be `cargo fmt`-clean.
- Two-process model is intentional (ADR-0002/0003): the WebView is the console only; the compositor is the native output window. Auto-launch spawns a **separate process**, never renders audience output in the WebView.
- Never-blank (NFR-024): the output window must not depend on an optional feature to launch — this is why the NDI DLL is **bundled** (present at load time), not downloaded at runtime.
- NDI redistribution (internal test build, owner-approved): ship `Processing.NDI.Lib.x64.dll` unmodified; do **not** rename the library; include attribution "NDI® is a registered trademark of Vizrt NDI AB" in the installer docs.
- Tauri v2 (`"$schema": "https://schema.tauri.app/config/2"`).
- The installer is **unsigned** for this internal test build (SmartScreen warning expected).
- Normal CI (`ci.yml`) and `make ci` stay native-feature-free — they never pass `--features ndi`/`--features stt`. Nothing in this plan may change that.

---

## File Structure

- Create: `implementation/desktop/crates/selahcue-operator/src/autolaunch.rs` — pure helpers (sidecar path resolution, bounded endpoint poll) + the spawn/kill wrapper. One responsibility: bring up and tear down the bundled output window. Inline `#[cfg(test)] mod tests` (matches the operator's convention, e.g. `deck_library.rs`).
- Modify: `implementation/desktop/crates/selahcue-operator/src/main.rs` — declare the module, DRY the endpoint path, wire the spawn + child-kill-on-close into the Tauri `setup` hook.
- Modify: `implementation/desktop/crates/selahcue-desktop/src/main.rs` — suppress the Windows console window for the bundled output binary.
- Modify: `implementation/desktop/crates/selahcue-operator/tauri.conf.json` — enable the NSIS bundle, `externalBin`, and the NDI DLL resource.
- Modify: `implementation/desktop/vendor/ndi/.gitignore` — un-ignore the committed Windows SDK subset.
- Create: `.gitattributes` — Git LFS rules for the NDI binary payload.
- Create: `implementation/desktop/vendor/ndi/windows/README.md` — exactly which owner-provided files go here.
- Create: `.github/workflows/windows-installer.yml` — the manual build+upload job.
- Create: `docs/ops/WINDOWS-INSTALLER.md` — how to produce it and how end users install it.

**Note — no task needed for STT model download:** it is already implemented end-to-end in `crates/selahcue-operator/src/listening.rs` (`fetch_model` on first `start_listening`, SHA-256-verified) and reported by `stt_ready`. Building the operator `--features stt` is all that's required (Task 6).

---

### Task 1: Auto-launch helper module (pure logic, TDD)

**Files:**
- Create: `implementation/desktop/crates/selahcue-operator/src/autolaunch.rs`

**Interfaces:**
- Produces:
  - `pub fn output_sidecar_path(operator_exe: &std::path::Path) -> std::path::PathBuf`
  - `pub fn wait_for_endpoint(ready: impl FnMut() -> bool, max_attempts: u32, on_wait: impl FnMut()) -> bool`
  - `pub struct SpawnedOutput` with `pub fn kill(&self)`
  - `pub fn spawn_output_window(operator_exe: &std::path::Path, endpoint: &std::path::Path) -> Option<SpawnedOutput>`

- [ ] **Step 1: Write the failing tests**

Create `implementation/desktop/crates/selahcue-operator/src/autolaunch.rs` with only the tests first:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;
    use std::path::Path;

    #[test]
    fn sidecar_sits_beside_the_operator_exe() {
        let got = output_sidecar_path(Path::new("/opt/selahcue/selahcue-operator"));
        let want = format!("/opt/selahcue/selahcue-output{}", std::env::consts::EXE_SUFFIX);
        assert_eq!(got, Path::new(&want));
    }

    #[test]
    fn wait_returns_true_as_soon_as_ready_and_stops_polling() {
        let calls = Cell::new(0u32);
        let waits = Cell::new(0u32);
        // false, false, true -> ready on the 3rd check
        let ok = wait_for_endpoint(
            || {
                let n = calls.get() + 1;
                calls.set(n);
                n >= 3
            },
            10,
            || waits.set(waits.get() + 1),
        );
        assert!(ok);
        assert_eq!(calls.get(), 3, "stops checking once ready");
        assert_eq!(waits.get(), 2, "waits only between checks");
    }

    #[test]
    fn wait_gives_up_after_max_attempts() {
        let waits = Cell::new(0u32);
        let ok = wait_for_endpoint(|| false, 3, || waits.set(waits.get() + 1));
        assert!(!ok);
        assert_eq!(waits.get(), 2, "no wait after the final failed check");
    }

    #[test]
    fn wait_with_zero_attempts_is_false() {
        assert!(!wait_for_endpoint(|| true, 0, || {}));
    }

    #[test]
    fn spawn_returns_none_when_no_sidecar_present() {
        // A temp dir with no selahcue-output binary beside the fake operator exe.
        let dir = std::env::temp_dir().join(format!("selahcue-autolaunch-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let fake_operator = dir.join(format!("selahcue-operator{}", std::env::consts::EXE_SUFFIX));
        let endpoint = dir.join("selahcue-operator-endpoint.json");
        assert!(spawn_output_window(&fake_operator, &endpoint).is_none());
        let _ = std::fs::remove_dir_all(&dir);
    }
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd implementation/desktop/crates/selahcue-operator && cargo test autolaunch`
Expected: FAIL — `cannot find function output_sidecar_path` / `wait_for_endpoint` / `spawn_output_window`.

- [ ] **Step 3: Write the minimal implementation**

Prepend to `autolaunch.rs` (above the `#[cfg(test)]` module):

```rust
//! Auto-launch of the native audience output window bundled beside the operator.
//!
//! In a packaged install the operator ships `selahcue-output(.exe)` as a sibling binary and
//! starts it on launch, then connects over the loopback endpoint file (the same file a
//! hand-started output window writes). This keeps the ADR-0002/0003 two-process model: the
//! console never renders audience output; it drives a separate native compositor process.
//!
//! In a dev run (`cargo run` / `make run`) the sibling binary does not exist next to the
//! operator's `target/` executable, so `spawn_output_window` returns `None` and today's
//! behaviour (connect to a separately-launched window, else the demo backend) is unchanged.

use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;

/// The bundled output-window binary that should sit beside the operator executable.
pub fn output_sidecar_path(operator_exe: &Path) -> PathBuf {
    let name = format!("selahcue-output{}", std::env::consts::EXE_SUFFIX);
    match operator_exe.parent() {
        Some(dir) => dir.join(name),
        None => PathBuf::from(name),
    }
}

/// Poll `ready` up to `max_attempts` times, calling `on_wait` between attempts. Returns `true`
/// as soon as `ready()` is true, else `false`. Clock-free so it is deterministically testable;
/// the real caller passes a filesystem check + a `thread::sleep`.
pub fn wait_for_endpoint(
    mut ready: impl FnMut() -> bool,
    max_attempts: u32,
    mut on_wait: impl FnMut(),
) -> bool {
    for attempt in 0..max_attempts {
        if ready() {
            return true;
        }
        if attempt + 1 < max_attempts {
            on_wait();
        }
    }
    false
}

/// Handle to the spawned output window so the operator can terminate it on exit (no orphan
/// process). `kill` is best-effort and safe to call more than once.
pub struct SpawnedOutput {
    child: Mutex<Option<Child>>,
}

impl SpawnedOutput {
    pub fn kill(&self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

/// Start the bundled output window (packaged install only) and wait briefly for its loopback
/// endpoint file to appear, so the operator's subsequent `build_backend()` connects instead of
/// falling back to the demo. Returns `None` when the sibling binary is absent (dev run) or the
/// spawn fails — the caller then keeps today's behaviour.
pub fn spawn_output_window(operator_exe: &Path, endpoint: &Path) -> Option<SpawnedOutput> {
    let sidecar = output_sidecar_path(operator_exe);
    if !sidecar.exists() {
        return None;
    }
    // Remove any stale endpoint from a previous run so we only ever connect to THIS instance.
    let _ = std::fs::remove_file(endpoint);
    let child = Command::new(&sidecar).spawn().ok()?;
    let appeared = wait_for_endpoint(
        || endpoint.exists(),
        66, // ~10s at 150ms per attempt
        || std::thread::sleep(Duration::from_millis(150)),
    );
    if !appeared {
        eprintln!(
            "SelahCue operator: output window started but wrote no endpoint yet; \
             using the demo backend until it connects."
        );
    }
    Some(SpawnedOutput {
        child: Mutex::new(Some(child)),
    })
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd implementation/desktop/crates/selahcue-operator && cargo test autolaunch`
Expected: PASS (5 tests). `spawn_returns_none_when_no_sidecar_present` passes because no `selahcue-output` binary exists in the temp dir.

- [ ] **Step 5: Lint + format**

Run: `cd implementation/desktop/crates/selahcue-operator && cargo fmt && cargo clippy --all-targets -- -D warnings`
Expected: no warnings (note the module is not yet declared in `main.rs`, so clippy only checks it once Task 2 adds `mod autolaunch;` — that is fine; this step confirms formatting).

- [ ] **Step 6: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/src/autolaunch.rs
git commit -m "feat(operator): auto-launch helpers for the bundled output window"
```

---

### Task 2: Wire auto-launch into the Tauri app

**Files:**
- Modify: `implementation/desktop/crates/selahcue-operator/src/main.rs` (module decl near L40; `read_endpoint` at L2062; `setup` hook at L2502)

**Interfaces:**
- Consumes: `autolaunch::spawn_output_window`, `autolaunch::SpawnedOutput` (Task 1).
- Produces: no new public API; behavioural change to app startup + shutdown.

- [ ] **Step 1: Declare the module**

Next to the other module declarations (currently `mod listening;` L31, `mod deck_workspace;` L35, `mod deck_library;` L40), add:

```rust
mod autolaunch;
```

- [ ] **Step 2: DRY the endpoint path**

Find `read_endpoint` (L2062):

```rust
fn read_endpoint() -> Option<Endpoint> {
    let path = std::env::temp_dir().join("selahcue-operator-endpoint.json");
    let data = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&data).ok()
}
```

Replace with:

```rust
/// The loopback endpoint descriptor path shared with the output window (both processes agree on
/// `temp_dir()/selahcue-operator-endpoint.json`).
fn endpoint_file_path() -> std::path::PathBuf {
    std::env::temp_dir().join("selahcue-operator-endpoint.json")
}

fn read_endpoint() -> Option<Endpoint> {
    let data = std::fs::read_to_string(endpoint_file_path()).ok()?;
    serde_json::from_str(&data).ok()
}
```

- [ ] **Step 3: Spawn the output window + kill on close, in the `setup` hook**

In the `.setup(|app| { ... })` closure (L2502), replace the first line:

```rust
            // Connect on the Tauri runtime so the client is bound to the same reactor the
            // async commands run on.
            let backend = tauri::async_runtime::block_on(build_backend());
```

with:

```rust
            // Packaged install: bring up the bundled output window (a sibling binary) BEFORE we
            // build the backend, so `build_backend()` finds its fresh loopback endpoint and
            // connects instead of falling back to the demo. In a dev run the sibling is absent,
            // so this is a no-op and today's behaviour is unchanged (ADR-0002/0003: separate
            // native compositor process, never rendered in the WebView).
            let output = std::env::current_exe()
                .ok()
                .and_then(|exe| autolaunch::spawn_output_window(&exe, &endpoint_file_path()))
                .map(std::sync::Arc::new);
            if let Some(output) = &output {
                // Terminate the bundled output window when the operator window is destroyed, so
                // quitting the console does not orphan the audience-output process.
                if let Some(win) = app.get_webview_window("main") {
                    let output = std::sync::Arc::clone(output);
                    win.on_window_event(move |event| {
                        if matches!(event, tauri::WindowEvent::Destroyed) {
                            output.kill();
                        }
                    });
                }
            }
            // Connect on the Tauri runtime so the client is bound to the same reactor the
            // async commands run on.
            let backend = tauri::async_runtime::block_on(build_backend());
```

Note: `app.get_webview_window` and `app.manage` both come from `tauri::Manager`, already in scope (used by the existing `app.manage(AppState { .. })`). No new imports needed.

- [ ] **Step 4: Format + lint + compile**

Run:
```bash
cd implementation/desktop/crates/selahcue-operator
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo check
```
Expected: clean. If clippy flags `output` unused when the `Arc` is only consumed inside the `if let`, confirm it is used (the `&output` borrow inside `if let Some(output) = &output` uses it); no `#[allow]` needed.

- [ ] **Step 5: Run the operator test suite**

Run: `cd implementation/desktop/crates/selahcue-operator && cargo test`
Expected: PASS — Task 1's `autolaunch` tests plus the existing suite. This confirms the module is wired without regressions. (Auto-spawn itself is not unit-tested here — it is process/GUI I/O verified by the CI build in Task 6 and the owner smoke test.)

- [ ] **Step 6: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/src/main.rs
git commit -m "feat(operator): auto-launch + reap the bundled output window on startup/exit"
```

---

### Task 3: Suppress the Windows console window for the output binary

**Files:**
- Modify: `implementation/desktop/crates/selahcue-desktop/src/main.rs` (top of file)

**Interfaces:**
- Consumes: nothing. Produces: nothing (build attribute only).

- [ ] **Step 1: Confirm the attribute is absent**

Run: `grep -n "windows_subsystem" implementation/desktop/crates/selahcue-desktop/src/main.rs`
Expected: no output (attribute not present). If it IS present, skip this task.

- [ ] **Step 2: Add the attribute**

Immediately after the module doc comment block (the `//! ...` lines at the top, before the first `use`/item), add:

```rust
// In release builds on Windows, run as a GUI app so no console window appears behind the
// audience output when the operator auto-launches it. No effect on other platforms or in debug
// builds (dev keeps the console banner). The endpoint file — not stdout — is how the operator
// discovers this window, so suppressing the console changes no behaviour.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
```

- [ ] **Step 3: Compile-check**

Run: `cd implementation/desktop && cargo check -p selahcue-desktop && cargo fmt --check`
Expected: clean (the attribute is ignored on non-Windows, so this passes on macOS/Linux too).

- [ ] **Step 4: Commit**

```bash
git add implementation/desktop/crates/selahcue-desktop/src/main.rs
git commit -m "feat(desktop): no console window for the output binary in release (Windows)"
```

---

### Task 4: Enable the NSIS bundle + externalBin + NDI DLL resource

**Files:**
- Modify: `implementation/desktop/crates/selahcue-operator/tauri.conf.json`

**Interfaces:**
- Consumes: the sidecar exe + DLL staged by CI (Task 6). Produces: the installer definition.

- [ ] **Step 1: Edit the `bundle` block**

Replace the current `bundle` object:

```json
  "bundle": {
    "active": false,
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ]
  }
```

with:

```json
  "bundle": {
    "active": true,
    "targets": ["nsis"],
    "externalBin": ["binaries/selahcue-output"],
    "resources": {
      "binaries/Processing.NDI.Lib.x64.dll": "Processing.NDI.Lib.x64.dll"
    },
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ]
  }
```

Rationale: `externalBin` places `selahcue-output.exe` beside `selahcue-operator.exe` in the install root; the `resources` map places the NDI runtime DLL in the same directory (a sibling of the output exe — required because grafton-ndi load-time-links it). The exact on-disk resource location is verified against the produced installer in Task 6 / the owner smoke test.

- [ ] **Step 2: Validate the JSON**

Run: `python3 -c "import json; json.load(open('implementation/desktop/crates/selahcue-operator/tauri.conf.json')); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Confirm normal compile is unaffected**

Run: `cd implementation/desktop/crates/selahcue-operator && cargo check`
Expected: clean. `cargo check`/`clippy`/`test` do NOT process `externalBin`/`resources` (only `tauri build` does), so the missing `binaries/` files do not break normal builds — confirming `ci.yml`'s operator job stays green.

- [ ] **Step 4: Commit**

```bash
git add implementation/desktop/crates/selahcue-operator/tauri.conf.json
git commit -m "build(operator): NSIS bundle with output-window sidecar + NDI runtime DLL"
```

---

### Task 5: Vendor the Windows NDI SDK (git tracking + LFS + owner instructions)

**Files:**
- Modify: `implementation/desktop/vendor/ndi/.gitignore`
- Create: `.gitattributes` (repo root)
- Create: `implementation/desktop/vendor/ndi/windows/README.md`

**Interfaces:**
- Consumes: owner-provided SDK files (added later). Produces: a committed, CI-discoverable `NDI_SDK_DIR` layout.

- [ ] **Step 1: Un-ignore the Windows subset**

`implementation/desktop/vendor/ndi/.gitignore` currently ends with:

```
*/include/
*/lib/
# Keep this dir and its docs tracked.
!README.md
!.gitignore
```

Append:

```
# The WINDOWS NDI SDK subset (headers + import lib + runtime DLL) IS committed for the CI
# Windows-installer build — owner-provided, redistribution approved for internal test builds.
# (macOS/Linux payloads remain ignored / fetched via scripts/fetch_ndi_sdk.sh.)
!windows/
!windows/include/
!windows/lib/
```

- [ ] **Step 2: Add Git LFS rules for the binary payload**

Create `.gitattributes` at the repo root:

```
# NDI Windows SDK binaries committed for the CI installer build (Task: windows-installer).
# Small (~6 MB) but binary — track via Git LFS. Headers stay as normal text-tracked files.
implementation/desktop/vendor/ndi/windows/lib/x64/*.lib filter=lfs diff=lfs merge=lfs -text
implementation/desktop/vendor/ndi/windows/lib/x64/*.dll filter=lfs diff=lfs merge=lfs -text
```

- [ ] **Step 3: Document the required files**

Create `implementation/desktop/vendor/ndi/windows/README.md`:

```markdown
# Vendored Windows NDI SDK (committed for the CI installer build)

These files are the minimum subset of the NDI 6 SDK the Windows-installer CI build needs. They
are owner-provided (the SDK is licence-gated and cannot be downloaded unattended) and committed
here — the binary `lib/x64` files via Git LFS (see repo-root `.gitattributes`).

Required layout (matches `scripts/fetch_ndi_sdk.sh` output for Windows):

```
windows/
  include/Processing.NDI.Lib.h        (+ the other Processing.NDI.*.h headers)
  lib/x64/Processing.NDI.Lib.x64.lib  (build-time import library)
  lib/x64/Processing.NDI.Lib.x64.dll  (runtime library, bundled into the installer)
```

## How to populate (owner, one time)

On a Windows machine with the NDI 6 SDK installed (from https://ndi.video/), under Git Bash:

```
scripts/fetch_ndi_sdk.sh            # auto-detects the installed SDK and copies into windows/
```

Then commit (Git LFS must be installed so the .lib/.dll commit as LFS objects):

```
git lfs install
git add implementation/desktop/vendor/ndi/windows
git commit -m "chore(ndi): vendor Windows NDI SDK subset for the installer build"
```

## Licence

Redistributing the NDI runtime is governed by the NDI SDK License Agreement. This internal
test build is owner-approved. Do not rename the library. Attribution: "NDI® is a registered
trademark of Vizrt NDI AB."
```

- [ ] **Step 4: Verify the ignore rules**

Run: `git check-ignore -v implementation/desktop/vendor/ndi/windows/lib/x64/Processing.NDI.Lib.x64.dll; echo "exit=$?"`
Expected: `exit=1` (NOT ignored — no output), or a line showing the `!windows/lib/` negation as the last match. If it prints a `*/lib/` ignore rule with `exit=0`, the negations are wrong — fix ordering in `.gitignore`.

- [ ] **Step 5: Commit the scaffolding (not the SDK binaries — those come from the owner)**

```bash
git add .gitattributes implementation/desktop/vendor/ndi/.gitignore implementation/desktop/vendor/ndi/windows/README.md
git commit -m "chore(ndi): track Windows SDK subset (LFS) for the installer build"
```

> **NOTE (LFS bandwidth):** GitHub free-tier LFS caps bandwidth at ~1 GB/month; each CI run pulls the SDK. The payload is small (~6 MB), so this is fine at low run volume. If it ever becomes a problem, the small files may instead be committed directly to git (drop the `.gitattributes` LFS lines) — functionally identical for CI. `git-lfs` must be installed on whichever machine commits the actual binaries (Step 3 above); it is not required to commit this scaffolding.

---

### Task 6: CI workflow to build + upload the installer, and docs

**Files:**
- Create: `.github/workflows/windows-installer.yml`
- Create: `docs/ops/WINDOWS-INSTALLER.md`

**Interfaces:**
- Consumes: everything from Tasks 1–5 + the owner-committed NDI SDK. Produces: a downloadable `-setup.exe` artifact.

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/windows-installer.yml`:

```yaml
# Manual, on-demand build of the downloadable Windows installer bundling the operator console +
# native output window, with NDI broadcast (--features ndi) and on-device STT (--features stt).
# Kept OUT of the push/PR matrix (workflow_dispatch only) so it never slows normal CI and only
# runs when someone clicks "Run workflow". Requires the owner-committed Windows NDI SDK subset
# under implementation/desktop/vendor/ndi/windows (see its README).
name: windows-installer

on:
  workflow_dispatch: {}

jobs:
  build:
    name: build Windows installer (NDI + STT)
    runs-on: windows-latest
    timeout-minutes: 60
    defaults:
      run:
        working-directory: implementation/desktop
    steps:
      - uses: actions/checkout@v4
        with:
          lfs: true
      - uses: dtolnay/rust-toolchain@stable
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: |
            implementation/desktop
            implementation/desktop/crates/selahcue-operator

      # whisper-rs (STT) compiles whisper.cpp: needs cmake + libclang (bindgen). windows-latest
      # ships both; assert them and export LIBCLANG_PATH so a future image change fails fast here
      # rather than deep inside the build.
      - name: Verify STT build deps (cmake + libclang)
        shell: pwsh
        run: |
          cmake --version
          $llvm = Join-Path $env:ProgramFiles "LLVM\bin"
          if (-not (Test-Path $llvm)) { throw "LLVM/libclang not found at $llvm" }
          "LIBCLANG_PATH=$llvm" | Out-File -FilePath $env:GITHUB_ENV -Append

      # Fail fast with an actionable message if the owner has not yet committed the NDI SDK.
      - name: Verify vendored Windows NDI SDK
        shell: pwsh
        run: |
          $files = @(
            "vendor/ndi/windows/include/Processing.NDI.Lib.h",
            "vendor/ndi/windows/lib/x64/Processing.NDI.Lib.x64.lib",
            "vendor/ndi/windows/lib/x64/Processing.NDI.Lib.x64.dll"
          )
          foreach ($f in $files) {
            if (-not (Test-Path $f)) {
              throw "Missing NDI SDK file: $f. Drop the owner-provided Windows NDI SDK into implementation/desktop/vendor/ndi/windows/ (see its README) and re-run."
            }
          }

      - name: Build output window (--features ndi)
        shell: pwsh
        env:
          NDI_SDK_DIR: ${{ github.workspace }}\implementation\desktop\vendor\ndi\windows
        run: cargo build --release -p selahcue-desktop --features ndi

      - name: Stage the output window as the operator sidecar + NDI DLL
        shell: pwsh
        run: |
          New-Item -ItemType Directory -Force -Path crates/selahcue-operator/binaries | Out-Null
          Copy-Item target/release/selahcue-output.exe `
            crates/selahcue-operator/binaries/selahcue-output-x86_64-pc-windows-msvc.exe -Force
          Copy-Item vendor/ndi/windows/lib/x64/Processing.NDI.Lib.x64.dll `
            crates/selahcue-operator/binaries/Processing.NDI.Lib.x64.dll -Force

      - name: Install Tauri CLI v2
        run: cargo install tauri-cli --version "^2.0" --locked

      - name: Build the installer (--features stt)
        working-directory: implementation/desktop/crates/selahcue-operator
        run: cargo tauri build --features stt

      - name: Upload installer artifact
        uses: actions/upload-artifact@v4
        with:
          name: selahcue-windows-installer
          path: implementation/desktop/crates/selahcue-operator/target/release/bundle/nsis/*-setup.exe
          if-no-files-found: error
```

- [ ] **Step 2: Validate the workflow YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/windows-installer.yml')); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Write the ops doc**

Create `docs/ops/WINDOWS-INSTALLER.md`:

```markdown
# Windows installer — build & install

A single downloadable installer bundling the SelahCue operator console + native output window,
with NDI broadcast and on-device STT. Built by GitHub Actions; **no toolchain is needed on the
maintainer's machine, and end users never install Rust.**

## One-time setup (maintainer)

Commit the Windows NDI SDK subset under `implementation/desktop/vendor/ndi/windows/`
(see that folder's README — it is licence-gated and cannot be downloaded by CI).

## Produce an installer

1. GitHub → Actions → **windows-installer** → **Run workflow**.
2. When it finishes, download the **selahcue-windows-installer** artifact — it contains
   `SelahCue Operator_<version>_x64-setup.exe`.

## Install (end user)

1. Download and run the `-setup.exe`.
2. It is unsigned, so Windows SmartScreen shows "Windows protected your PC" →
   **More info** → **Run anyway**.
3. Launch **SelahCue Operator** — it automatically starts the audience output window and
   connects. Enable NDI on the Screens page; "Start listening" downloads the STT model on first
   use (needs internet once).

## What's inside

`selahcue-operator.exe`, `selahcue-output.exe`, `Processing.NDI.Lib.x64.dll`, and the WebView2
bootstrapper (installed automatically by NSIS). "NDI® is a registered trademark of Vizrt NDI AB."

## Verifying DLL placement (highest-risk item)

After the first successful build, install into a scratch VM/dir and confirm
`Processing.NDI.Lib.x64.dll` and `selahcue-output.exe` are siblings in the install root. If the
DLL landed in a nested `resources/` subdir, adjust the `bundle.resources` mapping in
`tauri.conf.json` and rebuild.
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/windows-installer.yml docs/ops/WINDOWS-INSTALLER.md
git commit -m "ci: on-demand Windows installer build (NDI + STT) + ops docs"
```

- [ ] **Step 5: End-to-end validation (owner, after committing the NDI SDK)**

1. Complete Task 5 Step 3's owner steps (commit the SDK binaries).
2. Run the **windows-installer** workflow; confirm it goes green and uploads the artifact.
3. Install on a real Windows machine and run the smoke test in `docs/ops/WINDOWS-INSTALLER.md`
   (launch → output window appears + connects → NDI broadcasts → STT downloads + transcribes).

---

## Self-Review

**Spec coverage:**
- Installer contains operator (stt) + output (ndi) + DLL + WebView2 → Tasks 4, 6 (build flags, staging, NSIS default). ✓
- One-click auto-launch → Tasks 1, 2. ✓
- STT download-on-first-use → already implemented; Task 6 builds `--features stt` (noted, no task). ✓
- NDI DLL bundled (not downloaded) rationale → Global Constraints + Task 4. ✓
- Built by CI, no toolchain for owner/users → Task 6. ✓
- NDI SDK owner-supplied + committed → Task 5. ✓
- Unsigned/SmartScreen, quit semantics, blind-build verification → docs (Task 6) + Task 2 (kill on close). ✓
- Console-window polish (not in spec, added as correctness/UX for the bundled experience) → Task 3. ✓

**Placeholder scan:** No TBD/TODO; every code/config/YAML block is complete. The one "verify against the produced installer" item (DLL placement) is an explicit verification step, not a deferred implementation.

**Type consistency:** `output_sidecar_path`, `wait_for_endpoint`, `spawn_output_window`, `SpawnedOutput`/`.kill()` are defined in Task 1 and consumed with identical signatures in Task 2. `endpoint_file_path()` is defined once (Task 2 Step 2) and reused by `read_endpoint` and the setup hook. externalBin base name `binaries/selahcue-output` (Task 4) matches the staged file `binaries/selahcue-output-x86_64-pc-windows-msvc.exe` (Task 6). The resource key `binaries/Processing.NDI.Lib.x64.dll` (Task 4) matches the staged DLL path (Task 6).

## Risks & coverage gaps (carried from the spec)

- **Blind build:** auto-spawn, DLL placement, and feature linking are verifiable only via the CI build (Task 6 Step 5) + owner smoke test — not from macOS. Highest risk: the NDI DLL landing next to the exe (explicit verification in the ops doc).
- **Unsigned:** SmartScreen warning expected; code signing is a follow-up.
- **whisper-rs build:** needs cmake + libclang; the workflow asserts them up front (fails fast, never silent).
- **LFS bandwidth:** small payload; direct-commit fallback documented (Task 5 note).
- **Quit semantics:** quitting the operator terminates the output window (Task 2); acceptable for a test app, documented.
