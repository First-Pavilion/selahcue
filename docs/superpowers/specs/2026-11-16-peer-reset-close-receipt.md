# Peer reset evidence in the native deadline fixture

This bounded test-fixture correction follows an actual failing check encountered while reviewing the open release PRs. The user has authorized fixes, TDD, independent re-review and merge after passing. It changes the interpretation of an observed TCP termination, not the production deadline or transport.

## Evidence and scope

PR #417's tests-only composition left the desktop tree identical to main `28314d31f172ad05e757b14ee8a0a69016f9ddd7`. Its Rust job `133261904007` in run `43856442587` failed `delayed_head_and_slow_body_really_close_the_client_at_one_deadline` because the final read returned `FixtureFailure { phase: "eof-read", kind: Some(ConnectionReset) }`. The server observed the reset on the authenticated connection about 121 ms after admission. The late partial response write and reset are recorded before client return and fixture join. A later HTTP-feature invocation passed; neither that pass nor this correction erases the failed workspace invocation.

The original P03 C-001 requires measured network/client closure within 500 ms after the admitted deadline; it does not prescribe FIN instead of RST. RFC 9293 recognizes abortive termination. The controller accepts a narrowly qualified, separately typed peer-reset observation as terminal-connection evidence. The source preflight and construction supplement are authoritative inputs: `designs/access-socket-close-preflight-20261116.md` in the evidence workspace. They distinguish this observed reset from a previous unresolved receipt watchdog timeout.

Alternatives considered were preserving a FIN-only interpretation, accepting a general socket error, and retaining a typed distinction between orderly and abortive peer termination. The selected implementation admits only `ErrorKind::ConnectionReset` at the final observation read of the delayed-response fixture, after its existing complete authenticated request and successful partial response write. Other phases and error kinds retain their existing refusal behavior.

## Required behavior

- Own only `implementation/desktop/crates/selahcue-cloud/tests/test_access_transport.rs`. Production `deadline_transport.rs`, `AccessDeadline`, operator callers, dependencies, workflows and all frozen proof inputs remain unchanged.
- A successful observation carries its monotonic timestamp and an explicit EOF/reset kind. Preserve EOF as the only accepted kind for stalled-head and accepted-request forward-wall-jump controls. Admit reset only on the narrowly qualified delayed-response final read; never reclassify request parsing, authorization, response writing, extra bytes, timeouts, locally initiated teardown or unrelated I/O errors as success.
- Preserve the 120 ms admission created before client setup, 60 ms delayed-response fixture, same admission-relative less-than-620 ms ceiling, 500 ms receipt watchdog, forward-jump socket timeout, zero-I/O pre-expiry and post-expiry refusals, receipt-before-teardown ordering, owned joins and Drop cleanup. No retry, timeout relaxation, test skip or generic error swallowing.
- Record a reset as a reset using fixed diagnostic labels and durations. Never print request bodies, credentials, raw URLs or provider error text. Historical EOF receipts and failed runs retain their original labels and results.
- Add a real calibrated abortive-close control through the existing fixture. The locked direct Tokio dependency enabled by `http` provides `TcpStream::set_zero_linger()` and `into_std()`: connect with bounded I/O, send the exact synthetic authenticated fixture request, read through the first response body byte, and drop the sole client handle. Keep the fixture alive until its server-side observation and join. The tests-first assertion must use the current receipt API; an actual final-read `ConnectionReset` refusal is the desired RED. A missing symbol/type, setup timeout, premature reset or EOF-only run is not that RED.
- Add focused refusal/phase checks where needed to distinguish the permitted reset from a wider acceptance rule. Preserve the existing still-open authenticated-client watchdog and pre-dispatch refusal controls. Do not write tests that merely compare the source text or version strings.

## Evidence boundaries

The timely historical reset proves termination of one connection. The old trace does not prove the reqwest client reached its partial-body await before expiry, why the kernel reset the connection, or whether every request task had terminated. The original core no-renewal controls and accepted-request wall jump remain relevant but do not independently prove those body-phase claims. A general body-progress instrumentation or timer redesign is outside this classification correction. Keep those inherited qualification questions visible, and escalate any new evidence of surviving work, renewed budgets or another watchdog failure instead of treating it as a reset pass.

## Verification and delivery

Use the existing actual HTTP test binary and normal affected Linux CI on the exact candidate. First obtain the calibrated server-observed reset refusal against the unchanged fixture. Then implement the minimal typed receipt and execute the calibrated case, preserved timing/refusal controls, and the same workspace and `--features http` test invocations. Report actual named nonzero outcomes and EOF/reset kinds distinctly; an openai-only invocation with zero collected tests supplies no HTTP evidence.

Local runtime remains held for active paging; no local tests, project imports, compilers, browser/services or toolchain installs. Controller owns hosted execution, refs, reviews and merge. Use a fresh subagent for this task and the original worker for requested corrections, then independent code, security, QA and resource-lifecycle review and final whole-branch review. A passing fixture-classification increment is not a claim that all native or installer qualification is complete.
