# Goal Contract — TASK-licensing-delivery-decomposition

## Identity

- Goal ID: TASK-licensing-delivery-decomposition
- Parent goal ID: BUILD-selahcue
- Title: Every Platform-PRD licensing requirement is reconciled to exactly one accountable ClickUp ticket under epic 86ajy5v6k, sequenced against the D1-D6 decision gates
- Role: delivery-manager
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy5v6k
- Created: 2026-08-25
- Updated: 2026-08-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every functional and non-functional requirement in `docs/product/prds/SelahCue-Platform-PRD.md` (FR-501-543, NFR-501-508) maps to exactly one accountable ClickUp ticket under epic 86ajy5v6k - either an existing ticket annotated with its PRD citation, or a newly created one - with ownership recorded in the ticket body, real ClickUp dependencies on the decision tickets that gate them, and an explicit critical path naming what can start with zero decisions answered.

## Baseline

Verified 2026-08-25 against the working tree and ClickUp:

- The PRD is untracked and uncommitted (`git status --porcelain docs/` shows `?? docs/product/prds/SelahCue-Platform-PRD.md`). It is the source of scope.
- Epic 86ajy5v6k on list 901327960792 holds 44 subtasks: 13 `complete`, 31 open (`planning/todo`, plus 86ak0qn63 in `code review`).
- Six of eight `LicenseKeyStatus` values have no production writer; `DeviceStatus.REVOKED` is consumed at `apps/devices/services.py:130,587` but never produced.
- The desktop Rust workspace contains no activation, entitlement or licence code in any of its 13 crates.
- The entitlement manifest (`apps/entitlements/services.py:64-80`) carries `feature_scope` (flat string), `territory`, `instances_used`, `instances_limit` - and none of watermark, screen/output count, NDI output count, or an STT minutes balance.
- `implementation/marketing/src/lib/api/graphql.ts` and `account.ts` exist with 4 mutations; only `ResetView.vue` and `VerifyView.vue` import them (`SignInView.vue` does not).
- `implementation/api/tests/test_concurrency_postgres.py` exists with two tests exercising `select_for_update` on the licence row; both SKIP unless the backend is PostgreSQL.
- `CustomerOrg.device_limit` (`apps/accounts/models.py:25`) is written at org creation (`accounts/services.py:119,514`) and read by the admin GraphQL schema, but never consulted by activation; enforcement is `license_key.device_limit` (`apps/devices/services.py:290,416`) and the manifest publishes the same (`apps/entitlements/services.py:75`).
- No watermark rendering capability exists anywhere in the product.

## Inputs and evidence sources

- `docs/product/prds/SelahCue-Platform-PRD.md` (FR-501-543, NFR-501-508, FLOW-501-506, RISK-501-506, METRIC-501-505)
- `docs/delivery/goals/TASK-platform-licensing-prd.md`
- ClickUp epic 86ajy5v6k and its 44 subtasks; Build Control 86ajnx548
- `implementation/api/selahcue_api/` (the shipped Platform API - where code and document disagree, the code is the fact)
- `implementation/marketing/src/` and `implementation/desktop/crates/`
- Owner instructions relayed mid-task: the Free/Pro/Platinum tier table; catalogue volatility; seat = device instance; STT quota per calendar month, pooled per org

## Scope

### In scope

- Mapping each open ticket under 86ajy5v6k to the PRD requirement(s) it satisfies, recorded as a citation on the ticket
- Creating tickets only for requirements no existing ticket covers
- Correcting stale ticket text verified wrong against the tree
- Recording ownership (`/backend-engineer` Kenji, `/frontend-engineer` Farah, or the correct non-engineering role) in every ticket body I create or touch
- Setting real ClickUp dependencies from decision-gated tickets onto D1-D6
- Folding the owner's tier table and its four consequences into the backlog
- Updating Build Control 86ajnx548

### Non-goals

- Deciding D1-D6, or any facet the owner has not stated
- Assigning a ClickUp human assignee (no workspace user exists for Kenji or Farah)
- Implementing any requirement
- The affiliate programme (NG-P1, 86ak11w7g) - explicitly out of V1
- Committing, staging, stashing or pushing anything

