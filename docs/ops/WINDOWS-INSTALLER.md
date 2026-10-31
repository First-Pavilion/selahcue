# Windows installer — build & install

A single downloadable installer bundling the SelahCue operator console + native output window,
with NDI broadcast and on-device STT. Built by GitHub Actions; **no toolchain is needed on the
maintainer's machine, no manual SDK download, and end users never install Rust.**

## Produce an installer

1. GitHub → Actions → **windows-installer** → **Run workflow**, with branch **main** selected.
   Packaging is manual-only: pushes, pull requests, tags and releases never start it. A manual
   dispatch on any other branch or tag skips the packaging job before runner setup or credentials.
2. When it finishes, download the **selahcue-windows-installer** artifact — it contains
   `SelahCue Operator_<version>_x64-setup.exe` and `release-metadata.json`. The metadata records
   the exact dispatched main commit SHA, ref, event, repository, run ID and attempt. Checkout is
   pinned to that SHA, so a newer commit reaching main during the run cannot change its source.

This workflow still builds the ordinary release profile. It does **not** yet ship the new
expiring-key field-test profile: credential-expiry proof, a dedicated pilot profile and its
approved artifact-scanner policy remain tracked prerequisites (17tnw2bbhvz, 17tnw2bbhw1,
17tnw2bbhwz). A skipped non-main run or a metadata file is not proof of a working installer.

For the existing ordinary-release path, NDI is self-provisioned on the runner from public sources:
committed headers + the public NDI runtime redistributable (`ndi.link/NDIRedistV6`) + an import
library generated from the DLL. See `.github/workflows/windows-installer.yml` and
`implementation/desktop/vendor/ndi/windows/README.md`.

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

## First-run verification (owner)

This build path has Windows-only steps that cannot be tested from a Mac. On the first workflow run,
confirm:
1. The **Provision NDI** step prints "NDI provisioned at … (N exports)" and the
   **Build output window (--features ndi)** step links successfully.
2. After installing into a scratch VM/dir, `Processing.NDI.Lib.x64.dll` and `selahcue-output.exe`
   are siblings in the install root (if the DLL landed in a nested `resources/` subdir, adjust the
   `bundle.resources` mapping in `tauri.conf.json`).
3. NDI broadcast actually appears on an NDI receiver on the LAN.
4. The **Audience** and **Stage** windows open by themselves and the Screens page names a real
   monitor for each. If both rows read "No display assigned" and no output windows appeared, the
   operator could not start `selahcue-output.exe` — check it is a sibling of
   `selahcue-operator.exe` in the install root (see §What's inside).

## Auto-launch

On startup the operator spawns the sibling `selahcue-output.exe`, waits up to ~10s for its loopback
endpoint file, then connects over pinned TLS (`src/autolaunch.rs`). Quitting the console terminates
the output window, so no orphan process is left behind. This preserves the two-process model of
ADR-0002/0003 — the audience compositor is native, never the WebView.

In a dev run the sibling binary does not exist beside `target/…/selahcue-operator`, so the spawn is
a no-op and the console behaves as before: it connects to a separately started output window
(`make output`), or falls back to the stand-alone demo backend.
