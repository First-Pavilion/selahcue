# Goal Contract — TASK-86ak65mj5-password-reset-throttle-verification

## Identity

- Goal ID: TASK-86ak65mj5-password-reset-throttle-verification
- Parent goal ID: NONE
- Title: `requestPasswordReset`'s throttle is proven against every Acceptance Criterion of 86ak65mj5
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak65mj5
- Created: 2026-10-02
- Updated: 2026-10-02
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Ticket 86ak65mj5 asks for a throttle on the unauthenticated, mail-sending `requestPasswordReset`
that creates no account-existence oracle. That throttle is already on `main`: it landed under
86akcmfd4 (per-IP, PR #35), 86akcn8p4 (per-address and global, PR #107) and 86akcn92k (degraded
send ceiling and denial alerting, PR #109), all after the ticket was written. This goal closes
the gap between the ticket's Acceptance Criteria and what the existing tests actually prove,
with no production-code change unless a new test exposes a real defect.

## Baseline

- Verified: `origin/main` @ `66e514ee` — `request_password_reset`
  (`implementation/api/selahcue_api/apps/accounts/services.py`, ~L1236) spends global (500 per
  3600s), then per-IP (20 per 3600s), then per-address (3 per 900s, keyed on the HMAC email
  fingerprint) before any existence-dependent branch. All three fail open on a store outage; the
  SEND degrades under a process-local ceiling (`_claim_degraded_reset_send`).
- Verified: focused baseline `tests/test_password_reset_throttle.py` +
  `tests/test_customer_auth_slice.py` = 58 passed on the unmodified branch (SQLite + LocMemCache).
- Verified: the 86ak65mj5 description's premise "dummy `make_password` on the miss branch" is
  stale — DEC-013 (86ak66r5c) removed it; the miss branch is deliberately empty.
- Verified gaps (read in the existing tests): (1) no test uses the DEFAULT budgets against a
  mistyped-address flow, or asserts a legitimate single request sends exactly one email; (2)
  throttled-refusal byte identity is asserted for the address budget only, never the IP or
  global budget; (3) no test compares refusal TIMING between a registered and an unregistered
  address; (4) no test bounds the number of limiter keys by the global budget.

## Inputs and evidence sources

- ClickUp 86ak65mj5 (description, comment of 2026-08-28), 86ak5r2pt, 86ak5qy3p, 86ak7kka2,
  86ak10a13, 86ak11r67, 86akcn8p4
- `implementation/api/selahcue_api/apps/accounts/services.py`,
  `selahcue_api/apps/throttling/{guards,services}.py`, `selahcue_api/settings.py`
- `implementation/api/tests/test_password_reset_throttle.py`,
  `tests/test_customer_auth_slice.py`, `tests/test_resend_verification.py` (paired-timing
  technique)
- `docs/decisions/DECISION-LOG.md` DEC-013

## Scope

### In scope

- Extend `implementation/api/tests/test_password_reset_throttle.py` (the existing throttle
  suite; not a new file) with tests for gaps (1)-(4) above, plus a settings-vs-default drift
  guard for the four reset budgets.
- Mutation-verify every control with the sibling tests running (never `--exact`).

### Non-goals

- Padding / timing floor on the UNTHROTTLED path of `request_password_reset` — 86ak7kka2.
- `confirm_password_reset` failure logging — 86ak5r2pt. Row lock across the hash — 86ak5qy3p.
- Setting `SELAHCUE_TRUSTED_PROXY_COUNT` in production — 86ak10a13 (infra).
- Changing the shipped budget numbers.

### Constraints

- Test-only change. A production edit is allowed only if a new test exposes a real defect.
- `test_request_reset_is_uniform_for_existing_and_missing` must pass unedited (AC4).
- No raw email in any limiter key; key space bounded by attacker-independent budgets.
- No unbounded growth; the bounded-memory test must bite.

### Assumptions and unknowns

- Verified by the Django system check on this branch: `SELAHCUE_TRUSTED_PROXY_COUNT` is 0 unless
  the environment sets it (warning `selahcue_throttling.W001`).
- ASSUMED: `SELAHCUE_TRUSTED_PROXY_COUNT` is still unset in production (86ak10a13 is
  planning/todo). Not checkable from this repo. Owner: devops.
- UNKNOWN: the paired-timing tolerance's behaviour on GitHub's ubuntu runner. Measured here on a
  shared 10-core dev host, on both SQLite+LocMem and Postgres+Redis.

## Dependencies and approvals

- None blocking. Independent review (Cody, Vera, Shadow, Quinn) is dispatched by the parent
  agent, not by this role.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
|  C-001 | yes | AC1: under the DEFAULT budgets a person who mistypes their address (same typo twice, a different typo, then the right one) is never refused and only the real address gets mail | `test_a_person_who_mistypes_their_address_is_never_blocked_under_the_default_budgets` | passes | PASS in the focused run (73 passed) and the CI-equivalent run (572 passed); mutants M6a, M6b, M9, M10 RED | PASS |
|  C-002 | yes | AC1: one legitimate request sends exactly one email and mints exactly one live token; three same-address retries inside the window are served, the fourth is refused and sends nothing | `test_one_legitimate_request_sends_exactly_one_email_and_mints_exactly_one_token`, `test_retrying_the_same_address_after_a_lost_email_works_three_times_then_stops` | pass | PASS in both runs; mutants M6b, M9, M10 RED | PASS |
|  C-003 | yes | AC2: a throttled refusal is byte-identical (status and body) for a registered and an unregistered address under EACH of the IP, address and global budgets, and sends nothing | `test_a_throttled_refusal_is_byte_identical_for_a_known_and_an_unknown_address[ip/address/global]` | pass | PASS in both runs; mutants M1a, M1b, M2, M5, M9, M10 RED | PASS |
|  C-004 | yes | AC2: the same refusals take the same time (interleaved paired comparison, median gap within tolerance), and the probe can see an injected existence-dependent delay | `test_a_throttled_refusal_takes_the_same_time_for_a_known_and_an_unknown_address[...]`, `test_the_refusal_timing_probe_can_see_an_existence_dependent_delay` | pass; 30 of 30 repeat runs green | PASS in both runs; 30 of 30 repeat runs green (SQLite + LocMem), 20 of 20 (Postgres + Redis); mutants M7 (3 ms existence-dependent pause), M1a, M1b, M5 RED | PASS |
|  C-005 | yes | AC3: the limiter fails open on a store outage (response unchanged, send bounded) | existing `test_store_unavailable_fails_open_for_request_reset`, `test_a_limiter_outage_bounds_the_reset_send_without_denying_the_response`; mutant M4 turns them RED | pass; M4 RED | PASS in both runs; mutant M4 RED (4 tests) | PASS |
|  C-006 | yes | AC4: `test_request_reset_is_uniform_for_existing_and_missing` passes unchanged | `git diff origin/main -- implementation/api/tests/test_customer_auth_slice.py` is empty and the test passes | empty diff; pass | PASS; the diff of test_customer_auth_slice.py against origin/main is empty; green in both runs; it stays GREEN under the existence-keyed mutants (one call per address), so the RED evidence for the oracle is carried by the byte-identical and address-budget tests instead | PASS |
|  C-007 | yes | AC5: mutation-verify with siblings running — throttle keyed on account existence (address only, and all three), throttle after the mint, no address budget, fail-closed, address-before-global, shrunk defaults, drifted setting, existence-dependent pause, raw email in key, no send, double send | `mutate.py` matrix over both whole test files | every mutant RED, production files restored after each | PASS; 13 mutants, each RED with both whole sibling files running; production files restored each time; table in the PR body | PASS |
|  C-008 | yes | Bounded memory: the limiter creates at most `global_limit` address keys and `global_limit` IP keys however many distinct addresses and sources arrive; malformed addresses create none | `test_the_keys_the_limiter_can_create_are_bounded_by_the_global_budget_not_by_attacker_input`; mutant M3 turns it RED | pass; M3 RED | PASS; mutant M3 RED, and it is the only test that goes RED for M3 | PASS |
|  C-009 | yes | The API project's own CI gates are green (system check, migrations committed, full suite) on Postgres + Redis | `manage.py check`; `manage.py makemigrations --check --noinput`; `python -m pytest tests -q` with the `api (django)` job's env | exit 0 x3; 572 passed, 0 skipped | PASS; check exit 0, migrations exit 0 (No changes detected), tests exit 0: 572 passed, 0 skipped (557 baseline + 15 new) | PASS |
| C-010 | yes | PR opened as Draft against `main`, not behind `origin/main`, with no production-code change | `gh pr view`; `git rev-list --count HEAD..origin/main` is 0; `git diff --stat origin/main` lists only the test file and this contract | Draft; 0; test + contract only | PR URL | PENDING |
| C-011 | yes | Independent review (code, performance, security, QA) | brokered by the parent agent | 0 blocking outstanding | not run by this role | BLOCKED |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `python -m pytest tests/test_password_reset_throttle.py tests/test_customer_auth_slice.py -q`.
- Mutation: apply one mutant at a time to `services.py` / `guards.py` / `settings.py`, run BOTH
  whole files, record failures, `git checkout --` the production files.
- CI-equivalent: the `api (django)` job's three commands against Postgres 17.6 + Redis 7
  containers (the job uses postgres:16-alpine; the 17.6 image was already local).
- Independent verifier: Cody, Vera, Shadow, Quinn via the parent.
- Required environment: isolated venv `implementation/api/.venv`, Python 3.14.5,
  `pip install -e ".[dev]" "psycopg[binary]>=3.2,<4"`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004, C-008
- Hypothesis: the shipped three-budget throttle already satisfies the ticket; only the proof is
  missing, so tests alone close the gap, and each must go RED against a mutant to count.
- Change or investigation: read the throttle and its tests; added 15 tests to the existing
  throttle suite; measured the paired-timing probe's noise (max gap +/-0.07 ms over 75 runs)
  and its response to a throttle moved after the mint (+0.44 to +1.5 ms).
- Verifier executed: focused suite, then 30 repeat runs of the timing tests.
- Result: all new tests pass on unmodified production code; 30 of 30 repeat runs green.
- Decision: proceed to mutation matrix.

### Iteration 2

- Target criterion: C-005, C-007, C-008
- Change or investigation: ran 13 mutants against both whole sibling files. First matrix run
  found the M9 pattern ambiguous (resend has the same line); the pattern was made specific and
  M10 (double send) added. The timing tolerance was tightened from 2 ms to 1 ms after measuring
  that 2 ms could not see a throttle placed after the mint.
- Result: every mutant RED; production files restored each time.
- Decision: run the CI-equivalent gates.

## Risks and rollback

- Risks: the paired-timing tests are timing-based. Mitigations: interleaved pairs whose order alternates each round,
  median of 60, 1 ms tolerance vs 0.07 ms observed noise, a positive control that must flag an
  injected 2 ms delay, 30 of 30 repeat runs green on the dev host and a further repeat run on
  Postgres + Redis. If the GitHub runner proves noisier, the tolerance is one constant.
- Rollback: revert the single test-only commit. No migration, no production code, no state.

## Pause and escalation conditions

- A new test exposing a real production defect: fix it in this branch only if small and
  clearly inside this ticket; otherwise file a linked follow-up and stop.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <path> --completion`
- Validator result: TBD
- Independent verification result: TBD (parent-brokered)
- Terminal state: GATE_REVIEW (verifiable work complete; the four-reviewer gate is brokered by the parent)
- Remaining failed or blocked criteria: C-011 (review is brokered by the parent)
