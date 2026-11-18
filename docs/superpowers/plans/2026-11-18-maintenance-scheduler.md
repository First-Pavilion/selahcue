# Maintenance-only scheduler implementation plan

> Use Superpowers subagent-driven-development and test-driven-development.

Spec: docs/superpowers/specs/2026-11-18-maintenance-scheduler.md
Ticket: https://app.clickup.com/t/86ak11vwn
Base: 4467de91a4292f2a46b1feffe472553076899cd7.
Workspace: already isolated, branch codex/86ak11vwn-maintenance-scheduler-20261118.

Global constraints: one writer; no CI polling or gate; no deployment, provider credentials, paid resources, native build or Docker; preserve unrelated worktrees. User has authorized implementation and merging after independent review. Keep runtime ticket in progress until its manual operational criteria are met.

## Task 1: Safe provider schedule opt-ins
- Write regression tests first against real Django settings/Celery configuration: default maintenance-only, independent provisioner/usage opt-ins, both, public-feature flags alone, invalid values.
- Record assertion RED before changing production code.
- Update settings.py to retain the three maintenance schedules and conditionally add exactly the selected provider entries without altering task routes.
- Map both opt-ins with disabled defaults in the production beat service.
- Update deployment/environment documentation to match behavior and consumer prerequisites.
- Run focused bounded local tests and relevant existing configuration/registration controls. Do not run the entire API suite on this memory-constrained machine.
- Self-review, commit only this ticket's files and report exact evidence.

## Review and finish
Independent code/spec, security, QA and performance reviews examine the same current base/head. Resolve findings through TDD and re-review (up to five rounds, do not silently restart the count). Verify target main and relevant merge composition. Open one PR and merge when applicable local verification and independent reviews pass; hosted CI is not an acceptance gate by the user's instruction. Preserve any failures or unexecuted checks honestly.
