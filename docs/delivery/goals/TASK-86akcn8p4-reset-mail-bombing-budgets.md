# Goal Contract — TASK-86akcn8p4-reset-mail-bombing-budgets

## Identity

- Goal ID: TASK-86akcn8p4-reset-mail-bombing-budgets
- Parent goal ID: NONE
- Title: `request_password_reset` spends a per-target-email budget and a global budget,
  mirroring the resend-verification triple
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akcn8p4
- Created: 2026-09-26
- Updated: 2026-09-26
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`request_password_reset` currently spends only a per-IP budget (86akcmfd4). It has no
per-address cap and no global cap, unlike `resend_email_verification`'s three-budget shape
(address + IP + global). This makes it the only unauthenticated mail-sender in the API with
neither — a distributed attacker's mail volume to one victim is bounded only by IP count,
which the sibling IPv6 ticket (86akcn8ww) shows is nearly free. After this change,
`request_password_reset` spends address + IP + global budgets before any existence-dependent
branch runs, exactly mirroring the resend path's shape and no-oracle handling.

## Baseline

- Verified: `implementation/api/selahcue_api/apps/accounts/services.py:1138-1207` —
  `request_password_reset` spends only `password_reset_request_ip` (via `enforce_budget`)
  before the email is validated; no address or global budget exists.
- Verified: `resend_email_verification` (same file, ~line 856-984) spends
  `resend_verify` (global), `resend_verify_ip`, `resend_verify_addr` — in that order, widest
  first — via `enforce_budget_reporting_outage`, keyed on `_email_fingerprint(normalized)` for
  the address budget (never the raw email).
- Verified (86akcn8ww, this session, PR #106): full suite baseline is 538 passed against a
  dedicated Postgres 16 container, 0 failures, once DEBUG/CELERY_TASK_ALWAYS_EAGER env
  overrides are excluded.

## Inputs and evidence sources

- ClickUp 86akcn8p4 (full description read)
- `implementation/api/selahcue_api/apps/accounts/services.py` (`resend_email_verification`,
  `request_password_reset`)
- `implementation/api/selahcue_api/settings.py` (`SELAHCUE_THROTTLE_RESEND_*` block)
- `implementation/api/tests/test_resend_verification.py` (budget test patterns to mirror)
- `implementation/api/tests/test_password_reset_throttle.py` (existing per-IP coverage)

## Scope

### In scope

- Add a per-target-email budget to `request_password_reset`, keyed on the same
  `_email_fingerprint` HMAC the resend path and this function's own mint branch already use —
  never the raw email in a cache key.
- Add a global budget, same shape as `RESEND_GLOBAL_BUDGET`.
- Spend order: widest (global) first, then IP, then address — matching the resend path's own
  stated reasoning (a global flood should not be diagnosable by which specific limit tripped).
- Reuse `apps/throttling/guards.enforce_budget` — no second limiter.
- New settings mirroring `SELAHCUE_THROTTLE_RESEND_ADDRESS` / `_GLOBAL` in shape and location.
- The per-address refusal must be indistinguishable whether or not the address has an account
  (spent unconditionally, before the existence check — same discipline as resend).

### Non-goals

- The IPv6 bucketing gap (86akcn8ww, separate branch/PR, sequenced first).
- The degraded-outage ceiling extension, sustained-denial alerting, and `verify_email`
  throttle (86akcn92k, separate branch/PR, sequenced third).
- `confirm_password_reset` — the ticket scopes this to `request_password_reset` only (the mail
  side of the pair; confirm has no mail-sending side effect to bomb).

### Constraints

- Must not become an account-existence oracle: refusal behavior identical for a known vs.
  unknown address (byte-identical response, matching timing to the extent the existing floor
  covers it — note `request_password_reset` has NO constant-time floor, per its own docstring;
  this ticket does not add one, since RATE_LIMITED is already a structurally distinct response
  from `accepted:true` and its own timing reveals nothing further, same reasoning as resend's
  rate-limited-calls-are-not-padded rule).
- No CI coverage via `make ci`; the Django project's own pytest suite against Postgres is the
  gate, plus GitHub Actions `api (django)` green via `gh pr checks`.

### Assumptions and unknowns

- ASSUMED: setting names `SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS` and
  `SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL` (mirroring `_RESEND_ADDRESS`/`_RESEND_GLOBAL` but
  disambiguated with `REQUEST` since a future `RESET_CONFIRM_ADDRESS` is conceivable).
- ASSUMED: default budgets equal to the resend equivalents, (3, 900) address / (500, 3600)
  global — same magnitude, same reasoning, no evidence to justify a different number.

## Dependencies and approvals

- Sequenced after 86akcn8ww in this session (touches the same file); this branch is cut on
  top of 86akcn8ww's branch and will be rebased onto `origin/main` once that PR merges, before
  this PR is finalized.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Per-address budget refuses the (N+1)th request for one address while a different address still passes | new test in `test_password_reset_throttle.py` | passes | test output | PENDING |
| C-002 | yes | Refusal is indistinguishable between an existing and a non-existing account | new test (byte-identical response, same status) | passes | test output | PENDING |
| C-003 | yes | Global budget refuses once exhausted regardless of address or IP | new test | passes | test output | PENDING |
| C-004 | yes | Existing 86akcmfd4 per-IP tests still pass unmodified | `pytest tests/test_password_reset_throttle.py -q` | all pass | test output | PENDING |
| C-005 | yes | Mutation check: removing the per-address spend turns its test red | manual mutation + rerun | RED, then restored | transcript | PENDING |
| C-006 | yes | Full suite regression: no new failures vs. the 538-pass baseline | `pytest -q` against Postgres | 538+ passed, 0 failed | test output | PENDING |
| C-007 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) blocking findings resolved | review round + Artifact | 0 blocking outstanding | Artifact URL | PENDING |
| C-008 | yes | PR opened as Draft against `main`, rebased and not behind, GitHub Actions CI green | `gh pr checks` | all required checks pass | PR URL + checks output | PENDING |

## Verification plan

- Focused verification: `pytest tests/test_password_reset_throttle.py -q`.
- Broader regression verification: full `pytest -q` against the dedicated Postgres container.
- Independent verifier: Cody, Vera, Sana, Quinn.
- Required environment: `SQL_ENGINE=django.db.backends.postgresql`, `kenji-throttling-pg`
  container (127.0.0.1:55432).

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004
- Hypothesis: inserting two `enforce_budget` calls (global, then address-fingerprint) ahead of
  the existing per-IP call in `request_password_reset`, plus two new settings, closes the gap
  with the same no-oracle discipline the per-IP budget already has.
- Change or investigation: implement + add tests.
- Verifier executed: see completion predicate.
- Result: TBD
- New evidence: TBD
- Decision: TBD

## Risks and rollback

- Risks: a legitimate user requesting several resets in a short window (e.g. after mistyping,
  or across several browser tabs) now hits the address budget sooner than before — same trade
  `resend_email_verification` already accepts, at the same magnitude.
- Rollback: revert the single commit; `request_password_reset` returns to per-IP-only. No
  migration, no persisted state change (throttle counters are ephemeral cache entries).

## Pause and escalation conditions

- None expected — this mirrors an existing, already-approved pattern in the same file.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <path> --completion`
- Validator result: TBD
- Independent verification result: TBD
- Terminal state: TBD
- Remaining failed or blocked criteria: TBD
- ClickUp final evidence comment: TBD
