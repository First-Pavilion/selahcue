# Goal Contract - GOAL-admin-console-brief

## Identity

- Goal ID: GOAL-admin-console-brief
- Parent goal ID: BUILD-selahcue
- Title: Admin Console project brief for SelahCue licensing, Bible entitlements, and app-license operations is created and ready for product review
- Role: product-manager (+ ui-ux-designer and business-analyst support)
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Create an evidence-labelled Admin Console project brief/PRD that extends the existing SelahCue product definition with internal staff workflows for customer administration, subscriptions, timed SelahCue app license keys, Bible-translation licensing/entitlements/downloads, support operations, settings, staff permissions, audit, compliance, and readiness gaps, then pause at a product review gate before ClickUp ticket creation.

## Baseline

Verified current state before substantive work:

- `product/PRODUCT-BRIEF.md` describes the whole SelahCue product and requires properly licensed Bible translations, but it does not define an internal Admin Console for managing app license keys or SelahCue-managed Bible entitlements.
- `docs/product/prds/SelahCue-PRD.md` defines the desktop/mobile product. Its licensing posture currently says bundled public-domain Bibles only, with licensed translations API-only/user-supplied later.
- `docs/research/LICENSED-TRANSLATIONS.md`, `docs/research/LICENSING-REGISTER.md`, and `docs/architecture/adr/ADR-0017-translation-providers.md` already establish that licensed translations can be offline after entitlement-gated activation only when a licence permits it, with an encrypted app-locked store, refresh/revocation obligations, attribution, and usage/reporting hooks.
- `docs/design/ADMIN-CONSOLE-HANDOFF.md` and Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, page/node `518:124`, define a proposed Admin Console IA with Overview, Customers, Users, Affiliates, Subscriptions, Licenses, Support, and Settings. The handoff explicitly says Subscriptions, Licenses, Support, and Settings are planned destinations, not designed screens.
- ClickUp Build Control task `86ajnx548` is connected and in progress. No new ClickUp implementation tasks may be created before user approval of the product gate.

## Inputs and evidence sources

- User request on 2026-08-08: create the project brief for the Admin end of SelahCue, focusing on licensing, Bible licensing/downloads through SelahCue licensing, and time-bound license-key generation for prospective users.
- Existing product brief: `product/PRODUCT-BRIEF.md`.
- Existing PRD: `docs/product/prds/SelahCue-PRD.md`.
- Existing design handoff: `docs/design/ADMIN-CONSOLE-HANDOFF.md`.
- Figma design metadata: file `SYQn5hFY8YVQKm3c6rw0eJ`, Admin Console page/node `518:124`.
- Licensing research: `docs/research/LICENSING-REGISTER.md`, `docs/research/LICENSED-TRANSLATIONS.md`.
- Translation architecture: `docs/architecture/adr/ADR-0017-translation-providers.md`.
- Delivery traceability/build state: `docs/delivery/REQUIREMENTS-TRACEABILITY.md`, `docs/delivery/BUILD_STATE.md`.
- Current official source checks on 2026-08-08: API.Bible docs/terms and Biblica/Tyndale permissions pages, used only to confirm that live licensing constraints remain decision-sensitive.

## Scope

### In scope

- Admin Console product brief/PRD under `docs/product/prds/`.
- Product audit gate under `docs/product/audits/`.
- Requirements with stable Admin IDs and independently testable acceptance criteria.
- Business rules for time-bound SelahCue app license keys, customer/subscription administration, Bible translation entitlements, licensed downloads, offline/revocation rules, permissions, support, audit, and compliance.
- Design alignment and explicit design gaps based on Figma/Admin handoff.
- ClickUp start/final evidence comments on Build Control task `86ajnx548`.

### Non-goals

- Implementing code, database migrations, APIs, UI, billing, entitlement services, or license-key cryptography.
- Signing or authorising Bible publisher licences.
- Creating ClickUp epics/stories/tasks before user approval of the brief.
- Treating the Figma placeholder data, pricing, commission values, or names as approved product facts.

