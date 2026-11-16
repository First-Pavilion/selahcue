# Rust canary feature/profile coverage — 17tnw2b1f2f

Task: https://app.clickup.com/t/17tnw2b1f2f. Branch: codex/17tnw2b1f2f-rust-canary. Baseline: reviewed main2f4dcc25. Root owns independent Cody/Shadow/Quinn/Vera, actual current CI, merge/main and native QA verification. This document is execution evidence, not a duplicate task.

## Configuration coverage and disposition

The guard reads actual literal clippy commands across ci.yml jobs whose inherited or explicit working directory is the operator, including operator/operator-native, carrying their operator working directory, explicit Cargo features, default-feature flag and debug/release profile. It compares those configurations with actual commands reached after the operator cd in the canary. The current Windows installer command independently contributes release+stt: cargo tauri build defaults to release and explicitly requests stt. Unknown installer spelling or unsupported/wrapped CI clippy syntax fails for review, instead of silently dropping coverage. No remote workflow or arbitrary expression is executed by normal mode.

| Operator configuration | Actual source | Canary disposition |
|---|---|---|
| default, debug | ci.yml operator Clippy | lint |
| dev-keys, debug | operator Clippy dev-keys | lint |
| openai-notes, debug | operator Clippy openai-notes | lint |
| dev-keys+openai-notes, debug | operator combined Clippy | lint |
| dev-keys+openai-notes, release | operator-native release Clippy | lint |
| stt+cloud-stt, debug | operator-native native Clippy | lint |
| stt, debug | operator-native shipped-feature Clippy | lint |
| stt, release | windows-installer.yml Tauri build | lint; shipped, never called unshipped |
| cloud-live | Cargo.toml OPT-IN, no installer/CI command; Makefile requires explicit OP_FEATURES | excluded from this current shipped/CI parity, not a claim it compiles |
| pilot-credentials | Cargo.toml OPT-IN; real pilot embedding remains provider/policy-gated and absent from current installer/CI | excluded, not activated or claimed shipped |
| no-default-features | absent from installer/CI, removes default read-encrypted-transcripts/encryption | excluded; no default-feature behavior changed |

Release-only code matters independently of feature membership. stt_model_source.rs explicitly switches on debug_assertions, while listening.rs contains a not-cloud-stt arm. The release+stt command exercises that profile with the actually shipped feature choice; the old release dev-keys/openai-notes command does not substitute for it. No combinatorial all-features claim is made. Future CI/installer changes require updating the canary or an explicit reviewed disposition, not a hardcoded current count assertion.

Ubuntu canary setup now installs cmake and libasound2-dev in its own job. Existing toolchain action and RUSTUP_TOOLCHAIN=stable remain unchanged; setup/report/permissions/concurrency/events are semantically identical. Existing create-only placeholders remain. The lint block still accumulates fail=1 per command, attempts later gates and exits the aggregate; continue-on-error permits the existing issue report to run. No new job, trigger, package release, deployment, installer dispatch, credential or feature enablement is introduced. The new filesystem parity check/self-test runs in the existing workflow-policy CI job.

## Completed verification

- Initial real-source parity command RED: seven missing configurations plus missing cmake/ALSA.
- Final positive parity:8operator configurations covered.
- Actual gate/setup/profile/toolchain/continuation mutation controls:16refusals. Eight delete the actual operator command lines; others remove native packages, release profile, failure accumulation/exit or floating toolchain selection; another adds a real operator CI job with an uncovered feature combination.
- Exact production lint shell block executed with disposable local Cargo sentinel: success exits0; native failure exits1 while every later gate, including release STT, still runs. These are2real shell outcome probes, not real compiler executions.
- Existing workflow self-test118legacy+39CLI, normal six-workflow checks, minute self/normal, visual controls, Rust supply8policy/36real-Cargo and normal guards pass. actionlint for both changed workflows passes. All child processes reaped.
- Syntax initially hit the external macOS Python bytecode cache sandbox restriction; rerun with task-owned PYTHONPYCACHEPREFIX passes. No failed command is relabeled success.
- Programmatic YAML comparison proves only native apt packages and lint commands/comments changed in rust-canary; permissions, report step/token scope, staging, floating setup, events and concurrency are unchanged.

