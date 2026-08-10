# SelahCue - Admin Console Project Brief

Version: 0.1 (gate draft)  
Date: 2026-08-08  
Owner: Product Manager  
Status: Gate review - not approved for implementation  
Goal Contract: `docs/delivery/goals/GOAL-admin-console-brief.md`  
ClickUp Build Control: `https://app.clickup.com/t/86ajnx548`

> This brief is product and business-analysis due diligence, not legal advice. Copyrighted Bible translation availability, offline download rights, sublicensing, pricing, territories, and reporting obligations must be confirmed by qualified counsel and the relevant rights holders before ship.

## 1. Evidence Labels

- **Verified:** directly observed in repository artefacts, Figma metadata, ClickUp, or official source pages.
- **Inferred:** supported by verified evidence but not directly observed as implemented behaviour.
- **Assumed:** product premise used to make the brief concrete; needs owner confirmation.
- **Unknown:** unresolved and decision-relevant.

## 2. Current State

| Fact | Label | Evidence |
|---|---|---|
| SelahCue is currently defined as an offline-first desktop/mobile church presentation product with public-domain Bible bundles and later licensed-translation paths. | Verified | `product/PRODUCT-BRIEF.md`, `docs/product/prds/SelahCue-PRD.md` |
| The current PRD states: MVP bundles public-domain Bible translations only; licensed translations are API-only/user-supplied later. | Verified | `docs/product/prds/SelahCue-PRD.md` CON-3, FR-033, FR-034, FR-146 |
| Licensed translations dossier says major copyrighted translations can be offline after entitlement-gated activation only where a licence permits it, using an encrypted app-locked store with refresh/revocation/export controls. | Verified | `docs/research/LICENSED-TRANSLATIONS.md` section 4b; `docs/architecture/adr/ADR-0017-translation-providers.md` |
| API.Bible official docs still present commercial Pro plans, additional copyright Bible fees, FUMS/reporting expectations, cache guidance, and terms covering offline storage with DRM/security obligations. | Verified 2026-08-08 | [API.Bible account plans](https://docs.api.bible/quick-start/create-your-account/), [API.Bible FAQs](https://docs.api.bible/common-questions/), [API.Bible terms](https://api.bible/terms-and-conditions) |
| Biblica official permissions pages require written permission/licensing for app or website use that does not qualify as non-commercial Express Licensing; products still in development are generally not licensed. | Verified 2026-08-08 | [Biblica permissions](https://www.biblica.com/permissions/), [Biblica permission request form](https://www.biblica.com/permission-request-form/) |
| Tyndale permissions pages require permission/licence paths for commercial NLT use beyond limited quotation/fair-use policies. | Verified 2026-08-08 | [Tyndale permissions](https://www.tyndale.com/permissions) |
| A Figma Admin Console proposal exists in file `SYQn5hFY8YVQKm3c6rw0eJ`, page/node `518:124`, with sidebar IA including Overview, Customers, Users, Affiliates, Subscriptions, Licenses, Support, and Settings. | Verified | Figma metadata pull, `docs/design/ADMIN-CONSOLE-HANDOFF.md` |
| The Admin design handoff explicitly says Subscriptions, Licenses, Support, and Settings are planned destinations, not designed screens. | Verified | `docs/design/ADMIN-CONSOLE-HANDOFF.md` section 7 |
| There is no implemented Admin Console or affiliate/backend/admin surface yet. | Verified | `docs/design/ADMIN-CONSOLE-HANDOFF.md`; repo search found no admin backend implementation |
| The marketing/account design includes a customer Account dashboard with subscription, billing, license key, device list, and invoices. | Verified | `docs/design/MARKETING-SITE-HANDOFF.md` |
| Final staff roles, commercial model, billing provider, identity provider, publisher contracts, and exact translation catalogue are not yet approved. | Unknown | No approved decision artefact found |

## 3. Surface Boundary

The Admin Console is an internal SelahCue staff back-office. It is not the local desktop presenter, not the customer Account portal, and not the Affiliate Portal.

| Surface | Audience | Purpose | Relationship |
|---|---|---|---|
| SelahCue desktop app | Church operators and local admins | Present services, control outputs, use local/entitled content | Remains authoritative for live presentation state |
| Customer Account portal | Customer org owners/admins | Manage their own plan, devices, invoices, license key, and purchased Bible entitlements | External customer self-service |
| Affiliate Portal | Affiliates | Manage referrals, links, payouts, resources | External partner self-service |
| Admin Console | SelahCue staff | Manage customers, subscriptions, app license keys, Bible entitlements/licences, support, compliance, staff access, reporting | Internal source for commercial/support operations |

## 4. Problem Statement

SelahCue needs an internal operations console before paid distribution, trial outreach, and SelahCue-managed Bible translation licensing can scale. Staff need to issue time-bound access to prospective users, support customers, enforce device and seat limits, revoke compromised or expired access, manage which Bible translations a customer can download through SelahCue's licences, and keep auditable evidence for billing, support, security, and rights-holder compliance.

Without an Admin Console, the team would rely on ad hoc manual keys, spreadsheet tracking, and unclear licence provenance. That would create security risk, poor customer support, and a high chance of violating publisher conditions for copyrighted Bible content.

## 5. Goals

- **ADM-G-001:** Let authorised SelahCue staff issue, inspect, extend, revoke, and convert time-bound app license keys for prospects, pilots, churches, and paid customers.
- **ADM-G-002:** Let authorised staff manage customer organisations, users, plans, seats, devices, subscriptions, invoices, and support context from one internal record.
- **ADM-G-003:** Let authorised staff manage the Bible translation catalogue and customer translation entitlements that allow lawful in-app download where SelahCue has the required licence.
- **ADM-G-004:** Preserve SelahCue's offline-first promise: once a customer has valid activated entitlements, Sunday operation should not depend on the Admin Console being online.
- **ADM-G-005:** Make licensing, entitlement changes, impersonation, refunds, support actions, and destructive operations auditable and permission-scoped.
- **ADM-G-006:** Provide a clear product foundation for architecture, design, backend, frontend, security, legal, QA, and support to decompose after approval.

## 6. Success Measures

| ID | Measure | Target |
|---|---|---|
| ADM-MET-001 | Time to issue a prospect trial license key | Staff can create and copy/send a valid time-bound key in <= 2 minutes from a customer/prospect record |
| ADM-MET-002 | Licence-key recovery | Staff can find any key by key prefix, customer, email, status, or date range in <= 10 seconds for datasets up to 100k keys |
| ADM-MET-003 | Entitlement accuracy | A customer sees only Bible translations they are entitled to download; revoked/expired entitlements stop new downloads within the approved revocation SLA |
| ADM-MET-004 | Offline Sunday continuity | A valid already-activated desktop can continue using previously downloaded licensed translations while offline for the licence-approved grace period |
| ADM-MET-005 | Audit coverage | 100% of security-sensitive actions have an immutable audit record with actor, target, before/after, timestamp, reason, and result |
| ADM-MET-006 | Support resolution | Staff can see subscription, devices, license state, entitlement state, and recent audit/support history on one customer detail view |

## 7. Users And Jobs

| User | Jobs to be done |
|---|---|
| SelahCue Owner/Admin | Configure commercial operations, staff roles, licence policies, translation catalogue, and sensitive approvals |
| Sales/Partnership Staff | Generate prospect/demo/pilot keys, track expiry, convert trials, and understand entitlement limitations before promising availability |
| Support Staff | Diagnose customer activation, device, subscription, and translation-download issues without unsafe database access |
| Finance Staff | Review subscription state, invoices, refunds, discounts, and paid translation entitlement billing |
| Licensing/Compliance Staff | Track publisher agreements, permitted territories, attribution, reporting, download/caching rules, and customer entitlements |
| Security/Admin Staff | Manage staff access, revoke keys/devices, audit impersonation and destructive actions, and investigate suspicious activity |
| Customer Organisation Owner | Indirect user: receives keys/entitlements and expects activation/downloads to work predictably |

## 8. In Scope

- Staff authentication and role-based access for internal Admin users.
- Customer organisations, customer users, contacts, plans, subscription state, invoices, and device activations.
- Time-bound SelahCue app license-key generation for prospects, demos, pilots, trials, churches, paid plans, and special grants.
- License-key lifecycle: draft, issued, activated, expiring, expired, revoked, suspended, converted, and archived.
- Bible translation catalogue for versions SelahCue is authorised to offer.
- Bible entitlement lifecycle for customers, plans, subscriptions, devices, territories, expiry, revocation, and download state.
- Admin support workflows for activation/download failures.
- Staff permissions, approval gates, destructive confirmations, impersonation controls, and append-only audit.
- Operational reporting for licenses, entitlements, downloads, expiry, revocation, and rights-holder usage evidence.
- Design brief for the missing Admin Console screens: Licenses, Subscriptions, Support, Settings, and states.

## 9. Non-goals

- The Admin Console does not control live presentation outputs.
- The Admin Console does not replace the local desktop app's Administrator role for venue devices/roles during services.
- The Admin Console does not authorize bundling copyrighted Bible translations in the installer.
- The Admin Console does not allow staff to upload or distribute copyrighted Bible text without a recorded SelahCue licence or explicit legal approval.
- The Admin Console does not provide legal advice to customers or represent that a customer has CCLI or publisher rights outside the SelahCue-managed entitlement.
- The first release does not require automated publisher contract negotiation, affiliate payout automation, or full self-service customer purchase flow unless separately approved.
- This brief does not create ClickUp implementation tasks; that happens only after product gate approval.

## 10. Release Slice

### Slice A - Admin Licensing Foundation

The recommended first Admin release should include:

- Staff auth/RBAC with Owner, Admin, Support, Finance, Licensing, and Read-only roles.
- Customer organisation records and customer detail view.
- App license-key generation, issuance, activation tracking, expiry, revocation, and conversion notes.
- Bible translation catalogue records with legal status fields and "not available" states.
- Customer Bible entitlements with manual grant/revoke and desktop activation/download contract.
- Audit log for all sensitive actions.
- Support view for customer activation/download issues.
- Required design states for Licenses, Subscriptions, Support, and Settings.

### Slice B - Commercial Automation

- Billing-provider integration.
- Automated plan/seat/device enforcement.
- Customer self-service Account portal integration.
- Automated renewal/cancel/refund state sync.
- Email notifications for trial expiry, renewal, and entitlement changes.

### Slice C - Licensing Operations And Reporting

- Publisher-specific reporting exports.
- Translation-specific usage dashboards.
- API.Bible/FUMS or equivalent provider reporting reconciliation.
- Licence contract renewal workflows.
- Rights-holder audit package generation.

## 11. Functional Requirements

### Staff Access And Safety

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ADM-FR-001 | Staff sign in to the Admin Console through an approved identity provider. | Unauthenticated users cannot access any Admin route; active sessions expire per policy; failed logins/rate limits are surfaced without revealing account existence. |
| ADM-FR-002 | Staff roles are enforced server-side. | Each Admin route/action checks the server-side role; client-hidden buttons are not sufficient; unauthorised requests return a non-success result and are audited. |
| ADM-FR-003 | Staff role matrix supports Owner, Admin, Support, Finance, Licensing, and Read-only roles. | The permissions matrix in section 16 is implemented; role changes take effect on the next request or sooner; no role can grant itself higher access. |
| ADM-FR-004 | Sensitive actions require reason capture. | Revoking a key, extending a key, granting a paid entitlement, disabling a customer, impersonating, refunding, or changing licence terms requires a typed reason stored in audit. |
| ADM-FR-005 | Destructive or high-risk actions require confirmation. | High-severity actions use a confirmation dialog naming the exact consequence; selected actions require type-to-confirm; default focus is the safe action. |
| ADM-FR-006 | Impersonation is controlled and visibly labelled. | Only authorised roles can impersonate; impersonated sessions show a persistent banner; all viewed/changed customer records during impersonation are audited. |

### Customers And Organisations

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ADM-FR-010 | Staff can create and manage customer organisation records. | Organisation name, primary contact, billing contact, country, timezone, plan, status, seats, devices, and notes are captured with validation. |
| ADM-FR-011 | Staff can search/filter customers. | Search supports organisation name, contact email, key prefix, status, plan, country, and date ranges; empty/filtered-empty states are distinct. |
| ADM-FR-012 | Customer detail aggregates commercial and support context. | Detail view shows subscription, license keys, device activations, Bible entitlements, invoices, support tickets, internal notes, and audit timeline. |
| ADM-FR-013 | Internal notes are permissioned and auditable. | Staff can add append-only internal notes; edits/deletions are disallowed or versioned; notes never appear to customers. |
| ADM-FR-014 | Customer statuses are explicit. | Supported statuses include Prospect, Trial, Active, Past Due, Suspended, Cancelled, Churned, and Archived; invalid transitions are blocked. |

### App License Keys

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ADM-FR-020 | Authorised staff can generate time-bound SelahCue app license keys. | Staff choose customer/prospect, key type, start time, duration/end date, plan/features, seats/devices, territory, notes, and owner; system returns a masked key with copy/send action. |
| ADM-FR-021 | License keys support finite validity periods. | Keys can be valid for hours, days, months, or a custom date range; expiry is calculated in a specified timezone and stored as UTC. |
| ADM-FR-022 | License keys can be limited by seats and device activations. | Activation beyond seat/device limits is rejected with a support-friendly reason; staff can view and deactivate devices. |
| ADM-FR-023 | License keys can grant feature scopes. | Staff can grant Free, Pro, Church, Trial, Internal, or Custom feature scopes; the desktop receives only signed claims it is allowed to enforce. |
| ADM-FR-024 | License-key activation is tracked. | First activation records customer, device fingerprint, app version, platform, IP/country where legally allowed, timestamp, and activation result. |
| ADM-FR-025 | License keys can be extended, revoked, suspended, or converted. | Each action requires permission and reason; desktop entitlement response changes accordingly; existing offline grace follows approved policy. |
| ADM-FR-026 | Expiring keys are visible. | Staff can filter keys expiring in 7/14/30 days; customers/prospects can be notified if notification scope is approved. |
| ADM-FR-027 | Key values are protected. | Full key is shown only immediately after generation or through an approved recovery flow; later displays show prefix/suffix only; keys are never logged in full. |
| ADM-FR-028 | Bulk key generation is gated. | Bulk generation requires Owner/Admin permission, upload validation, preview, per-row result reporting, and a hard maximum per run. |
| ADM-FR-029 | Revoked or expired keys cannot activate new devices. | Activation requests for revoked/expired keys return a clear denial reason; the event is audited; no paid feature token is issued. |

### Subscriptions, Plans, And Billing Context

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ADM-FR-030 | Staff can view subscription state. | Customer detail shows plan, billing cycle, trial end, renewal date, payment status, past-due state, cancellation date, and billing provider reference if available. |
| ADM-FR-031 | Staff can record manual commercial arrangements. | For pilots or offline deals, staff can attach contract notes, approved duration, approved features, and owner approval evidence. |
| ADM-FR-032 | Plan changes are auditable. | Changing a plan records previous plan, new plan, effective date, actor, reason, and customer notification state. |
| ADM-FR-033 | Refund/cancel controls are permissioned. | Only Finance/Admin/Owner can initiate refund/cancel actions; actions require confirmation, reason, and billing-provider result or manual pending state. |

### Bible Translation Catalogue

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ADM-FR-040 | Admin Console maintains a translation catalogue. | Each translation record includes code, name, edition, language, copyright class, rights holder, source/provider, legal status, allowed territories, attribution text, and availability status. |
| ADM-FR-041 | Catalogue distinguishes public-domain/open and copyrighted translations. | Public-domain/open translations are marked separately from licensed/copyrighted translations; copyrighted translations cannot be marked "Available to customers" without legal approval fields. |
| ADM-FR-042 | Translation records capture licence constraints. | Fields cover offline allowed, cache refresh interval, deletion/revocation SLA, device limits, export/print caps, attribution display, reporting requirement, territory, effective date, expiry/renewal date, and contract owner. |
| ADM-FR-043 | Translation availability can be staged before publishing. | Draft/Review/Approved/Published/Suspended/Retired states exist; only approved translations can be granted to customers. |
| ADM-FR-044 | Unavailable translations are honest in customer-facing surfaces. | If a translation is not licensed, expired, territory-blocked, quota-exhausted, or provider-down, customer/app surfaces show a clear unavailable reason instead of silently omitting or failing empty. |

### Bible Entitlements And Downloads

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ADM-FR-050 | Authorised staff can grant a customer entitlement to a licensed Bible translation. | Staff select customer, translation, plan/license basis, start/end date, seats/devices, territory, offline allowance, and reason; invalid grants are blocked if translation is not approved. |
| ADM-FR-051 | Entitlements control in-app downloads through SelahCue licensing. | Desktop apps can download only translations included in an active entitlement and only under the translation's recorded licence constraints. |
| ADM-FR-052 | Entitlement-gated downloads are not bundles. | Licensed text is not included in the installer; it is downloaded after activation into an encrypted, app-locked local store where the licence allows offline storage. |
| ADM-FR-053 | Entitlements can be revoked or expire. | Revocation/expiry prevents new downloads and triggers the approved deletion/disable flow for local stores within the recorded SLA. |
| ADM-FR-054 | Offline use follows approved grace and refresh rules. | Already-activated desktops can use downloaded licensed translations offline only within licence-approved grace/refresh limits; expired or revoked entitlements are handled on reconnect or policy check. |
| ADM-FR-055 | Attribution is enforced per translation. | Desktop content responses include the required attribution/copyright line; slide/export rendering follows the translation record. |
| ADM-FR-056 | Export respects licence constraints. | Export/print/copy of licensed translations is blocked, limited, or watermarked according to the translation record; public-domain content exports normally. |
| ADM-FR-057 | Usage/reporting events are captured where required. | When a provider/licence requires reporting, display/download/reportable events are captured with enough metadata to generate the required report without exposing unnecessary customer data. |
| ADM-FR-058 | Download failures are supportable. | Failed downloads show provider, entitlement, territory, device, quota, network, refresh, or revocation cause; support can see the same reason in Admin. |

### Support Operations

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ADM-FR-060 | Support can triage activation issues. | Support view shows key status, activation attempts, device count, expiry, clock-skew/tamper flags if implemented, and last denial reason. |
| ADM-FR-061 | Support can triage Bible download issues. | Support view shows entitlement status, translation status, provider status, download attempts, cache refresh state, and revocation/deletion deadlines. |
| ADM-FR-062 | Staff can create support cases or link external tickets. | Support items can link customer, key, device, entitlement, invoice, and audit entries; unresolved cases are visible on customer detail. |
| ADM-FR-063 | Staff can perform safe remediation actions. | Resend activation, deactivate a device, refresh entitlement, retry provider sync, and extend a trial are available only to roles with permission and are audited. |

### Audit, Reporting, And Compliance

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ADM-FR-070 | Admin actions have append-only audit records. | Audit captures actor, role, action, target type/id, before/after where safe, reason, timestamp, result, request id, and source surface. |
| ADM-FR-071 | Audit log is searchable but tamper-resistant. | Staff can filter audit by customer, actor, action, target, result, date range; records cannot be edited/deleted through Admin UI. |
| ADM-FR-072 | Licence reporting exports are available. | Licensing/Admin roles can export approved reporting packages for translation usage/downloads within date ranges and provider requirements. |
| ADM-FR-073 | Sensitive exports are permissioned. | Customer data, audit exports, licence reports, and financial reports require explicit role permission and are themselves audited. |
| ADM-FR-074 | Compliance warnings are surfaced before publication. | Admin cannot publish a translation or entitlement if required legal fields, attribution, territory, expiry, offline policy, or reporting fields are missing. |

### Settings And Operational Configuration

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ADM-FR-080 | Admin settings manage staff, roles, and policy defaults. | Owners/Admins can manage staff invitations, role assignments, trial duration presets, key expiry notification windows, and destructive-action policies. |
| ADM-FR-081 | Licence-key templates can be configured. | Staff can use approved templates for 7-day demo, 30-day trial, event pilot, annual church, and internal QA keys; templates specify defaults and limits. |
| ADM-FR-082 | Translation provider settings are separated from customer grants. | Provider credentials/contracts are managed by authorised roles; Support can see provider status without seeing secrets. |
| ADM-FR-083 | Secrets are never exposed in plaintext after entry. | API keys, signing keys, billing secrets, and provider credentials use approved secret custody; UI shows status/fingerprint only. |

## 12. Business Rules

| ID | Rule | Source/owner |
|---|---|---|
| ADM-BR-001 | A SelahCue app license key is not the same as a Bible translation entitlement. A customer may have one without the other. | Product |
| ADM-BR-002 | A prospect/demo key must always have a finite end date. | Product/Commercial |
| ADM-BR-003 | No key generation, extension, revocation, refund, paid entitlement grant, or impersonation may occur without an audit reason. | Product/Security |
| ADM-BR-004 | Full license-key secrets are treated as sensitive and must not be stored or displayed in recoverable plaintext outside approved secret/hash design. | Security |
| ADM-BR-005 | Copyrighted Bible text must never ship in the app installer unless legal approves a specific redistribution arrangement. | Verified from existing PRD/licensing posture |
| ADM-BR-006 | "Download through SelahCue licensing" means entitlement-gated post-activation download into an app-locked protected store where the licence permits it, not a public module download. | Existing licensing dossier/ADR |
| ADM-BR-007 | A translation cannot be made customer-available until its rights holder, legal status, territory, attribution, offline/cache/export/reporting constraints, and approval owner are recorded. | Product/Legal |
| ADM-BR-008 | Entitlement revocation prevents new downloads immediately and applies stored-content deletion/disable behaviour according to the recorded licence terms. | Product/Legal/Architecture |
| ADM-BR-009 | If a licence requires usage reporting, display/download/reporting hooks are mandatory before the entitlement can be published. | Product/Legal |
| ADM-BR-010 | Customer-facing surfaces must not imply that unavailable copyrighted translations are included unless the customer's active entitlement grants them. | Product/Legal |
| ADM-BR-011 | Staff support actions should restore access only when the customer's commercial/licensing state permits it. | Support/Finance/Legal |
| ADM-BR-012 | Offline Sunday continuity is a product goal, but it cannot override publisher revocation, territory, refresh, deletion, or device-limit terms. | Product/Legal |

## 13. State Models

### Customer State

`Prospect -> Trial -> Active -> Past Due -> Suspended -> Cancelled -> Churned -> Archived`

- Prospect may receive demo/trial keys.
- Trial may convert to Active or expire to Prospect/Churned.
- Past Due may retain limited grace depending on billing policy.
- Suspended blocks new paid activations and new licensed downloads.
- Archived is read-only except Owner/Admin restoration.

### App License Key State

`Draft -> Issued -> Activated -> Expiring -> Expired -> Converted`

Exceptional states:

- `Revoked`: manually invalidated; no new activation.
- `Suspended`: temporarily disabled pending payment/support/security.
- `Archived`: retained for audit/search, not usable.

### Bible Translation Catalogue State

`Draft -> Legal Review -> Approved -> Published -> Suspended -> Retired`

- Draft/Legal Review cannot be granted to customers.
- Approved can be configured and tested internally.
- Published can be granted under policy.
- Suspended blocks new grants/downloads.
- Retired remains visible in history/reporting.

### Customer Translation Entitlement State

`Pending -> Active -> Expiring -> Expired`

Exceptional states:

- `Revoked`: removed by staff or contract requirement.
- `Territory Blocked`: customer/device territory not allowed.
- `Provider Unavailable`: upstream/provider issue.
- `Refresh Required`: offline content must refresh before further use.
- `Deletion Pending`: local protected store must remove/disable content by SLA.

## 14. User Journeys

### ADM-FLOW-001 - Issue a prospect trial key

1. Sales opens Customers or creates a Prospect.
2. Sales selects Generate license key.
3. Sales chooses a trial template, duration, features, seats/devices, territory, and reason.
4. Admin generates a masked key and records the full value only through approved secret handling.
5. Sales copies/sends the key.
6. Prospect activates the desktop app.
7. Activation appears on the customer timeline.

Acceptance:

- Key is finite.
- Activation beyond policy is denied.
- Expiry and upcoming-expiry filters include the key.
- All steps are audited.

### ADM-FLOW-002 - Grant a Bible translation entitlement

1. Licensing/Admin opens a customer detail.
2. Staff selects Add Bible entitlement.
3. Staff chooses a Published translation and confirms terms/territory/offline policy.
4. System validates the customer's plan, contract, territory, device count, and expiry.
5. Entitlement becomes Active.
6. Desktop app sees the translation as available and downloads it only after activation.
7. Desktop stores it in the protected local store and renders attribution.

Acceptance:

- Unapproved translations cannot be granted.
- Download without active entitlement is denied.
- Attribution and export limits follow the translation record.
- Revocation blocks new downloads and initiates deletion/disable workflow.

### ADM-FLOW-003 - Support a failed Bible download

1. Customer reports a download failure.
2. Support searches by customer, key prefix, device, or email.
3. Support opens entitlement/download diagnostics.
4. Admin shows whether the cause is key expiry, no entitlement, provider issue, quota, territory, offline refresh, device limit, or revoked translation.
5. Support performs a permitted remediation or escalates to Licensing/Finance/Security.

Acceptance:

- Support can diagnose without seeing provider secrets.
- Remediation cannot violate commercial/licensing state.
- Escalation reason and outcome are audited.

### ADM-FLOW-004 - Revoke compromised access

1. Admin/Security finds a key or device.
2. Staff selects Revoke.
3. UI requires consequence review, type-to-confirm where configured, and reason.
4. System blocks new activations/downloads and invalidates active sessions/tokens according to architecture.
5. Customer timeline and audit log show revocation.

Acceptance:

- Revocation cannot be performed by unauthorised roles.
- Desktop receives accurate denial/refresh state on next policy check.
- Offline grace follows approved legal/product policy.

## 15. Data Dictionary

| Entity | Key fields | Sensitivity | Owner |
|---|---|---|---|
| StaffUser | id, name, email, role, status, MFA/IdP reference, last active | Personal data, security-sensitive | Admin/Security |
| CustomerOrg | id, name, country, timezone, contacts, status, plan, notes | Customer data | Product/Support |
| CustomerUser | id, org id, email, role, status | Personal data | Customer/Support |
| Subscription | customer id, plan, billing status, renewal, provider ref, invoices | Financial/customer data | Finance |
| AppLicenseKey | key id, masked prefix/suffix, hash/fingerprint, type, features, start/end, seats/devices, status, reason | Highly sensitive | Product/Security |
| DeviceActivation | device id/fingerprint, platform, app version, activated at, last seen, status | Security/customer data | Support/Security |
| TranslationCatalogueItem | code, edition, rights holder, source/provider, legal status, licence constraints, attribution, territories, dates | Legal/commercial data | Licensing/Legal |
| TranslationEntitlement | customer, translation, start/end, devices, territory, offline policy, status | Legal/customer data | Licensing/Support |
| DownloadEvent | customer, device, translation, version, result, reason, timestamp | Operational/license-reporting data | Licensing/Support |
| UsageReportEvent | translation, action, display/download context, customer/org grouping, timestamp | Licence-reporting data | Licensing |
| SupportCase | issue, linked customer/key/device/entitlement, status, owner, notes | Customer/support data | Support |
| AuditEvent | actor, role, action, target, before/after, reason, result, timestamp | Security/compliance | Security |

Retention periods are Unknown and must be approved by Product, Legal, and Security before implementation.

## 16. Permissions Matrix

| Action | Owner | Admin | Support | Finance | Licensing | Read-only |
|---|---:|---:|---:|---:|---:|---:|
| View customers | yes | yes | yes | yes | yes | yes |
| Create/edit customer | yes | yes | limited | limited | no | no |
| Generate prospect/trial key | yes | yes | limited | no | no | no |
| Generate paid/custom key | yes | yes | no | yes | no | no |
| Extend/revoke key | yes | yes | limited | limited | no | no |
| View full key after creation | no | no | no | no | no | no |
| Deactivate device | yes | yes | yes | no | no | no |
| View subscriptions/invoices | yes | yes | yes | yes | no | yes |
| Refund/cancel subscription | yes | limited | no | yes | no | no |
| Manage translation catalogue | yes | no | no | no | yes | no |
| Grant/revoke Bible entitlement | yes | limited | no | no | yes | no |
| View entitlement diagnostics | yes | yes | yes | no | yes | yes |
| Export licence reports | yes | no | no | no | yes | no |
| Impersonate customer | yes | limited | limited | no | no | no |
| Manage staff roles | yes | limited | no | no | no | no |
| Export audit log | yes | no | no | no | no | no |

"limited" means the action requires additional policy constraints, approval, or scoped access before build.

## 17. Screen And IA Requirements

The existing Figma/Admin IA is the baseline shell:

- Sidebar: Overview, Customers, Users, Affiliates, Subscriptions, Licenses, Support, Settings.
- Top bar: page title, global search, notifications.
- Shared patterns: KPI cards, tables, filters, status chips, row actions, pagination, dialogs, cards, segmented controls, fields, toggles.

### Required New Or Expanded Screens

| Screen | Purpose | Design status |
|---|---|---|
| Admin Overview | Operational KPIs for customers, revenue, trials, expiring keys, entitlement/download health | Default designed; update KPIs for licensing |
| Customers List | Customer search/filter/table | Default designed |
| Customer Detail | Customer commercial/support context | Default designed; must add license keys and Bible entitlements sections |
| Users List | Customer users | Default designed |
| Subscriptions | Plan, billing, invoices, past due, cancellation/refund operations | Planned destination; needs design |
| Licenses | App license keys, Bible translation catalogue, customer entitlements, download diagnostics | Planned destination; needs design |
| Support | Cases, activation failures, download failures, escalation queues | Planned destination; needs design |
| Settings | Staff roles, IdP, key templates, licence policies, provider settings, audit retention | Planned destination; needs design |
| Audit Log | Searchable immutable security/compliance activity | Not explicitly designed; required |

### Required States Before Build

- Loading, empty, filtered-empty, error, retry, and pagination states for every table.
- Row hover/focus, sort-active, row action menu, and keyboard operation.
- Form states: default, focus, validation error, disabled, submitting, success, server error.
- Destructive confirmations for revoke key, suspend customer, cancel subscription, refund, deactivate device, revoke entitlement, suspend translation, and impersonate.
- Permission-denied states for every route and action.
- Provider-down, quota-exhausted, territory-blocked, expired entitlement, and refresh-required states for Bible downloads.
- Audit export success/failure and empty states.
- Notification panel states.

## 18. Accessibility And Responsive Behaviour

- Desktop-first internal tool. Target >=1280 px as designed.
- 1024-1279 px: collapse sidebar to icon rail; detail side panels drop below main content.
- <1024 px: Admin Console may degrade to drawer + horizontally scrollable tables; Affiliate Portal remains mobile-friendly separately.
- Tables use real table semantics, sortable header `aria-sort`, labelled action menus, and clear keyboard focus.
- Dialogs use `role="dialog"`, focus trap, `aria-modal`, labelled title, Esc cancel, and safe-action initial focus.
- Touch targets for any tablet use should be >=40 px; customer Account/Affiliate Portal should use >=44 px.
- Status cannot rely on colour alone; use label + colour.
- Audit/log/license-key data must be readable with keyboard and screen readers.

## 19. Security, Privacy, And Compliance

- Admin Console is high-risk because it can grant paid access, licensed Bible content, and support impersonation.
- All Admin traffic must use authenticated encrypted transport.
- Staff accounts require MFA or equivalent IdP policy before production.
- Signing/key-generation architecture must be designed by Architecture/Security; this brief does not prescribe cryptographic implementation.
- Admin Console availability must not be required for live Sunday operation of already-activated local desktop capabilities.
- License-key and provider secrets must never appear in plaintext logs, analytics, or support bundles.
- Customer personal data, billing data, support notes, device data, and audit records require retention/deletion policy approval.
- Licensed Bible text handling must enforce attribution, export/print restrictions, territory/device limits, revocation/deletion, and usage reporting where required.
- Legal pages, customer terms, and support scripts must avoid promising translations until entitlement availability is confirmed.

## 20. Analytics And Operational Events

| Event | Purpose |
|---|---|
| admin_customer_created | Customer operations |
| admin_license_key_generated | Trial/sales operations and abuse monitoring |
| admin_license_key_activated | Activation metrics and support |
| admin_license_key_revoked | Security/compliance |
| admin_entitlement_granted | Bible licensing operations |
| admin_entitlement_revoked | Bible licensing/compliance |
| admin_translation_published | Catalogue governance |
| admin_translation_suspended | Catalogue governance |
| admin_download_denied | Support and entitlement diagnostics |
| admin_impersonation_started | Security audit |
| admin_sensitive_export_created | Compliance audit |

Events must not include full license keys, provider secrets, or full Bible text.

## 21. Risks

| ID | Risk | Mitigation |
|---|---|---|
| ADM-RISK-001 | Staff may assume a translation can be offered before publisher approval. | Require legal-status gates and unavailable states in catalogue. |
| ADM-RISK-002 | Time-bound keys may be copied or abused. | Hash/fingerprint keys, device limits, audit, revoke/suspend, rate limiting, and security review. |
| ADM-RISK-003 | Offline-first promise can conflict with revocation/deletion obligations. | Record per-translation offline policy and require architecture/legal approval for grace periods. |
| ADM-RISK-004 | Support may over-grant access to resolve urgent customer issues. | Role limits, reason capture, audit, approval workflows, and support playbooks. |
| ADM-RISK-005 | Admin Console scope can sprawl into billing, affiliate, account, support, and compliance all at once. | Ship Slice A first; keep billing automation and reporting as later slices. |
| ADM-RISK-006 | Impersonation can expose customer data or create untraceable changes. | Banner, explicit permission, audit, time-bound session, and security review. |
| ADM-RISK-007 | Publisher terms may change. | Treat official source checks as time-bound; re-confirm before implementation and before launch. |

## 22. Open Decisions

| ID | Decision | Recommendation | Owner |
|---|---|---|---|
| ADM-OD-001 | Is the Admin Console web-hosted, private VPN-only, or self-hosted internal? | Web-hosted internal with strict staff auth, unless architecture/security chooses otherwise. | Product + Architecture + Security |
| ADM-OD-002 | Which identity provider handles staff auth? | Use a managed IdP with MFA and audit support. | Security |
| ADM-OD-003 | Which billing provider is source of truth? | Decide before automated subscription/refund work. | Product + Finance |
| ADM-OD-004 | What paid/free plan tiers exist and what do they include? | Reconcile marketing placeholder tiers with approved pricing. | Product |
| ADM-OD-005 | What is the default prospect trial duration? | Provide templates, but owner must approve defaults. | Product/Sales |
| ADM-OD-006 | Can Support extend keys, and by how much? | Allow limited extensions with reason; larger changes require Admin/Owner. | Product + Support |
| ADM-OD-007 | Which Bible translations will SelahCue actively license first? | Start with translations whose rights path is clear and commercially viable; do not promise NIV/TPT/etc. until direct approval. | Product + Legal |
| ADM-OD-008 | What offline grace period is allowed for licensed translations after entitlement expiry/revocation? | Must be translation/provider-specific and legal-approved. | Legal + Architecture |
| ADM-OD-009 | What staff can export licence/usage reports? | Limit to Licensing/Owner. | Security + Legal |
| ADM-OD-010 | What retention period applies to audit logs and activation/download events? | Define with Legal/Security before build. | Legal + Security |

## 23. Requirement Traceability

| Admin area | Existing SelahCue trace |
|---|---|
| Bible entitlement/download licensing | PRD FR-033, FR-034, FR-035, FR-146; ADR-0017; licensing dossier |
| App/customer license keys | Marketing Account handoff placeholder license-key card; new Admin requirements ADM-FR-020..029 |
| Customer/user administration | Admin handoff Customers/Users; PRD FR-147/148 local app admin parallel |
| Audit/security | PRD FR-150, NFR-017, NFR-027; Admin requirements ADM-FR-070..074 |
| Provider/secret configuration | PRD FR-134, FR-152; Admin requirements ADM-FR-080..083 |
| Support operations | Admin handoff planned Support destination; new Admin requirements ADM-FR-060..063 |
| Design system and states | Admin handoff sections 2-5; Figma Admin Console node `518:124` |

## 24. Readiness Summary

This brief is ready for product review, not implementation.

Ready:

- Problem, users, goals, scope, non-goals, and success measures are explicit.
- User-requested capabilities are covered: time-bound app license keys, Bible licensing, entitlement-gated downloads through SelahCue licensing, and Admin Console operations.
- Requirements have stable IDs and testable acceptance criteria.
- Business rules, states, data, permissions, risks, and open decisions are documented.
- Existing design proposal and design gaps are linked.

Not ready for build until:

- User/product owner approves this brief.
- Legal/product confirms the first Bible licensing route and translation catalogue.
- Architecture defines account, billing, entitlement, license-key/signing, provider, and audit services.
- Security reviews staff auth/RBAC, impersonation, key generation, entitlement downloads, secrets, and audit.
- UI/UX designs the missing Licenses, Subscriptions, Support, Settings, Audit Log, and non-default states.
- ClickUp delivery structure is created only after approval.
