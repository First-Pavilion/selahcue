# Pre-upgrade encrypted compatibility fixture

`sqlcipher-4.14.0-backup.db3` is synthetic TEST data, generated on 2026-11-11
before the dependency upgrade at base commit
`7f6dbcbb4782854cbb0fea14a3bb5a9ffcf7fcd0`. It contains one transcript,
one segment and one saved sermon note with explicitly synthetic text.
No church database, provider call, credential or personal data was used.

- Producer: rusqlite 0.40.2 / libsqlite3-sys 0.38.2.
- Actual runtime: SQLCipher `4.14.0 community`, SQLite `3.51.3`.
- SQLite source ID: `2026-03-13 10:38:09 737ae4a34738ffa0c3ff7f9bb18df914dd1cad163f28fd6b6e114a344fe6alt1`.
- Application schema: 25, created by the unmodified base migrations.
- Public TEST key: `EncryptionKey::from_raw([0x2d; 32])` (not a production secret).
- Size: 172032 bytes; SHA-256:
  `94652f5d2dee53c02ede8e41f029aeb050e31133ac482b836e0696d6223f5c65`.

The fixture is the output of the old application's `backup_to_encrypted`,
not a fresh database produced by the upgraded library. The runtime test
copies it into a temporary directory before opening it; the retained fixture
is never migrated or modified. It exercises keyed read-only and writable
reopen, transcript/note preservation, integrity, wrong-key and keyless rejection,
and a fresh encrypted backup/reopen under the new library.

`create_legacy_fixture.rs` retains the complete generator. To reproduce in a
separate disposable checkout of the base commit, copy that source to
`crates/selahcue-data/tests/create_legacy_fixture.rs`, create its `tests/fixtures`
directory, and run from `implementation/desktop`:

```sh
cargo test --locked -p selahcue-data --features encryption --test create_legacy_fixture -- --nocapture
```

Remove the temporary test after generation. The generator asserts both old
runtime versions so it cannot silently replace the compatibility fixture with
one made by the upgraded library. SQLCipher uses a random salt, so regeneration
preserves the logical test data but intentionally does not reproduce ciphertext
or the file checksum. Keep the existing fixture when checking the new library.
