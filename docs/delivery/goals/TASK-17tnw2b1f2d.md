# Goal Contract — TASK-17tnw2b1f2d

## Identity

- Goal ID: TASK-17tnw2b1f2d
- Parent goal ID: NONE
- Title: Push-time NDI sidecar type and lint coverage without SDK redistribution
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1f2d
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective

The existing Linux push/PR Rust job checks and lints the actual selahcue-desktop NDI feature and rejects a real gated type error without obtaining or linking a native runtime.

## Baseline

Verified at main d9fcd524: no push-time NDI gate. The committed Windows SDK headers are documented as identical across platforms and contain Linux/macOS declarations. grafton-ndi 2.0.0 build.rs generates real bindings from headers and requires selecting a library file even for link-free check. Existing minute rules reject always-on literal Windows runners.

## Inputs and evidence sources

- Live ClickUp acceptance criteria and direction comments 1400430000278183 and 1400430000278273.
- Existing CI Rust job, installer, SDK headers/README, Cargo manifests/lock and grafton-ndi build source.
- Actual Cargo diagnostics and mutation output.

## Scope

### In scope

- Link-free helper with temporary committed headers and empty platform library selection placeholder.
- Linux CI check/clippy and real ndi-gated mutation; focused lifecycle controls, goal and evidence.

### Non-goals

- SDK/runtime download, cargo build/link/test/package, installer dispatch, artifact upload, new runner, Windows or runtime acceptance.

### Constraints

- Preserve minute invariants, installer controls, existing source and lockfiles; no source change beyond temporary restored mutation unless root approves.
- Placeholder exists only in a private ephemeral directory during whitelisted check/clippy subprocesses; clean it after success/failure.

### Assumptions and unknowns

- UNKNOWN: NDI feature currently type/lint clean with real generated bindings; resolve from actual local and hosted runs.
- Local macOS can provide analogous command evidence; hosted Linux supplies the actual approved push-time OS gate.

## Dependencies and approvals

- User authorizes wave implementation and public PR, with four independent reviews before root merge/QA.
- Root approved Linux existing-job direction after discovering Windows minute-rule conflict; ticket records rationale before coding.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Actual NDI sidecar type-check and lint pass in push-time Linux job | hosted cargo check/clippy --features ndi through helper | both exit 0 with real bindgen headers | docs/delivery/evidence/17tnw2b1f2d.md and CI | PENDING |
| C-002 | yes | Introduced NDI-gated type error is rejected | actual temporary source mutation and cargo check | E0308 from named mutant, original restored | helper output and CI | PASS |
| C-003 | yes | Placeholder lifecycle and CI controls preserve no-link scope | helper controls, actionlint, workflow/minute tests and diff | controls pass, only check/clippy allowed, temp removed | docs/delivery/evidence/17tnw2b1f2d.md | PASS |
| C-004 | yes | Current frozen source passes all four independent reviews | root-coordinated Cody Shadow Quinn Vera | four Pass verdicts | PR/root reports | PENDING |

## Verification plan

- Focused verification: real NDI check/clippy, type-error mutation, restored positive; helper cleanup/failure controls.
- Broader regression verification: workflow permissions, actionlint, minute and installer invariants; no lock/header diffs.
- Independent verifier: root dispatches Cody, Shadow, Quinn, Vera.
- Required environment: macOS local command support plus hosted Linux normal source CI; no binary or packaging operation.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 and C-003.
- Hypothesis: real committed cross-platform headers and an ephemeral library-selection placeholder let check/clippy generate bindings and type-check without SDK redistribution/linking.
- Change or investigation: implemented fixed check/clippy helper, ephemeral real-header staging and platform placeholder selection, source-restoring actual type mutation; wired existing Linux Rust job and libclang dependency.
- Verifier executed: actual local macOS check/clippy, E0308 mutant and restored positive; four lifecycle/command controls; actionlint, workflow and minute tests.
- Result: all local commands/controls pass; type mutant fails E0308 at its exact marker and restored source passes. Check 41.83s, Clippy 16.89s, restored check 13.18s (cached local durations).
- New evidence: docs/delivery/evidence/17tnw2b1f2d.md and /private/tmp/wave10-ndi-local.log; no source/lock/header changes remain.
- Decision: integrate fresh main and publish draft for actual Linux CI and independent review. C-001 and C-004 remain pending.

## Risks and rollback

- Risks: false assurance from missing feature or placeholder leakage; prove real gated mutation and isolate child environment/lifecycle.
- Rollback or recovery: revert this ticket's source commit; no production data changes.

## Pause and escalation conditions

- Real NDI compile errors require root-approved minimal source remediation before expanding scope.
- No required hosted check/review is waived; report platform limitations explicitly.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b1f2d.md
- Validator result: pending.
- Independent verification result: pending.
- Terminal state: ACTIVE.
- Remaining failed or blocked criteria: all pending.
- ClickUp final evidence comment: pending.
