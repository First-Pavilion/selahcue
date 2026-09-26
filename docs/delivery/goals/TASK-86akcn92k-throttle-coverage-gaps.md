# Goal Contract — TASK-86akcn92k-throttle-coverage-gaps

## Identity

- Goal ID: TASK-86akcn92k-throttle-coverage-gaps
- Parent goal ID: NONE
- Title: Close three throttle-coverage gaps — reset-send degraded ceiling, sustained-denial
  alerting, and a `verify_email` budget
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akcn92k
- Created: 2026-09-26
- Updated: 2026-09-26
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Three independent sub-gaps, grouped because they share one class ("throttling that exists but
does not cover everything it appears to"):

1. `request_password_reset`'s send path has no degraded-outage ceiling — during a store outage
   it reverts to unmetered mail, unlike `resend_email_verification`, which is bounded by
   `_claim_degraded_send`.
2. `enforce_budget` raises `RATE_LIMITED` with zero logging, so a sustained attack that trips
   it repeatedly produces no signal.
3. `verify_email` has no throttle at all.

After this change: the reset send path degrades under a ceiling during an outage; sustained
denials on any scope log a suppressed-interval warning; `verify_email` spends a per-IP budget.

## Baseline

- Verified: `apps/accounts/services.py:383` (`_claim_degraded_send`) is called only from
  `resend_email_verification` (~line 922); `request_password_reset` has no such call.
- Verified: `apps/throttling/guards.py:54-57` (`enforce_budget`) calls `within_budget` and
  raises with no logging on denial.
- Verified: `apps/accounts/services.py:746` (`verify_email`) has no budget check;
  `graphql/account_schema.py:176` resolver calls it with only a raw token, no request/client_ip.
- Verified (this session, PRs #106/#107): full suite baseline is 538 passed, 0 failed against
  the dedicated Postgres 16 container.

## Inputs and evidence sources

- ClickUp 86akcn92k (full description read: F1, F3, and the scoped-out verify_email item)
- `implementation/api/selahcue_api/apps/accounts/services.py` (degraded-ceiling machinery,
  `verify_email`)
- `implementation/api/selahcue_api/apps/throttling/guards.py` (`enforce_budget`)
- `implementation/api/selahcue_api/apps/throttling/services.py`
  (`_STORE_ERROR_LOG_INTERVAL_SECONDS` pattern to mirror)
- `implementation/api/selahcue_api/graphql/account_schema.py` (resolver wiring pattern used by
  the other throttled mutations)

## Scope

### In scope

1. **Degraded-outage ceiling on the reset send.** Extend a process-local, per-worker fixed
   window ceiling to `request_password_reset`'s mint branch, spent only when the shared store
   is degraded (mirroring `_claim_degraded_send`'s "spent on every call during an outage, not
   only sends" discipline, so it cannot become an existence oracle). Own setting, own module
   state (not shared counters with the resend ceiling — a shared counter would let one flood
   starve the other endpoint's legitimate degraded-mode budget).
2. **Sustained-denial alerting, in the shared layer.** `enforce_budget` (or `within_budget`)
   gains a suppressed-interval warning log when a scope is DENIED, mirroring
   `_STORE_ERROR_LOG_INTERVAL_SECONDS`'s per-scope-suppression shape so every existing and
   future caller (resend, both reset budgets, the new verify_email budget) gets it for free.
3. **`verify_email` per-IP budget.** New budget in `verify_email`, keyed on `client_ip`,
   reusing `enforce_budget`. Thread `client_ip` through the `verifyEmail` GraphQL resolver the
   same way `requestPasswordReset` etc. already do.

### Non-goals

- The IPv6 bucketing gap (86akcn8ww, merged/in review as PR #106).
- The mail-bombing per-address/global budgets (86akcn8p4, PR #107).
- Deciding whether a process-local *sampling* ceiling (vs. only a *send* ceiling) is also
  wanted during outages for the reset REQUEST path's mint-vs-no-mint branch — the ticket
  explicitly leaves this open ("decide whether... is also wanted"); scoping this PR to a SEND
  ceiling only, matching resend's own shape exactly, and noting the sampling-ceiling question
  as an explicit deferred decision in the code comment rather than silently deciding it.

### Constraints

- The degraded ceiling must not become an account-existence oracle: spent unconditionally
  during a degraded call, not only when a mint would occur.
- The denial-alerting log must stay bounded (one line per scope per suppression interval, not
  one per denied request) — the exact defect class `_STORE_ERROR_LOG_INTERVAL_SECONDS` already
  solves elsewhere in this file.
- `verify_email`'s throttle must not weaken its own no-oracle collapse (every failure is
  VALIDATION_FAILED); RATE_LIMITED is a new, distinct, and already-established error code
  elsewhere in this file, so this mirrors existing precedent rather than inventing one.
- No CI coverage via `make ci`; the Django project's own pytest suite against Postgres is the
  gate, plus GitHub Actions `api (django)` green via `gh pr checks`.

### Assumptions and unknowns

- ASSUMED: the sustained-denial warning belongs on the DENIED outcome specifically (not
  STORE_UNAVAILABLE, which already has its own distinct warning in `services.py`), keyed by
  `scope` (not `scope:identity`, to keep the suppression state bounded rather than growing
  per-attacker-chosen-identity).
- ASSUMED: `verify_email`'s budget setting name `SELAHCUE_THROTTLE_VERIFY_EMAIL_IP`, magnitude
  matching the existing reset-confirm budget (20, 3600) — same "defence in depth against flood
  cost, not a guessing bound" reasoning the ticket gives (256-bit tokens, no practical guess).

## Dependencies and approvals

- Sequenced after 86akcn8p4 in this session (touches overlapping files); branch cut on top of
  that ticket's branch, will be rebased onto `origin/main` once both prior PRs merge.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | During a store outage, the reset send path is bounded by a process-local ceiling (send skipped once exhausted, response unchanged) | `test_a_limiter_outage_bounds_the_reset_send_without_denying_the_response` in `test_password_reset_throttle.py` | passes | test output below | PASS |
| C-002 | yes | The reset degraded ceiling is spent whether or not the account exists (no oracle) | `test_the_reset_degraded_ceiling_is_spent_whether_or_not_the_account_exists` | passes | test output below | PASS |
| C-003 | yes | A sustained run of denials on one scope logs exactly one suppressed-interval warning, not one per denial | `test_throttling_guards.py` (new file) | passes | test output below | PASS |
| C-004 | yes | `verify_email`'s (N+1)th call from one IP is refused while a different IP still passes (positive control) | `test_verify_email_nth_call_is_refused_and_earlier_calls_are_not` / `test_verify_email_budget_is_per_client_ip` in `test_customer_auth_slice.py` | passes | test output below | PASS |
| C-005 | yes | `verify_email`'s existing no-oracle collapse (every failure VALIDATION_FAILED) is unchanged | `test_verify_email_throttle_does_not_disturb_the_no_oracle_collapse` + pre-existing `test_verify_unknown_expired_consumed_are_uniform`, both pass unmodified | pass | test output below | PASS |
| C-006 | yes | Mutation check: removing each new control turns its own test(s) red, siblings unaffected | manual mutation + rerun, x3 (degraded ceiling, denial alerting removed separately from C-003's own dev, verify_email throttle) | RED then restored, each time | transcript in session log | PASS |
| C-007 | yes | Full suite regression: no new failures vs. the 538-pass baseline | `pytest -q` against Postgres (`kenji-throttling-pg`, 127.0.0.1:55432) | 538+ passed, 0 failed | 557 passed, 0 failed (post-rebase onto latest `origin/main`) | PASS |
| C-008 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) blocking findings resolved | review round + Artifact | 0 blocking outstanding | Round 1: Cody NON-BLOCKING, Sana 0 BLOCKING/4 non-blocking, Vera NON-BLOCKING, Quinn NON-BLOCKING — all four returned with zero blocking findings on the first pass. Artifact: TBD (to be published) | PASS |
| C-009 | yes | PR opened as Draft against `main`, rebased and not behind, GitHub Actions CI green | `gh pr checks` | all required checks pass | PR #109 (Draft); rebased onto `origin/main` post-review (`git merge-base --is-ancestor origin/main origin/fix/86akcn92k-throttle-coverage-gaps` confirms up to date); `gh pr checks 109` — TBD to re-confirm green post-rebase push | PENDING |

## Verification plan

- Focused verification: the three new/updated test files above.
- Broader regression verification: full `pytest -q` against the dedicated Postgres container.
- Independent verifier: Cody, Vera, Sana, Quinn.
- Required environment: `SQL_ENGINE=django.db.backends.postgresql`, `kenji-throttling-pg`
  container (127.0.0.1:55432).

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-005
- Hypothesis: (1) a sibling process-local ceiling for the reset send, keyed and shaped like
  `_claim_degraded_send` but with its own module state; (2) a warning log added to
  `enforce_budget`'s DENIED branch, suppressed per-scope on the same interval pattern used for
  store errors; (3) a new `verify_email` per-IP budget plus resolver wiring — together close
  all three sub-gaps with no shared-state cross-talk between them.
- Change or investigation: implemented as a `_DegradedSendCeiling` class (two independent
  instances: resend, reset) in `apps/accounts/services.py`; `_report_sustained_denial` added
  to `apps/throttling/guards.spend_budget`, keyed on `scope` alone; `verify_email` given a new
  `enforce_budget` call plus `client_ip` threaded through its GraphQL resolver.
- Verifier executed: `pytest tests/test_throttling_guards.py tests/test_password_reset_throttle.py tests/test_customer_auth_slice.py -q` (all pass), full suite `pytest -q` (557 passed, 0 failed), three manual mutation checks (one per sub-gap, each isolated to its own tests).
- Result: all five target criteria PASS.
- New evidence: PR #109 opened; four-reviewer round 1 (Cody, Sana, Vera, Quinn) returned zero
  blocking findings. Sana's four non-blocking notes (S-1..S-4) and Cody's/Quinn's non-blocking
  suggestions are recorded on the PR and in the consolidated review Artifact; none gate
  completion per the operating contract's "blocking findings" bar.
- Decision: handoff — proceeding to Artifact publication, CI re-confirmation post-rebase, and
  ClickUp evidence comment.

## Risks and rollback

- Risks: the new denial-alerting log could be noisy if a legitimate high-traffic caller
  sustains near-budget load — mitigated by the same suppression-interval pattern already
  proven safe for store-error logging in this file.
- Rollback: revert the single commit; each of the three changes is independent and additive,
  no migration, no persisted state change.

## Pause and escalation conditions

- None expected — all three sub-gaps mirror established patterns already reviewed and shipped
  in this same file (86akcmfd4, and this session's own 86akcn8ww/86akcn8p4).

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <path> --completion`
- Validator result: TBD
- Independent verification result: TBD
- Terminal state: TBD
- Remaining failed or blocked criteria: TBD
- ClickUp final evidence comment: TBD
