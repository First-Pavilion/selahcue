# SelahCue - Admin Console UX Handoff

Version: 0.1 gate draft  
Date: 2026-08-08  
Owner: UI/UX Designer  
Status: Gate review - not approved for implementation  
Goal Contract: `docs/delivery/goals/GOAL-admin-console-ux-design.md`  
Build Control: `https://app.clickup.com/t/86ajnx548`

> This UX handoff extends the existing Admin Console Figma proposal. It does not edit Figma, approve legal rights, create implementation tickets, or ship product behaviour.

## 1. Source Evidence

| Source | Label | What it contributes |
|---|---|---|
| `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md` | Verified | Admin scope, users, goals, requirements, business rules, permissions, states, risks, and open decisions |
| `docs/product/audits/Admin-Console-Project-Brief-Audit.md` | Verified | Product-readiness verdict and required design follow-ups |
| `docs/design/ADMIN-CONSOLE-HANDOFF.md` | Verified | Existing Figma Admin shell, default frames, token usage, component patterns, missing screens, and state gaps |
| Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, Admin page/node `518:124` | Verified | Proposed internal Admin Console page and navigation |
| `product/PRODUCT-BRIEF.md` | Verified | Whole-product offline-first posture and Bible licensing context |
| Bible translation availability, contract terms, offline rights, and reporting rules | Unknown | Must be confirmed per translation by Product/Legal/rights holders before launch |

## 2. Design Readiness Verdict

**Ready for product/design review. Not ready for implementation.**

The current Figma work gives the Admin Console a strong shell and reusable data-table/detail patterns. The key implementation gap is that the Admin-specific licensing surfaces are still textual: Licenses, Subscriptions, Support, Settings, Audit Log, and the non-default states need visual frames or a clear design-system implementation pass before frontend build.

This handoff makes those missing surfaces testable enough for architecture, security, backend, and frontend scoping. It should be followed by either Figma frame creation or a frontend prototype only after product approval.

## 3. Product Boundary

| Surface | Audience | Admin UX relationship |
|---|---|---|
| SelahCue desktop app | Church operators and local admins | Receives signed app-license and Bible-entitlement decisions; remains offline-first during services |
| Customer Account portal | Customer organisation owners/admins | Customer self-service for their own subscription, devices, invoices, and entitlements |
| Affiliate Portal | Affiliates | Separate external partner portal already covered by existing design handoff |
| Admin Console | SelahCue staff | Internal operational source for customers, app license keys, Bible catalogue, entitlements, support, settings, and audit |

Design rule: staff-only controls must never appear in customer Account or Affiliate Portal surfaces unless intentionally re-scoped.

## 4. Existing Figma Foundation

Reuse from the current Admin page:

- Shared Admin shell: left sidebar, top bar, global search, notifications, staff profile, active route treatment.
- Desktop-first data-table pattern: filters, search, status chips, pagination, row actions.
- Detail-page pattern: main column with commercial/support context plus right-side info/activity/internal notes.
- Reusable destructive confirmation dialog: scrim, consequence copy, type-to-confirm for high-severity actions.
- Token language: dark internal operations canvas using `bg/base`, `bg/panel`, `bg/elevated`, `border`, `text/primary`, `text/muted`, `accent/brand`, `accent/preview`, `accent/warn`, and `accent/live`.

Existing frames cover Overview, Customers, Customer detail, Users, Affiliates, affiliate detail, payouts, affiliate program settings, and a confirmation overlay. These are useful patterns, but mock values are placeholders.

## 5. Admin Information Architecture

| Route | Primary purpose | First-slice status |
|---|---|---|
| Overview | Operational health, expiring keys, licensing alerts, support queue, provider health | Expand existing frame |
| Customers | Search and manage organisations, contacts, plan state, keys, devices, entitlements, support context | Expand existing frame |
| Users | Manage customer users and internal support context | Existing list pattern, needs role/action states |
| Subscriptions | View plan, billing cycle, manual commercial arrangements, invoices, refunds/cancellations | Missing screen |
| Licenses | Manage app license keys, Bible translation catalogue, entitlements, download diagnostics, reports | Missing screen |
| Support | Triage activation, device, subscription, and Bible download issues | Missing screen |
| Settings | Staff, roles, key templates, licence policies, provider settings, notifications, audit retention | Missing screen |
| Audit Log | Search tamper-resistant staff/action history | Missing screen or Settings sub-route |
| Access Denied | Explain missing permission and link to safe destination | Missing state |

