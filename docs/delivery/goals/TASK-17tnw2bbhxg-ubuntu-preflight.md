# Goal Contract — TASK-17tnw2bbhxg-ubuntu-preflight

## Identity

- Goal ID: TASK-17tnw2bbhxg-ubuntu-preflight
- Parent goal ID: NONE
- Title: Ubuntu packaging prerequisites are executable and fail closed on missing native payloads
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhxg
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Produce an executable, nonsecret Ubuntu packaging inventory with negative controls for the Windows-only configuration, missing/placeholder output sidecar and missing NDI payload. Exercise it in a clean Ubuntu candidate environment if available; retain an explicit unverified support matrix.

## Baseline

Verified source add4702e3474fb9c6c793beccbd2d38b59993db0: Tauri bundles NSIS and a Windows DLL globally; no Linux config/workflow; binaries ignored/absent in clean worktrees. Existing Linux CI stages empty placeholders for compile checks only. NDI SDK/runtime is optional and untracked. Host is Darwin/arm64, Docker server Linux/arm64; no Ubuntu image cached initially.

## Inputs and evidence sources

- ClickUp P06 and owner manual/main-only packaging instruction
- Tauri configuration, desktop/operator Cargo manifests, existing CI native dependency steps
- vendor/ndi/README.md, scripts/fetch_ndi_sdk.sh, Makefile loader paths
- Official Tauri prerequisites and Debian distribution documentation

## Scope

### In scope

- Executable source/resource preflight, fixture-driven regression controls, clean Ubuntu package-availability evidence and bounded handoff

### Non-goals

- No production config/feature/SDK/signing changes, built installer claim, desktop Rust changes or paid CI dispatch
- No Ubuntu/macOS packaging workflow until prerequisites are satisfied; no licensing/SDK redistribution decision

### Constraints

- One ticket branch in a new isolated worktree; no other agent files
- No provider keys or credential scans in preflight; no new infrastructure

### Assumptions and unknowns

- Candidate only: Ubuntu 24.04 x86_64 GNU/.deb; proposed engineering baseline; native build/install validation remains unperformed
- Unknown: native output/WebView/audio/runtime dependency closure and real display/hardware behavior

## Dependencies and approvals

- Root owns ClickUp browser writes and independent review/merge
- P07 consumes this output; P01/P02/P04 remain full pilot build dependencies

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Preflight rejects Windows config, missing/placeholder/wrong-architecture sidecar, missing NDI payload and invalid inputs | python3 scripts/test_ubuntu_packaging_preflight.py | all regression cases pass | 14 host controls pass; 13 then-current controls pass in Ubuntu | PASS |
| C-002 | yes | Real clean checkout produces a bounded, actionable inventory rather than vacuous readiness | python3 scripts/ubuntu_packaging_preflight.py --root . | exit 1 with specific unresolved inputs | source report exits 1 with four precise source blockers | PASS |
| C-003 | yes | Candidate support matrix and native dependencies are checked in actual Ubuntu or inability is evidenced | ephemeral Ubuntu container read-only source preflight/package availability | OS/architecture/package evidence or precise blocker | docs/ops/UBUNTU-PACKAGING-PREFLIGHT.md: Ubuntu24.04 amd64 emulated run, all13 apt candidates | PASS |
| C-004 | yes | Independent reviews pass | Cody/Shadow/Quinn/Vera | no blocking findings | root review report | PENDING |

## Verification plan

- Focused verification: self-contained Python regression tests and CLI rejection cases
- Broader regression verification: compile script, diff check, no changes to existing workflow
- Independent verifier: root-coordinated specialists
- Required environment: Python 3 stdlib, optional local Docker official Ubuntu image

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003
- Hypothesis: resource/config evidence exposes clean-checkout packaging blockers without shipping placeholders or adding speculative workflows
- Change or investigation: reproduce source configuration, build/native prerequisites and exact candidate target
- Verifier executed: Python regression controls, actual source CLI, ephemeral Ubuntu24.04 amd64 host/source preflight and apt-cache availability inventory
- Result: initial test failed because checker did not exist (RED); 14 host tests pass (GREEN); clean source correctly exits 1; emulated Ubuntu13 tests pass and preflight rejects missing inputs
- New evidence: python3-minimal lacks json in clean Ubuntu; reproducible command uses python3. All13 native/build package names have apt candidates but are not installed or link-tested.
- Decision: handoff

## Risks and rollback

- Risks: passing preflight means prerequisite file/header checks only, never installability, ABI closure or store readiness
- Rollback or recovery: revert ticket branch; no live service or infrastructure changed

## Pause and escalation conditions

- Aria verifies the proposed technical matrix and build profile; no silent feature or redistribution change. Reasonable technical defaults do not require a generic user approval gate.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbhxg-ubuntu-preflight.md
- Validator result: structural validation passes
- Independent verification result: pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: independent reviews, candidate runtime evidence and matrix/build-profile validation
- ClickUp final evidence comment: root coordinates browser update
