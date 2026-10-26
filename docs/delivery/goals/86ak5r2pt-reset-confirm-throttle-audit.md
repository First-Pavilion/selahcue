# Goal Contract - 86ak5r2pt-reset-confirm-throttle-audit

## Identity

- Goal ID: 86ak5r2pt-reset-confirm-throttle-audit
- Parent goal ID: NONE
- Title: A failed `confirmPasswordReset` leaves a correlatable record that holds no token material and no client address, the per-IP budget in front of it is pinned, fails open and is mutation-verified, and the response is still indistinguishable across token failures
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5r2pt
- Created: 2026-10-26
- Updated: 2026-10-27
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Every `confirmPasswordReset` call that gets past the per-IP budget and then fails (malformed, unknown, wrong-purpose, consumed or expired token, a rejected password behind a live token, or an unexpected internal failure) writes one audit row carrying only the outcome class, a keyed daily-rotating pseudonym of the source, a random per-attempt id, a timestamp and, when the token row resolves, the owning user's id. No raw, fingerprinted, hashed or masked reset token, no fragment of one, and no client IP address appears in that row or in any log line. The response to the caller is unchanged: the five token-failure classes stay byte-identical (FR-529) and `test_every_token_failure_stays_mutually_indistinguishable` passes unchanged. The per-IP budget that already guards the mutation is pinned, shown to fail open, shown to honour `X-Forwarded-For` only behind `SELAHCUE_TRUSTED_PROXY_COUNT`, shown never to block a user who retries a weak password (per source), and mutation-verified. The number of trace rows is bounded, and bounded so that noise cannot blind the trace to a probe of an account: outcomes that name no account spend a shared brake (and a per-worker ceiling while the limiter store is down), outcomes that name an account spend only that account's own allowance, keyed by user id (and a per-worker, per-account table capped in size while the store is down). All of these skip the row and never the response.

## Baseline

Verified on origin/main 93bf8063 (2026-10-26):

- `confirm_password_reset` already spends `password_reset_confirm_ip` (20 per 3600 s per client IP, `RESET_CONFIRM_IP_BUDGET`, `SELAHCUE_THROTTLE_RESET_CONFIRM`) before the token is read (86akcmfd4). The ticket text saying the mutation has no throttle describes a state before that change. `tests/test_password_reset_throttle.py` already covers the Nth-call refusal, a spoofed `X-Forwarded-For` at proxy count 0, separate sources, and fail-open on a store outage.
- The shipped confirm budget is the only reset budget with no value pin.
- No test offers a live token behind an exhausted budget, so moving `enforce_budget` below the consume would pass every existing test.
- `confirm_password_reset` writes an audit row only on success (`customer_user.password_reset_completed`, actor the customer, `request_id` the masked token). No failure path writes anything. No test in `tests/test_customer_auth_slice.py` pins the success row.
- `RESTRICTED_PAYLOAD_FIELDS` blocks `device_token`, `full_key`, `secret`, passwords and OIDC tokens from audit `before` and `after`; it has no name for a reset token. Two existing writers store a device token's fingerprint under `after["token_fingerprint"]` on purpose (`device.activated`, `device_token.reminted`); no existing writer uses `reset_token`, `raw_token` or `token_hash`.
- `ActorKind` has CUSTOMER, STAFF, DEVICE, SERVICE; an unauthenticated caller has no honest kind.
- A `newPassword` of lone surrogates (written as JSON escapes) passes the length rule, the token is marked consumed, then the hasher raises `UnicodeEncodeError`: not a `SafeAPIError`, so no row, and the view masks it to `VALIDATION_FAILED`.
- `tests/test_customer_auth_slice.py` and `tests/test_password_reset_throttle.py`: 83 passed on this commit.

## Inputs and evidence sources

- ClickUp 86ak5r2pt: description and acceptance criteria. Source: security review of 86ak5p9aq (Sana, Finding 2).
- Review round 1 of PR #232 at ac2a4a83: Cody (0 blocker, 1 major), Shadow (0 critical or high, 3 medium), Quinn (0 blocker, 1 major). The orchestrator's decisions on each are recorded in the PR.
- `implementation/api/selahcue_api/apps/accounts/services.py`, `apps/throttling/guards.py` and `services.py`, `apps/audit/services.py`, `graphql/redaction.py`, `graphql/errors.py`.
- `docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md` lines 215-222 and 372-374 (rate-limit counters expire within an hour; audit records name who acted by an internal identifier), effective 2026-10-31.
- DEC-013 and FR-529 / CON-P6 / FR-551 as cited in the code.

