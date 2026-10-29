# Goal Contract — TASK-86ak5qy3p

## Identity

- Goal ID: TASK-86ak5qy3p
- Parent goal ID: NONE
- Title: Hash a validated reset password before taking token and user row locks
- Role: backend-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/86ak5qy3p
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Password-reset PBKDF2 runs after validating the token and password but before this service takes row locks; a fresh locked token check preserves single use and current expiry before the atomic password/session/audit update.

## Baseline

Verified main d8b296efd2e807393b0b32870464ba33cde54bf6: _consume_reset_token locks CredentialToken joined to CustomerUser, checks liveness and password, then runs make_password while both rows are locked. Root supplied complete live task/comments: Normal planning/todo, no blockers; safe offload or documented retention is allowed. Chosen safe offload after source confirms the existing atomic boundary and token checks.

## Inputs and evidence sources

- Root's full live task extract: /private/tmp/selahcue-batch20-20261029/api-queued-payloads.md section86ak5qy3p.
- accounts/services.py reset and trace paths; CredentialToken/CustomerUser/CustomerSession models.
- Existing test_customer_auth_slice.py and PostgreSQL concurrency lock-observer patterns.
- FR-551/FR-529, DEC-012/DEC-017 password-error versus collapsed-token rules.

## Scope

### In scope

- Initial nonlocking token liveness check before password policy and hashing.
- Password policy and PBKDF2 before the service's write transaction and row locks.
- Fresh locked revalidation, then atomic consume/password update/session revocation/audit.
- Behavior-first mutation and real PostgreSQL lock/concurrency evidence.

### Non-goals

- Session-token hash format/migration, login behavior, browser/API contracts, throttle budgets/logging, dependency or schema changes.
- Promise to remove caller-owned outer transactions; production has no ATOMIC_REQUESTS, and this service does not create the hashing transaction.

### Constraints

- Never hash unvalidated/expired/consumed/wrong-purpose tokens, never examine password policy before initial token validation.
- Valid token plus weak password remains PASSWORD_INVALID and does not consume the link.
- A token that becomes dead during hashing or lock wait is refused with the existing collapsed token error.
- Existing named reset/session-revocation and single-use tests remain unchanged.
- Root owns ClickUp status/evidence, PR/CI, four independent reviews, merge and QA; no child UI or publication.

### Assumptions and unknowns

- Verified production database is PostgreSQL; SQLite cannot prove row locking.
- Valid concurrent submissions may both pay PBKDF2, but exactly one may consume the same token; replay after consumption must not hash.

## Dependencies and approvals

- User explicitly authorized implementation agents, all four independent reviews, valid remediation and merge/QA.
- Isolated managed worktree and one ticket branch, cut from fresh main; root supplied live ClickUp evidence while UI inaccessible.
- Dedicated synthetic PostgreSQL database and separate cache namespace; never flush another task's cache/database.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Initial token validation precedes password policy/KDF, FR-551 preserved | Extended auth slice plus unchanged named reset tests | Dead token no hash, live weak password password error, no link burn | /private/tmp/selahcue-batch20-20261029/86ak5qy3p-postgres.log | PASS |
| C-002 | yes | Actual PostgreSQL token/user rows are free during real password KDF | Independent-connection NOWAIT observer during hash | Both locks acquired and hasher outside service atomic | /private/tmp/selahcue-batch20-20261029/86ak5qy3p-postgres.log | PASS |
| C-003 | yes | Fresh locked guard preserves single use and expiry under overlap | Actual PG same-token two-submit race, state-change cases and guard-removal mutation | Exactly one success/one refusal, one completed audit; mutant red with passing siblings | /private/tmp/selahcue-batch20-20261029/86ak5qy3p-mutation.log and expiry-mutation.log | PASS |
| C-004 | yes | Required broad regression and current-target checks pass | Complete API pytest, system/migrations/diff/goal checks, target ancestry and clean status | No introduced failures, actual environment/evidence scoped, behind0 at freeze | /private/tmp/selahcue-batch20-20261029/86ak5qy3p-report.md | BLOCKED |
| C-005 | yes | All four independent reviewers pass after valid fixes | Cody, Quinn, Vera, Shadow exact-head reports | Four Pass, no unresolved blocking finding | Coordinator reports | BLOCKED |
| C-006 | yes | Exact-head hosted CI passes, linked PR merges and ClickUp savesQA | Coordinator hosted CI/merge/status read-back | Verified merge and persistedQA | Coordinator delivery evidence | BLOCKED |

