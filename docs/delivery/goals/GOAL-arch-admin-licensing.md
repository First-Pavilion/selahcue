# Goal Contract - GOAL-arch-admin-licensing

## Identity

- Goal ID: GOAL-arch-admin-licensing
- Parent goal ID: GOAL-admin-console-ux-design
- Title: Admin account, billing, license-key, entitlement, and licensed-download architecture is ready for review
- Role: software-architect
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Produce a review-ready architecture for SelahCue Admin account, billing, app license-key, Bible entitlement, and licensed-download operations based on the Admin PRD and UX handoff, including bounded contexts, data ownership, API/event contracts, failure modes, security/privacy posture, observability, migration/rollback strategy, ADRs, implementation sequencing, and unresolved owner decisions.

## Baseline

Verified current state before substantive architecture work:

- ClickUp Build Control task `86ajnx548` is active and records SelahCue as being in implementation foundation work; ClickUp read/search/comment-read tools are available.
- Previous Admin documentation was moved into the existing docs structure after user clarification. User later refined code ownership: Vue 3 Admin frontend code belongs under `implementation/admin`, Django + Strawberry API code belongs under `implementation/api`, architecture documentation belongs in `docs/architecture/`, and goal evidence belongs in `docs/delivery/goals/`.
- `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md` defines the Admin Console requirements for staff access, customers, subscriptions, app license keys, Bible catalogue, entitlements/downloads, support, audit, settings, and compliance.
- `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md` defines the Admin UX flows and missing screens for app keys, Bible catalogue, entitlements, download diagnostics, subscriptions, support, settings, and audit log.
- `docs/architecture/adr/ADR-0017-translation-providers.md` defines the existing pluggable translation-provider seam and the entitlement-gated offline licensed-download posture.
- Current repository implementation has desktop/domain/data/LAN/operator/mobile foundations, but no implemented Vue Admin frontend or Django Platform API was found in prior PM evidence.
- ClickUp create-comment previously failed with `INVALID_ARGUMENT`; this goal will attempt start/final comments once and preserve pending ClickUp update text if writes remain unavailable.

## Inputs and evidence sources

- User request on 2026-08-08: `$software-architect` should work on account, billing, license-key, entitlement, and download architecture based on previous agent handoffs.
- User refinement on 2026-08-08: Admin frontend should be Vue 3; Django + Strawberry GraphQL API should serve both Admin and normal users.
- User refinement on 2026-08-08: generated Admin frontend code should live under `implementation/admin`; generated Django API code should live under `implementation/api`.
- `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md`
- `docs/product/audits/Admin-Console-Project-Brief-Audit.md`
- `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md`
- `docs/design/ADMIN-CONSOLE-HANDOFF.md`
- `docs/product/prds/SelahCue-PRD.md`
- `product/PRODUCT-BRIEF.md`
- `docs/research/LICENSING-REGISTER.md`
- `docs/research/LICENSED-TRANSLATIONS.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/adr/ADR-0007-persistence.md`
- `docs/architecture/adr/ADR-0008-lan-protocol-security.md`
- `docs/architecture/adr/ADR-0011-observability.md`
- `docs/architecture/adr/ADR-0017-translation-providers.md`
- Relevant current code boundaries in `implementation/desktop/crates/selahcue-core`, `selahcue-data`, `selahcue-lan`, `selahcue-app`, `selahcue-operator`, and `implementation/mobile/`.
- ClickUp Build Control task `86ajnx548`, recent comments, and duplicate search.

## Scope

### In scope

- Architecture document under `docs/architecture/`.
- ADR(s) under `docs/architecture/adr/` for material decisions.
- Current-state and target architecture views.
- Bounded contexts, ownership, trust boundaries, component boundaries, and deployment topology.
- Data model, invariants, lifecycle, retention, indexing, audit, migration, backfill, and rollback strategy.
- API and event contracts for accounts, billing, license keys, entitlements, downloads, translation catalogue, support diagnostics, audit, and desktop activation/download interactions.
- Failure modes, retries, reconciliation, idempotency, rate limits, versioning, compatibility, and supportability.
- Security/privacy posture, role/permission model touchpoints, secrets, key handling, auditability, observability, SLOs, and capacity assumptions.
- Vertical implementation sequence and follow-up recommendations for security, backend, frontend, QA, and legal/product decisions.

