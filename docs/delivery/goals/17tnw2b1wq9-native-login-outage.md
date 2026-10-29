# Goal Contract — 17tnw2b1wq9

## Identity

- Goal ID: 17tnw2b1wq9
- Parent goal ID: NONE
- Title: Refuse native bootstrap login when its limiter is unavailable
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b1wq9
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 6
- Independent verification required: yes

## Objective

When the limiter store is unavailable, native session login returns429 before password hashing. Healthy login retains its ten-per-minute budget and account locks; other routes and activated devices retain fail-open availability.

## Baseline

Verified fresh main9a968f978b6d0271de6a5f07c42a42fb96324629 includes actually merged PR258 native observability and prerequisite186. Shared decorator collapses STORE_UNAVAILABLE into permit through should_allow, allowing unbounded native password checks during cache faults. Existing outage warning claims all callers fail open and includes a key/IP.

## Inputs and evidence sources

- Fully qualified live ticket description/activity/dependencies in /private/tmp/selahcue-batch20-20261029/api-queued-payloads.md section17tnw2b1wq9, confirmed by root.
- Existing throttle evaluate_budget/decorator, native views, observability, native surface and cache-timeout tests.

## Scope

### In scope

- Root-selected allowed option: fail closed only for native session_login STORE_UNAVAILABLE, using explicit outcome and existing429/headers.
- Fixed full-window outage retry hint without additional failed-store lookup; retain actual remaining-window hint on a real budget denial.
- Honest secret-free existing outage warning with bounded synchronized once-per-minute state; tests, API operational docs and this record.

### Non-goals

- Browser GraphQL/account service changes, degraded per-identity maps, budgets/account locks, broker/email/settings/circuit breaker/timing padding, device policy or native client UI.

### Constraints

- No raw credentials, identity/key or exception text in new outage reporting; no new identity maps or database state.
- Preserve existing native observability, cookie/content-type guards and default fail-open behavior outside native login.
- Root owns external publication/status/reviews/CI/merge/QA. No shared Redis flush, native UI, Cargo, Flutter or shared build-cache use; other authors own separate worktrees.

### Assumptions and unknowns

- Verified root chooses fail-closed bootstrap login explicitly under ticket AC; cache faults therefore temporarily prevent new native sign-ins. Activated devices stay available. No owner decision pending.

## Dependencies and approvals

- Related86ak5t1gw is QA, prerequisite186 merged, live activity only reporter/creation and no hold. Root confirms PR258 merged9a968f97 with all four reviews and1594-test CI; fresh source integrated before work. User authorizes approved20-ticket delivery with review/remediation/conditional merge.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Twentyfive actual HTTP logins on raising cache cause zero password hashes and429 | New outage tests, actual PBKDF2 counter | Meaningful baseline RED then zero hash/429 and safe headers | /private/tmp/selahcue-batch20-20261029/17tnw2b1wq9-focused.log plus regression.log | PASS |
| C-002 | yes | Healthy/other-route/activated-device behavior and logging preserved | Whole native/outage/observability/throttle/header/guards regression on PostgreSQL | Healthy hash control, device200, browser unchanged; bounded redacted outage log | /private/tmp/selahcue-batch20-20261029/17tnw2b1wq9-regression.log | PASS |
| C-003 | yes | Disabled native outage guard is rejected with sibling controls | Temporary flag-disabled mutation across complete new and native modules, then restore | Outage regression RED; unrelated controls pass; source restored | /private/tmp/selahcue-batch20-20261029/17tnw2b1wq9-mutation.log and mutation-restoration.log | PASS |
| C-004 | yes | Final documentation/static checks and full exact-head hosted CI pass | Doc/system/migration/Goal/diff checks plus root CI | Local static and full hosted API job pass | Root CI and author report | BLOCKED |
| C-005 | yes | All four independent reviews pass after valid fixes | Cody, Quinn, Vera and Shadow | All PASS at frozen final SHA | Root reports | BLOCKED |
| C-006 | yes | Merge and linked ticket QA persisted | Root merge and ClickUp read-back | Reviewed PR merged; exact ticket QA | Root receipts | BLOCKED |

## Verification plan

- Focused verification: real HTTP raising-cache RED, then zero PBKDF2 calls with healthy/hash positive controls and no extra outage TTL query.
- Broader regression verification: complete native/new outage/observability/shared throttle/header/guards modules on private PostgreSQL/local cache; actual Redis header control separately without shared flush; hosted full suite remains required.
- Independent verifier: root dispatches Cody, Quinn, Vera and Shadow.
- Required environment: existing Python runtime; dedicated database batch20_native_outage at127.0.0.1:55453; private LocMem cache. No production access.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 and baseline controls.
- Hypothesis: explicit STORE_UNAVAILABLE distinction before native login can reduce outage password work from25 hashes to zero while preserving other scopes' admission behavior.
- Change or investigation: inspect current merged observability, pure outcome semantics and warning path; tests first.
- Verifier executed: complete new actual HTTP/cache-fault module on PostgreSQL before production edits.
- Result: baseline5 failed,11 passed14.92s. Core25 native requests performed25 real PBKDF2 calls; recovery/bootstrap/device split and neutral warning controls expose the missing policy. Healthy/browser/other-route/pre-guard/service-error controls pass.
- New evidence: existing retry metadata reader must not be used after store failure; existing warning decision text must become neutral for mixed caller policies.
- Decision: iterate.