## Verification plan

- Focused verification: initial RED on lock-free and token-state-during-hash assertions, then complete auth and PG concurrency modules.
- Broader regression verification: full API suite after final source changes; final document edits get relevant verification before freeze.
- Independent verifier: Cody, Quinn, Vera and Shadow, root-coordinated.
- Required environment: Python3.14/Django6.1.2, real PostgreSQL16 for locks/concurrency, synthetic isolated data and process-local cache where sufficient.

## Iteration ledger

### Iteration1 — trace and baseline

- Target criterion: C-001/C-002/C-003.
- Hypothesis: removing PBKDF2 from the locked section is safe only with initial validation and a new current locked check after hashing.
- Change or investigation: traced token parsing/fingerprint, all liveness fields, password policy, trace classification, joined user locks, atomic session revocation and audit rollback.
- Verifier executed: pending regression-first baseline.
- Result: source confirms the KDF currently holds both rows.
- New evidence: exact baseline source and existing real-PG NOWAIT/concurrent-connection patterns.
- Decision: iterate.

## Risks and rollback

- Risks: a new gap exists between preliminary liveness and write lock; only the fresh locked revalidation authorizes writes. Two truly concurrent valid callers may both hash; throttles remain unchanged.
- Rollback or recovery: revert this ticket; credential/password/session storage formats unchanged, no migration.

## Pause and escalation conditions

- Stop for business/credential-contract changes, unavailable required PostgreSQL evidence, unsafe access or three failed approaches without new evidence.
- No self-review or source changes after review freeze; return valid findings to author with scoped re-review.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak5qy3p-reset-kdf-lock.md
- Validator result: structural PASS; final evidence-only goal update must be revalidated before freeze.
- Independent verification result: pending root-owned four reviews and clean exact-head hosted API CI.
- Terminal state: BLOCKED on full hosted gate and independent review/delivery.
- Remaining failed or blocked criteria: C-004/C-005/C-006.
- ClickUp final evidence comment: root-owned pending handoff.


### Iteration2 — off-lock hash and mutation-backed locked revalidation

- Target criterion: C-001/C-002/C-003.
- Hypothesis: initial liveness establishes permission to inspect/hash the password; only a current locked read can authorize writes after the hash and any lock wait.
- Change or investigation: shared liveness reader checks fingerprint, purpose, consumed and current expiry. Preliminary read is nonlocking; password policy and real make_password run before this service's atomic block. Locked joined token/user re-read performs the same checks with clock read after query return. Consume/password/session/audit writes remain one transaction. Session-token hashing, budgets and browser contracts are untouched.
- Verifier executed: regression-first actual PostgreSQL baseline, initial restored focus, guard-removal fault plugin across BOTH full auth/concurrency modules, additional real lock-queue expiry probe, then final integrated focused PostgreSQL checks.
- Result: initial unchanged-production baseline7failed/6passed (37.77seconds). Restored focus16passed including the two unchanged named reset tests and rollback. Removing only second-phase liveness while keeping real ORM locks gives6failed/134passed across both complete modules (109.85seconds): five during-hash state/time changes and real two-call double consumption. Added lock-queue expiry probe also rejects the mutant:2failed/1positive-control passed among the three reset PostgreSQL tests. Final restored integrated focus17passed/124deselected (51.20seconds), including actual token/user NOWAIT availability, same-token exactly-one success/refusal and expiry after a proven token-query wait. No elapsed KDF performance claim is made.
- New evidence:86ak5qy3p-red.log, focused.log, mutation.log/.exit, expiry-mutation.log and postgres.log. Mutations replace the actual production liveness helper in a separate pytest process, preserving real database queries/locks; no fabricated outcomes or tracked source edits. Final expiry observer refreshes its PostgreSQL activity snapshot while holding the test lock and confirms the credential-table query before advancing its clock.
- Decision: run the complete restored API gate after all source/test changes; full module and hosted-CI claims remain separate.

