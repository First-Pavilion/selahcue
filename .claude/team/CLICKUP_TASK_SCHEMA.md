# ClickUp Task Schema

Every implementation-ready task should contain the following fields in its description or mapped custom fields.

## Identity

- Outcome-oriented title
- Type: Epic, Story, Task, Bug, Spike, Security, Documentation, or Release
- Parent epic / Build Control link
- Accountable owner or owner role
- Supporting roles

## Goal execution

- Goal ID and Goal Contract path
- Parent Build/Stage goal
- Execution engine: `goal` or `ralph`
- Maximum iterations
- Observable objective
- Completion predicate summary
- Required independent verifier
- Terminal state and final evidence comment

## Context

- User/business problem
- Current behaviour
- Desired observable outcome
- Links to PRD, research, business rules, design, ADR, API/data contract, or incident

## Scope

- In scope
- Explicitly out of scope
- Dependencies and blockers
- Assumptions and constraints
- Data, privacy, security, accessibility, and operational notes

## Acceptance criteria

Use independently testable statements covering relevant:

- Happy path
- Validation and boundaries
- Loading/empty/error states
- Permissions and tenant isolation
- Failure and recovery
- Concurrency/idempotency
- Responsive/platform behaviour
- Analytics/observability
- Migration/compatibility

## Verification expectations

- Required test levels
- Existing fixtures/helpers to reuse
- Manual or exploratory checks
- Performance/security checks
- Evidence to attach or link

## Definition of done

- Code/config/documentation complete
- Automated checks pass
- Code review resolved
- Security and QA gates pass when applicable
- Migration/deployment/rollback addressed
- Observability and support impact addressed
- Goal Contract validator passes
- Every mandatory completion criterion is `PASS` with evidence
- Required independent verification passes
- ClickUp final predicate/evidence comment added
- Follow-up work linked

## Bug additions

- Environment/build/version
- Reproduction steps
- Expected and actual result
- Frequency
- Impact and severity rationale
- Logs/screenshots/traces
- Regression status

## Spike additions

- Decision question
- Time/effort boundary
- Options to compare
- Evidence required
- Output and decision owner
- No production implementation unless separately approved
