# Goal Contract — TASK-17tnw2b9dra

## Identity

- Goal ID: TASK-17tnw2b9dra
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Return safe validation responses for raw GraphQL JSON decode failures
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9dra
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every actual GraphQL JSON endpoint cleanly rejects decoder recursion and oversized/malformed raw bodies with HTTP400/VALIDATION_FAILED, preserving existing body limits, ordinary authentication, CSRF, GET and operation-validation contracts.

## Baseline

Fresh actual main dcdb4f64433a5631465de7ad62ff2e1235349c05 contains SafeGraphQLView dispatch mapping HTTPException only. Strawberry parse_json catches JSONDecodeError but native json.loads RecursionError escapes. Cross-web decodes request.body as UTF8 before that parser. Both admin/account use this shared view; csrf bootstrap is a distinct GET endpoint.

## Inputs and evidence sources

- Full saved task/comments/deps: wave2-20261029/api-qualification/17tnw2b9dra.json;0comments,0dependencies. Task requests real unauthenticated raw-depth reproduction, safe400/VALIDATION_FAILED and size/depth protection on all GraphQL endpoints.
- Current URLs/shared GraphQL view, safe payload contracts, existing foundation auth/CSRF/GET tests and native platform decode-error pattern.
- Pinned package source: Django6.1.2 HttpRequest.body enforces DATA_UPLOAD_MAX_MEMORY_SIZE for JSON through Content-Length/seekable-stream checks; Strawberry BaseView.parse_json/decode_json and SyncBaseHTTPView.parse_http_body establish the narrow exception boundary. The task's older statement that the cap applies only to form data is not true for this pinned implementation.

## Scope

### In scope

- Reuse existing Django body-size admission rather than changing its configured maximum or adding a knob.
- Map native decoder recursion only at decode_json; map body-size/UTF8 decode exceptions only within HTTP body parsing, before resolver execution.
- Real route tests for200000-level raw bodies below the configured cap on both surfaces, size boundary, malformed JSON/UTF8, ordinary authenticated/unauthenticated behavior and preserved CSRF/GET contracts.
- Necessary CI prerequisite: measured full API runs exhaust the15-minute job cap after all tests pass; raise only API job cap to bounded20minutes and retain every assertion/job/service/pin/OS scope. Workflow edits intentionally trigger all areas.

### Non-goals

- New GraphQL AST-depth or complexity policy, custom JSON parser/pre-scan, new error code, broad resolver RecursionError masking, held PR233, unrelated scalar-envelope defects or changing body limits/disabled-limit policy.

### Constraints

- No local project runtime/tests/install/DB/containers/benchmark under paging. Only static stdlib checks locally; actual hosted RED before source fix.
- Author may ordinary-push/draftPR/body-file/immediately attach and run bounded own workflow-only diagnostics. No force push/protected edits/merge/ClickUp/UI/status/review publication/subagents.
- Preserve all other agents' work, AH8 source remains frozen. Integrate latest main before initialPR and inspect overlaps, including AH8 if it merges.

### Assumptions and unknowns

- Existing Django byte cap and native decoder recursion limit provide the requested bounded input behavior; no numeric AST-depth policy is invented.
- Real routes are admin/account; csrf bootstrap GET is preserved rather than treated as a GraphQL JSON decoder.
- Actual runtime response failures must be confirmed in hosted RED; setup exceptions do not count as a reproduction.

## Dependencies and approvals

- User authorizes implementation, hosted CI, valid remediation and review-passed merge/QA. Parent expands author to ordinary push/draftPR/attach and bounded hosted diagnostics; root owns four reviews, merge and QA.
- No dependency on held233 mutations or pending AH8 policy; main integration must retain any independently merged work.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Actual unauthenticated200000-level raw JSON below body cap is safely refused on both surfaces | real Django route tests, raw array/object bodies | meaningful RED then400safeVALIDATION_FAILED with no details | wave2-20261029/api-deep-json/red.log and GREEN evidence | PENDING |
| C-002 | yes | Existing body-size boundary preserved and oversize/UTF8/malformed decoding mapped safely | under/at/overcap and malformed tests | valid boundary retains200auth outcome; invalid inputs400safeJSON | hosted test logs | PENDING |
| C-003 | yes | Normal auth, CSRF, GET and GraphQL validation behavior preserved; resolver faults not broadly swallowed | positive browser/bridge/GET/query tests and narrow source inspection | expected200/403/GET400-or-405 contracts unchanged | focused/full hosted logs and review | PENDING |
| C-004 | yes | Current-main-integrated candidate passes full API checks/migrations/regressions and every other workflow-triggered gate with existing skips retained | normal hosted all-area CI after workflow edit | actual workflow success, raw logs inspected; cancelled does not pass | PR/run snapshot and raw logs | PENDING |
| C-005 | yes | Frozen source passes Cody,Quinn,Vera,Shadow and valid findings are remediated/reviewed | root independent review round | no unresolved findings | root review evidence | PENDING |
| C-006 | yes | PR merged and exact ticket QA persisted | root delivery readback | merge/QA verified | root delivery evidence | PENDING |

