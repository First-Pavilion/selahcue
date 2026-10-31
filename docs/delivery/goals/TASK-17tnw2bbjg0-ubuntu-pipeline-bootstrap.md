# Goal Contract — TASK-17tnw2bbjg0-ubuntu-pipeline-bootstrap

## Identity

- Goal ID: TASK-17tnw2bbjg0-ubuntu-pipeline-bootstrap
- Parent goal ID: TASK-86ak0qn4j-linux-installer
- Title: Make the manually dispatched main-only Ubuntu packaging pipeline available as a source prerequisite
- Role: devops-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2bbjg0
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Make the executable Ubuntu packaging/validation pipeline safely available on main, so an authorized owner can subsequently execute the existing Linux installer ticket. This source-only prerequisite does not assert that any Linux installer has been built, installed or accepted.

## Baseline

PR325 initially attempted source and runtime scope under 86ak0qn4j, frozen at a680e025. Original mandatory C-004 could not be satisfied by source checks. Aria's 2026-10-31 architecture decision and verified ClickUp ticket17tnw2bbjg0 prospectively split the bootstrap before approval or merge. The same source, PR325 and legacy branch codex/86ak0qn4j-linux-installer remain; no duplicate code/PR or runtime evidence waiver. Current main6bdf61c7 was merged without rewriting published history.

## Inputs and evidence sources

- Verified source-only ClickUp ticket17tnw2bbjg0 and owner manual-main decision
- Aria Linux bootstrap sequencing decision and non-NDI architecture decision
- Existing original goal TASK-86ak0qn4j-linux-installer.md, with mandatory C-004 still BLOCKED
- Pinned Tauri parser2.10.1, scanner policy and executable regression controls

## Scope

### In scope

- Linux-effective Debian config preserving Windows, real release/default-encryption/non-NDI sidecar staging, ELF/hash/unchanged unpacked-marker controls
- Fail-closed manual exact-main workflow with dispatch-SHA checkout/provenance and executable real installed-runtime probe source
- Inexpensive source regressions, truthful metadata/runbook, normal CI and four new scoped independent reviews

### Non-goals

- Native package creation/install/IPC/frame/uninstall acceptance or clean-location validation: mandatory existing86ak0qn4j and P18 remain responsible
- Actual dispatch, real provider keys, pilot scanner exception, signing, bucket/publication, API/mobile/marketing/Rust behavior changes

### Constraints

- One existing published branch/PR, isolated owned worktree; do not revert others
- Workflow_dispatch AND exact refs/heads/main before packaging/keys/upload; checkout authorized dispatch SHA
- No placeholders, debug assertions, disabled default encryption or NDI feature in Linux candidate

### Assumptions and unknowns

- Source controls can validate pipeline admission/staging behavior but cannot establish native installer readiness
- Future main execution can fail; fix/review/retry on main and retain honest blocked runtime status

## Dependencies and approvals

- Root authorized this prospective atomic source split against Aria decision and verified ticket; root owns browser updates, reviews and merge
- Required delivery sequence: this bootstrap -> existing86ak0qn4j actual main execution -> existing P18 clean-location validation
- No dispatch or public publication occurs in this source unit

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Effective Linux config selects deb/no Windows DLL and retains real external output; Windows base preserved | actual pinned Tauri parser and packaging regressions | Linux/Windows merge and placeholder negative controls pass | runbook/parser evidence and tests | PASS |
| C-002 | yes | Source checks enforce release/default encryption/non-NDI staging, ELF closure/hash validation and unchanged uncompressed marker scan before upload | positive/negative packaging tests and scanner selftests | fail closed for invalid source/artifact/scanner fixtures | packaging14/scanner45 cases | PASS |
| C-003 | yes | Workflow only accepts explicit dispatch on exact main with SHA checkout and provenance before build/upload; normal CI only focused source checks | workflow/cost mutation suites and actionlint | automatic/branch/tag packaging refused | workflow118/cost and source checks | PASS |
| C-004 | yes | Installed-runtime probe source requires actual IPC true/frame checks; metadata/docs preserve native evidence limits and original mandatory goal | regression controls and original goal/runbook comparison | demo cannot pass; original C004 BLOCKED/NOT RUN remains mandatory, P18 retained | tests and cross-linked original contract | PASS |
| C-005 | yes | Normal automatic CI passes on revised immutable head without packaging | recorded GitHub CI checks for exact head | required normal checks green | root CI evidence pending | PENDING |
| C-006 | yes | Four new independent scoped bootstrap reviews pass and blocking findings are resolved | Cody/Shadow/Quinn/Vera against revised head/contract | all pass, not recycled original-scope approvals | root review evidence pending | PENDING |

## Verification plan

- Focused verification: packaging14, unchanged scanner45, workflow118 and cost mutation controls, actionlint
- Broader regression verification: P06 tests14, actual pinned Tauri Linux/Windows parser probe and normal CI
- Independent verifier: root-coordinated fresh Cody/Shadow/Quinn/Vera reviews
- Required environment: Python/PyYAML/actionlint; native main run is downstream evidence, not performed by this source prerequisite

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-004
- Hypothesis: explicit source-only prerequisite removes the main-only workflow availability cycle without waiving runtime evidence
- Change or investigation: preserve original goal and mandatory C004, add this bounded contract, retarget same PR and runbook, merge current main
- Verifier executed: packaging/P06/scanner/workflow/cost/actionlint and both structural contracts
- Result: source controls pass; normal CI and new four-review verdicts pending
- New evidence: docs/ops/LINUX-INSTALLER.md; original goal and source tests; private parser/emulated Ubuntu logs
- Decision: fresh independent review and normal CI before source merge

## Risks and rollback

- Risks: main execution may expose build/runtime failures; source completion means pipeline availability only
- Rollback or recovery: revert Linux-only source pipeline; retain existing installer ticket and blocked actual proof; no production data migration or live infra

## Pause and escalation conditions

- Failed source guard/scanner or blocking independent review prevents merge
- Any runtime/pilot/publication completion claim without actual evidence is outside this prerequisite

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbjg0-ubuntu-pipeline-bootstrap.md
- Validator result: structural validation required before handoff; completion not asserted
- Independent verification result: fresh four-review verdicts pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C005 normal CI and C006 four new scoped reviews
- ClickUp final evidence comment: root coordinates browser update