Recommended Licenses sub-navigation:

- App Keys
- Bible Catalogue
- Entitlements
- Download Diagnostics
- Reports

## 6. Critical UX Flows

### UX-ADM-FLOW-001 - Generate A Prospect App License Key

Requirement coverage: `ADM-FR-020` through `ADM-FR-029`, `ADM-BR-001` through `ADM-BR-004`.

Entry points:

- Customers list: `Create prospect` or row action `Issue key`.
- Customer detail: `Issue license key`.
- Licenses > App Keys: `Generate key`.

Primary path:

1. Staff chooses or creates a prospect/customer organisation.
2. Staff selects key type: Demo, Trial, Pilot, Paid, Internal QA, or Custom.
3. Staff chooses start time, duration, end date, timezone, plan/features, seats, device limit, territory, owner, and internal notes.
4. UI validates finite duration for demo/trial/pilot keys and blocks invalid dates.
5. Staff enters an audit reason.
6. Confirmation summarizes customer, dates, features, seats/devices, territory, and expiry.
7. System generates key and shows the full value once with Copy and Send/Share actions.
8. Later displays show prefix/suffix, status, expiry, activation count, and audit history.

Required states:

- Draft form, validation errors, permission-denied, submitting, generated success, copy success, copy failure, send failure, partial bulk result, expired, revoked, suspended, converted.
- Full key reveal must be time-limited, labelled sensitive, excluded from logs, and not shown in screenshots/tooltips.

### UX-ADM-FLOW-002 - Publish A Bible Translation Catalogue Item

Requirement coverage: `ADM-FR-040` through `ADM-FR-044`, `ADM-FR-072` through `ADM-FR-074`.

Entry point: Licenses > Bible Catalogue.

Primary path:

1. Licensing/Admin opens a translation record.
2. Staff enters code, name, edition, language, copyright class, rights holder, provider/source, allowed territories, attribution, effective date, renewal/expiry date, contract owner, offline permission, cache refresh rule, export/print limits, reporting requirement, and availability state.
3. Draft can be saved with incomplete legal fields.
4. Request Review validates required fields and shows missing legal/compliance fields.
5. Approved translations can move to Published.
6. Published translations become grantable in Entitlements.
7. Suspended/Retired translations remain visible internally with customer-impact summary.

Required states:

- Draft, review blocked, approved, published, suspended, retired, licence expired, territory blocked, provider down, reporting hook missing, attribution missing.

### UX-ADM-FLOW-003 - Grant A Customer Bible Entitlement

Requirement coverage: `ADM-FR-050` through `ADM-FR-058`, `ADM-BR-005` through `ADM-BR-012`.

Entry points:

- Customer detail: `Grant Bible entitlement`.
- Licenses > Entitlements: `Grant entitlement`.
- Support case: remediation action when entitlement is missing.

Primary path:

1. Staff selects customer, translation, plan/license basis, start/end date, seats/devices, territory, offline allowance, and reason.
2. UI blocks grants if the translation is not approved/published, is expired, is not allowed in the customer territory, lacks offline rights for the selected allowance, or needs reporting hooks that are unavailable.
3. Staff reviews entitlement impact: customer-visible translation name, devices affected, offline grace, deletion/revocation SLA, export/copy restrictions, attribution, and reporting.
4. Staff confirms and the entitlement appears on customer detail and Licenses > Entitlements.
5. Desktop activation/download responses include only active entitlement claims.

Required states:

- Eligible, ineligible translation, territory mismatch, licence expired, quota exhausted, provider/reporting unavailable, grant pending, grant failed, active, expiring, expired, revoked, sync pending.

### UX-ADM-FLOW-004 - Diagnose A Failed Licensed Bible Download

Requirement coverage: `ADM-FR-051`, `ADM-FR-053`, `ADM-FR-054`, `ADM-FR-058`, `ADM-FR-060` through `ADM-FR-063`.

Entry points:

- Support route search.
- Customer detail > Support/Activity.
- Licenses > Download Diagnostics.

Primary path:

1. Support searches by customer, email, key prefix, translation code, device, request id, or failure reason.
2. Diagnostic detail shows timeline: activation, entitlement check, provider status, territory check, quota/device check, download attempt, local-store state, revocation/deletion deadline, and app version.
3. UI identifies the most likely issue and safe remediation actions.
4. Support can resend activation, deactivate a stale device, refresh entitlement, retry provider sync, extend trial if permitted, or open/link a support case.
5. Unsafe remediations require permission, reason, confirmation, and audit.

