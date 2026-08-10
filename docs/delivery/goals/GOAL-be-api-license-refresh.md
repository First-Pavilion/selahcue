# Goal Contract — GOAL-be-api-license-refresh

## Identity

- Goal ID: GOAL-be-api-license-refresh
- Parent goal ID: 86ajy5v6k (EPIC — Platform API / Licensing & Entitlements)
- Title: Implement `POST /v1/license:refresh` + the reusable device-token authentication for the SelahCue Platform API — a device presents its token and receives current license/entitlement status (offline-entitlement refresh, DEC-004)
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy5yze
- Created: 2026-08-09
- Updated: 2026-08-09
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Replace the `/v1/license:refresh` 501 stub with a real endpoint: a device presents its device token (Bearer); the server authenticates it (HMAC-fingerprint lookup of `DeviceToken` + constant-time `check_password`, status ACTIVE + not expired → resolve `Device`; any failure → UNAUTHENTICATED, no oracle) and returns the current license/entitlement status (license status + validity window, instance usage vs limit, token expiry, feature scope/territory) so the desktop can refresh its cached offline entitlement — delivering the reusable device-token authentication that every remaining `device_token`-gated `/v1` endpoint depends on.

## Baseline

- Device-activation slice shipped (task 86ajy5v7h): `apps/devices` with `Device` + `DeviceToken` (token stored as `make_password` hash + unique HMAC `token_fingerprint` + masked triple + `status` + `expires_at`). Full API suite green (28 passed).
- `/v1/license:refresh` is a 501 stub (`platform/views.py:license_refresh_not_implemented`), auth_context `device_token`; URL + contract declared.
- Conventions: frozen-dataclass services, `SafeAPIError(ErrorCode.X)`, `_fingerprint` = HMAC over `settings.SECRET_KEY`, `command_error_response` (SafeAPIError→HTTP status map, already added in the activation slice), redaction on error payloads.

## Inputs and evidence sources

- DEC-004; `implementation/api` devices + license_keys slices; `platform/views.py` (the activation view + error mapper); `graphql/context.py` (ErrorCode.UNAUTHENTICATED), `errors.py`.
- ClickUp epic 86ajy5v6k; activation task 86ajy5v7h.

## Scope

### In scope

- `apps/devices/services.py`: `authenticate_device_token(presented_token) -> Device` (reusable) + `refresh_license(presented_token) -> LicenseRefreshResult` assembling the status.
- `POST /v1/license:refresh` view: read the device token from `Authorization: Bearer <token>` (fallback body `device_token`), call the service, map errors via `command_error_response`, return status JSON.
- Remove `/v1/license:refresh` from the two 501-stub lists in `test_foundation_contract.py`.
- Tests `tests/test_license_refresh_slice.py` mirroring the activation-slice tests.

### Non-goals

- Device-token rotation / re-issue (this slice is a pure status read).
- Signed policy-envelope crypto; account IdP; offline-grace duration.
- `/v1/entitlements/manifest` (needs the entitlements domain) + other endpoints.
- New models/migrations (reuse `DeviceToken`); no schema change.

### Constraints

- Reuse `settings.SECRET_KEY` HMAC so a token issued at activation resolves here.
- No secret in responses/logs; error payloads run through `assert_no_restricted_payload_fields`.
- Pure read: no mutation, no audit noise, no new migration.
- Truthfully report an expired/revoked *license* status (client acts on it); only an invalid *token* denies (UNAUTHENTICATED).

### Assumptions and unknowns

- ASSUMED: device token presented as `Authorization: Bearer`. Owner: backend-engineer (matches the desktop cloud client).
- UNKNOWN: signed policy envelope + rotation — deferred.

## Dependencies and approvals