## Verification plan

- Focused: test_graphql_raw_json.py through real Django URL/middleware/view without auth credentials; seed CSRF only where reaching decoding is intended.
- Broader: normal hosted PostgreSQL16/Redis7/Python3.14 API job, checks/migrations/all tests, existing foundation/auth/CSRF and previous config guards. The CI timeout prerequisite edits ci.yml, triggering all existing code areas and their required Linux gates; no API-only claim.
- Independent verifier: Cody,Quinn,Vera,Shadow through root.
- Required environment: hosted services; no local project runtime or large-body construction/execution.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: real route tests expose native JSON recursion/body-cap/UTF8 exception contract gaps while existing positive contracts already pass.
- Change or investigation: full requirements/source/dependency decode boundaries inspected, worktrees checked, new isolated current-main branch, tests first.
- Verifier executed: static syntax,diff and structural goal validation only.
- Result: actual hosted RED41037528327/source d41d798b/diagnostic37e0ad17 produced10failed16passed in1.70s:8intended product failures (4raw-recursion500,2body-cap400HTML,2UTF8decode500) plus2GET test-oracle failures. No setup failures. The existing foundation contract accepts GET400or405; actual baseline returns400, so the test oracle is corrected without changing GET production behavior.
- New evidence: wave2-20261029/api-deep-json/red.log and https://github.com/First-Pavilion/selahcue/actions/runs/41037528327
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-004.
- Hypothesis: map native JSON recursion only in decode_json and body-size/UTF8 input errors only in parse_http_body; existing dispatch supplies the safe400envelope.
- Change or investigation: add two narrow overrides, preserving configured body cap, parser, authentication/CSRF/GET/operation handling and resolver error behavior. Correct only the GET positive assertion to existing400/405 contract; negative tests stay unchanged. Integrate actual AH8 main before initial PR and inspect overlap.
- Verifier executed: static source/test syntax, negative-test preservation, diff and structural goal checks; no local runtime.
- Result: minimal candidate prepared for draft PR/full hosted API; actual GREEN and all independent reviews remain pending.
- New evidence: wave2-20261029/api-deep-json/candidate-manifest.json and CI raw log at handoff.
- Decision: gate-review

### Iteration 3

- Target criterion: C-004, necessary CI prerequisite approved by parent.
- Hypothesis: the unchanged full suite needs bounded job headroom for service/install/check/post-job overhead;15minutes expires at the completed test summary, so rerunning unchanged cannot establish a successful required gate.
- Change or investigation: independently inspected both raw logs/step timestamps and workflow/minute contracts. Run41038300286 exact85385b9d attempt1 ran2147pass/1intentional study skip in854.46s (14:14), API job10:06:49–10:21:52; attempt2 repeated2147pass/1skip in857.22s (14:17), API job10:28:16–10:43:20, with42seconds before tests and cancellation immediately after100percent. Attempt1 Tests step succeeded but job cancelled; attempt2 Tests cancelled. Both workflow conclusions remain CANCELLED, never GREEN.
- Verifier executed: raw receipts and step timestamps; minute rules and workflow/API gate source read; actionlint, exact semantic-diff/static checks, goal validation. Fresh target integration and normal all-area hosted CI follow.
- Result: only API job cap15→20minutes with measured comment; no test bounds, checks, jobs, OS/tier scope, services, dependency pins, security or skip changes. This is hosted job overhead headroom, not a local resource override or production performance waiver. Allfour reviewers must re-review this semantic CI change; fresh actual workflow success remains mandatory.
- New evidence: wave2-20261029/pr288-cancelled-ci.log, pr288-attempt1-cancelled-ci.json, pr288-attempt2-cancelled-ci.log/json; updated candidate manifest/handoff and fresh run receipts.
- Decision: gate-review

## Risks and rollback

- Risks: API job maximum increases by5minutes while actual billed time remains actual runtime; all code areas rerun because ci.yml changed. Catching recursion outside the decoder would hide resolver bugs; fixed safe errors must not echo raw request content. Tests assert the exact safe envelope and source scope remains narrow.
- Rollback or recovery: revert this isolated input-boundary change; no schema,migration,data rewrite or operator configuration is changed.

## Pause and escalation conditions

- New AST-depth policy/body maximum or unrelated malformed-envelope work goes to root rather than expanding this ticket.
- Setup-only RED failures are diagnosed before source changes; maximum8iterations.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9dra-deep-graphql-json.md
- Validator result: structural validation, stdlib source/test syntax and diff check PASS.
- Independent verification result: pending root review.
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: actual GREEN/full API, all four independent reviews, merge and exact QA readback pending.
- ClickUp final evidence comment: root owns publication.
