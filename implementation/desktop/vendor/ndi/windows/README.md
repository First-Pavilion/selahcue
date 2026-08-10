# Vendored Windows NDI headers (for the CI installer build)

The Windows installer builds `selahcue-desktop --features ndi`, which needs the NDI SDK at compile
time. Rather than depend on the licence-gated developer SDK (it cannot be downloaded unattended),
the CI job **self-provisions NDI from public sources** — so no manual SDK download is required.

What lives here vs. what CI generates:

| Piece | Source | Committed? |
|-------|--------|-----------|
| `include/Processing.NDI.*.h` | NDI headers (identical across platforms) | **Yes** — this folder |
| `lib/x64/Processing.NDI.Lib.x64.dll` | public NDI runtime redistributable (`ndi.link/NDIRedistV6`) | No — fetched on the runner |
| `lib/x64/Processing.NDI.Lib.x64.lib` | generated from the DLL's exports (`dumpbin` → `.def` → `lib`) | No — generated on the runner |

At build time the CI job assembles a scratch `NDI_SDK_DIR` (these headers + the generated lib + the
DLL) and points `grafton-ndi` at it, then bundles the DLL beside `selahcue-output.exe` in the
installer. See `.github/workflows/windows-installer.yml`.

## If you ever want the real SDK instead

On a Windows machine with the NDI 6 SDK installed (from https://ndi.video/), under Git Bash,
`scripts/fetch_ndi_sdk.sh` populates the full `windows/{include,lib/x64}` layout. Not required for
the CI build.

## Licence

The NDI runtime is redistributed under the NDI SDK License Agreement (internal test build,
owner-approved): the DLL is shipped unrenamed with attribution
"NDI® is a registered trademark of Vizrt NDI AB." The headers are committed for build use only.
