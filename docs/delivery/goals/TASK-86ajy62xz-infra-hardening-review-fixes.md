# Goal Contract — TASK-86ajy62xz-infra-hardening-review-fixes

## Identity

- Goal ID: TASK-86ajy62xz-infra-hardening-review-fixes
- Parent goal ID: BUILD-selahcue
- Title: Every confirmed code-review and security-review finding on the landed Platform API infra + hardening batch is fixed, with a regression test that fails against the old shape
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy62xz
- Created: 2026-08-14
- Updated: 2026-08-14
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The eleven owner-accepted review findings against `cc66e75..HEAD` are remediated in
`implementation/api`, the rate limiter can never leave a counter key without a TTL, and the
suite that let the blocker ship now observes window expiry and the rollover race.

## Baseline

Verified on 2026-08-14 before any edit, with `/private/tmp/selahcue-api-venv/bin/python` from
`implementation/api`:

- `pytest tests -q` → `130 passed, 1 skipped in 34.05s`
- `manage.py check` → clean
- `manage.py makemigrations --check --dry-run` → clean

Verified defect: `CacheStore.incr_with_expiry` uses `cache.add()` then `cache.incr()`.
`django.core.cache.backends.redis.RedisCacheClient.incr` is `EXISTS` then `INCR` — two round
trips. A TTL lapse between them makes Redis `INCR` recreate the key at 1 **with no expiry**;
`add()` can then never reclaim it and no code path sets a TTL, so that key 429s permanently.
Not reproducible on `LocMemCache`, which evaluates expiry under a lock — which is why the suite
was green.

## Inputs and evidence sources

- Owner-accepted findings list (parent-agent brief, 11 items, with explicit out-of-scope set)
- `docs/superpowers/specs/2026-08-14-platform-api-infra-hardening-design.md` (§3 specifies
  `INCR` + `EXPIRE` on first increment — the safe shape the implementation did not follow)
- `docs/superpowers/plans/2026-08-14-platform-api-infra-hardening.md`
- Django 6.1 source: `django/core/cache/backends/redis.py`, `django/test/testcases.py`
- Repository `CLAUDE.md` (bounded memory, bounded logs, NFR-024)
- ClickUp 86ajy62xz (rate limiting) and 86ajyq86g (concurrency review), parent epic 86ajy5v6k

## Scope

### In scope

- F1 TTL-safe `incr_with_expiry` + clock-injected fake store covering window reset and the
  rollover race
- F2 `ipaddress` validation of the derived client IP with `REMOTE_ADDR` fallback
- F3 `transaction.on_commit` for the three `get_email_sender()` dispatches
- F4 bounded (non-traceback) logging in `should_allow`
- F5 `argsrepr`/`kwargsrepr` redaction on the three email tasks
- F6 `ImproperlyConfigured` guard on `CELERY_TASK_ALWAYS_EAGER` in prod
- F7 Django system-check **Warning** for `SELAHCUE_TRUSTED_PROXY_COUNT == 0` behind a proxy
- F8 index on `DeviceToken.status` + migration
- F9 per-label delete counts in `sweep_expired_credentials`
- F10 three tests that pass for the wrong reason
- F11 `threading.Barrier(2)` in the Postgres concurrency test

### Non-goals

- Cascade behaviour on SUSPENDED/CONVERTED/ARCHIVED and any reinstatement path — owner decision
- Choosing the production value of `SELAHCUE_TRUSTED_PROXY_COUNT` — owner decision; F7 only
  surfaces the risk
- Making `SELAHCUE_THROTTLE_*` env-configurable — owner decision
- `select_for_update` on the cascade for concurrent-worker double-revocation — owner decision
- `implementation/api/Dockerfile`, `implementation/api/.dockerignore`,
  `implementation/docker-compose.yml` — owned by a concurrent agent this session

### Constraints

- Bare `pytest` must stay green with no Redis, no Postgres and no Docker
- The limiter must keep failing OPEN
- `account_exists` email must carry no URL
- Tasks must stay idempotent under `acks_late`
- Bounded batches and bounded logs (CLAUDE.md); NFR-024 unaffected
- Path-scoped `git add` only; never stage `docs/delivery/BUILD_STATE.md` or
  `docs/product/audits/PRODUCT-GAP-AUDIT-2026-08-14.md`; one commit; no push

