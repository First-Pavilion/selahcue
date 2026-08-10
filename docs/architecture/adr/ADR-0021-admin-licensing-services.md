# ADR-0021: Admin Licensing Platform for accounts, billing, app keys, entitlements, and licensed downloads

- Status: Proposed
- Date: 2026-08-08
- Confidence: Medium
- Owner: Software Architect
- Related: `docs/product/prds/SelahCue-Admin-Console-Project-Brief.md`, `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md`, ADR-0007, ADR-0008, ADR-0011, ADR-0017

## Context

SelahCue now needs an internal Admin Console for commercial operations: customer organisations, subscriptions, time-bound app license keys, Bible translation catalogue, customer entitlements, licensed downloads, support diagnostics, reporting, and append-only audit.

The existing product architecture is desktop-authoritative and offline-first. That must remain true for live presentation. At the same time, several Admin responsibilities cannot live only on one desktop:

- Prospective users need time-bound keys that SelahCue staff can issue, search, extend, revoke, and audit.
- Customers need device/seat limits and supportable activation history.
- Licensed Bible translations cannot be bundled by default; they require SelahCue-held legal/provider terms, entitlement validation, usage/reporting, attribution, export constraints, and revocation/deletion policy.
- Billing state and subscription changes must eventually come from an external provider, but the provider is not selected yet.
- Staff auth/RBAC, audit, support diagnostics, and exports are multi-user internal operations.

## Decision

Introduce a **SelahCue Admin Licensing Platform** as a hosted internal/service-side system, initially implemented as a **Django modular monolith** with **Strawberry GraphQL**, explicit bounded contexts, and an outbox:

1. **Admin Web App** implemented as a Vue 3 frontend under `implementation/admin`.
2. **Platform API** implemented as a Django + Strawberry service under `implementation/api`.
3. **Staff Admin GraphQL** at `/graphql/admin` for staff operations.
4. **Customer Account GraphQL** at `/graphql/account` for normal customer/account self-service operations.
5. **Desktop activation/download command APIs** under `/v1` for app activation, policy refresh, entitlement manifests, download lease preparation/completion, and usage-event batches.
6. **Identity and Staff RBAC** integrated with a managed IdP and MFA policy.
7. **Customer Account Context** for organisations, contacts, customer status, and support notes.
8. **Billing Context** for plan/subscription projection, manual arrangements, invoices, refunds/cancels, and future billing provider webhooks.
9. **App License-Key Context** for high-entropy time-bound keys, hash-only persistence, masking, activation attempts, device activations, expiry, revoke, extend, and signed desktop policies.
10. **Translation Catalogue Context** for legal/provider metadata, territories, offline/cache/export/reporting constraints, attribution, and availability states.
11. **Entitlement Context** for customer grants/revocations and entitlement manifest projection.
12. **Download Gateway** for short-lived device-scoped download leases and supportable denial reasons.
13. **Provider Adapters** for API.Bible/direct publisher/user-supplied or future routes behind ADR-0017's translation-provider posture.
14. **Audit/Event Ledger** as append-only evidence for sensitive actions, plus an event outbox for downstream jobs.
15. **Desktop License Agent** in the app that activates, refreshes signed policy, fetches entitlement manifests, prepares licensed downloads, stores content in an encrypted app-locked local store, and batches usage/reporting events.

The desktop app remains fully capable for live services with public-domain content and already-valid local licensed content. Admin services are required for new activations, policy refreshes, new licensed downloads, and revocation propagation.

GraphQL is used for staff and customer/account surfaces because those experiences need dense relationship reads, filtered tables, detail projections, and typed mutations. Desktop activation/download and provider/billing webhooks remain narrow JSON command endpoints because those clients need very stable retryable contracts, simple error handling, and idempotency independent of browser UI state.

## Options Considered

### Option A: Hosted modular Admin Licensing Platform (chosen)

Pros:

- Matches the multi-staff, multi-customer, support, billing, and compliance nature of the Admin Console.
- Preserves offline-first desktop operation through signed local policies and entitlement manifests.
- Separates app license keys from Bible entitlements by design.
- Lets billing/provider choices remain adapters/projections instead of core product rewrites.
- Gives Security/Legal one central place to enforce audit, RBAC, provider terms, revocation, reporting, and export controls.
- Starts simple as a modular monolith while keeping context boundaries clear enough to split later.
- Uses Django for mature relational modelling, migrations, auth/session integration, webhook handling, admin operations, and worker-friendly service code.
- Uses Strawberry GraphQL where Admin/customer screens benefit from typed graph-shaped reads and mutations.
- Keeps Vue 3 Admin code and Django API code in separate source roots: `implementation/admin` and `implementation/api`.