Required states:

- No matching customer, no entitlement, revoked entitlement, expired key, device limit exceeded, provider down, reporting unavailable, network failure, app too old, clock skew, retry in progress, retry succeeded, retry failed.

### UX-ADM-FLOW-005 - Revoke A Key, Device, Or Bible Entitlement

Requirement coverage: `ADM-FR-004`, `ADM-FR-005`, `ADM-FR-025`, `ADM-FR-029`, `ADM-FR-053`, `ADM-FR-070` through `ADM-FR-074`.

Entry points:

- Customer detail.
- Licenses > App Keys.
- Licenses > Entitlements.
- Support diagnostic detail.

Primary path:

1. Staff chooses revoke/suspend/deactivate from a row action or detail action.
2. UI shows exact consequence: new activations blocked, active devices affected, offline grace/deletion rule, support impact, and customer-visible state.
3. High-severity actions require type-to-confirm plus audit reason.
4. Safe button receives initial focus.
5. Result banner links to audit entry and support follow-up.

Required states:

- Permission-denied, confirmation, reason missing, processing, success, partial success, failed, revocation pending on offline devices, undo not available, contact support/legal escalation.

### UX-ADM-FLOW-006 - Permission Denied And Read-Only Review

Requirement coverage: `ADM-FR-001` through `ADM-FR-006`, `ADM-FR-080` through `ADM-FR-083`.

Primary path:

1. Staff can see route-level navigation only for allowed areas.
2. If deep-linked to an unauthorized route/action, UI shows an Access Denied state with the missing permission and a safe destination.
3. Read-only users can inspect records and copy non-sensitive IDs, but cannot reveal full keys, grant entitlements, refund, impersonate, export sensitive reports, or change settings.
4. Hidden controls are still enforced server-side.

Required states:

- Route denied, action denied, read-only view, approval required, session expired, MFA required if configured.

## 7. Screen Specifications

### Overview

Purpose: executive operational scan for internal staff.

Required modules:

- KPI row: active customers, active subscriptions, MRR or ARR if approved, active app keys, expiring keys, active Bible entitlements, open support cases.
- Alert list: keys expiring in 7/14/30 days, translations expiring soon, provider/reporting failures, high-risk audit events.
- Recent activity: new trials, entitlement grants/revocations, failed downloads, support escalations.

States:

- Loading skeletons, no alerts, provider health error, limited role view, stale data warning.

### Customers

Purpose: staff entry point for organisations and support context.

Required modules:

- Search by organisation, contact email, key prefix, status, plan, country, date range.
- Filters for Prospect, Trial, Active, Past Due, Suspended, Cancelled, Churned, Archived.
- Table columns: org, contact, plan, customer status, app key status, Bible entitlement count, seats/devices, country, joined, recent issue.
- Row actions: View, Issue key, Grant entitlement, Open support case, Suspend customer, Archive.

States:

- Empty, filtered-empty, loading, server error, row-action open, sort active, permission-limited actions.

### Customer Detail

Purpose: one staff record for customer commercial, licensing, device, and support state.

Required modules:

- Header: organisation, status, country/timezone, primary contact, owner, high-risk flags.
- Tabs: Summary, App Keys, Devices, Bible Entitlements, Subscription, Invoices, Support Cases, Internal Notes, Audit.
- Right sidebar: recent activity, unresolved support cases, risk/compliance flags.
- Actions: Message, Issue key, Grant entitlement, Deactivate device, Change plan, Refund/cancel if permitted, Impersonate if permitted.

States:

- Customer not found, archived customer, read-only, unsupported country, open support case, destructive confirmation, stale data conflict.

### Users

Purpose: manage customer users and support context.

Required modules:

- Search/filter by name, email, organisation, role, status, last active.
- Row actions: View, reset password, suspend, impersonate if permitted.
- User detail follow-up: linked organisations, devices, recent sessions, support history.

States:

- Invite pending, suspended, disabled organisation, MFA/session issue if applicable.

### Subscriptions

Purpose: view commercial status and handle manual billing context without making billing provider decisions in the UI.

Required modules:

- Subscription table with customer, plan, cycle, trial end, renewal date, payment status, provider reference, MRR/ARR if approved.
- Customer subscription detail: plan timeline, invoices, discounts, refunds, cancellation, manual contract notes.
- Manual arrangement form: approved duration, features, contract owner, attachment/reference, reason.

States:

