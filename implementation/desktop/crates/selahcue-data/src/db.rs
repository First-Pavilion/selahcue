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
    /// Open (creating if needed) a file-backed database, applying production
    /// pragmas and any pending migrations.
    ///
    /// At-rest encryption (FR-154) is the `bundled-sqlcipher` feature swap plus a
    /// `PRAGMA key` here; the schema and repositories are unchanged by it.
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        let conn = Connection::open(path)?;
        Self::init(conn)
    }

    /// Open a private in-memory database (used for tests and ephemeral work).
    pub fn open_in_memory() -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        Self::init(conn)
    }

    fn init(conn: Connection) -> Result<Self> {
        // WAL: readers never block the writer; a crash loses only uncommitted WAL.
        // synchronous=NORMAL is the recommended durable-but-fast setting under WAL.
        // foreign_keys=ON makes ON DELETE CASCADE (plan → items) actually fire.
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             PRAGMA foreign_keys = ON;
             PRAGMA busy_timeout = 5000;",
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
        Ok(self.conn.query_row("PRAGMA user_version", [], |r| r.get(0))?)
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

    /// Crash-safe backup via SQLite's online backup API (not a raw file copy), so
    /// it is consistent even while the source is in use (FR-079).
    pub fn backup_to(&self, dst: impl AsRef<Path>) -> Result<()> {
        self.conn
            .backup(DatabaseName::Main, dst, None)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn opens_migrated_and_integrity_ok() {
        let db = Database::open_in_memory().unwrap();
        assert_eq!(db.schema_version().unwrap(), migrations::target_version());
        db.integrity_check().unwrap();
    }

    #[test]
    fn reopen_is_idempotent() {
        let file = tempfile::NamedTempFile::new().unwrap();
        let path = file.path().to_path_buf();
        {
            let db = Database::open(&path).unwrap();
            assert_eq!(db.schema_version().unwrap(), migrations::target_version());
        }
        // Reopening an already-migrated database must not re-run migrations.
        let db2 = Database::open(&path).unwrap();
        assert_eq!(db2.schema_version().unwrap(), migrations::target_version());
        db2.integrity_check().unwrap();
    }

    #[test]
    fn refuses_database_from_a_newer_build() {
        let file = tempfile::NamedTempFile::new().unwrap();
        let path = file.path().to_path_buf();
        Database::open(&path).unwrap();
        // Simulate a database written by a future build with a higher schema.
        let future = migrations::target_version() + 5;
        let conn = rusqlite::Connection::open(&path).unwrap();
        conn.execute_batch(&format!("PRAGMA user_version = {future};"))
            .unwrap();
        drop(conn);
        // Opening it must refuse rather than silently write with the old schema.
        assert!(matches!(
            Database::open(&path),
            Err(DataError::SchemaTooNew { .. })
        ));
    }
}
