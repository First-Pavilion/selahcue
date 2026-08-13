# macOS DMG build (signed + notarized, Universal) + "SelahCue" rename — design

- **Date:** 2026-08-13
- **Status:** Approved design (pending spec review) → next step: implementation plan
- **Owner decisions captured below** (from the brainstorming session)
- **Sibling:** `2026-08-09-windows-installer-design.md` — this mirrors that job for macOS.

## Goal

Produce a **single downloadable macOS DMG** that a church tech volunteer can double-click to
install SelahCue and test end-to-end, with no Gatekeeper friction — signed with a Developer ID,
notarized, and stapled. It bundles both binaries and both native features, exactly as the Windows
installer does:

- `SelahCue.app/Contents/MacOS/SelahCue` — the Tauri operator console (built `--features stt`)
- `SelahCue.app/Contents/MacOS/selahcue-output` — the native audience output window (`--features ndi`)
- `SelahCue.app/Contents/Frameworks/libndi.dylib` — the NDI runtime

Alongside it, the application's user-facing display name becomes **"SelahCue"** on both platforms
(today it is "SelahCue Operator").

## Decisions (settled)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Signing | **Developer ID: sign + notarize + staple.** Owner supplies six GitHub secrets |
| 2 | NDI | **Owner supplies the macOS NDI SDK**; `libndi.dylib` committed via **Git LFS** |
| 3 | Architecture | **Universal** (`aarch64` + `x86_64`) — church AV machines are often Intel |
| 4 | Rename scope | **"SelahCue" everywhere user-facing** — app name, window title, artifact filenames, Start-menu entry |
| 5 | Build machine | **GitHub Actions `macos-latest`**, `workflow_dispatch` only |
| 6 | Normal CI | **Untouched** — stays native-feature-free; no `--features ndi`/`stt` in `ci.yml` or `make ci` |

## Verified facts (measured, not assumed)

These were checked against the actual artefacts in this repo, and they shape the design:

| Fact | Evidence | Consequence |
|------|----------|-------------|
| `libndi.dylib` is already Universal | `lipo -info` → `x86_64 arm64` | Universal build needs **no** extra NDI work |
| Its install name is already `@rpath/libndi.dylib` | `otool -D` | No `install_name_tool` surgery on the library |
| The NDI-linked output binary has **zero `LC_RPATH` entries** | `otool -l target/debug/selahcue-output` | **Must add an rpath** — see Risk R1 |
| The dylib is built for **minos 13.0** | `otool -l` → `LC_BUILD_VERSION` | `LSMinimumSystemVersion` must rise 11.0 → 13.0 |
| The dylib is 28 MB | `ls -lh` | Far past GitHub's per-secret size limit → Git LFS |
| `make` relies on `DYLD_FALLBACK_LIBRARY_PATH` for dev NDI runs | `Makefile` `NDI_LOADER` | Confirms the missing-rpath finding independently |

## Architecture

Unchanged from Windows in every structural respect — this is a packaging job, not an app-behaviour
change. ADR-0002/0003 still hold: the WebView is the console only; the audience compositor is a
separate native process.

The auto-launch fix (commit `c070df6`, `src/autolaunch.rs`) is **platform-agnostic and needs no
change**. Tauri places `externalBin` sidecars in `Contents/MacOS/` beside the main executable, and
`output_sidecar_path` resolves the sibling of `current_exe()` — so it works in an `.app` bundle
unmodified. Renaming the operator binary cannot break it, because the sidecar's name comes from the
`externalBin` key (`binaries/selahcue-output`), not from `productName`.

## Components

### 1. Rename to "SelahCue"

- `tauri.conf.json` — `productName: "SelahCue"`; `app.windows[0].title: "SelahCue"`.
- `Info.plist` — `CFBundleName` / `CFBundleDisplayName` → `SelahCue`; `LSMinimumSystemVersion` → `13.0`.
- `mainBinaryName: "SelahCue"` set **explicitly**, with `CFBundleExecutable` set to match. Tauri v2
  generates its own `Info.plist` and merges the hand-written one; pinning the name on both sides
  removes the guesswork. Confirm against a real built bundle rather than trusting the docs.
- Artifacts become `SelahCue_0.1.0_x64-setup.exe` and `SelahCue_0.1.0_universal.dmg`.
- Docs: `docs/ops/WINDOWS-INSTALLER.md` references to "SelahCue Operator".

**Not renamed:** the output windows keep `"SelahCue Output"` and `"SelahCue Stage / Confidence"` —
those name roles, not the application.

**Migration note:** on Windows this changes the install directory and Start-menu entry, so the new
build installs *alongside* an existing "SelahCue Operator" rather than upgrading it. Uninstall the
old one first. Worth a line in the ops doc.

### 2. macOS bundle configuration

- `bundle.targets` becomes per-platform so Windows keeps `nsis` and macOS gets `dmg`.
- Sidecar: build `selahcue-output` for both arches, `lipo -create` them, and stage the result as
  `binaries/selahcue-output-universal-apple-darwin` (Tauri resolves sidecars by target triple).
- NDI: `bundle.macOS.frameworks` → lands `libndi.dylib` in `Contents/Frameworks/` and gets it signed
  as part of the bundle. Preferred over `bundle.resources`, which would put a dylib in
  `Contents/Resources/` — signable, but against convention and riskier through notarization.
- `bundle.macOS.entitlements` → a plist carrying `com.apple.security.device.audio-input`.

### 3. NDI delivery via Git LFS

The 28 MB dylib is far too large to pass as a CI secret, and is not publicly self-provisionable the
way the Windows runtime redistributable is (the Apple SDK is the licence-gated one that returned HTTP 403 during the
Windows work). So:

