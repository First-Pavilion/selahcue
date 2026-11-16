# Ubuntu installer prerequisite evidence

Ticket: [P06 — Ubuntu packaging prerequisites](https://app.clickup.com/t/17tnw2bbhxg).
This is prerequisite discovery and an executable check, not a shipped Linux installer.
The packaging implementation remains [86ak0qn4j](https://app.clickup.com/t/86ak0qn4j).

## Proposed first-target matrix

| Candidate | Status | Evidence still required |
|---|---|---|
| Ubuntu 24.04, x86_64 GNU, `.deb` | Engineering candidate; not yet build/install-validated | Native build, dependency closure, install/launch/uninstall on a clean machine |
| Ubuntu 22.04 or other versions | Not tested; no support claim | Separate oldest-supported-runtime/ABI decision and build proof |
| Ubuntu ARM64 | Not tested; no support claim | SDK architecture, toolchain, sidecar and runtime evidence |
| AppImage, RPM or Flatpak | Not selected | Owner format decision and independent packaging/runtime checks |

The `.deb` candidate here is a proposed engineering baseline within the requested Ubuntu pilot.
Aria can verify/refine the baseline from the evidence; no generic product approval gate is
required merely to investigate it. A broader distribution matrix still needs separate evidence. Build on the oldest supported target system, not an arbitrary
newer CI image, to avoid promising ABI compatibility that has never been tested.

## Executable inventory

```sh
python3 scripts/test_ubuntu_packaging_preflight.py
python3 scripts/ubuntu_packaging_preflight.py --root .
# On an actual Ubuntu candidate host, include tool/native dependency checks:
python3 scripts/ubuntu_packaging_preflight.py --root . --check-host
```

The default NDI choice is deliberately `undecided`, which blocks the input verdict. Use
`--ndi enabled` or `--ndi disabled` only to examine an explicitly chosen build profile; the
argument records the examined build profile; it does not silently change release features. The tool reads no provider keys, changes no configuration,
creates no fake binaries and never installs packages or starts a build. JSON diagnostics are
bounded by fixed checks. Exit `1` means unresolved inputs; exit `0` only means the inspected
inputs passed. `release_ready` is **always false** because this tool cannot prove a release.

The checker reads the current `tauri.conf.json`; it does not pretend to implement Tauri's
configuration-merging semantics. When platform overrides land, the packaging implementation
must inspect the actual effective config used by its bundler, not assume this source-file
inventory covers it automatically.

### Verified clean-checkout blockers

- `bundle.targets` selects only `nsis`. A Linux-effective configuration must select `.deb`.
- The shared resources map requires `Processing.NDI.Lib.x64.dll`. Linux must not depend on or
  ship that Windows payload. Removing it globally would break Windows and is not a fix.
- The output sidecar expected by Tauri is
  `binaries/selahcue-output-x86_64-unknown-linux-gnu`. It is ignored and absent from a clean
  checkout. Existing normal CI stages empty placeholders for compilation only; the preflight
  rejects these, truncated/Windows/wrong-CPU files, and missing executable permission.
- NDI is optional in Cargo but the requested pilot feature choice is unresolved. An NDI-enabled
  Ubuntu package additionally needs the approved Linux SDK header and x86_64 `libndi.so`,
  redistribution permission, a verified shipped resource location and an `$ORIGIN` loader
  path. `make output-ndi` uses a development `LD_LIBRARY_PATH`; it does not establish packaged
  runtime closure. The existing Linux ticket excludes NDI bundling, so reconcile that scope
  explicitly before enabling it.

Checking an ELF header is only a rejection filter. It is not a complete ELF validator and
never replaces `readelf`/`ldd`, real startup or clean installation evidence.

## Native dependency inventory

The existing `operator`/`operator-native` Linux CI jobs declare WebKitGTK 4.1, GTK3, Ayatana
appindicator, librsvg, X11, xkbcommon and ALSA development packages. The preflight also inventories
compiler/build tooling needed for Rust/native STT, bundled OpenSSL and Debian packaging:

```
build-essential pkg-config libwebkit2gtk-4.1-dev libgtk-3-dev
libayatana-appindicator3-dev librsvg2-dev libx11-dev libxkbcommon-dev
libasound2-dev cmake libclang-dev perl patchelf
```

This is an input inventory, not a verified `.deb` runtime `Depends` list. Build-only tools must
not be confused with user-machine dependencies. After a real package build, inspect its control
metadata and ELF `DT_NEEDED`/RUNPATH entries, install it into a separate clean target and verify
both operator and audience output with no developer loader variables set. Cover the OS secret
store/session bus, microphone denial/recovery, X11/Wayland, GPU/display and NDI receivers where
enabled. Headless compile checks cannot prove these behaviors.

Primary references checked for this investigation:
[official Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) and
[official Debian packaging documentation source](https://github.com/tauri-apps/tauri-docs/blob/v2/src/content/docs/distribute/debian.mdx).
The latter separates generated package dependencies from additional native libraries. Actual
SelahCue linkage and the final package metadata still determine the complete runtime closure.

## Clean Ubuntu experiment

The local Docker server is Linux/arm64 on an Apple Silicon host. The candidate container uses
`--platform linux/amd64`, therefore **emulated**, not native x86_64 hardware. The official image
used is `ubuntu:24.04` at
`ubuntu@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852`.
The source mount is read-only and the container is removed after execution.

```sh
docker run --rm --platform linux/amd64 \
  --mount type=bind,source="$PWD",target=/src,readonly \
  ubuntu:24.04 sh -c '
    apt-get update &&
    apt-get install -y --no-install-recommends python3 &&
    cat /etc/os-release && uname -m &&
    PYTHONPYCACHEPREFIX=/tmp/pycache python3 /src/scripts/test_ubuntu_packaging_preflight.py &&
    python3 /src/scripts/ubuntu_packaging_preflight.py --root /src --check-host
  '
```

Only Python is installed by this experiment. Native development tools/libraries are intentionally
not installed: their missing status on a clean system is expected, and package availability is
queried separately with `apt-cache policy` for the inventory above. This is not a Rust compile,
GUI smoke test or built package. `python3-minimal` alone lacked the `json` standard-library
module in the first disposable container, so the reproducible command installs `python3`.

Verified experiment result (31 October 2026):

- Container reported Ubuntu 24.04.5 LTS (`VERSION_ID=24.04`) and `x86_64`; the host remains
  Apple Silicon, so this is emulated evidence.
- All 13 inventoried apt package names had a candidate in the Ubuntu repositories. Examples:
  WebKitGTK dev `2.52.6-0ubuntu0.24.04.1`, ALSA dev `1.2.11-1ubuntu0.3`, libclang dev
  `1:18.0-59~exp2`, patchelf `0.18.0-1.1build1`. These are availability observations, not pins
  or installed/linked dependencies.
- The then-current 13 regression controls passed inside Ubuntu; the final host suite adds a
  fourteenth positive NDI-input control and passes all 14. Input-classification logic did not
  change after the container run; the matrix-status wording was clarified to distinguish
  missing validation from a product approval gate.
- Actual source inspection exited `1` with the NSIS/Windows-DLL/missing-sidecar/unresolved-NDI
  blockers described above. Host check correctly identified the Ubuntu/x86_64 candidate and
  missing Cargo/Rust/pkg-config/compiler/cmake/clang and native pkg-config prerequisites.
  The basic image supplied Perl and `dpkg-deb`; that alone is insufficient for packaging.
- No installer was built or launched. No full native dependency installation was attempted.
  Raw local evidence is `/private/tmp/otto-ubuntu24-amd64-preflight.log`; the commands and
  exact image digest above reproduce the bounded experiment.

## Implementation handoff and gates

1. Verify/refine the proposed Ubuntu24.04 x86_64/deb baseline with Aria and record whether
   the examined build profile includes NDI. Do not turn a reasonable technical default into
   a generic user-approval gate.
2. In the existing packaging ticket, introduce platform-effective Tauri configuration that
   preserves Windows resources while staging the real Linux sidecar. If NDI is enabled, prove
   its redistribution, native resource and loader closure before publishing.
3. Build the candidate on its validated Linux base and record toolchain, exact source SHA,
   package metadata, ELF dependencies and install/launch/uninstall evidence.
4. Only then add/enable the Ubuntu packaging workflow, with the same manual
   `workflow_dispatch` **and** `refs/heads/main` admission guard used by Windows. Refuse other
   events/branches/tags before credentials, build or upload; do not add automatic paid CI legs.
5. Pilot credential expiry/profile/scanning and private-bucket/registration contracts remain
   separate prerequisites. No ordinary local developer keys may be embedded or exposed by
   this investigation. No real installer, provider credential or SDK payload was published.
