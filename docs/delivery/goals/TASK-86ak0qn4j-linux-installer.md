# Goal Contract — TASK-86ak0qn4j-linux-installer

## Identity

- Goal ID: TASK-86ak0qn4j-linux-installer
- Parent goal ID: NONE
- Title: Manual main-only Ubuntu packaging builds and checks a real non-NDI output sidecar
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak0qn4j
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Provide an executable Ubuntu24.04 x86_64 .deb packaging path retaining real native output/default encryption and local STT, with platform-effective Tauri configuration, real sidecar staging, uncompressed-artifact scanning and manual main-only CI admission. Retain honest runtime/build evidence limits until the main workflow can execute.

## Baseline

Verified main 020ab896: Windows NSIS/shared DLL configuration; no Linux packaging workflow. P06 checker/runbook merged. Aria resolved Ubuntu24.04 x86_64 GNU/deb with a real non-NDI audience sidecar; NDI remains optional and excluded from this existing ticket. Operator can fall back to demo if sidecar startup fails, so shell appearance is insufficient runtime evidence.

## Inputs and evidence sources

- Existing ticket86ak0qn4j and owner manual-main packaging decision
- Aria continuation report and actual no-NDI Cargo dependency tree
- P06 preflight, Tauri pinned config parser2.10.1 and official platform merge/Debian documentation
- Existing installer scanner and autolaunch/host_connected IPC implementation

## Source bootstrap prerequisite (2026-10-31)

Architecture and delivery prospectively split the source bootstrap into ticket [17tnw2bbjg0](https://app.clickup.com/t/90131572460/17tnw2bbjg0), governed by [its separate contract](TASK-17tnw2bbjg0-ubuntu-pipeline-bootstrap.md). The same PR325 and published branch are retained; no duplicate implementation is introduced. The original source attempt/head a680e025 is history, not evidence of native completion. C-004 below remains **mandatory and BLOCKED/NOT RUN**, with its wording unchanged. Source-prerequisite reviews do not satisfy this ticket's runtime acceptance or independent verification.

Required sequence: source-bootstrap review/normal CI/merge -> authorized exact-main manual packaging run recorded on this existing ticket -> independent clean-location [P18](https://app.clickup.com/t/90131572460/17tnw2bbhxr). Record the actual source SHA/run/attempt, Debian hash/metadata, native package/ELF closure, installed real IPC/frame and uninstall evidence. A retained CI artifact after smoke failure is not an accepted installer. Original clean installed-app obligations remain unresolved until actual sufficient evidence is cross-linked here/P18; hosted software-GPU coverage does not waive them.

## Scope

### In scope

- Linux-only config, real release sidecar/operator build and staging, Debian content/ELF dependency checks, packaging provenance, manual-main workflow and regression tests
- Executable installed-app IPC/sidecar smoke checks where environment permits

### Non-goals

- Provider key issuance/embedding, pilot scanner exception, bucket/public download publication, NDI runtime or Windows/macOS changes
- No changes to desktop Rust behavior, ordinary debug-key guards, API, marketing or mobile

### Constraints

- Own isolated ticket worktree and branch; no other agent edits
- Workflow requires workflow_dispatch and exact refs/heads/main before runner work; SHA-pinned checkout
- No debug build, default-feature disabling, staged placeholders or developer loader-path dependence

### Assumptions and unknowns

- Actual native package construction and GUI/runtime evidence require Ubuntu runner/display; local Docker is amd64 emulation on arm64
- Pilot credentials/expiry/scanner and distribution remain separate unready gates

## Dependencies and approvals

- Aria Linux technical choice resolved; P06 prerequisite investigation merged
- Root owns live ClickUp updates and independent review/merge
- No paid packaging dispatch or public publication in this increment

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Linux-effective config selects deb and removes Windows DLL without modifying base Windows config | regression tests and actual pinned Tauri merge probe | Linux deb/noDLL; Windows NSIS/DLL retained | docs/ops/LINUX-INSTALLER.md; actual tauri-utils2.10.1 probe | PASS |
| C-002 | yes | Build path preserves release/default encryption/non-NDI sidecar, rejects placeholders and requires both package binaries | packaging regression tests | positive/negative controls pass | 14 host and emulated Ubuntu24.04 regressions | PASS |
| C-003 | yes | Manual main-only workflow, explicit checkout SHA and artifact scan/upload ordering validate | actionlint, workflow/cost guards and mutation tests | checks pass, automatic/non-main paths denied | actionlint; workflow118/cost selftests and live source checks | PASS |
| C-004 | yes | Actual Ubuntu package/ELF/install/real IPC/live output evidence exists | manual main workflow and clean installed-app smoke | real non-demo backend/output with no missing native deps | BLOCKED until main workflow/runtime execution | BLOCKED |
| C-005 | yes | Independent review passes | Cody/Shadow/Quinn/Vera | no unresolved blocking findings | root review report | PENDING |

## Verification plan

- Focused verification: packaging tests, shared scanner selftest, source config merge and workflows
- Broader regression verification: Ubuntu/P06 tests, existing workflow and CI-minute guard suites
- Independent verifier: root-coordinated four reviewers
- Required environment: Python, PyYAML, actionlint; pinned Rust/Tauri tooling and Ubuntu24.04 for actual package

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003
- Hypothesis: platform merge plus explicit real-artifact checks makes Linux packaging usable while preserving Windows and refusing false demo/placeholder readiness
- Change or investigation: inspect actual Tauri merge and sidecar autolaunch; write failing regression controls then build pipeline
- Verifier executed: fourteen packaging regressions on host and emulated Ubuntu24.04; actual pinned Tauri configuration parser; scanner45/workflow118/P06 selftests; actionlint and workflow/cost source checks
- Result: configuration and offline controls pass; no native build or installed runtime evidence
- New evidence: docs/ops/LINUX-INSTALLER.md; /private/tmp/otto-linux-packaging-tests-ubuntu24.log; /private/tmp/otto-tauri-actual-merge.json
- Decision: independent review, then main-only native build/install validation

## Risks and rollback

- Risks: static/fixture checks do not prove real installer, native ABI, graphics/audio, IPC or pilot readiness
- Rollback or recovery: revert Linux-only config/workflow/scripts; Windows base untouched

## Pause and escalation conditions

- Any unexpected default-feature or provider credential need stops the build; do not weaken shared policy
- No native package or real backend evidence means no ticket completion claim

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ak0qn4j-linux-installer.md
- Validator result: structural contract validation passes; completion intentionally not asserted
- Independent verification result: pending
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: mandatory C-004 actual package/runtime including clean installed-app evidence remains BLOCKED/NOT RUN; runtime acceptance reviews pending; source bootstrap now belongs to 17tnw2bbjg0
- ClickUp final evidence comment: root coordinates browser update
