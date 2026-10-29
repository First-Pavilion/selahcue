# Goal Contract — 17tnw2b2k4x

## Identity

- Goal ID: TASK-17tnw2b2k4x
- Parent goal ID: NONE
- Title: Bound synchronous transactional-email broker publishing
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b2k4x
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Signup, resend and reset requests return within a finite broker-failure budget and never promise delivery that was not confirmed.

## Baseline

Verified: main c0b8f84a publishes inline in on-commit callbacks; Redis broker socket timeouts are unset. The sender swallows failures after logging exception details. PR186 prerequisite merged d064bd96.

## Inputs and evidence sources

- Live task description and comments supplied by coordinator in /private/tmp/selahcue-batch20-20261029/additional-live-payloads.md.
- Installed Celery 5.6.3, Kombu transport and redis-py source; accounts services/email and deployment docs.

## Scope

### In scope

- Validated broker timeouts, bounded email publisher retries, safe failure logging, honest generic copy and caller integration tests.

### Non-goals

- Off-thread pipeline redesign, cache circuit breaker, reset timing-floor policy, native login and throttle diagnostics.

### Constraints

- Preserve account-existence privacy, transactions, task argument redaction and rate limits. Only synthetic private databases and broker namespaces.

### Assumptions and unknowns

- Connect blackhole cannot be deterministic on loopback; inspect actual redis client kwargs. Real silent TCP listener tests read stalls.

## Dependencies and approvals

- Approved ticket by coordinator; publication, all four independent reviews, CI, merge and QA owned by root.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Both broker timeout knobs validate and reach Redis | broker timeout tests | valid bounds accepted; invalid refused | /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-green.log | PASS |
| C-002 | yes | All three callers bound silent-broker failures and publish healthy tasks | broker timeout integration tests | accepted responses; one connection per failed publish; healthy task payloads correct | /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-green.log | PASS |
| C-003 | yes | Logs redact secrets and copy promises no delivery | email and copy tests | safe diagnostics and generic accepted copy | /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-green.log | PENDING |
| C-004 | yes | Regression and deployment documentation checks pass | API pytest suite and deployment-env-doc tests | no attributable regression; registry documented | /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-report.md | PENDING |
| C-005 | yes | All independent reviews and hosted CI pass | root coordinated Cody Quinn Vera Shadow review and CI | all pass | root delivery evidence | PENDING |

## Verification plan

- Focused verification: test_broker_socket_timeouts.py, test_email_delivery.py.
- Broader regression verification: API pytest, deployment docs guard; no Cargo/Flutter or full make ci while reserved by other agent.
- Independent verifier: Cody, Quinn, Vera and Shadow via root.
- Required environment: Python3.14, synthetic private PostgreSQL and dedicated Redis/stub ports.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002, C-003
- Hypothesis: socket timeouts plus no request-thread reconnect/publish retries bound a hard stall to one read timeout.
- Change or investigation: trace installed transport and write failing real-caller tests before implementation.
- Verifier executed: test_broker_socket_timeouts.py and test_email_delivery.py
- Result: baseline lacked configured limits; even explicit short limits incurred hidden reconnects; raw exception text leaked synthetic secrets.
- New evidence: Kombu default-channel retries use transport max_retries; publish retry is separate.
- Decision: iterate

### Iteration 2

- Target criterion: C-001, C-002, C-003
- Hypothesis: a dedicated email connection with zero reconnects and publish retries disabled bounds a silent broker, while fixed diagnostics and generic copy preserve privacy.
- Change or investigation: shipped validated 0.5 second socket defaults, per-email retry policy, once-per-minute safe logging, mail-request copy and deployment registry.
- Verifier executed: focused broker/email/docs tests; npm test; npm run build.
- Result: 103 focused tests pass; 1217 marketing tests pass and Vue typecheck/build pass. Real transaction commits publish before the HTTP response returns, with exactly one failed connection; both Redis socket kwargs and zero redis-py retries inspected. Healthy tasks carry correct names, arguments and redacted headers.
- New evidence: focused log, marketing-tests/build logs under /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-*.log. Default 0.5 second stalled requests measured 0.765/0.649/0.516/0.512 seconds for signup/existing signup/resend/reset in one run; these are local observations, not a production guarantee.
- Decision: iterate

### Iteration 3

- Target criterion: C-002, C-004
- Hypothesis: the integration test must fail if its real timeout is removed; broad failures require independent unchanged-main comparison.
- Change or investigation: omitted the shipped read timeout temporarily, then restored it; ran full PostgreSQL API suite and isolated affected cases on unchanged main and candidate.
- Verifier executed: timeout-removal mutation, full API pytest, targeted timing/no-work/cache teardown comparison.
- Result: mutant fails at 5.5-second watchdog; restored focused suite passes. Full suite: 1614 passed, two throttled-refusal timing failures and one Redis cache.clear teardown timeout. Unchanged main isolated seven-case comparison passes; candidate comparison is recorded in the handoff. A successful isolated retry does not establish a green whole suite.
- New evidence: mutation.log, full-api.log, baseline-retry.log and candidate-retry.log under the same evidence prefix.
- Decision: handoff

## Risks and rollback

- Risks: a timed-out publish has unknown delivery outcome; no automatic retry is promised. Healthy Redis round trips and DNS remain operational concerns.
- Rollback or recovery: revert this ticket; users may request a fresh link using existing flows. No schema migration.

## Pause and escalation conditions

- Escalate policy, independent review findings or unavailable private test resources to root.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2k4x-broker-timeouts.md
- Validator result: structural validator passes; completion validation remains gated on pending review and verification criteria.
- Independent verification result: pending root
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-003 requires root-coordinated rendered copy checks; C-004 retains whole-suite failure limits; C-005 requires all four independent reviews and hosted CI.
- ClickUp final evidence comment: root owns publication
