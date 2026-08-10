# SelahCue - Admin Licensing Security Review

Version: 0.1 gate draft  
Date: 2026-08-08  
Reviewer: Security Reviewer  
Status: Gate review - design-time review, not release sign-off  
Goal Contract: `docs/delivery/goals/GOAL-sec-admin-licensing.md`  
Related Architecture: `docs/architecture/ADMIN-LICENSING-ARCHITECTURE.md`  
Related ADR: `docs/architecture/adr/ADR-0021-admin-licensing-services.md`  
ClickUp Build Control: `https://app.clickup.com/t/86ajnx548`

> This review assesses the current Admin Licensing Platform architecture before code exists. It identifies implementation-blocking controls and design findings. It does not approve production release, legal rights, cryptographic details, penetration testing, or risk acceptance.

## 1. Verdict

**Pre-implementation security verdict: Pass with Required Controls.**

The architecture can proceed into detailed backend/frontend planning only if the required controls in sections 9 through 15 become explicit acceptance criteria for the implementation tasks. The design is not ready for production, and any release security verdict remains **Not Assessed** until code, deployment configuration, tests, and operational runbooks exist.

Release-blocking themes:

- Staff/customer GraphQL must enforce resolver-level authorization, object-level authorization, and tenant isolation across separate schema namespaces.
- Staff authentication, MFA, session policy, CSRF, CORS, CSP, secure cookies, and production GraphQL defaults must be decided before implementation.
- App license keys, device tokens, download leases, and signed policy envelopes need Security/Architecture-owned cryptographic and key-custody decisions.
- Licensed Bible text must never appear in logs, GraphQL payloads beyond approved metadata, reports, diagnostics, exports, public URLs, or the installer.
- Audit must fail closed for sensitive mutations and remain append-only, searchable, redacted, backed up, and permissioned.
- Legal/Product must approve first translations, territories, offline grace, deletion SLA, export/print limits, reporting payloads, and retention before live entitlements/downloads.

## 2. Evidence Labels

- **Verified:** directly observed in repository docs, code, ClickUp, or official current documentation.
- **Inferred:** supported by verified evidence but not directly observed as implemented behaviour.
- **Assumed:** used for this review; owner must confirm before implementation.
- **Unknown:** unresolved and decision-relevant.

## 3. Reviewed Evidence

| Evidence | Label | Security relevance |
|---|---|---|
| Admin architecture version 0.2 defines Vue 3 Admin under `implementation/admin`, Django + Strawberry Platform API under `implementation/api`, `/graphql/admin`, `/graphql/account`, desktop `/v1` command APIs, billing/provider webhooks, outbox, audit, and download gateway. | Verified | Defines entry points, trust boundaries, assets, and control assumptions. |
| ADR-0021 records the hosted modular Admin Licensing Platform and stack/source-root decision. | Verified | Establishes the shared service and GraphQL/command API split. |
| Admin PRD requires staff IdP, server-side RBAC, reason capture, confirmations, controlled impersonation, key masking, entitlements, provider secrets, audit, exports, and retention owner decisions. | Verified | Provides security requirements and business rules. |
| UX handoff defines permission-denied states, high-risk confirmations, support remediation, audit redaction, secret-fingerprint display, and missing Admin screens. | Verified | Shows where staff might perform dangerous operations. |
| ADR-0017 and licensing research require entitlement-gated post-activation downloads, encrypted app-locked local storage, attribution, export limits, refresh/deletion rules, reporting, and no installer bundling for copyrighted translations. | Verified | Defines licensed Bible text constraints. |
| Existing desktop architecture uses SQLite/SQLCipher-ready persistence, LAN TLS/pinning/RBAC/device tokens, and local-first redacted observability. | Verified | Existing controls should be reused for desktop license agent and local store. |
| No Admin frontend or Django Platform API code exists yet. | Verified | Findings are design findings, not confirmed implementation vulnerabilities. |
| Django and Strawberry official docs expose built-in CSRF/security and GraphQL extension/permission/deployment hooks, but those controls must be explicitly wired. | Verified 2026-08-08 | Confirms the stack can support required controls. |
| Staff IdP, customer identity, billing provider, hosting, KMS/secrets provider, object store, exact signing suite, first licensed translations, and retention periods are unresolved. | Unknown | Blocks production-grade security design. |

## 4. Assets