## Scope

### In scope

- A failed-confirm audit row (action `customer_user.password_reset_confirm_failed`, result DENIED, actor kind ANONYMOUS), written after the transaction has rolled back, in its own `atomic()`, best effort: a failure to write is counted and reported once a minute (class name, outcome and pseudonym of the first, no traceback) and never changes the response.
- A closed set of outcome classes, set by the service beside each raise, carried to the recorder in a side object and never on the exception. Any other exception inside the confirm is recorded as `internal_error` and re-raised; the owning user is recorded as soon as the token is validated.
- The source is stored only as `src:v1:<32 hex>`: Django `salted_hmac` (SHA-256, its own key salt, so structurally unlike a credential fingerprint) over the UTC date and the /64-bucketed address; the two address-less sources keep fixed labels (`src:unresolved-client-ip`, `src:unknown`). `after` holds only the outcome. `manage.py failed_reset_confirms --ip ... [--date ...]` computes the pseudonym for a known address and lists the rows.
- `_validate_password` refuses strings that cannot be UTF-8 encoded, with the code it already uses.
- Two allowances (review round 2). Outcomes that name NO account (unknown or malformed token, an internal error before any account is identified) spend a shared brake: 1000 rows an hour, one shared cache key, and 200 an hour per worker while the limiter store is down. Outcomes that NAME an account (consumed, expired, wrong purpose, rejected password, an internal error after the token validated) spend only that account's allowance, keyed by user id: 60 an hour, and 30 an hour per worker while the store is down, in a table of at most 1024 accounts with eviction. A separate shared bucket for named outcomes was rejected: anyone can mint wrong-purpose noise from tokens of accounts they own. The store is not consulted a second time once the per-source budget has failed open. Skipped rows are counted and reported once a minute with up to 20 distinct account ids. All bounded state is scalars, a capped string and a capped set of ids.
- The whole body of `_trace_failed_confirm` is protected (settings unpacking, ceilings, pseudonym, tally, logging), not only the INSERT; a malformed setting costs a counted row, never the answer. A lone-surrogate token is labelled `malformed_token`.
- The four trace knobs ship in `settings.py`, are described in `docs/ops/DEPLOYMENT.md` section 6b (with the operator command and the SECRET_KEY-rotation caveat), and are allow-listed as non-environment names in `tests/test_deployment_env_docs.py`.
- `ActorKind.ANONYMOUS` (one additive line in `graphql/context.py`); `reset_token`, `raw_token` and `token_hash` added to `RESTRICTED_PAYLOAD_FIELDS`. `token_fingerprint` is deliberately not added (two existing writers store it on purpose); tests pin the values those rows hold.
- Tests, in `tests/test_customer_auth_slice.py` (plus two pin tests next to the device audit tests), and the committed mutation harness and results under `docs/delivery/goals/86ak5r2pt-evidence/`.

### Non-goals

- The budget number. 20 per hour per IP stays; the decision is recorded in the PR.
- Setting `SELAHCUE_TRUSTED_PROXY_COUNT` in production (86ak10a13). Until it is set the whole customer base is one source: the 20 per hour are shared by everyone and every row names the proxy.
- A record for a throttled (RATE_LIMITED) attempt: the shared guard already warns once a minute per scope, and a row per refused request would re-open the write amplification the budget exists to stop.
- Audit retention and anonymise-on-delete: https://app.clickup.com/t/17tnw2b9dp1 (filed by the orchestrator). Token-derived values in other audit rows, and Strawberry's ERROR logging of literal tokens: https://app.clickup.com/t/17tnw2b9dp2 (filed by the orchestrator).
- Login with lone surrogates (found, not changed: see Risks) and padding the existing timing gaps.
- Any database migration.

### Constraints