- Re-add `.gitattributes` with an LFS rule for `vendor/ndi/macos/lib/*.dylib`. **This reverses the
  LFS removal** made in the Windows revision note — a deliberate, recorded change of course.
- Un-ignore `vendor/ndi/macos/` in `vendor/ndi/.gitignore` (headers + lib), mirroring `windows/`.
- Same redistribution posture as the Windows DLL: ship unmodified, do not rename, carry the
  attribution "NDI® is a registered trademark of Vizrt NDI AB".

### 4. Signing and notarization

Tauri v2 performs codesign, `notarytool` submission, and stapling natively when these env vars are
present — no bespoke scripting:

| Secret | What it is |
|--------|-----------|
| `APPLE_CERTIFICATE` | Developer ID Application `.p12`, base64-encoded |
| `APPLE_CERTIFICATE_PASSWORD` | Password for that `.p12` |
| `APPLE_SIGNING_IDENTITY` | e.g. `Developer ID Application: Name (TEAMID)` |
| `APPLE_ID` | Apple account email |
| `APPLE_PASSWORD` | **App-specific** password, not the account password |
| `APPLE_TEAM_ID` | 10-character team identifier |

Notarization requires the hardened runtime, which is why the entitlements file in §2 is mandatory
rather than optional: without `com.apple.security.device.audio-input`, notarization still succeeds
but the microphone fails at runtime and STT silently stops working.

**Ordering constraint:** anything that modifies a Mach-O invalidates its signature. The rpath fix
(R1) is a *link-time* flag precisely so it lands before signing; no post-build binary edits.

### 5. The workflow

`.github/workflows/macos-installer.yml`, `workflow_dispatch` only, `macos-latest`, mirroring
`windows-installer.yml`:

1. Checkout **with LFS** (`lfs: true` — otherwise `libndi.dylib` is a pointer file and the link fails).
2. Rust toolchain + both Apple targets; cache.
3. Build `selahcue-output --features ndi` for each arch with the rpath link-arg; `lipo -create`.
4. Stage the fat sidecar under `binaries/`.
5. `cargo tauri build --features stt --target universal-apple-darwin`, with the Apple secrets in env.
6. Verify the result (see Testing) and upload the DMG artifact.

## Error handling and honest degradation

The app's existing posture is preserved: NDI *setup* (name/enable, persisted and surfaced) works in
every build; only transmission needs the feature and the runtime. The output window already prints
an honest note when NDI is configured but not compiled in.

The new failure mode this design introduces is R1 — a bundled app whose sidecar cannot resolve
`libndi.dylib`. That failure is invisible: the sidecar is a GUI-subsystem binary, so dyld's error
goes nowhere, the endpoint file is never written, and the operator falls back to the demo backend
after its ~10s wait. The symptom would be **identical to the bug just fixed in `c070df6`** — console
opens, no output windows, "No display assigned". This is the single most important thing to verify.

## Risks

| # | Risk | Mitigation |
|---|------|-----------|
| **R1** | **Confirmed:** the NDI-linked binary has no `LC_RPATH`, so a bundled `.app` cannot find `libndi.dylib` | Build the sidecar with `-C link-arg=-Wl,-rpath,@executable_path/../Frameworks`. Verify with `otool -l` on the binary **inside the built `.app`**, and by launching the `.app` with no `DYLD_*` env set |
| **R2** | Spawned sidecar has no bundle of its own, so macOS may give it a different activation policy — windows might not come to front | Verify by building the `.app` locally on the owner's Mac and launching it. If it misbehaves, the fix is an `LSUIElement`-style policy or a minimal nested bundle — decide with evidence |
| **R3** | Tauri may not sign the nested sidecar, failing notarization | Inspect with `codesign -dv --deep-verify` and `spctl -a -vvv` on the built app before shipping; sign explicitly if needed |
| **R4** | `productName` change may rename the main binary and desync `CFBundleExecutable` | `mainBinaryName` is pinned explicitly (§1); confirm against a real bundle |
| **R5** | Universal build roughly doubles build time; whisper.cpp is the long pole | Accepted. Job timeout raised accordingly |
| **R6** | LFS re-introduction affects every future clone/CI checkout | Only `ci.yml` and the two installer workflows check out this repo; only the macOS job needs `lfs: true`. Confirm the others still pass with a pointer file present |

## Testing

CI cannot verify the thing that matters most — there is no GPU, no monitor, and no interactive
session on a runner — so verification is split deliberately:

**Automated, in the workflow (fail the build):**
- `lipo -info` on the sidecar and main binary → both slices present.
- `otool -l` on the sidecar inside the `.app` → an `LC_RPATH` resolving to `Contents/Frameworks`.
- `codesign --verify --deep --strict` and `spctl -a -vvv -t install` → accepted.
- `xcrun stapler validate` on the DMG.

**Manual, on a real Mac (owner, first run):**
- Mount the DMG, drag to Applications, double-click — **no Gatekeeper prompt at all** (the point of
  notarizing).
- **Audience and Stage windows open by themselves**, and the Screens page names a real monitor for
  each rather than "No display assigned" — the R1/R2 acceptance test.
- Quitting the console closes both output windows; no orphan `selahcue-output` in Activity Monitor.
- NDI source appears on an NDI receiver on the LAN.
- "Start listening" prompts for microphone access and transcribes — proves the entitlement.
- Ideally once on an Intel Mac, since that is the only thing Universal buys.

**Unaffected and must stay green:** `make ci`, `ci.yml`. No workspace crate changes are in scope.

## Out of scope

- Auto-update / Sparkle.
- App Store distribution (a different signing identity and sandbox entirely).
- Linux packaging.
- Any change to app behaviour, the LAN wire protocol, or the operator UI beyond the window title.
