# Managed Free licence lifecycle — source checkpoint

Task1 is implemented and independently reviewed through d59d1c4db92429600a3f15eade0b30df77b975f4. The initial304 focused PG tests preceded the live-replay correction; the correction has58 focused PG/wire passes. Independent review identified the live-replay mutation; scoped re-review at d59d1c4d confirmed it addressed, with spec and quality PASS and no fix regression. The original 12-file review found no other actionable issue. Exact implementation commands and their revision limits follow below. Full hosted CI, integration with the final native foundation, deployment and public cloud enablement remain separate. This is not a final release or provider-qualification claim.

# Task 1 implementation evidence

Baseline `4d46c56be00218ea79d4d43c4d8f0c34591dedc8`, worktree branch `codex/free-public-cloud-20261114`.

- Initial session activation issues a 365-day catalogue FREE licence for a verified, active self-service ADMIN whose org has no licence history. Legacy self-signup TRIAL promotion is audited. The existing CUSTOM key type supplies the key format. Staff issuance runs through its existing permission wrapper and shares the same internal issuance, catalogue assignment, and date-overlap checks.
- Existing eligible unmarked licences keep their existing plan and activation behavior. The managed marker is unique per org and licence. Automatic expiry changes require its current enabled policy version and an explicit FREE catalogue assignment. Staff reassignment preserves the existing valid licence and stops managed extension while assigned to another plan.
- Activation and refresh serialize on the existing org lock. Bound replays and recovery verify the exact receipt or device first. A valid original receipt replay carries no credential. A dead-result replay by a qualifying ADMIN can disclose the completed device identity without renewing or minting, even when its managed Free licence expired. Separate explicit recovery uses G1 for that device and fails closed on overlapping windows.
- A credential must authenticate and be live after lock acquisition to extend its date. Refresh can renew the licence at or within 30 days and updates the one presented token. A different token can catch up once it is itself presented live within the same threshold. A disabled marker stops extension. Suspended refresh remains a read-only status report.
- No provider or weekly usage model is part of this slice. The tracked changes do not create provider resources or reset a ledger. The tests use synthetic credentials and a uniquely named PostgreSQL 17 container published only to loopback.

## Red, green and schema evidence

Commands below ran from `implementation/api` unless noted. `PYTHON` is `/private/tmp/selahcue-pilot-runtime.QZIuGQ/venv/bin/python`. The invocations used a cleared environment with `PATH`, `HOME`, and `ENVIRONMENT=dev`. For PostgreSQL runs, `SQL_ENGINE=django.db.backends.postgresql`, `SQL_DATABASE=free_lifecycle_test`, `SQL_USER=free_lifecycle_test`, `SQL_PASSWORD=free_lifecycle_fixture`, `SQL_HOST=127.0.0.1`, and `SQL_PORT=61009` were set. SQLite runs used separate files under `/private/tmp`.

| Command | Observed result |
|---|---|
| `PYTHON -m pytest tests/test_free_license_lifecycle.py -q` before implementation | 6 failures on missing activation returning 404, 4 compatibility controls passed. |
| `PYTHON -m pytest tests/test_free_license_lifecycle.py tests/test_bound_activation.py -q` on the first implementation | 25 passed, 4 test fixture constraint failures. Fixtures needed an issue timestamp and an at-expiry token issued before expiry. |
| `PYTHON -m pytest tests/test_free_license_lifecycle.py tests/test_device_token_remint.py tests/test_one_valid_key_per_org.py tests/test_activation_licence_transition.py tests/test_native_account_surface.py tests/test_license_refresh_slice.py -q --tb=short` (SQLite) | 239 passed in 61.32s. |
| `PYTHON -m pytest tests/test_free_license_lifecycle.py tests/test_free_license_concurrency_postgres.py tests/test_bound_activation_postgres.py -q --tb=short` (PG17) | 29 passed in 19.23s, zero skips. This includes duplicate first activation, duplicate refresh, forced suspension contention for refresh and recovery, overlap denial audit persistence, and migration preservation of an existing staff licence. |
| `PYTHON -m pytest tests/test_free_license_lifecycle.py -k reassigned -q --tb=short` | Reassignment red returned 365-day dates on PRO. With the assignment recheck, 1 passed and 18 were deselected. |
| `PYTHON manage.py makemigrations --check --dry-run` and `PYTHON manage.py check` (PG17) | No changes detected and no system-check issues. |

## Actual native wire verification

From `implementation/desktop/crates/selahcue-operator`, the source and pinned lockfile at the baseline built in 11.34s with two jobs:

