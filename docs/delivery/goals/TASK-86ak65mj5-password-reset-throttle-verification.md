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
- Updated: 2026-10-02 (review round 1 addressed)
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
  mistyped-address flow, or asserts a legitimate single request sends exactly one email, and the
  shipped IP and global numbers were not pinned (inflating them survived every test); (2)
  throttled-refusal byte identity was asserted for the address budget only; (3) no test compared
  refusal TIMING or refusal WORK between a registered and an unregistered address; (4) no test
  bounded the number of limiter keys by the global budget.

## Inputs and evidence sources

- ClickUp 86ak65mj5 (description, comment of 2026-08-28), 86ak5r2pt, 86ak5qy3p, 86ak7kka2,
  86ak10a13, 86ak11r67, 86akcn8p4
- `implementation/api/selahcue_api/apps/accounts/services.py`,
  `selahcue_api/apps/throttling/{guards,services}.py`, `selahcue_api/settings.py`
- `implementation/api/tests/test_password_reset_throttle.py`,
  `tests/test_customer_auth_slice.py`, `tests/test_resend_verification.py` (paired-timing
  technique)
- `docs/decisions/DECISION-LOG.md` DEC-013
- Review round 1 of PR #152 (Cody, Shadow, Quinn, Vera), head `07dc9a1e`

## Scope

### In scope

- Extend `implementation/api/tests/test_password_reset_throttle.py` (the existing throttle
  suite; not a new file) with tests for gaps (1)-(4) above, the review-round regressions, and a
  pin of the shipped budgets.
- Mutation-verify every control with the sibling tests running (never `--exact`).

### Non-goals

- Padding / timing floor on the UNTHROTTLED path of `request_password_reset` — 86ak7kka2.
- `confirm_password_reset` failure logging — 86ak5r2pt. Row lock across the hash — 86ak5qy3p.
- Setting `SELAHCUE_TRUSTED_PROXY_COUNT` in production — 86ak10a13 (infra).
- Changing the shipped budget numbers.
- Per-refusal Strawberry ERROR logging and the 9 sequential Redis round trips per accepted
  request (Vera N5, N6): filed separately by the coordinator.

### Constraints

- Test-only change. A production edit is allowed only if a new test exposes a real defect.
- `test_request_reset_is_uniform_for_existing_and_missing` must pass unedited (AC4).
- No raw email in any limiter key; key space bounded by attacker-independent budgets.
- No unbounded growth; the bounded-memory test must bite.
- A timing test may not fail on host noise alone.

### Assumptions and unknowns

- Verified by the Django system check on this branch: `SELAHCUE_TRUSTED_PROXY_COUNT` is 0 unless
  the environment sets it (warning `selahcue_throttling.W001`, shown only when `CACHE_URL` is
  Redis and DEBUG is off).
- ASSUMED: `SELAHCUE_TRUSTED_PROXY_COUNT` is still unset in production (86ak10a13 is
  planning/todo). Not checkable from this repo. Owner: devops.
- UNKNOWN: the timing tests' behaviour under sustained load on GitHub's ubuntu runner (one green
  `api (django)` run on the first head; the re-measure design is evidenced below on a host, not
  on a runner).

## Dependencies and approvals

- None blocking. Independent review (Cody, Vera, Shadow, Quinn) is dispatched by the parent
  agent, not by this role. Round 1 returned; round 2 is the parent's call.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | AC1: under the SHIPPED budgets a person who mistypes their address is never refused; one legitimate request sends exactly one email and mints one live token; three same-address retries are served and the fourth is refused; the 21st request from one source is refused; the shipped numbers are pinned | `test_a_person_who_mistypes_their_address_is_never_blocked_under_the_default_budgets`, `test_one_legitimate_request_sends_exactly_one_email_and_mints_exactly_one_token`, `test_retrying_the_same_address_after_a_lost_email_works_three_times_then_stops`, `test_the_default_ip_budget_refuses_the_21st_request_from_one_source`, `test_the_shipped_reset_budgets_are_pinned_and_their_two_copies_agree` | pass | mutants M6a, M6b, M9, M10, X1, X2 RED | PASS |