### Assumptions and unknowns

- ASSUMED: `cache.touch(key, timeout)` is available on every backend this project uses — it is
  part of the Django `BaseCache` API (Redis and LocMem both implement it). Validated by test.
- UNKNOWN: the real production proxy depth. Owner decision; F7 only emits a warning.

## Dependencies and approvals

- Concurrent agent owns the three container files — no approval needed, avoidance only. Status: active.
- Owner already accepted all eleven findings; no further product approval required. Status: granted.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | No `incr_with_expiry` path can leave the counter key persistent | `pytest tests/test_throttling.py -q` | rollover-race + window-reset tests pass | `14 passed`; `CacheStore.incr_with_expiry` touches on every count of 1 and in the ValueError branch | PASS |
| C-002 | yes | The rollover-race test FAILS against the pre-fix `add()`+`incr()` shape | new test run against the reconstructed old store | 1 failed | `1 failed, 2 passed` — "INCR recreated the counter with no expiry … assert None is not None" | PASS |
| C-003 | yes | A non-IP `X-Forwarded-For` entry falls back to `REMOTE_ADDR`; a valid IPv6 entry is accepted | `pytest tests/test_throttling.py -q` | both pass | `test_forged_non_ip_entry_falls_back_to_remote_addr`, `test_valid_ipv6_forwarded_entry_is_accepted` | PASS |
| C-004 | yes | The three email dispatches run only after commit | `pytest tests/test_customer_auth_slice.py -q` | all pass, assertions unweakened | `27 passed`; new `test_rolled_back_signup_queues_no_verification_email` fails against inline dispatch | PASS |
| C-005 | yes | `should_allow` emits no traceback per failing request | `pytest -k store_outage_logs_once`; code review | single `logger.warning`, no `logger.exception` | 200 failing requests produce exactly 1 record, `exc_info is None` | PASS |
| C-006 | yes | Raw tokens cannot reach worker logs via task args | `pytest tests/test_email_delivery.py -q` | redaction test passes, tasks still execute | `9 passed`; `argsrepr="(<redacted>)"`, worker still receives real args | PASS |
| C-007 | yes | `CELERY_TASK_ALWAYS_EAGER=1` with `ENVIRONMENT=prod` raises `ImproperlyConfigured` | subprocess `manage.py check` with that env | non-zero exit, `ImproperlyConfigured` | exit 1 + `ImproperlyConfigured`; prod without eager exits 0 | PASS |
| C-008 | yes | A system-check **Warning** (not Error) fires for proxy-count 0 behind a proxy | `CACHE_URL=… manage.py check` | exit 0 with `WARNINGS:` | `selahcue_throttling.W001` printed, exit 0; silent once hop count > 0 | PASS |
| C-009 | yes | `DeviceToken.status` has a usable index and migrations are clean | `manage.py makemigrations --check --noinput` | `No changes detected` | `0002_devicetoken_device_token_status_idx.py`; `No changes detected`, exit 0 | PASS |
| C-010 | yes | `sweep_expired_credentials` reports per-label counts | `pytest tests/test_revocation_cascade.py -q` | exact-count assertions still pass | `16 passed` incl. the exact-count and idempotency sweeps | PASS |
| C-011 | yes | The three weak tests now fail for a limiter/decorator/dispatch defect | `pytest tests -q` | pass; assertions target the real property | full 4-response sequence asserted; per-IP budgets asserted; eager dispatch asserted | PASS |
| C-012 | yes | The Postgres concurrency test forces thread overlap | barrier probe + code review | overlap observed; SQLite skip retained | probe: "both threads inside simultaneously: True", "without the barrier … never overlap: True" | PASS |
| C-013 | yes | Full suite, system check and migration check all green | `pytest tests -q`; `manage.py check`; `manage.py makemigrations --check --noinput` | 147 passed, 1 skipped; no issues; no changes | see Final evaluation | PASS |
| C-014 | yes | No container file and no unrelated WIP is staged | `git diff --cached --stat` before commit | none of the three infra files, BUILD_STATE.md, or the audit doc | staged set = 15 files, all under `implementation/api/` + this contract | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-finding pytest selection; a reconstructed pre-fix store to prove the
  race test discriminates; a subprocess `manage.py check` for each settings guard.