```sh
TAURI_CONFIG='{"bundle":{"externalBin":[],"macOS":{"frameworks":[]}}}' \
CARGO_TARGET_DIR=/private/tmp/selahcue-native-account-task1-target \
cargo test --locked -j 2 --bin selahcue-operator --no-run
```

The standalone workspace was required. The default Tauri build attempted sidecar packaging unavailable in this checkout. The test-only overlay omits that packaging and the unused bundled NDI framework. No production native source or build configuration changed.

The exact executable `/private/tmp/selahcue-native-account-task1-target/debug/deps/selahcue_operator-503c6f12ec32e14c` supplied `SELAHCUE_G1_OPERATOR_TEST_BIN`. `PYTHON -m pytest tests/test_native_account_controller_integration.py -q --tb=short` passed 8 cases in 19.90s against Django's loopback server on PG17. This includes the existing signed-entitlement and presentation continuity cases and a managed Free version of the Rust lost-initial flow. In the new case the Rust controller signed into an empty self-service org, lost the initial response, and then recovered the recorded public device identity after original-token deletion and licence expiry. Django preserved the expiry and wrote no renewal at replay. Explicit ADMIN recovery renewed that exact licence and minted once for the same device.

Full API CI and platform packaging remain separate gates. The weekly ledger and provider adapter do not yet exist in this task's dependency graph. ClickUp quota prevented recording the audit there during this implementation.

## Final owned verification and commit

Commit `7a3fc7dd993035f7ad4cc3a833325501ed6dc08c` contains only the 12 owned API source, migration, and tests. `git diff --check` and `git diff --cached --check` passed before commit.

The final PG17 run included the reassignment protection and all eight actual Rust cases. It passed **304 tests in 118.29s with zero skips**. The exact command under the synthetic PG and Rust fixture environment above was:

```sh
PYTHON -m pytest \
  tests/test_free_license_lifecycle.py \
  tests/test_free_license_concurrency_postgres.py \
  tests/test_bound_activation.py \
  tests/test_bound_activation_postgres.py \
  tests/test_device_token_remint.py \
  tests/test_one_valid_key_per_org.py \
  tests/test_activation_licence_transition.py \
  tests/test_native_account_surface.py \
  tests/test_license_refresh_slice.py \
  tests/test_concurrency_postgres.py \
  tests/test_native_account_controller_integration.py \
  -q --tb=short
```

Existing manifest and licence status-reporting semantics remain in place. Managed org suspension stops Free activation and extension in the lifecycle, while the existing general manifest predicate retains its licence-status/window contract. No PR, push, deployment or other service mutation was performed.

## Independent-review correction 1

Commit `d59d1c4db92429600a3f15eade0b30df77b975f4` makes completed bound replay with a live original token read-only. The exact receipt and token binding and the current managed-account ADMIN and commercial licence eligibility checks still apply. The existing dead-result proof lane remains read-only. Fresh recovery and live authenticated refresh retain their renewal rules.

The regression tests exercise an EXPIRING licence at exactly 30 days, both with and without a future licence that starts precisely at its existing expiry. Replay must return the original device and reference with unchanged licence dates/status, token row, receipt row and renewal audit count. The token catch-up test now renews via a fresh ADMIN recovery nonce.

From `implementation/api`, using the interpreter and clean environment described above:

```sh
PYTHON -m pytest tests/test_free_license_lifecycle.py \
  -k 'completed_live_replay or catch_up_after_admin' -q --tb=short
```

On the old code, the direct replay extended expiry to 365 days and the competing-window replay returned 403. Output was `2 failed, 1 passed, 17 deselected in 1.85s`. On the fix, output was `3 passed, 17 deselected in 2.05s`.

```sh
PYTHON -m pytest tests/test_free_license_lifecycle.py \
  tests/test_free_license_concurrency_postgres.py \
  tests/test_bound_activation.py tests/test_bound_activation_postgres.py \
  tests/test_native_account_controller_integration.py -q --tb=short
```

The focused repeat used `SQL_ENGINE=django.db.backends.postgresql`, `SQL_DATABASE=free_replay_test`, `SQL_USER=free_replay_test`, `SQL_PASSWORD=free_replay_fixture`, `SQL_HOST=127.0.0.1`, and `SQL_PORT=54898` against a fresh disposable PG17 container. It reused the exact native test binary above because the fix changes only the Django application and tests. Output was `58 passed in 41.39s`, zero skips, including all eight live Rust/Django fixtures. Working and staged diff whitespace checks passed. The broader 304-test run remains prior-head evidence.