| C-002 | yes | AC2, primary: a refusal by each budget does no work beyond its budget checks — exactly 0 database queries, the same cache-call sequence for a registered and an unregistered address (2, 4 or 6 calls for global, IP, address), 0 mints, 0 sends — with positive controls that the query counter and the cache recorder are alive | `test_a_refused_request_does_no_work_beyond_its_budget_checks[ip/address/global]` | pass | mutants M2, M2b, M7, M11, M12, M15 RED; M11 and M12 are caught only by this test | PASS |
| C-003 | yes | AC2: a throttled refusal is byte-identical (status, body, headers, cookies) for a registered and an unregistered address under each of the IP, address and global budgets, and sends nothing | `test_a_throttled_refusal_is_byte_identical_for_a_known_and_an_unknown_address[ip/address/global]` | pass | mutants M1a, M1b, M2, M5, M17 RED; M17 (a differing header) is caught only by this test | PASS |
| C-004 | yes | AC2, second line: the refusal takes the same time (interleaved paired comparison; "leak" only when two independent measurements exceed 1 ms on the same side), and the probe flags a planted exact 2.0 ms existence-dependent delay | `test_a_throttled_refusal_takes_the_same_time_for_a_known_and_an_unknown_address[...]`, `test_the_refusal_timing_probe_can_see_an_existence_dependent_delay` | pass; 0 false failures in 1740 null verdicts; planted delay flagged | repeat-run evidence below; mutant M7 RED | PASS |
| C-005 | yes | AC3: the limiter fails open on a store outage (response unchanged, send bounded), and a partial outage of one budget does not switch off the others | existing `test_store_unavailable_fails_open_for_request_reset`, `test_a_limiter_outage_bounds_the_reset_send_without_denying_the_response`; new `test_a_global_budget_outage_does_not_switch_off_the_address_budget` | pass | mutants M4, M13 RED | PASS |
| C-006 | yes | AC4: `test_request_reset_is_uniform_for_existing_and_missing` passes unchanged | the diff of `tests/test_customer_auth_slice.py` against `origin/main` is empty; the test passes | empty diff; pass | PR diff scope | PASS |
| C-007 | yes | AC5: mutation-verify with the sibling tests running (both whole test files, never `--exact`) | `mutate.py` matrix, 24 mutants, table below | every mutant RED; production files restored after each | table below | PASS |
| C-008 | yes | Bounded memory: the limiter creates at most `global_limit` address keys and `global_limit` IP keys however many distinct addresses and sources arrive, each with its configured expiry; malformed addresses create none | `test_the_keys_the_limiter_can_create_are_bounded_by_the_global_budget_not_by_attacker_input`, `test_a_malformed_address_is_rejected_before_any_budget_is_spent` | pass | mutants M3, M16, X8 RED | PASS |
| C-009 | yes | QA regressions: a refused request leaves the registered account's live link usable; every spelling that reaches the account shares one address budget | `test_a_refused_request_leaves_the_real_accounts_live_link_untouched_and_usable`, `test_every_spelling_that_reaches_the_account_shares_its_one_address_budget` | pass | mutants M14, M15 RED | PASS |
| C-010 | yes | The API project's own CI gates are green (system check, migrations committed, full suite) on Postgres + Redis | `manage.py check`; `manage.py makemigrations --check --noinput`; `python -m pytest tests -q` with the `api (django)` job's env | exit 0 x3; 650 passed, 1 xfailed (`test_native_account_surface.py`, from main), 0 skipped | PR body | PASS |
| C-011 | yes | PR #152 is a Draft against `main`, not behind `origin/main`, with no production-code change | `gh pr view 152`; `git rev-list --count HEAD..origin/main` is 0; `git diff --stat origin/main` lists only the test file and this contract | Draft; 0; test + contract only | PR #152 | PASS |
| C-012 | yes | Independent review (code, performance, security, QA) with blocking findings remediated | brokered by the parent agent | 0 blocking outstanding | round 1: Vera CHANGES REQUESTED (B1) now addressed; Cody APPROVE WITH CHANGES; Shadow Pass with Accepted Risk; Quinn QA PASS; round 2 not run | BLOCKED |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Mutation evidence