- Strict TDD: failing tests first, then the code.
- `test_every_token_failure_stays_mutually_indistinguishable` is not edited.
- Python imports at module top level.
- No Co-Authored-By trailer or other attribution footer; push only the ticket branch; PR opened as Draft against main; no ready, no merge, no QA move.
- Footprint: `apps/accounts/services.py`, `apps/accounts/management/commands/failed_reset_confirms.py`, `tests/test_customer_auth_slice.py`, two pin tests, this contract and the evidence directory; plus the two additive shared-file edits named above, declared in the PR. The other lane (86ak1090r) owns `admin_schema.py`, `redaction.py` behaviour, `license_keys` services and the state machine; if it needs a migration, stop and tell the orchestrator.
- Disk free above 13 GiB.

### Assumptions and unknowns

- DECIDED (was ASSUMED in round 0): the source is stored as a keyed daily-rotating pseudonym, not as the address. Round 0 stored the address twice with no expiry, which contradicts the draft privacy policy (counters expire within an hour; audit records name actors by an internal identifier). Alternatives considered: the raw address with a retention period (rejected: retention is not built, 17tnw2b9dp1), and no source at all (rejected: loses the correlation the ticket asks for). A pseudonymised address is still personal data: whoever holds SECRET_KEY can test a candidate address against the table, which is what the operator command does. Retention of these rows remains an open ticket.
- UNKNOWN: behaviour against a real Redis in the test suite. The suite uses the local-memory cache and a broken-store stand-in; `real_redis_outage.py` in the evidence directory ran the trace against a genuinely unreachable Redis (connection refused).
- UNKNOWN: behaviour on Postgres. The recorder's `atomic()` is a real transaction without an enclosing one and a savepoint within one; the Postgres-only suite is skipped locally.
- NOT MEASURED: the timing of the failure branches. The skip tiers make the INSERT's presence depend on the token class (shared brake for unknown and malformed tokens, per-account allowance for consumed, expired and wrong-purpose ones), and the first account-named failure in a window makes about two fewer Redis round trips than later ones; the DEC-013 timing harness was not re-run. Practically exploitable only with a token already in hand; measure once 86ak10a13 is in place.
- NOT BOUNDED (recorded, accepted for now): rows that name an account have no aggregate ceiling (see Risks). In an outage the per-worker table's eviction gives an evicted account a fresh window.

## Dependencies and approvals

