# Registration profile validation before database access

Authority: [ticket 17tnw2bh4u0](https://app.clickup.com/t/17tnw2bh4u0), the existing field models and public error contract, and the owner's delegated backlog implementation/review/merge instruction. Base: `306a8f3a4eb9cc4a388af0b6091f52ad947f14b9`. No product policy change.

## Evidence and purpose

The existing registration service validates profile fields only in the new-account model path. A local guarded regression now shows four malformed inputs reaching SQL before validation: unknown/overlong timezone and overlong organisation/display names. All four fail the explicit validation-before-database assertion; two existing valid-signup controls pass. The guard stops SQL before it can resolve an identity. This is a defensive ordering result, not an observed account-disclosure comparison or timing result. Original logs and hashes remain in the release-evidence `backlog-20261119/signup-input-probe` directory.

## Approach

Reuse the models' field-format rules in a small shared pre-database check, after both existing registration admission claims and before password hashing/transaction entry. Normalize display name and timezone once and reuse those values for persistence. Keep the existing organisation normalization, early required-input checks and downstream model validation.

Checking only the frontend leaves direct service callers uncovered. Moving full model validation before account branching can execute uniqueness constraints and database queries. A field-only check with the existing timezone clean rule gives the required validation without either problem. This is the coordinator's implementation choice under delegated authority.

## Binding behavior

- Organisation and display names use the current whitespace normalization and model maximum of 200 characters. Organisation name remains required; optional display name may be empty.
- Timezone is stripped; blank becomes UTC. Retain the model maximum of 64 characters and UTC/IANA membership rule. Reuse model validators and its clean rule rather than introducing independent numeric constants or a new timezone policy.
- Malformed profile input receives the existing sanitized `VALIDATION_FAILED` response before SQL, session issuance, email callbacks or account/org/token/success-audit changes. No raw submitted values are newly logged.
- Keep the existing global/source registration admission order and fail-closed behavior. No added profile validation, hashing, query or email work may bypass admission on refusal/outage. Preserve existing cheap required-input checks that already precede admission.
- Preserve valid signup, normalized persisted values, existing-account acceptance, idempotency, uniqueness handling and transactional race/collision behavior. Do not relocate or modify database uniqueness checks in this task.
- Verification uses the guarded local test approach, synthetic fixtures, SQLite, LocMemCache and memory-only broker, in sequential owned processes with a 45-second timeout plus five-second cleanup. No public response-comparison reproduction, live service, timing benchmark, provider, CI, browser/native/Docker or full-suite execution.

## Scope and acceptance

Modify accounts `services.py` and the owning auth test module; only extract a shared pure timezone validation helper in `models.py` if existing model methods cannot be reused safely. No schema or deployment configuration change is needed. Include this spec and its plan. The four existing RED cases must become green with their no-SQL/error/no-effects assertions intact. Add meaningful valid/normalization/boundary controls and run the focused signup/admission/idempotency cases. Independent code, security and performance task reviews, final source/behavior QA and any scoped re-review must pass before the authorized merge.

The email model's length policy, unrelated auth validation, live delivery, deployed timing and native release qualification remain outside this bounded repair. The earlier safety-flagged agent attempts remain recorded; no blocked public-service test is being retried.
