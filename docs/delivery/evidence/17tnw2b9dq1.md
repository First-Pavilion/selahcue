# Error-hygiene evidence — 17tnw2b9dq1

Task: https://app.clickup.com/t/17tnw2b9dq1. Agent: Kenji. Original base `9deb975872eda7f16e67b4bee2c00dc8707af18b`; current integrated main `d9fcd524634ab9328231b6d984bd16be11d2ea78`.

This is the ticket's existing Low/Info diagnostic hygiene, not a newly demonstrated production exploit. No wire format, permissions, database schema, dependency, mobile production code or installer configuration changed.

## RED, then GREEN

Before implementation, actual production paths reproduced these failures:

- `cargo test --locked -p selahcue-lan --features server --test test_ws_error_redaction`: exit101. Derived `TransportError::Ws` Debug printed the HTTP403 peer header sentinel and body as decimal bytes. The test first establishes the underlying tungstenite error contains both, then requires wrapped Display/Debug/alternate Debug to omit header/body text and byte prefixes while retaining403. The initial test fixture needed a Box for tungstenite0.30; that compile error was corrected before recording the behavioral RED.
- `cargo test --locked -p selahcue-data --test test_plan_repo --test test_transcript_repo diagnostic_never_quotes`: exit101 on the first, actual-database kind regression, which showed `unknown item kind 'STORED-KIND-SENTINEL-...'`. Cargo stops at the failed test binary; the retention test was therefore executed separately.
- `cargo test --locked -p selahcue-data --test test_transcript_repo corrupt_retention_diagnostic`: exit101, actual-database retention value appeared in `corrupt data: transcript_setting retention_days value "STORED-RETENTION-SENTINEL-..." is not a valid u32`.
- `cargo test --locked --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml theme_error_hygiene_tests`: exit101, one failed/one passed. Unknown theme alignment returned serde's quoted theme sentinel; a valid built-in theme rendered successfully. The new diagnostic uses serde's `classify()`, `line()` and `column()` only, with no raw-message/source retention. Test category spelling was adjusted from lowercase `data` to serde's Debug `Data`; semantic requirements remain category, position and no value.

Completed GREEN commands use Rust1.98.0 on macOS, the existing locked dependencies and an existing local Cargo target cache. `make stage-operator-binaries` created only missing gitignored compile-check placeholders; no SDK/runtime was fetched or packaging run. All Cargo verification processes completed before handoff.

| Command | Result |
|---|---|
| `cargo test --locked -p selahcue-lan --features server` | exit0;229 passed,4 ignored child-process entrypoints |
| `cargo test --locked -p selahcue-data` | exit0;177 passed |
| `cargo test --locked --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` | exit0;457 passed,1 ignored child-process entrypoint |
| `cargo fmt --all --check --manifest-path implementation/desktop/Cargo.toml` | exit0 |
| `cargo fmt --check --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` | exit0 |
| `cargo clippy --locked -p selahcue-lan --features server -p selahcue-data --all-targets -- -D warnings` | exit0 |
| `cargo clippy --locked --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --all-targets -- -D warnings` | exit0 |
| `git diff --check` | exit0 |

The ignored tests are helpers intentionally invoked by their parent tests: LAN `child_checks_dir_env_current`, `child_prepares_under_a_hostile_umask`, `child_prints_the_descriptor_path`, `sweep_restart_child`; operator `endpoint_guard_tests::child_reads_the_descriptor_from_xdg_runtime_dir`. No test failure was omitted.

Raw local diagnostic logs: `/private/tmp/17tnw2b9dq1-{red-ws,red-data,red-retention,red-theme,green-lan,green-data,green-operator}.log`. These local paths are not published report links.
Clippy receipts: `/private/tmp/17tnw2b9dq1-clippy-{workspace,operator}.log`, both completed exit0. Initial parallel RED commands waited on this agent's own operator compilation; subsequent checks were serialized. No other agent's process was interrupted.

## Webview caller and comment audit

`selahcue-operator/dist/app.js` `tdPreview` invokes `preview_theme` and catches it with `console.error(e)` (baseline lines2569–2579). The supplied theme value therefore could reach the local webview console. Source inspection of `Cargo.toml`, `tauri.conf.json` and Tauri builder initialization found no configured log plugin or persistent console sink. This does not establish that an external debugger or OS cannot capture console output; no persistent-log claim is made.

All five obsolete comment sites now correctly say the protocol Debug dump and JSON value quoting were already fixed by17tnw2axppb/17tnw2b9aec. Existing fixed transcript/draft UI/log messages remain defence in depth.

## Dart item5 audit

Inspected current `lib/models/session.dart` and all `protocol.dart` model decoders after integrating mobile PR344. `StreamQueue.nextJson` refuses non-text/non-object frames and catches `FormatException`, returning the fixed `malformed frame from the host`; it does not forward the JSON parser's source. Command decoding still wraps non-SessionException failures using `'$e'`. The relevant model decoder failures are `as` casts/defaults; there is no numeric parse or value-bearing custom throw in `protocol.dart`.

Executed a standalone Dart runtime probe importing the actual production `protocol.dart`. Six malformed frames put a unique sentinel into ack request_id, operator view, plan-item id, transcript id, chapter number and verse number. Every fixture first required an actual TypeError; all six `toString()` results named only runtime types and the target type, never the sentinel. Probe exit0, output `/private/tmp/17tnw2b9dq1-dart-audit.log`; probe source `/private/tmp/17tnw2b9dq1-dart-audit.dart`. An initial scratch fixture used a nonexistent transcript field and correctly failed its premise; corrected to actual `id` before the completed run. No mobile production fix is justified by these results.

This settles the scoped cast/model question, not every possible platform/network exception or explicit protocol error-message payload. Stream onError and initial connect still stringify platform errors; their network/OS diagnostics are separate from model-cast failures. No claim of a complete Dart diagnostic security audit is made.

## Integration and review

Fetched main and fast-forwarded the isolated branch from9deb9758 to d9fcd524 before final handoff; no conflict, no change to scoped Rust inputs. Four independent reviews and exact-head hosted CI remain root-owned gates. No merge, QA, deployment, provider operation, installer dispatch or live-data test is claimed by the implementing agent.
