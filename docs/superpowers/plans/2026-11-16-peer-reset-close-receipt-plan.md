# Peer reset close receipt implementation plan

Spec: `docs/superpowers/specs/2026-11-16-peer-reset-close-receipt.md`.

## Global Constraints

- Only `implementation/desktop/crates/selahcue-cloud/tests/test_access_transport.rs` is implementation-owned. Production transport, core deadlines, operator routing, dependencies, workflows and historical proof inputs remain unchanged.
- Typed monotonic EOF/reset receipt; `ConnectionReset` is accepted only from the delayed-response final observer read after complete authenticated request and successful partial write. Head-only and accepted-request wall-jump observations remain EOF-only. All other failures remain failures.
- Preserve 120 ms admission before client setup, 60 ms response delay, less-than-620 ms admission-relative ceiling, 500 ms receipt watchdog, all existing timeouts, no retries/skips, zero-I/O refusals, receipt-before-teardown and join/Drop ownership.
- No local runtime under the paging hold. Root owns hosted test-first RED/GREEN, ref updates, review publication and merge. Static reads/AST or syntax checks that do not execute the project and Git metadata are permitted. No secrets/provider calls.
- One global source implementer, no subagents. Preserve other agents' work and sibling plans. Never stage unrelated files.

## Task 1: Classify the qualified abortive peer close correctly

Read the Spec and the full source preflight plus construction supplement at `/Users/m.oluwole/.codex/visualizations/2026/11/14/01a1d9e8-f42c-7583-89ee-386ea3167ba8/designs/access-socket-close-preflight-20261116.md`. Work in the isolated `/Users/m.oluwole/.codex/worktrees/selahcue-rust-release-fixes/scph` checkout on a controller-created `codex/` branch based at main `28314d31f172ad05e757b14ee8a0a69016f9ddd7`. The controller will supply the exact design-only dispatch HEAD.

Phase A — calibrated behavioral RED:

1. Read the existing CloseFixture, diagnostic trace and HTTP controls. Add a bounded real loopback peer using the already enabled Tokio APIs, set zero linger, convert to std if useful, send the exact synthetic authenticated request and read through the first response body byte before dropping its sole socket. Keep existing fixture implementation and production intact. Ensure all failure paths still close and join finite owned resources.
2. Add the focused positive assertion using the current fixture receipt API so the existing final-read refusal fails behaviorally, not at compilation or setup. The root must observe the actual `eof-read` plus `ConnectionReset` failure before authoring Phase B. Add only necessary test helpers; no new dependencies or workflow changes. A different runtime outcome needs diagnosis before changing production/fixture semantics.
3. Make static checks, commit only the owned test file, report exact expected assertion and finite cleanup, then release the source slot. Do not push, run CI or implement the receipt correction yet.

Phase B — after root supplies actual RED:

4. Implement the smallest typed receipt within the same test fixture, preserving the phase qualification, time measurement, all existing negative controls and EOF-only paths from the Spec. Update assertions and fixed labels to distinguish EOF and reset. Add meaningful targeted phase/refusal controls where required; do not use a broad `Err(_)` success path.
5. Self-review all changed test paths, actual time boundaries and ownership. Append full commands/results or UNRUN status to the same report, commit only the owned file, release the source slot for root-hosted GREEN.
6. Root obtains actual focused HTTP and ordinary affected workspace/feature results, including the real calibration and retained negative controls, then independent task and domain reviews. Fix requested changes using the original worker and scoped re-review. Final whole-branch review precedes merge.

Report file: this plan workspace's `task-1-report.md`. Include exact commits, observed versus predicted outcomes, which server phase produced a reset, actual receipt timestamp versus admission, finite test cleanup, unchanged production and dependencies, and the inherited qualification limits. Return only status, commit(s), one-line test summary and concerns. No subdelegation, remote mutations or provider/secret access.

## Completion

The calibrated RED and corrected GREEN are observed; material findings are addressed and re-reviewed; normal affected CI and final whole-branch review pass; live refs and expected composition are verified before the authorized merge. Preserve all historical failures and separately record any unresolved body-phase or prior watchdog qualification.
