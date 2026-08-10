# SelahCue - Admin Licensing Architecture

Version: 0.2 stack/path refinement  
Date: 2026-08-08  
Owner: Software Architect  
Status: Gate review - not approved for implementation  
Goal Contract: `docs/delivery/goals/GOAL-arch-admin-licensing.md`  
Decision Record: `docs/architecture/adr/ADR-0021-admin-licensing-services.md`  
ClickUp Build Control: `https://app.clickup.com/t/86ajnx548`

> This architecture defines service boundaries and contracts. It does not implement code, approve legal rights, create ClickUp implementation tickets, or choose final billing/identity/provider vendors.

## 1. Readiness Verdict

**Ready for architecture review. Not ready for implementation.**

The target architecture is a SelahCue-hosted Platform API implemented initially as a Django modular monolith with Strawberry GraphQL, explicit bounded contexts, and an event outbox. It manages staff access, customer accounts, billing state, app license keys, Bible translation catalogue records, customer entitlements, download leases, support diagnostics, reporting, and append-only audit.

The Admin Console is a Vue 3 frontend that consumes the staff GraphQL surface. The same Django domain services also expose customer/account GraphQL operations for normal users, while desktop activation, policy refresh, licensed-download preparation/completion, usage-event batching, and provider/billing webhooks remain narrow versioned JSON command endpoints.

The desktop app remains authoritative for live presentation and service operation. Admin services are required for new activations, licence refresh, new licensed downloads, revocation propagation, and support/compliance reporting; they are not required for an already-activated Sunday service to keep presenting previously downloaded content within approved grace rules.

## 2. Evidence Labels

- **Verified:** directly observed in repository docs, code, ClickUp, or tool output.
- **Inferred:** supported by verified evidence but not directly observed as implemented.
- **Assumed:** used to make the architecture concrete; needs owner confirmation.
- **Unknown:** unresolved and decision-relevant.

## 3. Current State Evidence

| Fact | Label | Evidence |
|---|---|---|
| SelahCue architecture is desktop-authoritative and offline-first; cloud/mobile are assistive and cannot gate core live operation. | Verified | `docs/architecture/ARCHITECTURE.md` sections 1, 3, 5 |
| Desktop persistence uses SQLite/WAL with SQLCipher-ready encrypted storage, append-only migrations, integrity checks, and repository-owned data access. | Verified | `docs/architecture/adr/ADR-0007-persistence.md`, `implementation/desktop/crates/selahcue-data/src/db.rs`, `migrations.rs` |
| LAN/mobile security already uses host-side RBAC, strict commands, encrypted transport, and denial semantics for untrusted clients. | Verified | `docs/architecture/adr/ADR-0008-lan-protocol-security.md`, `implementation/desktop/crates/selahcue-lan/src/rbac.rs`, `protocol.rs` |
| Observability posture is local-first, redacted, structured, bounded, and opt-in for off-device telemetry. | Verified | `docs/architecture/adr/ADR-0011-observability.md` |
| Licensed translation architecture already has a provider seam concept with entitlement-gated offline store where a licence allows it. | Verified | `docs/architecture/adr/ADR-0017-translation-providers.md`, `docs/research/LICENSED-TRANSLATIONS.md` |
| Admin PRD requires staff auth/RBAC, customers, subscriptions, time-bound app license keys, Bible catalogue, entitlements, downloads, support diagnostics, audit, and settings. | Verified | `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md` |
| UX handoff defines flows for app key generation, catalogue publication, entitlement grant, download diagnostics, revocation, and permission-denied states. | Verified | `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md` |
| A desktop cloud client seam exists for sermon notes, but the live SelahCue cloud service does not exist yet. | Verified | `implementation/desktop/crates/selahcue-cloud/src/lib.rs` |
| No implemented Admin Console frontend, shared Platform API, or Admin service exists in the current codebase. | Verified | Repo search found docs/design/product Admin references, but no `implementation/admin` or `implementation/api` implementation module |
| User architecture direction is Vue 3 for Admin frontend and Django + Strawberry GraphQL for the shared API that serves Admin and normal users. | Verified | User direction on 2026-08-08 in the architecture refinement thread |
| User source-layout direction is Admin frontend code under `implementation/admin` and Django API code under `implementation/api`. | Verified | User direction on 2026-08-08 in the architecture refinement thread |
| Billing provider, identity provider, hosting stack, legal entity, first licensed translations, provider terms, and retention periods are not approved. | Unknown | Admin PRD open decisions |

## 4. Requirement Traceability

| Area | Requirements and source |
|---|---|
| Staff auth, staff RBAC, access denied, impersonation controls | `ADM-FR-001` through `ADM-FR-006`, UX flow `UX-ADM-FLOW-006` |
| Customers and customer detail | `ADM-FR-010` through `ADM-FR-014` |
| App license keys | `ADM-FR-020` through `ADM-FR-029`, `ADM-BR-001` through `ADM-BR-004`, UX flow `UX-ADM-FLOW-001` |
| Subscriptions and billing context | `ADM-FR-030` through `ADM-FR-033` |
| Bible translation catalogue | `ADM-FR-040` through `ADM-FR-044`, UX flow `UX-ADM-FLOW-002` |
| Bible entitlements and downloads | `ADM-FR-050` through `ADM-FR-058`, `ADM-BR-005` through `ADM-BR-012`, UX flow `UX-ADM-FLOW-003` |
| Download/activation support | `ADM-FR-060` through `ADM-FR-063`, UX flow `UX-ADM-FLOW-004` |
| Revocation | `ADM-FR-025`, `ADM-FR-029`, `ADM-FR-053`, UX flow `UX-ADM-FLOW-005` |
| Audit, reporting, exports, compliance warnings | `ADM-FR-070` through `ADM-FR-074` |
| Settings, key templates, provider settings, secrets | `ADM-FR-080` through `ADM-FR-083` |
| Existing product scripture/licensing posture | PRD `FR-033`, `FR-034`, `FR-035`, `FR-146`; ADR-0017 |

