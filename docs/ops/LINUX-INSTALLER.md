# Ubuntu installer candidate

Source bootstrap: https://app.clickup.com/t/90131572460/17tnw2bbjg0 (same PR325/legacy published branch; no duplicate implementation). Actual package/runtime acceptance: https://app.clickup.com/t/86ak0qn4j; independent clean-location validation: https://app.clickup.com/t/90131572460/17tnw2bbhxr. The prospective source-only split preserves original mandatory C-004 as BLOCKED/NOT RUN in its original goal; source merge is not native installer acceptance. The first target is Ubuntu 24.04 x86_64 GNU, packaged as `.deb`. This path builds the real winit/wgpu audience-output executable with default encryption and no NDI feature. The operator retains its default encrypted-transcript support and enables local STT. Speech models are not downloaded or bundled by this workflow; model provisioning and actual microphone transcription still need device testing.

## Build and inspect

On native Ubuntu 24.04 x86_64 with the pinned Rust toolchain, native dependencies and pinned Tauri CLI from `.github/workflows/linux-installer.yml`:

```sh
python3 scripts/build_linux_installer.py --inspect-config
python3 scripts/test_linux_installer.py
python3 scripts/build_linux_installer.py
```

Use a fresh checkout/target and empty `dist/linux`; the builder refuses old package/output files. `tauri.linux.conf.json` replaces the Windows resource map with an empty **array** and selects only Debian packaging. An empty object would merge the Windows DLL back in. Windows retains its base NSIS configuration and DLL. The P06 raw-base preflight is a historical inventory tool; `--inspect-config` is the effective Linux configuration check.

The builder removes ordinary provider keys, developer loader overrides and Cargo profile/feature configuration overrides from its subprocess environment. It builds `selahcue-desktop` in release mode with default features and stages the executable identified by Cargo JSON, rather than selecting an arbitrary target-directory file. It rejects debug assertions, missing/undersized/non-x86_64 ELF sidecars, ambiguous Debian outputs and mismatched installed sidecar hashes. It requires the real operator and output in `/usr/bin`, checks `readelf`/`ldd` for missing libraries, NDI and development-tree paths, and applies the unchanged installer marker scanner to both **uncompressed** executables plus the Debian archive. Existing scanner positive controls remain intact. This checks ordinary-release markers; it is not authorization for a pilot-key scanner exception.

`dist/linux` contains one candidate `.deb`, `SHA256SUMS` and `release-metadata.json` with source SHA, package identity/version, size/hash, dependency inspection and workflow provenance when available. Metadata explicitly records no embedded pilot credentials, no public-download readiness and no runtime validation by the build script. There is no signing, bucket upload or marketing publication in this increment. Existing CI artifact upload retains the private candidate for seven days, including on a later smoke failure; download availability does not imply smoke success.

## Manual CI and installed checks

The Linux installer has only `workflow_dispatch`; **both jobs** require event `workflow_dispatch` and exact ref `refs/heads/main`, before runner work. Checkout uses the dispatch SHA. Packaging is never triggered by push, PR, release, tag or schedule. After the reviewed workflow is merged, the remaining native validation step is:

```sh
gh workflow run linux-installer.yml --ref main
```

This command is documented, not executed by this change. Record the selected main SHA and resulting run URL before treating any package as tested. Normal automatic CI runs only inexpensive Python packaging controls; it does not build installers.

The second job uses a fresh hosted Ubuntu runner, verifies the checksum and installs the `.deb` with apt. Debian runtime additions cover ALSA, Vulkan, DBus, X11/Wayland keyboard/window dependencies and fonts; Tauri adds its WebKit/GTK runtime requirements. The job does not install application build dependencies, but hosted runners can contain preinstalled development tools: this is not minimal-runtime-machine proof.

An installed `/usr/bin/selahcue-output --smoke` under Xvfb/software Vulkan must present a real frame and exit. The installed operator then runs through Tauri WebDriver. `scripts/smoke_linux_install.py` requires its actual `host_connected` IPC command to return literal `true`; a visible operator shell or demo fallback cannot pass. Temporary private XDG state and a public test passphrase isolate the encrypted fixture store. No provider keys are needed. Raw driver/app logs remain temporary and are not uploaded. The job uninstalls the application afterward.

WebDriver teardown kills its process group for test cleanup. This does **not** prove normal-close/no-orphan lifecycle behavior. Physical displays/audio, Wayland, an OS-keychain first run without the test passphrase, minimal-runtime clean install, local STT model loading and normal-close behavior still require separate device evidence. `ldd`/`readelf` do not prove every dynamically loaded graphics/audio dependency.

## Evidence recorded for this increment

On 2026-10-31, fourteen Python regressions passed on Darwin/arm64 and in an official Ubuntu 24.04 amd64 container emulated on that host. Ubuntu apt resolved the nine declared additional runtime dependencies and WebKit WebDriver. The pinned `tauri-utils` 2.10.1 parser also deserialized and merged both platform configurations: Linux Debian/no Windows resources and Windows NSIS/DLL retained. These checks do not build or execute either installed Linux binary.

Workflow admission/cost guards, actionlint, the unchanged scanner self-tests and the P06 regressions pass locally. No native `.deb`, installed-app IPC/frame evidence or manual packaging run exists yet. Actual main-workflow build/install evidence and runtime acceptance reviews remain mandatory under the original installer goal; that ticket stays in progress. The source-bootstrap goal separately requires normal CI and four fresh independent reviews before merge. Neither predicate waives the other.

## Recovery and release boundary

A failed build, marker hit, unresolved dependency or false IPC assertion stops acceptance. Do not replace the real sidecar with a placeholder, disable encryption, add NDI or point a development loader path at missing libraries to obtain green results. Fix and rerun the same controls. Reverting the Linux overlay/workflow/scripts removes this path without changing Windows packaging. Debian removal retains user data; the isolated test state is temporary. Pilot provider proof/profile/scanner, signing and public distribution have separate delivery gates.
