# P12 n8n private-grant source evidence

Ticket [17tnw2bbhxm](https://app.clickup.com/t/17tnw2bbhxm). Baseline main `4e2ce4374713956a498978fdf6383c74c2c548cb`; own branch `codex/17tnw2bbhxm-grant-workflow`. This is the remaining workflow integration, not proof of the original actual-private-read criterion.

## Verified source behavior

- One reviewed nonsecret configuration produces the pre-submit package label and the validator's fixed artifact/release/version/platform/architecture/hash/size/object/origin/query policy. Defaults are deliberately invalid; the export remains inactive with successful/error/manual execution payload saving disabled.
- Wrong submitted platform refuses before reserve or Sheet write. Browser artifact/path/version fields cannot replace configuration. Existing stable UUID and same-row recovery behavior is preserved.
- Fresh and already-confirmed paths join the existing receipt validator, then make the same dedicated server grant request with only schema version, receipt and fixed artifact ID. Registration callbacks and grant require different credentials at deployment.
- Exact response shape and package metadata, fixed HTTPS origin/object path, distinct allowlisted signature query keys and future expiry are required. Maximum expiry is the minimum of original receipt, fixed `2027-04-30T23:59:59Z` cutoff and configured read TTL (at most 300 seconds).
- Success projects only escaped metadata/link HTML. No receipt, registration identity or contact/church fields become completion input. Sheet, confirmation, transport, malformed grant and expiry failures route to fixed retry output without a link. No redirect or latest-package fallback is added.

## Executed checks

- Structural Goal validator: PASS before substantive implementation.
- Existing workflow baseline: **7 passed**. Initial sandbox pytest cache write warning was recorded; subsequent runs use a private temporary cache and have no warning.
- New test-first boundary: initial unmarked standalone test invocation hit the repository's autouse catalogue fixture without a database. This infrastructure/setup error is not RED behavioral proof. Adding the repository's Django test database marker reached the expected RED: `build() got an unexpected keyword argument 'deployment'`, showing the proposed fixed deployment contract was absent.
- After implementation: **31 new grant-workflow tests passed**. They execute actual shipped Code with literal package/receipt/grant data, exercise metadata/config/OS/URL/query/expiry failures, execute the real grant JSON body expression, and check graph error routing and sanitized output projection.
- Combined old/new workflow cases: **38 passed**.
- Affected compatibility scope: `tests/test_pilot_workflow.py tests/test_pilot_grant_workflow.py tests/test_pilot_registration_service.py tests/test_pilot_registration_contract.py tests/test_pilot_grants.py`: **163 passed, 1 skipped, 57 subtests passed**. The skip is the existing PostgreSQL-only concurrency case on local SQLite, not a passed race test. This workflow increment changes no API/database logic.
- `git diff --check`: PASS at source preparation.

## Runtime and release boundary

Own fresh official n8n 2.45.7 fixture uses image digest `sha256:9a8d8dcea75667496695d7810d7e1fe018a65efb36cc499d347f3931b3957b5d`, loopback-only port 5688, new volume and no external/account credentials. One graph uses six synthetic UUID-selected transport outcomes; only four external transport nodes and deployment/identity labels are replaced. Product validators, IF conditions, connections and completions remain unchanged. Fixture builder/provenance are under `/private/tmp/selahcue-p12-workflow-runtime/` on the execution host. Import/publication and actual root CUA observations are pending; startup/migration is not treated as runtime success.

First fixture initialization had setup contention from prematurely started CLI workers, which were stopped (import exit 137, not success). Migrations then finished. Its JavaScript runner startup exceeded the internal 30-second grant TTL; the official log identified the failure and recommended increasing `N8N_RUNNERS_GRANT_TOKEN_TTL`. Only the own synthetic container was stopped/recreated with 300 seconds and its own newly created volume retained, without reading existing container environment or credentials. These setup attempts are not product execution passes. The current own container is `selahcue-p12-n8n-runtime`; the failed original is stopped. No deployment/runtime settings in the repository changed.

Real HTTP/header authentication, Google OAuth/Sheet persistence, real receipt signatures, private object bytes, three-platform packages, actual provider policy and deployment are **not proved by these mocks**. P10/P11/P13/P14/P15 inputs and original P12 C-004 remain blocked. Version display binding requires a reviewed mapping to the promoted P11 manifest/public projection and matching P14 entry; the grant response itself has no version field. No actual keys, provider, bucket, store submission, live collection or public marketing enablement occurred.

All four independent reviews and applicable current CI are pending root coordination. Do not mark P12 Done from this source evidence.
