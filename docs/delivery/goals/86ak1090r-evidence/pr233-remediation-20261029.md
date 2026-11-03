# PR233 remediation verification, 2026-10-29

Implementation is ready for fresh independent review. Overall delivery remains **BLOCKED**
by owner decisions and pending complete corrected-revision CI/reviews. No merge approval.

## Immutable code history

- Original PR head: `92d52e7f8c85e6b94d65c3679c3e8bb33d5d8381` (preserved ancestor).
- Main integration: `4b6d178d` (fresh origin/main merged, no conflict).
- Regression-first: `7357366da7bd607fb14bd6f5771fe9ac38e4c9f6`.
- Renewal/recovery/replay/cascade: `3b0fdda51dd427994e1e8d4d7f7457bad40ddfff`.
- Writer-guard correction: `31a47bd707db76306c1219c7595d613019a4e593`.
- API CI runtime headroom: `f088fcff7b3eefd1209c0c83f9a8c1588b284d30`.

## Verification and limits

Dedicated CPython3.14.5 editable runtime, PostgreSQL16.2 and Redis7. All databases/caches
were disposable and isolated from other assignments. Full gate uses database
`remediation233_full`/RedisDB3; focused gates use `remediation233`/RedisDB1 on own services.

- Core regression RED: 4 failures reproduced; 3 dead-token negative controls passed.
- Core regression GREEN: 7 passed, 366 deselected,24.94s.
- Initial real-Postgres renewal/revoke/extension/duplicate-cascade seams: 9 passed,18.25s.
- ADMIN recovery RED: 9 meaningful failures; GREEN selected HTTP recovery checks:11 passed,13.19s.
- Extra queued replacement and real-revoke backlog/restart checks:6 passed,29.94s, with a
  teardown warning because the first full gate started too early on that test database.
  That full attempt was stopped (-15 after110.83s), logs preserved; no pass claim.
- Full separate-database gate before the final correction: `manage.py check` exit0;
  `manage.py makemigrations --check --noinput` exit0; entire pytest exit1:
  **1848 passed,1 failed,1 xfailed, no skips**,540.89s pytest /541.915s wrapper.
  Sole failure: existing licence-writer AST guard conservatively classified the cascade's
  existing `token.status` assignment after the new licence-lock import.
- Correction keeps the guard unchanged and writes through an explicitly DeviceToken-rooted
  update under the same locks/audit transaction. Final covering command:
  `python -m pytest tests/test_license_state_machine.py tests/test_revocation_cascade.py tests/test_concurrency_postgres.py -q -rfEs --durations=10`
  on real Postgres/Redis: **194 passed,56.18s,exit0,no skips/warnings**. This includes all
  writer-guard positive/negative controls, the >500-token real-revoke/restart test, duplicate
  cascade audit race, queued refresh/revoke/extension orders and concurrent ADMIN recovery.
- `actionlint -shellcheck='' .github/workflows/ci.yml`:exit0.
- `python3 .github/scripts/check_ci_minutes.py`:exit0,5 workflows satisfy minute rules.
- `python3 scripts/check_api_gate.py --self-test`:46 cases,0 failed.
- API CI timeout15→30minutes, explicitly approved by coordinator: previous hosted15minute
  timeout plus realistic local9minute complete-suite runtime justify bounded headroom;
  every install/check/test command and Postgres/Redis service remains unchanged.
- No second full local run after the small correction, per coordinator instruction.
  **A complete CI pass on the final published revision is still mandatory before merge.**

Commands ran in `implementation/api` with `/private/tmp/selahcue-remediation233-venv/bin/python`.
Full command was `python -m pytest -q -rfEs --durations=25`; environment selected
`django.db.backends.postgresql`, own loopback port55433, synthetic role`remediation`, and
own Redis loopback port56333. Exact complete commands, final exit codes/times and logs:
`/private/tmp/selahcue-remediation-20261029/task-1-report.md`, `task-1-complete-results.json`,
`task-1-complete-2.log`, `task-1-correction-covering.log`. No real credentials in this summary.

## Contract and recovery choices

Refresh rotates only a still-live token after a valid extension. Locks licence→device→token,
then re-authenticates; old-token revocation, replacement and masked audit are atomic.
Additive `activation_token` is show-once/no-store; ordinary status responses/audits have no
raw credential. The HTTP caller regression adopts it before subsequent calls.

An explicitly approved `replace_token` option on existing ADMIN account activation provides
lost-response recovery. Default=false; strict boolean; known ACTIVE same-org installation;
licence/plan/role gates retained. Fresh intent rotates, same intent never re-shows a secret.
Only account ADMIN authority can request this; enrollment-key activation has no such option.
NativeHTTP and accountGraphQL share the service. No native refresh/recovery UI is claimed.

Searches across tracked desktop/mobile/marketing/scripts found no shipped refresh consumer;
`selahcue-licensing` implements activation/manifest retrieval. Public API README and account
API handoff now describe rotation, secure persistence and actual HTTP ADMIN recovery.

Cascade uses500-token working sets, prompt drain, between-batch240s delivery budget and
minute recovery ticks. Persisted ACTIVE rows survive lost continuations/restarts. This is
not unlimited throughput or a guarantee during prolonged worker/database/broker outage.

## Unresolved gates and pending external work

- AC7/C-014 production-writer count: no accepted table-only interpretation found.
- ADMIN-GQL-006 consequence confirmation remains unbuilt/open decision17tnw2b9dpq;
  no approved token protocol/waiver was available. No implementation was invented.
- DEC-020 remains PROPOSED, not accepted.
- New revision needs independent Cody/Shadow/Quinn/Vera review and final complete CI.
- ClickUp quota/unconfigured REST prevent updates; coordinator has a pending local payload.
- No push/merge/external comment by implementer; coordinator owns existing PR publication.
