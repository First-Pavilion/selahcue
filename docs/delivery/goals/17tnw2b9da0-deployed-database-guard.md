# Goal Contract — TASK-17tnw2b9da0

## Identity

- Goal ID: TASK-17tnw2b9da0
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Refuse deployed SQLite and public database password defaults
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9da0
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Settings import refuses missing/blank or SQLite SQL_ENGINE and missing/blank or default SQL_PASSWORD outside exact dev, while dev retains current SQLite/default-password behavior and configured PostgreSQL works.

## Baseline

Freshly fetched main `6a1f414cc3213006b333a071893db394ffd03039` includes PR267 DEBUG/header guards and PR270's narrow omitted-environment guard. _database_config still defaults SQL_ENGINE to SQLite and non-SQLite SQL_PASSWORD to public postgres in every environment. DATABASES initializes after ENVIRONMENT, so a guard can reuse the established exact-dev boundary. Prior hosted API1976pass/1intentional-study-skip is baseline evidence only.

## Inputs and evidence sources

- Complete task/comments/dependencies in wave2-20261029/api-qualification/17tnw2b9da0.json:0comments,0dependencies; linked previous PR225 ticket.
- Acceptance: outside dev refuse unset/SQLite SQL_ENGINE with named SQL_ENGINE and ENVIRONMENT; refuse unset/default SQL_PASSWORD with named SQL_PASSWORD; positive dev/default and real configured PostgreSQL controls; docs rows and drift green.
- Existing hermetic fresh-settings/subprocess helpers, deployment matrices, TLS proxy controls and env-doc inventory.

## Scope

### In scope

- Import-time deployed database configuration guards and actionable fixed messages without secret values.
- Empty/whitespace-only required engine/password values count as missing; password default comparison is exact postgres, with no strength or normalization policy.
- Meaningful negative and positive tests, configured non-dev inputs in adjacent guard tests, accurate database docs/sample comments and this goal.

### Non-goals

- Backend allowlist beyond refusing SQLite/missing engine, credential provisioning/rotation, production deployment, data migration, PR233, audit/reason work, changes to prior approved DEBUG/header/environment boundaries.

### Constraints

- No local project runtime, Django imports, pytest, database setup, containers or builds under host paging. Parent owns hosted RED/GREEN and all independent reviews.
- No production changes before actual behavioral RED. Parent owns ClickUp, push/publication/PR, merge and QA. No extra agents or next API ticket.
- Shared repository: preserve other agents' work and closed source branches.

### Assumptions and unknowns

- The task requires refusal of unset or SQLite, not a new PostgreSQL-only backend allowlist or password entropy policy.
- Existing non-dev settings/control tests must explicitly configure legitimate database inputs once guarded, rather than weakening the guard or accepting a wrong earlier error.
- Actual deployment configuration/provisioning remains the owner's responsibility, separate from hosted evidence.

## Dependencies and approvals

- User authorizes implementation, valid remediation, all four independent reviews, green-CI merge and QA; parent orchestrates external actions.
- PR267 and PR270 are merged and preserved.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Every non-dev spelling refuses missing/blank and SQLite engines naming SQL_ENGINE and ENVIRONMENT | fresh-settings negative engine matrix | all named refusals pass | wave2-20261029/api-database-guard/verification.log | PENDING |
| C-002 | yes | Every non-dev spelling refuses missing/blank or public-default password without echoing values | fresh-settings negative password matrix | all named refusals pass | wave2-20261029/api-database-guard/verification.log | PENDING |
| C-003 | yes | Dev retains SQLite/defaults and configured PostgreSQL imports/connects in hosted environment | fresh-settings positives and hosted subprocess SELECT1 | controls pass; hosted connection succeeds | hosted RED/GREEN logs | PENDING |
| C-004 | yes | Adjacent guard tests preserve their intended assertions with legitimate non-dev configs and docs inventory stays accurate | hosted full deployment/TLS/docs suites and inspection | no masked intended errors; docs tests pass | parent API CI | PENDING |
| C-005 | yes | API checks/migrations/regression plus Cody Quinn Vera Shadow pass frozen source | hosted full API job and independent review round | CI green and no unresolved findings | parent gate evidence | PENDING |
| C-006 | yes | PR merged and exact ticket QA persisted | parent delivery readback | merge and QA verified | parent delivery evidence | PENDING |

## Verification plan

- Focused: engine/password refusal matrices across established non-dev spellings, dev default controls, configured PostgreSQL field assertions and hosted startup/connection positive.
- Broader: full existing API job with PostgreSQL16/Redis7/Python3.14, Django checks, migration consistency, prior deployment guards, TLS and docs drift.
- Independent verifier: Cody, Quinn, Vera and Shadow through parent.
- Required environment: hosted existing services. No local project runtime.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: new settings-import tests demonstrate the deployed fail-open defaults and valid configuration boundaries before implementation.
- Change or investigation: full task read, fresh main/worktree, existing prod/control paths identified, test-only matrices and hosted live-connection control prepared.
- Verifier executed: stdlib syntax, diff check and structural goal validation only.
- Result: test-only candidate prepared; actual hosted RED pending; production unchanged.
- New evidence: wave2-20261029/api-database-guard/test-only-manifest.json.
- Decision: handoff

## Risks and rollback

- Risks: non-dev deployments using absent/SQLite engine or absent/default password intentionally refuse startup. Adjacent tests must use valid unrelated configuration.
- Rollback or recovery: configure the intended row-locking database and real password. Revert this ticket only recognizing that it restores the fail-open defaults; no database data is changed by these checks.

## Pause and escalation conditions

- Policy expansion, production credential/deployment requests, or a prerequisite conflict go to parent.
- Missing hosted runtime evidence prevents completion; host paging prohibits local heavy work.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9da0-deployed-database-guard.md
- Validator result: initial structural validation, stdlib test syntax and diff check PASS.
- Independent verification result: pending parent orchestration.
- Terminal state: IN_PROGRESS
- Remaining failed or blocked criteria: hosted RED/GREEN and all review/delivery gates pending.
- ClickUp final evidence comment: parent owns publication.
