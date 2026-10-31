# Goal Contract — TASK-17tnw2b9dnv

## Identity

- Goal ID: TASK-17tnw2b9dnv
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Enforce HTTPS at every bounded model-download redirect hop
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9dnv
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The STT model downloader requests only HTTPS URLs, including each redirect hop, and stops at a finite five-hop bound while valid TLS redirects still stream and install the pinned verified model with unchanged lifecycle/cancellation behavior.

## Baseline

Actual main1ac7b781e499687d10b4ef2184d057051195ac38 includes reviewed DNU. Standalone selahcue-stt is excluded from the desktop workspace; current model_fetch agent sets proxy(None) only and delegates redirect behavior to pinned ureq3.5.0. Full frozen task has zero comments, no dependencies and linked predecessor231 merged. Parent confirms unchanged actionable scope; live tracker refresh/start pending access. Existing installer streams64KiB chunks, verifies SHA256, cleans failures/cancel and caches verified files; no new body-size/deadline policy is inferred from scripture.

## Inputs and evidence sources

- Full api-qualification/17tnw2b9dnv.json including task/comments/dependencies/linked task; qualifications.md rank5 and frozen selected20.
- Current STT model_fetch/model manifests/tests/lock; scripture download/url_policy as rule precedent only; pinned ureq3.5.0 source call_run/config/redirect loop and TLS APIs.
- Repository root/desktop CLAUDE guidance, backend/goal contracts and AGENT-RUNBOOK.md.

## Scope

### In scope

- Same HTTPS-only every-hop and finite max5redirect rule as scripture, using pinned client enforcement if real tests prove equivalent; no scripture behavior change.
- Hosted real throwaway-CA TLS fixtures proving downgrade target receives no request, legitimate HTTPS redirects work, relative/scheme-relative/bounds/status/error cases, pinned integrity/cache/cleanup/cancel positives.
- Private cfg(test)-only trust-root injection into the identical shipped builder; no exported production trust bypass or insecure fixture production policy.
- Standalone default/download tests and clippy plus normal affected desktop gates; meaningful policy mutants/exact source restoration and accurate implementation docs.

### Non-goals

- No provider/model choice/download-service rollout, weights download, legal/held185/233 decisions, broad downloader redesign, new timeout/size/proxy/TLS-root policy, DNU branch edits or next AWR unit.
- No scripture, controller/LAN/mobile/driver/UI changes.

### Constraints

- Own isolated codex branch from actual main, not alone, preserve all others' source.
- Actual hosted behavior RED before policy fix; setup/compile/oracle failures are never RED/pass. Preserve valid HTTPS redirect behavior and all existing assertions.
- No local project runtime/import/test/install/build/container/benchmark. Local source/Git/stdlib/static pinned formatting/goal checks only.
- Runtime must explicitly target standalone selahcue-stt default and download; normal workspace CI alone never establishes these tests/clippy.
- Root owns tracker/fourreviews/publication/merge/QA. Author ordinary push/draft PR/body-file/immediate attachment and compact exact-parent workflow-only hosted diagnostics authorized;100attachment cap remains explicit.

### Assumptions and unknowns

- UNKNOWN actual downgrade behavior until real TLS RED; task originally inferred it. Pinned client HTTPS-only guard is checked before headers/connect on each call_run, to be corroborated by real multihop fixtures.
- Existing STT ureq timeout defaults and streaming/integrity/cancel semantics are preserved; scripture's separate body-size/deadline policy is not added implicitly.

## Dependencies and approvals

- User-authorized selected20 and root dispatch cover this unchanged existing task; DNU actual merge1ac verified by root, QA/export pending root receipt.
- No AWR/controller work without later root dispatch and required Mika serialization.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Actual TLS downgrade reproduced before policy fix | Hosted standalone download tests with real trusted TLS redirect and HTTP receiver, positive controls | Genuine missing-policy RED; trusted TLS and recorder positives execute; setup/oracle failures separate | stt-https-redirects/red-attempt1 and red-classification.json actual18pass8fail | PASS |
| C-002 | yes | HTTPS enforced at first request and every bounded redirect hop | Real TLS downgrade/relative/scheme-relative/limit tests and meaningful HTTPS/max-hop mutants/exact restoration | Insecure target sees no request, legitimate TLS chain works, finite max5 enforced, mutants detected and original bytes restored | Focused/sensitivity raw and component proofs | PENDING |
| C-003 | yes | Existing installer/lifecycle/network policy invariants preserved | Existing default/download tests unchanged, real integrity/cache/partial-cleanup/cancel/TLS positives, source/docs review | No altered pin, streaming chunk/proxy/timeout/default trust/cancellation/phase semantics; existing assertions pass | Hosted full standalone suites and source/lock/doc proof | PENDING |
| C-004 | yes | Actual standalone and normal affected integration gates pass | Hosted explicit standalone default/download test+clippy and normal affected Rust/operator/RELEASE/native gates | All required final-source gates pass; skips/ignores/platform exclusions explicit | Current exact-source normal/supplemental raw receipts | PENDING |
| C-005 | yes | Four final independent reviews and actual merged tree/QA verified | Root Cody/Quinn/Vera/Shadow receipts, expected/actual merge proof, exact linked ticket qa readback | No unresolved finding; reviewed tree merged, correct ticket qa | Root review/merge/QA receipts | PENDING |

