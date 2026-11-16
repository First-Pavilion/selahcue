# Session password Unicode refusal — 17tnw2bbfm5

Ticket: [API malformed password refusal](https://app.clickup.com/t/17tnw2bbfm5).

## Verified behavior

A lone-surrogate candidate now takes the ordinary credential-refusal branch. Login hashes an empty safe candidate but forces a non-match for the original unencodable string. Unknown and locked accounts retain their existing hash-and-refuse paths. Known accounts retain failed-attempt increments and account lockout. No schema or route changes.

The original string is never logged. Native response tests capture logs from real HTTP requests and require no ERROR records or exception traces, 401 UNAUTHENTICATED identical to ordinary unknown-account refusal, no cookies, no sessions and no-store responses. Three malformed candidates exercise known, unknown and locked accounts; an instrumented original PBKDF2 encoder confirms three real hashes for each group. An empty stored-password fixture verifies the safe substitute cannot authenticate. Source throttle behavior remains ten 401s followed by 429. Direct-service callers with byte passwords retain success for correct UTF-8 bytes and refusal for invalid UTF-8 bytes.

GraphQL baseline was explicitly observed: malformed passwords previously raised UnicodeEncodeError and were collapsed to VALIDATION_FAILED; ordinary wrong passwords returned UNAUTHENTICATED. After shared credential normalization, malformed passwords return the same stable coded UNAUTHENTICATED as wrong passwords. Successful login/session behavior remains governed by existing tests.

## Environment

Local SQLite `:memory:`, scrubbed `env -i` (only PATH, HOME, TMPDIR and SQL_DATABASE), same-repository installed runtime `/Users/m.oluwole/.codex/worktrees/batch20-dev-env-cap/scph/implementation/api/.venv-api-check/bin/python`, Django 6.1.2. Pytest cwd and pytest.ini pythonpath select THIS ticket checkout's source. No environment files or credentials loaded. No external providers, production or packaging calls.

## RED then GREEN

- Before implementation: `python -m pytest tests/test_login_unicode_password.py -q --tb=short` → **5 failed, 1 passed**. Three native parameter groups and lockout failed due to HTTP 500 with Django ERROR UnicodeEncodeError traces. GraphQL failed because malformed VALIDATION_FAILED differed from ordinary UNAUTHENTICATED. Byte-password compatibility already passed. Raw output is local `/private/tmp/17tnw2bbfm5-red.txt` (synthetic test fixtures only).
- After implementation and two additional guard cases: `python -m pytest tests/test_login_unicode_password.py -q` → **8 passed in 13.26s**. Output `/private/tmp/17tnw2bbfm5-focused.txt`.
- `python manage.py check` → **no issues**.
- `python manage.py makemigrations --check --dry-run` → **no changes detected**.
- `git diff --check` → **passed**.
- Compatibility: `python -m pytest tests/test_login_unicode_password.py tests/test_native_account_surface.py tests/test_native_login_outage.py tests/test_customer_auth_slice.py -q --tb=short` → running; raw output `/private/tmp/17tnw2bbfm5-green.txt`.
- Full API: `python -m pytest tests -q -rfEs` → running; raw output `/private/tmp/17tnw2bbfm5-suite.txt`.

## Limits and next gates

SQLite cannot exercise tests requiring PostgreSQL or Redis; exact suite skips will be reported when its run completes. No wall-clock timing benchmark is claimed: original KDF execution is directly measured; existing account/timing tests remain in the regression suites. Cody, Shadow, Quinn and Vera reviews are pending root coordination. No completion, merge, QA or deployment claim is made.
