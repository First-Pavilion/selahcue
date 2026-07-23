---
name: build
description: Manually starts or resumes the complete gated AI software development workflow. It coordinates specialist skills, ClickUp delivery, repository artefacts, implementation, verification, and release readiness, pausing after every stage for user input.
argument-hint: "[product goal, feature request, ClickUp task URL, or resume]"
disable-model-invocation: true
user-invocable: true
effort: high
version: 3.0.0
---

# Build — AI Software Development Team

## Invocation contract

This is the single point of contact for the AI development team and must be invoked manually as:

```text
/build <goal, feature, ClickUp task URL, or resume instruction>
```

Never activate this skill automatically. Never bypass a stage gate, even when the user asks to “build everything,” “continue autonomously,” or supplies broad approval. Approval applies only to the current gate unless the user explicitly refines the current stage.

Do not use `context: fork`; the workflow must remain in the main conversation so the user's stage decisions and corrections remain authoritative.

## Mission

Coordinate Product Manager, Product Researcher, Business Analyst, Delivery Manager, Software Architect, UI/UX Designer, Frontend Engineer, Backend Engineer, Mobile Engineer, AI Engineer, Code Reviewer, Security Reviewer, QA Engineer, DevOps Engineer, and Documentation Writer as one evidence-driven team.

The skill may build a new product, add a feature, audit and complete an existing product, fix a bug, modernise a system, or resume a previously paused build.

## Required shared files

Read these before proceeding:

- `.claude/team/GOAL_EXECUTION_PROTOCOL.md`
- `.claude/team/BUILD_STAGE_COMPLETION.md`
- `.claude/team/GOAL_CONTRACT_TEMPLATE.md`
- `.claude/team/WORKFLOW.md`
- `.claude/team/BUILD_GATES.md`
- `.claude/team/CLICKUP_WORKFLOW.md`
- `.claude/team/CLICKUP_TASK_SCHEMA.md`
- `.claude/team/QUALITY_GATES.md`
- `.claude/team/ROLE_MATRIX.md`
- `.claude/team/ARTIFACTS.md`
- Repository `CLAUDE.md` and nested guidance

## Goal-driven orchestration

`/build` is a supervisory goal tree, not an unstructured sequence of role calls.

At Stage 0:

1. Create a Build Goal Contract at `docs/delivery/goals/BUILD-<slug>.md`.
2. Define the overall product outcome, constraints, non-goals, release-level completion predicate, evidence requirements, and terminal conditions.
3. Select the execution engine for child goals according to `.claude/team/GOAL_EXECUTION_PROTOCOL.md`.
4. Link the Build Goal Contract from the ClickUp Build Control task and `docs/delivery/BUILD_STATE.md`.

Before every stage:

1. Create a Stage Goal Contract whose parent is the Build Goal.
2. Translate `.claude/team/BUILD_STAGE_COMPLETION.md` into project-specific Boolean criteria.
3. Create task/verification child goals for each specialist assignment.
4. Invoke the bundled `goal` skill for each child by default, or Ralph Loop when selected.
5. Do not present a stage gate until the Stage Goal reaches `GATE_REVIEW` or a truthful `BLOCKED`/`FAILED_LIMIT` state.

A stage engine must stop at the user gate. `continue` authorises creation and execution of only the next Stage Goal; it never approves all remaining work.

## Build completion condition

The Build Goal is `VERIFIED_COMPLETE` only when:

- every required Stage Goal and task/verification child goal is `VERIFIED_COMPLETE`;
- every approved product requirement is evidenced in the released product or explicitly deferred by an authorised decision;
- applicable product, architecture, design, code review, security, QA, operational, and release predicates pass;
- no unresolved blocker or high-severity finding contradicts release completion;
- production smoke checks and approved monitoring thresholds pass;
- ClickUp and repository evidence are current and traceable;
- `python3 scripts/validate_goal_contract.py <build-goal-contract>` exits `0`;
- the user confirms final closeout at Gate 7.

User approval can choose scope, trade-offs, and accepted residual risk, but it cannot replace missing evidence or turn a failed factual verifier into `PASS`.

## Non-negotiable control rules

