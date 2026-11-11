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

## Windows-only private pilot publication

This policy supports a reviewed Windows-only manifest; it does not publish an installer or
complete the pending pilot packaging, provider, signing or Windows installation gates above.
When those gates have evidence and a publication is authorized:

1. Use only the verified installer and source metadata from the authorized manual **main** run
   above. Record its pinned source SHA, run ID/attempt, version, exact bytes, size and SHA256;
   verify the package, credential expiry and approved Windows signing state independently.
   Do not automatically rebuild a package during publication. A state string or metadata/hash
   file alone does not prove a package signature or provider rights.
2. Promote those exact bytes to approved **private**, immutable, content-addressed storage at
   `pilot/<release_id>/<sha256>/<filename>`. Verify stored bytes/checksum, anonymous-read refusal,
   exact-object access and bounded signed GET expiry with the actual provider. Never use a
   public bucket. P10 owns real signer/private-read evidence; no production signer exists yet.
3. Build the server manifest using the strict contract in
   [pilot-download-grants.md](../release/pilot-download-grants.md), with exactly one verified,
   available Windows x86_64 artifact, its approved signing state and actual credential/provider
   upper bound. Manifest and credential expiry must be in the future and no later than
   **2027-04-30T23:59:59Z**; do not restart a six-month window at build or download.
4. Configure server-only `SELAHCUE_PILOT_GRANT_REQUIRED_PLATFORMS=Windows` and
   `SELAHCUE_PILOT_GRANT_SIGNING_REQUIREMENTS={"Windows":"authenticode_verified"}` only after
   that signing claim is verified. An unsigned pilot requires separate explicit approval and
   the exact `unsigned_pilot_approved` state in both policy and manifest; there is no unsigned
   default. Pin the promoted local manifest path and independently verified digest together.
   Omitted platform configuration still requires Windows, Ubuntu and macOS; blank, duplicate,
   unknown and other partial sets refuse. Signing keys must exactly match the declared set.
5. Preserve the protected registration Sheet/ledger and server-side receipt flow. Require a
   confirmed, unexpired Windows registration receipt before granting the fixed Windows artifact;
   preserve checksum, expiry, exact private URL and access checks in the existing registration
   workflow. Payloads, receipts and public metadata cannot select manifest/signing policy.
   Keep public marketing downloads disabled until separately authorized; Ubuntu/macOS and other
   unavailable architecture choices must remain unavailable in a Windows-only projection.
6. For rollback, disable new grants if needed, then select a previously approved, unrevoked,
   still-unexpired snapshot with its matching digest, exact platform policy and signing policy.
   Do not revive expired packages/credentials, mutate stored artifact keys, or change registration
   rows/counters. Already issued URLs remain subject to their provider expiry.

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