## 5. Quality Attribute Scenarios

| Attribute | Scenario | Architecture response |
|---|---|---|
| Security | A Support staff member attempts to grant a paid Bible entitlement. | Admin API rejects with `PERMISSION_DENIED`, records audit event, and does not create entitlement. |
| Privacy | A support diagnostics export is created. | Export redacts full keys, secrets, provider credentials, full Bible text, and unnecessary personal data; export action is audited. |
| Offline-first | A valid activated desktop loses internet before Sunday service. | Previously downloaded licensed translations remain usable only until the signed entitlement policy's grace/refresh deadline; no live output blanks because Admin is offline. |
| Revocation | Licensing revokes an entitlement while a device is offline. | New downloads stop immediately server-side; desktop enforces revocation on next policy check and disables/deletes local content by recorded SLA. |
| Consistency | Billing provider sends duplicate subscription webhooks. | Webhook handler is idempotent by provider event id; repeated events produce one billing state transition and one audit reference. |
| Availability | Bible content provider is unavailable. | Published translations are marked provider-unavailable for new downloads; existing live output and already valid local content continue; support diagnostics show provider cause. |
| Performance | Staff searches 100k app keys by prefix/customer/date. | License key table stores prefix/suffix/hash/fingerprint and indexed search fields; no full-key scan is required. |
| Maintainability | API.Bible is replaced by a direct publisher provider. | Provider adapter changes behind Translation Catalogue and Download Gateway contracts; GraphQL/command API contracts and desktop entitlement policy shape remain stable. |
| Cost | Download/reporting volume grows. | Download leases, usage-event batching, report jobs, and provider-specific quotas are metered and observable per provider. |

## 6. Target Architecture Overview

Recommended first deployable shape: **one SelahCue Platform API deployable** with modular contexts, one primary relational database, one object/package store for licensed translation packages where allowed, one job/worker process, and one event outbox, plus a separate Vue 3 Admin frontend deployable.

Source ownership:

- `implementation/api`: Django project, Strawberry GraphQL schema/resolvers, domain services, data models, migrations, workers, desktop command APIs, provider/billing webhooks, audit/outbox.
- `implementation/admin`: Vue 3 Admin Console frontend, generated GraphQL client types/operations, route guards, Admin state management, Admin UI implementation.
- `docs/...`: product, UX, architecture, ADR, security, QA, delivery-goal, and operations evidence.

It should be modular enough to split later, but not split into microservices before the product/billing/licensing decisions are stable.

```text
 SelahCue staff browser
   -> Admin Console (Vue 3; implementation/admin)
   -> Staff GraphQL endpoint /graphql/admin
   -> SelahCue Platform API (Django + Strawberry; implementation/api)
      -> Identity + Staff RBAC
      -> Customer Account Context
      -> Billing Context
      -> App License-Key Context
      -> Translation Catalogue Context
      -> Entitlement Context
      -> Download Gateway
      -> Support Diagnostics
      -> Audit/Event Ledger
      -> Reporting Jobs
      -> Provider Adapters

 Customer/account user browser, future
   -> Customer Account portal, future frontend
   -> Account GraphQL endpoint /graphql/account
   -> Same Platform API contexts with customer-scoped authorization

 SelahCue desktop app
   -> Activation / Policy JSON command API
   -> Entitlement Manifest JSON API
   -> Download Lease JSON command API
   -> Usage Event Batch JSON command API
   -> Encrypted local licensed-content store

 External systems
   -> Staff IdP
   -> Billing provider, unknown
   -> Translation providers or publisher feeds, unknown
   -> Email/notification provider, later slice
```

## 7. Bounded Contexts And Ownership

| Context | Owns | Does not own | Primary owner |
|---|---|---|---|
| Identity and Staff RBAC | Staff identity links, roles, permissions, session policy, access-denied decisions | Customer app roles, mobile venue roles | Security/Admin |
| Customer Account | Customer organisations, contacts, customer users, status, country/timezone, internal notes | Billing truth, entitlement terms, provider credentials | Product/Support |
| Billing | Plans, subscription state, invoices, refunds/cancels, manual arrangements, provider refs | License-key cryptography, Bible legal status | Finance |
| App License-Key | Key generation, hashing, masking, activation attempts, device activations, feature claims, expiry/revoke/extend/convert | Bible translation entitlement grants | Product/Security |
| Translation Catalogue | Translation metadata, legal status, rights holder, terms, territories, attribution, provider mapping, availability | Customer-specific entitlement state | Licensing/Legal |
| Entitlement | Customer-to-translation grants, expiry/revocation, offline/refresh/deletion policy, device scope | Full Bible text storage | Licensing/Support |
| Download Gateway | Download authorization, short-lived leases, package metadata, checksums, provider availability, local-store policy | Permanent entitlement truth | Architecture/Backend |
| Provider Adapter | API.Bible/direct publisher/user-supplied feed integration, provider errors, usage/reporting obligations | Staff/customer policy decisions | Licensing/Backend |
| Support Diagnostics | Searchable activation/download timelines and remediation surfaces | Unsafe data repair outside policy | Support |
| Audit/Event Ledger | Append-only security/compliance events, before/after summaries, reasons, actor/result | Operational metrics detail | Security |
| Reporting | Licence usage/download/export reports per provider | Legal interpretation of report sufficiency | Licensing/Legal |

