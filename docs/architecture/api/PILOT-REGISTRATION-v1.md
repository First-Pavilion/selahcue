# Pilot registration v1 — first implementation increment

Ticket: [P13 n8n registration](https://app.clickup.com/t/17tnw2bbhxk). Grant follow-up: [P12](https://app.clickup.com/t/17tnw2bbhxm). Status: proposed integration contract; only normalized validation and Sheet-cell rendering are implemented. No route is registered or deployed by this increment.

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

## Required orchestration, still unimplemented

1. Host and handle the form in n8n; use HTTPS, request bounds and throttling. Keep personal/church data and credentials out of URL parameters and routine logs.
2. Establish a stable submission UUID before writing. The attached draft's `pilot-${execution.id}` changes between executions and is not a retry identity. Do not silently substitute a new UUID after an ambiguous failure.
3. Authenticate n8n's server callback using a dedicated deployment credential. A public form or a browser-provided `registered=true` flag cannot attest persistence.
4. Durably claim the UUID with uniqueness/concurrency protection and bind it to a canonical payload fingerprint. Same UUID/same normalized payload resumes the existing record; same UUID/different payload fails rather than modifying an existing registration.
5. Write the private Google Sheet row with that UUID. Serialize writers for a submission. A timeout is an ambiguous outcome: reconcile by submission UUID before appending again. A lookup followed by append without locking is not concurrency-safe and does not guarantee exactly once.
6. Mark persistence confirmed only after an acknowledged write or verified reconciliation. Outage or unconfirmed persistence cannot issue a success receipt or download. Store minimal durable state with a defined retention policy; do not duplicate full personal data without a requirement.
7. Only trusted server code may issue a short-lived signed receipt. An allowlisted receipt format should bind schema version, registration UUID, platform, pilot channel/release, issuer/audience and issue/expiry times; no contact/church data, provider keys or arbitrary bucket paths. Signing keys, TTL and deployed route names remain explicit configuration/design decisions, not fabricated values here.
8. P12 verifies signature/purpose/expiry and resolves only allowlisted available manifest entries before returning a bounded private-object URL. Expired pilot builds and absent artifacts cannot be granted. Define replay/recovery behavior so a grant outage after registration does not require another Sheet append. Preserve the separate licensed-account/device API.

Suggested browser-facing failure categories for coordination are invalid submission, registration pending/retry, download temporarily unavailable, and pilot expired/unavailable. They are not an implemented HTTP schema. Farah must use configured deployment URLs only after the route/response contract is implemented and tested.

## Verification and remaining evidence

Run `python3 implementation/api/tests/test_pilot_registration_contract.py` from the repository root. The pure boundary suite loads its module directly because importing the API package starts Celery; it is not an API/Django integration test.

Remaining before P13/P12 completion: durable model/migration and race tests; authenticated callback; actual n8n JSON mapping and stable browser retry identity; sandbox import and Sheets acknowledged/ambiguous write tests; approved fields/notice/retention; signing and expiry/replay tests; manifest/private-bucket grant integration; keyboard/mobile form checks; independent code/security/performance/QA review. This module is intentionally not wired into application settings or URL routing until these trust boundaries are implemented.
