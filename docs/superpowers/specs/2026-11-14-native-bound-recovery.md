# Native bound activation/recovery — narrow API ruling

14 November 2026. Coordinator-accepted engineering correction for Task3 finding1; implementation and independent review pending. No code/plan edits, provider calls, credential reads, application tests or agents. Read the finding at `/private/tmp/selahcue-native-account-task3-review-f5222403.md` and current relevant source in `/Users/m.oluwole/.codex/worktrees/selahcue-native-account-ui/scph`. The worktree is being edited by its owner: its new Prepared/PossiblySent tracking was present during this read and is preserved by this recommendation.

## Ruling

Use **two new, strict native activation endpoints and one small durable operation-binding table**, while retaining the legacy routes for existing callers. The new native protocol handles both first activation and bound recovery; it reuses the existing activation/G1 implementation. A recovering request names its expected device, and the server verifies that exact device before any create, replay or remint. A retry resolves its recorded operation target instead of selecting a licence again.

A new route is necessary because old views ignore unknown fields. Durable binding is justified because a first activation can freeze no expected ID, learn the allocated ID, then crash: replay must remain the same request, yet must not select a different licence. Neither an optional field on today's URL nor today's Device.idempotency_key provides that guarantee. This is two native wrappers, one metadata table and frozen native metadata additions; no account switching, cross-licence transfer or general API version migration is proposed.

### Alternatives considered

| Approach | What it establishes | Remaining problem |
|---|---|---|
| Optional expected_device_public_id on old URLs | New server can check it | Old server ignores it and may allocate. Reject as the safety boundary. |
| New recovery-only URL + self-binding key such as nonce+hash(expected ID/identity/path) | Old server404; unchanged key cannot name a different target if hash is verified | Does not record prior execution or first-activation result. Legacy random keys lack that binding. A pending first activation with frozen expected=None still needs a safe replay path. Useful only if those cases are deliberately unsupported. |
| New strict URLs + durable binding | Old server fails without allocation; target and request are frozen independently of Device's creation key; initially unbound retries remain bound after first execution | Adds one small table and migration. Recommended for the actual Task3 retry contract. |

A bound key is not secret, proof of ownership, or proof that an earlier request ran. Do not describe it as a replacement for authenticated scope checks or retained operation outcome.

## Wire contract

New paths:

- `POST /v1/activations:bound` — enrollment key in the body, as today; no cookie or device-token authority.
- `POST /v1/activations:bound-with-session` — authenticated ADMIN account-session bearer, never cookie fallback.

Both require strict fields: `operation_version:1`, `mode:'initial'|'recover'`, `idempotency_key` (the saved32-lowercase-hex native operation nonce), `expected_device_public_id` (explicit null for initial, nonempty canonical dev_ public ID for recover), and the existing frozen fingerprint/platform/app_version/display_name. Enrollment additionally requires license_key. Missing/unknown fields or inconsistent mode/expectation fail400 before domain mutation. The envelope's version belongs to these new routes, not a global API version. Preserve current body limits, validation, throttling, no-store and audit/redaction requirements.

No URL negotiation or fallback:404/405/unrecognized response from these paths becomes native `BoundActivationUnsupported`. Retain the pending operation and credentials, preserve local presentation, and tell the operator that account recovery requires the compatible server. Never retry against `/v1/activations`, `/v1/activations:with-session` or GraphQL. Deployment must not rewrite/alias the new URLs onto old handlers. Mixed server versions may yield a safe404; they must not allocate through the legacy path.

Require the new successful response to echo `operation_version`, `idempotency_key`, and a non-secret `operation_state:'completed'|'replay'` in addition to the existing activation metadata. Native checks these plus expected/previously learned public ID and platform before metadata or OS credential writes. A structurally old success is not sufficient confirmation.

## Operation persistence and transaction order

Add `DeviceActivationOperation` in devices/models.py, with its next migration (observed current leaf0002): ordinary BigAutoField PK; globally unique random operation key; authenticated org FK; selected licence FK; device FK; nullable result_token FK to DeviceToken with SET_NULL, plus immutable issued_token_pk metadata; auth path, mode, original expected public ID (nullable), normalized request digest, created/completed timestamps and outcome `CREATED|REMINTED|EXISTING`. Use PROTECT only for org/licence/device identity references. The result_token relation is nullable SET_NULL so token deletion is not blocked; issued_token_pk is an immutable non-null PositiveBigIntegerField snapshot, not a second FK or a lookup/rebinding authority. No raw credential, password or enrollment key is stored. Operation rows are written only with a successful activation result. Keep bindings for the device/licence lifetime rather than pruning a key so it can later execute as new. All FKs use existing integer PKs; device_public_id remains a string.