- Broader regression verification: full `pytest tests -q`, `manage.py check`,
  `manage.py makemigrations --check --dry-run`, all three from `implementation/api`.
- Independent verifier: the owner's own review pass on the resulting commit.
- Required environment: `/private/tmp/selahcue-api-venv/bin/python`, no Redis, no Postgres, no Docker.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: `add()`+`incr()` cannot guarantee a TTL because Django's Redis `incr` is
  `EXISTS`+`INCR`; asserting the TTL after every increment that returns 1 closes the window.
- Change or investigation: read the Django 6.1 Redis backend, then rewrite `incr_with_expiry`
  to touch the key whenever the count is 1, and build a TTL-tracking clock-injected fake.
- Verifier executed: `pytest tests/test_throttling.py -q`, plus the race test against a
  reconstructed pre-fix store.
- Result: recorded in Final evaluation.
- New evidence: recorded in Final evaluation.
- Decision: iterate

### Iteration 2

- Target criterion: C-003 … C-012
- Hypothesis: the remaining ten findings are independent and each admits a local fix plus a
  test that fails against the pre-fix shape.
- Change or investigation: applied per finding, smallest coherent increment each.
- Verifier executed: per-criterion verifiers listed above.
- Result: recorded in Final evaluation.
- New evidence: recorded in Final evaluation.
- Decision: iterate

### Iteration 3

- Target criterion: C-013, C-014
- Hypothesis: the combined change keeps the full suite, system check and migration check green
  and touches nothing owned by the concurrent agent.
- Change or investigation: full regression run and a path-scoped commit.
- Verifier executed: `pytest tests -q`; `manage.py check`; `makemigrations --check`; `git show --stat`.
- Result: recorded in Final evaluation.
- New evidence: recorded in Final evaluation.
- Decision: complete

## Risks and rollback

- Risks: `on_commit` changes the observable moment of email dispatch, so any test reading a
  captured token immediately after the mutation breaks — mitigated by executing on-commit
  callbacks around the request in the test helper rather than by weakening assertions.
  Adding an index is an online `CREATE INDEX` on a small table; negligible.
- Rollback or recovery: single commit, `git revert` restores the prior behaviour; the migration
  is a pure index add and reverses cleanly.

## Pause and escalation conditions

- Any finding that turns out to be wrong on evidence — report it rather than implement it (owner instruction).
- Any change that would require touching the three container files — stop, the concurrent agent owns them.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajy62xz-infra-hardening-review-fixes.md --require-complete`
- Validator result: PASS (14 criteria, 14 mandatory, all PASS)
- Regression evidence, from `implementation/api` with `/private/tmp/selahcue-api-venv/bin/python`:
  - `pytest tests -q` → `147 passed, 1 skipped in 48.99s` (baseline was 130 passed, 1 skipped)
  - `manage.py check` → `System check identified no issues (0 silenced).` exit 0
  - `manage.py makemigrations --check --noinput` → `No changes detected` exit 0
- Independent verification result: PENDING — the owner reviews the resulting commit. Two
  properties cannot be executed in this environment and are verified by CI's `api` job, which
  runs the suite against real Postgres + Redis: the `threading.Barrier` overlap in
  `test_concurrency_postgres.py` (skipped on SQLite by design) and the limiter against a real
  Redis backend. The barrier's thread structure was verified here with a stubbed
  `activate_device`.
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none
- Carried forward as owner decisions, deliberately NOT implemented: cascade reinstatement
  path; the production value of `SELAHCUE_TRUSTED_PROXY_COUNT`; env-configurable
  `SELAHCUE_THROTTLE_*`; `select_for_update` on the cascade. Plus one raised by this work: the
  new `status` index does not by itself stop the hourly full walk, because `ACTIVE` is the
  dominant value in steady state — the effective fix is to drive the cascade query from the
  (rare) non-activatable licence keys instead. Recommended as a follow-up ticket.
- ClickUp final evidence comment: posted on 86ajy62xz.
