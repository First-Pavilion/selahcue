# P12 private grant source evidence

Ticket: https://app.clickup.com/t/17tnw2bbhxm . Kenji backend source increment. Base: cbc1e541f66f4f99fae0591733e2497a670b9fbd. Original source baseline3f651d14; reviewed Linux bootstrap delta does not touch API inputs.

## Actual checks

- Own Python3.14.5 venv `/private/tmp/kenji-p12-venv`, pinned API direct/dev dependencies installed offline from local cache. Initial unprivileged uv cache access was denied; authorized dependency installation succeeded.
- Baseline `pytest tests/test_pilot_registration_service.py -q`:32passed. One nonfunctional cache-write warning from the managed worktree; later commands disable pytest cache.
- Initial RED: configured grant endpoint returned404 rather than required503 for a missing real signer; subsequent63 new behavior tests failed before new modules existed.
- First source GREEN attempt62passed/1failed: the test helper replaced explicit None receipt with a real receipt. Corrected helper; combined grant/P13/deployment-registry/foundation/route-inventory run:347passed.
- Additional configuration/HTTP/throttle tests:84passed/1failed, confirming NUL-character token admission. Fixed validator to printable ASCII. Current `pytest tests/test_pilot_grants.py -q -p no:cacheprovider`:85passed/1skipped. The skipped test specifically requires actual PostgreSQL concurrent replay, not simulated SQLite locking.
- `SQL_DATABASE=:memory: python manage.py check`: no issues. `makemigrations --check --dry-run`: no changes. Initial default-worktree SQLite check could not create its DB; it was rerun against the explicit in-memory check DB, without changing user data or permissions.
- Full API suite is **RUNNING/PENDING** against a new disposable PostgreSQL17 container, with newly generated credentials held in the harness memory only. It includes a four-thread replay test that asserts one registration/allocation and unchanged confirmation time, and refuses signing inside a DB transaction. No existing container credentials were inspected/extracted. Private output: `/private/tmp/kenji-p12-postgres-full.log`; harness automatically removes its own fixture after completion. Root will receive final results separately. This pending run is not a passing check.
- `git diff --check` and structural Goal Contract validation pass before source freeze. Full hosted CI and Cody/Shadow/Quinn/Vera verdicts remain pending.

## Source contract and limits

Dedicated n8n server credential/auth-before-body,8KiB request bound, no-cookie/no-CORS authority, fixed safe errors/headers and independent fail-closed30/minute throttle. P13 authenticity, live confirmed ledger, platform/retention and anchored expiry are reused unchanged. Only opaque artifact IDs resolve against a hash-pinned≤64KiB complete promoted manifest. Exactly Windows x64/Ubuntu x64/Mac Universal, content-addressed immutable keys and approved explicit signing policy; Mac remains Developer ID/notarized/stapled.

Read expiry is min(original receipt, configured pilot, fixed2027-04-30T23:59:59Z cohort, manifest, artifact/provider, explicit≤300-second TTL). Result origin/object/query/expiry are validated and clock is rechecked after signer execution. No registration/contact/church values or provider keys are added to URLs/ledger/logs. Licensed501 routes are unchanged; no migrations, jobs or actual remote storage call added.

There is deliberately **no production signer or fake URL generator**. P10 actual provider/account/region/permissions/immutability/read evidence, P11 real verified complete promotion, P15 approved collection policy, actual n8n selection/link integration and clean platform evidence remain mandatory. The exact P11/P10 source interface is in `docs/release/pilot-download-grants.md`; producer compatibility remains to be confirmed. No n8n/marketing edits or enablement, real credentials, bucket operations or installation/publication occurred. Existing P12 real private-read/full-journey criterion stays BLOCKED. A source merge is not a completed installer/download claim.

Root owns current ClickUp browser reread/start/evidence/status. Those actions remain pending/unverified while browser access is unavailable; no connector/API workaround was used.
