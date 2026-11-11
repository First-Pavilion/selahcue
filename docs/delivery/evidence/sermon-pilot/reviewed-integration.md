# Reviewed desktop pilot integration checkpoint — 2026-11-11

Local integration source: `099415f6c819215b662799bd9d09f2ea7ed2a927`, assembled on
fresh main `7f6dbcbb4782854cbb0fea14a3bb5a9ffcf7fcd0`. This evidence is scoped to
source assembly and focused synthetic checks on macOS arm64 with Rust 1.98.0.
Independent combined review and the broader exact-head matrix remain open.

## Attributable inputs

| Unit | Reviewed source | Integration merge |
| --- | --- | --- |
| Marker/P03/P04/frame | `b129a8cf` | `c79f0a08` |
| A1 endpoint | `b04d9af5` | `9ca37316` |
| A2 licensing | `4b5dae4a` | `03eb1ed3` |
| SQLite | `8c8cd7b4` | `6892708f` |
| A3 evaluation source | `73145bad` | `bf44e618` |
| B1 storage | `a7f355d2` | `d4d0c5c8` |
| B5 cooldown | `aba0429d` | `75c7028f` |
| C4 complete notes stack | `1f555ec1` | `34b36ba0` |
| Browser and passive diagnostics | `20368c7f` | `099415f6` |

Each source is an ancestor through one explicit non-fast-forward merge. C1–C3
were retained through C4 ancestry. The marker comparison was merged onto current
main; no old main snapshot was transplanted. Other local branches were preserved.

## Combination resolutions

The start-session conflict retains both storage-request visibility and fresh
transcript/detection state. Notes conflicts retain both expiry tests, draft DOM
preservation, saved-state preflight, the captured provider route, pre/post-generation
and save-time pilot admission, and both native command registrations. Imported
PDF and notes test setup uses the existing admitted staging API with an explicit
positive synthetic admission callback. The operator lock was regenerated narrowly
at printpdf 0.12.8; only two stale dependency edges changed, with no package version,
source or checksum change. Both locks retain rusqlite 0.42.0, libsqlite3-sys 0.40.0
and SQLCipher 4.20.0; the operator retains harfrust 0.5.2 and printpdf 0.12.8 with
its optional HTML defaults disabled.

Canary correction `036c9119` separates the literal pilot Clippy command, preserves
its synthetic fixture environment and the complete expiry runtime block, retains
all eight prior canary configurations, and adds the exact required release/default-on
pilot tuple. Strict parsing and unconditional no-default refusal remain. Non-shipped
opt-ins require the exact tuple derived from actual CI; this selects no shipping
profile. The imported browser settings/budgets were retained without further change.

## Focused evidence

- Patched linked SQLite: 1 plain runtime test and 2 encrypted tests pass, including
  the old encrypted-backup fixture; queries report SQLite 3.54.1 / SQLCipher 4.20.0.
- Endpoint siblings: 42 pass, 4 child helpers ignored at top level. Synthetic
  licensing loopback: 8 pass with eight test threads. License policy probes: 14 pass.
- Cooldown/storage owning suites: 12 and 20 pass. Notes remote: 11 pass; note
  durability: 27 pass. Cloud OpenAI/pilot suites: 50 and 7 pass with `openai` enabled.
- Native notes orchestration: 30 default and 35 `openai-notes` cases pass; native
  history-generation tests: 15 pass. PDF: 16 pass, 1 author-fixture helper ignored.
  Pilot release filter: 10 pass with the synthetic fixture, including late-result,
  backend-lock expiry, route capture and local-source cutoff controls.
- Complete owning operator headless suite: actual 2,993 checks, zero assertion
  failures; its old exact-count guard first refused 2,987, then the measured 2,993
  value passes. Every parent scenario/assertion remains; no historical totals were summed.
- Canary: nine exact tuples, 25 negative drift controls, three real sentinel-shell
  outcome probes pass, including failure followed by shipped release STT. Final
  workflow structure/self-tests, minute policy and actionlint pass. The original
  expiry block is structurally identical after extraction of its single Clippy line.

Sandbox socket refusals are environmental failures, retained separately from
successful outside-sandbox synthetic-loopback reruns. An initial no-feature cloud
run executed zero tests and supplies no acceptance evidence. These focused results
are not a workspace-wide or full native matrix pass. Empty ignored local sidecar/DLL
placeholders were copied create-only for compilation and are not shipping artifacts.

## Pending gates

Task 3 combination review/regressions and Task 4 broad validation remain open,
including full feature/profile/toolchain matrices, actual floating-stable canary,
combined supply-chain checks, native Windows/Linux and engine-specific browser
runtime evidence. No inference explains the previous WebKit timeout. No accepted
recognition profile, authorized four-language corpus or Windows 10 / 4 GB tester
exists. This checkpoint proves no real-provider, device-resource, installer,
package, deployment or release acceptance. The pilot cutoff remains
`2027-04-30T23:59:59Z`, with earlier provider expiries taking precedence.

No main merge, push, PR, external status update, workflow dispatch, release,
credential/provider/congregation operation or corpus operation was performed.
