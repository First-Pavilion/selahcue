//! Database open/configure, integrity, checkpoint, and crash-safe backup
//! (FR-079; ADR-0007).

use crate::{migrations, DataError, Result};
use rusqlite::{Connection, DatabaseName};
use std::path::Path;
use std::time::Duration;

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

    /// Best-effort WAL checkpoint+truncate, called automatically after
    /// `transcript_repo::delete`/`purge_expired` commit (FR-153; PR #30 review, Sana
    /// F6). `secure_delete = ON` (above) only zeroes freed *page* content inside the
    /// main `.db3` file; in WAL mode a deleted row's bytes can still sit in the `-wal`
    /// sidecar — as stale, already-superseded frames left over from the write that
    /// originally created the row — until something truncates it. A plain checkpoint
    /// (`PASSIVE`, what SQLite's own auto-checkpoint runs) moves the *current* state
    /// into the main file but does not truncate the WAL, so those old frames can
    /// persist indefinitely while the app keeps running. `TRUNCATE` does both.
    ///
    /// **This does not, and structurally cannot, "never block" — an earlier version of
    /// this comment claimed that and it was false** (PR #30 review, Vera F5, measured
    /// against `0b87d91`): a `TRUNCATE` checkpoint consults SQLite's busy handler while
    /// it waits for existing readers to release the WAL, and running it under this
    /// connection's normal `busy_timeout` (5000ms, set in [`init`](Self::init)) made
    /// that wait a real, multi-second stall — felt not just by this call, but by
    /// *every other connection's writes* on the same file, because the checkpoint
    /// holds the WAL write lock while it waits. Worse, a writer whose deferred
    /// transaction had already performed a read (the shape `transcript_repo::
    /// append_segment`'s `SELECT MAX(ord)` + `INSERT` takes) failed immediately with
    /// `SQLITE_BUSY` for the entire window, because SQLite will not invoke the busy
    /// handler on a read-to-write lock upgrade. Measured: up to ~5.2s of stall per
    /// call, compounding across repeated deletes, with write failures on every writer
    /// shape once the reader outlasted the writer's own timeout.
    ///
    /// The fix: scope `busy_timeout` to 0 for just the checkpoint statement (restored
    /// unconditionally on drop, via a small `RestoreBusyTimeout` RAII guard defined
    /// inside this function, so a panic or early return here can never leave the
    /// connection parked at timeout 0). At `busy_timeout = 0`
    /// SQLite's busy handler is disabled entirely, so the checkpoint either completes
    /// immediately or returns at once reporting it could not fully truncate — it can no
    /// longer stall this call or any other connection's write past a few milliseconds
    /// (measured: 5,194ms -> 1.5ms for the caller, 5,179ms -> 0.4ms for a concurrent
    /// writer's stall, and every measured write-failure shape dropped to zero).
    ///
    /// **Still genuinely best-effort — this is a real, documented trade, not a solved
    /// problem:** with a busy_timeout of 0, any reader holding the WAL open — even
    /// briefly — makes the checkpoint skip or only partially truncate, where the old
    /// (blocking) code would sometimes have waited it out. Under a continuously
    /// spinning reader (back-to-back reads with no gap) this fix succeeds measurably
    /// less often than the old blocking behaviour did (about half the attempts, vs.
    /// nearly all of them) — an accepted cost, because the truncate was already
    /// best-effort: a skipped or partial truncate here is retried for free on the next
    /// successful delete, purge, or clean close, and the deleted row is unreachable via
    /// the read API regardless of whether the WAL was truncated this time.
    ///
    /// **Callers must not assume the WAL is truncated after every call** — only that
    /// this call will not meaningfully block them or any other connection on the file.
    /// The PRAGMA's own result row (`busy`, `log` frame count, `checkpointed` frame
    /// count) is surfaced at `eprintln!` granularity (this crate has no logging
    /// framework dependency; matches the precedent elsewhere in this workspace of
    /// `eprintln!` for "observable, not a hard failure" diagnostics, e.g.
    /// `selahcue-desktop`/`selahcue-stt`) whenever the checkpoint is skipped or only
    /// partial, so the degradation is observable without being a hard error (PR #30
    /// review, Sana — the PRAGMA's result row was previously discarded via
    /// `execute_batch`, which cannot even see it). Never logs transcript/detection/
    /// segment *content* — only the PRAGMA's own counts/flags (FR-082).
    pub(crate) fn try_checkpoint_truncate(&self) {
        // Read the connection's current busy_timeout before touching it, so the
        // restore below always puts back whatever `init()` actually configured —
        // no second hardcoded copy of the 5000ms production value to drift out of
        // sync with it. `PRAGMA busy_timeout` with no argument is a pure getter
        // (returns `db->busyTimeout`; does not touch the handler) per SQLite's own
        // pragma.c, so this cannot itself perturb the value being read.
        let previous_ms: i64 = self
            .conn
            .query_row("PRAGMA busy_timeout", [], |r| r.get(0))
            .unwrap_or(5000); // best-effort: if even this fails, fall back to the
                              // documented production default rather than leaving
                              // the restore path without a target.

        // RAII guard: restores the connection's busy_timeout on drop regardless of
        // how this function returns (early return, the happy path, or a panic
        // unwinding through it) — the scope-down below must never leak.
        struct RestoreBusyTimeout<'a> {
            conn: &'a Connection,
            previous_ms: i64,
        }
        impl Drop for RestoreBusyTimeout<'_> {
            fn drop(&mut self) {
                let ms = u64::try_from(self.previous_ms).unwrap_or(5000);
                // Best-effort like the rest of this function: nothing more to do if
                // even this fails.
                let _ = self.conn.busy_timeout(Duration::from_millis(ms));
            }
        }
        let _restore_on_drop = RestoreBusyTimeout {
            conn: &self.conn,
            previous_ms,
        };

        // Disabling the busy handler (timeout 0) is what makes the checkpoint
        // return at once instead of waiting on a concurrent reader — see the doc
        // comment above (Vera F5).
        if self.conn.busy_timeout(Duration::ZERO).is_err() {
            return; // Couldn't even set it — leave the WAL for the next attempt.
        }

        let result: rusqlite::Result<(i64, i64, i64)> =
            self.conn
                .query_row("PRAGMA wal_checkpoint(TRUNCATE)", [], |r| {
                    Ok((r.get(0)?, r.get(1)?, r.get(2)?))
                });
        if let Ok((busy, log_frames, checkpointed_frames)) = result {
            if busy != 0 || checkpointed_frames < log_frames {
                // Skipped or partial — counts/flags only, never row content
                // (FR-082: this crate never formats transcript/detection/segment
                // text into a diagnostic).
                eprintln!(
                    "selahcue-data: wal_checkpoint(TRUNCATE) did not fully truncate the WAL \
                     (busy={busy}, log_frames={log_frames}, checkpointed_frames={checkpointed_frames}) \
                     — will retry on the next delete/purge/clean close"
                );
            }
        }
        // An `Err` here (the PRAGMA itself failing) is likewise silently discarded —
        // best-effort by design, same as before this fix.
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
