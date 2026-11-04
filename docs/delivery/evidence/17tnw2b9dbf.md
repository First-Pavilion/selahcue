# Rust audit CI hardening — 17tnw2b9dbf

Task: https://app.clickup.com/t/17tnw2b9dbf. Branch: `codex/17tnw2b9dbf-audit-ci`.
Initial baseline: `65c2bba6f379ab71da9a23fe23c4fe4e3c7be097`; integrated fresh main `0ec577c24db9550e97ae375478bcbbd0977dc699` before final verification. The intervening change is mobile-test-only; audited Cargo locks and deny policies are byte-unchanged by that integration or this ticket.

## Changed behavior

The existing RustSec job invokes `cargo-audit audit` directly in every git-discovered Cargo root. Cargo's `[alias] audit` and `CARGO_ALIAS_AUDIT` cannot replace that executable. The supply-chain job similarly invokes `cargo-deny check licenses sources bans` directly, adds the previously omitted independent STT root, and retains each existing all-features policy without an allowlist/dependency change. Both Ubuntu jobs have bounded timeouts, only contents:read, and no persisted checkout credentials. The alarm keeps its existing separate issue-write permission.

`check_rust_supply_ci.py` derives required roots from the existing independent coverage discovery, checks exact unmasked binary invocations and policy/job boundaries, and runs an offline regression through real Cargo. Its same self-test and normal check run in the always-reached workflow-policy job and in local make ci. The coverage parser recognizes direct cargo-audit invocation while retaining its previous discovery and comment/missing-root protections.

## Actual alias reproduction and regression

Before the fix, a disposable repository `.cargo/config.toml` with audit="version" caused real Cargo 1.97.1 to return 0 and print Cargo's version plus a shadow-warning. A task-owned cargo-audit sentinel configured to fail 23 was never invoked. The original workflow command therefore reported success without auditing; the new regression went RED on that exact command.

The final regression drives the actual six workflow audit/deny commands across all three roots using real Cargo plus disposable sentinel tool binaries. Repository aliases, environment aliases and an alias forging a cargo-audit-looking identity are all exercised. Cargo must actually report observing an alias; an unavailable toolchain cannot count as a successful alias fixture. For each case, tool success and failure23 must reach the exact expected binary/arguments and preserve its status. All 36 probes pass. These are real Cargo dispatch tests with synthetic auditor results, not36 live advisory scans.

Eight configuration mutations independently reject restored cargo dispatch, failure masking, missing required deny coverage, conditional skipping, widened token, missing timeout, removed schedule and an audit hidden from the alarm. Normal mode only reads workflow/git data; the self-test performs no advisory fetch, production operation or live issue write.

## Genuine installed-tool execution

Local cargo-audit 0.22.2 and cargo-deny 0.20.2, existing Rust tooling and lockfiles:

| Exact command / root | Result | Wall observation |
| --- | --- | --- |
| cargo-audit audit / desktop workspace | exit 0, no vulnerability failures;1 existing allowed warning |4.274s |
| cargo-audit audit / operator shell | exit 0, no vulnerability failures;3 existing allowed warnings |5.778s |
| cargo-audit audit / independent STT | exit 0, no vulnerability failures/warnings |2.169s |
| cargo-deny check licenses sources bans / STT | exit 0; existing duplicate-version warnings remain warnings |0.763s |

The real audits fetched the RustSec database and scanned477/569/179 crate dependencies respectively. Existing unmaintained/unsound warnings remain visible under the unchanged default failure policy; this is not a zero-warning claim. No advisory ignore flag/configuration, dependency update or policy waiver was introduced. Raw task-owned receipts: `/private/tmp/17tnw2b9dbf-live-tools.json` and associated live audit/deny logs.

## Existing weekly audit / issue disposition

No additional scheduler was created. Current CI already has one Sunday03:17UTC schedule. Its tested tier script sets everything=true; desktop output consequently enables the all-root RustSec and supply-chain jobs. The ci-alarm job explicitly needs audit and supply-chain, uses always(), includes schedule events, and reconciles the ci-red issue with its existing scoped issue permission. The alarm's pure regression tests verify failed/skipped/recovered tracking without a live issue write.

The parent accepted this existing all-root weekly job plus issue alarm as the operational equivalent of the ticket's requested weekly make audit. CI directly invokes the same RustSec tool/defaults over the same git-discovered root set; local make audit retains its existing identity/shadow-warning refusal and all-root behavior. The task's historical private-repository billing assumption is superseded by the current public repository and actually running CI. No workflow dispatch or live failure rehearsal was performed.

## Completed local checks and remaining gates

- New CI helper:8 rejected configuration mutations and 36 actual-Cargo alias/status probes; normal three-root policy check passes.
- Existing local audit script:37 cases pass, including alias identity, shadow warning, nonzero results, interruption/cleanup and Makefile last-gate/opt-out protections.
- Existing dependency coverage self-test and real discovered-root check pass, including new direct-binary positive and missing/commented-root negatives.
- Existing workflow, CI-minute self/normal, visual-policy and alarm self-tests pass; actionlint, syntax, diff whitespace and Goal structural validation pass.

The first sandboxed 37-case run was invalidated by macOS system git/xcrun writing an xcrun_db file into the signal-test temporary directory. The same unchanged 37 tests were rerun with the required execution permission and all passed; no cleanup assertion was relaxed. Other final checks are recorded with individual exits. All verifier processes finish before handoff.

Parent owns Cody, Shadow, Quinn and Vera reviews, current hosted CI, snapshot freshness, merge/main verification and QA readback. No pre-review/CI/QA completion is claimed. ClickUp connector quota is exhausted; the parent saved/read back In Progress and owns authenticated UI evidence updates. Rollback is a revert of this isolated CI change; no application data, production service or installed artifact changed.

Primary references: https://github.com/RustSec/rustsec/tree/main/cargo-audit ; https://embarkstudios.github.io/cargo-deny/checks/index.html .
