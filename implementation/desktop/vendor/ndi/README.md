# Vendored NDI SDK

SelahCue's optional **NDI output** (Screens page → "NDI OUTPUT") broadcasts a composed audience
feed as an NDI source. It is compiled only under `--features ndi` on `selahcue-desktop`, via the
[`grafton-ndi`](https://crates.io/crates/grafton-ndi) crate, which at **build time** needs the NDI
SDK **headers + import library** and at **run time** needs the NDI runtime (`libndi`).

To keep the build **self-contained** — no reliance on a system-installed SDK or another app's copy
— the SDK lives here, and the build points `grafton-ndi` at it with the `NDI_SDK_DIR` environment
variable. The `make output-ndi` / `make launch-ndi` targets set `NDI_SDK_DIR` to this directory
automatically (see the root `Makefile` and `make ndi-preflight`).

## Layout (what the build expects)

Per OS, `grafton-ndi`'s `build.rs` looks under `NDI_SDK_DIR` for `include/Processing.NDI.Lib.h`
and a platform library:

```
implementation/desktop/vendor/ndi/
  macos/    include/Processing.NDI.Lib.h (+ the other Processing.NDI.*.h)   lib/libndi.dylib
  linux/    include/Processing.NDI.Lib.h                                    lib/x86_64-linux-gnu/libndi.so
  windows/  include/Processing.NDI.Lib.h                                    lib/x64/Processing.NDI.Lib.x64.lib (+ .dll)
```

## Populating it

The SDK binaries are **not committed** by default (see `.gitignore` here) — they are large (~30 MB
per platform) and carry the NDI SDK licence. Populate them from the official SDK with:

```
scripts/fetch_ndi_sdk.sh            # copies from an installed NDI SDK, or a path you pass
scripts/fetch_ndi_sdk.sh /path/to/NDI\ SDK\ for\ macOS
```

Then build/run with NDI on:

```
make ndi-preflight                  # verifies this dir is populated for your OS
make output-ndi                     # output window with NDI transmission (or: make launch-ndi)
```

## Two decisions that are NOT mine to make (flagged for the owner)

1. **Commit the binaries, or fetch them?** Committing gives a truly offline, self-contained
   checkout but adds ~30 MB/platform to git (use **Git LFS** if so). Fetch-on-setup keeps the repo
   lean. Default here is fetch (`.gitignore` excludes the payload); switch to LFS-committed if the
   team wants zero-setup builds.
2. **NDI redistribution licence.** Bundling and shipping the NDI runtime is governed by the **NDI
   SDK License Agreement** (attribution "NDI® is a registered trademark of Vizrt NDI AB"; you must
   not rename the library; redistribution terms apply). Product/legal must approve bundling the
   runtime in a released SelahCue build.

## Packaging into a shipped app (follow-up, owned by the release pipeline)

For a distributed build, the runtime (`libndi.dylib` / `libndi.so` / `Processing.NDI.Lib.x64.dll`)
must travel **inside** the app bundle and be found at run time:

- **macOS (.app):** copy `libndi.dylib` into `Contents/Frameworks/` and add an `@executable_path/
  ../Frameworks` rpath (the dylib's install name is `@rpath/libndi.dylib`).
- **Windows:** ship `Processing.NDI.Lib.x64.dll` next to the `.exe`.
- **Linux:** ship `libndi.so` and set an `$ORIGIN` rpath.

For local dev, `make output-ndi` sets the loader path to this `vendor/ndi/<os>/lib` directory so the
runtime is found without a system install.
