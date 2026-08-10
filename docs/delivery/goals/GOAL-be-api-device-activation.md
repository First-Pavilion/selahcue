# Goal Contract — GOAL-be-api-device-activation

## Identity

- Goal ID: GOAL-be-api-device-activation
- Parent goal ID: 86ajy5v6k (EPIC — Platform API / Licensing & Entitlements)
- Title: Implement the SelahCue Platform API device-activation slice (`POST /v1/activations`) — account-instance registration that validates a presented enrollment key and issues a show-once device token, per DEC-004, mirroring the license-key slice conventions
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy5v7h
- Created: 2026-08-09
- Updated: 2026-08-09
- Maximum iterations: 10
- Independent verification required: yes

## Objective

Replace the `/v1/activations` 501 stub with a real activation endpoint: the desktop presents an org enrollment key (`AppLicenseKey`, reframed per DEC-004 as a bootstrap token) + device info + an idempotency key; the server validates the key (HMAC-fingerprint lookup + `check_password`, validity window, key status, instance/`device_limit` not exceeded), registers a **Device** instance, issues a **show-once device token** (masked triple + `make_password` hash + unique HMAC fingerprint), flips the key ISSUED→ACTIVATED, records a `device.activated` audit event, and is idempotent — all mirroring the existing `license_keys` slice, with tests that prove secrecy/idempotency/validity/audit/rollback and a green suite.

## Baseline

Verified this session:

- `implementation/api` is Django 5.2 + Strawberry, pytest-django. Baseline suite: **18 passed** (`/private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q`).
- Implemented slices: `accounts` (CustomerOrg), `audit` (AuditEvent + `record_audit_event`), `license_keys` (Admin issuance — the template). Scaffold-only apps: billing, catalogue, entitlements, downloads.
- `/v1/activations` is a `@csrf_exempt @require_POST` **501 stub** (`platform/views.py:activation_not_implemented`); URL + `CommandEndpointContract("desktop","v1/activations","POST","app_key_then_device_token")` already declared.
- **No** Device/DeviceToken model or devices app exists. Reusable seams already present: `ActorKind.DEVICE`, `"device_token"` in `RESTRICTED_PAYLOAD_FIELDS`, `LicenseKeyStatus.ACTIVATED`.
- Conventions to mirror (from the license_keys slice): frozen-dataclass `Data`/`Result` services; `_generate_full_key`/`_fingerprint` (HMAC over `settings.SECRET_KEY`)/`_mask` (prefix[:12]/suffix[-4:]); `make_password` hash + unique fingerprint; `transaction.atomic()` with **idempotency-first** return; `full_clean()`→`SafeAPIError(VALIDATION_FAILED)`; `record_audit_event(...)` inside the atomic block with only masked/non-secret fields in `after`; `SafeAPIError(ErrorCode.X)` everywhere; hand-committed migration.

## Inputs and evidence sources

