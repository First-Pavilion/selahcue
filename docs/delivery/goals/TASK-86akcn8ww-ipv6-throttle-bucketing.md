# Goal Contract — TASK-86akcn8ww-ipv6-throttle-bucketing

## Identity

- Goal ID: TASK-86akcn8ww-ipv6-throttle-bucketing
- Parent goal ID: NONE
- Title: `client_ip` buckets IPv6 addresses to /64 before they become a throttle cache key
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akcn8ww
- Created: 2026-09-26
- Updated: 2026-09-26
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`apps/throttling/services.client_ip` returns the full normalised IPv6 address, giving one
attacker on a /64 allocation ~2^64 distinct throttle identities. After this change, IPv6
addresses are truncated to their /64 network prefix before use as a cache key; IPv4 is
unchanged.

## Baseline

- Verified: `implementation/api/selahcue_api/apps/throttling/services.py:127-158` — `client_ip`
  parses and normalises the address via `ipaddress.ip_address` but returns it unbucketed.
- Verified: full local pytest suite against a dedicated Postgres 16 container passes at
  530 passed / 1 pre-existing timing-flake (`test_resend_verification.py::
  test_response_timing_does_not_distinguish_the_three_cases`, host-load sensitive, unrelated to
  throttling) with no other failures, using only `SQL_ENGINE=django.db.backends.postgresql` +
  matching `SQL_*` vars (no `DEBUG`/`CELERY_TASK_ALWAYS_EAGER` overrides, which independently
  produce 3 false failures confirmed not to reproduce against the correct env).

## Inputs and evidence sources

- ClickUp 86akcn8ww (full description read)
- `implementation/api/selahcue_api/apps/throttling/services.py`
- `implementation/api/tests/test_throttling.py` (existing `client_ip` coverage)
- `implementation/api/tests/test_password_reset_throttle.py` (consumer of `client_ip` via the
  reset paths)
- ADR-0023 / DEC-013 (per-IP budget rationale)

## Scope

### In scope

- Bucket IPv6 addresses to their /64 network prefix inside `client_ip`, before the value is
  returned (i.e. before any caller turns it into a cache key).
- IPv4 addresses: unchanged, full address, no bucketing.
- Malformed/unparseable input: unchanged fallback behaviour (`REMOTE_ADDR` or `"unknown"`).
- Record the /64-vs-/56 choice and the shared-bucket collateral (large IPv6-native NAT) in the
  function's docstring.
- Tests: same-/64 addresses share a budget (mutation-verified), different-/64 addresses do not
  (positive control), IPv4 unaffected, malformed input still falls back.

### Non-goals

- Hashing the address (explicitly ruled out by the ticket — preserves cardinality).
- Changing IPv4 behavior.
- The mail-bombing / degraded-ceiling / alerting / verify_email gaps — those are 86akcn8p4 and
  86akcn92k, separate tickets/branches/PRs.

### Constraints

- Fix lives in the shared helper (`client_ip`), not per-caller, so every consumer (`/v1`
  device-auth, resend-verification, both reset paths) inherits it at once.
- No CI coverage via `make ci` for `implementation/api`; the Django project's own pytest suite
  against Postgres is the gate. GitHub Actions CI must still show green via `gh pr checks`
  before considering this done.

### Assumptions and unknowns

- ASSUMED: /64 (not /56) is the right bucket size — matches the ticket's primary
  recommendation ("a standard residential IPv6 allocation is a /64") and is the narrower,
  less-collateral-prone choice; recorded in the code comment per the ticket's "pick one and
  record why."

## Dependencies and approvals

- None — self-contained fix to a pure helper function.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Two IPv6 addresses in the same /64 share one throttle budget | `pytest tests/test_throttling.py -k ipv6 -q` (run with siblings, not `--exact`) | new test passes | test output | PENDING |
| C-002 | yes | Two IPv6 addresses in different /64s have separate budgets (positive control) | same file, companion test | passes | test output | PENDING |
| C-003 | yes | IPv4 behavior is unchanged — existing suite still green | `pytest tests/test_throttling.py tests/test_password_reset_throttle.py tests/test_customer_auth_slice.py -q` | all pass | test output | PENDING |
| C-004 | yes | Malformed/unparseable input still falls back safely | existing `test_forged_non_ip_entry_falls_back_to_remote_addr` still passes unmodified | passes | test output | PENDING |
| C-005 | yes | Mutation check: removing the bucketing turns the same-/64 test red | manual mutation + rerun | RED, then restored | transcript | PENDING |
| C-006 | yes | Full suite regression: no new failures vs. baseline | `pytest -q` against Postgres | same failures as baseline only (the one pre-existing timing flake) | test output | PENDING |
| C-007 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) blocking findings resolved | review round + Artifact | 0 blocking outstanding | Artifact URL | PENDING |
| C-008 | yes | PR opened as Draft against `main`, GitHub Actions CI green | `gh pr checks` | all required checks pass | PR URL + checks output | PENDING |

## Verification plan

- Focused verification: `pytest tests/test_throttling.py -q` and the mutation check above.
- Broader regression verification: full `pytest -q` against the dedicated Postgres container.
- Independent verifier: Cody, Vera, Sana, Quinn (standard review pipeline).
- Required environment: `SQL_ENGINE=django.db.backends.postgresql`, dedicated container
  (`kenji-throttling-pg`, 127.0.0.1:55432), `connection.vendor == "postgresql"` asserted by
  `tests/test_concurrency_postgres.py`'s own skip guard.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004
- Hypothesis: adding an `ipaddress.IPv6Network(..., strict=False)` truncation branch inside
  `client_ip` for `ip_address.version == 6` closes the gap with no change to IPv4 or the
  malformed-input fallback.
- Change or investigation: implement + add tests.
- Verifier executed: see completion predicate.
- Result: TBD
- New evidence: TBD
- Decision: TBD

## Risks and rollback

- Risks: /64 bucketing means a large IPv6-native NAT (e.g. a campus or carrier-grade NAT
  sharing one /64) shares a single throttle budget across many real users — a shared-bucket
  denial risk of the same shape as the existing W001 warning. Documented in the code and the
  PR description, not hidden.
- Rollback: revert the single commit; `client_ip` returns to the full address. No data
  migration, no persisted state change.

## Pause and escalation conditions

- If the /64-vs-/56 choice needs a product/security decision beyond engineering judgment —
  not expected; the ticket explicitly leaves this as an engineering call to make and record.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <path> --completion`
- Validator result: TBD
- Independent verification result: TBD
- Terminal state: TBD
- Remaining failed or blocked criteria: TBD
- ClickUp final evidence comment: TBD
