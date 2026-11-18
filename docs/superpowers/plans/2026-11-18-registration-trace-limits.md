# Registration and reset-trace limits implementation plan

> Use Superpowers subagent-driven-development and test-driven-development.

Spec: docs/superpowers/specs/2026-11-18-registration-trace-limits.md.
Ticket: https://app.clickup.com/t/17tnw2bbfm6.
Base:49d78fd00f7503c2fccf86b615bf0a0c9d349572.
Branch:codex/17tnw2bbfm6-registration-trace-limits-20261118.

Global constraints: one ticket/PR, one writer; no CI work or deployment; no native/browser/Docker/full API suite; no secret reads; unchanged signup enumeration and password-reset response contracts. Independent design security preflight found two issues (mixed-reason alarm and safe registration error code), both corrected and re-reviewed before code. Role/provider/mail choices remain outside scope. Respect the documented global-first/cardinality tradeoff.

## Task1: Complete the existing ticket
1. Read existing service/GraphQL throttling and trace tests. Run a bounded relevant baseline.
2. Write actual assertion regressions for signup global/source admission, cache outage and zero expensive/DB/mail work, trusted GraphQL IP wiring, inline-literal log privacy, bounded key count and TTL. Implement service admission and existing-safe RATE_LIMITED refusal.
3. Write failing tests for named trace aggregate cap, anonymous independence and no second store call after an outage. Implement fixed aggregate shared budget and bounded local fallback.
4. Write failing tests for full local table churn, incumbent spent-window preservation, overflow ceiling, expiry reclamation and correct exhausted-versus-overflow classification. Implement without nested ceiling/table locks.
5. Write failing mixed-reason suppression alarm test; add constant-size aggregate flag to the existing tally and atomic report/reset. Preserve lost-trace and original response/log redaction controls.
6. Update exact environment/reference/deployment instructions, including settings defaults, cardinality/outage behavior and rollback. Keep historical failure records intact.
7. Mutation-check each new bound and the cardinality/ordering/forwarding/logging controls with focused siblings. Restore source exactly and rerun owning focused tests. Split long test selections into bounded nonoverlapping groups.
8. Self-review and commit only this ticket's source, tests and docs. Report exact RED/GREEN/mutant evidence and limitations.

## Review and merge
Independent code/spec, security, QA and performance reviews at exact base/head, with TDD remediation and re-review up to five rounds. Broad final review after task acceptance. Verify live target and merge composition. User authorized merge after passed reviews without hosted CI as a gate. This ticket can move to QA after the full scoped implementation is merged; do not claim production deployment or broader release completion.
