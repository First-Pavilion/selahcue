# WebKit failure-probe receipt implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Preserve a bounded independent receipt from the existing WebKit failure probe.
**Architecture:** Add a closed console protocol to the existing observer/probe, validate it in the existing per-page diagnostic object and emit the post-probe observation with the current error-channel result. Preserve gate semantics and all coverage.
**Tech Stack:** Existing Python unittest/Playwright harness and browser JavaScript; bounded Node boundary execution in tests.
**Spec:** docs/superpowers/specs/2026-11-16-webkit-failure-probe-receipt.md

## Global Constraints

- Only the two source/test paths named in the spec; all81existing dirty/untracked inputs and these root-owned documents are protected.
- One existing failure-time probe only, timeout1000/polling100; original settle wait10000 and failure exit2 remain unchanged.
- Strict version1 document/probe records,768ASCII-byte body cap,32lowercase-hex document nonce, one accepted record of each kind, rejection counters at most65535; nonce never in emitted receipt.
- Closed outcomes/state/gate/lifecycle schema from the spec; no arbitrary strings, provider access, new waits, gate bypass, browser installation or workflow changes.
- Actual hosted RED precedes production; local runtime held; controller owns push/review/merge.

## Review Focus

1. A replacement document must compare different, while absent identity is unknown.
2. Getter/property/encoding failures must produce a closed stage label without leaking supplied text.
3. A valid console snapshot must survive a failed error channel; neither channel may replace the primary timeout result.
4. Probe-time lifecycle/console events after the old journal cutoff must remain bounded and visible in the post-probe receipt.
5. Duplicate/hostile output and closed stdout must preserve original exit2 and exactly one invocation.

### Task 1: Independent bounded probe receipt

**Files:**
- Modify implementation/marketing/scripts/responsive_sweep.py.
- Test implementation/marketing/tests/responsive_diagnostic_regression.py.

**Interfaces:**
- Consume existing SettleDiagnostic, probe_settle_state(page), emit_settle_probe(page,capture), SETTLE_DIAGNOSTIC_JS, SETTLE_STATE_PROBE_JS and unchanged SETTLE_JS.
- Preserve current callers/default signatures; an optional diagnostic parameter may be added only with backward compatibility and real-main wiring coverage.
- Produce the exact spec protocol and post-probe evidence through the existing receipt. No application consumer changes.

- [ ] Read spec, source preflight and actual retained failures; record production behaviors the new tests will distinguish.
- [ ] Add at most12meaningful methods to existing CI-selected DiagnosticProbeInertRegression or DiagnosticLedgerPrivacy classes. Cover all five review-focus cases and six outcomes using real entry points; preserve all existing assertions. New-source APIs must not be the cause of RED.
- [ ] Perform only static AST/whitespace/custody checks locally; commit tests alone, append full report including child bounds and expected assertions, then release the source slot for controller-hosted RED.
- [ ] Wait for root-supplied exact named assertion RED. Do not author production beforehand.
- [ ] Implement minimal receipt production from the proven tests and spec; keep exact predicate/coverage/timeouts and prior interfaces.
- [ ] Root obtains actual GREEN with existing CI command from implementation/marketing: python3 tests/responsive_diagnostic_regression.py DiagnosticProbeInertRegression DiagnosticLedgerPrivacy -v, plus the original geometry selection, full routed marketing suite and all ordinary affected checks. No unrun check is a pass. Interpret a live failing-trial receipt separately from synthetic controls.
- [ ] Append full commands/results/hashes/protected custody report, commit owned files and release source slot. Independent scoped review and whole-branch review follow. Reproduce an evidenced root-cause fix in a separately specified follow-up only when this observation identifies it.
