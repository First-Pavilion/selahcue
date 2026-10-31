# Goal Contract — TASK-17tnw2bbhxf-manual-main

## Identity

- Goal ID: TASK-17tnw2bbhxf-manual-main
- Parent goal ID: NONE
- Title: Windows installer packaging accepts manual main dispatch only and records source SHA
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhxf
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Deliver the first independent packaging increment: reject all non-manual/non-main packaging before job execution, pin checkout to the dispatch SHA, and retain source metadata with the installer artifact.

## Baseline

Verified main 93bf472: windows-installer.yml has workflow_dispatch only, but no job-level event/ref gate, implicit checkout ref, and no uploaded source metadata. This is not a working expiring-key pilot release yet.

## Inputs and evidence sources

- Owner manual/main-only decision, 2026-10-31, and ClickUp task 17tnw2bbhxf
- .github/workflows/windows-installer.yml
- .github/scripts/check_workflows.py
- docs/ops/WINDOWS-INSTALLER.md

## Scope

### In scope

- Manual-main job guard, immutable checkout SHA, artifact source metadata
- Existing workflow checker regression coverage, runbook update

### Non-goals

- Pilot provider keys/profile/scanner-policy exception, Ubuntu/macOS packaging, bucket provisioning/publication
- Running paid packaging builds, deployment, merging, changing normal CI triggers

### Constraints

- Agent-owned worktree and one ticket branch; no source checkout edits
- No secret values in code, metadata or logs

### Assumptions and unknowns

- UNKNOWN: Windows end-to-end packaging remains unexecuted in this increment
- P01/P02/P04 remain dependencies for full pilot installer acceptance

## Dependencies and approvals

- Owner authorizes engineering kickoff and manual main-only packaging
- Independent code/security/performance/QA review remains required before ticket completion

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Existing workflow checker rejects nonmanual triggers, missing/broadened main guard and mutable checkout ref | checker self-test and actual workflow scan | negative controls reject; real workflow passes | 117 baseline cases, then 118 with empty-job control; real workflow passes | PASS |
| C-002 | yes | Windows YAML validates and existing cost guard remains green | actionlint; check_ci_minutes.py self-test and real | exit 0 | actionlint and both CI-minute checks exit 0 | PASS |
| C-003 | yes | Source metadata contains source SHA/ref/event/run and is uploaded with installer | inspect actual metadata construction and upload/preflight configuration | required keys and uploaded file pinned | workflow diff: SHA/env metadata, Get-ChildItem required installer preflight, combined artifact paths | PASS |
| C-004 | yes | Independent review of this increment passes | Cody/Vera/Shadow/Quinn review | no blocking finding | parent coordination | PENDING |

## Verification plan

- Focused verification: workflow checker self-tests and actual YAML
- Broader regression verification: actionlint and existing CI-minute guard
- Independent verifier: parent-coordinated specialists
- Required environment: Python3/PyYAML/actionlint; no Windows runner or secrets

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003
- Hypothesis: strict workflow invariants prevent accidental trigger/ref regressions without adding CI jobs
- Change or investigation: inspect existing packaging/checker and add negative regression cases before production edit
- Verifier executed: check_workflows self-test and all workflows; check_ci_minutes self-test and all workflows; actionlint; git diff --check
- Result: initial real-workflow check failed on missing guard and implicit checkout (RED); amended workflow passes (GREEN). Existing workflow/cost checks remain green.
- New evidence: adding a second artifact path can mask a missing installer; added a required-NSIS preflight before upload. Windows/PowerShell execution remains unverified locally.
- Decision: handoff

## Risks and rollback

- Risks: local/static proof does not prove Windows installer success or live GitHub dispatch behavior
- Rollback or recovery: revert this ticket branch; no infrastructure or secret changes made

## Pause and escalation conditions

- Full pilot profile depends on Nova/expiry decisions; return increment to parent without claiming full ticket complete

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbhxf-manual-main.md
- Validator result: structural validation passed
- Independent verification result: pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: independent review and unimplemented full-ticket dependencies
- ClickUp final evidence comment: root owns browser updates