## 8. Trust Boundaries

| Boundary | Threats | Controls |
|---|---|---|
| Staff browser -> Admin GraphQL | Session theft, CSRF, over-broad staff action | Managed IdP, MFA, same-site session/csrf controls, server-side RBAC, reason capture, audit |
| Platform API -> database/object store | Data corruption, privilege escalation, secret exposure | Repository/service layer, parameterised queries, row-level tenant checks, KMS/secret-store, migrations, backups |
| Desktop app -> Activation/Policy API | Stolen key, replay, fake device, brute force | TLS, rate limits, high-entropy keys, hash-only storage, device fingerprint, signed responses, idempotency |
| Download Gateway -> desktop | Unauthorized licensed text copy | Entitlement validation, short-lived download lease, device-bound policy, checksum, encrypted local store, no public URLs |
| Billing provider -> webhook | Forged or duplicate event | Provider signature verification, event id idempotency, reconciliation job |
| Provider adapter -> external translation provider | Provider outage, quota, terms mismatch | Circuit breaker, typed provider errors, availability state, retry with backoff, manual suspension |
| Admin exports -> staff machine | Excessive sensitive data exposure | Explicit permission, export minimisation, redaction, watermark/manifest, audit |

## 9. Logical Data Model

Use a server-side relational database for Admin multi-user concurrency and webhooks. PostgreSQL is the preferred baseline, but hosting selection is still Unknown and must be confirmed by DevOps. Desktop continues using SQLite/SQLCipher for local app state.

| Entity | Required fields and invariants | Indexes |
|---|---|---|
| `staff_user` | `id`, `idp_subject`, `email`, `role`, `status`, `created_at`, `last_seen_at`; cannot self-escalate; disabled staff cannot act | unique `idp_subject`, unique lower email |
| `staff_session` | session id/hash, staff id, issued/expires, mfa/assurance, revoked_at | staff id, expires |
| `customer_org` | name, slug/code, status, country, timezone, primary/billing contacts, owner, archived_at | status, country, lower name |
| `customer_user` | org id, email, role, status | org/email unique |
| `subscription` | org id, plan, billing_status, cycle, trial_end, renewal, provider, provider_customer_ref, provider_subscription_ref, manual_arrangement_ref | org, provider refs, billing_status |
| `invoice_ref` | org id, provider invoice ref, amount/currency, status, issued/paid dates, hosted url token/ref | org/date, provider ref unique |
| `manual_commercial_arrangement` | org id, approved features, start/end, approver, reason, attachment/ref | org/end |
| `app_license_key` | key id, type, customer/prospect id, prefix, suffix, secret_hash, status, start/end UTC, timezone label, feature scope, seat/device limits, territory, generated_by, generated_reason; full key never persisted recoverably | prefix, suffix, secret_hash unique, customer/status/end |
| `device_activation` | org id, key id, device id/fingerprint hash, platform, app version, status, first/last seen, last_policy_version, revoke_reason | org/device, key/status, last_seen |
| `license_policy_snapshot` | org id/device id, signed policy version, plan/features, expiry/grace, generated_at, signing_key_id | org/device/version |
| `translation_catalogue_item` | code, name, edition, language, copyright class, rights holder, provider, legal_status, availability_status, attribution, terms json, published_at | code unique, status, provider |
| `translation_contract` | catalogue item id, contract owner, legal approval ref, territories, offline_allowed, refresh_interval, deletion_sla, export/print caps, reporting requirement, effective/expiry dates | item/status/expiry |
| `translation_entitlement` | org id, catalogue item id, basis, status, start/end, territory, seat/device scope, offline policy snapshot, granted_by, reason, revoked_at/reason | org/item/status, end, territory |
| `download_lease` | entitlement id, device id, translation code, lease token hash, status, expires_at, package version, checksum, result/reason | token hash unique, device/status, expires |
| `download_event` | request id, org/device/translation, entitlement id, result, denial code, provider cause, app version, timestamp | org/date, device/date, translation/result |
| `usage_event` | org/device/translation, event type, provider usage token, presentation context, timestamp, reporting batch id | provider token, translation/date, batch |
| `support_case_ref` | external ticket id/ref, org id, linked key/device/entitlement/download, status, owner, severity | org/status, external ref |
| `audit_event` | append-only id, actor staff/service/device, role, action, target type/id, before/after redacted json, reason, result, request id, source surface, timestamp | actor/date, target/date, action/date, request id |
| `outbox_event` | id, event type, payload, idempotency key, status, attempts, next_attempt_at | status/next_attempt, idempotency unique |

Retention periods are Unknown. Until Legal/Security decides, architecture should support configurable retention by event class rather than hardcoding one global value.

## 10. Domain Invariants And Lifecycles

### Customer

Allowed states: `Prospect`, `Trial`, `Active`, `PastDue`, `Suspended`, `Cancelled`, `Churned`, `Archived`.