### Iteration3 — current target and complete API gate

- Target criterion: C-004.
- Hypothesis: the reset-only transaction-boundary change preserves all existing account, throttle, trace and rollback behavior on the latest target.
- Change or investigation: fetched/integrated main712358a209a01d293fb4b310ebe0ca0d6d3f8846 after the mutation, inspected its entire throttle-header/docs/tests delta and verified no accounts-services overlap. No new operational-doc prose or executable edits are planned after the final gate starts.
- Verifier executed: complete restored API pytest on dedicated PostgreSQL/Redis, plus system/migration/diff/structural checks; actual output recorded in the external handoff report before any success claim.
- Result: complete local run1575passed/1failed/1setup error,904.24seconds, exit1. The setup error is Redis TimeoutError in test_password_reset_throttle.py::test_request_reset_nth_call_is_refused_and_earlier_calls_are_not, at fixture cache.clear before the test body. Failure is test_a_throttled_refusal_takes_the_same_time_for_a_known_and_an_unknown_address[address], paired gaps+2.32/+5.33ms versus1ms. The deterministic zero-extra-work guards passed in that full run. Exact two nodes plus all three deterministic guards then passed unchanged on candidate5/5 (6.58seconds), and on reviewed baseline469e834c5/5 (3.36seconds), whose API tree equals current main712358a. Neither request-reset path invokes the changed confirm-reset code. These observations support a transient host/Redis explanation, not proof of a permanent baseline defect or a complete-suite pass. C-004 remains BLOCKED until clean exact-head hosted full API verification. Any final evidence-only goal update receives fresh structural/diff validation and executable-tree equality proof.
- New evidence:86ak5qy3p-full-api.log/.exit and final report under the batch evidence directory.
- Decision: hand off only after the complete run and current-target freeze; C-005/C-006 remain independent coordinator gates.


### Iteration4 — broad-failure diagnosis and frozen handoff

- Target criterion: C-004; no source change.
- Hypothesis: full-run setup timeout and request-refusal timing alarm are outside the reset-confirm change; exact candidate/baseline reruns and deterministic guards can test that hypothesis without weakening checks.
- Change or investigation: kept executable/test tree60e797d022af781eea34c3591188293efc500565 unchanged; read both tracebacks, the request-reset timing test's existing overload caveat and count-based primary guard. Compared unchanged request-reset/test paths, verified reviewed baseline API tree equality and used separate synthetic PG databases with own Redis10.
- Verifier executed: both exact problem nodes plus all three primary count-based guards on candidate and baseline, without timeout/tolerance/skip changes.
- Result: candidate5passed, baseline5passed; no issue reproduced. The full local run remains red and is not relabeled green. No introduced reset regression was demonstrated; only final hosted full CI may close C-004/C-006. System checks/migrations and structural/diff checks passed, named acceptance tests are unchanged, source/test equality to the full-run tree is verified before final commit.
- New evidence:86ak5qy3p-candidate-retry.log and baseline-retry.log, full-api.log/.exit, static.log and immutable final patch/report. Baseline checkout was read/tested only; no tracked writes or other task's data changed.
- Decision: BLOCKED handoff for root-owned all-four review and clean exact-head hosted CI, then conditional merge and QA. No tracked edits after freeze during review.