Each mutant was applied to production code, both whole sibling files were run
(`tests/test_password_reset_throttle.py` + `tests/test_customer_auth_slice.py`, 83 tests), and the
production files were then restored with `git checkout --` (`git status` clean for them after
every one). The mutation harness is a scratch script and is not committed; each row below states
the exact change so it can be redone by hand. Services = `apps/accounts/services.py` in
`request_password_reset`; "defaults" = the module constant and the matching setting together.

| Mutant | What was changed | Tests that failed | Caught by |
|---|---|---|---|
| M1a | per-address budget spent only when the account exists | 11 | bounded keys, byte+header, count-based, existing throttle tests x4, malformed, partial outage, timing, timing control |
| M1b | all three budgets spent only when the account exists | 23 | 21st request, bounded keys, byte+header x3, count-based x3, existing throttle tests x9, malformed, partial outage, timing x3, timing control |
| M2 | all three budgets moved after the mint and send, outside the transaction | 16 | byte+header x3, count-based x3, existing throttle tests x5, live link, spellings x3, typo/lost-email/single |
| M3 | per-address budget spent before the global budget | 4 | bounded keys, count-based x3 |
| M4 | limiter fails closed when the store is down | 5 | existing throttle tests x4, partial outage |
| M5 | per-address budget removed | 17 | bounded keys, byte+header, count-based, existing throttle tests x5, live link, malformed, partial outage, spellings x3, timing, timing control, typo/lost-email/single |
| M6a | shipped IP budget shrunk to 2 per hour (default and setting) | 7 | 21st request, auth slice, existing throttle tests, live link, pins, typo/lost-email/single x2 |
| M6b | shipped address budget shrunk to 1 per window (default and setting) | 6 | auth slice, existing throttle tests, live link, pins x2, typo/lost-email/single x2 |
| M7 | 3 ms pause before the throttle, only for registered addresses | 6 | count-based x3, timing x3 |
| M8 | raw normalised email in the address key instead of the HMAC fingerprint | 2 | existing throttle tests, timing control |
| M9 | a legitimate request is silently not sent | 26 | auth slice x10, byte+header x3, count-based x3, existing throttle tests x3, live link, spellings x3, typo/lost-email/single x3 |
| M10 | a legitimate request sends twice | 17 | auth slice, byte+header x3, count-based x3, existing throttle tests x4, spellings x3, typo/lost-email/single x3 |
| M2b | all three budgets moved after the mint and send, inside the transaction | 5 | count-based x3, existing throttle tests x2 |
| M11 | one extra lookup plus one query, only for registered addresses, in front of the address spend | 1 | count-based |
| M12 | account lookup moved in front of all three spends (the same one query for both addresses) | 3 | count-based x3 |
| M13 | `or` instead of `\|=` joining the three spends | 1 | partial outage |
| M14 | address key built from an unstripped `email.lower()` | 2 | spellings x2 |
| M15 | a throttled call first consumes the registered account's live reset link | 5 | count-based x3, live link, typo/lost-email/single |
| X1 | shipped IP budget inflated 20 to 20000 (default and setting) | 2 | 21st request, pins |
| X2 | shipped global budget inflated 500 to 500000 (default and setting) | 1 | pins |
| X8 | email validation moved after the budgets | 1 | malformed |
| M16 | key expiry 1000x too long | 1 | bounded keys |
| M17 | a response header that differs for registered addresses | 3 | byte+header x3 |

`M2`/`M2b` moved the three spend statements after the `if user is not None: ... else: pass` branches
of `request_password_reset` (outside / inside the `transaction.atomic()` block). `M7`, `M11`,
`M12` and `M15` add the code named in the row immediately before the global (`M7`, `M12`,
`M15`) or address (`M11`) spend. `X8` calls `_normalize_email` first and `_require_valid_email`
after the address spend. `M16` multiplies the window passed to `evaluate_budget` in
`guards.spend_budget` by 1000. `M17` sets a response header in the `requestPasswordReset`
resolver for addresses that start with `known-`.

## Timing probe: how it was made robust, and the evidence

Review round 1 (Vera B1, Cody High-1, Quinn N1) found that the first version — one median of 60
paired differences against a 1 ms tolerance — failed on UNMODIFIED code under load (Vera: 8 of
about 312 runs with Postgres + Redis in containers on a host at twice its core count) and that
its failure message accused the code of a leak.

