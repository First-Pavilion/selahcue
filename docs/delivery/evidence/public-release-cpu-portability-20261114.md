# Whisper CPU policy for Windows and Ubuntu installers

The Windows and Ubuntu operator installer builds now require compiler evidence for a portable x86-64 Whisper build before accepting the package. The policy applies to the installer operator build with STT. The output sidecar follows its existing build path. Windows retains NDI, whose runtime has its own SSE4.2 requirement.

The operator lockfile pins `whisper-rs-sys` 0.15.0 and `cmake` 0.1.58. The Whisper build script's environment loop forwards `GGML_*`, `CMAKE_*` and most `WHISPER_*` variables to CMake. Its source does not announce rebuild triggers for the forwarded CPU variables. In ggml's CMake source, native GCC-style builds use `-march=native`. The MSVC native branch calls `FindSIMD.cmake` and can enable an `/arch:` extension. Disabling native tuning alone can enable other x86 options through `INS_ENB`. These are source observations. No earlier Windows or Ubuntu package build supplied its actual Whisper flags.

The operator builds remove inherited Whisper, GGML, CMake and compiler tuning settings, then disable native tuning, SSE4.2, AVX, AVX2, BMI2, FMA and F16C, along with later x86 extensions and dynamic CPU variants in this locked source. Both require an empty operator target before building, so Cargo cannot reuse an earlier Whisper archive. The Windows runner no longer restores the standalone operator target. It uses Ninja within its existing x64 MSVC shell so CMake emits per-source compile options. Ubuntu uses Unix Makefiles, requires `-march=x86-64`, and builds under `.target/portable-linux`.

The verifier requires one release CMake cache, the expected CPU policy, all 24 locked translation units, and four static Whisper/GGML archives. It checks every command in the database, including the compiler, compile-only switch, source binding and ISA options. It rejects opaque response files. The Windows gate verifies direct x64 MSVC invocations and rejects explicit ISA raises. Release metadata includes the baseline, settings, command count and hashes of the CMake cache, compiler database, libraries and exact installer. Raw compiler commands, cache contents and environment values are excluded from metadata. The Windows release feature parity check, existing developer-key scanner and dispatch-on-main rule still apply.

| Local verification | Result |
| --- | --- |
| `python3 -B scripts/test_whisper_cpu_policy.py` | 6 passed using synthetic GCC and MSVC compiler records. Covers inherited overrides, stale targets, unsafe flags and defines, missing or contradictory evidence, and exact installer binding |
| `python3 -B scripts/test_linux_installer.py` | 20 passed, including the shared policy controls |
| `actionlint .github/workflows/windows-installer.yml .github/workflows/linux-installer.yml` | Passed |
| `python3 -B scripts/check_installer_features.py --self-test` and `python3 -B scripts/check_installer_features.py` | 12 controls and exact feature parity passed |
| `python3 -B scripts/installer_secret_scan.py --self-test` | 47 passed |
| CMake 4.4.2 configuration of the actual locked Whisper source on macOS | Generated 24 x86 translation units and verified all pinned CPU settings. All generated commands contained `-march=x86-64`. The option parser was also exercised after removing the Apple-specific `-arch x86_64` argument for this probe |

The Windows MSVC and Ubuntu GCC package receipts are still pending their first approved hosted installer builds. Public STT acceptance also requires installing each candidate on a CPU or VM that exposes the declared platform minimum, loading a supported local Whisper model, and transcribing a fixed speech fixture. The installed output/IPC smoke exercises a separate path.
