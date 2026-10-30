# Goal Contract — TASK-17tnw2b9adv

## Identity

- Goal ID: TASK-17tnw2b9adv
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Keep origin refusal diagnostics secret-free and make the nginx trust guard resist valid bypasses
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9adv
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Origin startup refusals cannot disclose pasted credentials or query secrets; four valid nginx trust bypasses fail the guard, while the shipped configuration and legitimate quoted values pass. Operators receive accurate HSTS, Traefik and full-checkout test instructions.

## Baseline

Verified fresh main dd5cc038efe04681e42746edb8d243996badc947, baseline normal CI41063872568 success. Full live task has zero comments, dependencies or linked tasks; raw packet and six-unit qualification are under wave3-20261030/api-qualification. Current settings split origins before credential masking; nginx guard strips quoted hashes and searches quoted directive text. Current nginx production configuration is unchanged and is the fixture input only.

## Inputs and evidence sources

- Complete task17tnw2b9adv payload, source-backed qualifications.md and selected20.json in the parent wave evidence.
- Repository CLAUDE.md, current settings and TLS/nginx tests, DEPLOYMENT.md section6c, API README and normal API workflow.
- Parent WAVE3-SELAHCUE-20 contract, bounded backend/goal operating contracts and explicit author/root ownership.

## Scope

### In scope

- Origin diagnostic sanitization before split information can leak, with comma/space/plain-userinfo, query and scheme-less negative cases and legitimate controls.
- Test-only nginx parser/guard hardening: comments only outside quotes; real directives only; reject mapped-variable set overrides and includes inside server; four actual bypass mutants and quoted positive controls.
- Accurate next API response HSTS rollback, edge full coverage, Traefik Cloudflare trustedIPs and never forwardedHeaders.insecure=true, full-repository checkout prerequisite.
- Only settings.py, test_tls_proxy.py, test_nginx_forwarded_proto.py, DEPLOYMENT.md, API README and this contract.

### Non-goals

- No production marketing/nginx.conf edit, origin-admission policy change, proxy-count/CSRF/header/DEBUG/environment/database behavior change, held PR185/233 scope, new dependency or deployment.
- No unrelated API/throttle/desktop tasks, no local project runtime, no independent self-review or merge/ClickUp writes.

### Constraints

- Isolated owned codex/17tnw2b9adv-origin-nginx-hardening branch; preserve other authors' changes.
- Hosted tests first against unchanged production, inspect behavioral RED before minimal fix; no setup errors counted as regressions.
- Hosted normal API twenty-minute gate retains checks/migrations/Postgres16/Redis7 and existing skips/assertions. No local project imports/tests/builds/containers due host paging.
- Root owns four independent reviews, valid finding routing, merge and QA/status/comment readbacks; author owns ordinary push/draftPR/immediate attachment and bounded own hosted diagnostics.

### Assumptions and unknowns

- UNKNOWN exact hosted regression and sensitivity results until executed; current text inspection is not runtime proof.
- Nginx fixtures must be accepted by a real hosted nginx parser before their guard refusal is meaningful; production fixture remains byte-identical.

## Dependencies and approvals

- Existing user authorization and frozen parent selection cover this unchanged task and valid remediation. No owner decision or unresolved declared dependency.
- Parent start/status/comment is delegated to root after this structural preflight; no authorization inferred for later queued tasks.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Actual settings RED demonstrates pasted secret leaks and nginx RED demonstrates all four missed bypasses | Hosted unchanged-production focused pytest plus real nginx syntax validation | Behavioral failures identify each gap; positive controls and setup succeed | api-origin-nginx-hardening/red-job.log and red-classification.json:19failed/75passed,8valid nginx fixtures | PASS |
| C-002 | yes | Origin errors are secret-free without changing accepted-origin and proxy/security semantics | Hosted test_tls_proxy.py including new redaction negatives/legitimate controls | No password fragments/query secrets; raw @ shows scheme plus mask only; all cases pass | Focused/full API raw logs | PENDING |
| C-003 | yes | Guard rejects all four valid bypasses and preserves legitimate quoted configuration | Hosted test_nginx_forwarded_proto.py and fixture syntax checks; sensitivity/restoration receipts | Four refusals, genuine directives/quoted benign controls pass; shipped config unchanged | Focused logs and Git fixture blob proof | PENDING |
| C-004 | yes | Operations and test docs describe the precise boundaries | Diff/readback against task AC and independent reviews | Next API response, edge coverage, trustedIPs/no insecure flag and full-checkout/no-skip guidance present | Current diff and four review reports | PENDING |
| C-005 | yes | Normal full API integration checks pass on the frozen current source | Official hosted normal CI checks, migration drift/apply and full pytest with PG16/Redis7 | All applicable gates pass; existing study skip explicit | CI metadata/raw logs and immutable handoff | PENDING |
| C-006 | yes | All four independent reviews and root integration/QA gates pass | Cody/Quinn/Vera/Shadow current-source receipts, actual merged tree and exact qa readback | No unresolved finding; approved tree merged; linked ticket qa | Root review, merge and QA receipts | PENDING |

## Verification plan