Cons:

- Introduces a hosted service, deployment, secrets, backup, monitoring, and incident response surface.
- New activations and new licensed downloads require network availability.
- Requires careful security review for signing keys, staff RBAC, device tokens, exports, provider credentials, and audit.
- Requires GraphQL-specific controls: resolver authorization, tenant scoping, query depth/complexity limits, batching to avoid N+1 queries, schema deprecation discipline, and production introspection policy.

### Option B: Extend the desktop local database and avoid a hosted Admin service

Rejected.

Pros:

- Keeps all state local and fully offline.
- Reuses ADR-0007 SQLite/SQLCipher infrastructure.

Cons:

- Cannot support multi-staff Admin operations, prospective key issuance, billing webhooks, support diagnostics, or rights-holder reporting across customers.
- Makes revocation and entitlement changes unreliable because each desktop would be an island.
- Encourages spreadsheet/manual operations, the risk the Admin PRD explicitly exists to remove.

### Option C: Use the billing provider as the source of truth for keys and entitlements

Rejected as the primary architecture.

Pros:

- Less custom account/subscription code if a provider supports subscriptions, coupons, invoices, and customer portal.

Cons:

- Billing providers do not own Bible legal terms, offline download policy, attribution, provider reporting, or device-bound licensed-content state.
- App license keys and Bible entitlements have security/compliance semantics beyond payment status.
- Vendor lock-in would make provider change a licensing re-architecture.

Billing provider state should feed the Billing Context as an integration, not replace the domain model.

### Option D: Build separate microservices from day one

Rejected for Slice A.

Pros:

- Strong service isolation and independent scaling.

Cons:

- Premature operational cost while product/legal/billing/provider decisions are still Unknown.
- Slows first architecture/build validation.
- Distributed transactions would complicate audit, revocation, and entitlement consistency before scale requires it.

Keep explicit module boundaries and an outbox now; split later if load or team structure demands it.

## Consequences

Positive:

- SelahCue gets one coherent control plane for customers, billing projection, app license keys, Bible entitlements, downloads, diagnostics, reporting, and audit.
- Sunday service continuity is preserved because the desktop caches signed policy and licensed content under explicit grace/refresh rules.
- Legal/licensing constraints are encoded as catalogue and entitlement policy, not buried in UI conditionals.
- Provider-specific logic is isolated behind adapters and does not leak into Admin UI or desktop presentation logic.
- Support gets searchable denial reasons and timelines for activation/download failures.
- The API service is named and placed as the shared platform backend, not an Admin-only backend: Django code lives under `implementation/api`.
- The Admin frontend is named and placed as one consumer of the API: Vue 3 code lives under `implementation/admin`.

Negative:

- The Admin platform becomes a high-value target and must pass security review before implementation.
- The team must operate a hosted service and secure signing/private keys.
- Exact behaviour depends on unresolved Legal/Product decisions for provider terms, offline grace, reporting, and translation availability.
- Desktop now has two cloud-facing concerns: sermon-note cloud client and licensing policy/download client. These must remain separate contracts with shared secret/redaction patterns, not one confused "cloud" surface.
- GraphQL makes staff/customer UI development faster but adds schema governance and resolver-security obligations that REST-only APIs would not have in the same form.
- Desktop clients must not be coupled to staff/customer GraphQL operation shapes.

## Requirements Traceability

- App license keys: `ADM-FR-020` through `ADM-FR-029`
- Subscriptions/billing: `ADM-FR-030` through `ADM-FR-033`
- Translation catalogue: `ADM-FR-040` through `ADM-FR-044`
- Entitlements/downloads: `ADM-FR-050` through `ADM-FR-058`
- Support diagnostics: `ADM-FR-060` through `ADM-FR-063`
- Audit/reporting/compliance: `ADM-FR-070` through `ADM-FR-074`
- Settings/secrets: `ADM-FR-080` through `ADM-FR-083`
- Existing translation-provider posture: ADR-0017
- Persistence/security/observability posture: ADR-0007, ADR-0008, ADR-0011

## Required Follow-Up

- Security Reviewer: threat model and crypto/key-custody review.
- Product/Legal: first translation/provider route, offline grace/deletion/reporting terms, and legal approval process.
- Product/Finance: billing provider and pricing/plan source of truth.
- DevOps Engineer: hosting, database, secrets, backups, SLOs, and incident response.
- Backend Engineer: Django + Strawberry API/data implementation plan under `implementation/api` after gate approval.
- Frontend Engineer/UI Designer: Vue 3 Admin screens and state implementation under `implementation/admin` after visual/product approval.
