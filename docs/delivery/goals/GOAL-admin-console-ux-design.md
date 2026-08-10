# Goal Contract - GOAL-admin-console-ux-design

## Identity

- Goal ID: GOAL-admin-console-ux-design
- Parent goal ID: GOAL-admin-console-brief
- Title: Admin Console UX handoff for SelahCue app licensing and Bible entitlements is ready for design review
- Role: ui-ux-designer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Create an implementation-ready UX handoff for the SelahCue Admin Console that builds on the existing Figma Admin shell and product brief, with particular attention to time-bound app license keys, Bible translation catalogue management, entitlement-gated downloads through SelahCue licensing, support diagnostics, staff permissions, auditability, responsive behaviour, accessibility, and missing screen states.

## Baseline

Verified current state before substantive work:

- `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md` defines the Admin Console product scope, functional requirements, business rules, state models, permissions, data definitions, risks, and open decisions for app license keys and Bible licensing.
- `docs/product/audits/Admin-Console-Project-Brief-Audit.md` recommends UI/UX design for missing Licenses, Subscriptions, Support, Settings, Audit Log, and non-default states before implementation.
- `docs/design/ADMIN-CONSOLE-HANDOFF.md` documents an existing Figma Admin Console proposal in file `SYQn5hFY8YVQKm3c6rw0eJ`, page/node `518:124`.
- The existing Figma Admin page includes the shared Admin shell and default frames for Overview, Customers, Customer detail, Users, Affiliates, affiliate detail, payouts, affiliate settings, and a reusable confirmation dialog.
- The existing design handoff explicitly says Subscriptions, Licenses, Support, and Settings are planned destinations, not designed screens.
- The user clarified after this pass that documentation should stay in the existing docs structure, and only generated Admin code should live under `Admin/`.

## Inputs and evidence sources

- User request on 2026-08-08 to continue the AI development workflow after the Admin brief, with the next role identified as UI/UX Designer.
- `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md`
- `docs/product/audits/Admin-Console-Project-Brief-Audit.md`
- `docs/design/ADMIN-CONSOLE-HANDOFF.md`
- `product/PRODUCT-BRIEF.md`
- Figma file reference: `SYQn5hFY8YVQKm3c6rw0eJ`, Admin Console page/node `518:124`
- ClickUp Build Control task: `https://app.clickup.com/t/86ajnx548`

## Scope

### In scope

- UX handoff under `docs/design/`.
- Information architecture and screen inventory for the Admin Console.
- Screen-level UX specifications for Overview, Customers, Customer detail, Users, Subscriptions, Licenses, Support, Settings, Audit Log, and permission/access states.
- End-to-end flows for prospect license key generation, Bible translation catalogue publication, customer Bible entitlement grants, entitlement-gated downloads, failed download triage, and revocation.
- State matrix covering loading, empty, filtered-empty, error, validation, permission, destructive confirmation, expired/revoked, and recovery states.
- Responsive, accessibility, keyboard, content, and component guidance suitable for frontend and QA follow-up.
- Traceability to the Admin requirement IDs in the project brief.

### Non-goals

- Editing the Figma file directly.
- Creating production code, routes, APIs, schemas, database migrations, tests, or ClickUp implementation tickets.
- Approving legal rights to distribute or download any copyrighted Bible translation.
- Finalising billing provider, identity provider, pricing, or publisher contract decisions.
- Designing the external Affiliate Portal beyond noting the existing handoff boundary.

### Constraints

- Documentation must follow the existing repository docs structure. Future generated Admin code should live under `Admin/`.
- Use the existing Figma Admin shell, token language, and interaction patterns as the base.
- Treat Figma values, customer names, KPI values, licence keys, commission values, and mock data as placeholders.
- Keep Admin as an internal staff operations tool, separate from the desktop presenter, customer Account portal, and Affiliate Portal.
- Label unapproved legal/licensing decisions as open decisions rather than product facts.

### Assumptions and unknowns

- ASSUMED: This pass should create a repository handoff/spec and not write to Figma, because the user asked to continue the workflow and did not request Figma edits. Owner: Product/UI.
- ASSUMED: The first implementation slice is "Admin Licensing Foundation" from the Admin project brief. Owner: Product.
- UNKNOWN: Exact staff identity provider, billing provider, publisher contracts, translation catalogue, and offline grace rules. Owner: Product/Legal/Architecture/Security.
- UNKNOWN: Final data-table volume, filtering backend, and audit/export retention policy. Owner: Architecture/Backend/Security.

## Dependencies and approvals

- Product owner approval required before delivery decomposition.
- Legal/rights-holder approval required before any copyrighted Bible translation is sold, sublicensed, downloaded, cached offline, exported, or advertised as available.
- Architecture approval required for account, billing, entitlement, key-generation, audit-log, and revocation-service ownership.
- Security review required before staff RBAC, impersonation, full-key display/recovery, entitlement grants, export/reporting, refunds, device deactivation, or revocation ships.
- Figma/design approval required if the team wants visual frames beyond this textual UX handoff.

## Completion predicate