### Constraints

- Label material facts as Verified, Inferred, Assumed, or Unknown.
- Do not give legal advice; Bible licensing decisions require rights-holder/legal confirmation before ship.
- Preserve the existing offline-first SelahCue product posture: core desktop presentation must continue without cloud or admin-console availability.
- Use ClickUp as delivery source of truth and repository docs as durable product evidence.

### Assumptions and unknowns

- ASSUMED: The Admin Console is a web-accessible internal back-office for SelahCue staff, separate from the local desktop app, external customer Account portal, and Affiliate Portal. Owner: Product.
- ASSUMED: App license keys may be generated for prospects as trials, demos, pilots, or paid entitlements with finite validity periods. Owner: Product + Commercial.
- UNKNOWN: Final billing provider, tax handling, account identity provider, staff roles, legal entity, pricing tiers, and exact publisher contracts. Owner: Product + Legal + Finance + Architecture.
- UNKNOWN: Whether SelahCue will resell Bible translation entitlements directly, provision API.Bible-backed access, or negotiate direct publisher entitlements by translation. Owner: Product + Legal.

## Dependencies and approvals

- User approval required after the brief/audit gate before ClickUp implementation tasks are created.
- Legal and rights-holder approval required before any copyrighted Bible translation is sold, sublicensed, downloaded, cached offline, exported, or advertised as available.
- Architecture approval required for account, billing, entitlement, key-generation, audit-log, and revocation-service design.
- Security review required before impersonation, license-key generation, staff RBAC, refund/payout operations, entitlement download, or device deactivation ships.

## Completion predicate

All mandatory rows must be `PASS` for `GATE_REVIEW`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Current state and source evidence are inspected and summarised with Verified/Inferred/Assumed/Unknown labels | Document review against source list | Brief includes a current-state section with labelled evidence and cites existing PRD/design/licensing/ADR/Figma sources | `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md` sections 1-2 | PASS |
| C-002 | yes | Admin Console scope is defined with users, problem, goals, success measures, in-scope capabilities, non-goals, and launch/release slice | Document review | Brief contains these sections and distinguishes internal Admin Console from customer Account and Affiliate Portal surfaces | `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md` sections 3-10 | PASS |
| C-003 | yes | Functional requirements have stable Admin IDs and independently testable acceptance criteria for app license keys, Bible entitlements/downloads, customers, subscriptions, staff users, support, settings, audit, and reporting | Requirements coverage review | Every major user-requested capability is covered by at least one stable requirement with observable acceptance criteria | `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md` section 11, `rg ADM-FR-` coverage | PASS |
| C-004 | yes | Business rules, permissions, states, exceptions, data definitions, privacy/security/licensing implications, risks, assumptions, and decision owners are documented | Business-analysis review | Brief includes rule catalog, state model, permissions matrix, data dictionary, exception catalogue, and open decisions | `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md` sections 12-22 | PASS |
| C-005 | yes | Design alignment and gaps are documented against the existing Figma/Admin handoff | Design review | Brief links Figma node `518:124`, lists reusable IA/components, and names missing Licenses/Subscriptions/Support/Settings screen/state work before build | `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md` sections 2 and 17 | PASS |
| C-006 | yes | Product audit gate is produced with coverage, unresolved decisions, conflicting evidence, risks, recommended refinements, and readiness verdict | Product audit review | Audit file exists and explicitly pauses for user approval before ClickUp delivery decomposition | `docs/product/audits/Admin-Console-Project-Brief-Audit.md` | PASS |
| C-007 | yes | Goal contract validates before and after work; ClickUp receives start and final evidence comments | Validator + ClickUp comment review | Validator exits 0; ClickUp Build Control `86ajnx548` has start/final evidence comments with terminal state | Validator PASS; ClickUp `_clickup_create_task_comment` returned `INVALID_ARGUMENT` for long, short, and `hello` comments on task `86ajnx548` | BLOCKED |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: run the Goal Contract validator, inspect the brief/audit for every criterion, and search requirement IDs/sections.
- Broader regression verification: confirm no production code was changed and no ClickUp implementation tasks were created before approval.
- Independent verifier: user/product gate review after this handoff; legal/security/architecture reviews are required child goals before build.
- Required environment: local repository, ClickUp MCP, Figma metadata/screenshot tools where available, official source checks for live licensing-sensitive claims.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-007
- Hypothesis: Existing product, design, licensing, ADR, Figma, and ClickUp evidence are sufficient to create a gate-ready Admin Console brief without new implementation tasks.
- Change or investigation: Inspected source artefacts, Figma metadata, ClickUp Build Control, and current official licensing source pages; created the brief and audit; validated the contract; attempted ClickUp evidence comments.
- Verifier executed: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-admin-console-brief.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-admin-console-brief.md`; `rg` coverage checks for Admin requirement/rule/flow IDs.
- Result: C-001 through C-006 PASS. C-007 BLOCKED because ClickUp comment creation failed with `INVALID_ARGUMENT` even for a literal `hello`, although ClickUp get/search/comment-read tools worked.
- New evidence: `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md`; `docs/product/audits/Admin-Console-Project-Brief-Audit.md`; Figma metadata for `518:124`; ClickUp task `86ajnx548`; API.Bible/Biblica/Tyndale official source checks dated 2026-08-08.
- Decision: blocked

### Iteration 2

- Target criterion: Repository layout correction after user clarification.
- Hypothesis: Documentation artifacts should follow the existing docs structure, while future generated Admin code should be reserved for `Admin/`.
- Change or investigation: Moved the Admin project brief to `docs/product/prds/`, the audit to `docs/product/audits/`, and the goal contract to `docs/delivery/goals/`; updated internal references.
- Verifier executed: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-admin-console-brief.md`; `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-admin-console-brief.md`; stale moved-document path search across `docs` and `product`; `find Admin -maxdepth 1 -type f -print`.
- Result: Goal contract validation PASS from both validators; no stale moved-document paths found; no document files remain in `Admin/`.
- New evidence: Current docs paths listed above.
- Decision: blocked only on ClickUp evidence comment creation.

