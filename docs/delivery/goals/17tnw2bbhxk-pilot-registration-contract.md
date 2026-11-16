# Goal Contract — 17tnw2bbhxk registration contract increment

## Identity

- Goal ID: 17tnw2bbhxk-registration-contract
- Parent goal ID: NONE
- Title: Versioned pilot registration validation rejects invalid submissions without disclosing field values
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhxk
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 3
- Independent verification required: yes

## Objective

Implement and test the normalized v1 registration boundary as the first P13 increment; document the remaining durable persistence and trusted receipt handshake without claiming deployed endpoints.

## Baseline

Verified local main at 93bf472f65a1846117eecf09b1972c4118dc0cd4: licensed downloads is a placeholder namespace. The attached n8n draft hosts/validates a form and appends to Sheets, but uses execution IDs, has no durable retry identity and issues no authorization. No Django environment is installed in this worktree.

## Inputs and evidence sources

- User-approved P13 and P12 task descriptions, including the Figma reference notes.
- Attached n8n draft and README under /private/tmp/selahcue-pilot-handoff.
- Existing API package layout and root CLAUDE.md.

## Scope

### In scope

- Pure normalized-payload validation in a separate pilot_downloads namespace.
- Bounded fields, explicit version/platform/UUID identity, literal Sheet-cell rendering.
- Focused standard-library tests and proposed integration contract.

### Non-goals

- HTTP routes, database/deduplication implementation, signed receipts, live n8n/Sheets, private bucket grants, licensed API changes.

### Constraints

- Own worktree and branch; no changes to main or other agents' files.
- Only root writes ClickUp through the browser.

### Assumptions and unknowns

- Proposed form fields mirror the draft; final fields/privacy notice and hosting are owner decisions.
- Live provider credentials and deployment hostnames remain unknown and are not invented.

## Dependencies and approvals

- User authorized implementation startup. Root owns ClickUp status and comments.
- P12 grant resolution depends on bucket/manifest; no deployed download claim in this increment.
- Independent Cody/Shadow/Quinn/Vera review remains pending before ticket completion.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Valid normalized payload is accepted and invalid boundaries fail without echoing values | unittest registration contract suite | All focused cases pass after observed initial failure | implementation/api/tests/test_pilot_registration_contract.py and iteration ledger | PASS |
| C-002 | yes | Contract separates validation, persistence and authorization and records unresolved work | Read contract against task and implementation | No claim that validation or execution identity grants downloads | docs/architecture/api/PILOT-REGISTRATION-v1.md | PASS |
| C-003 | yes | Required independent reviews approve the increment | Independent reviewer reports | No unresolved blocking finding | Root review handoff | PENDING |

## Verification plan

- Focused verification: standard-library unittest with API root on PYTHONPATH, no service credentials.
- Broader regression verification: compile added Python files and git diff --check; no routes/settings/migrations changed.
- Independent verifier: root routes the four team reviewers when a slot is available.
- Required environment: Python 3.12+ for supported API runtime; tests also avoid third-party dependencies.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 and C-002.
- Hypothesis: a strict bounded normalized contract can reject malformed data without needing live Sheets or Django.
- Change or investigation: test-first validation and explicit integration boundaries.
- Verifier executed: Python 3.14.5 standalone suite (8 tests), py_compile with a temporary cache prefix, and git diff --check.
- Result: 8 tests PASS. Initial package import failed on missing Celery; isolating the pure module then proved the expected missing-file failure before implementation. Python 3.9.6 also passed, but Python 3.14.5 is the relevant supported-runtime evidence.
- New evidence: default Xcode Python cache path is outside the writable sandbox; a temporary PYTHONPYCACHEPREFIX makes compilation succeed without changing app code. No full Django test environment is installed.
- Decision: handoff.

## Risks and rollback

- Risks: this is not a complete registration system; caller must preserve stable retry identity and implement durable deduplication.
- Rollback or recovery: remove the isolated module/tests/docs; no database or deployed endpoint changes.

## Pause and escalation conditions

- Unresolved receipt/deduplication design or deployment choices return to root; no public endpoint is guessed.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2bbhxk-pilot-registration-contract.md
- Validator result: structural validator PASS; completion validation intentionally withheld while review criterion is pending.
- Independent verification result: pending.
- Terminal state: GATE_REVIEW for this increment only; P13 remains In progress.
- Remaining failed or blocked criteria: C-003 independent review. Full P13 persistence, deduplication and n8n integration remain unimplemented.
- ClickUp final evidence comment: root to post; increment does not complete P13.