## Verification plan

- Focused verification: real tiny pinned bytes over throwaway-CA TLS chain, downgrade/no-send and recorder positives, max-hop and relative-hop controls; never real model weights/provider endpoints.
- Broader regression verification: explicit standalone default/download tests and clippy plus full normal affected Linux desktop gates.
- Independent verifier: root-coordinated Cody, Quinn, Vera and Shadow.
- Required environment: hosted pinned Rust/Linux/cache/setup only for runtime; local source/Git/stdlib/static/goal tools.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: the current proxy-only ureq builder allows an HTTPS-to-HTTP hop and uses a broader default redirect bound than the scripture rule.
- Change or investigation: read complete task/current source/qualification/runbook; managed checkout at actual1ac, existing100attachment registration error recorded and path reused. Read pinned ureq guard before connection and its redirect loop as source precedent, not runtime proof.
- Verifier executed: source/Git/manifest/lock read and structural child validation before substantive tests.
- Result: contract/scope established; actual hosted policy RED and all final gates pending.
- New evidence: full frozen task/qualification/current pinned source and this goal.
- Decision: iterate

### Iteration 2

- Target criterion: C-001.
- Hypothesis: unsafe default redirect settings produce observable plaintext requests and exceed the scripture five-hop rule.
- Change or investigation: independently verified official raw/hash/run41174561222. Actual26selected cases:18passed8failed0.09s, five downgrade statuses eachHTTP1, laterTLS2+HTTP1, firstHTTP1, loop11requests. Default60+4+3passed/1existingignore; no setup/oracle substitution. Strict all-target clippy separately exposed3legacy engine-test unwraps and9model-test unwraps+1constant assertion.
- Verifier executed: raw failures/markers/positive cases, official metadata/hash validation and Cargo lock base64 decode/SHA comparison.
- Result: C-001 PASS. Actual generated lock e59f57a54d55be911f038337a8c2b1958c56775180ee68587ef8fc57dc8844e1 contains only reachable dev fixture additions/rootedges, no existing production package version/checksum churn.
- New evidence: red-attempt1/, red-classification.json, Cargo.generated-red.lock and lock-proof.json.
- Decision: iterate

### Iteration 3

- Target criterion: C-002 through C-004.
- Hypothesis: the pinned client's HTTPS-only setting and max5 redirects enforce the same rule with unchanged installer/default network behavior.
- Change or investigation: added https_only(true)/max_redirects5 only to the same builder, retained proxy(None)/all defaults and existing streaming/install/error logic. Committed the exact inspected Cargo-generated dev fixture lock. Necessary strict-clippy prerequisite is test-only descriptive expect messages and black_box of the same chunk-ceiling assertion; all old runtime assertions retained, no lint allowance/skip, engine production byte-identical.
- Verifier executed: static pinned formatting, source/lock/component/goal checks. Hosted full standalone/default/download/clippy, policy mutants/exact restoration and normal affected gates pending.
- Result: candidate prepared, no GREEN or independent-review claim yet.
- New evidence: lock-proof.json, forthcoming static/mutation/normal candidate receipts and compact review-dispatch.
- Decision: handoff

## Risks and rollback

- Risks: fixture trust injection masking production policy, later-hop downgrade or off-by-one hop limit, hidden standalone clippy failures and accidentally altered installer/default policy.
- Rollback or recovery: isolated one-PR fix, private cfg(test) root seam, real TLS/no-send positives, exact mutants/restoration and normal/standalone gates. No deployment action.

## Pause and escalation conditions

- Stop for new product/policy/owner decisions or unapproved/destructive/production actions; preserve every actual failed/unknown gate. Yield durable checkpoints while hosted runs execute; no next task without dispatch.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9dnv-stt-https-redirects.md
- Validator result: PASS structural verification before substantive tests
- Independent verification result: pending
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: C-001 through C-005 pending
- ClickUp final evidence comment: root-owned pending access