- Depends on the device-activation slice (86ajy5v7h) — DONE.
- Python venv `/private/tmp/selahcue-api-venv` — present.
- Independent review — required; not self-certified.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `authenticate_device_token` resolves a Device from a valid token (fingerprint + check_password, ACTIVE, not expired); unknown/mismatch/expired/revoked → UNAUTHENTICATED, no device leaked | `pytest tests/test_license_refresh_slice.py -q` (auth tests) | Exits 0; valid token resolves; each invalid case → 401 UNAUTHENTICATED | test file + output | PASS |
| C-002 | yes | `POST /v1/license:refresh` returns 200 with the current license/entitlement status for a valid device token | `pytest` HTTP test | 200 with license status + validity window + instance usage + token expiry; no secret in body | test output | PASS |
| C-003 | yes | An expired/revoked *license* is reported truthfully in the status (not a hard token denial); an invalid *token* is 401 | `pytest` status tests | expired-license refresh → 200 with status reflecting expiry; invalid token → 401 | test output | PASS |
| C-004 | yes | No secret leakage: the presented token / its hash never appear in the response or logs; error payloads carry no secret | `pytest` secrecy test + review | token absent from response JSON beyond the caller's own input; error bodies coded-only | test output | PASS |
| C-005 | yes | The full API suite is green; system check + migration state + compile clean (no new migration) | `pytest implementation/api/tests -q`; `manage.py check`; `manage.py makemigrations --check --dry-run`; `compileall` | pytest all pass (≥ 28 + new); check clean; "No changes detected"; compile 0 | suite output | PASS |
| C-006 | yes | Independent review (security + correctness) confirms token-auth safety (no oracle, constant-time, no secret leak) with no unresolved critical/high | code-reviewer + security-reviewer subagent | No unresolved critical/high (or fixed + re-verified) | review report | PASS |
| C-007 | yes | ClickUp task 86ajy5yze carries goal ID, engine, evidence, terminal state | Inspect task 86ajy5yze | Start + final comments present | ClickUp task 86ajy5yze | PASS |
| C-008 | no | Goal Contract structural validator passes | `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-api-license-refresh.md` | Exits 0 | validator output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-criterion pytest; inspect actual behaviour (auth denials, truthful status, secrecy).
- Broader: full `pytest implementation/api/tests -q` + `manage.py check` + `makemigrations --check` + `compileall` (C-005).
- Independent verifier: security + correctness subagent (C-006); not self-certified.
- Environment: `/private/tmp/selahcue-api-venv` Python.

## Iteration ledger

### Iteration 1

- Target: setup (C-007, C-008)
- Change: created task 86ajy5yze under epic 86ajy5v6k; authored this contract; device-activation baseline green (28 passed).
- Verifier executed: validator (pending run).
- Result: baseline established.
- Decision: iterate

## Risks and rollback

- Risks: (1) token-auth oracle/timing — mitigated by fingerprint lookup + constant-time verify + uniform UNAUTHENTICATED + independent review. (2) secret leak — first-class secrecy test. (3) scope creep into rotation/policy — explicit non-goals.
- Rollback: additive (service fns + one view swap + tests); revert = restore the 501 stub; no schema change.

## Pause and escalation conditions

- BLOCKED to product/security if a criterion needs the signed policy envelope or account IdP (out of scope).
- Stop after three materially different failed attempts without new evidence.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-api-license-refresh.md --require-complete
- Validator result: PASS (all 7 mandatory criteria PASS)
- Independent verification result: independent security+correctness review — no-oracle token-auth + no-secret-leak invariants confirmed HOLD; no critical/high. Fixed the [MEDIUM] revoked-token test gap + case-insensitive Bearer + natural-expiry design test + success-payload redaction guard; re-verified. Rate-limiting (defense-in-depth) + revocation-cascade tracked as follow-ups.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none. Deferred (open owner decisions): token rotation, signed policy-envelope crypto, account IdP, other /v1 endpoints.
- ClickUp final evidence comment: posted to task 86ajy5yze; task moved to code review.

### Iteration 2 — build + verify + independent review + fixes

- Target criteria: C-001..C-007
- Change: `authenticate_device_token` + `refresh_license` + `LicenseRefreshResult` in `apps/devices/services.py`; real `POST /v1/license:refresh` view (Bearer/body token) + `_device_bearer_token`; urls + foundation-test updates; `tests/test_license_refresh_slice.py`.
- Verifier: `pytest implementation/api/tests -q` (36 passed) + `manage.py check` + `makemigrations --check` (no new migration) + `compileall` — all clean.
- Independent review: security+correctness subagent — invariants hold, no critical/high. Fixed [MEDIUM] revoked-token test gap; [LOW] case-insensitive Bearer; added the natural-license-expiry→401 design contract test; added success-payload redaction guard (defense-in-depth). Findings 4 (rate-limit) + 6 (revocation cascade) recorded as follow-ups.
- Result: all mandatory criteria PASS.
- Decision: complete
