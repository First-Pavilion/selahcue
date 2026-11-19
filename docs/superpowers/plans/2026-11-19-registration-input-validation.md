# Registration Profile Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Complete ticket 17tnw2bh4u0 with uniform format validation before database access.
**Architecture:** Reuse model field validation after registration admission and before persistence logic. Keep existing model validation as a defensive check and leave uniqueness/race handling in place.
**Tech Stack:** Django, Strawberry, pytest; existing pinned local Python environment.
**Spec:** docs/superpowers/specs/2026-11-19-registration-input-validation.md.

## Global Constraints

Base `306a8f3a4eb9cc4a388af0b6091f52ad947f14b9`, branch `codex/registration-input-parity-20261119`. One implementation writer. Names retain 200-character model limits and existing whitespace normalization; timezone retains 64-character limit, strip/blank-to-UTC and UTC/IANA rule. Keep profile checks after both existing admission claims and before password hashing/transaction entry. No uniqueness checks or SQL in the new check. Preserve idempotency, existing-account acceptance and race behavior. No schema/configuration/provider/password-policy changes. No live-service requests, account-disclosure response comparisons, CI, native/browser/Docker, installs, secrets, timing benchmark or full suite. Sequential local Python children only, 45-second TERM plus five-second KILL/reap. Preserve all other worktrees and prior evidence.

## Review Focus

- Invalid names/timezones must fail before SQL, with safe error and no mail/session/persisted effects; preserve the real SQL tripwire rather than replacing validation with a mock.
- Valid boundary names, optional blank display name, blank/default/trimmed timezone and installed IANA values must still work and persist normalized values.
- A field check must not run uniqueness constraints, actor/idempotency validation or account-dependent lookups.
- Refused/outage admission must still prevent profile validation, password hashing, SQL and mail work; current global/source budgets remain unchanged.
- Applying IANA rules on the request path must remain bounded by admission and avoid new database work, external calls, unbounded caches or retained per-account state.

## Task 1: Reuse profile field rules before database work

**Files:** modify `implementation/api/selahcue_api/apps/accounts/services.py`, `implementation/api/tests/test_customer_auth_slice.py`; only if necessary, a pure helper in `implementation/api/selahcue_api/apps/accounts/models.py`. Include the plan and spec. No other implementation paths.

**Interfaces:** retain `register_customer_user(data: RegisterCustomerUserData, *, client_ip: str = "") -> AcceptedResult`. Introduce a private pure-validation helper taking normalized organisation name, display name and timezone and returning `None` or the existing sanitized validation exception. Reuse model field validators and timezone clean behavior without calling full model uniqueness validation. The existing field/constraint validation inside account creation remains in place.

- [x] Read the spec, complete ticket readback and source map. Inspect the existing guarded test and retained RED log/root custody: four expected validation-before-SQL failures, two valid controls pass. Do not rerun or recreate the blocked response-comparison attempt. Record this accepted RED checkpoint in the task report before production edits.
- [x] Add positive/boundary tests covering normalized 200-character names, optional blank display name, UTC, Africa/Lagos, whitespace-trimmed UTC and blank-to-UTC. Exercise a 64-character nonmember zone separately from the existing 65-character case so membership and length are not conflated. These are ordinary local input validation tests; malformed requests retain the SQL tripwire. Cover the pre-admission refusal ordering without mocking the actual field validators.
- [x] Implement the smallest profile check after both existing registration admission claims, before hashing and transaction entry. Normalize display name/timezone once and use those values in candidate creation. Translate Django validation failures through the existing safe validation helper. Do not run model uniqueness constraints in the shared check or change collision handling.
- [x] Run the four guarded regressions and positive controls with the existing bounded runner; expect all pass, no timeout. Then run only owning signup/admission/idempotency controls selected from `tests/test_customer_auth_slice.py` and registration controls from `tests/test_throttling.py`, under the same sequential budget. Preserve every failure and explain it; no unbounded broadening. Stop on timeout/resource trouble.
- [x] Inspect diff, verify no new migration/configuration/dependency files, run `git diff --check`, and commit owned paths. Report exact commands, full retained outputs, source hashes, normalization/validator choices, test counts and limitations. Do not push or mutate the tracker.

## Review and merge

Code/spec, security and performance task review are required for this request-path change. Use source/query/ordering evidence for performance; no latency promise or timing benchmark is part of acceptance on the paged host. Then most-capable final whole-branch QA review, bounded remediation and re-review. Root verifies current live main, reviewed head and merge tree; merge under standing authority, then move only this ticket to QA with readback. Native release qualification remains separate.

### Fix expected validation logging

- [x] Add a guarded regression for a rejected signup with synthetic inline fields. Confirm the validation rejection reaches the framework log guard before repair. Confirm typed rate limits, untyped code matches and unexpected errors keep their existing handling.
- [x] In the registration resolver, send typed validation errors through the existing query-free account-field handler. Preserve the public error and all other error paths.
- [x] Rerun the logging regression, guarded profile cases, valid signup and admission controls. Retain both runs for scoped re-review.
