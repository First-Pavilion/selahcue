# ClickUp Workflow Contract

## Source of truth

ClickUp is authoritative for epics, stories, tasks, bugs, spikes, ownership, dependencies, priority, milestones, status, blockers, and execution history. Do not maintain duplicate Markdown tickets.

Repository artefacts remain authoritative for PRDs, research, business rules, ADRs, diagrams, designs, API/data contracts, Goal Contracts, test plans/evidence, security reports, runbooks, and release notes. Every ClickUp task links to the relevant paths. Goal Contracts are execution evidence, not duplicate tickets.

## MCP requirement

Use the official ClickUp MCP connection available to Claude Code. If unavailable, stop before ticket operations. Do not substitute local tickets.

## Structure discovery

Before creating work:

1. Identify the Workspace, Space, Folder, List, statuses, custom fields, task types, tags, automations, and naming conventions.
2. Search for related epics/tasks and duplicates.
3. Propose any new hierarchy or field before creating it.
4. Reuse existing statuses and map workflow semantics to them.

## Recommended logical model

Adapt to the workspace rather than forcing it:

- **Build Control task:** one per `/build` initiative; records stage/gate history and links all epics.
- **Epic:** a coherent product outcome or release slice.
- **Story:** testable vertical user value.
- **Engineering task:** enabling work that cannot be expressed as a standalone story.
- **Bug:** verified deviation from approved or expected behaviour.
- **Spike:** time-bounded investigation with an explicit decision/output.
- **Subtask:** tightly contained child work; avoid hiding major cross-team work as subtasks.

## Status semantics

Map these meanings to existing workspace statuses:

- Draft / Needs Definition
- Ready
- In Progress
- Blocked
- In Review
- Security Review
- QA / Verification
- Ready for Release
- Done
- Deferred / Cancelled

Never create or rename statuses without explicit user approval.

## Required task behaviour

- Every executable task links one active Goal Contract before status moves to In Progress.
- Start comments name the selected engine and completion predicate.
- Final comments include the full predicate status and terminal state.

- Search before create.
- One accountable owner; supporting roles may be named in description or custom field.
- Dependencies represent true blockers.
- Comments are append-only evidence; do not erase prior history.
- Scope changes require Product Manager approval and visible change history.
- Link commits/PRs, design nodes, ADRs, test evidence, dashboards, and runbooks.
- Out-of-scope findings become linked follow-up tasks.
- Deletion and workspace restructuring require explicit approval.

## Build gate history

The Build Control task receives one comment per gate containing stage Goal ID, engine, iteration count, predicate evaluation, evidence, decisions, risks, response, and next stage. The current stage must be recoverable from ClickUp without relying on chat history.