### Non-goals

- Production code, database migrations, API implementation, UI implementation, billing-provider setup, or ClickUp implementation task creation.
- Legal approval for copyrighted Bible translation distribution, offline storage, sublicense, price, territory, attribution, export, or reporting terms.
- Final billing provider, identity provider, payment/refund flow, legal entity, pricing, initial publisher contracts, or exact translation list decisions.
- Security sign-off; this architecture can request a security review but cannot approve its own security posture.
- Writing generated Admin frontend code outside `implementation/admin` or generated Django API code outside `implementation/api`.

### Constraints

- Label material facts as Verified, Inferred, Assumed, or Unknown.
- Preserve SelahCue's offline-first desktop operation during services.
- Licensed Bible text must not be bundled in the installer unless a later legal decision explicitly approves it.
- App license keys and Bible translation entitlements are separate domain concepts.
- Sensitive key values, provider credentials, billing identifiers, customer data, and audit exports must be permissioned and redacted by design.
- Docs stay in the established docs tree. Future Vue 3 Admin code belongs under `implementation/admin`; future Django + Strawberry API code belongs under `implementation/api`.

### Assumptions and unknowns

- ASSUMED: The first architecture slice should target the Admin Licensing Foundation from the Admin PRD, not the later commercial automation/reporting slices. Owner: Product.
- ASSUMED: A web-admin backend can be introduced as a cloud/service-side component while desktop apps continue to function offline using signed local claims and refresh/grace rules. Owner: Architecture/Product.
- UNKNOWN: Final staff identity provider, billing provider, subscription source of truth, publisher contracts, reporting obligations, legal entity, exact plan tiers, and first licensed Bible translations. Owner: Product/Legal/Finance/Architecture.
- UNKNOWN: Whether SelahCue will provision Bible entitlements through API.Bible, direct publisher licences, mixed providers, or user-supplied content. Owner: Product/Legal.
- UNKNOWN: Exact production hosting stack for Admin services. Owner: DevOps/Architecture.

## Dependencies and approvals

- Product owner review required before delivery decomposition.
- Legal/rights-holder approval required before any copyrighted translation is sold, sublicensed, cached, downloaded, exported, or advertised as available.
- Security Reviewer must review staff RBAC, key generation, entitlement grants, download token design, audit logs, impersonation, secrets, and exports before implementation.
- Backend Engineer must validate data/API feasibility before implementation.
- Frontend Engineer must validate Admin UI contract fit against the UX handoff before implementation.
- DevOps Engineer must validate deployment, secrets, backup/restore, and observability choices before production.

## Completion predicate