| ID | Asset | Data class | Why it matters |
|---|---|---|---|
| A-01 | Staff sessions, staff roles, MFA/IdP links | Security-sensitive personal data | Compromise grants internal control-plane access. |
| A-02 | Customer organisations, contacts, users, notes, support cases | Customer personal/support data | Privacy, support integrity, tenant isolation. |
| A-03 | Billing status, invoice refs, provider customer/subscription refs | Financial/customer data | Payment state can grant or revoke access. |
| A-04 | App license-key full secret, hash, prefix/suffix, templates | Highly sensitive access credential | Full key exposure enables unauthorized activation. |
| A-05 | Device activations, device token, fingerprint hash, policy freshness | Security-sensitive device data | Controls seats/devices, revocation, support diagnostics. |
| A-06 | Signing private keys and public verification keys | Critical secret material | Forged policy enables paid features/licensed text. |
| A-07 | Signed app policy and entitlement manifest | Authorization artifact | Desktop relies on it offline. |
| A-08 | Translation catalogue and licence constraints | Legal/commercial data | Determines what can be offered, cached, exported, reported. |
| A-09 | Translation entitlements | Commercial/licensing authorization | Controls customer access to licensed translations. |
| A-10 | Download leases and package metadata/checksums | Security-sensitive access artifact | Controls short-lived licensed content download. |
| A-11 | Licensed Bible text packages/local store | Copyrighted content | Redistribution and export violations are high-impact. |
| A-12 | Provider credentials and billing webhook secrets | Critical secrets | Exposure compromises integrations and reporting. |
| A-13 | Usage/reporting events and provider reports | Licence-reporting data | Must be sufficient for rights holders without over-collecting. |
| A-14 | Audit events and internal notes | Security/compliance data | Tampering destroys accountability. |
| A-15 | Exports, diagnostics, support bundles | Mixed sensitive data | High leakage risk if redaction fails. |
| A-16 | Outbox and background job state | Operational integrity data | Duplicate or lost jobs can corrupt billing/entitlement state. |

## 5. Actors And Privileges

| Actor | Expected access | Security concern |
|---|---|---|
| Owner/Admin staff | Broad configuration, staff, customer, key, entitlement, export access | Self-escalation, destructive changes, over-broad export. |
| Sales/Partnership staff | Prospect/trial key workflows | Over-issuing keys, promising unavailable translations. |
| Support staff | Diagnostics and safe remediation | Over-granting, sensitive data overexposure, unsafe extension of access. |
| Finance staff | Billing/refund/subscription workflows | Payment-state tampering, financial data leakage. |
| Licensing/Compliance staff | Translation catalogue, entitlements, reports | Publishing without legal fields, report over-collection. |
| Read-only staff | Inspect records and non-sensitive IDs | Hidden-field leakage through GraphQL. |
| Customer owner/admin | Own organisation, devices, invoices, entitlements | Cross-tenant access and unauthorized self-service escalation. |
| Desktop license agent | Activation, policy refresh, manifest, downloads, usage events | Replay, fake device, stolen key/token, abuse of offline grace. |
| Billing provider | Webhook delivery and reconciliation source | Forged/duplicate/out-of-order events. |
| Translation provider/object store | Package/feed availability and usage reporting | Provider outage, wrong package, terms mismatch. |
| Background worker/service job | Outbox, expiry, reconciliation, report jobs | Excess privilege, duplicate processing, secret exposure. |
| External attacker | Internet-facing attack surface | Credential stuffing, GraphQL DoS, IDOR, webhook spoofing. |
| Malicious/compromised staff | Insider threat | Misuse of entitlements, exports, impersonation, audit tampering. |

## 6. Entry Points, Boundaries, And Data Classification

| Boundary | Entry point | Data crossing | Required posture |
|---|---|---|---|
| Staff browser to Platform API | `POST /graphql/admin` | Staff session, customer data, keys metadata, entitlements, audit, exports | HTTPS, CSRF protection for cookie sessions, strict Origin/CORS, server-side RBAC, resolver-level checks, query limits. |
| Customer browser to Platform API | `POST /graphql/account` | Customer session, org billing/devices/entitlements | Separate schema/context, tenant scoping, no Admin graph exposure. |
| Desktop to Platform API | `/v1/activations`, `/v1/license:refresh`, `/v1/entitlements/manifest`, `/v1/downloads:*`, `/v1/usage-events:batch` | App key, device token, policy, leases, manifest, usage metadata | HTTPS, idempotency, anti-replay, rate limits, signed responses, stable error taxonomy. |
| Billing provider to Platform API | `/webhooks/billing/{provider}` | Provider events, customer/subscription/invoice refs | Signature verification, replay window, event-id idempotency, reconciliation. |
| Provider adapter to translation provider/object store | Background jobs or signed URL issuance | Provider secrets, package metadata, checksums, usage reports | Least-privilege service identity, secret custody, checksum verification, no public bearer entitlement. |
| Platform API to database/object store | ORM/repository access | All server-side state and licensed packages | Parameterized ORM, tenant-aware repositories, encryption, backups, row/object-level authorization. |
| Platform API to audit/outbox | Sensitive action facts and jobs | Actor, reason, target, result, event payloads | Append-only, idempotent, redacted, tamper-evident where feasible. |
| Admin exports to staff machine | CSV/PDF/report bundles | Customer, audit, billing, usage/reporting data | Explicit permission, minimization, watermark/manifest, audit, expiry, redaction. |

