# Goal Contract — TASK-17tnw2b1wf2

## Identity
- Goal ID: TASK-17tnw2b1wf2
- Parent goal ID: NONE
- Title: Native account bootstrap sessions can be revoked without cookies or device disruption
- Role: mobile-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1wf2
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective
Add the approved bearer-only native revoke route and connect native activation cleanup so the bootstrap account session is ended while device credentials and presentation remain intact on success or cleanup failure.

## Baseline
Verified main d5476edde13649e8b1c4fbfc92647d07e2f9e3eb: logout_session already revokes one account session without touching devices, but only the browser GraphQL surface exposes it. LicensingClient signs in and activates through native routes but has no revoke operation. DeviceCredentials stores the account session separately and local sign_out preserves the device token. Source trace finds no operator licensing dependency or pending-session activation flow on this main; its hosted-provider account_token is a different secret entry. The coordinator subsequently confirmed the existing LicensingClient library as the accepted caller boundary, with no new operator UI or hosted-provider token wiring.

## Inputs and evidence sources
- Full coordinator-qualified native ClickUp task/AC/activity and final re-read in /private/tmp/selahcue-batch20-20261029/api-queued-payloads.md.
- ADR-0029 remains Proposed pending the owner's wire/residual-risk decision; DEC-007 session model remains unchanged.
- Existing API native guards, account logout service, audit/route contracts and actual Rust client/custody/transport code.
- Mobile/backend/goal skills and runtime; no repository/nested AGENTS.md found, personal .codex/AGENTS.md is empty.

## Scope
### In scope
- POST bearer-only JSON native session revoke, existing single-session service/auth/audit, independent per-IP budget and explicit route/exemption inventory updates.
- Rust client wire contract, post-activation cleanup and appropriate existing custody lifecycle integration; fail-safe activated device behavior.
- Meaningful test-first security, lifecycle, regression and mutation evidence; accurate docs and residual retry limits.
### Non-goals
- No activation-only grant, TTL/session model change, broad logout, new access duration, device revocation or presentation gate.
- No unrelated email/circuit-breaker/broker implementation, UI automation or secret credentials.
### Constraints
- User approved route-only option; coordinator owns ClickUp, all four reviews, source publication, hosted CI, merge and QA.
- Work only isolated ticket branch/worktree; do not revert other authors. Serialize native builds in reserved cache; use local fixtures and dedicated PostgreSQL/LocMem, never shared Redis flush.
- No unsafe production access or external provider calls; use existing transport/secret-store seams.
### Assumptions and unknowns
- Physical-device/Flutter/permissions/signing checks are not applicable: pure backend/native credential lifecycle, no mobile UI or device API changes.
- Verified operator licensing integration is absent on current main. Coordinator explicitly accepts the actual LicensingClient activation method plus a narrow existing-secret-store wrapper; no operator/physical-booth E2E claim is permitted.

## Dependencies and approvals
- Current task first-option route+desktop cleanup approved; grant-only product-owner decision is not selected.
- Parent coordinator supplies authoritative live task snapshot and handles external tracker updates/reviews.
- Native caches previously released and available; Cody book review uses its own separate cache.

## Completion predicate
All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Cookieless native bearer revokes only presented session and token is refused afterward | API real-service/socket regression | revoked true; subsequent auth401; other sessions/device remain valid | ticket API logs | PASS |
| C-002 | yes | Native route preserves JSON, no ambient credential/cookie, CSRF/browser separation and per-IP budget | CSRF-enabled API security and mutation tests | invalid requests refused, simple bodies spend no budget, pinned route set deliberate | ticket API/mutation logs | PASS |
| C-003 | yes | Rust wire and actual activation cleanup use native revoke operation | Client wire and activation caller tests | bearer-only JSON and cleanup after activation/abandon as scoped | ticket Rust logs | PASS |
| C-004 | yes | Cleanup failure leaves activated device credentials/output intact and retry limits explicit | Native custody/caller/never-blank failure regressions | no device erase/revoke/presentation gate | ticket lifecycle logs/docs | PASS |
| C-005 | yes | Focused and affected regression suites, lint, docs and target integration pass | API PostgreSQL/LocMem; Rust suites; format/clippy; system/migration/docs/goal/diff checks | all required local checks pass with limits stated | final report | PASS |
| C-006 | yes | All four independent reviews pass exact frozen source | Cody, Quinn, Shadow, Vera | all pass after remediation | coordinator reports | BLOCKED |
| C-007 | yes | Hosted exact-head CI, merge and linked QA readback pass | coordinator delivery | verified CI/merge/QA | coordinator evidence | BLOCKED |

## Verification plan
- Focused verification: test-first real-service revoke, security refusals/budget, Rust cleanup/custody/wire and failure controls.
- Broader regression verification: complete changed native crates and affected API/auth/throttle/contracts/CSRF/device tests, current-main integration and static/documentation gates.
- Independent verifier: coordinator's four distinct reviewers.
- Required environment: dedicated PostgreSQL test database with private LocMem cache, local loopback transport fixtures and injected test secret store; serialized Rust caches.

## Iteration ledger
### Iteration 1
- Target criterion: C-001/C-002/C-003/C-004.
- Hypothesis: existing single-session logout service can expose a bearer-only native route and the existing client activation lifecycle can end its bootstrap session without changing device credentials or access policy.
- Change or investigation: trace services/native guards and all production Rust callers; source finding about absent operator licensing flow sent to coordinator.
- Verifier executed: structural goal validation, then test-first regressions.
- Result: pending.
- New evidence: account_session_token custody exists only as library API; operator account_token is separate hosted-provider secret.
- Decision: iterate.

### Iteration 2
- Target criterion: C-001 through C-004.
- Hypothesis: the existing native guards and single-session service can support route-only cleanup, and adding one real client request plus separate outcome/custody fields preserves activation success across remote/local cleanup failures.
- Change or investigation: coordinator resolved caller scope to LicensingClient's actual activate_with_session; no operator dependency/commands/UI or hosted-provider token change. API test-first RED404, client test-first RED one request instead of two. Add native bearer-only sessions:revoke, empty JSON object, independent10/minute/IP budget, native audit provenance and deliberate CSRF/route inventories. Reuse logout_session; only optional audit-source keyword changes browser service default unchanged. Actual successful activation attempts revoke once and carries Revoked or RetryRequired separately. A narrow activate_and_persist_with_session wrapper persists device credentials and clears only matching account custody after confirmed cleanup, with separate persistence/removal results. Failed/ambiguous activation retains session for same-idempotency retry.
- Verifier executed: initial PostgreSQL route/socket suite; complete licensing crate; affected API regressions; actual ReqwestTransport loopback activation/cleanup plus injected secret-store failure tests; meaningful cleanup/guard mutations then restored checks.
- Result: initial API17 PASS. Initial complete licensing PASS after deliberate request-sequence fixture updates; actual transport/client suite67 PASS before later timeout/device-persistence/explicit-retry additions. First API broader run459 PASS/1 Redis skip with1 test-fixture failure: denial reporter's process-wide suppression persisted from a previous case, yielding0 new scope warnings; isolate its existing reset seam per test, do not change production reporting. One test initially used a non-exported ReqwestTransport path; corrected to the actual transport module. Final restored broader results pending.
- New evidence:17tnw2b1wf2-api-red.log, client-red.log, api-green.log, licensing.log, client-wire.log and mutation/final receipts in /private/tmp/selahcue-batch20-20261029/. No live credentials, external provider requests or shared Redis flush. Real HTTP loopback tests include Set-Cookie from a server but prove subsequent client cleanup sends no ambient cookie/CSRF/Origin/Referer.
- Decision: iterate through restored final regression/lint/docs/system/integration gates, then coordinator reviews and hosted CI.

### Iteration 3
- Target criterion: C-001 through C-005.
- Hypothesis: restored production source passes the affected native/API suites and the deletion mutations prove cleanup and browser-simple request refusal are behaviorally protected.
- Change or investigation: mutations remove actual cleanup and JSON content-type guard, restore both files in finally. Guard mutation3 expected failures plus1 valid bearer sibling pass; cleanup removal expected request-count failure. Correct separate wire helper's credential-body-only assumption by taking an explicit expected body for the new empty-object route. New classification RED showed coded cleanup NOT_FOUND wrongly mapped to device license lapse; preserve it as an unknown coded cleanup refusal instead. No session lifetime/access/grant model, device revocation or presentation-path change.
- Verifier executed: restored PostgreSQL affected native/browser auth, throttle, route contracts and TLS modules; complete licensing+cloud HTTP debug suites; complete licensing release suite; strict all-target clippy/format; import guards; system/migration/docs checks.
- Result: PostgreSQL460 passed1 existing Redis-only metadata skip in81.26s. Native debug221 passed1 existing external-network manual probe ignored across27 targets; licensing release150 passed0 ignored across9 targets. Client71 cases include actual method+production ReqwestTransport loopback wire/cookie isolation, positive ack, unknown/malformed response, remote failure/timeout, local session removal/device persistence failure, changed custody, replay and explicit retry. Format/clippy and presentation dependency/import guards PASS. System check clean, no pending migrations; deployment-doc116 PASS. No full make ci, full API suite, hosted CI or operator/physical-device E2E claim.
- New evidence:17tnw2b1wf2-native-final.log/.json/.exit; api-restored-regressions.log/.exit; api-static.log/.json/.exit; named mutation logs under the coordinator evidence directory. Test-only existing-cloud HTTP feature enabled as dev-dependency for real transport coverage; no new package or Cargo.lock change.
- Decision: final new-route/docs plus explicit randomized-key real-Redis control, structural/diff/target checks follow this tracked evidence-only update before commit. Final receipts/frozen SHA in17tnw2b1wf2-report.md. C-006/C-007 remain coordinator-owned.

### Iteration 4
- Target criterion: C-003/C-004/C-005 final lifecycle order and freeze.
- Hypothesis: persisting a show-once device token before waiting on remote cleanup reduces the recovery window without changing the required immediate cleanup or public activation success contract.
- Change or investigation: a targeted actual-wrapper transport assertion first failed because device custody was empty at the cleanup call. Share the existing request and cleanup steps between the public activate_with_session method and custody wrapper; the wrapper now persists device credentials before the cleanup request. The original activation method still actually attempts cleanup and both paths carry the same honest outcome. No new host/UI or grant behavior.
- Verifier executed: restored complete affected native debug/release suites, strict clippy/format and import guards after that change. Final API route/docs/explicit Redis metadata control after prior evidence update.
- Result: native debug222 passed1 existing manual public-network probe ignored across27 targets; licensing release151 passed0 ignored across9 targets. Client72 cases include the new persistence-order regression. Strict clippy/format and import guards PASS. Final API135 passed0 skipped in9.08s:18 new-route cases,116 docs and the one existing Redis metadata control previously skipped by the broader460-pass run. That Redis backend uses only a randomized prefixed key, deletes only that key and closes its client; new route fixtures use private LocMem. No shared cache flush. Repeated coverage is not additive distinct coverage. Final docs/new-route/static checks repeat after this evidence update before committing; receipts and frozen SHA belong in the author report.
- New evidence:17tnw2b1wf2-persist-order-red.log and latest native-final.log/.json/.exit; previous native-before-persistence-order receipts preserved separately. Existing API broad receipt remains its original source/environment scope; API production behavior did not change during native ordering fix. Current main ancestry/behind0 and clean snapshot verified at freeze.
- Decision: freeze author source and release native cache reservations when own final processes exit; coordinator owns C-006/C-007.

## Risks and rollback
- Risks: accidentally reading ambient cookies, clearing a device token, dropping an unrevoked account token or coupling cleanup failure to activation failure.
- Rollback or recovery: revert isolated ticket branch; no migration or session-token model change.

## Pause and escalation conditions
- Stop for a new product/session model decision, unsafe cleanup behavior, unjudgeable integration conflict, or three materially different failed attempts without new evidence. Continue independent authorized work while awaiting caller clarification.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wf2-native-session-revoke.md
- Validator result: structural PASS; final receipt after this evidence update is in the author report
- Independent verification result: coordinator pending
- Terminal state: BLOCKED pending coordinator independent reviews and delivery
- Remaining failed or blocked criteria: C-006 and C-007
- ClickUp final evidence comment: coordinator-owned