### Constraints

- The checkout is shared with live agent sessions and `main` is protected: no git write operations of any kind
- A ClickUp MCP timeout is not proof of failure - verify before retrying, because a duplicate ticket is worse than a slow retry
- Never silently delete a ticket; supersession is recorded in a comment
- CON-P4: requirements gated on an open owner decision are marked DEFERRED or gated, never built ahead

### Assumptions and unknowns

- ASSUMED: the board convention of recording role ownership in the description body (as epic 86ajy5v6k does) is the sanctioned substitute for a ClickUp assignee. Validation owner: the owner, who instructed it directly.
- DECIDED (owner, mid-task): seat = device instance; one org licence key per org with `device_limit` 1/3/7. DEC-004 unchanged.
- DECIDED (owner, mid-task): STT quota period is per calendar month, resetting on the billing anniversary; scope is pooled per org.
- UNKNOWN: pricing and affiliate terms (D1 remaining scope). Validation owner: the owner.
- UNKNOWN: whether PRD NG-P2, which names watermarking as a prohibited enforcement mechanism, is amended to permit the Free-tier output watermark the owner has now required. Validation owner: Product Manager, then the owner.

## Dependencies and approvals

- D1 86ak10gph - partially closed by the owner (tier structure and limits decided; pricing and affiliate terms open). Owner-owned.
- D2 86ak10g47 (payment provider / merchant of record) - open. Owner-owned. Gates EPIC-PL-F only.
- D3 86ak10g8q (suspend vs revoke severity) - open. Owner-owned. Gates FR-504/510/522.
- D4 86ak10ga1 (renewal grace) - open. Owner-owned. Gates FR-521.
- D5 86ak10gb9 (signing-key rotation and custody) - open. Owner-owned. Gates FR-538, shapes FR-518.
- D6 86ak120fz (distinct EXPIRED error code) - open. Owner-owned. Gates FR-523, shapes FR-529.
- PRD approval on 86ak0qn63 - in `code review`; decomposition is explicitly post-approval work (PRD 32).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Every MVP, R2 and DEFERRED FR in PRD 32 traceability maps to exactly one accountable ticket or a cited disposition | Requirement-by-requirement review of the coverage map against PRD 32 | 43 FR + 8 NFR all accounted for; zero unmapped | Coverage map in the final report | PASS |
| C-002 | yes | No new ticket duplicates an existing one under 86ajy5v6k | Compare every created ticket title and scope against the 31 open tickets before creating | Zero duplicates | Created-vs-existing table in the final report | PASS |
| C-003 | yes | Every ticket created or touched carries an explicit `**Owner:**` line and its PRD citation in the body | Read back each written description | Owner line and citation present on each | ClickUp descriptions | PASS |
| C-004 | yes | The stale claim on 86ak11r67 is corrected against verified tree evidence | `grep` for API-layer imports in `implementation/marketing/src` | Ticket text names the 4 shipped mutations and the 2 consuming views; remaining scope is sign-in / create-account / forgot-password | Ticket 86ak11r67 description | PASS |
| C-005 | yes | 86ajyq86g is verified against the tree and dispositioned per finding | Read `implementation/api/tests/test_concurrency_postgres.py` and the six findings | Each of the 6 findings marked satisfied or still-open with file evidence; ticket closed only if all are satisfied | Ticket 86ajyq86g comment | PASS |
| C-006 | yes | Decision-gated tickets carry real ClickUp `waiting_on` dependencies to D1-D6, with no cycles | Read back dependencies on each gated ticket | Every gated ticket blocked by its decision; zero cycles | ClickUp dependencies | PASS |
| C-007 | yes | The critical path is explicit, including the ordered set startable with zero decisions answered | Review sequencing against the dependency graph | An ordered list of decision-free tickets exists and none of them is gated | Final report | PASS |
| C-008 | yes | The owner's tier table and its consequences are folded in: catalogue data-driven, metering MVP and org-pooled monthly, OQ-P1 as a defect, manifest dimension gaps ticketed, watermark NG-P2 conflict raised | Review the affected tickets | Each of the five consequences has a ticket or a recorded amendment request | ClickUp tickets | PASS |
| C-009 | yes | Build Control 86ajnx548 records this decomposition | Read the Build Control comment | One comment naming scope, counts, decision gates and critical path | Ticket 86ajnx548 | PASS |
| C-010 | yes | Nothing was committed, staged, stashed or pushed | `git status --porcelain` and `git stash list` before and after | No staged entries introduced by this session; no new commits; stash list unchanged | Command output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: read back each created and updated ticket; walk the coverage map against PRD 32 requirement by requirement.
- Broader regression verification: confirm the 13 already-complete tickets are untouched, and that no ticket outside epic 86ajy5v6k was modified.
- Independent verifier: the owner at the delivery gate; Product Manager for the NG-P2 watermark amendment.
- Required environment: ClickUp MCP; read-only access to the shared checkout.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: the 31 existing tickets cover the shipped-adjacent API surfaces but not the licence state machine, the desktop enforcement client, or the new tier dimensions.
- Change or investigation: read the PRD, read all 44 subtasks, verified three claims against the tree.
- Verifier executed: `grep`/`sed` over `implementation/api`, `implementation/marketing`, `implementation/desktop`; `clickup_get_task` on the epic with subtasks.
- Result: hypothesis confirmed. EPIC-PL-C (8 requirements) has zero existing tickets; the state machine, suspend/reinstate, conversion, archiving, lifecycle emails, security-patch availability, signing-key custody, and all four new tier dimensions are uncovered.
- New evidence: the manifest payload carries none of watermark / screens / NDI / STT balance; no watermark capability exists anywhere in the product; PRD NG-P2 forbids watermarking as an enforcement mechanism.
- Decision: iterate

