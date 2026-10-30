# Goal Contract — TASK-17tnw2b9dnu

## Identity

- Goal ID: TASK-17tnw2b9dnu
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Refuse insecure hosted base URLs before credentials leave the device
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9dnu
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Operator cloud configuration and LicensingClient construction refuse non-HTTPS URLs with fixed actionable data-free errors before credentials or transcripts are sent, while legitimate HTTPS and explicit loopback test fixtures remain functional.

## Baseline

Actual main83d9cf81bf5174d0c3cd3858921bf05540ba02fd contains merged reviewed WVF. Operator cloud_base_url filters only absent/empty values; LicensingClient::new stores any scheme without validation; shared ReqwestTransport refuses redirects but accepts HTTP. Frozen full task has no comments/dependencies and linked predecessor231 is merged. No new owner feedback is assumed; root tracker refresh/start is pending access.

## Inputs and evidence sources

- Full api-qualification/17tnw2b9dnu.json and qualifications.md; AGENT-RUNBOOK.md; parent WAVE3 selection and root dispatch.
- Current operator configuration/provider callers, licensing constructors/callers, cloud transport TLS/redirect fixtures, DEC-019 and repository CLAUDE guidance.

## Scope

### In scope

- HTTPS admission at the operator env configuration and public licensing constructor; explicit compatibility and safe error handling.
- Shared cloud transport defence in depth after existing TLS/loopback test analysis; retain redirect-none and OS-root/ring/timeouts.
- Real credential receiver refusal tests, HTTPS and explicit loopback fixture positives, meaningful admission mutants/exact restoration, accurate config/test docs.

### Non-goals

- No sign-in service rollout, TLS root/provider decision, held185/233 scope, secret provisioning, LAN/mobile/driver/UI changes or next DNV ticket.

### Constraints

- Own isolated codex branch and source only; not alone, preserve all other agents' work.
- No local project runtime/import/test/build/install/container. Hosted pinned normal Linux gates and bounded exact-parent separate workflow diagnostics only.
- Root owns ClickUp/status/publication/reviews/merge/QA. Author ordinary push/draft PR/body-file/immediate attachment authorized; actual100 attachment cap must remain explicit.
- Do not panic, rewrite bad URLs silently, expose URL query/userinfo in errors, weaken assertions or follow redirects.

### Assumptions and unknowns

- UNKNOWN actual RED and precise compatibility impact until hosted real cases. Constructor API changes require all callers adjusted explicitly without weakening their behavior assertions.

## Dependencies and approvals

- User selected20 authorization and root dispatch authorize unchanged actionable task; WVF merged. Root catches up start/QA receipts truthfully when tracker access returns.
- Farah13y0 operator main.rs test changes wait for this merge. DNV remains queued.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Actual insecure credential path reproduced before fix | Hosted unchanged-production operator/licensing refusal regressions with real receiver and positive controls | Behavioral RED, setup failures separated, request capture proves baseline risk | cloud-https-admission/red receipts | PENDING |
| C-002 | yes | Operator and licensing refuse insecure bases safely before send | Hosted scheme/error/no-send regressions, actual cloud-live wiring and meaningful mutants/restoration | Non-HTTPS refused with fixed data-free error, receiver untouched; mutants detected and exact source restored | Focused/mutation logs and source proofs | PENDING |
| C-003 | yes | HTTPS and explicit loopback fixtures preserve transport contracts | Existing TLS/redirect/error/timeout tests plus focused positive controls | Legitimate HTTPS and explicit test loopback work; no redirects, OS roots/ring/deadlines unchanged | Hosted target/full regressions and docs | PENDING |
| C-004 | yes | Final normal affected desktop and opt-in cloud-live gates pass | Exact-source normal Rust/operator/RELEASE/native/cloud-http plus hosted cloud-live checks/tests/clippy | Required gates pass without assertion weakening or timeout inflation; exclusions explicit | Normal and supplemental CI receipts | PENDING |
| C-005 | yes | Four final independent reviews and verified merge/QA pass | Root Cody/Quinn/Vera/Shadow, expected/actual merge tree and exact qa readback | No unresolved finding, reviewed tree merged, linked ticket qa | Root review/merge/QA receipts | PENDING |

## Verification plan

- Focused verification: hosted real receiver counts/body capture and fixed error redaction, valid HTTPS/TLS, explicit loopback and opt-in operator wiring; meaningful mutants and exact restoration.
- Broader regression verification: normal affected Rust/operator/default/devkeys/openainotes/RELEASE/native/cloud-http gates; additional cloud-live coverage remains distinct.
- Independent verifier: Cody, Quinn, Vera and Shadow coordinated by root.
- Required environment: hosted Linux pinned Rust/cache/system packages; local Git/stdlib/source/static/goal tools only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: the current operator env and licensing constructor accept plain HTTP before the no-redirect transport can protect a first credential request.
- Change or investigation: read full task/current code and canonical contracts; created isolated managed checkout at actual83d main. Registration hit100 attachment cap, checkout exists and is reused explicitly.
- Verifier executed: Git/source baseline and structural goal validator before substantive code.
- Result: scope established; runtime RED and all completion predicates pending.
- New evidence: full frozen task/qualification/runbook and this contract.
- Decision: iterate

## Risks and rollback

- Risks: constructor compatibility, hidden cloud-live branch, test-only escape leaking to ordinary production calls, unsafe URL error text and fixture coverage loss.
- Rollback or recovery: one scoped reviewed PR; real refusal/positive/mutation proof and normal CI; no deployment action.

## Pause and escalation conditions

- Stop for new owner policy, required unapproved production/destructive action or bounded no-progress limit. Yield hosted checkpoints and preserve every failed/unknown gate.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9dnu-cloud-https-admission.md
- Validator result: pending structural verification
- Independent verification result: pending
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: C-001 through C-005 pending
- ClickUp final evidence comment: root-owned pending