Data handling baseline:

- Full app keys, signing private keys, provider credentials, billing webhook secrets, device tokens, and object-store credentials are **Critical Secret**.
- Licensed Bible text is **Restricted Copyright Content**.
- Customer contacts, billing data, support notes, device fingerprints, IP/country where collected, and audit events are **Sensitive Customer/Security Data**.
- Aggregated metrics and provider health are **Internal Operational Data** and still must avoid keys, secrets, full Bible text, and unnecessary personal data.

## 7. Threat Matrix

| ID | STRIDE | Threat | Assets | Severity | Impact | Likelihood | Required controls |
|---|---|---|---|---|---|---|---|
| SEC-ADM-T01 | Spoofing | Staff session theft or weak IdP/MFA lets attacker access `/graphql/admin`. | A-01..A-15 | Blocker | Full internal control-plane compromise. | Medium until IdP/MFA known. | Managed IdP, MFA, short session TTL, secure cookies, session revocation, audit, impossible account enumeration. |
| SEC-ADM-T02 | Elevation | Staff UI hides an action, but GraphQL resolver permits it. | A-04, A-09, A-14 | Blocker | Unauthorized key/entitlement/billing/export changes. | High if controls are frontend-only. | Server-side permission checks on every query/mutation/field, deny by default, permission tests. |
| SEC-ADM-T03 | Information disclosure | Customer Account GraphQL can traverse Admin object graph or another tenant's records. | A-02, A-03, A-05, A-09, A-14 | Blocker | Cross-tenant data breach and entitlement leakage. | Medium in shared schema/service designs. | Separate `/graphql/admin` and `/graphql/account` schemas, tenant-scoped repositories, object-level checks on nodes and edges. |
| SEC-ADM-T04 | Denial of service | Deep, aliased, batched, or unbounded GraphQL queries exhaust API/database resources. | A-16, availability | High | Admin/account/API outage; activation/download support degraded. | High without GraphQL limits. | Depth, alias/token/count limits, max page size, query cost/timeouts, DataLoader, rate limits, production GraphiQL/introspection policy. |
| SEC-ADM-T05 | Tampering | Mutating GraphQL/desktop commands replay or double-submit state changes. | A-04, A-05, A-09, A-16 | High | Duplicate grants, duplicate webhooks, inconsistent billing/entitlement state. | Medium. | Idempotency keys scoped by actor/operation/target, request id, provider event id, outbox idempotency, conflict detection. |
| SEC-ADM-T06 | Information disclosure | Full license keys appear in logs, audit, diagnostics, exports, or support views. | A-04, A-15 | Blocker | Unauthorized app activations and customer trust breach. | Medium unless redaction is allowlist-based. | Show once, hash-only storage, prefix/suffix display, no recovery plaintext, redaction tests. |
| SEC-ADM-T07 | Tampering | Weak app-key generation or storage permits guessing, offline cracking, or recovery. | A-04 | Blocker | Unauthorized paid/trial access at scale. | Unknown until design exists. | CSPRNG, sufficient entropy, secret hash with slow or keyed design reviewed by Security, rate limits, abuse detection. |
| SEC-ADM-T08 | Spoofing/Elevation | Stolen app key or device token activates fake device or refreshes policy. | A-05, A-07, A-09 | High | Device-limit bypass and licensed text exposure. | Medium. | Device-bound activation, token rotation/revocation, rate limits, safe fingerprinting, signed policy with expiry/grace. |
| SEC-ADM-T09 | Tampering | Forged signed policy or compromised signing private key grants features/entitlements offline. | A-06, A-07, A-11 | Blocker | Catastrophic license bypass and Bible-content exposure. | Low with KMS/HSM, high if app/server stores raw key. | Server-side KMS/HSM-equivalent custody, asymmetric signatures, key rotation, key-id overlap, no private keys in app or logs. |
| SEC-ADM-T10 | Information disclosure | Licensed Bible text is served through public URLs, GraphQL payloads, logs, exports, or cache paths. | A-11, A-15 | Blocker | Copyright breach and contractual violation. | Medium unless content path is isolated. | GraphQL returns lease metadata only, short-lived device-scoped URLs, checksum, app-locked local store, no content logs/exports. |
| SEC-ADM-T11 | Tampering | Download package is swapped, stale, or incomplete but accepted by desktop. | A-10, A-11 | High | Wrong/corrupt text, malicious package, reporting mismatch. | Medium. | Package version, checksum/signature, complete callback, partial delete, provider metadata pinning, legal-state recheck. |
| SEC-ADM-T12 | Repudiation | Sensitive mutation commits but audit write fails or omits actor/reason/result. | A-14 | Blocker | No accountability for grants, revocations, refunds, exports, impersonation. | Medium. | Audit transaction or fail-closed mutation, append-only storage, reason required, redacted before/after, request id. |
| SEC-ADM-T13 | Elevation/Information disclosure | Impersonation exposes customer data or permits untraceable customer actions. | A-02, A-03, A-09, A-14 | High | Insider misuse and privacy breach. | Medium if not time-bound. | Owner/Admin-only, explicit reason, persistent banner, scoped duration, no sensitive export during impersonation unless separately authorized, audit all viewed/changed records. |
| SEC-ADM-T14 | Spoofing/Tampering | Billing webhook is forged, replayed, duplicated, or processed out of order. | A-03, A-09, A-16 | High | Unauthorized paid access or wrongful suspension. | Medium. | Provider signature, timestamp/replay window, event id idempotency, reconciliation, monotonic subscription projection. |
| SEC-ADM-T15 | Tampering | Provider availability sync changes legal status or grants customer access. | A-08, A-09 | High | Translation becomes available without legal approval. | Medium. | Provider adapter may update availability only, not legal/published/customer grants; legal fields required before publish. |
| SEC-ADM-T16 | Information disclosure | Provider credentials, billing secrets, or signing-key fingerprints are overexposed to Support/Admin UI. | A-06, A-12 | Blocker | Integration compromise. | Medium. | Secret store only, display status/fingerprint, role-limited rotation, no plaintext after entry. |
| SEC-ADM-T17 | Information disclosure | Usage reports over-collect verse text, customer personal data, or device identifiers. | A-13, A-02, A-05, A-11 | High | Privacy breach and legal exposure. | Unknown until provider terms are known. | Provider-specific minimization, legal-approved payloads, pseudonymous IDs where possible, no verse text unless explicitly required and approved. |
| SEC-ADM-T18 | Denial of service | Activation/download brute force or key-prefix enumeration stresses service or leaks valid key patterns. | A-04, A-05 | High | Abuse, credential discovery, support noise. | Medium. | Per-IP/key-prefix/device/org rate limits, generic errors where needed, lockouts/cooldowns, anomaly alerts. |
| SEC-ADM-T19 | Tampering | Rollback or migration re-enables revoked keys/entitlements. | A-04, A-09 | Blocker | Revoked access returns; licensed content exposure. | Medium during early migrations. | Monotonic revocation state, forward-only migrations, rollback guard tests, restore drill. |
| SEC-ADM-T20 | Information disclosure | Diagnostics/support bundles include full keys, provider secrets, full Bible text, internal notes, or excessive customer data. | A-02, A-04, A-11, A-12, A-15 | High | Privacy/licensing incident. | Medium. | Allowlist export serialization, redaction tests, permissioned export, manifest of included fields, audit every export. |
| SEC-ADM-T21 | Tampering/Elevation | Background worker runs with broad privileges and processes poisoned outbox payloads. | A-12, A-16 | High | Unauthorized provider/billing/download actions. | Medium. | Typed outbox schema, least-privilege service identities, payload validation, retry caps, dead-letter review, audit. |
| SEC-ADM-T22 | Information disclosure | Production GraphQL debug errors, suggestions, GraphiQL, or introspection reveal internal fields. | A-01..A-15 | Medium | Reconnaissance and targeted abuse. | High if defaults not changed. | Disable debug stack traces, disable GraphiQL in production, restrict introspection, sanitize errors. |
| SEC-ADM-T23 | Tampering | Staff uploads/imports customer/key data with formula injection, CSV injection, oversized batches, or malformed rows. | A-02, A-04, A-14 | Medium | Export attacks, bad records, audit confusion. | Medium if bulk import ships. | Preview, per-row validation, max rows, escaped exports, no formula-leading output, audit. |
| SEC-ADM-T24 | Privacy | Retention/deletion period is missing or too broad for audit, billing, activation, download, support, and usage data. | A-02, A-03, A-05, A-13, A-14 | High | Regulatory/customer trust risk. | High until Legal/Security decides. | Data-class retention table, deletion/anonymization jobs, legal holds, customer export/delete policy. |

