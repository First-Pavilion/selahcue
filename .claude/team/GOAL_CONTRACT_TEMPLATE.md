# Goal Contract — <goal-id>

## Identity

- Goal ID: <BUILD-or-STAGE-or-TASK-id>
- Parent goal ID: <goal-id-or-NONE>
- Title: <observable outcome>
- Role: <skill-name>
- Status: DRAFT
- Execution engine: goal
- ClickUp task: <URL-or-NONE>
- Created: <ISO-8601>
- Updated: <ISO-8601>
- Maximum iterations: 8
- Independent verification required: yes

## Objective

<One observable outcome.>

## Baseline

<Verified current state before work begins.>

## Inputs and evidence sources

- <source>

## Scope

### In scope

- <item>

### Non-goals

- <item>

### Constraints

- <constraint>

### Assumptions and unknowns

- <ASSUMED or UNKNOWN item and validation owner>

## Dependencies and approvals

- <dependency, owner, and status>

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | <boolean observable condition> | <command/review/check> | <exact expected result> | <path/link/output> | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: <checks>
- Broader regression verification: <checks>
- Independent verifier: <role/person/check>
- Required environment: <environment>

## Iteration ledger

### Iteration 1

- Target criterion:
- Hypothesis:
- Change or investigation:
- Verifier executed:
- Result:
- New evidence:
- Decision: iterate | handoff | blocked | gate-review | complete

## Risks and rollback

- Risks:
- Rollback or recovery:

## Pause and escalation conditions

- <condition and owner>

## Final evaluation

- Validator command:
- Validator result:
- Independent verification result:
- Terminal state:
- Remaining failed or blocked criteria:
- ClickUp final evidence comment:
