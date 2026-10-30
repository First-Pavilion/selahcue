# Goal Contract — 17tnw2b1f1w

## Identity

- Goal ID: TASK-17tnw2b1f1w
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Release connections and late WebSockets after establishment timeout
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1f1w
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

An expired connection attempt cannot retain its HTTP client or an eventually acquired WebSocket, and cannot return a session. Timely success and existing pair/connect error semantics remain intact, including the merged queue cleanup.

## Baseline

Fresh main b80261fb1f8e9dacdb20ec8397498479dad3955a contains the approved queue cleanup but _establish still only applies Future.timeout to WebSocket.connect. It neither force-closes its HttpClient on timeout nor consumes/closes a late successful WebSocket. Current main dcdb4f64433a5631465de7ad62ff2e1235349c05 was fetched and integrated before tests; its marketing-only delta leaves mobile unchanged.

Full saved task/comments at wave2-20261029/mobile-qualification/17tnw2b1f1w.json were read: comments empty, no declared blocking dependency. Reporter measurements are task evidence, not local benchmark results.

## Inputs and evidence sources

- Existing ticket criteria: delayed loopback upgrade leaves zero sockets, 100 consecutive timeouts return owned socket count to baseline, tests fail without cleanup.
- session.dart establishment, pair/connect callers and merged StreamQueue disposal.
- Real pinned-TLS LoopbackHost and current SDK Future.timeout/WebSocket.connect source inspected read-only for scheduling seams.
- Root's authority for this branch push, draft PR/body, attachment and hosted RED/GREEN; root owns reviews/merge/QA.

## Scope

### In scope

- Timeout/error ownership of the HTTP client and late successful connection future.
- Real pinned-TLS delayed upgrade, acquired-socket late completion and 100-cycle owned-resource regressions.
- Positive timely auth/pair and timely/late error controls; production ten-second default remains unchanged.

### Non-goals

- Overall pairing deadline, active frame/buffer caps, retry/backoff policy, role/credential policy, queue redesign or wire changes.
- UI, signing, platform configuration, local builds or device/OS-wide file-descriptor acceptance claims.

### Constraints

- Test-first hosted behavioral RED on unchanged production before minimal fix; compiler/setup failures do not qualify.
- No local Flutter/pub/Node/build/project runtime, simulator, container or benchmark under resource restrictions.
- Keep actual TLS, WebSocket, HTTP client and caller code real; control only external upgrade/deadline/completion delivery in test utilities.
- No force push, protected edits, merge, ClickUp mutation, review publishing, extra agents or next ticket.
- Preserve others' changes and previous delivered branches; only this isolated branch and scoped session connection/test/goal files.

### Assumptions and unknowns

- One real ten-second connection deadline and a gated late server upgrade establish the actual default path; 100 further controlled-deadline cycles avoid a thousand-second test while retaining real sockets.
- A zone-delayed delivery of an already acquired real WebSocket distinguishes fallback close from HTTP cancellation. A fully forwarding socket observer counts explicit closes while host/client state checks prove actual closure.
- Counts apply to sockets owned by the loopback fixture/connection attempts, not unrelated process descriptors or a statistical performance claim.
- Hosted setup, behavioral RED, corrected full GREEN and independent reviews remain pending.

## Dependencies and approvals

- Actual main contains the reviewed queue/session cleanup; retain it unchanged.
- No task owner decision or declared blocking dependency exists in captured full task/comments.
- Mika owns ordinary branch publication, draft metadata/attachment and hosted CI. Root exclusively owns all four independent reviews, remediation routing, merge and exact linked QA handoff.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Upgrade completing after the actual connection deadline retains no socket/session | Real pinned-TLS server gates upgrade until public connect times out | SessionException timeout; zero owned client/server sockets within bounded completion after release | Hosted real-deadline regression | PENDING |
| C-002 | yes | Already acquired late WebSocket closes exactly once | Real acquired WebSocket completion held past controlled deadline for auth/pair callers | No session/hello; one explicit close; actual client/server closed state | Hosted completion-race tests and timely release control | PENDING |
| C-003 | yes | 100 consecutive late-upgrade timeouts return owned sockets to baseline | Real loopback upgrades with controlled production timeout callbacks and observed resource counts before fixture teardown | Every cycle zero open owned client/server sockets; aggregate count equals initial baseline | Hosted 100-cycle resource receipt | PENDING |
| C-004 | yes | Timely success and connection error semantics stay correct | Timely auth/pair, pre-deadline held completion, wrong-pin and late-error controls plus existing session tests | Successful session usable until caller closes; existing typed errors; no uncaught late failure | Hosted controls/full suite | PENDING |
| C-005 | yes | Regressions detect the missing cleanup before implementation | Frozen tests-only source, draft PR and actual hosted execution | Behavioral retained socket/missing close failures; positive controls pass | Exact-source RED log/run | PENDING |
| C-006 | yes | Corrected full mobile gates pass | Hosted flutter analyze and full flutter test on exact candidate | Analysis exits 0 and applicable full suite passes | Exact-source GREEN log/run | PENDING |
| C-007 | yes | Independent reviews and authorized delivery close | Cody, Quinn, Vera, Shadow and root delivery receipts | Four current-source passes, merge verified, exact linked QA status persisted/reread | Root review/merge/QA evidence | PENDING |

## Verification plan

- Focused selector: flutter test test/models/session_connect_timeout_cleanup_test.dart from implementation/mobile/selahcue_controller.
- Existing hosted PR workflow runs pub get, analysis and full Flutter tests. Inspect actual behavior and positive controls before production edits.
- Preserve raw RED/GREEN logs/run IDs and source/tree hashes. Mark path-gated/native/device/OS-wide descriptor checks explicitly unexecuted.
- Root coordinates independent review; no self-approval or merge.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-005
- Hypothesis: Future.timeout abandons an uncancelled connection future, so owned HTTP resources and late WebSockets persist unless ownership is explicitly discharged.
- Change or investigation: inspect full task/current main/SDK source, extend real loopback fixture with bounded upgrade gates, and add unchanged-production regression/controls.
- Verifier executed: structural Goal validation and full baseline diff check; actual hosted setup/RED pending publication.
- Result: pending hosted execution
- New evidence: public connect/pair paths share establishment; test-only scheduling can expose both pending-upgrade and already-acquired completion ownership without production API additions.
- Decision: freeze tests only, publish draft PR, inspect actual behavioral RED, then implement minimal cleanup.

## Risks and rollback

- Risks: cleanup must not close a timely returned session, publish an expired session, double-close a late socket or expose unhandled late errors. Force-closing HTTP alone cannot discharge a WebSocket already detached from that client.
- Rollback or recovery: revert only this ticket; no schema, wire, storage or platform change.

## Pause and escalation conditions

- Wait for actual behavioral RED before production edits; repair invalid harness/setup results first.
- Yield long CI waits with exact PR/head/run/job IDs and saved receipts; resume on supplied results.
- Hand back a clean immutable corrected candidate after hosted gates; root owns reviews/merge/QA. Do not start another ticket.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1f1w-late-websocket-cleanup.md
- Validator result: structural validation passed (exit 0); behavior awaits hosted tests-only execution
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-007
- ClickUp final evidence comment: root owns publication
