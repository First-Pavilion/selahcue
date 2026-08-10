# Goal Contract - GOAL-sec-admin-licensing

## Identity

- Goal ID: GOAL-sec-admin-licensing
- Parent goal ID: GOAL-arch-admin-licensing
- Title: Admin licensing Platform API security review is ready for gate review
- Role: security-reviewer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 5
- Independent verification required: yes

## Objective

Produce a design-time security and privacy review for the SelahCue Admin Licensing Platform architecture, covering Vue 3 Admin, Django + Strawberry Platform API, staff/customer GraphQL surfaces, desktop licensing/download command APIs, billing/provider webhooks, app license keys, device tokens, entitlements, licensed Bible downloads, audit, exports, secrets, privacy, and implementation-blocking findings.

## Baseline

Verified current state before substantive security work:

- ClickUp Build Control task `86ajnx548` is active and readable. Recent comments show ongoing SelahCue delivery gates and review evidence.
- ClickUp create-comment has repeatedly returned `INVALID_ARGUMENT` for Admin PM/UX/architecture handoffs; this goal will attempt comments and preserve pending update text if writes remain unavailable.
- `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md` version 0.2 defines the target architecture as a Django + Strawberry Platform API under `implementation/api`, a Vue 3 Admin frontend under `implementation/admin`, separate staff/customer GraphQL endpoints, narrow desktop `/v1` command APIs, and provider/billing webhooks.
- `docs/architecture/adr/ADR-0021-admin-licensing-services.md` records the hosted modular Admin Licensing Platform decision and the stack/source-root refinement.
- No implemented Admin frontend or Django Platform API code exists yet, so this security pass is a design-time threat model and secure-design review, not a code vulnerability assessment.
- Existing SelahCue security posture includes desktop-local encrypted storage, LAN RBAC/encrypted transport, local-first redacted observability, and a prior early threat model for the desktop/mobile product.

## Inputs and evidence sources

- User request on 2026-08-08: continue after `$security-reviewer` was recommended as the next workflow skill.
- `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md`
- `docs/architecture/adr/ADR-0021-admin-licensing-services.md`
- `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md`
- `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md`
- `docs/security/reviews/threat-model-draft.md`
- `docs/architecture/adr/ADR-0007-persistence.md`
- `docs/architecture/adr/ADR-0008-lan-protocol-security.md`
- `docs/architecture/adr/ADR-0011-observability.md`
- `docs/architecture/adr/ADR-0017-translation-providers.md`
- `docs/research/LICENSED-TRANSLATIONS.md`
- ClickUp Build Control task `86ajnx548` and recent comments.

## Scope

### In scope

- Security review document under `docs/security/reviews/`.
- Assets, actors, entry points, privileges, trust boundaries, data classification, and attacker goals.
- STRIDE-style threats for staff Admin GraphQL, customer Account GraphQL, desktop command APIs, billing/provider webhooks, provider adapters, download leases, licensed Bible text, audit/export, secrets, and background jobs.
- Authentication, session handling, CSRF/CORS/CSP/security headers, authorization, tenant isolation, object-level access, idempotency/replay, rate limits, GraphQL query controls, input/output handling, file/download handling, secrets, key custody, logging, privacy, retention, deletion, third parties, and operations.
- Severity-classified findings with evidence, impact, likelihood, remediation, verification approach, and owner.
- Security verdict for pre-implementation gate review.

### Non-goals

- Production code, database migrations, API implementation, UI implementation, dependency installation, destructive tests, penetration tests, exploit development, production access, or secret handling.
- Final legal approval for Bible licensing, retention, privacy terms, publisher reporting obligations, or customer terms.
- Final identity provider, billing provider, hosting platform, exact cryptographic suite, or object-store vendor selection.
- Creating duplicate Markdown tickets in place of ClickUp tasks.
- Risk acceptance on behalf of Product, Legal, Finance, Security, or the user.

### Constraints

