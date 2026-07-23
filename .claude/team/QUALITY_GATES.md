# Quality Gates

Apply only gates relevant to the change, but document why a gate is not applicable. No quality gate may pass without an active validated Goal Contract and evidence-backed completion predicate.

## Goal execution

- Goal Contract validates before and after execution.
- Selected engine is `goal` or `ralph`.
- Every mandatory criterion has a verifier, expected result, evidence, and `PASS` status.
- Required independent verification is complete.
- No criterion was weakened to hide failure.

## Product readiness

- Problem, users, goals, non-goals, metrics, requirements, edge cases, dependencies, and decision owners are clear.
- PRD audit is approved by the user before ClickUp implementation work is created.

## Business/domain readiness

- Processes, rules, permissions, calculations, data definitions, integrations, and exceptions are testable.

## Architecture readiness

- Contracts, data model, failure modes, security, migration, observability, compatibility, and rollback are explicit.
- Material decisions have ADRs.

## Design readiness

- Complete flows and states exist for target platforms.
- Accessibility and responsive/platform behaviour are testable.
- Precise design references are linked.

## Implementation readiness

- Active ClickUp task meets the task schema.
- Dependencies are unblocked or intentionally sequenced.
- Tests and observability are part of scope.

## Code review

- No unresolved Blocker or High correctness/reliability findings.
- Tests meaningfully cover changed behaviour.
- Performance and maintainability risks are addressed.

## Security/privacy

- Threats and data handling are assessed proportionally.
- No unresolved release-blocking findings.
- Accepted risk names an authorised human owner.

## QA

- Acceptance criteria have evidence.
- Happy, edge, permission, integration, recovery, and regression paths are covered proportionally.
- Failures and untested areas are explicit.

## Operational readiness

- CI/CD, migration, configuration, observability, backup/restore, rollback, runbooks, support, and release notes are ready.

## Release

- Gate 6 receives explicit user approval before production action.
- Smoke checks and monitoring confirm release health.
- Known issues and follow-ups are in ClickUp.
