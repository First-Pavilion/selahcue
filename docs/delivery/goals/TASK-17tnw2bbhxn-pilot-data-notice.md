# Goal Contract — TASK-17tnw2bbhxn-pilot-data-notice

## Identity

- Goal ID: TASK-17tnw2bbhxn-pilot-data-notice
- Parent goal ID: NONE
- Title: Explain pilot registration collection and deletion
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhxn
- Created: 2026-11-03
- Updated: 2026-11-03
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Show the approved pilot collection purpose and handling notice before registration, with a coherent deletion procedure and separate optional marketing/cloud consent.

## Baseline

Main 4e2ce4374713956a498978fdf6383c74c2c548cb. P14 website and P13 inactive workflow source are merged. The existing form notice is a placeholder. Collection and marketing downloads remain disabled.

## Inputs and evidence sources

- ClickUp P15 description/comments; current P13/P14 source.
- Current owner authorization relayed by root: tester owns church data; legal@selahcueapp.com primary deletion contact, support@selahcueapp.com alternate; root selected pilot-end plus90days retention ending2027-07-29T23:59:59Z. This describes product policy, not a conclusion about statutory controller roles.

## Scope

### In scope

- Static marketing notice route/link; pre-submit inactive n8n form notice and matching notice version; operator restricted-access/deletion instructions.

### Non-goals

- No collection enablement, credential creation, live Google changes, retention engine, broad platform legal rewrite or public deployment.

### Constraints

- Do not alter fixed-row allocation or erase outstanding ledger bindings. No fabricated release availability or configured endpoints.

### Assumptions and unknowns

- Restricted Sheet administrator, dedicated deployment credentials, deletion execution/backup retention proof and live end-to-end collection remain operational dependencies.

## Dependencies and approvals

- Owner supplied data ownership/deletion contacts and delegated retention selection. Root owns review/merge/status. Existing technical enabled gates remain unchanged.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Before submission visitors can read purpose, necessary fields, n8n/Sheets handling and deletion contacts/deadline | Actual marketing route and exact generated form inspection | Clear readable notice and working links | docs/delivery/evidence/p15-pilot-data-notice.md | PASS |
| C-002 | yes | Marketing optional and separate; no account/payment requirement; cloud consent separate | Actual rendered marketing/form text | No bundled consent or prerequisite | docs/delivery/evidence/p15-pilot-data-notice.md | PASS |
| C-003 | yes | Procedure records restricted access, fixed-row clearing and operational retention/config limits without enabling collection | Workflow generation checks, focused regression tests, build/lint and procedure inspection | Reproducible inactive export and safe no-enable diff | docs/delivery/evidence/p15-pilot-data-notice.md | PASS |
| C-004 | yes | Independent Cody Shadow Quinn Vera approve current source | Root-coordinated review | All four pass | docs/delivery/evidence/p15-pilot-data-notice.md | PENDING |

Allowed criterion statuses: PENDING, PASS, FAIL, BLOCKED, NOT_APPLICABLE.

## Iteration ledger

### Iteration 1

- Selected criterion: C-001.
- Hypothesis: One shared readable policy statement in marketing and the inactive form removes the placeholder without enabling collection.
- Plan: Add notice route/link, form text/version and an operator runbook, then verify generated graph/actual browser/build.
- Result: Shared notice, real marketing route and inactive pre-submit form description implemented. Build/lint/1246 regression tests and both42-check focused responsive engine runs pass. Required independent review remains pending.

### Iteration 2

- Selected criterion: C-003, Cody CODY-P15-01.
- Hypothesis: Attempt-only copy removes the false receipt lifetime claim without changing behavior.
- Plan: Correct the public label, clarify the runbook's two clocks and verify against actual service consumers plus focused tests/build/lint.
- Result: UI/service clock check PASS; focused51tests/build/typecheck/lint PASS. Independent final reviews remain pending. Local-only remediation; no remote publication attempted.

## Risks and rollback

- Procedure is not an implemented deletion service. Production remains disabled pending operational checks. Revert this source unit to restore prior inactive notice.

## Pause and escalation conditions

- Stop if implementing notice would require live service credentials, owner decisions beyond supplied policy or weakening existing gates.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbhxn-pilot-data-notice.md
- Validator result: Structural PASS.
- Independent verification result: Pending.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: C-004 independent reviews pending; actual pinned n8n rendering remains separately disclosed verification limit.
- ClickUp final evidence comment: Root owns publication.
