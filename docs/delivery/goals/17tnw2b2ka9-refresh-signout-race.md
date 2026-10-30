# Goal Contract — TASK-17tnw2b2ka9

## Identity

- Goal ID: TASK-17tnw2b2ka9
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Sign-out revokes the rotated session when refresh is already in flight
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2ka9
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Sign-out waits for any in-flight session rotation, revokes the resulting cookie-backed session and leaves no resurrected hint or live browser session.

## Baseline

Verified at fetched main6a1f414cc3213006b333a071893db394ffd03039: sessionStore.signOut sends logout immediately; the router starts opportunistic refresh without awaiting it; refreshIfExpiringSoon unconditionally remembers captured metadata after its request. API refresh revokes the presented session and creates its replacement before the resolver sets the new HttpOnly cookie. Logout carrying the old token fails authentication before delete_cookie, so an early UNAUTHENTICATED cannot prove the later refresh cookie is revoked.

## Inputs and evidence sources

- Complete saved task/comments: wave2-20261029/frontend-qualification/17tnw2b2ka9-live.json; no comments or owner decisions outstanding.
- Implemented prerequisite PR268 shared sign-out on current main.
- sessionStore.ts, router/index.ts, API account_schema.py refresh/logout, services.py refresh_session/logout_session, existing customer auth rotation tests.

## Scope

### In scope

- Bounded shared refresh/logout orchestration and stale hint suppression in the marketing session store.
- Router integration only as necessary; preserve unguarded route paint and opportunistic refresh behavior.
- Real session-store/GraphQL-seam scripted-fetch tests, browser race and regression controls.

### Non-goals

- Server authentication policy, token families, cross-tab synchronization, native clients, unrelated sign-in races or cookie-reading workarounds.
- Notes ticket dq6 and previously frozen shared sign-out implementation.

### Constraints

- New managed worktree and one-ticket branch. Root owns ClickUp, publication, hosted RED/GREEN, reviews, merge and QA.
- No local project runtime, builds or browser runs while host is paging. Actual hosted assertion RED must precede production edits.
- Do not claim revocation from a hint-only assertion. Model or verify the request cookie and server session after rotation.
- Preserve truthful retryable logout failure and no-refresh UNAUTHENTICATED handling; no unbounded queues or timers.

### Assumptions and unknowns

- VERIFIED: same-origin fetch carries the browser's cookie; refresh resolver installs the rotated cookie before its response is consumed.
- UNKNOWN: final hosted/runtime/review outcomes until executed. Scripted cookie tests model the inspected server contract; they are not a real browser HttpOnly-cookie integration claim.

## Dependencies and approvals

- Root selected this ticket after shared sign-out PR268 merged and authorized auth/session/test ownership.
- Root coordinates latest-main integration and all external actions; no backend policy decision has been inferred from the same-SPA request-ordering defect.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Sign-out waits for in-flight refresh, sends logout with rotated cookie and ends with no live session or hint | `node --test tests/refreshSignOut.test.ts` | Held-refresh cookie/session assertions pass after observed baseline RED | Hosted focused log | PENDING |
| C-002 | yes | No stale hint rewrite or new refresh admission during sign-out; duplicate refresh is bounded/shared | Focused scripted-fetch concurrency tests | No late hint resurrection, duplicate rotation or refresh during held logout | Hosted focused log | PENDING |
| C-003 | yes | Failed refresh/logout and no-refresh UNAUTHENTICATED preserve honest recovery | Focused controls plus existing sign-out tests | Failure remains retryable/signed-in until revoked; already-ended session is handled without false race success | Hosted control logs | PENDING |
| C-004 | yes | Real UI race and marketing regressions pass | `make marketing-check` and required `npm run test:states` | Type/lint/node/build and browser gates exit zero on frozen source | Hosted CI and browser log | PENDING |
| C-005 | yes | All independent reviews approve current source | Cody, Quinn, Vera and Shadow | No unresolved blocking findings after remediation/re-review | Root consolidated review | PENDING |

## Verification plan