Invariants:

- Archived customers are read-only except restore by Owner/Admin.
- Suspended/PastDue state can block new activations/downloads but must not silently delete audit/history.
- Customer country/territory affects Bible entitlement eligibility.

### App License Key

Allowed states: `Draft`, `Issued`, `Activated`, `Expiring`, `Expired`, `Suspended`, `Revoked`, `Converted`, `Archived`.

Invariants:

- Prospect/demo/pilot keys must have a finite end date.
- Full key is generated once, returned once, and then discarded; only hash, prefix, suffix, and fingerprint remain.
- Activation checks are server-side: date window, key status, customer status, seat/device limits, feature scope, territory, and abuse/rate limits.
- Revoked/expired keys cannot activate new devices. Existing devices receive changed policy on next refresh according to approved grace.

### Translation Catalogue

Allowed states: `Draft`, `LegalReview`, `Approved`, `Published`, `Suspended`, `Retired`.

Invariants:

- Copyrighted translations cannot be Published until legal approval fields, attribution, territory, offline/cache/export/reporting fields, and contract owner are present.
- Suspended/Retired translations cannot receive new entitlements or download leases.
- Provider-down is availability, not legal status.

### Entitlement

Allowed states: `Pending`, `Active`, `Expiring`, `Expired`, `Revoked`, `TerritoryBlocked`, `RefreshRequired`, `DeletionPending`.

Invariants:

- Entitlement is separate from app license key. A customer may have one without the other.
- Active entitlement requires Published translation plus valid customer/app policy.
- Entitlement grant/revoke requires staff permission, reason, audit, and legal policy validation.
- Revocation immediately blocks new downloads and creates desktop policy changes that enforce local disable/delete by SLA.

### Download Lease

Allowed states: `Prepared`, `Started`, `Completed`, `Expired`, `Denied`, `Revoked`, `Failed`.

Invariants:

- A lease is short-lived, single-device, and scoped to one entitlement, package version, checksum, and translation.
- Public download URLs are not bearer entitlements; they must expire quickly and be useless without a valid lease.
- Download failures produce a supportable denial code.

## 11. API Contracts

All surfaces use TLS, correlation id `X-Request-Id`, stable machine error codes, and server-side authorization. Staff/customer account operations use Strawberry GraphQL in the Django service. Desktop activation/download and external webhooks use narrow structured JSON command endpoints under `/v1` because those contracts must be especially stable, idempotent, cache/test friendly, and easy for desktop clients and providers to retry.

### Staff Admin GraphQL

Endpoint: `POST /graphql/admin`

| ID | Operation | Auth | Notes |
|---|---|---|---|
| ADMIN-GQL-001 | `Query.adminCustomers` | Staff `ViewCustomers` | Relay-style cursor connection; filters by name/email/key prefix/status/plan/country/date. |
| ADMIN-GQL-002 | `Mutation.adminCreateCustomer` | Staff `ManageCustomers` | Creates prospect/customer; validates country/timezone/contact; requires idempotency key. |
| ADMIN-GQL-003 | `Query.adminCustomer` | Staff `ViewCustomers` | Aggregated customer detail: subscription, keys, devices, entitlements, support, audit summary. |
| ADMIN-GQL-004 | `Mutation.adminGenerateLicenseKey` | Staff `GenerateLicenseKey` | Returns full key once; requires reason; stores hash only. |
| ADMIN-GQL-005 | `Mutation.adminExtendLicenseKey` | Staff `ExtendLicenseKey` | Requires reason and valid new end date. |
| ADMIN-GQL-006 | `Mutation.adminRevokeLicenseKey` | Staff `RevokeLicenseKey` | Requires consequence confirmation token and reason. |
| ADMIN-GQL-007 | `Query.adminTranslations` | Staff `ViewCatalogue` | Catalogue connection with legal and availability filters. |
| ADMIN-GQL-008 | `Mutation.adminUpdateTranslation` | Staff `ManageCatalogue` | Draft/Review/Approved/Published/Suspended/Retired transitions. |
| ADMIN-GQL-009 | `Mutation.adminGrantEntitlement` | Staff `GrantEntitlement` | Validates translation, legal fields, territory, plan/basis, and reason. |
| ADMIN-GQL-010 | `Mutation.adminRevokeEntitlement` | Staff `RevokeEntitlement` | Blocks new downloads and issues policy-change event. |
| ADMIN-GQL-011 | `Query.adminDownloadDiagnostics` | Staff `ViewDiagnostics` | Search by request id, customer, key prefix, device, translation, denial code. |
| ADMIN-GQL-012 | `Mutation.adminLinkSupportCase` | Staff `ManageSupport` | Creates/links external support case refs. |
| ADMIN-GQL-013 | `Query.adminAuditEvents` | Staff `ViewAudit` | Tamper-resistant search; redacted detail by role. |
| ADMIN-GQL-014 | `Mutation.adminCreateLicenceUsageExport` | Staff `ExportLicenceReports` | Starts async report job; export itself audited. |

### Customer Account GraphQL

Endpoint: `POST /graphql/account`

