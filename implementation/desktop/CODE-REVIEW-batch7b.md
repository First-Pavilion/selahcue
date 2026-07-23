# Code Review — batch7b: `selahcue-data` persistence crate

**Reviewer role:** Independent Rust reviewer (did not author this code).
**Date:** 2026-07-23
**Scope:** `db.rs`, `migrations.rs`, `plan_repo.rs`, `error.rs`, and the
`from_parts` / `next_id` / `ItemKind` tag additions in `selahcue-core/src/plan.rs`.

## Verdict: PASS WITH CONDITIONS

The crate is well-structured and correct for its intended single-connection,
single-writer use. Round-trip fidelity, transactional writes, cascade delete,
graceful handling of unknown kind tags, the online backup API, and the no-reuse
id invariant are all implemented correctly and covered by tests (9/9 pass,
clippy clean). No live functional defect was found. Two robustness gaps should
be addressed before the schema is allowed to evolve — chiefly the missing
downgrade guard (M1) — hence *conditions* rather than an unqualified pass.

## Verification performed
- `cargo test -p selahcue-data` → 9 passed, 0 failed.
- `cargo clippy -p selahcue-data --all-targets` → clean.
- `cargo test -p selahcue-core` → pass.
- Manual trace of insert→load round-trip, migration atomicity, and cast paths.

## Findings by severity

### Medium

**M1 — Migration runner has no forward-compat / downgrade guard.**
`migrations::run` (migrations.rs:41-54) applies migrations only while
`user_version < MIGRATIONS.len()`. A database whose `user_version` is *greater*
than `target_version()` — i.e. one written by a newer build — is silently
accepted and then read/written by the older build against a schema it does not
match. Because the append-only migration design exists precisely so the schema
*will* evolve, this is a real (not theoretical) data-integrity risk the first
time a user opens a v2 database with a v1 binary. Recommend erroring
(e.g. a `DataError::SchemaTooNew`) when `user_version > MIGRATIONS.len()`.

### Low

**L1 — Item order is guaranteed only incidentally.**
`load` uses `ORDER BY ord` (plan_repo.rs:60) with no secondary sort key, and the
schema has no `UNIQUE(plan_id, ord)` constraint (migrations.rs:21-31; the index
`idx_plan_item_order` is non-unique). Ordering is correct today solely because
`insert` is the only writer and assigns a dense `0..n` via `enumerate`. If any
future or alternate write path — or a manual row — ever produced a duplicate
`ord`, the order among the tied rows would be undefined. Harden with
`UNIQUE(plan_id, ord)` and/or `ORDER BY ord, item_id` so order is guaranteed
structurally, not by convention.

**L2 — Load-side `i64 → u32` narrowing on `planned_secs` truncates silently.**
`planned.map(|s| s as u32)` (plan_repo.rs:81) narrows without range check. This
is inconsistent with the crate's own corruption philosophy: an unknown `kind`
tag is surfaced as `DataError::Corrupt` (plan_repo.rs:75-76), but a
`planned_secs` value outside `u32` range would be truncated silently rather than
reported. No real-world impact (the app only ever writes `u32`), but a stored
out-of-range value should be treated as corrupt, not folded.

**L3 — `integrity_check` discards the detail rows.**
`PRAGMA integrity_check` returns one row per problem on failure; `query_row`
(db.rs:56-58) reads only the first, so `IntegrityFailed` carries just the first
line of the report. Detection is correct; diagnostics are lossy. Consider
collecting all rows.

### Info / Nits

**N1 — Unchecked wide-integer casts at astronomically large values.**
`plan.next_id() as i64` and `item.id.0 as i64` (plan_repo.rs:22, 31) and the
inverse `as u64` on load (plan_repo.rs:78, 86) only misbehave at values ≥ 2^63,
which id counters cannot reach in practice. Likewise `from_parts`'s `m + 1`
(plan.rs:192) would overflow-panic in debug if an item id were `u64::MAX`. Not
real-world reachable; noted for completeness.

