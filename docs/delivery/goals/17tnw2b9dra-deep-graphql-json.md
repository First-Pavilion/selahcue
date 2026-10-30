# Goal Contract — TASK-17tnw2b9dra

## Identity

- Goal ID: TASK-17tnw2b9dra
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Return safe validation responses for raw GraphQL JSON decode failures
- Role: backend-engineer
- Status: IN_PROGRESS
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
| C-003 | yes | Normal auth, CSRF, GET and GraphQL validation behavior preserved; resolver faults not broadly swallowed | positive browser/bridge/GET/query tests and narrow source inspection | expected200/403/405 contracts unchanged | focused/full hosted logs and review | PENDING |
| C-004 | yes | Current-main-integrated candidate passes full API checks/migrations/regressions with existing skips retained | normal hosted API CI | CI green, raw logs inspected | PR/run snapshot and raw log | PENDING |
| C-005 | yes | Frozen source passes Cody,Quinn,Vera,Shadow and valid findings are remediated/reviewed | root independent review round | no unresolved findings | root review evidence | PENDING |
| C-006 | yes | PR merged and exact ticket QA persisted | root delivery readback | merge/QA verified | root delivery evidence | PENDING |

## Verification plan

- Focused: test_graphql_raw_json.py through real Django URL/middleware/view without auth credentials; seed CSRF only where reaching decoding is intended.
- Broader: normal hosted PostgreSQL16/Redis7/Python3.14 API job, checks/migrations/all tests, existing foundation/auth/CSRF and previous config guards.
- Independent verifier: Cody,Quinn,Vera,Shadow through root.
- Required environment: hosted services; no local project runtime or large-body construction/execution.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: real route tests expose native JSON recursion/body-cap/UTF8 exception contract gaps while existing positive contracts already pass.
- Change or investigation: full requirements/source/dependency decode boundaries inspected, worktrees checked, new isolated current-main branch, tests first.
- Verifier executed: static syntax,diff and structural goal validation only.
- Result: unchanged-product candidate prepared for actual hosted RED.
- New evidence: wave2-20261029/api-deep-json/test-only-manifest.json.
- Decision: iterate

## Risks and rollback

- Risks: catching recursion outside the decoder would hide resolver bugs; fixed safe errors must not echo raw request content. Tests assert the exact safe envelope and source scope remains narrow.
- Rollback or recovery: revert this isolated input-boundary change; no schema,migration,data rewrite or operator configuration is changed.

## Pause and escalation conditions

- New AST-depth policy/body maximum or unrelated malformed-envelope work goes to root rather than expanding this ticket.
- Setup-only RED failures are diagnosed before source changes; maximum8iterations.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9dra-deep-graphql-json.md
- Validator result: structural validation and stdlib test syntax PASS.
- Independent verification result: pending root review.
- Terminal state: IN_PROGRESS
- Remaining failed or blocked criteria: actualRED/GREEN/fullAPI/reviews/merge/QA pending.
- ClickUp final evidence comment: root owns publication.
