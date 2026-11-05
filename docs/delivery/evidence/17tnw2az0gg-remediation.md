# Admin catalogue remediation — 17tnw2az0gg

## Scope and authorization

The user requested the remaining catalogue/API/card changes be fixed, independently re-reviewed and merged after passing. This implements the existing admin dependency as its own ticket/branch/PR; no staff login, IdP, MFA, deployment, production enablement or price choice is included.

Verified requirements correction: task17tnw2b2jvy requires an actual admin mutation to propagate to public data, not production staff sign-in. ADR0027 and task17tnw2az0n5 explicitly permit built/merged pricing features before staff login while prohibiting production enablement. Real HTTP mutation evidence using the exact-dev identity fixture is labeled a test fixture, never production authentication. The owner decisions on staff login remain intact.

## Behavior

`adminPlanCatalogue` lists plan identifiers/display names, current prices and all grants. SQL row numbering selects only the current effective version for each plan/currency/interval, excluding historical versions from the response. `adminSetPlanPrice`, `adminSetPlanGrant` and `adminRenamePlan` require MANAGE_PLAN_PRICING in the service layer, a reason, actor-scoped idempotency key and the revision the admin read. Existing grant/price services remain the shared writers. Prices use decimal-string minor units at GraphQL; null is explicitly unpriced and zero is priced zero. Omit effectiveFrom for a server-timed immediate version; a supplied future boundary is retained. History is append-only.

A transactional compare-and-swap on CatalogueRevision serializes competing admin edits and refuses stale changes with CONFLICT and a reload message. A durable unique actor/key receipt retains the original result; identical retry applies once, changed intent on the same key conflicts. Audit, receipt, revision and data write commit or roll back together. Existing catalogue grants retain their previous GRANT_ENTITLEMENT authority; the new pricing authority can edit catalogue grants, not licence overrides or assignments.

SELAHCUE_ENABLE_ADMIN_CATALOGUE defaults false. Settings refuse true outside exact dev, and the service independently refuses any non-dev environment even if an actor is injected. Header trust remains forbidden outside dev. This deliberate gate cannot be removed until the separately reviewed staff authenticator is implemented.

Field validation exposes only fixed allowlisted input names alongside VALIDATION_FAILED. Raw values, arbitrary extensions and database errors remain redacted. All price/grant edits preserve existing reason and model validation. Rename updates row accountability and writes an old/new audit event.

## Observed checks

- Verified RED: missing admin module before implementation.
- First focused implementation: 13 passed.
- Verified RED: invalid currency HTTP response lacked required field; corrected fixed-name error projection.
- Verified RED: immediate-price behavior absent; implemented explicit None/server-time through the same append-only writer.
- Final focused admin/price/deployment regression run: 303 passed,4 explicit service/PG skips in10.76s. Migration drift check reports no changes; Goal structural validator passes. PostgreSQL-only concurrency remains required on hosted CI.
- Real resolver/service/database HTTP tests cover read/grant/invalid-currency responses; a real issued/activated licence and signed next manifest changes allowance1 to6 after the GraphQL mutation.
- Full local API check initially failed on sandbox socket bind permissions (3 failed/318 passed/2 skipped/3 errors before deliberate interruption). This is not a product pass. The full check was restarted with local socket permission and is still running at initial freeze.
- Native PostgreSQL and nginx binaries are absent. Shared Docker version responds, but image/run/rm operations timed out; no PostgreSQL runtime success is claimed from Docker. Actual PostgreSQL concurrency must pass in hosted API CI.

## Review and CI gates

Cody, Shadow, Quinn and Vera must independently review the frozen source. Hosted API CI must execute both competing-admin and concurrent-retry PostgreSQL cases (not skips), migration consistency and the complete API suite. No merge or QA claim is made by implementation.

## Rollback

Revert this PR to remove the gated GraphQL operations. Preserve audit and price history. Do not drop retry receipts in a live enabled system: a client retry could otherwise apply again. No production system or data was changed here.