Digest the frozen normalized non-secret request and authenticated org identity, including mode, expected ID, path, fingerprint, platform, version and display name. Enrollment proof is checked against the bound licence each time; its secret is not in the digest. A renewed ADMIN session in the same org may resume; session/user token bytes are not part of the frozen request. All requests still require current valid authority—an operation key is never an authentication capability.

1. Authenticate/normalize without mutation, then look up the operation key before choosing a fresh target. If present, verify its authorized org/path/digest and use its recorded licence/device for all following checks; a conflict returns without a lifecycle write. Only an absent operation may enter fresh target selection. For a new recovery, resolve expected device only within the authenticated org (session) or the exactly authenticated licence (enrollment). Require exact stored fingerprint and platform. For a session recovery, select **that device's licence**, even when another licence has a later expiry. Wrong org/licence/fingerprint, revoked/inactive device, ineligible licence or allowance fails before creating an operation, device or token; a denied attempt must not poison the correct retry key.
2. Lock org→selected licence→device/token in the established order. Recheck scope/status/time and recovery proof under locks. Initial creation may use the ordinary selected eligible licence and existing activation core. Recovery calls the existing-device/G1 branch only; it can never fall through to creation or the generic creation-key lookup. Do not bypass G1's within-plan allowance check, live-token show-once behavior or current licence gate.
3. Recheck the durable operation under the locked transaction (the first lookup was only routing, not authority). An existing key is accepted only for the same authorized org/path/frozen digest and recorded device/licence; any change is a generic409 conflict without mutation. For an existing recorded operation, lock/check its recorded licence/device rather than re-running the furthest-expiry resolver. A globally unique key also prevents the same operation being silently rebound to another org; cross-org errors reveal no target details.
4. If absent, finish all authorization/precondition checks, insert the operation and perform the existing initial/create-or-existing/G1 mutation in **one transaction**, then record its exact result target/token. A uniqueness race rolls back all losing mutations and rereads the winner; no caught IntegrityError inside a broken transaction and no orphan seat. If an initial request's legacy creation-key lookup already names a device with a different fingerprint/platform, reject before calling that replay branch. Do not assume the legacy key lookup validates the full request.
5. First successful execution may return the newly created/reminted raw token once. No raw token is retained for replay. An operation replay never invokes another remint, even if its referenced token later expires, is revoked or is deleted: return existing no-secret replay metadata only while the original result_token relation is present and that token/result remains usable; otherwise409 `ACTIVATION_OPERATION_COMPLETED` with no credential. A genuinely later recovery requires a new explicitly prepared operation and valid ADMIN/enrollment proof. Existing licence/device revocation or invalid authority still denies rather than returning success.

This separates operation idempotency from G1 recovery: the same operation does not produce another credential, while a new authorized recovery may remint when the device has no usable token. A dead token is never the recovery authority, and a revoked Device remains terminal. If a licence needs the upcoming ongoing-Free renewal, the trusted lifecycle service must renew the **bound same licence PK** when eligible; it must not call an initial-Free helper that selects/replaces another key. Until that service exists, expiry is a truthful refusal.

Suggested interfaces in new devices/bound_activation.py:

- `activate_bound_with_session(actor:ActorContext,data:BoundActivationData)->BoundActivationResult`
- `activate_bound_with_key(data:BoundEnrollmentData)->BoundActivationResult`
- `BoundActivationData(operation_version,mode,idempotency_key,expected_device_public_id,device_fingerprint,platform,app_version,display_name)`
- `BoundEnrollmentData` adds presented_key with redacted representation.
- `BoundActivationResult` wraps existing ActivateDeviceResult plus operation key/version/state; no alternate token-custody abstraction.

Use existing POLICY_DENIED/NOT_FOUND outward scoping conventions, plus409 `ACTIVATION_OPERATION_CONFLICT` and `ACTIVATION_OPERATION_COMPLETED`. Apply the existing per-path activation budgets to the new endpoints without giving a caller extra quota by alternating old/new aliases; bound row creation with those shared budgets. Retained operation metadata adds write/storage cost and must be included in the implementation review; no table pruning may silently make an old operation executable again. The native unsupported-server classification is based on the dedicated path's failure, not on guessing whether an optional field was understood.

## Native frozen operation and legacy behavior

For every **new** pending operation, persist protocol `bound_v1`, path, mode, expected ID (including null), nonce and identity before any request; retain existing Prepared→PossiblySent write-before-dispatch behavior. Initial is allowed only when the installation has no known public binding. A known binding creates recover mode with its exact ID. Do not derive/change expectation from the latest top-level metadata each time a pending operation retries.