| ID | Operation | Auth | Notes |
|---|---|---|---|
| ACCOUNT-GQL-001 | `Query.accountViewer` | Customer user | Returns current customer user, organisation, role, and allowed self-service capabilities. |
| ACCOUNT-GQL-002 | `Query.accountSubscription` | Customer owner/admin | Shows plan, billing status, renewal/trial dates, invoice refs, and manual arrangement summary. |
| ACCOUNT-GQL-003 | `Query.accountLicenseKeys` | Customer owner/admin | Lists masked app keys, expiry, activation count, and renewal/revoke state visible to the customer. |
| ACCOUNT-GQL-004 | `Query.accountDevices` | Customer owner/admin | Lists activated devices and policy freshness without exposing unsafe fingerprints. |
| ACCOUNT-GQL-005 | `Query.accountEntitlements` | Customer owner/admin | Shows customer-visible licensed translations, attribution, availability, expiry, territory, and offline policy summary. |
| ACCOUNT-GQL-006 | `Mutation.accountDeactivateDevice` | Customer owner/admin | Customer-initiated safe device deactivation, audited and policy-projected. |
| ACCOUNT-GQL-007 | `Query.accountInvoices` | Customer owner/admin | Lists invoice refs/hosted URLs from the billing projection, subject to provider decision. |

### Desktop Activation And Download API

| ID | Endpoint | Auth | Notes |
|---|---|---|---|
| DESKTOP-API-001 | `POST /v1/activations` | App key plus device attestation/fingerprint | Validates key and device limit; returns signed license policy and device token if accepted. |
| DESKTOP-API-002 | `POST /v1/license:refresh` | Device token | Returns current signed license policy, entitlement manifest version, and denial/warning states. |
| DESKTOP-API-003 | `GET /v1/entitlements/manifest` | Device token | Lists active, expiring, revoked, refresh-required, and unavailable translations with attribution and policy constraints. |
| DESKTOP-API-004 | `POST /v1/downloads:prepare` | Device token | Validates entitlement and returns short-lived download lease plus package metadata/checksum. |
| DESKTOP-API-005 | `POST /v1/downloads/{lease_id}:complete` | Device token | Records checksum/result and local-store package version. |
| DESKTOP-API-006 | `POST /v1/usage-events:batch` | Device token | Batches display/download/reporting events; idempotent by event id. |

### Billing And Provider Inputs

| ID | Endpoint/job | Auth | Notes |
|---|---|---|---|
| BILLING-API-001 | `POST /webhooks/billing/{provider}` | Provider signature | Idempotent by provider event id; updates subscription projection and outbox. |
| BILLING-JOB-001 | Billing reconciliation job | Service identity | Compares provider subscription/invoice state to local projection. |
| PROVIDER-JOB-001 | Translation provider availability sync | Service identity | Updates provider health/availability without changing legal status. |
| PROVIDER-JOB-002 | Licence usage report export | Service identity | Produces provider-specific reporting package from usage events. |

## 12. Contract Rules

### Versioning

- Staff Admin GraphQL starts at `/graphql/admin`; Customer Account GraphQL starts at `/graphql/account`.
- GraphQL schema changes should be additive first. Removed fields, changed meanings, or changed authorization semantics require deprecation windows and a documented version/migration plan.
- Desktop and webhook command APIs start at `/v1`.
- Additive JSON response fields are allowed; removal/semantic changes require `/v2`.
- Desktop policy responses include `policy_version`, `manifest_version`, `issued_at`, `expires_at`, and `signing_key_id`.
- Desktop clients must treat unknown manifest fields as ignore-safe and unknown denial codes as supportable generic denial.

### Authentication And Authorization

- Staff GraphQL uses managed IdP session plus server-side role permissions. Client-hidden controls are advisory only.
- Account GraphQL uses customer-user sessions and resolver-level tenant scoping. Admin object graphs must not be exposed to customer users.
- Staff and customer GraphQL may share Django domain services, but not permission checks, schema namespaces, or tenant assumptions.
- Desktop APIs use high-entropy app key only for first activation; all later calls use a device token bound to the activation/device.
- Service-to-service jobs use short-lived service identity and least privilege.
- Billing webhooks use provider signature verification and replay-window checks.

### GraphQL Guardrails

- Strawberry schemas use typed inputs/payloads and generated frontend types. Vue Admin operations are generated from the API schema rather than handwritten loosely typed query strings.
- Resolvers enforce authorization before loading sensitive rows. Frontend route guards reduce confusion but do not count as security controls.
- Use DataLoader or equivalent batching for customer/detail screens to avoid N+1 database access.
- Apply query depth, complexity, and timeout limits to staff/customer GraphQL endpoints.
- Disable or restrict introspection in production unless the Security Reviewer approves the exposure model.
- GraphQL prepares download leases or reports; licensed package bytes are delivered through short-lived download URLs or provider/object-store mechanisms, never as GraphQL response payloads.

### Idempotency

- Mutating Admin and Account GraphQL operations require an idempotency key input and are scoped by actor id plus operation plus target. `clientMutationId` is useful for UI correlation but is not sufficient by itself.
- Activation is idempotent by key hash plus device fingerprint where retrying the same request should return the same activation result.
- Usage events are idempotent by client-generated event id and device id.
- Billing webhooks are idempotent by provider event id.

### Pagination

- GraphQL lists use Relay-style connections or equivalent opaque cursor fields with stable sort keys.
- JSON search endpoints return `next_cursor`; clients must not derive cursor structure.
- Hard maximum page size is required; recommended default 50, max 200.

### Error Taxonomy

Use stable machine codes with safe display messages:

| Code | Meaning |
|---|---|
| `UNAUTHENTICATED` | Missing/expired session or device token |
| `PERMISSION_DENIED` | Authenticated actor lacks permission |
| `VALIDATION_FAILED` | Request field invalid or missing |
| `NOT_FOUND` | Target absent or hidden to avoid tenant leak |
| `CONFLICT` | State transition/version conflict |
| `POLICY_DENIED` | Customer/subscription/policy blocks action |
| `LICENSE_KEY_EXPIRED` | App key has expired |
| `LICENSE_KEY_REVOKED` | App key was revoked |
| `DEVICE_LIMIT_EXCEEDED` | Activation exceeds device/seat limit |
| `ENTITLEMENT_REQUIRED` | Translation download requires active entitlement |
| `ENTITLEMENT_EXPIRED` | Entitlement expired |
| `ENTITLEMENT_REVOKED` | Entitlement revoked |
| `TRANSLATION_UNAVAILABLE` | Translation not published/available |
| `TERRITORY_BLOCKED` | Customer/device territory not allowed |
| `PROVIDER_UNAVAILABLE` | Upstream/provider unavailable |
| `REPORTING_REQUIRED` | Reporting hook missing for a required provider |
| `RATE_LIMITED` | Request over abuse or provider-safe limit |

## 13. Event Contracts

Use an outbox table for reliable event publication. Events are append-only facts, not direct RPC commands.

| ID | Event | Producer | Consumers |
|---|---|---|---|
| ADMIN-EVT-001 | `customer.created` | Customer Account | Audit, CRM/email later |
| ADMIN-EVT-002 | `subscription.updated` | Billing | License policy projector, audit |
| ADMIN-EVT-003 | `license_key.generated` | License-Key | Audit, expiry notifications later |
| ADMIN-EVT-004 | `license_key.activated` | Activation API | Audit, support diagnostics |
| ADMIN-EVT-005 | `license_key.revoked` | License-Key | Policy projector, support diagnostics |
| ADMIN-EVT-006 | `translation.published` | Catalogue | Entitlement validation, audit |
| ADMIN-EVT-007 | `translation.suspended` | Catalogue | Download Gateway, entitlement projector |
| ADMIN-EVT-008 | `entitlement.granted` | Entitlement | Policy projector, audit |
| ADMIN-EVT-009 | `entitlement.revoked` | Entitlement | Policy projector, download gateway, audit |
| ADMIN-EVT-010 | `download.denied` | Download Gateway | Support diagnostics, audit if sensitive |
| ADMIN-EVT-011 | `usage_event.accepted` | Usage API | Reporting aggregator |
| ADMIN-EVT-012 | `audit_event.recorded` | Audit Ledger | Export/search indexer |

## 14. Key Flows

### Activate Desktop With App Key

1. Desktop prompts for app key and derives no local entitlement from it.
2. Desktop sends `DESKTOP-API-001` with key, device fingerprint hash, app version, platform, timezone/country if allowed, and request id.
3. Activation API hashes the key, finds matching active key, checks customer, status, date, territory, seat/device limits, rate limits, and abuse flags.
4. On success, service records device activation and returns device token plus signed license policy.
5. Desktop stores device token in OS secret store and policy in encrypted local state.
6. Audit records activation result without full key.

### Generate Prospect Key

1. Staff opens Admin and calls `ADMIN-GQL-004` with customer/prospect, template, duration, features, limits, territory, and reason.
2. License-Key service generates high-entropy secret, stores hash/prefix/suffix/fingerprint, and returns full value once.
3. Audit event records actor, target, template, limits, reason, and result, excluding full key.

### Grant Licensed Bible Entitlement

1. Staff calls `ADMIN-GQL-009`.
2. Entitlement context checks customer status, translation Published state, legal fields, territory, offline policy, reporting hooks, plan/basis, dates, and permissions.
3. Entitlement is created as Active/Pending and emits `entitlement.granted`.
4. Policy projector increments entitlement manifest version.
5. Desktop sees translation on next refresh/manifest fetch.

### Licensed Download

1. Desktop calls `DESKTOP-API-003` to show available translations and policies.
2. Desktop calls `DESKTOP-API-004` for one translation.
3. Download Gateway validates device token, app policy, entitlement, translation availability, territory, provider health, quota, and reporting requirement.
4. Gateway returns a short-lived lease, package metadata, checksum, attribution, export limits, refresh interval, and deletion SLA.
5. Desktop downloads over TLS, verifies checksum, stores content in encrypted app-locked local store, and records completion via `DESKTOP-API-005`.
6. Usage/download event is batched through `DESKTOP-API-006` if required.

### Revocation

1. Staff revokes key/device/entitlement with reason and confirmation.
2. Server blocks new activations/download leases immediately.
3. Policy projector increments policy/manifest version and records revocation/deletion deadline.
4. Online desktops receive denial/refresh-required state on next check.
5. Offline desktops enforce the prior signed policy until its approved grace/refresh deadline, then disable affected licensed content until refreshed.

## 15. Failure Modes And Recovery