All mandatory rows must be `PASS` for `GATE_REVIEW`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Source inputs are inspected and the UX handoff identifies what is existing, missing, assumed, and unresolved | Document review against source list | Handoff cites the Admin brief, audit, existing Figma Admin handoff, and Figma node `518:124`; existing vs missing screens are distinguished | `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md` sections 1-3 | PASS |
| C-002 | yes | Admin IA and screen inventory cover all required internal Admin screens without blending customer Account or Affiliate Portal responsibilities | IA review | Handoff defines Overview, Customers, Customer detail, Users, Subscriptions, Licenses, Support, Settings, Audit Log, and access-denied routes | `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md` sections 3-5 | PASS |
| C-003 | yes | App license-key, Bible catalogue, entitlement, download diagnostics, and revocation flows are implementation-ready | Flow review | Handoff includes flow steps, decision points, primary screens, actions, states, and requirement traceability | `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md` section 6 | PASS |
| C-004 | yes | Screen states and operational edge cases are documented for frontend and QA | State review | Handoff includes loading, empty, filtered-empty, error, validation, permission, destructive, expired/revoked, provider-down, retry, and recovery states | `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md` sections 7-8 | PASS |
| C-005 | yes | Accessibility, keyboard, responsive, content, and component behaviour are specified | UX quality review | Handoff covers semantic tables, focus, dialogs, copy/reveal behaviour, status labels, breakpoints, touch/keyboard behaviour, and component inventory | `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md` sections 9-12 | PASS |
| C-006 | yes | Requirement traceability maps UX coverage to Admin brief IDs and calls out design/Figma follow-ups | Traceability review | Handoff maps flows/screens to `ADM-FR-*` requirements and lists frame backlog names for Figma follow-up | `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md` sections 13-14 | PASS |
| C-007 | yes | Goal contract validates and ClickUp evidence status is recorded | Validator + process review | Validator exits 0; because ClickUp comment creation is a known connector blocker, the handoff records pending ClickUp update text instead of claiming the task was updated | Validator PASS via shared and repo scripts; `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md` section 15 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Run the Goal Contract validator from the repository and shared AI development team scripts.
- Search the UX handoff for required flow IDs, screen names, state coverage, and requirement traceability.
- Confirm documentation artifacts are in the existing docs structure and no generated Admin code is outside `Admin/`.
- Confirm no production code or ClickUp implementation tasks were created.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-007
- Hypothesis: The existing Admin brief and Figma handoff are sufficient to create an implementation-ready textual UX handoff for the missing Admin licensing surfaces without editing Figma.
- Change or investigation: Created the UX goal contract and Admin Console UX handoff, then moved documentation artifacts into the existing docs structure after user clarification; expanded the Admin shell into screen inventory, flows, states, accessibility, responsive, content, component, and traceability guidance.
- Verifier executed: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-admin-console-ux-design.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-admin-console-ux-design.md`; `rg -n 'UX-ADM-FLOW-|ADM-FR-|Licenses|Subscriptions|Support|Settings|Audit Log|Access Denied|Download Diagnostics' docs/design/ADMIN-CONSOLE-UX-HANDOFF.md`; `rg --files Admin`.
- Result: C-001 through C-007 PASS. The UX handoff is ready for product/design review. ClickUp final update remains pending as repository evidence because prior create-comment attempts on task `86ajnx548` failed with `INVALID_ARGUMENT`.
- New evidence: `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md`
- Decision: gate review

### Iteration 2

- Target criterion: Repository layout correction after user clarification.
- Hypothesis: Documentation artifacts should follow the existing docs structure, while future generated Admin code should be reserved for `Admin/`.
- Change or investigation: Kept the UX handoff in `docs/design/`, the UX goal contract in `docs/delivery/goals/`, and updated references to the Admin project brief and audit in their docs locations.
- Verifier executed: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-admin-console-ux-design.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-admin-console-ux-design.md`; stale moved-document path search across `docs` and `product`; `find Admin -maxdepth 1 -type f -print`.
- Result: Goal contract validation PASS from both validators; no stale moved-document paths found; no document files remain in `Admin/`.
- New evidence: Current docs paths listed above.
- Decision: gate review

## Risks and rollback

- Risks: A textual UX handoff may be mistaken for approved final Figma frames. Mitigation: explicitly mark visual frames as a follow-up and cite existing Figma gaps.
- Risks: Licensing operations could imply legal approval. Mitigation: keep legal approval, territory, offline, reporting, and rights-holder decisions as required gates.
- Risks: Admin interactions such as impersonation, revoke, refund, export, and full-key reveal are security-sensitive. Mitigation: include permission, reason, confirmation, and audit requirements.
- Rollback or recovery: Docs-only changes can be revised or removed without runtime impact.

## Pause and escalation conditions

- Pause for product owner approval before delivery decomposition.
- Escalate Figma write requests to UI/UX Designer plus Figma tool workflow.
- Escalate legal/licensing decisions to Legal/Product before build.
- Escalate key-generation, entitlement-service, audit-log, and revocation details to Software Architect and Security Reviewer before implementation.

## Final evaluation

- Validator command: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-admin-console-ux-design.md`
- Validator result: PASS via both `/Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py` and repo `scripts/validate_goal_contract.py`.
- Independent verification result: Pending product/design review; this handoff does not approve implementation.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: None in the repository goal contract. ClickUp evidence comment remains pending because the create-comment connector is failing.
- ClickUp final evidence comment: Pending because prior `_clickup_create_task_comment` attempts returned `INVALID_ARGUMENT` on task `86ajnx548`. Proposed comment: `Admin Console UX handoff is ready for product/design review in docs/design/ADMIN-CONSOLE-UX-HANDOFF.md. It covers missing Licenses, Subscriptions, Support, Settings, Audit Log, app license-key, Bible entitlement/download, revocation, accessibility, responsive, state, component, and requirement-traceability guidance. No production code or ClickUp implementation tasks were created.`