- Trial ending, past due, cancelled, provider sync delayed, manual pending, refund pending, action denied.

### Licenses

Purpose: central operations area for app license keys and Bible licensing.

Sub-routes:

- App Keys: generate/search/revoke/extend/convert keys.
- Bible Catalogue: define available translations and legal/compliance constraints.
- Entitlements: grant/revoke customer access to licensed translations.
- Download Diagnostics: investigate activation/download failures.
- Reports: export approved usage/download/licensing reports.

States:

- No keys, filtered-empty, bulk preview, generated success, key masked, entitlement ineligible, provider down, report unavailable, export permission denied.

### Support

Purpose: triage customer activation, device, subscription, and licensed-download issues.

Required modules:

- Queue summary: unassigned, urgent, provider-related, activation-related, billing-related, entitlement-related.
- Search by customer, user, key prefix, device, translation, request id, external ticket id.
- Case detail: linked customer, app key, device, entitlement, invoice, diagnostic timeline, internal notes, audit references.
- Safe remediation actions: resend activation, refresh entitlement, retry provider sync, deactivate device, extend trial if permitted.

States:

- No case selected, empty queue, linked ticket unavailable, retry pending, escalation required, remediation denied.

### Settings

Purpose: configure internal Admin operations.

Required modules:

- Staff and Roles: invitations, role assignment, disabled staff, permission matrix.
- Key Templates: 7-day demo, 30-day trial, event pilot, annual church, internal QA, custom limits.
- Licence Policies: default offline grace, expiry notices, revocation handling, deletion SLA placeholders pending legal approval.
- Provider Settings: API/provider status, contract references, secrets status/fingerprint only.
- Notifications: expiry windows, support routing, reporting alerts.
- Audit Retention: retention policy display and export permission controls.

States:

- Invite sent, role conflict, cannot self-escalate, secret saved, secret hidden after entry, policy requires approval, disabled setting, validation error.

### Audit Log

Purpose: searchable, tamper-resistant evidence of sensitive Admin actions.

Required modules:

- Filters: actor, role, action, target type/id, customer, result, date range, request id.
- Event detail: actor, target, before/after where safe, reason, timestamp, result, source surface, linked support case.
- Export action available only to permitted roles and audited itself.

States:

- Empty, filtered-empty, export denied, export generated, event detail redacted, retention boundary.

## 8. State Matrix

| Surface | Loading | Empty | Filtered empty | Error | Permission | Destructive/high risk | Expired/revoked/recovery |
|---|---|---|---|---|---|---|---|
| Overview | Skeleton KPIs and tables | No alerts | Not applicable | Provider health unavailable | Limited KPIs | Not applicable | Stale data banner with refresh |
| Customers | Skeleton rows | No customers yet | No customers match filters | Retry table load | Hide/disable restricted actions | Suspend/archive confirm | Archived customer state |
| Customer Detail | Header/tabs skeleton | Not applicable | Empty tab state | Customer unavailable | Read-only tabs/actions | Revoke, deactivate, refund, cancel, impersonate | Sync conflict, offline device pending |
| App Keys | Skeleton rows | No app keys yet | No keys match filters | Key service unavailable | Generate/reveal denied | Revoke/extend/convert confirm | Expired, revoked, suspended, conversion success |
| Key Generation Modal | Submitting overlay | Not applicable | Not applicable | Server validation error | Generate denied | Confirm issue/bulk issue | Generated once, copy/send failure |
| Bible Catalogue | Skeleton rows | No translations yet | No translations match filters | Provider/licence service unavailable | Publish denied | Suspend/retire confirm | Licence expired, reporting blocked |
| Translation Detail | Field skeleton | New draft | Not applicable | Save failed | Restricted legal fields | Publish/suspend confirm | Missing legal fields, renewal overdue |
| Entitlements | Skeleton rows | No entitlements yet | No entitlements match filters | Entitlement service unavailable | Grant/revoke denied | Grant paid entitlement/revoke confirm | Expired, revoked, territory blocked |
| Download Diagnostics | Timeline skeleton | No failures yet | No diagnostics match filters | Diagnostic source unavailable | Remediation denied | Device deactivate/retry impact confirm | Retry pending/succeeded/failed |
| Subscriptions | Skeleton rows | No subscriptions yet | No subscriptions match filters | Billing sync unavailable | Refund/cancel denied | Refund/cancel/change plan confirm | Past due, cancelled, manual pending |
| Support | Queue skeleton | No cases | No cases match filters | Ticket provider unavailable | Remediation denied | Extend/deactivate/retry confirm | Escalated, resolved, reopened |
| Settings | Section skeleton | No staff/templates where applicable | Not applicable | Save failed | Route/action denied | Role change/secret/policy confirm | Approval required, cannot self-escalate |
| Audit Log | Skeleton rows | No audit events | No events match filters | Search/export failed | Redacted/export denied | Export sensitive report confirm | Retention boundary, event redacted |