| Failure | User-visible result | System behaviour | Owner |
|---|---|---|---|
| Platform API down | Staff cannot manage new keys/entitlements; new activations/download leases fail | Desktop live presentation unaffected; already cached entitlements follow local policy | DevOps |
| Activation API down | New activations fail/retry | Existing activated devices continue until policy refresh/grace deadline | DevOps |
| Billing webhook delayed | Subscription projection stale | Reconciliation job repairs; policy changes lag within approved SLA | Finance/Backend |
| Provider down | New licensed downloads blocked with provider reason | Existing local content remains under signed policy; support sees provider cause | Licensing/Backend |
| Quota exhausted | Download denied with quota/provider code | No silent empty states; reporting alert emitted | Licensing |
| Entitlement revoked while device offline | New downloads blocked server-side; local device pending | Device disables/deletes on next refresh or grace deadline | Legal/Architecture |
| Signing key rotation | Old policies remain valid until expiry | Publish new signing key id; desktop accepts overlapping keys during rotation | Security |
| Duplicate request/webhook | No duplicate state transition | Idempotency key/provider event id prevents replay | Backend |
| Partial download | Resume or restart; partial package deleted on cancel | Lease status records failure; no partially trusted content is installed | Backend/Desktop |
| Audit write failure | Sensitive mutation fails closed | High-risk actions cannot commit without audit event | Security/Backend |

## 16. Security And Privacy Posture

Security review is mandatory before implementation. This section is a starter threat model, not sign-off.

| Asset | Threat | Control |
|---|---|---|
| Full app license key | Log/export/recovery leak | Show once, hash-only persistence, prefix/suffix display, redacted logs/diagnostics |
| Signing keys | Forged app/entitlement policy | KMS/HSM or equivalent custody, asymmetric signatures, rotation, audit, no app-embedded private keys |
| Device token | Stolen activation session | OS secret store, token rotation/revoke, rate limits, binding to device fingerprint where legally acceptable |
| Licensed Bible text | Unauthorized redistribution | Not bundled, entitlement-gated download, encrypted app-locked store, export/print enforcement, deletion/disable SLA |
| Provider credentials | Staff/support exposure | Secret store only, status/fingerprint display, role-limited settings, never in plaintext after entry |
| Billing data | Staff over-access/export | Finance/Admin role gating, redacted exports, audit |
| Audit log | Tampering | Append-only event table, no Admin delete path, backup, restricted export |
| Customer personal data | Excess retention/support overexposure | Role scoping, retention policy, minimised diagnostics, redacted bundles |

Recommended signing model:

- Use asymmetric signing for desktop policy envelopes. Private key lives only in server-side KMS/HSM-equivalent custody.
- Desktop stores public verification keys and accepts overlapping key ids for rotation.
- Policy envelope includes `policy_id`, `org_id`, `device_id`, `issued_at`, `expires_at`, `grace_until`, `features`, `entitlement_manifest_version`, `signing_key_id`, and `signature`.
- Exact cryptographic suite must be reviewed by Security Reviewer. Ed25519/PASETO-style signed envelopes are acceptable candidates, but this architecture does not self-approve cryptography.

## 17. Observability, SLOs, And Capacity

| Signal | Purpose | Redaction rule |
|---|---|---|
| `admin.request.count/latency/error` | API health | No full key, no Bible text |
| `activation.result` | Activation success/denial rates | Key prefix only, device hash only |
| `license_policy.refresh` | Desktop policy freshness | Org/device ids pseudonymised in aggregate metrics |
| `entitlement.grant/revoke` | Compliance and support | No full licensed text |
| `download.prepare/result` | Download diagnostics | Translation code, denial code, checksum, no content |
| `provider.availability/quota` | Provider health and cost | No provider secret |
| `usage_event.batch` | Reporting completeness | Provider token if required, no verse text unless provider contract requires and legal approves |
| `audit.write.failure` | Security reliability | No sensitive payload |

Initial SLO proposals for review:

- Admin read APIs p95 <= 500 ms for common filters up to 100k keys.
- Key generation p95 <= 2 seconds after validation.
- Activation p95 <= 1 second excluding network.
- Download lease prepare p95 <= 1 second when provider/package metadata is warm.
- Policy revocation visible to online devices within 5 minutes, or an approved SLA per release.
- Audit write success for sensitive actions: 100 percent or action fails closed.

Capacity assumptions:

- First slice should comfortably handle 100k app keys, 25k customer orgs, 250k activations, and millions of download/usage events with partitioning/archival planned.
- Usage/download/reporting events should be write-optimised and batchable.
- Search indexes must be designed for support workflows, not retrofitted after launch.

## 18. Deployment, Secrets, Backup, And Recovery

Deployment topology:

- Admin Web App (`implementation/admin`) and Platform API (`implementation/api`) can deploy together at first, but their source roots remain separate.
- Worker process handles provider sync, billing reconciliation, report generation, expiration jobs, and outbox delivery.
- Database is managed relational storage with point-in-time recovery.
- Package/object store holds licensed translation packages only where legal/provider terms permit.
- Separate environments: local/dev, staging, production. Production data must not be cloned to lower environments without anonymisation.

Secrets:

- Staff IdP client secrets, billing webhook secrets, provider credentials, signing private keys, and object-store credentials live in managed secret custody.
- Support can see provider status/fingerprint, never secrets.
- Desktop stores device token and local content keys in OS secret store or existing secure fallback.

Backup and disaster recovery:

- Daily backups plus point-in-time recovery for relational store.
- Object/package store versioning where permitted, with delete/revoke workflows respecting legal terms.
- Audit log backup is release-blocking because sensitive actions must remain explainable.
- Recovery drill required before production launch: restore database, restore package metadata, verify no revoked entitlement becomes active.

Rollback:

- Schema migrations must be forward-only with pre-migration backups, matching ADR-0007 discipline.
- Feature flags for provider adapters, billing automation, and licensed-download publication.
- Rollback must never re-enable a revoked key/entitlement; revocation state is monotonic.

## 19. Migration And Compatibility Strategy

No existing Admin data needs migration because the Admin Console is not implemented.

Future desktop compatibility:

- Existing public-domain bundled translations remain available with no account.
- Licensed translation flows are additive and feature-gated by signed policy.
- Older desktop builds that do not understand entitlement manifests should see licensed translations as unavailable, not fail open.
- Desktop local store for licensed content should be a new encrypted namespace/table/package path so public-domain scripture remains unchanged.

Backfill:

- If manual customer/key spreadsheets exist outside the repo, import must be a controlled Admin bulk import with validation preview and per-row results.
- Imported historical keys cannot recover full plaintext key values unless the source has them; prefer issuing replacements.
- Historical billing subscriptions import from chosen provider or manual arrangement records.

## 20. Implementation Sequence

No ClickUp implementation tasks are created in this architecture pass. Recommended later sequence after product/security/legal gates:

1. Security + architecture spike: signing envelope, key custody, device token model, and threat model for Admin Licensing Platform.
2. Backend foundation: Django project under `implementation/api`, modular apps/contexts, Strawberry schema split, staff IdP integration, RBAC middleware, audit ledger, database migrations, outbox.
3. Customer/account slice: customer orgs, contacts, notes, search, customer detail projection.
4. App license-key slice: templates, key generation, hash/mask, activation API, device activation, signed policy envelope.
5. Billing context slice: manual arrangements first, then provider webhook/reconciliation after billing provider decision.
6. Translation catalogue slice: legal fields, availability states, provider settings, compliance gates.
7. Entitlement slice: grant/revoke with validation, manifest projection, desktop entitlement manifest contract.
8. Download gateway slice: prepare/complete leases, encrypted local-store integration, diagnostics.
9. Usage/reporting slice: batched usage events, provider reports, export permissions.
10. Admin UI implementation under `implementation/admin`: Vue 3 shell integration, generated GraphQL types/operations, Licenses, Subscriptions, Support, Settings, Audit Log, and states from UX handoff.
11. Independent Security Review.
12. QA test strategy and exploratory support-flow testing.

## 21. Open Decisions, Risks, And Required Reviews

| ID | Decision/risk | Owner | Implementation impact |
|---|---|---|---|
| ARCH-OD-001 | Staff IdP and MFA policy | Security/Product | Blocks staff auth implementation |
| ARCH-OD-002 | Billing provider and subscription source of truth | Product/Finance | Blocks automated billing/refund slice |
| ARCH-OD-003 | Hosting platform/database/object store | DevOps/Architecture | Blocks deploy/runbook details |
| ARCH-OD-004 | Exact signing envelope and key custody | Security/Architecture | Blocks activation/policy implementation |
| ARCH-OD-005 | First licensed translations and provider route | Product/Legal | Blocks catalogue publication and real downloads |
| ARCH-OD-006 | Offline grace, refresh, deletion SLA per translation | Legal/Product/Architecture | Blocks local licensed store policy |
| ARCH-OD-007 | Retention for audit, activation, download, support, billing events | Legal/Security | Blocks data retention jobs |
| ARCH-OD-008 | Whether Support can extend keys and limits | Product/Support/Security | Affects RBAC/policy |
| ARCH-OD-009 | Whether usage reports require verse-level content or metadata only | Legal/Licensing | Affects privacy and reporting payloads |
| ARCH-OD-010 | Admin GraphQL client/cache library and generated-types workflow | Frontend/Architecture | Affects Vue 3 data layer and operation versioning |

Required next reviews:

- `$security-reviewer`: threat model for Admin staff auth, signing keys, key generation, device tokens, entitlements, downloads, audit, impersonation, exports.
- `$backend-engineer`: API/data feasibility and implementation planning after product gate.
- `$ui-ux-designer`: Figma frames for missing Admin screens if visual approval is required before build.
- `$qa-engineer`: risk-based test strategy for activation, revocation, downloads, support diagnostics, and permission boundaries.
- `$devops-engineer`: hosting, secrets, backups, observability, deployment, rollback.

## 22. Gate Notes And Pending ClickUp Update

ClickUp read/search/comment-read tools worked for task `86ajnx548`, but `_clickup_create_task_comment` returned `INVALID_ARGUMENT` when posting the architecture start comment, original final handoff, and the 2026-08-08 stack/path refinement handoff. Prior PM/UX goals observed the same create-comment failure. Do not claim ClickUp was updated until the connector succeeds.

Pending ClickUp final update text:

`Architecture handoff ready for review: docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md and docs/architecture/adr/ADR-0021-admin-licensing-services.md. Goal GOAL-arch-admin-licensing reached GATE_REVIEW after stack/path refinement. Scope covers Vue 3 Admin under implementation/admin, Django + Strawberry Platform API under implementation/api, staff/customer GraphQL surfaces, desktop licensing/download command APIs, account, billing, app license-key, Bible catalogue, entitlement, licensed-download, support diagnostics, audit, deployment, security/privacy, observability, migration, rollback, and implementation sequence. No production code or duplicate Markdown tickets created. ClickUp create-comment still fails with INVALID_ARGUMENT if this update cannot post, so this text is recorded in repo evidence.`
