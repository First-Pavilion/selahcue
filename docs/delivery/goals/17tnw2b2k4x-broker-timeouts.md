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
| C-001 | yes | Both broker timeout knobs validate and reach Redis | broker timeout tests | valid bounds accepted; invalid refused | /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-result-subscription-final.log | PASS |
| C-002 | yes | All three callers bound silent-broker failures and publish healthy tasks | broker timeout integration tests | accepted responses; one connection per failed publish; healthy task payloads correct | /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-result-subscription-final.log | PASS |
| C-003 | yes | Logs redact secrets and copy promises no delivery | email and copy tests | safe diagnostics and generic accepted copy | /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-remediated-auth.log and result-subscription-final.log | PASS |
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

### Iteration 4

- Target criterion: C-003, C-004, C-005
- Hypothesis: retaining all checks but matching the approved conditional acknowledgement wording and the five added assertions' exact count restores the rendered gate.
- Change or investigation: Cody found four stale substring assertions and the unchanged 2570 count. Correct only those four expectations and the exact 2575 count/provenance; preserve all 71 scenarios, privacy pairs, TTL checks and no-delivery-claim checks. Integrate actually merged native-observability and shared launcher fixes through main 6ef0e098.
- Verifier executed: actual hosted CI40875032873 establishes RED (71 scenarios, 2575 checks, four conditional-copy failures and stale exact2570 guard). After correction, complete real required-Chrome auth gate and durable full PostgreSQL/LocMem API run executed to completion with atomic exit0 receipts.
- Result: rendered gate passes all 71 scenarios, 2575 checks and zero failures; Vue typecheck/build passes. Full PostgreSQL/LocMem API passes 1676 tests with exactly two real-cache-only skips (healthy cache counting and response headers; CACHE_URL is empty). Dedicated real-broker healthy cases and silent broker fixtures ran. This proves the supported LocMem configuration, not the final hosted PostgreSQL/Redis gate.
- New evidence: remediated-auth.log/json/exit and remediated-full-api.log/json/exit under /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-; the full API took 1173.44 seconds. The previous lost 69-percent process is incomplete, and earlier Redis failures/interruption remain separate in the handoff. Full executed source equals head871977cb plus dirty diff49e7f691; only this goal evidence changed after those passing snapshots. Final source fingerprints and fresh focused/docs/static checks are recorded in the handoff.
- Decision: handoff

### Iteration 5

- Target criterion: C-004, C-005
- Hypothesis: preserving published history with merge commits and keeping the tested email/frontend tree unchanged permits a proportional fresh-main integration check without repeating the complete previous snapshots.
- Change or investigation: merge the published1097d570 history into8c7585c5, resolving only the goal add/add conflict with the current evidence. Before any main integration, verify the complete merge tree equals tested8c tree00116b777b71b83df77e38b691bba6c865609f4b. Then merge actually published main d5476edd (native bootstrap fail-closed) without rebasing. Preserve its native-bootstrap deployment exception and this ticket's broker-bound paragraphs.
- Verifier executed: exact tree and ancestry proofs; byte comparisons for all email publisher/caller/frontend/helper/tests against8c and incoming native-bootstrap code/tests against main; fresh broker/email/native-outage/deployment checks and static checks recorded in the handoff.
- Result: the published1097 history is an ancestor, the history-only merge tree exactly matches8c, and the email/frontend/caller source is unchanged from the passing complete snapshots. The original1676-pass PostgreSQL/LocMem and71-scenario rendered runs predate WQ9; fresh focused coverage must verify the combined source and final hosted CI remains mandatory. No complete full/API browser rerun is claimed for the combined tree.
- New evidence: history-merge-proof.json; main-merge-fingerprints.json; integration-focused.log and integration-static.log under /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-.
- Decision: handoff

### Iteration 6

- Target criterion: C-002, C-004, C-005
- Hypothesis: unused email-result subscriptions bypass the broker limits; per-publish ignore_result prevents that synchronous I/O without changing task defaults or unrelated result consumers.
- Change or investigation: Shadow S260-1 and Vera independently confirmed RedisBackend.on_task_call subscribes before publication. Repository reference search finds no email result consumer: sender methods return None and discard AsyncResult; email tasks return no data. Add actual committed HTTP/shared-task regressions with Redis result backend defaults (read120 seconds, connectNone), separate silent result/broker endpoints, and healthy-broker/silent-result controls; retain explicit memory-backend siblings. Set ignore_result=True only at this sender's apply_async call, leaving all task/global defaults unchanged.
- Verifier executed: before production correction, four Redis-result HTTP cases fail at the5.5-second BaseException watchdog with on_task_call/subscription in the stack. Final focused broker/email/native-outage/docs checks, regression/mutation receipts and effective configuration evidence are recorded in the handoff.
- Result: corrected source passes191 focused PostgreSQL checks, including four Redis-result/silent-broker committed HTTP calls, four healthy-broker/silent-result calls and the memory siblings. Requests measured0.642/0.644/0.515/0.524 seconds at the0.5-second broker limit, with zero result connections/subscriptions. Healthy messages retain task names/args/redacted headers and set only their message ignore-result flag. Removing that one flag makes reset hit the5.5-second watchdog again; source restored in finally. An actual production Django/Celery app probe returned0.511 seconds with zero result connections, one broker connection, result defaults120/None, app/email/unrelated-sweep ignore-result defaults False and global publish retry True. Global result timeouts and worker/revocation policy are unchanged. Existing complete API and71/2575 rendered results remain earlier snapshots; Vue/auth sources are unchanged and not rerun for this backend-only correction. C-004 is returned to PENDING for the exact-head full API gate; exact-head hosted CI and all four re-reviews remain mandatory.
- New evidence: result-subscription-red.log/exit; email-result-consumer-search.log; result-subscription-green.log and result-scope-probe.log under /private/tmp/selahcue-batch20-20261029/17tnw2b2k4x-.
- Decision: handoff

## Risks and rollback

- Risks: a timed-out publish has unknown delivery outcome; no automatic retry is promised. Healthy Redis round trips and DNS remain operational concerns.
- Rollback or recovery: revert this ticket; users may request a fresh link using existing flows. No schema migration.

## Pause and escalation conditions

- Escalate policy, independent review findings or unavailable private test resources to root.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2k4x-broker-timeouts.md
- Validator result: structural validation required after final prose; completion validation remains gated on C-004 exact-head full API and C-005 independent reviews/hosted CI.
- Independent verification result: pending root
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-004 requires exact-head full API verification after the result-subscription correction; C-005 requires all four fresh independent reviews and new full hosted PostgreSQL/Redis and marketing CI. Fresh focused checks are separate from the previous full API snapshot; earlier failed/incomplete runs remain disclosed.
- ClickUp final evidence comment: root owns publication
