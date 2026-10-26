# Goal Contract - 86ak5r2pt-reset-confirm-throttle-audit

## Identity

- Goal ID: 86ak5r2pt-reset-confirm-throttle-audit
- Parent goal ID: NONE
- Title: A failed `confirmPasswordReset` leaves a correlatable record that holds no token material, and the per-IP budget in front of it is pinned, fails open and is mutation-verified, with the response still indistinguishable across token failures
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5r2pt
- Created: 2026-10-26
- Updated: 2026-10-26
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Every `confirmPasswordReset` call that gets past the per-IP budget and then fails (malformed, unknown, wrong-purpose, consumed or expired token, or a rejected password behind a live token) writes one audit row carrying only the outcome class, the source IP bucket, a per-attempt id, a timestamp and, when the token row resolves, the owning user's id. No raw, fingerprinted, hashed or masked reset token appears in that row or in any log line. The response to the caller is unchanged: the five token-failure classes stay byte-identical (FR-529) and `test_every_token_failure_stays_mutually_indistinguishable` passes unchanged. The per-IP budget that already guards the mutation is pinned, shown to fail open, shown to honour `X-Forwarded-For` only behind `SELAHCUE_TRUSTED_PROXY_COUNT`, shown never to block a user who retries a weak password, and mutation-verified.

## Baseline

Verified on origin/main 93bf8063 (2026-10-26):

- `confirm_password_reset` already spends `password_reset_confirm_ip` (20 per 3600 s per client IP, `RESET_CONFIRM_IP_BUDGET`, `SELAHCUE_THROTTLE_RESET_CONFIRM`) before the token is read (86akcmfd4). The ticket text saying the mutation has no throttle describes a state before that change. `tests/test_password_reset_throttle.py` already covers the Nth-call refusal, a spoofed `X-Forwarded-For` at proxy count 0, separate sources, and fail-open on a store outage.
- The shipped confirm budget is the only reset budget with no value pin (`test_the_shipped_reset_budgets_are_pinned_and_their_two_copies_agree` lists the request-side budgets and the degraded ceiling only).
- No test offers a live token behind an exhausted budget, so moving `enforce_budget` below the consume would pass every existing test.
- `confirm_password_reset` writes an audit row only on success (`customer_user.password_reset_completed`, actor the customer, `request_id` the masked token). No failure path writes anything. No test in `tests/test_customer_auth_slice.py` pins the success row.
- `RESTRICTED_PAYLOAD_FIELDS` blocks `device_token`, `full_key`, `secret`, passwords and OIDC tokens from audit `before` and `after`; it has no name for a reset token, a token fingerprint or a token hash.
- `ActorKind` has CUSTOMER, STAFF, DEVICE, SERVICE; an unauthenticated caller has no honest kind.
- `tests/test_customer_auth_slice.py` and `tests/test_password_reset_throttle.py`: 83 passed on this commit.

## Inputs and evidence sources

- ClickUp 86ak5r2pt: description and acceptance criteria. Source: security review of 86ak5p9aq (Sana, Finding 2).
- `implementation/api/selahcue_api/apps/accounts/services.py` (`confirm_password_reset`, the budgets, `_report_unresolved_client_ip`).
- `implementation/api/selahcue_api/apps/throttling/guards.py` and `services.py` (`enforce_budget`, `client_ip`).
- `implementation/api/selahcue_api/apps/audit/services.py` (`record_audit_event`) and `graphql/redaction.py`.
- `implementation/api/selahcue_api/graphql/errors.py` (the argument for the collapsed code and for `PASSWORD_INVALID`).
- DEC-013 and FR-529 / CON-P6 / FR-551 as cited in the code.

## Scope

### In scope

- A failed-confirm audit row (action `customer_user.password_reset_confirm_failed`, result DENIED, actor kind ANONYMOUS with the source bucket as actor id), written after the transaction has rolled back, in its own savepoint, best effort: a failure to write is logged once a minute and never changes the response.
- A closed set of outcome classes, set by the service beside each raise, carried to the recorder in a side object and never on the exception, so a class cannot reach the response.
- `ActorKind.ANONYMOUS` (one additive line in `graphql/context.py`; `actor_kind` is a free-text column, no migration).
- Reset-token field names added to `RESTRICTED_PAYLOAD_FIELDS` (`reset_token`, `raw_token`, `token_fingerprint`, `token_hash`), so the audit writer redacts them anywhere in the codebase.
- Tests, in `tests/test_customer_auth_slice.py`: one record per failure class; success row pinned and no failure row on success; no token material in any audit column or log line (with a positive control); response bodies byte-identical across the token-failure classes; recording failure leaves the response unchanged; throttle refuses before the token is read and writes no row; confirm budget pinned; weak-password retries never blocked; fail-open still reaches the service and still leaves a trace; `X-Forwarded-For` honoured only behind the proxy count and the record names the derived source; unresolved and over-long sources.
- Mutation verification of the throttle and the redaction guard, siblings running, not `--exact`, each file restored byte for byte.

### Non-goals

- The budget number. 20 per hour per IP stays; the decision is recorded in the PR.
- Setting `SELAHCUE_TRUSTED_PROXY_COUNT` in production (86ak10a13).
- A record for a throttled (RATE_LIMITED) attempt: the shared guard already emits a once-a-minute warning per scope, and a row per refused request would re-open the write amplification the budget exists to stop.
- Audit retention or pruning, a process-local ceiling for trace writes while the limiter is down, and padding the existing timing gaps. Listed as follow-ups in the PR.
- Any database migration.

### Constraints