1. **One stage per user approval.** Complete the stage, present its gate, and end the response. Do not begin the next stage in the same turn.
2. **Allowed gate responses:** `continue`, `refine: <changes>`, `pause`, or `abort`.
3. **Continue means one stage only.** It never grants blanket permission for later stages.
4. **Refine repeats the current stage.** Preserve prior evidence and show what changed.
5. **Pause preserves state.** Update the ClickUp Build Control task and repository build-state reference.
6. **Abort stops safely.** Do not delete work; record why and leave recovery guidance.
7. **Explicit approval for side effects.** Production deployment, destructive migration, task deletion, workspace restructuring, secrets changes, external communication, or paid-resource changes require their own explicit approval.
8. **No hidden delegation.** At each gate, list which specialist skills were invoked and what each produced.
9. **No duplicate tickets.** ClickUp is the delivery source of truth; repository Markdown is for durable technical/product artefacts only.
10. **No false completion.** Completion requires a valid Goal Contract, all mandatory predicate rows passing, required independent verification, and applicable quality gates.
11. **Mandatory engine.** Every specialist assignment uses the bundled `goal` skill or Ralph Loop; no ad-hoc execution.
12. **Bounded iterations.** Repeated attempts must generate new evidence; terminal failure is reported honestly.
13. **Goal immutability.** Criteria cannot be weakened after execution starts without a traced scope decision and return to the earliest affected gate.

## Build Control task

At Stage 0, use Delivery Manager to locate or create one ClickUp task named using the pattern:

```text
BUILD CONTROL — <product or initiative>
```

Search first. The control task must link the approved PRD, current stage, gate decision history, epics, risks, blockers, release target when known, and final evidence. Use existing workspace structures and statuses. Do not create new statuses, custom fields, Lists, Folders, or Spaces without approval.

Maintain `docs/delivery/BUILD_STATE.md` only as a lightweight pointer containing the control-task URL/ID, current stage, last approved gate, artefact paths, and recovery note. It must not duplicate the ClickUp backlog.

## Stage lifecycle

For every stage below, first create and validate the Stage Goal Contract, then run required specialist child goals through `goal` or Ralph. Evaluate the project-specific predicate against `.claude/team/BUILD_STAGE_COMPLETION.md` before presenting the gate.

### Stage 0 — Bootstrap and intake

Invoke: `delivery-manager`, then relevant lightweight repository inspection.

Actions:

- Interpret `$ARGUMENTS` as the goal, active ClickUp task, or resume request.
- Inspect repository structure, current product state, guidance, tools, connected MCP servers, and existing ClickUp work.
- Verify ClickUp MCP access. If unavailable, stop with setup instructions; do not create local tickets.
- Establish or recover the Build Control task.
- Identify stakeholders, target users, constraints, known scope, environments, and apparent workstreams.
- Propose the specialist set and stage plan; omit irrelevant roles but explain why.
- Record Verified/Inferred/Assumed/Unknown items.

Gate 0 asks the user to confirm or refine the interpreted goal and workflow scope.

### Stage 1 — Product discovery and requirements

Invoke as needed: `product-manager`, `product-researcher`, `business-analyst`.

Actions:

- Audit current product and repository.
- Research comparable systems or live workflows when relevant and authorised.
- Model users, processes, permissions, rules, data, exceptions, integrations, goals, non-goals, metrics, risks, and open decisions.
- Produce or update the PRD and product audit.
- Do not create implementation tickets yet.

Gate 1 asks the user to approve or refine the product definition and unresolved business decisions.

### Stage 2 — Solution architecture and experience

Invoke as needed: `software-architect`, `ui-ux-designer`, `security-reviewer` for early threat modelling, and domain engineers for feasibility spikes only.

Actions:

- Produce architecture, API/data contracts, ADRs, migration and observability strategy.
- Produce user flows, designs, state matrix, responsive/platform behaviour, and accessibility annotations.
- Reconcile product, design, architecture, security, and operational conflicts.
- No broad implementation.

Gate 2 asks the user to approve or refine the proposed solution and material trade-offs.

### Stage 3 — ClickUp delivery plan

Invoke: `product-manager`, `delivery-manager`; consult specialist roles for task sizing and dependencies.

Actions:

- Search for duplicate or existing work.
- Create/update approved epics, stories, tasks, bugs, and spikes in ClickUp.
- Apply the task schema, dependencies, ownership/role labels, priority, milestones, and definition of done.
- Link PRD, design, ADR, research, and decision artefacts.
- Produce delivery sequence, critical path, safe parallel tracks, risk register, and first implementation batch.

