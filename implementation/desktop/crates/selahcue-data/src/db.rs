//! Database open/configure, integrity, checkpoint, and crash-safe backup
//! (FR-079; ADR-0007).

use crate::{migrations, DataError, Result};
use rusqlite::{Connection, DatabaseName};
use std::path::Path;

/// An open SelahCue database with its schema migrated to the current version.
pub struct Database {
    conn: Connection,
}

impl Database {
    /// Open (creating if needed) an **unencrypted** file-backed database, applying
    /// production pragmas and any pending migrations.
    ///
    /// For at-rest encryption (FR-154) use [`open_encrypted`](Self::open_encrypted),
    /// available with the `encryption` feature.
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        let conn = Connection::open(path)?;
        Self::init(conn)
    }

    /// Open a private in-memory database (used for tests and ephemeral work).
    pub fn open_in_memory() -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        Self::init(conn)
    }

    /// Open (creating if needed) an **encrypted** file-backed database, keyed with
    /// `key` before any other access, then applying production pragmas and
    /// migrations (FR-154; ADR-0007).
    ///
    /// Only compiled with the `encryption` feature. This is deliberate: on a build
    /// without SQLCipher, `PRAGMA key` is silently ignored by plain SQLite, which
    /// would produce an *unencrypted* database while appearing keyed — a dangerous
    /// footgun. Gating the API makes an unencrypted "encrypted open" impossible.
    ///
    /// A wrong key surfaces as an error when the first page is read during
    /// migration (SQLCipher cannot decrypt the header).
    #[cfg(feature = "encryption")]
    pub fn open_encrypted(path: impl AsRef<Path>, key: &crate::EncryptionKey) -> Result<Self> {
        let conn = Connection::open(path)?;
        key.apply(&conn)?;
        Self::init(conn)
    }

    /// Encrypted in-memory database, for tests and ephemeral work.
    #[cfg(feature = "encryption")]
    pub fn open_in_memory_encrypted(key: &crate::EncryptionKey) -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        key.apply(&conn)?;
        Self::init(conn)
    }

    fn init(conn: Connection) -> Result<Self> {
        // WAL: readers never block the writer; a crash loses only uncommitted WAL.
        // synchronous=NORMAL is the recommended durable-but-fast setting under WAL.
        // foreign_keys=ON makes ON DELETE CASCADE (plan → items) actually fire.
        // secure_delete=ON (FR-153; PR #30 review, Sana F1): bundled SQLite defaults
        // this OFF, which leaves a deleted row's bytes sitting in freed pages (and in
        // the WAL until checkpointed) until some later write happens to reuse that
        // page — "deleted" transcript/detection text can otherwise still be recovered
        // from the raw file after `transcript_repo::delete`. A keyed SQLCipher open
        // enables this implicitly, but `make launch`/`make output` and the installer
        // all build the plaintext path today, so this must be set here, unconditionally,
        // for every open — not left to depend on the `encryption` feature being on.
        // Verified: `test_transcript_repo.rs`'s
        // `deleting_a_transcript_removes_its_text_from_the_plain_store_file_and_wal`
        // fails without this line and passes with it.
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             PRAGMA foreign_keys = ON;
             PRAGMA busy_timeout = 5000;
             PRAGMA secure_delete = ON;",
        )?;
        migrations::run(&conn)?;
        Ok(Database { conn })
    }

    /// Borrow the underlying connection (used by repositories).
    pub fn conn(&self) -> &Connection {
        &self.conn
    }

    /// The applied schema version (`PRAGMA user_version`).
    pub fn schema_version(&self) -> Result<i64> {
        Ok(self
            .conn
            .query_row("PRAGMA user_version", [], |r| r.get(0))?)
    }

    /// Run `PRAGMA integrity_check`; `Ok(())` iff the store reports `ok`.
    pub fn integrity_check(&self) -> Result<()> {
        let result: String = self
            .conn
            .query_row("PRAGMA integrity_check", [], |r| r.get(0))?;
        if result == "ok" {
            Ok(())
        } else {
            Err(DataError::IntegrityFailed(result))
        }
    }

    /// Checkpoint and truncate the WAL — call before a raw file copy so the copy
    /// is self-contained (a naive copy of a live WAL database can corrupt).
    pub fn checkpoint_truncate(&self) -> Result<()> {
        self.conn
            .execute_batch("PRAGMA wal_checkpoint(TRUNCATE);")?;
        Ok(())
    }

    /// Crash-safe backup of an **unencrypted** database via SQLite's online backup
    /// API (not a raw file copy), so it is consistent even while the source is in
    /// use (FR-079).
    ///
    /// This routes through `Connection::backup`, which opens the destination
    /// *unkeyed* — so it does **not** work for an encrypted database (SQLCipher
    /// rejects an unkeyed backup destination). For an encrypted source use
    /// [`backup_to_encrypted`](Self::backup_to_encrypted).
    pub fn backup_to(&self, dst: impl AsRef<Path>) -> Result<()> {
        self.conn.backup(DatabaseName::Main, dst, None)?;
        Ok(())
    }

    /// Crash-safe backup of an **encrypted** database (FR-079 + FR-154).
    ///
    /// `Connection::backup` opens the destination unkeyed, which SQLCipher refuses;
    /// so this keys the destination with `key` *before* running the online backup,
    /// producing a backup encrypted with the same key (never plaintext on disk).
    /// The key must be supplied here because [`Database`] deliberately does not
    /// retain it (minimising the key's lifetime in memory).
    #[cfg(feature = "encryption")]
    pub fn backup_to_encrypted(
        &self,
        dst: impl AsRef<Path>,
        key: &crate::EncryptionKey,
    ) -> Result<()> {
        let mut dst_conn = Connection::open(dst)?;
        key.apply(&dst_conn)?;
        let backup = rusqlite::backup::Backup::new(&self.conn, &mut dst_conn)?;
        backup.run_to_completion(64, std::time::Duration::from_millis(0), None)?;
        Ok(())
    }
}