A bound_v1 initial operation remains initial/expected=null after it learns a public ID. Persist the returned public ID before OS storage as now, but leave the frozen request unchanged. After a crash, replay the same new URL/nonce/body; the server's durable operation selects the original device. Locally compare its reply against the now-known public ID as an additional check. This is the reason to include first activation in the narrow new protocol rather than protecting only recovery calls.

Legacy metadata that has no protocol/expected snapshot must decode as `legacy_v1`; never treat absence as a newly prepared safe operation. Current source already defaults absent dispatch phase to PossiblySent. Preserve that conservative classification.

| Legacy/local state | Required behavior |
|---|---|
| Prepared, with durable evidence it never entered dispatch | Retire the unsent operation atomically and prepare/save a fresh bound_v1 operation before network. Preserve fingerprint/public ID and account/device custody. This uses the existing newly added phase distinction. |
| PossiblySent legacy pending, with a retained in-memory matching answer | Finish the current metadata-first/custody path; do not send another activation. |
| PossiblySent legacy pending, matching durable local device credential and known public ID | A read-only refresh can establish that the intended current local identity is usable; retire pending only through the existing validated-completion path. This does not prove that the old request never allocated some other row. Do not erase evidence of a detected mismatch. |
| PossiblySent legacy pending, missing/invalid credential or no known target | Preserve its frozen request; return `LegacyActivationOutcomeUnknown` and do not POST it to either the old allocating route or a new route as a fabricated fresh operation. An absent new operation row is not proof that the old endpoint did nothing. Reconciliation/support must establish the existing target/outcome before a new bound recovery is prepared. |

The last case is a deliberately explicit compatibility limitation for pre-protocol ambiguous operations. This ruling does **not** claim transparent recovery of evidence the old server never retained. Adding a legacy receipt-discovery/migration endpoint would be a separately bounded follow-up, not a reason to guess a target or mutate the frozen request now. In particular, top-level activated_public_id learned after an old request was sent does not retroactively change that request's expected=null/absent precondition.

Show-once remains honest: if the first raw response was lost and the server token is still live but unavailable locally, a replay returns no secret and does not rotate it just to make custody succeed. Retained in-memory answers may finish OS save; a valid existing stored credential may be kept. Otherwise show the existing missing-local-credential/recovery limitation. No reusable token replay cache or forced live-token rotation is added. A binding table prevents unintended new seats; it cannot reconstruct a lost show-once secret.

## Focused implementation/test ownership

Backend owner: devices/models.py and next migration; new devices/bound_activation.py; minimal refactor of existing devices/services.py to expose a prevalidated existing-device branch; platform/{views,urls,responses}.py; graphql/{errors,route_contracts}.py; new tests/test_bound_activation.py and tests/test_bound_activation_postgres.py. Old endpoints and browser GraphQL need no behavioral rewrite for this fix. Test new route strict fields/no-cookie auth/no-store and preserve existing activation/remint regression tests.

Native owner: licensing/src/{contract,client,error}.rs (new request/result/path types); operator/src/account/{state,controller,mod}.rs and owning tests. Metadata save guards must allow only legitimate phase progression/public-ID recording and preserve the complete pending request; adding protocol fields cannot silently rewrite legacy PossiblySent snapshots. No change to keychain order or presentation state.

Required tests:

1. Old API serving only legacy routes receives the new bound URL:404, zero activation calls/rows/tokens; native never falls back. Sending an optional field to old URL is a negative-control demonstration, not a safe path.
2. Two eligible same-org licences, later-expiry B and bound device on A: ADMIN recovery targets A, keeps its public ID and slot; B remains untouched. Enrollment key for B refuses before operation/device/token writes, then correct key A with the same nonce can still succeed.
3. Wrong org, wrong fingerprint/platform, revoked bound device, suspended/revoked licence and an available seat on another licence all refuse without allocation or remint.
4. Reuse a recovery nonce with changed expected ID, mode, path, fingerprint or org: conflict/no mutation. Prove it using the new operation table, not Device.idempotency_key. Parallel identical operation creates/remints once; losing transaction cannot leave a second seat/token.
5. Initial expected=null returns ID A; persist ID, fail keychain write, crash; change selected licence ordering; replay identical frozen initial request returns A without creating B. Change the reply ID and verify no metadata/OS overwrite.
6. Replay a successful remint returns no raw token and never remints again. New later authorized recovery can remint a dead token under a fresh operation while preserving device ID; revoked Device and dead-token-only requests cannot.
7. Legacy metadata defaults to PossiblySent/legacy_v1; known-prepared conversion is allowed only before dispatch; ambiguous legacy cannot allocate; learning a public ID cannot mutate a frozen expectation. Missing-local live token remains explicitly unresolved, not forged successful custody.
8. PostgreSQL tests interleave licence/device suspension, operation insertion, duplicate activation and wrong-scope retries. Assert both row counts and token status, not just the client mismatch error. Preserve metadata-first→OS-store→session-cleanup ordering and uninterrupted local presentation in joint native/API tests.