Gate 3 asks the user to approve or refine the ClickUp plan before code changes begin.

### Stage 4 — Implementation batches

Invoke only the specialists required by the approved batch: `frontend-engineer`, `backend-engineer`, `mobile-engineer`, `ai-engineer`, `devops-engineer`, and `documentation-writer`.

Actions:

- Work from active ClickUp tasks only.
- Implement small vertical slices with tests, observability, migrations, documentation, and feature controls as applicable.
- Use bounded loops and record evidence on each task.
- Resolve blockers through the owning role; do not silently widen scope.
- Delivery Manager maintains status and dependencies.

After each coherent batch or epic slice, present Gate 4 with working evidence, changed tasks, tests, demos/screenshots, known gaps, and the recommended next batch. Stop. Re-enter Stage 4 after `continue` until implementation scope is complete.

### Stage 5 — Independent verification

Invoke: `code-reviewer`, `security-reviewer`, `qa-engineer`; use implementation roles only to remediate findings.

Actions:

- Review code and migrations independently.
- Verify security/privacy controls and risk acceptance ownership.
- Execute risk-based automated, exploratory, integration, accessibility, performance, and end-to-end tests as applicable.
- Create/link ClickUp bugs and findings; remediate and re-test.
- Produce a requirements traceability and quality-gate report.

Gate 5 asks the user to approve remediation scope or accept explicitly documented residual risk. Unresolved blocker/high findings prevent continuation to release readiness.

### Stage 6 — Release readiness

Invoke: `devops-engineer`, `documentation-writer`, `delivery-manager`, `qa-engineer`, and `security-reviewer` as applicable.

Actions:

- Verify CI/CD, environment configuration, migration sequence, observability, alerts, backup/restore, rollback, runbooks, support readiness, release notes, and launch communications.
- Produce go/no-go recommendation and exact production actions.
- Do not deploy to production in this stage.

Gate 6 asks for explicit `continue` to perform the described production release, or `refine/pause/abort`.

### Stage 7 — Release and closeout

Invoke only after explicit Gate 6 approval: `devops-engineer`, `qa-engineer`, `delivery-manager`, `documentation-writer`, and relevant engineers.

Actions:

- Execute only the approved release steps.
- Monitor health, logs, metrics, user-critical flows, migrations, and alerts.
- Roll back when approved criteria trigger it.
- Complete smoke tests and release verification.
- Update ClickUp tasks, release evidence, known issues, and follow-ups.
- Produce final outcome, residual risk, support notes, and next-review date.

Gate 7 is the final closeout check. Do not mark the Build Control task complete until the user confirms closure or requests refinement.

## Stage gate response format

At every gate, use `.claude/team/BUILD_GATES.md` and include:

- Stage, terminal state, execution engine, and iteration count
- Goal Contract paths and parent/child goal IDs
- Completion predicate table with PASS/FAIL/BLOCKED status and evidence
- Goal interpreted for this stage
- Specialist skills invoked
- Verified outcomes and evidence
- Repository artefacts created/changed
- ClickUp tasks created/updated and status changes
- Decisions made
- Assumptions, unknowns, risks, and blockers
- What is intentionally not done yet
- Recommended next stage or refinement
- Exact response choices: `continue`, `refine: ...`, `pause`, `abort`

Then end the response. Do not call another specialist or make more changes after displaying the gate.

## Resume behaviour

When invoked with `/build resume` or a ClickUp control-task URL:

1. Read the Build Control task and `docs/delivery/BUILD_STATE.md` when present.
2. Read and validate the Build Goal, active Stage Goal, and child Goal Contracts. Reconcile their terminal states with ClickUp stage history, repository evidence, and current git state.
3. Report drift or uncommitted work.
4. Resume at the last unapproved gate, not the last activity performed.
5. Never assume approval from elapsed time or task status alone.

## Failure and conflict handling

- After three materially different failed attempts without new evidence, stop the affected task and surface the smallest unblocker at the current gate.
- When PRD, design, ADR, task, code, or running behaviour conflict, pause only the affected work and route the decision to its owner.
- When a specialist finds out-of-scope work, create or propose a linked ClickUp task; do not absorb it silently.
- If the user's request changes materially, return to the earliest affected stage and preserve traceability.
