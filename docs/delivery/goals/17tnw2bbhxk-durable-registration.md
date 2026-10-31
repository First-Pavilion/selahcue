# Goal Contract — 17tnw2bbhxk durable registration

## Identity

- Goal ID: 17tnw2bbhxk-durable-registration
- Parent goal ID: NONE
- Title: Retry-safe n8n registration reserves one Sheet row and confirms only acknowledged writes
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhxk
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Implement authenticated, disabled-by-default n8n reservation/confirmation callbacks with durable identity binding, bounded non-reused row allocation and short-lived receipt issuance only after trusted matching Sheet acknowledgement. Supply an inactive workflow and explicit deployment prerequisites.

## Baseline

Verified origin/main add4702e3474fb9c6c793beccbd2d38b59993db0 includes the pure v1 validator but no persistent pilot registration or endpoint. Earlier n8n export appends rows with execution-specific IDs and cannot recover ambiguous timeouts safely.

## Inputs and evidence sources

- P13 ClickUp source/comments relayed by root, and prior API contract.
- User chosen pilot validity: 2027-04-30T23:59:59Z, per root handoff.
- Root verified current n8n Form Trigger production hidden query fields; target-runtime verification remains required.

## Scope

### In scope

- Minimal PII-free durable allocation/binding/confirmation state and migrations.
- Authenticated JSON reserve/confirm callbacks and receipt verifier interface for P12.
- Fixed-row RAW write contract, retry/race/error tests, inactive workflow and runbook.

### Non-goals

- Bucket download grants, licensed downloads, actual collection/deployment or invented owner/retention approval.

### Constraints

- Dedicated protected Sheet tab: no structural row insertion, sort or deletion; retention clears cells without shifting allocations.
- Explicit approved notice, owner, retention, capacity and secrets must be configured before enabling.
- Root owns ClickUp browser updates and final merges; own worktree/branch only.

### Assumptions and unknowns

- Data owner, retention and actual Sheet/n8n credentials remain unknown; deployment disabled.
- Live n8n/Google and PostgreSQL availability must be reported honestly.

## Dependencies and approvals

- User authorized remaining implementation and independent four-role reviews before merge.
- Farah coordinates stable UUIDv4 query identity; hidden values remain untrusted.
- P12 resolves receipt to allowed release artifacts separately.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Auth/config/validation gates fail closed; no success without matching Sheet acknowledgement | focused Django integration tests | all targeted cases pass | tests/test_pilot_registration_service.py | PASS |
| C-002 | yes | Retry/race identity binds one destination/row/payload; allocation capacity enforced | Postgres race suite and migration checks | no duplicate row or identity under race; checks pass | tests/test_pilot_registration_races.py | PASS |
| C-003 | yes | Workflow and runbook use stable identity, fixed RAW writes and safe failure paths | workflow structure/Code tests and sandbox import when available | artifacts validated; live limits explicit | docs/release/pilot-registration | PENDING |
| C-004 | yes | Independent code/security/QA/performance findings resolved | root-coordinated reviews on final head | four reviews pass | root review report | PENDING |

## Verification plan

- Focused verification: own API venv pytest, prior pure contract suite, migration drift and Django checks.
- Broader regression verification: API suite as feasible; root coordinates shared resources.
- Independent verifier: Cody, Shadow, Quinn and Vera through root.
- Required environment: Python 3.14 own API venv; PostgreSQL for real locking/race proof; n8n sandbox and fake Sheet for workflow proof when available.

## Iteration ledger

### Iteration 1

- Target criterion: C-001/C-002.
- Hypothesis: a DB-unique stable identity plus immutable fixed row allows idempotent RAW writes after ambiguous remote outcomes.
- Change or investigation: test-first state and callbacks.
- Verifier executed: own Python 3.14 API venv, SQLite service/JS tests; PostgreSQL 17-alpine loopback fixture for real lock races; schema drift/Django checks; isolated empty SQLite migration forward/reverse/forward.
- Result: first service run exposed and fixed a 413 incorrectly caught as generic JSON ValueError. Current focused suite: 46 tests and 57 subtests pass. Earlier PostgreSQL combined suite: 48 tests and 57 subtests pass, including four actual races; final affected checks are recorded in the PR.
- New evidence: root independently imported all 13 nodes into pinned n8n 2.45.7, source SHA256 b816c91abd62cd7a4714243d0416455f9614607da40e7f4f039e0b0f73c12cc8. Live Google write/protection and the full mocked graph remain separate rollout evidence. Default placeholders fail closed.
- Decision: handoff.