Design now (Vera's Option 1): a verdict is "leak" only when TWO independent measurements both
exceed 1 ms on the SAME side; the second is taken only when the first is out. The failure
message states the two numbers and says repeating on one side is unlikely to be host noise alone,
and to read the count-based test first. The count-based test (C-002) is now the primary check and
timing is the second-line alarm. Option 2 (fastest of three tries per address) was not needed: it
costs three times the time and measured a 0.90 ms worst median under load against the 1 ms
tolerance.

Evidence, all against the committed helpers (`_refusal_timing_verdict`), Postgres 17.6 + Redis 7
in containers, fresh Postgres database and Redis db per stream, host load average 5 to 19 on 10
cores (natural load plus my own parallel streams; artificial CPU burners were refused by the
harness and not used):

- Run A, 4 parallel streams: 240 null verdicts, 0 leaks, 0 first measurements out of 1 ms
  (largest 0.30 ms); planted exact 2.0 ms delay: 80 of 80 verdicts flagged.
- Run B, 6 parallel streams: 540 null verdicts, 0 leaks, 0 first measurements out (largest
  0.47 ms); planted delay: 180 of 180 flagged.
- Run C, 8 parallel streams, load average up to 18.7: 960 null verdicts, 0 leaks; ONE first
  measurement was out (1.05 ms, IP budget) and the re-measure was inside the tolerance, so the
  verdict passed; planted delay: 149 of 160 single verdicts flagged (the 11 misses came in bursts
  of at most two in a row, in the same seconds across streams), which is why the control allows
  five attempts.
- Total: 1740 null verdicts, 0 false failures. A single-measurement probe would have failed 1
  of them.
- Replay of Vera's own loaded-host data through this verdict: 120 null verdicts, 5 first
  measurements out of 1 ms (her 4-parallel campaign), 0 would fail; her planted delays flagged
  per single verdict 39 of 40 at 2.0 ms, 33 of 40 at 1.5 ms, 13 of 40 at 1.0 ms, 1 of 40 at
  0.5 ms.
- The committed timing and count tests, run as pytest in fresh processes (7 tests per run): 30 of
  30 runs green on SQLite + LocMemCache, 20 of 20 on Postgres + Redis.

What it cannot see (stated in the test comments): a throttle moved after the mint reads +0.7 to
+0.8 ms on SQLite (under the tolerance; 2 of 40 probes flagged it in review) and +3 to +15 ms on
Postgres in containers; a lookup or small query in front of the spends reads +0.1 to +0.3 ms.
Those are caught by the count-based test, which asserts exactly zero queries and a fixed
cache-call shape. The planted-delay control is an exact busy-wait because macOS oversleeps
`time.sleep`.

## Review round 1: dispositions

Fixed in this round:

- Vera B1 / Cody High-1 / Quinn N1: two-measurement verdict, reworded message, corrected
  comment, repeat-run evidence above.
- Vera N1: count-based guard added as the primary check, with the four mutants she named plus
  `M11`/`M12` all RED, `M11` and `M12` only by that test.
- Vera N2: exact busy-wait in the control. N3: the claim that 1 ms catches a throttle moved
  after the mint is corrected in the test comments and here. N4: key expiry asserted for every
  key the limiter touches.
- Cody Medium-1: shipped numbers pinned (`X1`, `X2` now RED) and the 21st request refused under
  the defaults.
- Cody Low-1: the malformed-address assertion is its own test with the budgets open (`X8` RED).
  Low-2: the control asserts its hook ran, with a distinct message. Low-3: constant renamed with
  the underscore prefix. Low-4: this contract.
- Cody Suggestion-1: AC5 wording below. Cody Suggestion-2 / Shadow F6: headers and cookies
  compared (`M17` RED).
- Quinn T1-T3: three regression tests added (live link usable after a refusal; partial outage;
  spellings) with `M13`, `M14`, `M15` RED.
- Shadow F2: the lockout trade-off IS recorded, in this repo: `docs/delivery/goals/TASK-86akcn8p4-reset-mail-bombing-budgets.md`,
  "Risks and rollback", "Deliberate lockout, quantified (Sana, PR #107 review round 1, S-4)". It
  is not in `DECISION-LOG.md`; the PR body now cites the file precisely.

Deferred, not in this PR (the coordinator files them): Vera N5 (a Strawberry ERROR plus traceback
per refused request) and N6 (9 sequential Redis round trips per accepted request); Cody
Medium-2 / Quinn F1 (one source can exhaust the global budget with requests its own IP budget
already refuses, so about 500 requests an hour from one source make reset unavailable to
everyone) — pre-existing, order-dependent, and the order is what bounds the key space; Quinn F2
(a Redis that accepts the connection and never answers blocks `spend_budget`, so AC3 holds for a
hard-down store, not a stalled one; needs cache socket timeouts); Shadow F1 (the shared IP bucket
until `SELAHCUE_TRUSTED_PROXY_COUNT` is set, 86ak10a13, plus a boot-time refusal idea), F3
(86ak7kka2 should measure with the Celery sender, whose broker publish is synchronous), F4 (a
`DEPLOYMENT.md` paragraph on the per-worker degraded ceiling), F5 (HMAC the IP bucket; a
`SECRET_KEY` rotation runbook), F7 (informational). Cody Low-3 duplication and fixture style
(`capturing_sender` fixture beside six inline set/finally tests) and the "global test says or IP
but uses one IP" remark are left as they are: neither is wrong.

AC5, restated: the ticket's literal wording ("the uniformity test goes RED") cannot be met,
because `test_request_reset_is_uniform_for_existing_and_missing` makes one call per address and
never reaches a refusal, so it stays green for any throttle that counts requests (`M1a`, `M1b`).
Spending the budgets only for existing accounts is detected by the address-budget non-leak test
and by the byte-identical, count-based and timing tests.

## Verification plan

- Focused: `python -m pytest tests/test_password_reset_throttle.py tests/test_customer_auth_slice.py -q` (83 passed).
- Mutation: apply one mutant at a time, run BOTH whole files, record failures, `git checkout --`
  the production files.
- CI-equivalent: the `api (django)` job's three commands against Postgres 17.6 + Redis 7
  containers (the job uses postgres:16-alpine; the 17.6 image was already local).
- Independent verifier: Cody, Vera, Shadow, Quinn via the parent.
- Required environment: isolated venv `implementation/api/.venv`, Python 3.14.5,
  `pip install -e ".[dev]" "psycopg[binary]>=3.2,<4"`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-003, C-004, C-008
- Hypothesis: the shipped three-budget throttle already satisfies the ticket; only the proof is
  missing, so tests alone close the gap, and each must go RED against a mutant to count.
- Change or investigation: added 15 tests; measured the paired-timing probe's noise on a quiet
  host and its response to a throttle moved after the mint.
- Result: all new tests passed on unmodified code; 13 mutants RED.

### Iteration 2 (review round 1)

- Target criterion: C-002, C-004, C-005, C-007, C-009
- Hypothesis: the timing probe is the weak control (flaky under load, blind to small
  existence-dependent work); counts are deterministic and see what timing cannot.
- Change or investigation: count-based guard with exact-zero queries; two-measurement verdict;
  pinned numbers; header equality; Quinn's three regressions; split bounded-memory test; 11 new
  mutants. A first draft of the query counter used `CaptureQueriesContext` and read 0 queries for
  an allowed call, because the test client's `request_started` signal clears `connection.queries_log`;
  replaced by `connection.execute_wrapper`, which is not affected.
- Result: 25 new tests in the file; 24 of 24 mutants RED; 650 passed on Postgres + Redis; 1740
  null timing verdicts with 0 false failures.
- Decision: hand back for round 2.

## Risks and rollback

- Risks: the timing tests are time-based. Mitigation: the count-based test is the primary guard;
  timing needs two same-side measurements over 1 ms to fail; the control allows five attempts.
  If a GitHub runner proves noisier, the tolerance is one constant.
- Rollback: revert the test-only commits. No migration, no production code, no state.

## Pause and escalation conditions

- A new test exposing a real production defect: fix it in this branch only if small and clearly
  inside this ticket; otherwise file a linked follow-up and stop.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <path> --completion`
- Validator result: structural OK; `--completion` fails only on C-012 (BLOCKED), which is the
  independent review the parent brokers
- Independent verification result: round 1 returned (see C-012); round 2 pending
- Terminal state: GATE_REVIEW (verifiable work complete; the review gate is brokered by the parent)
- Remaining failed or blocked criteria: C-012