## 8. Abuse Cases

1. A read-only staff user edits a GraphQL mutation manually and tries `adminGrantEntitlement`.
2. A customer owner uses GraphQL global IDs from one org against another org.
3. A staff session is CSRFed into generating a trial key or exporting audit data.
4. A script sends one GraphQL request with hundreds of aliased customer lookups to bypass per-request rate limiting.
5. A leaked prospect key is brute-forced across device fingerprints until a policy is issued.
6. A stolen device token refreshes entitlement manifests after customer cancellation.
7. A billing webhook replay reactivates a cancelled subscription.
8. A provider-sync job marks a translation provider-available and accidentally bypasses legal publication gates.
9. A support user extends access for an urgent Sunday issue beyond their allowed limit.
10. A diagnostics export includes a full key or licensed Bible text snippet.
11. A rollback restores database state before an entitlement revocation.
12. An attacker swaps a download package after lease preparation but before desktop install.

## 9. Required Secure-Design Controls

These are release-blocking for any implementation slice that touches the relevant surface.

### Auth, Sessions, CSRF, CORS, And Headers

- Use a managed IdP with MFA for staff. Staff IdP/MFA policy is a Security/Product decision before build.
- Use short-lived staff sessions with secure, HttpOnly, SameSite cookies where cookie sessions are used.
- Keep CSRF protection enabled for cookie-authenticated GraphQL mutations and admin/account command surfaces. Django's CSRF middleware provides Origin/referer checks under HTTPS and cookie/token validation, but the view must not be exempted casually.
- Configure `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS, secure host validation, clickjacking protection, content-type nosniff, and a CSP appropriate to the Vue Admin bundle.
- Restrict CORS to approved Admin/account origins. Do not use wildcard origins with credentialed requests.
- For token-auth desktop `/v1` APIs, separate them from browser session surfaces and do not let browser cookies authenticate desktop command APIs.

### Staff RBAC And Customer Tenant Isolation

- Maintain one server-side permission matrix for staff actions and GraphQL fields.
- Enforce permissions in resolvers and domain services, not just route guards or hidden buttons.
- Separate staff and customer schema namespaces and authorization contexts.
- Use tenant-scoped repository methods that require actor, org, permission, and target. Avoid ad hoc ORM calls in resolvers.
- Check authorization on both edges and nodes, especially global IDs, nested GraphQL fields, audit/event detail, support notes, invoice refs, devices, and entitlements.
- Add tests that unauthorised staff and cross-tenant customers receive non-success results without target leakage.

### GraphQL-Specific Controls

- Disable GraphiQL in production and restrict or disable introspection for untrusted users.
- Apply query depth, alias/count/token, page-size, operation-count, batching, timeout, and rate limits.
- Use DataLoader or equivalent batching to avoid N+1 queries without bypassing authorization checks.
- Sanitize GraphQL errors. Stable error `extensions.code` values are useful; stack traces, internal model names, and secret-bearing values are not.
- Disable multipart uploads unless a later feature explicitly needs them and receives a separate file-upload threat model.
- Generate Vue client types/operations from the schema, but treat generated types as client ergonomics only, not authorization.
- Use explicit typed mutation payloads with idempotency key input, reason capture where required, and safe redaction.

### Keys, Tokens, Signing, And Revocation

- Generate app keys with a CSPRNG and sufficient entropy. Key format should include human-friendly prefix only; prefix must not reduce secret entropy.
- Persist only hash/fingerprint/prefix/suffix. Full key is shown once and never stored recoverably unless Security approves a separate recovery mechanism.
- Rate-limit key activation by IP, key prefix/hash, org, and device fingerprint where lawful.
- Device tokens must be random, revocable, rotated on risk events, and stored in OS secret storage on the desktop.
- Signed policy envelopes must use asymmetric signatures. Private keys stay in server-side KMS/HSM-equivalent custody; public keys and key IDs are safe for desktop verification.
- Revoked key, device, or entitlement state is monotonic and cannot be undone by restore, retry, rollback, or stale provider events without explicit Owner/Admin action and audit.

### Licensed Downloads And Content Handling

- GraphQL may create/inspect leases but must never return licensed package bytes.
- Download URLs/leases are short-lived, single-device, single-entitlement, package-version/checksum bound, and useless after expiry or revocation.
- Desktop verifies checksum/signature before installing content and deletes partial packages on failure.
- Licensed content is stored in a separate encrypted app-locked local store, distinct from public-domain bundled content.
- Export/print/copy limits are enforced by the desktop using signed policy and translation constraints.
- New downloads stop immediately on revocation; offline local use follows the legal-approved grace/deletion policy only.

### Webhooks, Providers, Workers, And Outbox

- Verify billing webhook signatures, timestamp/replay windows, and event IDs before state changes.
- Provider adapters can update availability/health and package metadata, but cannot publish legal status or create entitlements.
- Use typed outbox events with idempotency keys, retry caps, dead-letter review, and least-privilege service identity.
- Reconciliation jobs repair missed/delayed provider events without reactivating revoked state.
- Report jobs must validate provider terms and legal-approved payloads before export.

### Audit, Diagnostics, And Exports

- Sensitive mutations fail closed if audit cannot be written.
- Audit records include actor, role, target, source surface, request id, reason, before/after where safe, result, and timestamp.
- Audit records are append-only from Admin UI. Any correction is a new event.
- Export actions require explicit permission, reason where appropriate, redaction, watermark/manifest, retention class, and audit.
- Diagnostics bundles use allowlist serialization. Do not post-process scrub arbitrary blobs as the primary redaction mechanism.

## 10. Privacy And Compliance Review

| Data area | Risk | Required control |
|---|---|---|
| Customer/org/user data | Cross-tenant exposure or unnecessary support visibility | Tenant scoping, role-limited support views, minimised diagnostics. |
| Billing data | Financial privacy and provider reference leakage | Finance/Admin gating, redacted exports, provider-hosted invoice links only where approved. |
| Device/IP/country data | Personal data depending on jurisdiction | Collect only where legally allowed and necessary for abuse/licensing; retention owner required. |
| Full license keys | Credential leakage | Show once, never log/export, hash-only persistence. |
| Provider credentials and signing keys | Secret exposure | Managed secret custody, fingerprint/status display only, no plaintext after entry. |
| Licensed Bible text | Copyright breach | No installer bundling, no logs/exports/support bundles, encrypted app-locked store, entitlement-gated downloads. |
| Usage/reporting events | Over-collection | Provider-specific payload minimization, legal approval before verse-level or user/device-level reporting. |
| Audit events | Over-retention or under-retention | Retention schedule by event class, legal hold support, restricted export. |
| Impersonation | Customer data exposure | Time-bound, bannered, reasoned, audited, role-limited, export-restricted. |
| Support notes | Sensitive pastoral/customer context | Append-only/versioned, internal-only, role-scoped, retention owner required. |

Open privacy decisions before implementation:

- Retention periods for staff sessions, activation attempts, device records, support notes, audit, download/usage events, invoices, exports, and provider reports.
- Whether IP/country/device fingerprint collection is necessary and lawful for the supported customer regions.
- Whether provider reporting requires verse-level text, reference metadata only, or customer/device identifiers.
- Customer-facing terms for offline grace, revocation, deletion, export/print limits, and third-party provider handling.

## 11. Design Findings

| ID | Severity | Finding | Evidence | Impact | Remediation | Verification |
|---|---|---|---|---|---|---|
| SEC-ADM-F01 | Blocker | Shared Django domain services create a cross-schema tenant-isolation risk. | Architecture uses `/graphql/admin` and `/graphql/account` on same Platform API. | Customer users or lower staff roles may access Admin-only or other-tenant data. | Separate schemas/contexts, tenant-scoped repository APIs, resolver/service authorization, node/edge checks, cross-tenant tests. | Backend security tests for every query/mutation and global ID path. |
| SEC-ADM-F02 | Blocker | Staff IdP, MFA, session policy, CSRF/CORS/CSP and cookie settings are unresolved. | Architecture marks IdP/hosting unknown; stack is Django/GraphQL. | Staff account compromise or CSRF can generate keys, grants, exports, or refunds. | Decide IdP/MFA and security headers before build; keep Django CSRF active for cookie-auth GraphQL; restrict CORS and production origins. | Integration tests for CSRF, SameSite, Origin/CORS, HSTS/security headers, session expiry/revocation. |
| SEC-ADM-F03 | Blocker | App-key cryptography and storage design is not final. | Architecture says high-entropy/hash-only but exact design is pending Security. | Guessable or recoverable keys allow unauthorized activation. | Security-approved key format, entropy, hashing/fingerprint design, rate limits, show-once flow, redaction tests. | Unit/property tests for key entropy/format, no plaintext persistence/logging, activation abuse throttling. |
| SEC-ADM-F04 | Blocker | Signing-key custody and policy envelope suite are not final. | Architecture says KMS/HSM-equivalent and candidate Ed25519/PASETO-style envelope only. | Forged or stale policies can unlock features/licensed content offline. | ADR or security appendix for suite, envelope fields, KMS/HSM custody, rotation, revocation, clock skew, desktop verification. | Cryptographic design review, policy verification tests, rotation/revocation tests. |
| SEC-ADM-F05 | Blocker | Licensed Bible content path needs stricter no-content-in-GraphQL/logs/export constraints. | Architecture says GraphQL prepares leases, package bytes elsewhere; PRD forbids bundled copyrighted text. | Copyright breach and contractual incident. | Explicit content-boundary tests, no package bytes in GraphQL, signed short-lived URLs, checksum, local encrypted store, export/print policy tests. | Tests assert no full text in GraphQL/admin logs/diagnostics/exports and desktop rejects invalid package/checksum. |
| SEC-ADM-F06 | High | GraphQL DoS and batching controls are implementation-critical. | Architecture requires query depth/complexity but no implementation exists. | Staff/account API outage; database load; brute-force amplification. | Depth, alias/token/operation, max page size, timeout, query cost where needed, DataLoader, per-actor/IP rate limits. | Load/abuse tests with deep/aliased/batched queries and large pagination requests. |
| SEC-ADM-F07 | High | Billing and provider webhooks can corrupt entitlement state if ordering/idempotency is weak. | Architecture uses provider event id and reconciliation but provider unknown. | Wrongful grants/suspensions, stale paid state, audit mismatch. | Provider-specific signature verification, timestamp/replay windows, event store, monotonic projection, reconciliation. | Replay/duplicate/out-of-order webhook tests per provider adapter. |
| SEC-ADM-F08 | High | Support remediation can over-grant access under pressure. | PRD allows limited support extensions and safe remediation; limits unresolved. | Unauthorized paid access or licensed content exposure. | Hard-coded policy limits, permission matrix, reason capture, approval thresholds, support playbook. | Permission tests and workflow tests for Support vs Admin/Owner actions. |
| SEC-ADM-F09 | High | Usage/reporting payload could over-collect personal data or verse text. | Provider reporting requirements unknown. | Privacy breach and licensing non-compliance. | Legal-approved per-provider report schemas and minimization before report jobs ship. | Report fixture tests prove only approved fields are included. |
| SEC-ADM-F10 | High | Retention/deletion policy is unresolved. | Architecture and PRD list retention as open decision. | Privacy/regulatory risk and inconsistent support/audit retention. | Retention table by data class, deletion/anonymization jobs, legal hold model, export expiry. | Data lifecycle tests and runbook review before production. |
| SEC-ADM-F11 | Medium | Production GraphQL defaults can leak schema/error detail. | Strawberry docs require deployment choices; architecture mentions introspection policy. | Reconnaissance and targeted field probing. | Disable GraphiQL, restrict/disable introspection, sanitize errors, no stack traces. | Production settings test and smoke check. |
| SEC-ADM-F12 | Medium | Bulk import/export formula injection and CSV injection are not yet specified. | PRD includes bulk generation/import style workflows and exports. | Staff machine compromise or corrupted records. | Escape spreadsheet-leading characters, validate imports, cap rows, preview, audit. | Import/export fixture tests. |

## 12. Implementation Verification Requirements

Backend implementation under `implementation/api` must include:

- Permission tests for every `ADMIN-GQL-*` and `ACCOUNT-GQL-*` operation.
- Cross-tenant negative tests for customer/account queries, nodes, nested fields, devices, invoices, entitlements, audit, and support data.
- CSRF/CORS/secure-cookie/security-header tests for browser GraphQL endpoints.
- GraphQL depth/alias/token/page-size/rate-limit abuse tests.
- Idempotency tests for staff/customer mutations, activation, download complete, usage batch, and billing webhooks.
- Key generation tests proving no full key is persisted or logged.
- Signed policy tests for expiry, grace, rotation, invalid signature, revoked entitlement, and older desktop compatibility.
- Webhook replay/duplicate/out-of-order tests.
- Audit fail-closed tests for key generation, revocation, entitlement grant/revoke, refund/cancel, impersonation, export, and provider-secret changes.
- Redaction tests for logs, diagnostics, support bundles, audit exports, and licence reports.

Frontend implementation under `implementation/admin` must include:

- Route guards and permission-limited states, while documenting that server checks are authoritative.
- Persistent impersonation banner and export restrictions during impersonation.
- Safe-action focus for high-risk dialogs, type-to-confirm where required, and required reason capture.
- No full key display outside the generated-success flow.
- No storage of secrets, tokens, provider credentials, or licensed Bible text in localStorage/sessionStorage.
- CSP-compatible asset loading and no unsafe inline script requirement unless reviewed.

DevOps implementation must include:

- Managed secret custody/KMS decision, database encryption/backup/PITR, object-store access policy, production/staging separation, and no production data clone without anonymization.
- TLS/HSTS/security headers, dependency/SBOM scanning, vulnerability alerting, audit-log backup, restore drill, and incident runbook.

## 13. Open Owner Decisions

| ID | Decision | Owner | Security impact |
|---|---|---|---|
| SEC-OD-001 | Staff IdP, MFA, session TTL, and emergency access | Security/Product | Blocks staff auth. |
| SEC-OD-002 | Customer identity model for `/graphql/account` | Product/Security | Blocks customer tenant isolation implementation. |
| SEC-OD-003 | Hosting, database, object store, KMS/secrets provider | DevOps/Architecture/Security | Blocks deployment controls and key custody. |
| SEC-OD-004 | Policy-envelope cryptographic suite, key rotation, and grace-clock handling | Security/Architecture | Blocks activation/policy implementation. |
| SEC-OD-005 | First licensed translations and provider route | Product/Legal | Blocks real entitlement/download publication. |
| SEC-OD-006 | Offline grace, refresh, deletion SLA, export/print caps by translation | Legal/Product/Architecture | Blocks desktop licensed store policy. |
| SEC-OD-007 | Retention/deletion periods by data class | Legal/Security | Blocks data lifecycle jobs. |
| SEC-OD-008 | Provider reporting payload requirements | Legal/Licensing | Blocks usage/report exports. |
| SEC-OD-009 | Support extension limits and approval thresholds | Product/Support/Security | Blocks safe remediation permissions. |
| SEC-OD-010 | Production GraphQL introspection policy for staff and customer endpoints | Security/Backend | Blocks production GraphQL settings. |

## 14. Follow-Up Work

ClickUp task creation was not performed in this pass because this review is attached to Build Control and prior ClickUp comment creation for Admin handoffs is failing. The following items should become linked implementation/security tasks once the ClickUp write path is healthy:

1. Security architecture spike: app-key format/hash, policy envelope, KMS/HSM custody, device-token model.
2. Backend security foundation: staff/customer GraphQL auth, tenant isolation, permission matrix, CSRF/CORS/CSP, query limits.
3. Download gateway security: lease design, signed URLs/package checksums, desktop local encrypted-store contract.
4. Audit/export/redaction foundation: fail-closed audit, export permissioning, diagnostics/export allowlist tests.
5. Billing/provider webhook security: signature verification, replay/idempotency, reconciliation.
6. Privacy/legal data lifecycle: retention/deletion/reporting schema and customer-facing terms.

## 15. Gate Notes And Pending ClickUp Update

ClickUp read and comment-read worked for task `86ajnx548`. `_clickup_create_task_comment` returned `INVALID_ARGUMENT` when posting the security start comment and final security handoff comment. Prior Admin PM/UX/architecture handoffs observed the same create-comment failure. Do not claim ClickUp was updated until the connector succeeds.

Pending ClickUp start update text:

`Security review started: GOAL-sec-admin-licensing, engine=goal, max iterations=5. Scope: design-time threat model for Vue 3 Admin under implementation/admin, Django + Strawberry Platform API under implementation/api, staff/customer GraphQL, desktop licensing/download command APIs, billing/provider webhooks, app keys, device tokens, signed policies, entitlements, licensed Bible downloads, audit, exports, secrets, privacy, and operational controls. Evidence target: docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md. No production code or secrets will be touched.`

Pending ClickUp final update text:

`Security review ready for gate review: docs/security/reviews/ADMIN-LICENSING-THREAT-MODEL.md and docs/delivery/goals/GOAL-sec-admin-licensing.md. Goal GOAL-sec-admin-licensing reached GATE_REVIEW. Verdict: Pass with Required Controls for pre-implementation planning; release security sign-off remains Not Assessed because no Admin/API code exists. Scope covers Vue 3 Admin, Django + Strawberry Platform API, staff/customer GraphQL, desktop command APIs, billing/provider webhooks, app keys, device tokens, signing keys, entitlements, licensed downloads, audit, exports, privacy, retention, and operational controls. No production code, secrets, destructive tests, or duplicate Markdown tickets created.`

## 16. Sources

Repository sources:

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

External sources checked 2026-08-08:

- Django security overview: https://docs.djangoproject.com/en/dev/topics/security/
- Django CSRF reference: https://docs.djangoproject.com/en/4.2/ref/csrf/
- Strawberry Django integration: https://beta.strawberry.rocks/docs/integrations/django
- Strawberry permissions guide: https://beta.strawberry.rocks/docs/guides/permissions
- Strawberry deployment guide: https://beta.strawberry.rocks/docs/operations/deployment
- Strawberry disable-introspection extension: https://beta.strawberry.rocks/docs/extensions/disable-introspection
- OWASP GraphQL Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/GraphQL_Cheat_Sheet.html
