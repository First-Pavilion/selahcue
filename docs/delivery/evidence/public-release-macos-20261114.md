# Universal macOS packaging baseline, 2026-11-14

Both images use local Whisper STT and NDI. Tauri ad-hoc signs the app and its nested code. The DMG is unsigned and unnotarized under the owner’s waiver. Cloud acceptance is tracked separately.

## Build inputs

- Host was Apple Silicon running macOS 26.3 (25D125) with Xcode 26.6 (17F113) and SDK 26.5.
- Rust 1.98.0 with `aarch64-apple-darwin` and `x86_64-apple-darwin`. Build jobs were limited to one.
- Tauri CLI 2.12.4, distributed as `cargo-tauri-aarch64-apple-darwin.zip` under tag `tauri-cli-v2.12.4`. Archive SHA-256 `f71a34ada728ca2d1a51c28d6d21639e1e080898ec69ec8d49c5da3b7e8bc1be`.
- The locally staged NDI SDK supplies `Processing.NDI.Lib.h` and the universal `libndi.dylib` under `implementation/desktop/vendor/ndi/macos`. The input dylib SHA-256 is `b38d6b35712cef45ebf08838355a1185a80b9d45c4f72bf7494c51e846367689`. Its two slices advertise macOS 13.0 and install name `@rpath/libndi.dylib`. NDI® is a registered trademark of Vizrt NDI AB.
- Output compiled with `ndi` and default `encryption`. Operator compiled with `stt`, default `read-encrypted-transcripts`, and Tauri's production `custom-protocol`. `dev-keys`, `openai-notes`, `cloud-stt`, `pilot-credentials`, and `cloud-live` were absent from the selected operator features.

The sidecar build started at `3ae74484bb72d3be77ba842b7aa4734bc7968f28`. The operator build started at `1059e697b9fb185401a043c760e52476e0339e77`. The intervening commit changed only marketing diagnostics, tests and evidence. The uncommitted build inputs for the operator were the tracked macOS plist patch (SHA-256 `e3ed133e945cc0482f1a4c39a0b34f7a9a2a099c46d681110c6b5dca9a5bb909`) and the new macOS overlay patch (SHA-256 `b4890c839020c584241e4e4d85db83fd6ea1fc3a49cd079cd08b937fbfa315a7`). Exact patches and receipt SHAs are in the scratch directory below.

## Original build

The first build used the Tauri command below from the operator crate, after compiling and staging the output for both architectures. The wrapper in the next section uses the same source configuration, validates the Cargo artifact receipts and checks the compiler flags before packaging.

```bash
cargo build --release --locked -p selahcue-desktop --bin selahcue-output --features ndi \
  --target aarch64-apple-darwin --message-format=json-render-diagnostics
# Repeat with --target x86_64-apple-darwin and combine the two reported outputs with lipo.
cargo-tauri tauri build --target universal-apple-darwin --bundles dmg --features stt --ci -- --locked
```

Builds run with a clean environment, `CARGO_BUILD_JOBS=1`, `MACOSX_DEPLOYMENT_TARGET=13.0`, the staged `NDI_SDK_DIR` and the link flag `-C link-arg=-Wl,-rpath,@executable_path/../Frameworks`. The per-architecture siblings are inputs to the two Cargo build scripts. Tauri packages the universal sibling. The macOS overlay replaces the Windows DLL resource with the font notices, places the NDI dylib in `Contents/Frameworks` and selects ad-hoc app signing. The source `Info.plist` sets macOS 13.0 because Tauri merges existing plist values over its generated keys. It retains the microphone usage description.

## Portable Whisper build

The original baseline used the build dependency's default CPU settings. Its ARM CMake cache had `GGML_NATIVE=ON` and the generated C and C++ flags included `-mcpu=native+dotprod+i8mm+nosve+sme`. The Intel cross-build cache had `GGML_NATIVE=OFF`. A universal app contains both Mach-O slices, but these ARM flags can select instructions beyond older Apple Silicon CPUs. Keep the original baseline local to this investigation.

In an isolated checkout, install the pinned Rust toolchain and both targets, provide the pinned Tauri CLI and stage the NDI SDK with `scripts/fetch_ndi_sdk.sh`. Use the wrapper for the portable local-STT baseline. It starts with a new Cargo target directory (the locked `whisper-rs-sys` build script does not declare the `GGML_*` variables as Cargo rebuild triggers), sets `GGML_NATIVE`, `GGML_SSE42`, `GGML_AVX`, `GGML_AVX2`, `GGML_BMI2`, `GGML_FMA` and `GGML_F16C` to `OFF`, and uses Tauri in two steps. It compiles the universal operator with `--no-bundle`, then checks both generated CMake caches and CPU flags before invoking `tauri bundle`.

```bash
python3 scripts/build_macos_installer.py \
  --tauri /path/to/cargo-tauri \
  --output /path/to/new/macos-portable
```

Seven focused tests exercise the clean environment, the just-built Cargo artifact requirement, the CPU flag guards and existing output rejection. The portable settings were also configured against the actual pinned Whisper source for both architectures as an independent preflight. The guard rejected the original ARM baseline's real CMake cache.