## Risks and rollback

- Risks: Licensing claims may be misread as legal authorisation; mitigate by labelling legal decisions as Unknown and requiring rights-holder/legal approval.
- Risks: Admin Console scope may blend customer Account, Affiliate Portal, and internal staff tools; mitigate by explicit surface boundaries.
- Risks: License-key and entitlement operations are security-sensitive; mitigate by requiring architecture/security review before build.
- Rollback or recovery: Docs-only changes can be reverted or revised without affecting runtime code.

## Pause and escalation conditions

- Pause at `GATE_REVIEW` for user approval before ClickUp decomposition.
- Escalate any Bible translation availability, offline download right, sublicense, or pricing claim to Legal/Product before implementation.
- Escalate any architecture decision about key generation, entitlement service ownership, billing provider, identity provider, or audit retention to Software Architect/Security.

## Final evaluation

- Validator command: `python3 /Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-admin-console-brief.md`
- Validator result: PASS via both `/Users/m.oluwole/.agents/ai-development-team/scripts/validate_goal_contract.py` and repo `scripts/validate_goal_contract.py`.
- Independent verification result: Pending user/product gate review; this self-audit does not approve the brief.
- Terminal state: BLOCKED.
- Remaining failed or blocked criteria: C-007, ClickUp evidence comments could not be created because `_clickup_create_task_comment` returned `INVALID_ARGUMENT` for task `86ajnx548`.
- ClickUp final evidence comment: Pending. Proposed comment: `Admin Console project brief is gate-ready in docs/product/prds/SelahCue-Admin-Console-Project-Brief.md with audit docs/product/audits/Admin-Console-Project-Brief-Audit.md. Goal GOAL-admin-console-brief: product artefacts C-001..C-006 PASS; terminal BLOCKED only because ClickUp comment creation failed with INVALID_ARGUMENT. No implementation or delivery tasks created before user approval.`