### Iteration 2

- Target criterion: compatibility/security integration of C-001 and C-002.
- Hypothesis: exhaustive route/CSRF/deployment registries must explicitly include the new server-only surface without changing desktop licence semantics.
- Change or investigation: added separate pilot route contracts, pinned intentional CSRF exemptions with server-auth/cookie isolation tests, and registered every new environment read in deployments.md.
- Verifier executed: affected API contract/native/deployment suites with loopback permission; full API regression and final focused controls.
- Result: affected regression suite 352 PASS. Initial unprivileged full suite reported 15 failures and 8 errors: four expected new integration-gate failures were fixed; the others were loopback socket permission failures. Authorized-loopback full rerun passed 2235 tests, with 52 explicit skips and 57 subtests. That full run started before a final local callback-only 429-envelope normalization and its new CSRF-enforced budget test; final affected checks validate that change rather than claiming the earlier broad result covers later bytes.
- New evidence: maximum valid 254-character formula-like email produces a 255-character literal Sheet cell; corrected per-column workflow bounds and added a backend-to-JS regression control.
- Decision: handoff.

### Iteration 3

- Target criterion: C-003 actual n8n runtime.
- Hypothesis: the unary boolean If descriptor must carry singleValue=true so strict validation does not treat the empty right operand as a boolean.
- Change or investigation: root's actual n8n 2.45.7 mocked graph reproduced the missing-descriptor error; generator fixed and regression control added. Privacy execution-retention settings stay unchanged.
- Verifier executed: current workflow structure/Code suite; root reruns pinned n8n full graph with synthetic callback/Sheet mocks.
- Result: root subsequently verified both saved and Sheet-failure retry completions on the prior export using mocked transport nodes. Real HTTP authentication and Google persistence remain unverified. Cody's required visible-platform finding is addressed below; its updated runtime rerun remains pending.
- New evidence: import validation alone does not execute strict If operand validation.
- Decision: handoff.

### Required review remediation — Cody round 1

- Finding: the marketing page promises platform confirmation, but the original export hid platform; reviewers also found a blank line at the new workflow test file's EOF, invalidating the earlier diff-check claim for that snapshot.
- Change: only the stable UUID remains hidden. A required visible platform dropdown offers Windows, Ubuntu and macOS, using identical label/name `platform` and no configured default. Existing query fields, strict enum validation and server payload binding stay intact. Removed the extra EOF blank line.
- Red control: the revised workflow test failed with platform still hidden (1 failed, 6 passed); two narrower invocations hit the repository's session catalogue fixture without a DB-marked test, so the full workflow module was used to initialize its synthetic schema.
- Verifier: current workflow/service/race/contract and affected integration checks, diff check against the PR base, plus root's pinned n8n 2.45.7 visible-prefill and graph controls.
- Result: PostgreSQL 17 affected checks PASS (107 tests, 57 subtests); full PR diff against base passes `git diff --check`, and goal structure validates. Updated-runtime verification remains pending. C-003/C-004 remain PENDING until coordinator evidence and four independent rechecks are current.

## Risks and rollback

- Risks: external structural Sheet edits break allocation integrity; configuration gate and runbook must make this explicit. Registration UUID/fingerprint metadata still requires an owner retention policy.
- Rollback or recovery: disable collection first; preserve allocation state/counters and existing Sheet rows. Never reuse old row numbers or restore DB/Sheet independently.

## Pause and escalation conditions

- Unapproved collection policy, credentials or structural Sheet protection blocks enabling deployment, not safe code/test work.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2bbhxk-durable-registration.md
- Validator result: structural schema passes; completion mode withheld until independent reviews pass.
- Independent verification result: pending.
- Terminal state: GATE_REVIEW for the atomic code increment, not live P13 completion.
- Remaining failed or blocked criteria: C-004 reviews; final mocked workflow/actual Google integration, protected destination, owner/retention approval and private download handoff still gate deployment.
- ClickUp final evidence comment: root to post.