## 9. Interaction And Component Inventory

Prioritise reusable operational components over one-off layouts:

- AdminShell: sidebar, top bar, global search, notifications, staff menu.
- DataTable: sortable headers, row selection where needed, pagination, loading/empty/error states, row action menu.
- StatusChip: includes text label and semantic status, never colour alone.
- DetailHeader: object name, status, high-risk flags, primary actions.
- TabSet: Summary/App Keys/Devices/Bible Entitlements/Subscription/Invoices/Support/Audit patterns.
- ConfirmDialog: consequence copy, safe default focus, type-to-confirm for high severity, reason capture.
- KeyRevealCopy: one-time full-key reveal, masked later display, copy status, sensitive logging guard.
- DurationField: preset durations plus custom start/end, timezone visibility, UTC storage note.
- EntitlementGrantForm: translation eligibility checks, licence summary, reason, confirmation.
- TranslationPolicyPanel: offline, cache, territory, export, attribution, reporting, expiry fields.
- DiagnosticTimeline: ordered checks with pass/fail/warn status and remediation links.
- PermissionBanner: explains read-only or missing permission without exposing hidden capabilities.
- AuditDiff: safe before/after display with redaction for secrets and sensitive values.
- ToastLiveRegion: polite announcements for success/failure and copy/send events.

## 10. Accessibility Requirements

- Use real table semantics for data tables, including column headers, row labels where helpful, sortable headers with `aria-sort`, and labelled row action menus.
- Every interactive element needs visible `:focus-visible` treatment. Keyboard order follows visual order: sidebar, top bar, page actions, filters, table, pagination.
- Dialogs use `role="dialog"`, `aria-modal`, labelled title, focus trap, Escape to cancel, and initial focus on the safe action.
- Destructive actions must be understandable without colour: title, status chip text, consequence copy, affected object names, and explicit result message.
- Status chips include accessible names such as "Expired app key" or "Bible entitlement active".
- Copy/reveal actions announce success and failure through a polite live region.
- Full key values are sensitive: avoid putting full keys in tooltip titles, URLs, analytics, page titles, logs, screenshots, or clipboard history beyond the deliberate copy action.
- For long tables, preserve keyboard access to horizontal scroll containers and row actions.
- Use concise labels for screen-reader clarity: "Grant Bible entitlement", "Revoke app key", "Deactivate device", "Export licence report".
- Validate contrast for small chips and muted text on the dark admin canvas before build.

## 11. Responsive Behaviour

Admin is desktop-first, but it must remain usable on constrained devices:

- 1280 px and wider: full sidebar, 4-up KPI rows, 2-column detail pages with right sidebar.
- 1024 to 1279 px: sidebar collapses to icon rail, KPI rows become 2-up, right sidebar drops below main detail column.
- Below 1024 px: sidebar becomes a drawer, tables use horizontal scroll or stacked row summaries, page body must not horizontally scroll.
- Modal forms must fit mobile heights with sticky header/footer and scrollable body.
- High-density tables keep stable column widths and avoid layout shift when filters, status chips, row actions, or loading states change.
- Admin mobile is lower priority than Affiliate Portal mobile, but support triage and emergency revoke/deactivate flows should not be blocked on tablet widths.

## 12. Content Guidelines

Use operational copy that names the object, reason, and next step. Avoid marketing language.

Recommended labels:

- "Generate key"
- "Grant entitlement"
- "Revoke entitlement"
- "Deactivate device"
- "Retry provider sync"
- "Download diagnostics"
- "Export licence report"
- "Access denied"

Error and empty-state examples:

- No customers: "No customers yet."
- Filtered customers: "No customers match these filters."
- Expired key: "This key expired on {date}. New device activations are blocked."
- Revoked entitlement: "This entitlement was revoked. New downloads are blocked; offline devices follow the recorded revocation policy."
- Territory blocked: "This translation is not available for the customer's territory."
- Provider down: "Provider sync is unavailable. Retry when provider health recovers or escalate to Licensing."
- Missing legal fields: "Complete rights holder, territory, attribution, offline, expiry, and reporting fields before publishing."
- Full key warning: "This full key is shown once. Store and share it carefully."