All mandatory rows must be `PASS` for `GATE_REVIEW`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Current product, UX, architecture, code-boundary, licensing, and ClickUp evidence are inspected and labelled | Source review and `rg` evidence check | Architecture document includes labelled current-state evidence and cites the Admin PRD, UX handoff, ADR-0017, existing architecture docs, current code boundaries, and ClickUp task | `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md` sections 1-3 | PASS |
| C-002 | yes | Target bounded contexts, trust boundaries, ownership, component boundaries, deployment topology, and quality-attribute scenarios are explicit | Architecture review | Account, billing, license-key, entitlement, download, translation catalogue, audit/support, desktop activation, and provider contexts are defined with boundaries and scenarios | `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md` sections 4-8 | PASS |
| C-003 | yes | Data model, invariants, lifecycle, retention, indexing, auditability, migration, backfill, and rollback are defined | Data-contract review | Core entities and invariants for customers, subscriptions, keys, activations, translations, entitlements, downloads, audit, reports, and provider sync are documented | `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md` sections 9-10 | PASS |
| C-004 | yes | API and event contracts cover Staff Admin GraphQL, Customer Account GraphQL, desktop activation/download command APIs, billing sync, provider sync, audit, idempotency, pagination, errors, auth, authorization, rate limits, and compatibility | Contract review plus search for contract IDs | Stable GraphQL/API/event contract IDs and error taxonomy are present with authentication/authorization, schema/versioning rules, and GraphQL guardrails | `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md` sections 11-12 | PASS |
| C-005 | yes | Failure modes, retries, reconciliation, support diagnostics, security/privacy, observability, SLOs, capacity, backup, disaster recovery, and operational ownership are explicit | Operational/security architecture review | Document includes failure-mode table, threat-model starter, observability/SLO matrix, deployment/backup/restore/rollback guidance, and owner follow-ups | `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md` sections 13-18 | PASS |
| C-006 | yes | Material architecture decisions have ADR coverage with alternatives, consequences, and requirement traceability | ADR review | New ADR(s) exist under `docs/architecture/adr/` and link to Admin PRD/UX/ADR-0017 with options considered | `docs/architecture/adr/ADR-0021-admin-licensing-services.md` | PASS |
| C-007 | yes | Implementation sequence and next-role recommendations are explicit without creating duplicate Markdown tickets | Handoff review | Architecture document recommends vertical slices, spikes, and next roles while deferring ClickUp task creation until product gate | `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md` sections 19-21 | PASS |
| C-008 | yes | Goal contract validates before and after execution; ClickUp evidence status is attempted or recorded as pending if create-comment still fails | Validator + ClickUp process review | Shared and repo validators exit 0; start/final ClickUp comment succeeds or pending update text is recorded with the connector failure | This goal contract, validator output, and section 22 of architecture document | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: run the shared and repo Goal Contract validators; search for architecture sections, GraphQL/API contract IDs, source-root decisions, data entities, ADR link, and requirement IDs.
- Broader regression verification: confirm no production code was changed and no duplicate Markdown tickets were created.
- Independent verifier: later Security Reviewer/Backend Engineer/Product gate review; this architecture pass ends at `GATE_REVIEW`.
- Required environment: local repository, ClickUp read/comment tools, shell validation scripts.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-008
- Hypothesis: Existing Admin PRD, UX handoff, translation-provider ADR, architecture spine, and current code boundaries are sufficient to produce a review-ready architecture without implementation.
- Change or investigation: Inspected Admin PRD/UX handoff, architecture spine, persistence/security/observability ADRs, translation-provider/licensing documents, current provider/privacy code boundaries, ClickUp Build Control, and duplicate search. Created the Admin licensing architecture document and ADR-0021.
- Verifier executed: `rg -n '^## |ADMIN-API-|DESKTOP-API-|BILLING-|PROVIDER-|ADMIN-EVT-|ADM-FR-|ARCH-OD-|app_license_key|translation_entitlement|download_lease|audit_event|outbox_event|POLICY_DENIED|ENTITLEMENT_REQUIRED|GATE_REVIEW|ClickUp' docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md`; `rg -n 'ADM-FR-|ADR-0017|ADR-0007|ADR-0008|ADR-0011|modular monolith|Options Considered|Consequences|Required Follow-Up' docs/architecture/adr/ADR-0021-admin-licensing-services.md`; `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-arch-admin-licensing.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-arch-admin-licensing.md`; `git status --short docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md docs/architecture/adr/ADR-0021-admin-licensing-services.md docs/delivery/goals/GOAL-arch-admin-licensing.md Admin`.
- Result: C-001 through C-008 PASS. ClickUp start and final create-comment attempts failed with `INVALID_ARGUMENT`; pending start/final update text is recorded in the architecture document.
- New evidence: `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md`; `docs/architecture/adr/ADR-0021-admin-licensing-services.md`; ClickUp task `86ajnx548` read/search/comment-read evidence.
- Decision: gate-review

### Iteration 2