The portable build started at `1059e697b9fb185401a043c760e52476e0339e77` with the same macOS plist and overlay patches recorded above. The invoked wrapper’s SHA-256 was `d95b173872d48e93f9bc854131d39656fe233a453454a7ad572067946d01de3b`. Subsequent committed changes before the Mac packaging commit did not modify the desktop inputs.

## Inspect the exact DMG

Use `hdiutil verify` and `hdiutil attach -readonly -nobrowse -mountpoint "$mountpoint" "$dmg"`. On the actual mounted app, verify the bundle plist with `plutil`. Verify both slices with `lipo -archs` and the minimum OS and loader paths with `vtool -show-build` and `otool -L/-l`, passing `-arch` for each slice. Run `codesign --verify --all-architectures --deep --strict` on the app. Hash the mounted files and the image with `shasum -a 256`.

Run `python3 scripts/installer_secret_scan.py --self-test`. To scan the exact mounted files, call `installer_secret_scan.run_scan` on the operator, output, NDI runtime and DMG using the existing `SIGNATURES` and `MIN_ARTEFACT_BYTES`. The scanner checks the binaries uncompressed and exercises its positive control on each file.

Run `selahcue-output --smoke` directly from the mounted image, with a wall limit of 45 seconds and scratch-only `HOME`, `TMPDIR` and `XDG_RUNTIME_DIR`. Use a one-use passphrase for the scratch store so it bypasses the real Keychain. Supply no DYLD or NDI loader overrides. Exit 0 and the first-frame log marker are required. A separate `arch -x86_64 selahcue-output --help` checks Intel loader resolution under Rosetta.

The first image’s installed operator was also exercised in a separate native right-click check.

## Observed results

Both package runs completed. Their exact images passed `hdiutil verify`, mounted read-only, and detached successfully. Each mounted app has an Applications shortcut, bundle ID `com.selahcue.operator`, executable `selahcue-operator`, a microphone usage description and a macOS 13.0 minimum. The operator, output and NDI library have both Mach-O slices, each declaring 13.0. The output links `@rpath/libndi.dylib` and resolves it through `@executable_path/../Frameworks` in both slices. The matched code-section hashes confirm signing preserved the staged output and NDI executable code. The original NDI library name, both font notices and the ad-hoc signatures were verified. The Windows DLL was absent. Deep strict signature verification passed for both mounted apps and their matching scratch-installed copies.

The portable wrapper recorded `GGML_NATIVE=OFF` and the six optional x86 flags off in the actual ARM and Intel CMake caches. The generated C and C++ flags each selected the exact expected architecture and macOS 13.0, without host-specific CPU options. The original run’s ARM cache failed that guard as expected.

The scanner self-test passed 47 cases. Each DMG and its three uncompressed binaries passed with zero forbidden signatures and 18/18 positive-control signature/encoding pairs per target. On the portable image the mounted ARM output exited 0 in 2.670 seconds and reported a first frame after 1.053 seconds from app initialization. The original image exited 0 in 3.944 seconds and reported 2.207 seconds to the first frame. Both mounted Intel outputs loaded and printed their help under Rosetta.

| Exact payload | Original SHA-256 | Portable SHA-256 |
| --- | --- | --- |
| DMG | `0a1ddf2e0ef138e7b447d65f4a7be596fa5ccb3f6fcd7a957c7f4001690e46c6` | `8eac452e41225cc20c93fc3b2c10d8bd8d307ecab6acb8a6ccccfc38569fab1e` |
| Operator | `29d8b8de26c049b7344ed38e0084b5ae8cae450239846aaa943d8adae8c232a7` | `8c4a2176d102e5f46d1bb220c9b528cf5a60ef138536de9e14a3fe252489ad92` |
| Output | `3ed863ee11793dd3de41faa27b123fc8a3d363dd18234b6fa34b64eeb06365db` | `2a091ea2b2437f834d9ae3350f916291b350ead1834a6b2ea2d764deb9d6c03a` |
| NDI runtime | `5220ae8032cd31feaad97ddf7786075d4fc1c5d9e73b947d7824e7c09c702ffb` | `5220ae8032cd31feaad97ddf7786075d4fc1c5d9e73b947d7824e7c09c702ffb` |
| Bundle plist | `071e09332f005221853e0fe35f457be8e22f8e26370aed24b0ee86d162aeda24` | `071e09332f005221853e0fe35f457be8e22f8e26370aed24b0ee86d162aeda24` |
| Font OFL license | `0dab92d0544f7b233403f14b84a663bdbfa746982eda629e7f4f9ffe1b036feb` | `0dab92d0544f7b233403f14b84a663bdbfa746982eda629e7f4f9ffe1b036feb` |
| Font README | `3b025dac35402448ec660c05378a8d4c4342741047566d7a69605d514686edd1` | `3b025dac35402448ec660c05378a8d4c4342741047566d7a69605d514686edd1` |

The original DMG is 72,791,134 bytes. The portable DMG is 72,791,095 bytes. Local artifacts, build stdout/stderr, exact compiler flags, source diffs and mounted-payload receipts are under `/private/tmp/selahcue-public-release-20261114/macos-baseline/` and `/private/tmp/selahcue-public-release-20261114/macos-portable/`.

Physical Intel and early Apple Silicon first transcription, microphone permission behavior, external display and NDI receiver acceptance, Gatekeeper behavior for a downloaded image and the final cloud-feature profile remain unverified here.
