# Pilot registration v1

Ticket: [P13 n8n registration](https://app.clickup.com/t/17tnw2bbhxk). Grant follow-up: [P12](https://app.clickup.com/t/17tnw2bbhxm). Normalized validation, durable row reservation, authenticated confirmation and signed receipts are implemented behind disabled-by-default configuration. Deployment and the download-grant flow remain unconnected. The exact callback/runbook contract is [durable n8n handoff](../../release/pilot-registration/README.md).

## Boundary and fields

The marketing CTA navigates to the configured n8n-hosted form. n8n maps its display labels into the normalized payload below. Final required fields and collection notice remain product/privacy decisions; these mirror the existing draft, not an independently approved expansion of collection.

| Field | v1 contract |
|---|---|
| `schema_version` | JSON integer `1`; booleans and strings rejected |
| `registration_id` | Canonical lowercase UUIDv4 generated before the submission is first attempted; retained across retries of that submission |
| `full_name`, `church_name`, `church_role`, `church_city`, `church_country` | Nonblank trimmed strings, at most 200 input characters each |
| `email` | Nonblank trimmed/lowercased email-shaped string, at most 254 input characters; not proof of mailbox ownership |
| `phone` | Optional string, at most 50 input characters; omitted becomes empty |
| `platform` | Exactly `Windows`, `Ubuntu` or `macOS` |
| `notice_version` | Nonblank identifier, at most 80 characters, using letters/digits/dot/underscore/hyphen; draft notices rejected |

Unknown fields, nonstring field values, ASCII controls, malformed identifiers and unsupported versions/platforms fail closed. Validation errors name fixed fields without echoing personal data. Ingress must independently enforce a total request-size limit. The validator does not establish that a notice identifier is an approved deployed version: orchestration must check an explicit configured allowlist.

`to_sheet_row()` supplies literal values for Sheets writes that also use RAW input. Formula-like leading characters are escaped only at this serialization boundary; normalized identity values are not mutated. The function does not supply a receipt or installer URL. Server time/source provenance must be added by trusted orchestration, not accepted as browser assertions.

## Orchestration and remaining integration

1. The inactive n8n export hosts/maps the form and consumes a stable UUIDv4 from the marketing production-form query. There is no execution-ID fallback. Hidden platform/UUID fields are untrusted. Actual deployment requires approved fields/notice, owner/retention and protected private Sheet configuration.
2. `POST /v1/pilot/registrations:reserve` requires dedicated server Bearer authentication and bounded JSON. It validates the notice allowlist, binds canonical payload/destination fingerprints, and allocates one durable row with PostgreSQL locking and uniqueness constraints. Same UUID/different payload fails.
3. n8n uses fixed-row Google `values.update` with RAW cell formatting, never append. Concurrent or ambiguous-timeout retries use identical values at the same reserved range. The dedicated Sheet structure must be protected: no inserts, sorts, deletes or other writers. Preserve allocation counters; retention clears values without shifting rows.
4. `POST /v1/pilot/registrations:confirm` accepts only authenticated n8n's matching write acknowledgement: document, exact row/range and 1 row/13 columns/13 cells. Only then is confirmation time set once and a purpose-bound signed receipt issued. No contact fields or provider keys are in the receipt. Retry does not extend receipt expiry; no confirmation means no receipt.
5. `verify_registration_receipt()` checks signature/purpose and the live confirmed ledger, fixed expiry and retention. Receipts bind schema version, registration UUID, platform, pilot channel, intended audience and issue/expiry times. They are not tied to an arbitrary client-supplied bucket path. P12 must resolve the requested architecture/release to an allowlisted available manifest entry, enforce build expiry, produce a private-object URL and define replay/recovery. The licensed-account/device API remains separate.

The [runbook](../../release/pilot-registration/README.md) defines actual callback responses/error statuses and n8n configuration. Farah uses configured production form URLs and retains retry identity; these API callbacks are not browser endpoints. No live hostname, signing secret or provider credential is invented by this contract.

## Verification and remaining evidence

Run `python3 implementation/api/tests/test_pilot_registration_contract.py` from the repository root. The pure boundary suite loads its module directly because importing the API package starts Celery; it is not an API/Django integration test.

The new service/workflow suites cover durable identity/row binding, callback authorization/configuration, RAW serialization, ACK matching and expiry, with real PostgreSQL races. Remaining gates: final n8n export runtime/import proof, sandbox/live Sheet write/recovery evidence and structural protection, approved fields/notice/owner/retention, actual deployment credentials, P12 manifest/private-bucket integration, representative mobile/keyboard form checks and independent reviews. Registered API routes remain disabled until all required deployment configuration is supplied; this is not a completed public installer journey.
