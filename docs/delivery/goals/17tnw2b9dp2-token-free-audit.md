# Goal Contract — TASK-17tnw2b9dp2

## Identity

- Goal ID: TASK-17tnw2b9dp2
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Keep account token derivatives out of new audit rows
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9dp2
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

New account credential/session audit rows use independent random attempt IDs and retain useful non-secret account outcomes without token-derived values in any audit column. Existing credential/session behavior, historical audit rows and intentional device renewal correlation remain unchanged.

## Baseline

Fresh main b01ce4e6860be99db2f82a71aef10c4ae229db8a still writes verification/reset live fingerprints, consumed masked tokens and session fingerprints in request_id; login/refresh also include masked tokens in after. Existing failed-reset-confirm rows already use uuid.uuid4().hex. Account writers and existing all-column failed-confirm test patterns inspected.

## Inputs and evidence sources

- Full saved task17tnw2b9dp2: wave2-20261029/api-qualification/17tnw2b9dp2.json;0comments,0dependencies. Follow-up of86ak5r2pt/PR232.
- Exact Wanted permits replacing account token correlation with uuid4().hex; device.activated and device_token.reminted token_fingerprint fields explicitly excluded.
- services.py, audit models/writer/redaction and existing customer auth/failed-confirm all-column tests.

## Scope

### In scope

- Seven account audit actions: email_verified, verification_resent, logged_in, session_refreshed, logged_out, password_reset_requested, password_reset_completed.
- Replace token-derived request_id with random independent UUID4hex and remove masked token fields from session audit payloads.
- Real successful flow tests scan every audit column and service logs for raw/fingerprint/hash/masked derivatives with planted-material positive controls, validate random attempt IDs and domain outcomes.

### Non-goals

- Historical audit rewriting, device renewal chain correlation changes, global redaction denylist changes, reset/auth/policy/identity/schema changes, held PR233/185 scope.
- Ticket's inline GraphQL literal logging note is explicitly informational/consideration, as qualified. No query-excerpt logging project or unexpected traceback suppression in this audit fix; known note remains documented for separate scoped work.

### Constraints

- No local project runtime/imports/tests/install/containers/benchmarks under paging; meaningful hosted RED and full normal API CI required.
- Isolated ticket branch; preserve other agents. Ordinary push/draft PR/immediate attach and bounded diagnostic refs authorized; no force push, merge, ClickUp/UI/status/review publication/subagents.
- Parent owns ClickUp and four independent reviews, merge, QA. Integrate fresh main before first PR; DRA/WVE source frozen in separate worktrees.

### Assumptions and unknowns

- UUID4hex pattern is already shipped and expressly allowed; test independence through deterministic UUID seam and uniqueness/format assertions rather than statistical randomness claims.
- Log absence proof covers successful service/variable-based real GraphQL flows; optional inline literal GraphQL failure leakage is not claimed fixed.

## Dependencies and approvals

- User approved wave implementation/CI/reviews/remediation/mergeQA; parent selects existing ticket and delegates author pipeline.
- No owner choice required for explicitly permitted random attempt ID option. Prior driver advisory and held policy work remain separate.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Seven successful account actions contain no raw/fingerprint/hash/masked token derivatives in any audit column or flow log | focused real flow/all-column regressions | meaningful RED then all scanned values absent | api-token-free-audit/red.log and green raw log | PENDING |
| C-002 | yes | Each action retains correct actor,target,outcome and independent distinct UUID4 attempt IDs | deterministic UUID and positive domain controls | correct rows/session/token lifecycle and unrelated fields | focused hosted tests | PENDING |
| C-003 | yes | Scanner detects planted full/fragment material in every actual audit column/log and intentional device correlation/history remains intact | scanner positive controls and existing renewal/auth regressions | positives bite; excluded data preserved | focused/full API logs | PENDING |
| C-004 | yes | Fresh target-integrated source passes checks,migrations and full API suite | normal hosted CI | green with prior skips preserved | PR/run/raw CI receipts | PENDING |
| C-005 | yes | Cody,Quinn,Vera,Shadow accept frozen source/remediation | parent independent reviews | allfour pass/no unresolved findings | parent review receipts | PENDING |
| C-006 | yes | PR merged and exact ticket QA persisted | parent delivery readback | source/tree/QA verified | parent delivery receipts | PENDING |

## Verification plan

- Focused: new account token-free audit regression module reusing real signup/verify/login/reset services and existing audit scan patterns; scanner positive controls.
- Broader: full normal API hosted PostgreSQL16/Redis7/Python3.14 checks/migrations/pytest with existing auth/audit/device renewal tests.
- Independent verifier: parent routes Cody,Quinn,Vera,Shadow.
- Required environment: hosted services; local stdlib syntax/diff/goal checks only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-003.
- Hypothesis: successful account writers still persist token fingerprints/masks in request_id/after; replacing with already-used independent attempt IDs removes these derivatives without weakening auth or useful audit outcomes.
- Change or investigation: complete task/comments/deps and current seven writer calls read; meaningful test-only real-flow regressions next.
- Verifier executed: structural goal validation; hosted diagnostic pending.
- Result: no production changes; actual runtime RED pending.
- New evidence: api-token-free-audit test-only receipt.
- Decision: iterate

## Risks and rollback

- Risks: operators lose direct account-token fingerprint correlation by design; actor,target,expiry,outcome remain. Avoid touching explicit device renewal correlation or historical evidence.
- Rollback or recovery: revert isolated account writer changes; no data/schema migration, credential policy or historical rewrite.

## Pause and escalation conditions

- Any need to rewrite history, invent correlation policy or widen held scope goes to parent; no such work assumed.
- Setup failures are not meaningful RED. Stop after3materially different failed attempts without new evidence and at maximum8iterations.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9dp2-token-free-audit.md
- Validator result: pending first execution.
- Independent verification result: pending.
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: actual hosted RED/GREEN, full CI, four reviews, mergeQA pending.
- ClickUp final evidence comment: parent owns publication.