- Focused verification: actual settings subprocess behavior through existing batched environment fixture; real guard invocation on valid nginx mutants and positive controls.
- Broader regression verification: normal hosted full API check/migrations/tests, preserving all prior accepted cases and skips.
- Independent verifier: Cody, Quinn, Vera and Shadow coordinated by root; author does not independently approve own source.
- Required environment: hosted Linux with current Python/API service setup; local source/Git/stdlib AST/goal validator only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: unsplit raw diagnostic context and quote-aware real-directive guard checks are required by the specified regressions.
- Change or investigation: complete task/source qualification; new isolated managed worktree from actual dd5; established owned file boundaries and hosted test-first plan.
- Verifier executed: Git branch/status/base identity; source reads and structural goal validator.
- Result: baseline and scope verified; runtime results pending; no production source edited.
- New evidence: api-qualification/17tnw2b9adv.json and qualifications.md; this contract.
- Decision: iterate

### Iteration 2

- Target criterion: C-001.
- Hypothesis: the specified valid bypasses evade the unchanged guard and origin refusal diagnostics leak secret fragments or exceed the mandated raw-@ mask boundary.
- Change or investigation: committed test-only source78e452e4, published workflow-only child0aa9027a; real nginx syntax checks precede focused tests on current API service setup.
- Verifier executed: hosted diagnostic41089126195, exact raw red-job.log independently classified against selectors and assertions.
- Result: actual19failed75passed4.87s, zero setup/oracle errors. Four valid bypasses DID NOT RAISE; one quoted-comment loss; seven settings diagnostic failures and seven actual manage.py stderr failures. Eight nginx syntax successes (shipped, four bypasses, three quoted positives); preserved original counts and failures.
- New evidence: api-origin-nginx-hardening/red-classification.json, red-job.log, red-immutable-proof.json and red-receipt.json.
- Decision: iterate

### Iteration 3

- Target criterion: C-002 through C-005.
- Hypothesis: using raw unsplit diagnostic context and quote-aware directive tokens eliminates those gaps while preserving origin admission and real proxy behavior.
- Change or investigation: raw-@ errors expose only a safe scheme and mask; other query/fragment payloads masked. Guard reads real quoted/escaped tokens, own-location directives, forbids map overrides/server includes. Existing credential expectations aligned with stricter explicit task boundary; four new bypass assertions strengthened to require the intended refusal message. Updated HSTS/Traefik/full-checkout docs. Production nginx fixture unchanged.
- Verifier executed: local AST, whitespace and goal structural checks; current-main integration and hosted normal full API gates to follow.
- Result: scoped candidate prepared; no hosted GREEN or independent review claimed yet.
- New evidence: owned diff and forthcoming immutable candidate/CI handoff.
- Decision: handoff

### Iteration 4

- Target criterion: C-003.
- Hypothesis: CODY-ADV-01 is a valid residual because nginx variable names are case-insensitive but the mapped-variable set guard compares exact spelling.
- Change or investigation: read complete independent Cody receipt and traced guard/token/bypass path; added uppercase and mixed-case genuine override regressions with intended refusal message, retaining all original cases and an unrelated uppercase-variable set positive. Guard comparison unchanged for hosted RED.
- Verifier executed: stdlib AST/diff and goal checks; bounded own hosted nginx syntax/current-guard RED prepared.
- Result: existing normal run is superseded for this newly exposed scope; actual new RED/CI results pending, no finding closure claimed.
- New evidence: reviews/17tnw2b9adv-cody.md; forthcoming cody-case-red workflow/receipt/log under api-origin-nginx-hardening.
- Decision: handoff

### Iteration 5

- Target criterion: C-003 and C-005.
- Hypothesis: normalizing the ASCII map-variable name comparison closes CODY-ADV-01 without refusing unrelated set directives or altering any production code.
- Change or investigation: independently classified actual hosted41091760647 raw; all11nginx syntax fixtures accepted, exactly2DID NOT RAISE failures (uppercase/mixed-case map overrides),26controls passed in1.68s, no setup/oracle failure. Added lower() only to the mapped-variable comparison, with explanatory nginx semantic comment. All regression/positive fixtures unchanged since their RED.
- Verifier executed: raw selector/count/syntax classification, stdlib AST/diff/structural goal checks; final current-main integration/full normal hosted API CI pending.
- Result: actual review regression confirmed and minimal fix prepared; finding closure remains subject to full hosted GREEN and all four final reviews. No production nginx/settings/policy/dependency/workflow changes in remediation.
- New evidence: api-origin-nginx-hardening/cody-case-red-job.log and cody-case-red-classification.json; final immutable source/full CI receipts to follow.
- Decision: handoff

## Risks and rollback

- Risks: hiding useful diagnostics, inadvertently changing accepted origins, treating quoted directive text as executable configuration, invalid nginx mutants or absent checkout fixture.
- Rollback or recovery: one scoped PR; preserve original production fixture blob, positive controls and actual RED; correct evidence/setup separately and revert only an evidenced affected merge if necessary.

## Pause and escalation conditions

- Stop for new owner/product policy, unapproved production access, destructive operations or exhausted bounded iteration evidence.
- Yield immutable checkpoints during long hosted waits; root routes any valid review remediation. Do not begin queued tasks.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9adv-origin-nginx-hardening.md
- Validator result: PASS structural validation before source/test edits
- Independent verification result: pending
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: C-001 through C-006 pending
- ClickUp final evidence comment: root-owned, pending