- DEC-004 (licensing model: account spine + device instances + offline entitlement).
- `implementation/api` — license_keys/accounts/audit slices (template), graphql/context.py + errors.py + redaction.py, platform/views.py + urls.py + route_contracts.py, settings.py, tests/*.
- README open decisions (policy-envelope crypto, account IdP, offline grace) — deferred, flagged.
- ClickUp epic 86ajy5v6k; desktop cloud dependency 86ajy04hz.

## Scope

### In scope

- New app `selahcue_api.apps.devices` (label `selahcue_devices`) with `Device` + `DeviceToken` models + hand-committed `0001_initial` migration; registered in `INSTALLED_APPS`; `"selahcue_devices"` added to `expected_labels` in `test_foundation_contract.py`.
- `apps/devices/services.py::activate_device(actor, data)` mirroring `generate_license_key` — enrollment-key fingerprint lookup + `check_password`, validity-window + status + instance-limit checks, device+token creation, key ISSUED→ACTIVATED, `device.activated` audit, idempotency (actor+idempotency_key and natural key+fingerprint), rollback-on-audit-failure.
- Real `POST /v1/activations` view in `platform/views.py` replacing the stub: parse JSON, build a `DEVICE` `ActorContext`, call the service, map success + `SafeAPIError.code`→HTTP status into the existing JSON error shape (`{"error":{code,message},"surface","operation"}`), run `assert_no_restricted_payload_fields` on the error payload, return the show-once token once.
- Tests `tests/test_device_activation_slice.py` mirroring `test_admin_license_key_slice.py`.

### Non-goals

- The **signed** offline entitlement policy-envelope crypto + key rotation (open owner decision) — a basic entitlement/validity in the response only; the signed policy is a follow-up.
- Real account sign-in / customer IdP — activation stays enrollment-key-authed per the existing `app_key_then_device_token` contract; the header-actor dev bridge is unchanged.
- The other `/v1` endpoints (license:refresh, entitlements/manifest, downloads, usage-events) — still stubs.
- Offline-grace duration, entitlement manifest contents, billing.

### Constraints

- Mirror the license_keys conventions exactly; reuse `settings.SECRET_KEY` as the HMAC pepper so the activation fingerprint matches issuance.
- Secrets: the full device token leaves the system exactly once (the activation response); never persisted in plaintext, never logged, never placed in an audit `after` (redaction blocks `device_token`/`full_key`/`secret`).
- All datetimes tz-aware UTC (`USE_TZ=True`); use `timezone.now()` + the `_coerce_datetime` discipline.
- Migration is additive + hand-committed; `manage.py check` and `makemigrations --check` clean (no missing migrations).
- Do not change existing slices' behaviour or the GraphQL wire.

### Assumptions and unknowns

- ASSUMED: activation is authenticated by the presented enrollment key (per the existing contract), not a staff/account session yet. Owner: product (account IdP is a tracked open decision).
- ASSUMED: SafeAPIError→HTTP status map (400/401/403/404/409/429) — no prior HTTP precedent; documented in the view. Owner: backend-engineer.
- UNKNOWN: signed policy-envelope crypto suite + offline-grace duration. Owner: product/security — deferred.

## Dependencies and approvals

- ClickUp MCP — connected (task 86ajy5v7h).
- Python test venv `/private/tmp/selahcue-api-venv` — present, baseline green.
- Independent review (security + correctness) — required; not self-certified.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `devices` app + `Device`/`DeviceToken` models + `0001_initial` migration exist, registered in INSTALLED_APPS + `expected_labels`; system check + migration state clean | `manage.py check` and `manage.py makemigrations --check --dry-run` | Both exit 0 (no issues, no missing migrations); foundation test lists `selahcue_devices` | migrations file + settings diff + command output | PASS |
| C-002 | yes | `activate_device` registers a Device + issues a show-once device token from a presented enrollment key (fingerprint lookup + check_password), flips key ISSUED→ACTIVATED, audits `device.activated` | `pytest tests/test_device_activation_slice.py -q` (create path) | Exits 0; created=True returns a `SC-DEV-…` full token once; key status becomes ACTIVATED; one AuditEvent action=`device.activated` | test file + output | PASS |
| C-003 | yes | `POST /v1/activations` returns 200 with the show-once token on success and maps `SafeAPIError.code`→HTTP status with the JSON error shape on failure | `pytest` HTTP tests hitting `/v1/activations` | 200 + token on success; 404/403/400 with `{"error":{"code",...}}` on the mapped failures | test output | PASS |
| C-004 | yes | Idempotent: repeating the same activation returns created=False, the same device, `full_token=None`, and leaves exactly one Device + one DeviceToken | `pytest` idempotency test | Second call created=False, token None, `Device.objects.count()==1`, `DeviceToken.objects.count()==1` | test output | PASS |
| C-005 | yes | Validity/policy: expired / not-yet-started / revoked / suspended key → POLICY_DENIED (no rows); unknown key → NOT_FOUND; instance/`device_limit` exceeded → POLICY_DENIED | `pytest` validity tests | Each maps the expected ErrorCode; `Device.objects.count()==0` for the denied cases | test output | PASS |
| C-006 | yes | Show-once secrecy: the full token never appears in a replay response, the DB (`token_hash`/`token_fingerprint`), or any audit payload; masked triple correct | `pytest` secrecy test | `full_token not in json.dumps(...)` for replay + audit; not equal to hash/fingerprint; prefix/suffix/masked correct | test output | PASS |
| C-007 | yes | Audit + rollback: a failing `record_audit_event` rolls back the whole activation (0 Device, 0 DeviceToken rows) | `pytest` rollback test (monkeypatch audit) | Raises; `Device.objects.count()==0` and `DeviceToken.objects.count()==0` | test output | PASS |
| C-008 | yes | The full API test suite is green after the change | `/private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q` and `python -m compileall implementation/api` | pytest all pass (≥ 18 + new); compileall exits 0 | suite output captured to scratchpad | PASS |
| C-009 | yes | Independent review (security + correctness) confirms secret handling (show-once only, no plaintext persistence/logs), constant-time key verify, fingerprint-lookup, and DEC-004 alignment, with no unresolved critical/high | code-reviewer + security-reviewer subagent review of the diff | No unresolved critical/high (or fixed + re-verified) | review report in ClickUp/handoff | PASS |
| C-010 | yes | ClickUp task 86ajy5v7h carries goal ID, engine, iteration evidence, and terminal state | Inspect task 86ajy5v7h comments | Start + final evidence comments present with links | ClickUp task 86ajy5v7h | PASS |
| C-011 | no | Goal Contract structural validator passes | `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-api-device-activation.md` | Exits 0 | validator output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-criterion pytest targets; inspect actual behaviour (secrecy/idempotency/validity/audit/rollback), not just exit codes.
- Broader regression: full `pytest implementation/api/tests -q` (C-008) + `manage.py check` + `makemigrations --check` + `compileall`.
- Independent verifier: code-reviewer + security-reviewer subagents on the diff (C-009); not self-certified.
- Required environment: `/private/tmp/selahcue-api-venv` Python; repository working tree.

## Iteration ledger

### Iteration 1

- Target criterion: setup (C-010, C-011)
- Hypothesis: a validated contract + a registered ClickUp task under the new epic are prerequisites; DEC-004 fixes the model so the slice is unblocked.
- Change: recorded DEC-004 + annotated OD-04; created epic 86ajy5v6k + task 86ajy5v7h; investigated slice conventions; authored this contract; confirmed baseline suite green (18 passed).
- Verifier executed: baseline pytest (18 passed); validator (pending run).
- Result: baseline established.
- Decision: iterate

## Risks and rollback

- Risks: (1) secret leakage (token) — mitigated by mirroring the proven license-key show-once/hash/fingerprint pattern + first-class secrecy tests (C-006) + independent security review (C-009). (2) migration drift — mitigated by `makemigrations --check` (C-001). (3) SafeAPIError inert outside GraphQL — mitigated by an explicit view-level code→status mapper (C-003). (4) over-reach into the deferred signed-policy/IdP scope — mitigated by explicit non-goals + flags.
- Rollback: all changes additive (new app + migration + one view swap + tests). Revert = remove the devices app + restore the 501 stub; no other slice touched.

## Pause and escalation conditions

- BLOCKED to product/security if a criterion requires the signed policy-envelope crypto or account IdP (out of scope for this slice).
- Stop after three materially different failed attempts on a criterion without new evidence; report the smallest unblocker.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-api-device-activation.md --require-complete
- Validator result: PASS (all 10 mandatory criteria PASS)
- Independent verification result: independent security+correctness review — secrecy + no-token-leak invariants confirmed HOLD; no critical/high. Fixed [MEDIUM] instance-limit race (select_for_update) + [LOW/MED] revoked-device re-activation (POLICY_DENIED) + test hardening; re-verified.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none. Deferred (open owner decisions, flagged): signed policy-envelope crypto, account IdP, offline-grace duration, other /v1 endpoints.
- ClickUp final evidence comment: posted to task 86ajy5v7h; task moved to code review.

### Iteration 2 — build + verify + independent review + fixes

- Target criteria: C-001..C-010
- Change: new `selahcue_api.apps.devices` (Device + DeviceToken + migration); `activate_device` service (fingerprint lookup + check_password, validity/status/instance-limit, show-once token, ISSUED->ACTIVATED, audit, idempotency, rollback); real `POST /v1/activations` view (SafeAPIError->HTTP map); settings + foundation-test updates; `tests/test_device_activation_slice.py`.
- Verifier executed: `pytest implementation/api/tests -q` (28 passed) + `manage.py check` + `makemigrations --check` + `compileall` — all clean.
- Independent review: security+correctness subagent — invariants hold, no critical/high. Fixed MEDIUM (instance-limit concurrency: `select_for_update` on the license key serialises activations) + LOW/MED (revoked device re-activation now POLICY_DENIED) + hardened tests (key stays ISSUED on rollback; presented key absent from audit; revoked-device denial). Findings 3/4 (safely-handled check-constraint edge; non-exploitable timing) accepted/documented.
- Result: all mandatory criteria PASS.
- Decision: complete
