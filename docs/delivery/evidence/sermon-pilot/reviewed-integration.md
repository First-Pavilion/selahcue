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


## Separately attributed marketing job budget

Task 3 applies the approved 20→25 minute marketing timeout, based on exact source20368c7f / CI43085580106 / job130749079236: all22 steps and browser/CSP assertions succeeded, but the job was cancelled at1,201s with the explicit20m0s timeout annotation. Required work finished at1,196s; Node post was a cache hit/rounded0s. No cache stall or historical WebKit cause is established. The bounded change adds at most five Linux runner-minutes and no deliberate routine work, retaining every assertion, cache, step and other budget. Current integrated-head hosted success remains unproven until root's reviewed combined publication. See browser-ci.md and Task3 report for exact semantic-diff/policy evidence and separate Flutter/audit observations.


## Final grouped required-gate fixes

The final review/Task4 pass at957cbda0 found two required-gate failures. SHADOW-INTEGRATION-01 is addressed by making only `source_root` resolution strict, preserving its operation-local OSError/RuntimeError refusal, fixed `source-root-refused` code and suppressed private diagnostic context. Real loop/missing/broken paths refuse; a real existing module resolves to this repository and validates its committed public development inventory. CPython3.14.5 and3.12.13 each pass17 provenance tests,34 scanner tests and47 unchanged ordinary-deny controls. The original15-test/one-failure receipt and the new failing-before-fix controls remain preserved.

The required Rust1.98 release pilot/cloud all-target Clippy gate is addressed with12 descriptive `expect` assertions confined to the stopped-store combination test and two equivalent PCM array repeats confined to the capture-cadence test. Imports, barriers, PCM values/lengths, timeouts and assertions remain. Exact release/pilot/cloud all-target Clippy passes with `-D warnings`; both affected named native tests pass individually. No lint allowance, lock/workflow/browser/renderer or application-runtime behavior changed.

Detailed commands, RED/GREEN receipts, scanner before/after hashes and final source binding are in the local `final-fix-report.md` and `final-fix-*` artifacts under `.superpowers/sdd/2026-11-11-sermon-pilot-reviewed-integration/`. Four independent scoped re-reviews and the remaining Task4 validation are still required. These focused corrections establish no full-matrix, hosted, device/resource, real-provider/profile, corpus, package or release acceptance.

## HTTP deadline diagnostic checkpoint — 2026-11-12

Verified main `97699bc1b75ade6fc37ed5236f33df1b550a3e8d` was merged normally
into the reviewed integration as `77ffbee67b35dd2693e153cbde741adb4dc8ca45`,
with prior integration `3ecb46be714453fcc0fcc840ff2f5427d0d6a0d9` as first
parent. All fourteen incoming main paths were disjoint from cloud/core.

The original PR394 Linux workspace failure remains unresolved: the endpoint EOF
receipt timed out, while its later separate HTTP invocation passed. A local
baseline passed once after a separately retained sandbox bind refusal. Test-only
receipts now distinguish listener setup, admission/client construction, request
entry/return, complete bounded synthetic authenticated request, response write,
actual EOF and receipt/join. Accept/read/write cleanup is bounded and the server
is joined on assertion failures. Cleanup and pre-dispatch refusal cannot count as
in-flight cancellation. The original 120 ms admission, 60 ms response delay,
500 ms receipt watchdog and `<620 ms` actual-EOF assertion remain unchanged;
client construction still consumes the same admission. The accepted-request
forward-clock-jump control retains its original 500 ms read bound, and the
20/30 ms expired-dispatch control is retained.

On macOS arm64/Rust 1.98.0 with locked offline dependencies, one fixed diagnostic
pair passed: exact case **1/0**, then owning HTTP binary with three test threads
**4/0**. The new forced-setup-expiry case refused with no accepted socket or bytes
through the observer window. A disposable authenticated raw client held open past
the original 500 ms watchdog produced the expected no-EOF failure; EOF appeared
only after explicitly dropping that client, and cleanup joined. Removing the
forced setup delay also made its refusal assertion fail on an actual accepted
request. Both mutations were removed. Self-review retained explicit error-phase
receipts and the original forward-jump bound; final owning verification **4/0**,
workspace format and affected cloud HTTP all-target Clippy with `-D warnings`
passed. One invalid initial observer calibration exposed and corrected only the
new fixture's inherited nonblocking accepted-socket mode; it is not evidence
about the old blocking fixture or Linux cause.

No production transport/policy, dependency, CI or cancellation-design correction
is claimed. External receipts do not identify internal future-drop/shutdown
phases or prove what happened in the original hosted workspace binary. The
causal/runtime gate remains open pending equivalent hosted Linux/workspace
evidence and independent review. These local synthetic checks establish no
Windows 10 / 4 GB / 128 GB, four-language corpus, real-provider, installer or
release acceptance. Full commands, controls, raw output and limits are retained
locally in `.superpowers/sdd/2026-11-12-pilot-http-deadline-remediation/task-1-report.md`.

## Mobile pairing timing checkpoint — 2026-11-12