- Label material facts as Verified, Inferred, Assumed, or Unknown.
- Do not overstate speculative design risks as confirmed code vulnerabilities.
- Do not expose sensitive exploit detail beyond what is needed for remediation.
- Preserve desktop offline-first live operation while assessing activation/download security.
- Docs stay under `docs/...`; future Admin code belongs under `implementation/admin`; future Django API code belongs under `implementation/api`.
- If ClickUp comment creation fails, record the exact pending update text in the repository evidence.

### Assumptions and unknowns

- ASSUMED: This pass should assess the current architecture and produce implementation-blocking guardrails before backend/frontend build. Owner: Product/Architecture.
- ASSUMED: Staff Admin and customer Account GraphQL will share Django domain services but use separate schema namespaces and authorization contexts. Owner: Architecture/Backend.
- UNKNOWN: Staff IdP, MFA policy, customer identity model, billing provider, hosting platform, secrets/KMS provider, object-store provider, exact signature envelope, first licensed translations, retention periods, and publisher reporting payloads. Owner: Product/Security/Legal/Finance/DevOps.

## Dependencies and approvals

- Architecture handoff must exist and be review-ready. Status: satisfied by `GOAL-arch-admin-licensing`.
- Legal/Product must decide first licensed Bible translations, offline grace/deletion/reporting terms, and customer-facing promises before implementation. Status: unresolved, not blocking this design review.
- DevOps must later decide hosting, KMS/secrets, database, object store, backups, and environment controls. Status: unresolved, not blocking this design review.
- Backend/Frontend must later implement controls and tests before release security sign-off. Status: future work.

## Completion predicate

All mandatory rows must be `PASS` for `GATE_REVIEW`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Security review inputs and current-state facts are inspected and labelled | Source review and `rg` evidence check | Security review cites architecture, ADR, PRD, UX handoff, prior threat model, relevant ADRs, licensing research, and ClickUp evidence with Verified/Inferred/Assumed/Unknown labels | `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md` sections 1-3 | PASS |
| C-002 | yes | Assets, actors, entry points, privileges, trust boundaries, and data classification are explicit | Security architecture review | Review includes staff, customer, desktop, provider, billing, service-job, database/object-store, export, and audit boundaries with data classes | `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md` sections 4-6 | PASS |
| C-003 | yes | Threats and abuse cases cover GraphQL, tenant isolation, key generation, device activation, signed policies, download leases, licensed Bible text, webhooks, provider adapters, audit, exports, and background jobs | STRIDE review plus search for threat IDs | Severity-classified threats exist with impact, likelihood, controls, and verification approach | `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md` sections 7-8 | PASS |
| C-004 | yes | Required secure-design controls are specified for auth/session, RBAC, object access, GraphQL, CSRF/CORS/CSP, idempotency/replay, rate limits, secrets, signing keys, downloads, logs, and operations | Control checklist review | Review identifies release-blocking controls and implementation verification expectations | `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md` sections 9 and 12 | PASS |
| C-005 | yes | Privacy and compliance risks are assessed for customer data, billing data, device data, licensed Bible text, reporting, retention, deletion, exports, diagnostics, and third parties | Privacy review | Data minimisation, redaction, retention/deletion, legal owner decisions, and no-full-Bible-text logging/export rules are explicit | `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md` sections 10 and 13 | PASS |
| C-006 | yes | Findings, security verdict, owner decisions, and follow-up tasks are actionable and do not overclaim implementation security | Findings review plus ClickUp process review | Findings include severity, evidence, remediation, owner, verification; verdict is `Blocked` or `Pass with Required Controls`; ClickUp updates are posted or pending text recorded | `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md` sections 1, 11, and 13-15 | PASS |
| C-007 | yes | Goal contract validates before and after execution and no Admin/API production code is changed | Validator and scoped git status | Shared and repo validators exit 0; scoped status shows docs-only changes for this pass | This goal contract and command output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: run positive `rg` checks for threat IDs, GraphQL/security controls, source-root decisions, privacy controls, findings, and verdict in the security review.
- Negative verification: confirm this pass does not create Admin/API production code or claim security sign-off for unimplemented code.
- Goal verification: run `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-licensing.md` and `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-licensing.md`.
- Independent verifier: later Backend/Frontend/Security implementation reviews and QA; this design-time security pass ends at `GATE_REVIEW`.
- Required environment: local repository, shell validators, ClickUp read/comment tools.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-007
- Hypothesis: The Admin licensing architecture has enough detail to produce a design-time security review with actionable implementation-blocking controls, without production code or external secrets.
- Change or investigation: Reviewed Admin architecture/ADR, Admin PRD, UX handoff, prior threat model, persistence/LAN/observability/translation-provider ADRs, licensing research, current Django/Strawberry/OWASP guidance, and ClickUp Build Control/comments. Created `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md`.
- Verifier executed: `rg -n '^## [1-9]|SEC-ADM-T0|SEC-ADM-T1|SEC-ADM-T2|SEC-ADM-F|SEC-OD-|Pass with Required Controls|Not Assessed|/graphql/admin|/graphql/account|implementation/admin|implementation/api|CSRF|CORS|CSP|DataLoader|GraphiQL|introspection|licensed Bible|retention|Pending ClickUp final update' docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md`; placeholder scan for unfinished template markers in the security review and goal contract; `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-licensing.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-licensing.md`; `git status --short docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md docs/delivery/goals/GOAL-sec-admin-licensing.md implementation/admin implementation/api Admin`.
- Result: C-001 through C-007 PASS. ClickUp start comment failed with `INVALID_ARGUMENT`; pending start/final update text is recorded in the security review.
- New evidence: `docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md`; current Django/Strawberry/OWASP source checks; ClickUp task `86ajnx548` read/comment-read evidence.
- Decision: gate-review

