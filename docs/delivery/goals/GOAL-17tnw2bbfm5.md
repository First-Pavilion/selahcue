# Goal Contract — GOAL-17tnw2bbfm5

## Identity

- Goal ID: GOAL-17tnw2bbfm5
- Parent goal ID: NONE
- Title: Refuse unencodable login passwords uniformly
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbfm5
- Created: 2026-11-03
- Updated: 2026-11-03
- Maximum iterations: 4
- Independent verification required: yes

## Objective

A lone-surrogate password receives the ordinary wrong-password response without a server error.

## Baseline

Verified: login passes every password directly to Django check_password for known, unknown and locked users; UTF-8 encoding can raise before SafeAPIError. Ticket has no dependencies or comments.

## Inputs and evidence sources

- Live ClickUp description and acceptance criteria; accounts/services.py; platform/views.py; existing native tests.

## Scope

### In scope

- Shared credential refusal and focused HTTP, logs, lockout, GraphQL and byte-caller regression tests.

### Non-goals

- No schema, persistence model, session lifetime, authorization policy or production changes.

### Constraints

- Own isolated ticket branch. Preserve user main checkout and other agents. No credentials or provider calls.

### Assumptions and unknowns

- Unknown: external CI result until PR exists. Review ownership remains with root coordinator.

## Dependencies and approvals

- User authorized implementation and public ticket PR. Root owns four independent reviews, merge and QA transition.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Malformed passwords uniformly refuse known, unknown and locked HTTP login without ERROR logs | pytest tests/test_login_unicode_password.py | All cases return matching 401 UNAUTHENTICATED; no ERROR records | docs/delivery/evidence/17tnw2bbfm5.md | PASS |
| C-002 | yes | Normal login, lockout, GraphQL and byte-caller compatibility hold | pytest tests/test_login_unicode_password.py tests/test_native_account_surface.py tests/test_native_login_outage.py tests/test_customer_auth_slice.py | Passed tests; real KDF and limiter preserved | docs/delivery/evidence/17tnw2bbfm5.md | PENDING |
| C-003 | yes | API regression suite passes | pytest tests -q -rfEs | All applicable tests pass; skips reported | docs/delivery/evidence/17tnw2bbfm5.md | PENDING |
| C-004 | yes | Independent code, security, QA and performance gates pass on frozen revision | Root coordinated Cody Shadow Quinn Vera review | All four gates passed | Root review report and PR | PENDING |

## Verification plan

- Focused verification: real Django HTTP requests with captured logs and seeded known/locked accounts.
- Broader regression verification: API pytest suite and Django checks.
- Independent verifier: Cody, Shadow, Quinn and Vera coordinated by root.
- Required environment: local SQLite in memory; installed API dependency runtime; no network providers.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: replacing only unencodable input with a safe hash candidate while forcing credential refusal preserves hashing and failure accounting.
- Change or investigation: regression tests first, then minimal shared login change.
- Verifier executed: pytest tests/test_login_unicode_password.py -q; Django check; makemigrations --check --dry-run.
- Result: RED 5 failed/1 passed, then GREEN 8 passed; system checks clean and no migrations.
- New evidence: code traced through native handler and three shared login paths.
- Decision: iterate; compatibility and complete API suites running, independent reviews pending.

## Risks and rollback

- Risks: malformed-password timing, lockout accounting and shared GraphQL compatibility.
- Rollback or recovery: revert this ticket commit; no migrations.

## Pause and escalation conditions

- Scope or security policy decision goes to root. Production access is out of scope.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-17tnw2bbfm5.md
- Validator result: pending.
- Independent verification result: pending root coordination.
- Terminal state: ACTIVE.
- Remaining failed or blocked criteria: C-001 through C-004 pending.
- ClickUp final evidence comment: pending.