## Risks and rollback

- Risks: a ClickUp write times out but lands, producing a duplicate; the PRD is still in `code review` so decomposition could churn if the audit changes scope; the NG-P2 watermark contradiction is a product decision I must not resolve.
- Rollback or recovery: every created ticket is individually identifiable by its `[PL-x]` title prefix and can be cancelled; no repository state is changed, so there is nothing to revert in git.

## Pause and escalation conditions

- The owner must resolve the NG-P2 watermark contradiction before the Free-tier watermark work is buildable - escalate, do not decide.
- If ClickUp MCP becomes unavailable, stop before further ticket operations and return `BLOCKED` rather than writing a repository shadow backlog.
- Pricing and affiliate terms remain owner-owned; nothing in EPIC-PL-F may be sequenced as startable.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-licensing-delivery-decomposition.md`
- Validator result: PASS (10 criteria, 10 mandatory)
- Independent verification result: PENDING — owner review at the delivery gate; /product-manager owns the NG-P2 watermark amendment (86ak5mn3z)
- Terminal state: VERIFIED_COMPLETE for the decomposition; the epic itself returns GATE_REVIEW pending D3/D4/D5/D6 and the NG-P2 ruling
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: Build Control 86ajnx548 and tracking ticket 86ak5mmwv

### Iteration 2

- Target criterion: C-003 through C-010
- Hypothesis: the 31 existing tickets can be reconciled by citation comments plus targeted description rewrites, without duplicating any of them.
- Change or investigation: created 24 tickets; rewrote 6 descriptions (86ak11r67, 86ajyq86g, 86ak10gph, 86ak10abc, 86ak10amq, 86ak5mn3j); posted 16 PRD-traceability comments; set 23 ClickUp dependencies and removed 1 stale one.
- Verifier executed: `clickup_get_task` read-backs; `git status --porcelain`; `grep`/`sed` over `implementation/api` and `implementation/marketing`.
- Result: all 10 mandatory criteria PASS.
- New evidence: 5 of 6 findings on 86ajyq86g are fixed in the tree; the marketing SPA's API seam ships with 4 mutations and 2 consumers; the entitlement manifest carries none of the 4 new tier dimensions; PRD NG-P2 contradicts the owner's Free-tier watermark requirement.
- Decision: complete