- Strict TDD: failing tests first, then the code.
- `test_every_token_failure_stays_mutually_indistinguishable` is not edited.
- Python imports at module top level.
- No Co-Authored-By trailer or other attribution footer; push only the ticket branch; PR opened as Draft against main; no ready, no merge, no QA move.
- Footprint: `apps/accounts/services.py`, `tests/test_customer_auth_slice.py`, this contract; plus the two additive shared-file lines named above, declared in the PR. The other lane (86ak1090r) owns `admin_schema.py`, `redaction.py` behaviour, `license_keys` services and the state machine; if it needs a migration, stop and tell the orchestrator.
- Disk free above 13 GiB.

### Assumptions and unknowns

- ASSUMED: the source IP bucket may be stored in the audit row. It is already held in the limiter cache for an hour; the audit table has no retention, so the row keeps it longer. Validation owner: the orchestrator and the owner, in PR review.
- UNKNOWN: behaviour against a real Redis. The suite runs the limiter on the local-memory cache and a broken-store stand-in.
- UNKNOWN: behaviour on Postgres. The recorder uses a savepoint, which SQLite also honours, but the Postgres-only suite is skipped locally.

## Dependencies and approvals

- 86akcmfd4 (the existing budget) and 86ak10a13 (production `SELAHCUE_TRUSTED_PROXY_COUNT`): context, not code dependencies.
- The other lane (86ak1090r) in worktree w2-p2: shared package, disjoint files except the two additive lines above.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Each failure class leaves exactly one DENIED row with its outcome, source, attempt id and timestamp; the user id appears only where the token row resolves | `pytest tests/test_customer_auth_slice.py -q` (the record test) | six classes, six rows, fields as stated | PENDING | PENDING |
| C-002 | yes | No raw, fingerprinted, hashed or masked reset token, and no submitted password, appears in any column of a failure row or in any log line, and the search is proven able to find a planted token | same file (the token-material test) | zero hits; planted control found | PENDING | PENDING |
| C-003 | yes | The audit writer redacts the reset-token field names; removing them turns a test red | same file (the redaction test) plus mutation | stored value is `[redacted]`; mutant RED | PENDING | PENDING |
| C-004 | yes | The five token-failure classes return byte-identical bodies, no outcome class reaches the response, and `test_every_token_failure_stays_mutually_indistinguishable` passes unchanged | same file | identical bytes; existing test GREEN and unedited (`git diff` shows no change inside it) | PENDING | PENDING |
| C-005 | yes | A failure to write the record changes nothing the caller sees and is logged without token material | same file | same code and message as without the fault; one log line | PENDING | PENDING |
| C-006 | yes | A success still writes `customer_user.password_reset_completed` and no failure row | same file | one completed row, zero failed rows | PENDING | PENDING |
| C-007 | yes | The budget refuses before the token is read: an exhausted source offering a live token and a good password is refused, the token is unspent, the password unchanged, and no row is written for the refusal | same file plus mutation (throttle removed, and throttle moved below the consume) | RATE_LIMITED; token unspent; mutants RED | PENDING | PENDING |
| C-008 | yes | The shipped confirm budget is pinned at (20, 3600) and the setting equals the module default | same file | pinned | PENDING | PENDING |
| C-009 | yes | A user who retries a weak password behind a live token is never blocked under the shipped budget and then resets successfully | same file | PASSWORD_INVALID each time, then success | PENDING | PENDING |
| C-010 | yes | With the limiter store down the mutation still reaches the service, completes a real reset, and still leaves its trace | same file | no RATE_LIMITED; rows written | PENDING | PENDING |
| C-011 | yes | `X-Forwarded-For` is honoured only behind `SELAHCUE_TRUSTED_PROXY_COUNT`; behind it the record and the budget name the forwarded client, not the proxy | same file | separate budgets and source equal the forwarded address; ignored at count 0 | PENDING | PENDING |
| C-012 | yes | The mutation harness shows every guard RED with siblings running and restores each file byte for byte | harness run, `cmp` after each restore | every mutant RED; `cmp` exit 0 | PENDING | PENDING |
| C-013 | yes | `make api-check` exits 0, including `manage.py check` and `makemigrations --check --noinput` | `make api-check` | exit 0 | PENDING | PENDING |
| C-014 | yes | No non-ASCII in touched files, no function-local import added, no migration | scan of the diff | clean | PENDING | PENDING |
| C-015 | yes | Branch is up to date with origin/main, pushed, and a Draft PR exists against main | `git rev-list --count HEAD..origin/main`, `gh pr view` | 0; Draft | PENDING | PENDING |
| C-016 | yes | The goal contract validates structurally now and with `--completion` before the claim | `validate_goal_contract.py` | exit 0 both times | PENDING | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the new tests in `tests/test_customer_auth_slice.py`, run with their siblings (that file and `tests/test_password_reset_throttle.py`), never `--exact`.
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

## Risks and rollback

- Risks: the failure row turns an unauthenticated read path into a write path. It is bounded by the per-IP budget only; while the limiter store is down (fail open) it is unbounded, and the audit table has no retention. The new INSERT runs on every failure branch alike, so it adds a constant, not a new gap, but the existing timing gaps (DEC-013) were not re-measured. The source IP is stored with no expiry.
- Rollback or recovery: revert the commit. No migration, no data change, no settings change. Rows already written stay in the audit table and are harmless.

## Pause and escalation conditions

- Any need for a database migration: stop and tell the orchestrator (two migrations in one app collide with the other lane).
- A conflict with the other lane on `redaction.py` or `context.py` that needs a judgement call: stop and ask.
- Disk free below 13 GiB: stop.
- Any change that would alter a response body or code on the token-failure path: stop, that is FR-529.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak5r2pt-reset-confirm-throttle-audit.md --completion`
- Validator result: PENDING
- Independent verification result: NOT YET RUN
- Terminal state: PENDING
- Remaining failed or blocked criteria: PENDING
- ClickUp final evidence comment: PENDING