Confirmation copy must include:

- The exact customer, key, device, translation, or report affected.
- What will stop working.
- Whether existing offline devices are affected immediately or on next policy check.
- Whether the action can be undone.
- The required audit reason.

## 13. Requirement Traceability

| UX area | Admin requirement coverage |
|---|---|
| Staff auth, access denied, read-only controls, impersonation banner | `ADM-FR-001` through `ADM-FR-006`, `ADM-FR-080` through `ADM-FR-083` |
| Customers, customer detail, customer search/status | `ADM-FR-010` through `ADM-FR-014` |
| App key generation, finite durations, feature/device limits, activation, revoke/extend/convert, masked display | `ADM-FR-020` through `ADM-FR-029` |
| Subscription list/detail, manual arrangements, plan changes, refunds/cancellation | `ADM-FR-030` through `ADM-FR-033` |
| Bible catalogue, legal fields, constraints, staged availability, unavailable states | `ADM-FR-040` through `ADM-FR-044` |
| Customer Bible entitlements, licensed downloads, protected local store, revocation, offline rules, attribution, export limits, reporting, download failures | `ADM-FR-050` through `ADM-FR-058` |
| Support triage and safe remediation | `ADM-FR-060` through `ADM-FR-063` |
| Audit log, licence reports, sensitive exports, compliance warnings | `ADM-FR-070` through `ADM-FR-074` |
| Key templates, policy defaults, provider settings, secret handling | `ADM-FR-080` through `ADM-FR-083` |

## 14. Figma Follow-Up Backlog

Create or update visual frames after product owner approval:

| Proposed frame name | Purpose |
|---|---|
| Admin - Licenses - App Keys | Key search, filters, generate key, key lifecycle states |
| Admin - Licenses - Generate Key Modal | Duration/features/seats/devices/territory/reason/copy flow |
| Admin - Licenses - Bible Catalogue | Translation list, legal status, availability, provider health |
| Admin - Licenses - Translation Detail | Legal/licence constraints, publish workflow, reporting fields |
| Admin - Licenses - Entitlements | Customer grants, eligibility, revoke/expiry states |
| Admin - Licenses - Grant Entitlement Modal | Translation eligibility, terms summary, reason, confirmation |
| Admin - Licenses - Download Diagnostics | Timeline and remediation actions for failed downloads |
| Admin - Subscriptions | Plan/billing/manual arrangement list and detail |
| Admin - Support | Support queue, diagnostic detail, remediation states |
| Admin - Settings - Staff And Roles | Staff invites, role matrix, cannot self-escalate state |
| Admin - Settings - Key Templates | Presets for demo/trial/pilot/annual/internal QA keys |
| Admin - Settings - Licence Policies | Defaults and legal-approval placeholders |
| Admin - Settings - Providers | Provider health, contract references, secret fingerprints |
| Admin - Audit Log | Search, event detail, redaction, export states |
| Admin - Access Denied | Route/action denied state |
| Admin - Empty/Loading/Error States | Reusable state frames for tables, forms, diagnostics, reports |

Keep the existing Admin shell, dark token system, table pattern, status chips, confirmation dialog, and detail layout. Do not use marketing-page composition for these internal operational surfaces.

## 15. Gate Notes And Pending ClickUp Update

This handoff is ready for product/design review once the goal validator passes. It intentionally stops before implementation.

Known process issue: prior attempts to create comments on ClickUp task `86ajnx548` failed with `INVALID_ARGUMENT`, including a minimal `hello` comment, while ClickUp read/search/comment-read operations worked. Do not claim ClickUp has been updated unless the connector succeeds.

Pending ClickUp update text:

`Admin Console UX handoff is ready for product/design review in docs/design/ADMIN-CONSOLE-UX-HANDOFF.md. It covers missing Licenses, Subscriptions, Support, Settings, Audit Log, app license-key, Bible entitlement/download, revocation, accessibility, responsive, state, component, and requirement-traceability guidance. No production code or ClickUp implementation tasks were created.`

## 16. Recommended Next Skill

After product/design review, the next workflow skill should be `$software-architect` to define system boundaries, service ownership, data models, APIs, entitlement/key lifecycle, audit, security posture, and integration decisions before backend or frontend implementation.

If product wants visual frames before architecture, run `$ui-ux-designer` again with Figma-write scope for the backlog in section 14.