On clean `0aad17b9c098cc34eec6441fb84fbf00cb6b492c`, the selected actual
Flutter 3.47.5 / Dart 3.13.4 and existing locked resolution produced one focused
internal diagnostic **1/0**, followed by three deliberate RED controls, then one
full mobile run **515/0** at unchanged default concurrency. All commands consumed
that resolution with `--no-pub`. The full run used the committable test fixture
and byte-identical original production `session.dart`, without internal tracing.
Final analysis and the changed test's Dart format check pass. The existing
Android debug APK compile also passed locally with task-owned Gradle/Android-user
caches; no install, emulator/device execution or release signing was performed.

The fixture retains at most 32 ordinary interval events, reserved terminal
summaries, and aggregate heartbeat count/max lateness. It records pair/hello,
parked schedule/due/fire, frame receipt, close entry/completion and caller/matcher
completion. Receipts are dumped after the measured interval, including assertion
failures; timers and stream controllers are cleaned up. No frame payloads,
credentials or arbitrary exception text are logged. Disposable internal tracing
only observed the already computed real remaining budget, requested read and
refusal phases; no extra policy decision or substitute clock was added.

The focused diagnostic requested about 148 ms for its second read and delivered
the timeout to the caller at 1.006 s. Controls distinguish three explanations:
same-isolate stall from 0.902 to 2.502 s retained a shrinking 148 ms second wait,
showed 1.551 s heartbeat lateness and failed the original elapsed bound at
2.504114 s; a 1.5 s close delay reached refusal/close entry at 1.003 s, completed
close at 2.505 s with only 2.725 ms max heartbeat lateness, and failed at
2.507036 s; a disposable full-budget-per-read mutant requested a second full
1 s and failed at 1.862262 s. Each reached the correct timeout matcher and failed
the unchanged `<1.5 s` assertion, leaving its subsequent close-count assertion
unreached. All mutations were restored; patches, hashes and outputs are retained.
These controls prove diagnostic sensitivity, not the historical cause.

In the final broad run the parked frame fired at 852.428 ms, close entered at
1003.274 ms and completed at 1003.442 ms, and the caller received the timeout at
1003.451 ms from the fixture's monotonic origin. The measured caller interval was
1003.275 ms; both the strict elapsed and close-count assertions passed. Aggregate
heartbeat max lateness was 2.110 ms. Broad receipts do not expose internal budget
decisions; the separate scratch diagnostic does. Immediate grant, rejection,
malformed/disconnect, buffered zero-budget grant refusal, silent-host and honest
120/150 scaled parking controls remain in the passing suite.

The original full **514/1**, actual **2.504491 s**, and unreached close-count
assertion remain separate from the later historical isolated **1/0** and these
new observations. Historical attribution remains unresolved; no production
pairing behavior or test contract correction is claimed. One initial sandbox
attempt failed before loading the case because Flutter's local runner socket was
refused; its separately retained loopback-enabled execution supplies the actual
focused result. Production 150 s, host 120 s, test 1 s, parked 850 ms, strict
`<1.5 s` and outer 3 s remain unchanged, along with timer/manual/protocol behavior.

Full commands, exact source/SDK/lock bindings, all control outputs and Android
compile disposition are retained locally in
`.superpowers/sdd/2026-11-12-pilot-mobile-ci-remediation/task-2-report.md`.
Current local source verification does not supply equivalent hosted evidence,
Windows 10 / 4 GB / 128 GB device, four-language corpus, real-provider, installer
or release acceptance. Independent review and final hosted gates remain root-owned.

## Windows release Perl environment checkpoint — 2026-11-12

The earlier Windows release-output failure reached OpenSSL Configure through
Git's `/usr` Perl/module tree before release tests ran. The Rust job now resolves
an application executable in PowerShell, normalizes its absolute native Windows
path to forward slashes, probes that exact executable for `IPC::Cmd`,
`Params::Check`, `Locale::Maketext::Simple` and `MSWin32`, explicitly rejects a
nonzero native exit, and exports its unquoted value as `OPENSSL_SRC_PERL`.
The existing release Bash step requires and probes that same executable before
Cargo. Installed pinned `openssl-src 300.6.1+3.6.3` source confirms that variable
wins over `PERL` and bare `perl`; no dependency or module installation changed.

Actionlint 1.7.12, workflow self-tests/checks (118 legacy cases; 39 cache CLI
fixtures; 7 workflows / 21 jobs), nine cache-handler mutation controls, minute
self-tests/checks, alarm self-tests and diff whitespace checks pass locally.
Disposable macOS Bash controls reject absent/empty variables, a nonexistent
executable, an explicit exit-23 executable and actual Darwin Perl before the
Cargo sentinel. A path-with-spaces positive stub reaches the sentinel and
checks the exact module/native-OS probe arguments. These are shell-contract
checks, not native Windows acceptance. All other workflow mappings are unchanged;
the release body is byte-identical after removing the two added preflight lines.
Encryption, full binary suite, timeout, named tests, nonzero receipt, pipefail
and matrix remain intact.

The original hosted failure remains evidence. No Windows or PowerShell runtime,
release compilation, hosted retry, provider/device, installer or release
acceptance is claimed by this YAML-only correction. The next reviewed hosted
run must print the same native path/OS/version in setup and release preflight,
then pass the complete encrypted release-output suite and its existing receipt.
Exact commands, RED/GREEN shell controls and limitations are retained locally in
`.superpowers/sdd/2026-11-12-pilot-windows-webkit-remediation/task-1-report.md`.
