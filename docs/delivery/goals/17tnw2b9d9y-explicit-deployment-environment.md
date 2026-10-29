# Goal Contract — TASK-17tnw2b9d9y

## Identity

- Goal ID: TASK-17tnw2b9d9y
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Refuse an unset deployment environment with an empty key and non-local hosts
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9d9y
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Settings import refuses genuinely unset ENVIRONMENT when the raw SECRET_KEY is absent/empty and any allowed host is non-local, while preserving explicit dev, bare local development, and the approved DEBUG/header bridge guards.

## Baseline

Freshly fetched main `0d3d3da8658985ad6dbb758933557dbc18df1c59` includes merged PR267. No ENVIRONMENT becomes dev and an empty raw key becomes the public dev key before ALLOWED_HOSTS is read. The current test explicitly pins the unsafe omitted-environment behavior and the docs describe unconditional silent fallback. The prior hosted API gate passed1935tests with1intentional study skip; that is baseline evidence, not this ticket's verification.

## Inputs and evidence sources

- Complete saved ClickUp task/comments/dependencies: wave2-20261029/api-qualification/17tnw2b9d9y.json; its comments payload is complete and empty, dependencies empty.
- Task acceptance expressly permits option(a): “raise ImproperlyConfigured naming ENVIRONMENT when it is genuinely unset (not explicitly dev), SECRET_KEY is empty and DJANGO_ALLOWED_HOSTS names a host other than localhost, 127.0.0.1, ::1 or testserver”.
- Qualification report selects that narrow option(a); parent explicitly authorized it. Option(b) requires unverified Coolify Docker build evidence and is not selected.
- Existing env_list, fresh-settings hermetic helpers, deployed secret guards and env-doc inventory tests.

## Scope

### In scope

- Import-time detection of the exact unset-environment/empty-raw-key/non-local-host combination.
- Local allowlist localhost, 127.0.0.1, ::1 and testserver; support bracketed IPv6 loopback already present in the sample configuration.
- Regression and positive controls, deployment docs and stale doc-predicate update.

### Non-goals

- Universal deployment detection; changing explicit dev or configured-key behavior; staff IdP; DEBUG/header policy changes; Dockerfile/Coolify changes; database configuration guard from separate17tnw2b9da0; production deployment/config audit.

### Constraints

- No local project runtime, Django imports, pytest, database setup, containers or builds under host paging. Parent runs hosted RED/GREEN and all reviews.
- No source change before behavioral RED. Parent owns ClickUp, publication/push/PR, merge and QA; all other API tickets remain queued.
- Shared worktrees: preserve all other agents' edits; closed PR267 branch is immutable.

### Assumptions and unknowns

- This is the explicitly permitted narrow option(a), not proof that every real deployment is detected. Explicit dev and an intentionally configured raw key are outside this guard.
- The task's separate owner audit of existing deployed keys remains outside implementation evidence.
- Coolify Docker build provenance is unverified and unnecessary because option(b) is not selected.

## Dependencies and approvals

- User authorizes implementation, all four independent reviews, valid author remediation, green-CI merge and QA; parent orchestrates external actions.
- PR267 DEBUG/header policy is merged and must remain valid.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Genuinely unset environment with absent/empty raw key and any non-local allowed host refuses settings import naming ENVIRONMENT | new fresh-settings negative matrix and legacy-variable regression | expected refusals pass | wave2-20261029/api-explicit-environment/verification.log | PENDING |
| C-002 | yes | Local defaults, IPv6 loopback, explicit dev and configured-key boundaries remain supported; empty environment keeps existing deployed-key refusal | focused positive controls | all controls pass | wave2-20261029/api-explicit-environment/verification.log | PENDING |
| C-003 | yes | Both deployment guides accurately describe the narrow new behavior and env inventory remains consistent | env-doc tests and source/doc inspection | no unconditional silent-fallback claims; docs tests pass | hosted CI and author handoff | PENDING |
| C-004 | yes | Approved DEBUG/header policy and broader API behavior remain valid | hosted complete API job including deployment guard suite | all tests/checks/migrations pass | parent hosted CI evidence | PENDING |
| C-005 | yes | Frozen source passes Cody Quinn Vera Shadow and CI | parent independent review round | no unresolved findings and CI green | parent review evidence | PENDING |
| C-006 | yes | PR merged and exact ticket moved to QA with persisted readback | parent delivery checks | merge and QA verified | parent delivery evidence | PENDING |

## Verification plan

- Focused: fresh-settings negative host/key matrix and positive local/explicit/configured boundaries; updated legacy-variable regression; updated docs explanation assertion.
- Broader: hosted API job with PostgreSQL/Redis, all deployment guards including PR267, env-doc drift, checks and migration consistency.
- Independent verifier: Cody, Quinn, Vera and Shadow through parent.
- Required environment: existing hosted Python3.14/PostgreSQL16/Redis7 setup. No local project runtime.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002, C-003.
- Hypothesis: the narrow accepted option(a) catches the omitted-environment legacy-doc deployment without breaking intentional local dev.
- Change or investigation: read complete task and owner comments, fetch main, create isolated worktree and prepare tests before production changes.
- Verifier executed: static syntax, diff check and structural contract validation only.
- Result: actual hosted RED40944471627 on source6616cac2 produced18failed/25passed in1.65s:17behavioral DID NOT RAISE failures plus1stale documentation explanation failure. No setup failures; production was unchanged.
- New evidence: wave2-20261029/api-explicit-environment/red.log and https://github.com/First-Pavilion/selahcue/actions/runs/40944471627
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-004.
- Hypothesis: check raw configuration before public-key fallback, using the exact accepted local-host allowlist.
- Change or investigation: move existing allowed-host parsing before secret fallback; add the conjunctive import-time refusal and actionable fixed error; describe exact boundaries in both deployment guides and sample comments. Preserve explicit dev, configured-key behavior, existing non-dev guards and database configuration.
- Verifier executed: stdlib syntax, diff check, structural goal validation and source inspection only; no local project runtime.
- Result: candidate prepared for hosted GREEN and all independent gates, which remain pending.
- New evidence: wave2-20261029/api-explicit-environment/candidate-manifest.json and verification.log.
- Decision: gate-review

## Risks and rollback

- Risks: an operator relying on an omitted ENVIRONMENT with an empty key and a non-local host will now receive an intentional startup refusal. Explicit dev remains intentional opt-in; configured keys remain outside this narrow check.
- Rollback or recovery: configure ENVIRONMENT=staging/prod and a real key for deployment, or explicit dev for trusted local development. Reverting this ticket restores the unsafe omitted-environment case.

## Pause and escalation conditions

- Do not broaden option(a) or change deployment policy without parent routing.
- Missing hosted runtime evidence blocks verified completion; local resource pressure is not permission for heavy tests.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9d9y-explicit-deployment-environment.md
- Validator result: structural validation PASS; candidate source/test syntax and diff checks PASS.
- Independent verification result: pending parent orchestration.
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: hosted GREEN, full API regression, all four independent reviews, merge and exact QA readback remain pending.
- ClickUp final evidence comment: parent owns publication.