## Source evidence

- platform/views.py:95–120 and316–344 construct data via raw.get and ignore extra fields; no expected-ID safety contract exists on the old routes. platform/urls.py:7–12 lists only legacy activation paths.
- devices/services.py:477–499 scopes idempotency/fingerprint lookup to the selected licence;516–537 creates a new public ID/device/token. `_resolve_org_active_license_key`:619–637 selects furthest expiry; session activation:640–666 delegates after that selection.
- devices/models.py:43–50 stores uniqueness for licence+creation key and licence+fingerprint. `_remint_device_token`:280–325 records the supplied recovery key only as an audit request ID; `_existing_device_result`:390–443 preserves live-token show-once and remints only when no usable token exists. It does not create a durable recovery-operation binding.
- native licensing/client.rs:365–390 and459 onward send current identity/key to legacy endpoints; contract.rs:69,79,97,358 owns paths/request structs.
- operator/account/controller.rs at the reviewed finding:369–459 sends first, then compares ID and saves metadata before custody. Current state.rs:93–120 adds Prepared/PossiblySent; existing pending immutability must remain. Worker edits were observed, not reviewed or changed by this ruling.

## Token-retention preflight amendment — SET_NULL, not PROTECT

**Conclusion:** keep operation identity durable but allow DeviceToken rows to disappear. The proposed protected token FK is withdrawn. Use `result_token = ForeignKey(DeviceToken, null=True, on_delete=SET_NULL)` and immutable `issued_token_pk = PositiveBigIntegerField()` captured in the same success transaction. Org, licence and device bindings remain PROTECT. An operation still records which token it originally referenced after cleanup; it stores no secret/hash copy and never resolves a deleted relation by querying the integer snapshot.

**What current source establishes:** `apps/devices/tasks.py:60–94` implements a bounded revocation cascade that changes ACTIVE tokens to REVOKED and audits; it does not delete them. No scheduled DeviceToken purge was found in the scoped owning task/maintenance search, so this ruling does not invent a shipped token-retention period or claim the current cascade would itself be blocked. However, the existing joint G1 acceptance fixture explicitly deletes the server token at `tests/test_native_account_controller_integration.py:99–100`, then verifies missing-token recovery after valid authority/renewal at109–115. A protected reference would make this supported case fail with ProtectedError. `_live_token` at services.py:264–276 deliberately returns None when no usable row exists; the existing recovery path treats that as eligible for a new authorized remint. Token→device currently uses CASCADE (models.py:69–72); the new operation table must not accidentally add token immortality.

**Exact replay rule:** if result_token is NULL, missing on locked re-read, revoked or expired, a replay of that completed operation returns409 ACTIVATION_OPERATION_COMPLETED with no token and no mutation. It must not consult `_live_token` and silently substitute another token or rerun G1. Deletion never deletes/resets the operation, changes its device/licence, frees its key for reuse, or changes issued_token_pk. A later fresh operation with valid ADMIN/enrollment authority may recover the same ACTIVE device through ordinary G1; this is a new operation, not replay of the deleted token. A dead/unknown bearer and a revoked Device remain insufficient. If another usable token already exists, the new operation follows the existing no-secret show-once branch instead of rotating it.

Do not set the old operation's nullable relation to the new token during recovery. The new operation receives its own result_token/issued_token_pk; the old operation remains completed with its original snapshot. Any existing automatic token cleanup can therefore use its usual deletion policy without a recovery-table exception. This amendment adds no token-deletion job or new retention policy.

**Owning tests to add to test_bound_activation.py and test_bound_activation_postgres.py:**

