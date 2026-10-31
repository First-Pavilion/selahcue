# Goal Contract — TASK-17tnw2bbhxm-private-grants

## Identity

- Goal ID: TASK-17tnw2bbhxm-private-grants
- Parent goal ID: NONE
- Title: Authorize a bounded private pilot read only after confirmed registration
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhxm
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

A pilot-only server grant validates the live receipt and immutable allowlisted artifact, then obtains a bounded private read URL without exposing PII or provider credentials.

## Baseline

Verified original main3f651d14 contains P13 receipts and confirmed allocation ledger. No private signer/manifest consumer exists; licensed downloads are separate501 stubs. Integrated reviewed current maincbc1e541 (Linux-only delta, no API overlap). Root supplies previously browser-verified criteria; current ClickUp reread/start evidence awaits root browser access.

## Inputs and evidence sources

- Existing P12 four criteria and P10/P11/P13 dependencies from verified ticket handoff
- Aria private-grant architecture accepted by root
- P13 services/policy and route/throttle contracts

## Scope

### In scope

- Disabled server grant, strict server-manifest consumer, private-read signer interface, focused tests, P11 schema handoff and runbook

### Non-goals

- Real bucket/provider invention, credentials, live collection, n8n/marketing changes, artifact promotion or licensed501 implementation

### Constraints

- Own managed worktree, ticket branch/PR; preserve others' files
- No production fake signer; missing real adapter returns503
- Fixed cohort cutoff2027-04-30T23:59:59Z; replay never extends receipt deadline
- No PII/provider credential or receipt in object URLs/logs

### Assumptions and unknowns

- UNKNOWN P10 provider/account/region/owner, P11 complete real manifest, P15 owner/retention/notice

## Dependencies and approvals

- Root authorizes synthetic source work while real P10/P11/P15/full-journey gates remain blocked
- Reuse P13 verification unchanged; root owns browser updates and four-review/merge coordination

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Only authenticated bounded requests with valid live receipts and same-platform artifacts reach signer | grant endpoint/service tests | forged/altered/pending/unsupported/cross-platform denied without URL | pytest log | PASS |
| C-002 | yes | Expiry is anchored and unsafe/failed signer results return safe errors | clock/signer tests | exact expiry/slow signer/replay/wrong origin/object fail closed | pytest log | PASS |
| C-003 | yes | Complete strict manifest, no fake production URLs, no PII URL/logs, licensed compatibility | config/manifest/regression tests | invalid/incomplete/revoked refused;501 unchanged | pytest log/runbook | PASS |
| C-004 | yes | Actual private read through recorded registration returns correct real bytes | approved P10/P11/P13/P15 live journey | anonymous denied; signed read bounded; hash verified | owner runtime evidence required | BLOCKED |
| C-005 | yes | All four independent reviews and current CI pass after fixes | root reviews and CI | Cody/Shadow/Quinn/Vera pass, current checks green | PR/reports | PENDING |

## Verification plan

- Focused verification: grant/config/manifest failures, registration and route/CSRF inventories, real PostgreSQL replay concurrency
- Broader regression verification: API suite and Django checks
- Independent verifier: Cody, Shadow, Quinn, Vera through root
- Required environment: own Python3.14 venv and newly generated disposable PG fixture; no credential extraction

## Iteration ledger

### Iteration 1

- Target criterion: C001-C003
- Hypothesis: strict receipt/manifest/signer boundaries can earn source evidence without live storage
- Change or investigation: read baseline, write failing behavioral tests first
- Verifier executed: structural validator; baseline32 registration checks; RED/GREEN grant tests; combined347 grant/P13/env/route/foundation checks; final85 grant checks; Django check and migration drift
- Result: source85 grant checks pass,1 PG-only case skipped on SQLite; prior combined347 checks pass; full PostgreSQL suite running
- New evidence: docs/delivery/evidence/p12-private-grants.md and private pytest logs; generated PG credentials remain only in harness process memory
- Decision: iterate

## Risks and rollback

- Risks: bearer URL can survive until short expiry; storage revocation/full journey require actual evidence
- Rollback or recovery: disable grants; preserve P13 ledger/counters/Sheet; reject unknown schema

## Pause and escalation conditions

- No live enablement without real inputs; three materially different failed approaches without new evidence stop
- Form selection integration stays explicit until root reconciles frontend/n8n

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbhxm-private-grants.md
- Validator result: structural PASS; completion not asserted
- Independent verification result: root scheduling all four reviewers; not yet passed
- Terminal state: GATE_REVIEW for source snapshot; live C004 BLOCKED and reviews/CI pending
- Remaining failed or blocked criteria: C004 live journey; C005 review/CI
- ClickUp final evidence comment: root browser pending
