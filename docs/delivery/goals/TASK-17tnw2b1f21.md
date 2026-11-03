# Goal Contract — TASK-17tnw2b1f21

## Identity

- Goal ID: TASK-17tnw2b1f21
- Parent goal ID: NONE
- Title: Operator SBOM includes shipped STT dependencies and rejects omissions
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1f21
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective

The operator supply-chain job generates its SBOM with the shipped stt feature and refuses an SBOM missing required feature crates.

## Baseline

Verified at main e45ac0ef: operator generation invokes cargo cyclonedx without features; Windows installer ships stt. Actual default-feature SBOM generated: 355 components, four required STT crates absent. Official cargo-cyclonedx 0.5.9 installed temporarily for verification.

## Inputs and evidence sources

- Live ClickUp acceptance criteria and installer/operator/STT manifests.
- .github/workflows/ci.yml and windows-installer.yml.
- Actual generated CycloneDX output and local tool help/source.

## Scope

### In scope

- Operator SBOM generation flags, generated-document validation, focused controls and execution evidence.

### Non-goals

- Packaging dispatch, binary builds, native SDK work, provider calls, deployments, manifests and lock updates.

### Constraints

- Preserve existing manual/main-only packaging controls. One ticket/branch/PR. Shared repository; no other agent/user edits.
- Do not claim native binary completeness from metadata-only generation. Existing desktop SBOM step stays intact.

### Assumptions and unknowns

- UNKNOWN: actual generated SBOM dependency membership without/with stt; resolve with real cargo-cyclonedx.

## Dependencies and approvals

- User authorized this wave, public source PR and eventual merge after four independent passes; root owns review/merge/QA.
- Local tool installation and Cargo metadata resolution require network; no production services.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Generated operator SBOM includes shipped STT tree | cargo cyclonedx with stt and checker on actual output | whisper-rs and direct feature crates found | docs/delivery/evidence/17tnw2b1f21.md | PASS |
| C-002 | yes | Missing required component causes failure | checker self-tests and removed-component actual-output mutation | each omission exits nonzero, valid output passes | docs/delivery/evidence/17tnw2b1f21.md | PASS |
| C-003 | yes | CI invokes feature generation and validation before upload without weakening controls | workflow/actionlint controls and diff inspection | gates pass and mutation refused | docs/delivery/evidence/17tnw2b1f21.md | PASS |
| C-004 | yes | Current frozen source passes independent code/security/QA/performance reviews and CI | root-coordinated Cody Shadow Quinn Vera and hosted checks | four Pass results and actual relevant CI success | PR and root reports | PENDING |

## Verification plan

- Focused verification: actual baseline/fixed SBOM, component omission, checker controls.
- Broader regression verification: workflow permissions/actionlint, installer parity and scope/lock diff.
- Independent verifier: root dispatches Cody, Shadow, Quinn and Vera.
- Required environment: macOS local Cargo metadata and hosted Linux source CI; no installer dispatch.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 and C-002.
- Hypothesis: enabling stt resolves the optional selahcue-stt tree into the operator SBOM without requiring native compilation.
- Change or investigation: generated actual default and shipped-STT all-target inventories; added feature flags and required Cargo identity/dependency graph validator before upload.
- Verifier executed: real cargo-cyclonedx baseline and fixed generation; checker controls and actual graph inspection.
- Result: default lacks four required components; fixed includes all five. Initial graph checker incorrectly required dependsOn on valid leaves.
- New evidence: actual 355/559-component documents; leaf omission shape identified, no application compile needed.
- Decision: iterate.

### Iteration 2

- Target criterion: C-001, C-002 and C-003.
- Hypothesis: accepting omitted leaf dependsOn as empty preserves valid generated documents while required graph reachability and omission negatives remain effective.
- Change or investigation: valid-leaf handling and regression; actual document and negatives rerun.
- Verifier executed: 11 grouped controls; actual baseline/fixed CLI; five removed-component CLI mutations; disconnected STT edge; actionlint; 118 workflow controls; 12 parity controls.
- Result: real baseline fails; fixed passes; all six actual-output negatives fail for the expected missing components. Workflow gates pass.
- New evidence: docs/delivery/evidence/17tnw2b1f21.md and raw task-owned temporary JSON/logs.
- Decision: handoff after freshness, source freeze and hosted CI; C-004 remains root review gate.

## Risks and rollback

- Risks: document schema/name validation could accept unrelated components; use package identity/root validation and deliberate omission cases.
- Rollback or recovery: revert this ticket's isolated commit; no persistent application data changes.

## Pause and escalation conditions

- Missing licensed SDK needed for metadata or inability to obtain actual generated output: report evidence and ask root for bounded alternative.
- Four-review gate or source CI failure remains gating; no self-merge.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b1f21.md
- Validator result: pending.
- Independent verification result: pending root reviews.
- Terminal state: ACTIVE.
- Remaining failed or blocked criteria: all pending.
- ClickUp final evidence comment: pending.