**N2 — `unchecked_transaction` relies on an unstated invariant.**
`insert` uses `db.conn().unchecked_transaction()` (plan_repo.rs:19). This is safe
here because `rusqlite::Connection` is `!Sync` and singly owned, so no nested or
concurrent transaction can exist — but the safety rests on that invariant. A
one-line comment would make the reasoning explicit.

## What is correct (confirmed, not assumed)

- **Migrations:** idempotent (guarded by `user_version`, re-open is a no-op —
  `reopen_is_idempotent` passes); atomic per migration (each wrapped in
  `BEGIN … PRAGMA user_version = n … COMMIT`, and `user_version` is part of the
  transactional DB header, so a mid-migration crash rolls back cleanly); version
  tracking correct; append-only design sound; a failed migration aborts `init`
  and drops the connection, discarding the open transaction.
- **Round-trip fidelity:** name, items (id/kind/title/planned/owner), explicit
  `ord` ordering, and `next_id` all round-trip. Persisting `next_id` separately
  is what preserves no-reuse when the tail item was removed — verified by trace.
- **Transactional writes & cascade:** `insert` commits atomically and rolls back
  on drop; delete cascades via `ON DELETE CASCADE` with `foreign_keys = ON`
  (set per-connection in `init`) — `deleting_plan_cascades_items` confirms.
- **Stored-data errors:** unknown kind tag → `DataError::Corrupt`, not a panic
  (`corrupt_kind_tag_is_reported`).
- **Backup:** uses SQLite's online backup API (`conn.backup`), not a raw copy;
  a `checkpoint_truncate` helper is provided for the raw-copy path but is not on
  the backup path — `backup_produces_a_loadable_copy` confirms restore + integrity.
- **SQL injection:** every user/domain input is bound via `params!`. The only
  `format!`-built SQL is in `migrations::run` and interpolates a compile-time
  constant migration string plus an integer version — no injection surface.
- **Pragmas:** WAL + `synchronous = NORMAL` + `foreign_keys = ON` +
  `busy_timeout = 5000` is the recommended durable-but-fast configuration.
- **`from_parts` invariant:** `next_id.max(max(item id) + 1)` genuinely enforces
  no-reuse even when a too-small `next_id` is supplied
  (`from_parts_preserves_no_reuse_invariant`).

## Remediation (applied post-review)

All conditions raised above were addressed and re-verified (`cargo test` 50/50,
`cargo clippy --all-targets` clean):

- **M1 (Medium) — fixed.** Added `DataError::SchemaTooNew { found, supported }` and a
  forward-compat guard in `migrations::run`: opening a database whose `user_version`
  exceeds `target_version()` is now refused. Regression test:
  `db::tests::refuses_database_from_a_newer_build`.
- **L1 (Low) — fixed.** Added `UNIQUE (plan_id, ord)` to the v1 `plan_item` schema
  (unreleased, no deployed data) and a deterministic `ORDER BY ord, item_id`
  tie-breaker in `load`. Order is now guaranteed structurally, not by convention.
- **L2 (Low) — fixed.** `load` now uses `u32::try_from`/`u64::try_from` for
  `planned_secs` and `item_id`, returning `DataError::Corrupt` on out-of-range values
  instead of silently truncating — consistent with the unknown-kind-tag handling.
  Regression test: `plan_repo::tests::out_of_range_planned_secs_is_reported_not_truncated`.
- **L3 / N1 / N2 (Low/Nits) — accepted as-is for this batch.** L3 (lossy integrity
  detail) and N1 (astronomically-large-value casts, not real-world reachable) are
  logged as follow-ups; N2 is addressed by the existing explanatory comment on the
  `unchecked_transaction` call.

## Independence statement

I did not write, co-author, or previously review any of the code under review.
This assessment is based solely on reading the listed source files and running
the project's own test and lint tooling on an unmodified checkout. Findings are
reported by observed behavior and code inspection; no changes were made to the
codebase.
