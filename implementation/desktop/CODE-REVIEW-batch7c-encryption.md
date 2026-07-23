# Code Review — batch 7c: at-rest encryption (FR-154)

**Method:** Independent multi-lens adversarial review (4 lenses × find → adversarially
verify), run as a fresh-context workflow. No self-approval.
**Date:** 2026-07-23
**Scope:** `selahcue-data` `encryption` feature — `key.rs`, `db.rs` (`open_encrypted`,
`open_in_memory_encrypted`, `backup_to_encrypted`), `lib.rs`, `Cargo.toml`, and the
`tests/test_encryption.rs` suite.

## Verdict: PASS (2 confirmed findings remediated + regression-tested)

12 agents ran (4 review lenses + 8 verify). **8 findings raised → 2 confirmed** after
adversarial verification; **6 dismissed** (each empirically refuted). All confirmed
findings are fixed and re-verified: `cargo test --features encryption` **16/16**,
`cargo clippy --all-targets --features encryption` clean.

## Confirmed & fixed

### H1 (High) — `backup_to` fails on every encrypted database
`Database::backup_to` routes through `Connection::backup`, which opens the destination
**unkeyed**; SQLCipher rejects an unkeyed backup destination, so crash-safe backup
(FR-079) failed in the shipping (encrypted) configuration — and the original backup
test used a plain in-memory DB, hiding it.

**Fix:** added `Database::backup_to_encrypted(&self, dst, key)` (feature-gated) that
opens the destination, applies the same key, then runs the online backup via
`rusqlite::backup::Backup`. `backup_to` is now documented as unencrypted-only.
**Regression test:** `encrypted_backup_round_trips_and_stays_encrypted` — backs up a
live encrypted DB, reopens the backup with the same key, asserts data + integrity, and
scans the backup file for the plaintext marker and the `SQLite format 3\0` header magic
(both absent).

### L1 (Low) — raw key lingered in a freed heap buffer after `apply()`
`format!` under-estimated capacity (38 B) for the 83-B pragma and reallocated through a
buffer holding the hex key, so `zeroize` did not cover that freed copy.

**Fix:** the pragma `String` is now pre-sized to its exact length (`16 + 64 + 3`) and
built with `push_str`, so no reallocation occurs and `zeroize` covers the only heap copy
this function owns. The doc comment was corrected to stop overclaiming: it now states
that only the strings this function allocates are wiped, and that SQLite retains an
un-wipeable copy of the key text in its tokenizer/VDBE buffers because rusqlite exposes
only the text `PRAGMA key` API (not `sqlite3_key_v2`), which this `#![forbid(unsafe_code)]`
crate cannot reach.

## Dismissed (verified not-a-defect)

- **WAL/-shm not scanned for plaintext** (×2 lenses): SQLCipher encrypts the WAL —
  verified empirically (a populated ~45 KB `-wal` scanned clean without checkpoint); the
  `-shm` file holds only the WAL index, never record content.
- **SQLite version skew** (dev links 3.46.0, SQLCipher links 3.45.3): true but inherent
  to SQLCipher (a fork that trails upstream); the crate uses only long-stable pragmas/DDL,
  and `--features encryption` recompiles the whole crate against the shipping engine, which
  the suite exercises. Process note, not a code defect.
- **`open_in_memory_encrypted` had no coverage / marker scan could go vacuous / wrong-key
  asserts only `is_err()`**: test-hardening nits, each already covered by sibling
  assertions. Coverage gap addressed anyway with `in_memory_encrypted_round_trips`.

## Design notes (for the record)

- Encryption is behind the `encryption` feature (`rusqlite/bundled-sqlcipher-vendored-openssl`,
  self-contained). The keyed-open API is compiled **only** with the feature, so an
  "encrypted open" on a non-SQLCipher build is impossible — closing the silent-no-encryption
  footgun (plain SQLite ignores `PRAGMA key`).
- The key is a 256-bit **raw** key (KDF bypassed); derivation/storage (OS secret store;
  Argon2id on Linux) is the app shell's responsibility per ADR-0007. `Database` deliberately
  does not retain the key, which is why the backup path takes it as a parameter.

## Independence statement

The review was performed by fresh-context agents that did not author the code, over the
listed files, using the crate's own test and lint tooling. Findings were verified
adversarially (default-to-not-real) before being reported; the two confirmed defects were
then fixed and re-verified.