## Risks and rollback

- Risks: This review could be mistaken for final security sign-off; mitigation is an explicit design-time verdict and later implementation security-review gate.
- Risks: GraphQL/shared-service risks could be underspecified until code exists; mitigation is to define concrete resolver, schema, tenant, and test guardrails now.
- Risks: Legal/licensing/privacy decisions are unresolved; mitigation is to mark them owner-blocked and require Product/Legal acceptance before implementation.
- Rollback or recovery: Docs-only security review can be revised without runtime impact.

## Pause and escalation conditions

- Pause before any production access, secret handling, destructive test, exploit execution, or provider/billing integration.
- Escalate legal/licensing/retention/customer-terms decisions to Product/Legal.
- Escalate cryptographic suite, signing-key custody, and identity/MFA choices to Security/Architecture/DevOps.
- If ClickUp write access remains unavailable, record pending update text and stop at gate review rather than claiming ClickUp was updated.

## Final evaluation

- Validator command: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-sec-admin-licensing.md`
- Validator result: PASS via shared validator and repo `scripts/validate_goal_contract.py`.
- Independent verification result: Design-time security review complete. Release security sign-off remains Not Assessed until implementation, deployment configuration, tests, and runbooks exist.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: None in the repository goal contract. ClickUp evidence comment remains pending because `_clickup_create_task_comment` returned `INVALID_ARGUMENT` for the security start and final handoff attempts.
- ClickUp final evidence comment: `Security review ready for gate review: docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md and docs/delivery/goals/GOAL-sec-admin-licensing.md. Goal GOAL-sec-admin-licensing reached GATE_REVIEW. Verdict: Pass with Required Controls for pre-implementation planning; release security sign-off remains Not Assessed because no Admin/API code exists. Scope covers Vue 3 Admin, Django + Strawberry Platform API, staff/customer GraphQL, desktop command APIs, billing/provider webhooks, app keys, device tokens, signing keys, entitlements, licensed downloads, audit, exports, privacy, retention, and operational controls. No production code, secrets, destructive tests, or duplicate Markdown tickets created.`