- Focused verification: Node tests import the actual session store/API seam and use a per-test browser-cookie/server-session transport model derived from current API behavior.
- Broader regression verification: normal marketing CI and required real-UI scripted-fetch auth-state scenarios, retaining shared sign-out and threshold controls.
- Independent verifier: root coordinates Cody, Quinn, Vera and Shadow.
- Required environment: clean hosted Node matching lockfile and required Chrome/browser gates; no local project runtime. API source/tests ground cookie semantics, but no new API behavior is presumed.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: while refresh has revoked the old session but held back its response cookie, immediate logout uses the old token and reports already signed out; releasing refresh then leaves a live replacement cookie and resurrected hint.
- Change or investigation: inspect actual server transaction/cookie order and prepare meaningful tests-only RED with authenticated-cookie, hint, ordering and failure/concurrency controls against unchanged production.
- Verifier executed: isolated hosted diagnostic41031973619, source478cd79e, diagnosticb89d1f66; actual `node --test tests/refreshSignOut.test.ts` after clean npm ci.
- Result: Actual assertion RED: seven failures and two passing controls. Primary assertion expected no live rotated cookie but actual true; logout dispatched early, duplicate refresh, new refresh admission and late hint rewrite also failed. Long-session threshold and no-refresh UNAUTHENTICATED controls passed. Production was unchanged before this evidence.
- New evidence: auth-refresh-race/red-receipt.json and auth-refresh-race/node-red.log; https://github.com/First-Pavilion/selahcue/actions/runs/41031973619.
- Decision: iterate

### Iteration 2

- Target criterion: C-004.
- Hypothesis: real Account interactions while the router's refresh response is held reproduce the same request-cookie ordering and hint failures, including honest retry after a failed logout.
- Change or investigation: add two scripted server/cookie scenarios to the existing real-browser auth harness, keeping production unchanged for the browser RED checkpoint. They exercise router refresh, real shared sign-out controls, rotated-cookie logout, failed logout/retry and protected-route confirmation. The model limits remain explicit; no cookie value is read by application code.
- Verifier executed: Goal structural, stdlib Python AST and full baseline diff check; hosted browser RED prepared.
- Result: Static checks PASS; browser behavior/count pending hosted execution. Exact count remains unchanged until measured.
- New evidence: scripts/auth_pages_headless.py test-only additions and isolated browser diagnostic receipt.
- Decision: handoff

### Iteration 3

- Target criterion: C-001 through C-003.
- Hypothesis: a single tracked refresh, synchronous logout admission barrier and post-await hint identity check serialize the real cookie rotation/revocation while preserving retryable failures.
- Change or investigation: after observed Node RED, track one refresh promise and a fixed-size logout counter; close new refresh admission before awaiting the existing request, then call logout with the installed cookie. Suppress metadata writes once logout began or the hint changed. Failed refresh still drains before logout, and failed logout retains truthful signed-in state. Router refresh stays opportunistic; no API policy or cookie access change.
- Verifier executed: Goal structural, full baseline diff check and script stdlib AST locally; isolated hosted focused GREEN prepared. Browser RED executes separately against unchanged production sourceb12f230c.
- Result: Static checks PASS; current implementation runtime GREEN and exact browser count remain pending hosted evidence. Existing HTTP deadlines bound both operations; no queue or timer was added.
- New evidence: sessionStore orchestration diff and diagnostic receipts under auth-refresh-race/.
- Decision: handoff
## Risks and rollback

- Risks: ignoring only late JS state leaves a valid cookie; waiting without closing refresh admission can race a second rotation; clearing hints on failed logout falsely claims success.
- Rollback or recovery: revert this one PR; no migration or server/session schema change.

## Pause and escalation conditions

- Pause production changes until actual hosted assertion RED is observed.
- Escalate any genuine server coordination or policy requirement rather than widening this same-SPA slice silently.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2ka9-refresh-signout-race.md
- Validator result: PASS structural validation on 2026-10-30; full baseline diff check passed, no local project runtime executed.
- Independent verification result: Pending root-owned review pipeline.
- Terminal state: BLOCKED on root-owned actual hosted assertion RED before implementation; tests-only checkpoint prepared.
- Remaining failed or blocked criteria: C-001 through C-005 pending.
- ClickUp final evidence comment: Root owns publication and persisted QA status after passing merge gates.