### Iteration 2

- Target criterion: C-001, C-002.
- Hypothesis: a native-only decorator option preserves pure outcome semantics while refusing unavailable admission before password work; neutral synchronized outage logging is honest for both admission policies.
- Change or investigation: evaluate explicit outcome, enable option only at create_session, use full-window outage hint without another store call. Extract redacted _report_store_unavailable(error_type) with existing global timestamp and one lock; coordinate helper contract with separate circuit-breaker author. Document bootstrap/device tradeoff and qualify existing deployment fail-open wording.
- Verifier executed: complete focused module, then required guard-disabled mutation and restored broad regressions.
- Result: pending execution; final receipts will remain in author report after final tracked prose edits.
- New evidence: no per-IP/email outage map or new auth state; store algorithm and other callers retain their outcome/admission semantics.
- Decision: iterate; do not freeze until guard mutation is killed and restored gates pass.

### Iteration 3

- Target criterion: C-003 guard-disabled regression proof; C-002 fresh integration.
- Hypothesis: disabling only native fail-closed admission must restore unbounded password work, while unrelated native controls remain valid.
- Change or investigation: temporary actual-source True-to-False native decorator flag mutation across both complete new16-case and existing69-case native modules. A finally block restores exact original bytes; no mutation committed. Then integrate merged launcher main6ef0e098 (no API overlap); add an unexpected service-exception control to distinguish it from store unavailability and clarify the timeout comment/doc wrap before final verification.
- Verifier executed: mutation log and restoration receipt /private/tmp/selahcue-batch20-20261029/17tnw2b1wq9-mutation.log and mutation-restoration.log.
- Result: 4 failed,81 passed190.48s. Core outage again performs25 real PBKDF2 calls; recovery/bootstrap-device separation/retry refusal regressions also fail. Exact views.py bytes restored, SHA2561fedb804d51f44d203d6049e881d51bfbe04e2c3b80bfa480355b388d0ab2ca9. Earlier corrected focused16 passed7.08s. Final restored new module now has17 cases; added exception control does not change the guard mutation evidence or implementation.
- New evidence: this is native admission-policy mutation, not a fake hash or fabricated store result; actual HTTP/cache faults and real encoder remain active. Existing69 native controls pass under mutation.
- Decision: restore and run broader proportional API modules on fresh main; hosted full CI remains root-owned.

### Iteration 4

- Target criterion: C-001, C-002 restored integration and C-004 local documentation/static checks.
- Hypothesis: restored guard plus unchanged store algorithm preserves all non-login callers and current merged native visibility.
- Change or investigation: finalize this evidence prose before final checks; no production/test/operator-doc changes after the broad restored run.
- Verifier executed: entire new17-case outage/native account/native observability/shared throttle/guards/header/cache timeout/deployment-doc modules on PostgreSQL/private local cache. Final gate is new17 plus entire53 docs guards and existing unique-key Redis header control, followed by system/migration/Goal/diff checks.
- Result: restored broad303 passed,2 skipped195.39s. Both skips are existing real-Redis controls because CACHE_URL was intentionally empty; one header case is executed separately in final gate with a randomized key/no shared flush. The existing healthy-Redis timeout control remains assigned to final hosted CI. This is not a full local API suite or skip-free broad claim. Final receipts belong in the author report, avoiding tracked edits after verification.
- New evidence: zero hashes/429 under outage, healthy10 hashes, recovery, actual activated-device refresh200, other scopes fail open, browser unchanged, normal SafeAPIError and unexpected service exception preserved, synchronized redacted warning at60s and concurrent faults. Only native admission flag changes policy; no per-identity fallback or breaker added.
- Decision: freeze only after final gate/static checks pass; root owns hosted full CI, all four independent reviews, merge and QA.

## Risks and rollback

- Risks: cache outage blocks native bootstrap login until recovery; full-window retry hint is conservative, not evidence of recovery. Activated devices and other scopes retain existing fail-open semantics. Global warning now describes unavailable budget evaluation without incorrectly promising every caller admission.
- Rollback or recovery: restore cache service; reverting this ticket reopens unbounded native password work during outage. No schema/data migration or per-identity recovery required.

## Pause and escalation conditions

- Stop for unapproved account/budget policy or unrelated conflict. Coordinate final fresh-main integration and any explicitly reserved benchmark window with root.

## Final evaluation

- Validator command: python /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wq9-native-login-outage.md
- Validator result: structural validation required after final evidence edit; completion remains intentionally blocked by C-004, C-005 and C-006.
- Independent verification result: pending root dispatch.
- Terminal state: BLOCKED pending reviews, CI and delivery.
- Remaining failed or blocked criteria: C-004, C-005, C-006.
- ClickUp final evidence comment: root owns external evidence updates.