## Actual compiler/runtime evidence

All16 operator Clippy commands completed exit0, no timeout or retry: eight configurations on pinned rustc1.98.0 and all eight on officially installed task-isolated stable rustc1.99.1/clippy0.1.99. Each uses the actual operator with default encryption retained, --all-targets and -D warnings; --locked/offline preserves the existing graph. Cargo build jobs were2 and commands were serial. Compile-check placeholders were created only when absent; no GUI/model/provider/installer was run.

The exact8configurations and16completed exits are committed in clippy-summary.json. Full raw logs and argv receipts remain local /private/tmp/17tnw2b1f2f-clippy-receipts.json and per-command logs. All453 tracked Rust/build/resource inputs were independently rehashed unchanged after the runs; Rust source, manifests, locks and profile settings are unchanged by this ticket. Latest reviewed main remained2f4dcc25 immediately before finalization.

The first pinned default command's501.474s wall includes a233.105s explicitly coordinated SIGSTOP/SIGCONT pause of only this owned Cargo group, while frontend browser tests ran. It resumed and exited0; no deadline was increased and no failed test was retried. Timings are shared-host observations, not comparable compiler benchmarks or a hosted cost guarantee. Pinned release build scripts emitted nonfatal rust-objcopy stripping warnings about missing libLLVM; macOS MallocStackLogging diagnostics also remain in logs. No warning-free or release-artifact/packaging claim follows from the successful lint exits.

The globally named stable compiler was1.97.1 and was not called latest or repointed. Fresh official stable was installed with task Rustup/Cargo homes; only that isolated1.99.1 compiler is the current local floating evidence. These16checks cover the operator matrix, not every workspace command in the full scheduled canary, Ubuntu native package installation or Windows. Actual hosted PR CI and future scheduled/manual canary execution are separate; no workflow dispatch is claimed.

## Bounds and recovery

Normal parity work is local metadata parsing of three workflows, with finite step/command sets. Self-test subprocesses are fixed two shell probes, each30seconds, using disposable directories and no network/issue write. Existing scheduled canary cost grows by seven operator lint configurations, with Cargo reusing dependencies within debug/release profiles; no controlled speedup or scheduled-run time guarantee is claimed. Workflow duration must be observed on the actual floating compiler before asserting a budget.

Revert this isolated workflow/guard change to restore the prior canary. No production state/data/schema was changed. Native ClickUp continuation/handoff remains pending root-owned access recovery; the earlier In Progress start was actually saved/read back. Source review/current CI and QA are not claimed complete.

Normal parsing intentionally covers literal Cargo commands and explicit operator directories. Dynamic shell helpers, matrix-derived feature expressions and arbitrary remote actions remain human review boundaries; unsupported detected command/option shapes fail for review. This is not a general shell or GitHub expression interpreter.

## 2026-11-11 reviewed pilot integration reconciliation

The imported P03 CI adds the exact default-on release tuple
`pilot-credentials,cloud-live`. Its lint now has a separate literal `!cancelled()`
step with the same synthetic fixture environment; the expiry test block and its
nonzero/required-name controls remain intact. The canary retains its eight prior
configurations and adds this ninth synthetic-CI tuple. This supersedes the earlier
no-CI-pilot disposition, not the historical compiler results recorded above.

The strict checker derives opt-in admission from exact actual-CI tuples and still
refuses wrappers, missing/profile-drifted gates, non-CI opt-ins and all no-default
configurations. Focused mutation controls and sentinel shell execution verify
aggregate failure and continuation through shipped release STT. These are policy
checks, not actual floating-stable compiler, provider, installer or shipping-profile
evidence. Current compiler/runtime verification remains a separate integration gate.
