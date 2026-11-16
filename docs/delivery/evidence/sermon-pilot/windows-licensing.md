# Windows licensing loopback fixture — A2

Date: 2026-11-11. Ticket: [17tnw2bey5n](https://app.clickup.com/t/17tnw2bey5n).
Base: `7f6dbcbb4782854cbb0fea14a3bb5a9ffcf7fcd0`.

## Diagnosis

The supplied exact-main Windows run (2026-11-08, `windows-main-failures.log`
lines 6203–6212 in the controller's foundation handoff) failed in the shared
`selahcue-cloud/tests/support/credential_receiver.rs` at `read request`:
Windows error 10035 / `WouldBlock`. The licensing client consequently received
connection reset (10054), yielding `ActivationFailure::Unreachable` instead of
`ActivationFailure::Server(503)`. That file reported 6 passes and 1 failure.

The test fixture makes its listener nonblocking to support bounded shutdown,
but previously assumed accepted streams were blocking. Windows can retain the
listener's nonblocking mode on the accepted stream. Setting a read timeout does
not disable that mode. A connection accepted before request bytes arrive, or a
request body delivered after its headers, can therefore fail immediately.

The correction explicitly calls `set_nonblocking(false)` on each accepted socket
before applying the existing two-second read timeout. No production client or
HTTPS admission code changes. The nonblocking listener, ten-second accept
horizon, eight-request cap, 16 KiB read-loop threshold, and joined worker shutdown
remain. New readiness/body-progress notifications use bounded channels; at most
one pending-body notification is emitted per request.

## Regression and local mechanism evidence

The new licensing sibling test sends headers with a nonzero content length and
withholds the body. A channel notification from the receiver's actual
incomplete-body branch confirms that the parser reached that boundary. The test
then checks that no response has arrived, supplies the synthetic credential body,
reads the 503 response, and joins the receiver to assert the exact complete
request, including the bearer header. There are no added sleeps or larger
request timeouts. Existing production HTTP-refusal, scoped loopback-constructor,
503 mapping, body, and bearer controls remain intact.

A dedicated test-only receiver constructor explicitly sets accepted sockets
nonblocking before the normal preparation path, reproducing the inherited-mode
condition on development hosts. Ordinary fixture users keep `Receiver::start()`.
The new regression selects the forced-mode constructor; normalization must handle
that real socket before any header/body reads.

Mutation validation removed **only** `set_nonblocking(false)`, leaving that
permanent regression and its constructor intact. The full admission file failed
in all three bounded parallel-8 runs: 7 passed / 1 failed each, with
`read request: WouldBlock` followed by connection reset in
`dnu_receiver_normalizes_nonblocking_sockets_and_waits_for_the_complete_body`.
Restoring normalization made the same full file pass 8/8. No mutation remains;
the synthetic inherited-mode constructor remains as the regression's test input.

RED command (three runs with normalization removed) and GREEN command after
restoring it:

```sh
CARGO_TARGET_DIR=/private/tmp/selahcue-pilot-a1-target cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-licensing --test test_https_admission -- --nocapture --test-threads=8
```

Host: macOS/Darwin 25.3.0, arm64; pinned `rustc 1.98.0`.
The initial sandboxed attempt could not bind localhost (`PermissionDenied`);
that environment failure was not treated as a code regression. All subsequent
socket checks ran with focused local-socket authorization.

## Final-source validation

All Cargo commands below used `CARGO_TARGET_DIR=/private/tmp/selahcue-pilot-a1-target`.

| Command (after `cargo test`) | Result on development macOS host |
| --- | --- |
| `--manifest-path implementation/desktop/Cargo.toml -p selahcue-licensing --test test_https_admission -- --nocapture` | 8 passed |
| Same command with `--test-threads=8` appended, three bounded repetitions | 8 passed each; 24 executions |
| `--manifest-path implementation/desktop/Cargo.toml -p selahcue-cloud --features http --test test_https_admission -- --nocapture` | 3 passed |
| `--manifest-path implementation/desktop/Cargo.toml -p selahcue-cloud --features http --lib transport::tls_tests -- --nocapture` | 11 passed; 6 unrelated unit tests filtered |
| `--manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --no-default-features --features cloud-live cloud_url_tests -- --nocapture` | 4 passed; 450 unrelated unit tests filtered; filtered integration target ran 0 tests |

`make stage-operator-binaries` created only missing, gitignored compile-check
placeholders as documented in repository guidance. No provider, real credential,
OS credential-store operation, or external write was used. The operator test
feature selection excludes unrelated default encrypted-data support while
including the real `cloud-live` URL consumer and its child-process probes.

`rustfmt --check --edition 2021` on both changed Rust files and `git diff --check`
passed. Verification is focused on all four consumers of the shared test helper;
no workspace-wide or GUI/runtime claim is made.

## Native Windows evidence received after the fixture commit

Independent native QA reviewed [run 43005029634, Windows job 130470327997](https://github.com/First-Pavilion/selahcue/actions/runs/43005029634/job/130470327997)
against exact fixture commit `dab726e14390070e0dfcd3da59a2d1b218ed3e9e`.
The retained job log identifies Windows Server 2025 / `windows-2025-vs2026`,
`rustc 1.98.0`, and `x86_64-pc-windows-msvc`.

- Debug admission: **8 passed, 0 failed, 0 ignored, 0 filtered** (log lines
  5320–5330), within `cargo test --workspace --no-fail-fast`.
- Release admission: **8 passed, 0 failed, 0 ignored, 0 filtered** (lines
  6384–6396), within `cargo test -p selahcue-licensing --release --no-fail-fast`.
- Both executions include the forced nonblocking/fragmented-body regression,
  scoped loopback constructor, real receiver body/bearer positive control,
  HTTP-refusal siblings, and redaction control.

These are two native complete-file executions in different profiles. The log
contains no explicit `--test-threads`, `RUST_TEST_THREADS`, or bounded focused
repeat, so it does **not** establish three native parallel-8 repetitions.
Overall CI failed on the separate A1 desktop endpoint permission test; native
licensing GREEN is not an overall CI GREEN claim.

## Fix round 1: explicit bounded Windows scheduling gate

The existing `rust` matrix job now has step `windows-licensing-parallel` after
the workspace/debug tests. The existing debug and release sibling runs remain.
Its condition is `${{ !cancelled() && runner.os == 'Windows' }}`, so a separate
earlier workspace failure does not skip this evidence, and that earlier failure
remains a failed job outcome. The Bash loop has exactly three iterations:

```sh
for repetition in 1 2 3; do
  echo "Windows licensing admission parallel run ${repetition}/3 (8 threads)"
  cargo test -p selahcue-licensing --test test_https_admission -- --nocapture --test-threads=8 || exit $?
done
```

Any failed repetition exits the step with its failure status immediately; a later
passing repetition cannot overwrite it. No runner, matrix leg, schedule, provider,
production code, fixture timeout, or fixture source changes accompany this round.
The only added Windows workload is three focused admission-file invocations in
an already-scheduled job, reusing the just-built debug target.

The existing `check_ci_minutes.py` validator executes that actual workflow loop
with a synthetic Cargo executable. It verifies three exact complete-file calls
with eight harness threads when all pass, and preserves exit 7 with immediate
termination when repetition 1, 2, or 3 fails. Its self-test rejects eleven
mutations covering skipped-after-failure and Linux conditions, wrong shell,
continue-on-error, wrong workspace, missing/two/four repetitions, wrong thread
count, a filtered test, and swallowed failure. This adds no new CI job.

Round-1 checks passed: `check_ci_minutes.py --self-test` and its real-workflow
check; `check_workflows.py --self-test` (118 legacy cases and 39 CLI fixtures) and
its real-workflow check; `actionlint -color`; `ci_alarm.py --self-test`; and
`git diff --check`. Executing the actual workflow loop locally with
`CARGO_TARGET_DIR=/private/tmp/selahcue-pilot-a1-target` passed **8/8 × 3** on macOS.
These checks prove loop wiring and local behavior, not a future native run.

## Remaining gates

The controller must dispatch and review a native Windows run of the new head,
including all three explicit parallel-8 repetitions. The prior debug/release
Windows GREEN is verified for the unchanged fixture commit; the new explicit
parallel-repeat Windows result is **pending**. Independent re-review and hosted
CI remain controller-owned. No merge, release, deployment, push, or ticket
completion is claimed here.
