# Goal Contract — TASK-17tnw2b1f2f

## Identity
- Goal ID: TASK-17tnw2b1f2f
- Parent goal ID: NONE
- Title: Floating Rust canary covers CI and shipped operator feature profiles
- Role: devops-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1f2f
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
The scheduled Rust canary lints every actual operator CI feature/profile combination and the shipped release STT configuration; a removed combination fails an independent parity guard.

## Baseline
Verified main2f4dcc25. Existing canary compiles operator default only; CI operator/operator-native contain seven feature/profile combinations. Native In Progress/start was previously saved/read back by root; this continuation comment is pending external ClickUp quota/browser recovery. Clean owned worktree moved into /private/tmp without changing its branch or primary checkout. Named installed stable is1.97.1, pinned compiler1.98.0; installed stable is not claimed latest.

## Inputs and evidence sources
- Root LIVE-read task scope and delegated implementation contract.
- Actual ci.yml operator/operator-native, rust-canary.yml and Windows installer build command.
- Operator Cargo feature declarations, release/debug profile branches and Makefile release feature rules.

## Scope
### In scope
- Canary operator clippy feature/profile parity, native Ubuntu dependencies, executable metadata guard and real removal/failure controls.
- Central documented opt-in/non-shipped exceptions with source trace, focused compilation and workflow checks.
### Non-goals
- No feature shipping change, production deployment, installer/canary dispatch, provider calls, credentials, database/service migration or policy relaxation.
- Backup/restore, production observability/capacity and data migration are unaffected by this scheduled lint-only change.
### Constraints
- Preserve floating toolchain and scheduled/manual warning/report semantics, scoped issue token, create-only placeholders and aggregate gate failures.
- One owned branch/worktree; preserve other engineers and primary user mobile lock. Root owns four independent reviews, current CI, merge and QA.
### Assumptions and unknowns
- VERIFIED: current canary covers only default operator clippy.
- UNKNOWN: latest hosted floating-stable execution until scheduled or separately authorized test dispatch; no local older stable will be mislabeled latest.

## Dependencies and approvals
- User authorizes selected wave2 ticket; prerequisite359 is merged. Root supplied LIVE task criteria and confirmed native In Progress start.
- ClickUp MCP quota exhausted and browser unavailable; exact pending continuation/handoff update belongs to root. No retry before16:16UTC.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Canary covers every actual CI operator clippy feature/profile and shipped release STT | parity guard on real workflow commands and actual removal mutations | all current combinations present, missing combo fails | docs/delivery/evidence/17tnw2b1f2f.md | PASS |
| C-002 | yes | Native dependencies/floating compiler/failure aggregation/report boundaries remain valid | workflow control tests, real shell execution with sentinel cargo, focused actual clippy | native deps present, fail propagates while later gates run, no token widening | same evidence | PASS |
| C-003 | yes | Existing workflow/minutes/audit and syntax controls pass with explicit exception disposition | existing guards/actionlint/feature source trace | controls pass, unshipped features documented truthfully | same evidence | PASS |
| C-004 | yes | Four independent reviewers and actual current CI pass before merge/QA | root Cody/Shadow/Quinn/Vera and hosted CI/main/native readback | all required reviews and CI pass, verified main before QA | parent receipts | PENDING |

## Verification plan
- Focused verification: current coverage RED, actual workflow-removal mutants, shell command success/failure aggregation, native dependency checks and local pinned/available stable clippy.
- Broader regression verification: workflow/cache/minutes/visual/audit guards, actionlint, whitespace and structural validator.
- Independent verifier: root coordinates Cody, Shadow, Quinn and Vera.
- Required environment: local macOS Python/PyYAML/Rust plus hosted Linux CI; Windows/native scheduled canary not claimed without actual run.

## Iteration ledger
### Iteration1
- Target criterion: C-001 baseline.
- Hypothesis: parsing the actual literal Cargo commands with their working directory and profile exposes missing canary coverage.
- Change or investigation: inspected full operator/native/canary workflows and shipping/release features; establish exact parity RED before workflow changes.
- Verifier executed: pending initial parity guard.
- Result: actual initial guard exits1, lists six missing CI combinations plus release-STT and missing cmake/ALSA; source inspection confirmed the same gap.
- New evidence: parent start baseline and actual workflow source.
- Decision: iterate

### Iteration2
- Target criterion: C-001 through C-003.
- Hypothesis: eight explicit operator configurations plus native setup and independently derived parity checks close the actual gap without changing warning/report boundaries.
- Change or investigation: added seven operator commands, CMake/ALSA and the literal-command parity guard to the existing always-reached workflow checks. Central opt-in exclusions remain cloud-live, pilot-credentials and no-default-features, each traced in evidence.
- Verifier executed: parity positive,16 gate/setup/profile/compiler/continuation/new-job/shell-shape mutations, two real shell outcome probes; existing118+39 workflow, minute/visual/audit controls and actionlint.
- Result: all completed policy checks pass; actual shell exits0 on success and1 when native lint fails while subsequent shipped release STT still runs. Fresh pinned/floating native clippy pending coordinated browser completion.
- New evidence: /private/tmp/17tnw2b1f2f-controls.json and retained initialRED. Official task-isolated compiler reports1.99.1; no claim that old globally namedstable1.97.1 is latest. Initial Python syntax compile used macOS external bytecode cache and was denied before completion; rerun uses task-owned cache.
- Decision: iterate


### Iteration3
- Target criterion: C-002 actual native compiler evidence and final C-003 controls.
- Hypothesis: actual pinned and fresh isolated stable Clippy can compile all eight operator configurations without changing shipping/source/profile behavior.
- Change or investigation: official task-only stable installation, create-only compile placeholders and two exclusive local targets; no production/Rust code changes. The first pinned process was temporarily paused233.105s by explicit coordination, then resumed; no timeout reset or retry.
- Verifier executed:16 actual locked/offline operator clippy commands with all-targets/-D warnings, eight per compiler; all453 tracked Rust/build/resource files rehashed afterward. Existing workflow/minute/audit/actionlint controls and final parity positives/16drift negatives/two real shell probes.
- Result: all16 commands exit0, no timeout; source inputs unchanged. Pinned release stripping/tool diagnostics retained and not called warning-free. Latest main still2f4dcc25 before publication.
- New evidence: committed clippy-summary.json and full local argv/exit logs. Local macOS does not prove Ubuntu/Windows or full scheduled canary runtime; no dispatch performed.
- Decision: gate-review

## Risks and rollback
- Risks: missing cfg arms or a falsely reassuring canary; derive parity from actual commands and preserve failure aggregation.
- Rollback or recovery: revert isolated workflow/guard; no production data or deployment changed.

## Pause and escalation conditions
- Stop at four iterations, unknown toolchain/native failure, approval rejection or any requested packaging/production expansion.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b1f2f.md
- Validator result: structural validation passes; completion intentionally remains pending C-004.
- Independent verification result: pending parent four-review/CI gates.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: local C-001/C-002/C-003 pass; parent-owned C-004 reviews/hosted CI/merge/main/native QA pending.
- ClickUp final evidence comment: root owns pending native continuation/handoff.
