# SelahCue - Admin Console Project Brief Audit

Date: 2026-08-08  
Auditor: Product Manager self-audit for user gate  
Brief: `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md`  
Goal Contract: `docs/delivery/goals/GOAL-admin-console-brief.md`  
Status: Gate review - requires user approval and later independent review

> This is a product-readiness audit, not approval. The author of the brief cannot independently approve it. User/product owner review is required before ClickUp implementation work is created.

## 1. Verdict

**Ready with Conditions** for product owner review.  
**Not Ready** for implementation.

The brief is sufficient to decide whether the Admin Console should enter delivery planning. It is not sufficient to build because legal/licensing, architecture, security, and missing UI states/screens remain unresolved.

## 2. Coverage Check

| Required area | Coverage | Evidence |
|---|---|---|
| Current state | Covered | Brief section 2 |
| Users and jobs | Covered | Brief section 7 |
| Problem and goals | Covered | Brief sections 4-6 |
| Scope and non-goals | Covered | Brief sections 8-10 |
| Time-bound app license keys | Covered | ADM-FR-020..029, ADM-BR-001..004 |
| Bible translation catalogue | Covered | ADM-FR-040..044, ADM-BR-005..009 |
| Bible entitlements/downloads through SelahCue licensing | Covered | ADM-FR-050..058, ADM-FLOW-002/003 |
| Customers/subscriptions/support/settings | Covered | ADM-FR-010..014, 030..033, 060..063, 080..083 |
| Business rules/state transitions | Covered | Brief sections 12-13 |
| Permissions matrix | Covered | Brief section 16 |
| Data dictionary | Covered | Brief section 15 |
| Design alignment/gaps | Covered | Brief section 17 |
| Accessibility/responsive behaviour | Covered | Brief section 18 |
| Security/privacy/compliance | Covered | Brief section 19 |
| Analytics/events | Covered | Brief section 20 |
| Risks/open decisions | Covered | Brief sections 21-22 |
| ClickUp ticket creation | Correctly deferred | Brief section 24 and goal scope |

## 3. Requirements Coverage By User Request

| User request | Requirement coverage |
|---|---|
| "Admin console" | Surface boundary, IA, staff roles, customer/support/settings/subscription/license screens; ADM-FR-001..083 |
| "Handle licensing" | App license key lifecycle, subscriptions, customer/device activation, audit, support; ADM-FR-020..033 |
| "Bible licensing so users can download available versions through our licensing" | Translation catalogue, entitlements, protected download, offline/revocation/attribution/export/reporting rules; ADM-FR-040..058 |
| "Generate license keys for prospective users" | Prospect/trial key generation, finite duration, templates, expiry, copy/send, activation tracking; ADM-FR-020..029 |
| "With a set time/period" | ADM-FR-021, ADM-BR-002, ADM-FLOW-001 |
| "Build on Figma Admin work" | Existing shell/IA reused; missing screens and states explicitly called out in section 17 |

## 4. Conflicting Or Changed Evidence

| Item | Assessment | Disposition |
|---|---|---|
| Existing PRD says licensed translations are API-only/user-supplied later. User now asks for downloads through SelahCue licensing. | Product scope expansion, not a contradiction if framed as a later licensed-entitlement system. | Brief defines entitlement-gated post-activation download, not bundled redistribution. Requires PRD/update decision if approved. |
| Figma Admin Console includes `Licenses` nav, but handoff says Licenses screen is not designed. | Design gap. | Brief marks Licenses, Subscriptions, Support, Settings, Audit Log as required design follow-ups before build. |
| Existing Account portal has customer license-key placeholder, while Admin Console manages internal license keys. | Complementary surfaces. | Brief separates customer self-service Account from internal Admin Console. |
| Official API.Bible/Biblica/Tyndale source checks are current enough for brief, but legal terms can change. | Temporal/legal risk. | Brief labels licensing as decision-sensitive and requires re-confirmation before implementation/launch. |

## 5. Unresolved Decisions

These block implementation planning, not the product-review gate:

- Staff identity provider and MFA policy.
- Billing provider and source of truth for subscriptions/invoices/refunds.
- Approved pricing/plan tiers and prospect-trial defaults.
- Legal entity, customer terms, and privacy/compliance ownership.
- First licensed Bible translations SelahCue will pursue.
- Whether SelahCue resells translations directly, uses API.Bible-backed entitlements, negotiates direct publisher licences, or supports a mixed model.
- Offline grace/refresh/deletion rules for each licensed translation.
- Admin Console hosting/security model.
- Audit and operational-event retention.
- Staff roles allowed to extend keys, grant entitlements, impersonate, refund, or export reports.

## 6. Risks And Controls

| Risk | Severity | Control in brief |
|---|---|---|
| Shipping or promising copyrighted translations without permission | High | Legal-status gates, unavailable states, rights-holder approval dependency |
| License keys copied/abused | High | Sensitive key handling, device/seat limits, revocation, audit, security review |
| Offline use conflicts with publisher revocation/deletion duties | High | Per-translation offline policy and legal/architecture approval |
| Staff over-grants access during support pressure | Medium | Role matrix, reason capture, audit, approval constraints |
| Admin scope sprawl delays product | Medium | Slice A foundation separated from automation/reporting |
| Missing UI states cause build ambiguity | Medium | Explicit screen/state design backlog |
| Commenting evidence to ClickUp failed in this session | Low for product artefact; process issue | Goal records the connector failure; final handoff will include pending ClickUp update text |

## 7. Recommended Refinements Before Build

1. Product owner confirms Admin Console scope and Slice A priority.
2. Legal/Product choose the first Bible licensing route and the initial target translation list.
3. Architect drafts an ADR for Account/Billing/Entitlement/License-key services.
4. Security drafts a threat model for Admin staff access, impersonation, key generation, entitlement downloads, and audit retention.
5. UI/UX designs the missing Licenses, Subscriptions, Support, Settings, Audit Log, and non-default states.
6. Product Manager updates or supersedes affected PRD sections after approval.
7. Delivery Manager creates or updates ClickUp epics/stories only after approval.

## 8. Gate Recommendation

Ask the product owner to approve, reject, or revise the brief before delivery planning.

Recommended approval wording:

> Approve the Admin Console project brief for delivery planning, with Slice A as the first release and legal/security/architecture/design follow-up gates required before implementation.

Without approval, no ClickUp implementation work should be created.