1. Complete an operation, delete its original DeviceToken through the ORM, and assert deletion succeeds, result_token becomes NULL, operation/org/licence/device bindings and issued_token_pk remain unchanged.
2. Replay that key after deletion:409 completed/unusable, no device/token insert, no G1 audit, no seat change. Repeating the replay is still a no-op.
3. Renew the same eligible licence and submit a fresh authorized bound-recovery operation: exactly one new token, unchanged device/public ID/seat, old operation remains NULL-bound, new operation snapshots the new token PK. Old/unknown bearer alone still fails.
4. Old operation with a deleted token plus a different currently usable token: replay does not substitute that token; a fresh operation returns existing no-secret behavior and does not remint.
5. Race token deletion against operation replay/recovery on PostgreSQL. Re-read the nullable relation under the transaction; no500, dangling reference, unintended remint, duplicate issuance or identity change. Enforce the existing consistent org→licence→device/token lock order and handle SET_NULL clearing the relation rather than assuming it cannot happen.
6. Preserve revocation-cascade regression and the existing joint `missing` G1 scenario. A revoked original token has the same completed/unusable replay outcome even while its row still exists.

Only this ruling report was amended. No code, migration, plan or test was changed or executed.


## Accepted completed-operation identity proof amendment

The coordinator approved this during Task 3 fix round 1, before implementation. When the original operation committed but its original token is deleted or unusable, a narrowly authenticated 409 ACTIVATION_OPERATION_COMPLETED may include a no-secret completed-operation identity proof. Authorize the recorded nonce/path/digest/org and recheck the locked licence and exact device first. Return only version, recorded nonce, stored public device ID and platform from the durable receipt; do not echo unvalidated input or issue a token. Other compatible domain errors include operation_version 1; a bare legacy 404 or unknown version remains unsupported.

The native client requires the expected status/version/nonce/platform and a canonical ID matching any known or frozen expected binding. It must atomically CAS-save the learned public ID and retire the completed pending request. A failed CAS preserves the identical pending request for the identical no-secret proof on retry. Display reauthentication/recovery required. Only a separate explicit authorized action can create a fresh recover nonce; never implicitly remint or allocate another initial device. Tests must cover the entire first response lost followed by token expiry/deletion, wrong-proof rejection and CAS-failure preservation.

Rationale: a lost first response could otherwise leave a safely recorded server operation unresolved forever despite a durable known target. Cost if wrong: an additive authenticated error DTO; no new token disclosure, seat allocation or weakened binding.


## Foundation review amendment — local operation and cleanup ownership

The consolidated foundation correction supersedes the Task 3 exact-send-generation
response-custody rule. A revision change for the identical frozen bound operation is
progress, not authority to discard its delayed show-once response. Before custody,
reload and compare the complete immutable pending request and known device binding
under the shared local ownership fence. A different nonce, protocol, mode, path,
identity or binding still refuses custody. Save public identity before OS custody;
retire pending only after the token is stored, or an existing bearer is verified
against that exact device. A no-secret replay with missing or rejected local custody
retains the pending operation and retry authority because the original response may
still arrive. This does not re-show lost secrets or mint another live credential.

The stable account-session-custody lock now coordinates short metadata/session/device
custody decisions. Dispatch validates the loaded metadata before session replacement
and advances its durable send generation within the same fence. Cleanup validates
its metadata and captures the exact session under that fence, then saves a non-secret
`cleanup_reserved` boolean before HTTP. All cooperating activation writers refuse
that reservation. Confirmation removes only the matching session and clears the
reservation; a restart with no local session can clear a leftover reservation.
Every HTTP call and view projection remains outside this fence and the metadata
writer lock. OS custody failures remain explicit; no cross-system transaction or
protection from arbitrary external keyring writers is claimed.

`POST /v1/sessions:revoke` may confirm an exact recorded already-revoked bearer with
its usual `revoked:true` result. This is terminal cleanup only: it grants no login,
activation, refresh, browser logout or other account authority, does not touch other
sessions, and repeats no logout audit. Unknown/deleted or other inactive tokens
retain the existing refusal. This closes acknowledgement loss and restart after a
local-remove failure without treating a generic401 as successful cleanup.

The receipt-token relationship uses an explicit database `ON DELETE SET NULL` via
an additive migration. Django E323/E050 prohibit mixing `DB_SET_NULL` with the
existing Python `PROTECT` graph; ORM state therefore uses `DO_NOTHING` and the
migration installs the database action through schema-editor `alter_field` with
`DB_SET_NULL`. Existing identity protection remains unchanged. PostgreSQL owns the referential action so a fresh recovery receipt committed while
DELETE waits on the live token is also nulled. Both receipts and their immutable
issued-token PK snapshots survive. Earlier ORM-only SET_NULL wording is superseded.

Online display retains the observed licence expiry and check instant, evaluates
exact expiry on every view/busy read, and ignores online facts after a backwards
clock jump before the observation. A later genuine renewal can supersede an older
signed licence expiry for online display; offline authority remains signed-only.
