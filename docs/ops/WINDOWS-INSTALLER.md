# Windows installer — build & install

A single downloadable installer bundling the SelahCue operator console + native output window,
with NDI broadcast and on-device STT. Built by GitHub Actions; **no toolchain is needed on the
maintainer's machine, no manual SDK download, and end users never install Rust.**

## Produce an installer

1. GitHub → Actions → **windows-installer** → **Run workflow**.
2. When it finishes, download the **selahcue-windows-installer** artifact — it contains
   `SelahCue Operator_<version>_x64-setup.exe`.

There is nothing to set up first. NDI is self-provisioned on the runner from public sources:
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

## Note on auto-launch (pending)

The one-click auto-launch (the operator spawning + connecting to the output window on startup) is
implemented in the operator crate as a separate step (plan Tasks 1–2), deferred until the
operator's in-flight changes settle. Until it lands, the installer bundles both executables but the
operator connects only if the output window is already running; otherwise it shows the demo
backend. See `docs/superpowers/plans/2026-08-09-windows-installer.md`.
