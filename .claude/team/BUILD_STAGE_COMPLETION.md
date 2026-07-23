# `/build` Stage Completion Predicates

Each stage creates a child Goal Contract. The stage reaches `GATE_REVIEW` only when every mandatory criterion below is evidenced or the gate is explicitly presented as `BLOCKED`. User approval authorises progression; it does not convert failed verification into a pass.

## Stage 0 — Bootstrap and intake

- A valid Build Goal Contract and Stage 0 Goal Contract exist.
- ClickUp MCP access is verified and one Build Control task is located or created.
- Repository, environments, current artefacts, active work, and relevant tools are inventoried.
- The product goal, target users, desired outcome, constraints, non-goals, and apparent scope are stated.
- Unknowns are classified as blocker, important assumption, or detail.
- Required specialist roles and the stage plan are proposed with reasons.
- Build state pointer links ClickUp and the active Goal Contract.

## Stage 1 — Product discovery and requirements

- Current-state findings distinguish verified behaviour from assumptions.
- Users, jobs, permissions, workflows, rules, edge cases, integrations, risks, non-goals, and success metrics are defined.
- Requirements have stable IDs and independently testable acceptance criteria.
- Research claims link to evidence and unresolved questions have owners/dispositions.
- PRD traceability and product audit are complete.
- The PRD is ready for user approval or the exact blockers are presented.

## Stage 2 — Solution architecture and experience

- Approved requirements map to architecture and design decisions.
- Architecture covers components, data, APIs/events, permissions, failure modes, compatibility, migration, observability, and rollback.
- Material trade-offs have ADRs or explicit pending decisions.
- UX covers complete flows, states, responsive/platform behaviour, accessibility, content, errors, and recovery.
- Early security/privacy threats and controls are documented.
- Cross-discipline conflicts are resolved or presented as gate decisions.

## Stage 3 — ClickUp delivery plan

- Existing work was searched before creation.
- Every approved requirement is covered by at least one ClickUp item or explicit deferral.
- Epics, stories, tasks, bugs, and spikes satisfy the ClickUp Task Schema.
- Dependencies are valid, acyclic, and identify the critical path.
- Ownership, priorities, milestones, verification expectations, and definition of done are present.
- The first implementation batch is independently actionable and all blocking inputs are linked.

## Stage 4 — Implementation batch

- Every task in the approved batch has a Goal Contract and selected execution engine.
- Code/configuration/doc changes match approved scope and repository conventions.
- Task-level completion predicates and focused tests pass.
- Required migrations, observability, feature controls, compatibility, and rollback are implemented or explicitly not applicable.
- Self-review evidence is recorded and tasks are ready for independent review; they are not falsely marked done.
- Known out-of-scope findings are linked as ClickUp follow-ups.

## Stage 5 — Independent verification

- Code review, security review, and QA goals cover the complete changed scope.
- Requirements-to-tests traceability is complete.
- Applicable unit, integration, end-to-end, exploratory, accessibility, performance, migration, and recovery checks have evidence.
- No unresolved Blocker or High finding remains unless an authorised human explicitly accepts the residual risk.
- Remediated findings were re-tested by the appropriate independent role.
- A release-quality verdict is produced with untested areas and residual risks explicit.

## Stage 6 — Release readiness

- CI/CD, configuration, secrets handling, deployment sequence, migrations, rollback, backup/restore, observability, alerts, runbooks, support, and release notes are verified.
- Production steps and owners are exact and reversible where required.
- Go/no-go criteria and rollback triggers are explicit.
- No required release evidence is missing.
- The stage stops for explicit production approval.

## Stage 7 — Release and closeout

- Only the approved production actions were executed.
- Deployment/migrations completed or rollback was executed according to criteria.
- Smoke tests and critical user journeys pass in the approved environment.
- Monitoring evidence covers the approved observation window and thresholds.
- ClickUp tasks, release evidence, known issues, residual risks, support notes, and follow-ups are updated.
- The Build Goal Contract's full completion predicate passes.
- The user confirms closure before the Build Control task is marked complete.