- Target criterion: C-004, C-006, C-007, and stale path constraints
- Hypothesis: User stack/path refinements can be incorporated as an ADR-backed architecture update without changing production code or reopening product scope.
- Change or investigation: Updated `ADMIN-LICENSING-ARCHITECTURE.md` to specify Vue 3 Admin under `implementation/admin`, Django + Strawberry Platform API under `implementation/api`, Staff Admin GraphQL at `/graphql/admin`, Customer Account GraphQL at `/graphql/account`, desktop `/v1` JSON command APIs, GraphQL guardrails, and revised implementation sequencing. Updated ADR-0021 to include the stack/source-root decision and consequences. Updated this goal contract to replace the superseded `Admin/` code-location constraint.
- Verifier executed: `rg -n 'Vue 3|Django|Strawberry|GraphQL|/graphql/admin|/graphql/account|implementation/admin|implementation/api|ADMIN-GQL-|ACCOUNT-GQL-|DESKTOP-API-' docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md docs/architecture/adr/ADR-0021-admin-licensing-services.md docs/delivery/goals/GOAL-arch-admin-licensing.md`; `rg -n 'ADMIN-API-|/admin/v1|All APIs use TLS, structured JSON|Future generated Admin code should live under' docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md docs/architecture/adr/ADR-0021-admin-licensing-services.md`; `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-arch-admin-licensing.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-arch-admin-licensing.md`; `git status --short docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md docs/architecture/adr/ADR-0021-admin-licensing-services.md docs/delivery/goals/GOAL-arch-admin-licensing.md implementation/admin implementation/api Admin`.
- Result: C-004, C-006, and C-007 remain PASS. Both goal validators passed. Active architecture/ADR docs no longer use the superseded Admin REST table, `/admin/v1`, or the old all-JSON API premise. Scoped git status shows only the three docs in this refinement.
- New evidence: `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md` version 0.2; `docs/architecture/adr/ADR-0021-admin-licensing-services.md`; this goal contract.
- Decision: gate-review

## Risks and rollback

- Risks: Architecture could imply legal approval for copyrighted translations; mitigation is explicit legal gate and unavailable states.
- Risks: Shared GraphQL service could accidentally expose staff object graphs to customer users; mitigation is separate `/graphql/admin` and `/graphql/account` schemas, resolver-level tenant scoping, and mandatory security review.
- Risks: Cloud Admin design could erode offline-first desktop promises; mitigation is signed local claims and service-independent Sunday operation.
- Risks: Key/entitlement operations are security-sensitive; mitigation is mandatory Security Reviewer follow-up before implementation.
- Risks: Billing/provider choices are unknown; mitigation is provider-adapter contracts and decision-owner labelling.
- Rollback or recovery: Docs-only architecture can be revised without runtime impact.

## Pause and escalation conditions

- Pause if legal/licensing decisions are required to pick exact translation terms.
- Pause if billing provider, identity provider, or hosting stack must be finalised.
- Pause before any production code, migration, secret, billing, or provider credential action.
- Escalate security-critical details to Security Reviewer before implementation.
- If ClickUp write access remains unavailable, record pending ClickUp update text and stop at gate review rather than claiming ClickUp was updated.

## Final evaluation

- Validator command: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-arch-admin-licensing.md`
- Validator result: PASS via both `/Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py` and repo `scripts/validate_goal_contract.py`.
- Independent verification result: Pending product/security/backend review; this architecture pass does not approve implementation.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: None in the repository goal contract. ClickUp evidence comment remains pending because `_clickup_create_task_comment` returned `INVALID_ARGUMENT` for the start comment, original final handoff, and 2026-08-08 stack/path refinement handoff attempts.
- ClickUp final evidence comment: `Architecture handoff ready for review: docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md and docs/architecture/adr/ADR-0021-admin-licensing-services.md. Goal GOAL-arch-admin-licensing reached GATE_REVIEW after stack/path refinement. Scope covers Vue 3 Admin under implementation/admin, Django + Strawberry Platform API under implementation/api, staff/customer GraphQL surfaces, desktop licensing/download command APIs, account, billing, app license-key, Bible catalogue, entitlement, licensed-download, support diagnostics, audit, deployment, security/privacy, observability, migration, rollback, and implementation sequence. No production code or duplicate Markdown tickets created. ClickUp create-comment still fails with INVALID_ARGUMENT if this update cannot post, so this text is recorded in repo evidence.`