- 86akcmfd4 (the existing budget) and 86ak10a13 (production `SELAHCUE_TRUSTED_PROXY_COUNT`; the shared-bucket lockout lever, commented on by the orchestrator): context, not code dependencies.
- The other lane (86ak1090r) in worktree w2-p2: shared package, disjoint files except the additive lines above.
- Owner decision on retention of the audit rows: pending (17tnw2b9dp1). The pseudonym default was applied as the safer option.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Each failure class leaves exactly one DENIED row with its outcome, pseudonymised source, attempt id and timestamp; the user id appears only where the token row resolves | `pytest tests/test_customer_auth_slice.py -q` (the record test) | six token or password classes, eight scenarios, eight rows; `internal_error` and `unclassified` have their own tests | test_every_failed_confirm_leaves_exactly_one_record_naming_its_outcome passed; mutants B1, B3, B4, B5a, B5b, B8, B10, B12, Q04 RED (final run, 78 mutants) | PASS |
| C-002 | yes | No raw, fingerprinted, hashed or masked reset token, no 12-character fragment of one, no 6-character password prefix and no submitted password appears in any column of a failure row or in any log line; the search is proven able to find a planted whole value and a planted fragment in both places | same file (the token-material test) | zero hits; planted controls found | passed; mutants L1, L1b, L2, L3, L3b, L3c, L3d, L4 RED | PASS |
| C-003 | yes | The audit writer redacts reset-token names (`reset_token`, `raw_token`, `token_hash`) and still stores a token fingerprint; `device.activated` and `device_token.reminted` hold the real fingerprint | same file, test_activation_licence_transition.py, test_device_token_remint.py | stored values as stated | passed; mutants R1, R2a-R2c RED; R3 (fingerprint put back in the deny-list) RED in three tests across the three files | PASS |
| C-004 | yes | The five token-failure classes return byte-identical bodies, no outcome class reaches the response, and `test_every_token_failure_stays_mutually_indistinguishable` passes unchanged | same file | identical bytes; existing test GREEN and outside every diff hunk | passed; mutant B9 RED in both | PASS |
| C-005 | yes | A failure to record changes nothing the caller sees, whatever the error (RuntimeError, OperationalError, IntegrityError); the loss is counted and reported once a minute with the class, outcome and pseudonym of the first, no traceback and no token material | same file | same bytes with and without the fault; one report, then a second carrying the count | passed; mutants B2 (both swallow layers), Y07, N9, N10, Z22 RED | PASS |
| C-006 | yes | A success still writes `customer_user.password_reset_completed` and no failure row | same file | one completed row, zero failed rows | passed; mutant B11 RED | PASS |
| C-007 | yes | The budget refuses before the token is read; the refusal writes no row; the shipped 21st confirm from one source is refused | same file plus the sibling throttle file | RATE_LIMITED; token unspent; 20 rows | passed; mutants T1, T2, T8 RED | PASS |
| C-008 | yes | The shipped confirm budget, both trace allowances, both outage ceilings and the account table size are pinned, and agree with settings.py | same file | (20, 3600), (1000, 3600), (200, 3600), (60, 3600), (30, 3600), 1024 | passed; round-1 mutants T4, T9, T10 RED on 6186cf3d | PASS |
| C-009 | yes | A user who retries a weak password behind a live token is never blocked under the shipped budget, from one source, and then resets successfully | same file | PASSWORD_INVALID ten times, then success | passed; mutant B3 RED | PASS |
| C-010 | yes | With the limiter store down the mutation still reaches the service, completes a real reset, and still leaves a bounded trace | same file | no RATE_LIMITED; rows capped at the ceiling; one store round trip per request | passed; mutants T5, N3, N6 RED | PASS |
| C-011 | yes | `X-Forwarded-For` is honoured only behind `SELAHCUE_TRUSTED_PROXY_COUNT`; behind it the budget and the record name the forwarded client, not the proxy | same file | separate budgets; actor ids equal the forwarded addresses' pseudonyms; ignored at count 0 | passed; mutants T3, T6, T7 RED | PASS |
| C-012 | yes | A lone-surrogate password is a rejected password (PASSWORD_INVALID behind a live token, traced, link unspent; refused at signup) and non-ASCII passwords (accented, CJK, emoji) are still accepted at signup and reset; an unexpected failure inside the confirm (hasher error, UnicodeEncodeError, OperationalError, IntegrityError, a failing token save) leaves one `internal_error` row naming the user, answers like a dead token, leaves the link live, logs no token material, and the next reset completes; that branch honours the degraded flag | same file | as stated | passed; mutants N1, N2, Z14, Y08, Z23, B5b RED | PASS |
| C-013 | yes | No address is stored or logged; the pseudonym is pinned by an independent recomputation, keyed, rotating, versioned, per /64, with fixed labels for the two address-less sources; its day basis is the UTC day, pinned across midnight with a frozen clock; a hostile REMOTE_ADDR is never stored; the operator command finds the rows, strips whitespace, shows the account, caps its output and defaults to the writer's day | same file | as stated | passed; mutants L5-L10, B7, Q10, Q11, Q13, Q14, Z17-Z21 RED | PASS |
| C-014 | yes | The trace rows are bounded: a shared brake, per-worker outage ceilings, one shared limiter key however many sources (recorded at `evaluate_budget`, so the test means the same on LocMemCache and Redis), bounded tally state; skipped rows are counted and reported; a reset still completes while the brake is spent; against a genuinely unreachable Redis 300 failures write 200 rows | same file; `real_redis_outage.py` | as stated | passed on LocMemCache and against a real Redis 7 container; round-1 mutants N4-N8 RED on 6186cf3d; real-redis-outage.txt: round 1 (25 failures write 25 rows, 300 write 200), and re-run in round 3 on the account tier too: 300 unknown-token failures write 200 rows (shared ceiling) and 40 weak-password failures behind one account's link write 30 rows (that account's outage allowance), every response unchanged, one fail-open warning and one skip report each | PASS |
| C-015 | yes | A failed trace write leaves no half-written row and does not poison an enclosing transaction | same file (outer `atomic()`, real IntegrityError) | no row; follow-up query and next trace work | passed; mutant N11 RED | PASS |
| C-016 | yes | The committed harness runs every mutant with siblings running in full (four files, 206 to 207 tests) and restores each file byte for byte | `python3 docs/delivery/goals/86ak5r2pt-evidence/mutate.py` | every mutant RED; restored identical | mutation-results.txt: 78 mutants, 0 not RED or not restored. 75 lines from one full run; B2, N8 and N10 from a second run after the first showed B2 to be an equivalent mutant (the whole trace body is protected one level up, so I now remove both layers), N8 to need a direct test, and N10 a stale pattern. No production file differs between the runs | PASS |
| C-017 | yes | `make api-check` exits 0, including `manage.py check` and `makemigrations --check --noinput`; the full suite also passes against a real Redis | `make api-check`; the suite with `CACHE_URL` pointing at a Redis 7 container | exit 0 | make api-check exit 0 on the final head (merged with origin/main 3ab74050, which is still main): manage.py check no issues, makemigrations --check no changes, pytest 1411 passed, 24 skipped, 1 xfailed. Full suite against a real redis:7-alpine container (CI's image), one commit earlier: 1411 passed, 23 skipped, 1 xfailed, exit 0 | PASS |
| C-018 | yes | No non-ASCII in added lines, no function-local import added in code or tests, no migration | scan of the diff | clean | scans clean. The six function-local imports review round 2 found in `tests/test_customer_auth_slice.py` are at module top (`datetime`'s `timezone` imported as `dt_timezone` to avoid the clash with `django.utils.timezone`); the four that remain in that file pre-date this change. `docs/delivery/goals/86ak5r2pt-evidence/real_redis_outage.py` imports models after `django.setup()`, which cannot be done earlier (commented there). `git diff origin/main --stat` lists no migration | PASS |
| C-019 | yes | Branch is up to date with origin/main, pushed, and a Draft PR exists against main | `git rev-list --count HEAD..origin/main`, `gh pr view` | 0; Draft | recorded in the hand-off | PASS |
| C-020 | yes | The goal contract validates structurally and with `--completion` | both validators | exit 0 | OK from both validators, structural and --completion | PASS |
| C-021 | yes | Noise cannot blind the trace to a probe of an account: with the shared brake fully spent, a rejected password and a wrong-purpose token of other accounts from other sources still leave rows; a flood against account A leaves account B's row; an account's allowance bounds its own rows and a stranger's noise does not spend it; the same split holds in the outage ceiling; the outage table is bounded and evicts | same file | as stated | tests passed; mutants Q1-Q7, N4-N7 RED | PASS |
| C-022 | yes | A malformed trace setting (shared or per-account, budget or ceiling) never changes the answer or the response bytes; the loss is counted | same file | PASSWORD_INVALID / VALIDATION_FAILED bytes identical; one report | tests passed; mutant Q8 RED | PASS |
| C-023 | yes | The audit-day seam's real body is the UTC date (tested with an aware time in another zone), the operator command defaults to today, a lone-surrogate token is `malformed_token`, the pseudonym is `src:v1:` + a salted-HMAC digest pinned by an independent recomputation | same file | as stated | tests passed; mutants Q10-Q14, Z24 RED | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the tests in `tests/test_customer_auth_slice.py` run with their siblings (`tests/test_password_reset_throttle.py`, `tests/test_activation_licence_transition.py`, `tests/test_device_token_remint.py`), never `--exact`.
- Mutation verification: `docs/delivery/goals/86ak5r2pt-evidence/mutate.py`.
- Broader regression verification: `make api-check` (check, migrations committed, full pytest on SQLite).
- Independent verifier: the orchestrator dispatches Cody, Shadow, Quinn and Vera; this run does not.
- Required environment: `make api-install` venv (Python 3.14); SQLite; no Postgres or Redis.

## Iteration ledger

### Iteration 0

- Target criterion: baseline
- Hypothesis: the two relevant test files are green on origin/main 93bf8063
- Change or investigation: ran `tests/test_customer_auth_slice.py` and `tests/test_password_reset_throttle.py`
- Verifier executed: pytest under the Makefile's scrubbed environment
- Result: 83 passed, exit 0
- New evidence: the throttle half of the ticket already exists on main (see Baseline)
- Decision: iterate

### Iteration 1

- Target criterion: C-001 to C-011
- Hypothesis: with the tests written first, the existing budget already satisfies the throttle criteria and only the trace, the redaction names and the actor kind are missing
- Change or investigation: wrote the tests first (collection error, then 16 failed / 43 passed with only constants in place), then added the trace, the recorder, four deny-list names and ActorKind.ANONYMOUS
- Verifier executed: both sibling files, a 28-mutant harness, make api-check
- Result: 102 passed in the two files; all 28 mutants RED; api-check exit 0 (1364 passed)
- New evidence: none against the design
- Decision: gate-review; reviews followed

### Iteration 4 (review round 3: docs, tests and imports only)

- Target criterion: C-018 and the risk and not-verified statements
- Hypothesis: the reviewers' remaining findings are documentation and hygiene; no behaviour changes
- Change or investigation: six function-local imports moved to module top; three missing blank lines between test definitions restored; the contract, PR body and runbook now state that account-named rows have no aggregate ceiling, that the allowance is charged before the INSERT, and what the skip tiers do to timing; runbook wording fixed; the harness's pytest subprocess has a timeout and the same LANG/LC_ALL `make api-check` passes; `real_redis_outage.py` extended to a named-outcome scenario and re-run on this head
- Verifier executed: both validators, `make api-check`, the harness baseline and a sample of mutants
- Result: see C-016, C-017
- Decision: gate-review

### Iteration 3 (review round 2: Cody, Shadow)

- Target criterion: C-008, C-014, C-016, C-021 to C-023
- Hypothesis: one shared counter lets a flood blind the trace to the outcomes it exists for; splitting by whether an outcome names an account, with a per-account allowance keyed by user id, closes that without an unbounded key space
- Change or investigation: the split in the store-backed budget and in the outage ceiling (bounded table with eviction); whole-body protection of the trace; salted-HMAC key derivation with a version in the stored value; real-Redis-safe bounded-state test; real day seam test; malformed token label; settings, runbook, deployment-docs allow list; harness hardening (signal-safe restore, no hard-coded PATH); merged origin/main 3ab74050
- Verifier executed: focused files on LocMemCache and against a real redis:7-alpine container; `make api-check`; the full suite against Redis
- Result: green on both (see C-017); the 78-mutant harness green on the final code (C-016)
- New evidence: the deployment-docs test caught five names the runbook paragraph introduced; fixed by allow-listing them with reasons. Quinn's round 2 showed the UTF-8 check could be an ASCII check and no test would notice (Z14); the DB-error and command mutants (Y07, Y08, Z17-Z23) were written for her items. The first harness run exposed one equivalent mutant (B2), one mutant needing a direct test (N8) and one stale pattern (N10)
- Decision: gate-review

### Iteration 2 (review round 1: Cody, Shadow, Quinn)

- Target criterion: C-003, C-005, C-010, C-012 to C-016
- Hypothesis: each finding is closed by a test that fails first or a mutant it kills
- Change or investigation: removed `token_fingerprint` from the deny-list (two existing writers store it on purpose) and pinned both rows; lone-surrogate passwords refused and unexpected failures traced; cross-source brake and outage ceiling; pseudonymised source with an operator command; counted loss and skip reports without a traceback; atomic-write test; fragment search; spent verification token pinned; hostile REMOTE_ADDR; real unreachable-Redis demonstration; committed harness and results
- Verifier executed: sibling files (118 passed; 178 across the four files), the committed harness (53 mutants), `real_redis_outage.py`, make api-check
- Result: all green; a first draft of the outage test let a mutant survive (the per-source degraded flag was redundant with the brake's own outage detection); fixed by asserting one store round trip per request
- New evidence: login with lone surrogates also fails masked (see Risks)
- Decision: gate-review

## Risks and rollback

- Risks:
  - The failure row turns an unauthenticated read path into a write path. Rows that name NO account (unknown or malformed token, an internal error before any account was identified) are bounded per source by the per-IP budget, across sources by the shared 1000 an hour brake, and while the limiter store is down by a 200 an hour per-worker ceiling (N workers: N times that). A mis-set `SELAHCUE_TRUSTED_PROXY_COUNT` lets a caller choose its own left-hand `X-Forwarded-For` entry and so a fresh per-source budget per request; for this class the shared brake is what bounds that case.
  - **Rows that NAME an account have NO aggregate ceiling.** The shared brake skips only rows that name no account, and an account's rows compete only with that account's own allowance (60 an hour, 30 per worker in an outage): probing ONE account more than 60 times an hour leaves the later rows unwritten (counted, and the report names the account id). Nothing bounds the total across accounts. The real bound on how fast a caller can fill accounts is the per-source budget (20 an hour per source), and that holds only while `SELAHCUE_TRUSTED_PROXY_COUNT` is right and a caller cannot pick a fresh source per request. `register_customer_user` has no budget of its own, so accounts, each with its own tokens and its own allowance, are cheap to create. In an outage the per-worker table holds 1024 accounts and evicts the oldest window, so rotating through more than 1024 accounts gives each claim a fresh window. This is a recorded, accepted-for-now residual; the follow-up (an aggregate ceiling for named outcomes and a registration throttle) is filed by the orchestrator, not part of this PR.
  - **The allowance is charged before the INSERT.** With a healthy cache and a down audit store, every lost write still spends the account's allowance for that hour, so once it is gone later rows are reported as skipped while the real cause is the store. Bounded to the hour and counted in both reports; documented in the runbook. No code change.
  - A pseudonymised source is still personal data and the audit table has no retention (17tnw2b9dp1).
  - Other audit rows still hold token-derived values and Strawberry logs tracebacks of masked resolver errors (17tnw2b9dp2).
  - Until `SELAHCUE_TRUSTED_PROXY_COUNT` is set in production (86ak10a13) every caller is one source: 20 per hour shared by everyone, and every row names the proxy.
  - Timing: the INSERT and commit run on dead-token classes unevenly. The skip tiers make the INSERT's presence depend on the token class (the shared brake for unknown and malformed tokens, the per-account allowance for consumed, expired and wrong-purpose ones), and the first account-named failure in a window makes about two fewer Redis round trips than later ones. Both are unmeasured (the DEC-013 harness was not re-run), practically exploitable only by someone who already holds a token, and should be measured once 86ak10a13 is in place. No claim is made about the gaps.
  - Login with lone surrogates raises an unhandled `UnicodeEncodeError` that the view masks to `VALIDATION_FAILED` for known and unknown accounts alike. It is uniform, so not an oracle, and not changed here.
  - The hostile REMOTE_ADDR text still reaches the throttle cache key (Django warns); only the server sets it. Pre-existing.
- Rollback or recovery: revert the commits. No migration, no data change, no settings change. Rows already written stay in the audit table and are harmless.

## Pause and escalation conditions

- Any need for a database migration: stop and tell the orchestrator (two migrations in one app collide with the other lane).
- A conflict with the other lane on `redaction.py` or `context.py` that needs a judgement call: stop and ask.
- Disk free below the floor the orchestrator sets for the run (13 GiB in round 1, 12 GiB in round 2): stop heavy runs.
- Any change that would alter a response body or code on the token-failure path: stop, that is FR-529.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak5r2pt-reset-confirm-throttle-audit.md --completion`
- Validator result: OK (structural) and OK (--completion) on the final head
- Independent verification result: round 1 done (Cody, Shadow, Quinn: no blockers); round 2 on cc62068c: Cody PASS (0 blocker, 0 major), Shadow PASS and signed off, per the orchestrator; Quinn's round 3 is pending. The PR stays Draft until the reviews clear
- Terminal state: GATE_REVIEW (all mandatory criteria PASS; not VERIFIED_COMPLETE because the independent re-review of this head has not run)
- Remaining failed or blocked criteria: none. Not run locally: Postgres, hosted CI, the timing harness
- ClickUp final evidence comment: posted on 86ak5r2pt at hand-off
