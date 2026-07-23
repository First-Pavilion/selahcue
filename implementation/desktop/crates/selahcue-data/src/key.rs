//! At-rest encryption key handling for SQLCipher (FR-154).
//!
//! This layer only *applies* an already-derived 256-bit key to a connection. Key
//! acquisition — reading from the OS secret store (macOS Keychain / Windows DPAPI
//! / libsecret) or deriving from a passphrase via Argon2id on Linux — is the
//! application shell's responsibility, per ADR-0007. Keeping derivation out of the
//! data layer means the crate has no opinion on the KDF and never sees a passphrase.

use crate::Result;
use rusqlite::Connection;
use std::fmt::Write as _;
use zeroize::Zeroize;

/// A 256-bit raw encryption key for the at-rest database.
///
/// Applied as SQLCipher's **raw key** (hex), which bypasses SQLCipher's own KDF —
/// the caller supplies fully-derived key material. The bytes are zeroed on drop.
pub struct EncryptionKey([u8; 32]);

impl EncryptionKey {
    /// Construct from 32 bytes of already-derived key material.
    pub fn from_raw(bytes: [u8; 32]) -> Self {
        Self(bytes)
    }

    /// Apply this key to `conn` via `PRAGMA key`. Must be called immediately after
    /// opening, before any other statement, so every page (including the header
    /// and WAL) is encrypted.
    ///
    /// Memory hygiene: the hex string and the key-bearing PRAGMA string this
    /// function allocates are both zeroed after use, and the pragma buffer is
    /// pre-sized to its exact length so no reallocation leaves an un-zeroed copy
    /// behind. Note the residual limitation — rusqlite exposes only the *text*
    /// `PRAGMA key` API (not `sqlite3_key_v2`, which takes raw bytes), so SQLite
    /// keeps its own copy of the key text in tokenizer/VDBE buffers that this
    /// crate cannot reach; that copy persists until SQLite overwrites it. Full
    /// wiping would require an `unsafe` FFI binding, which this crate forbids.
    pub(crate) fn apply(&self, conn: &Connection) -> Result<()> {
        // SQLCipher raw-key form: PRAGMA key = "x'<64 hex chars>'";
        let mut hex = String::with_capacity(64);
        for b in &self.0 {
            // Infallible for a String sink; ignore the formatter Result.
            let _ = write!(hex, "{b:02x}");
        }
        // Pre-size to the exact final length — `PRAGMA key = "x'` (16) + 64 hex +
        // `'";` (3) = 83 — so pushing the key never triggers a realloc that would
        // strand an un-zeroed copy of the key on the heap (unlike `format!`, whose
        // capacity estimate is too small and reallocates through the key bytes).
        let mut pragma = String::with_capacity(16 + 64 + 3);
        pragma.push_str("PRAGMA key = \"x'");
        pragma.push_str(&hex);
        pragma.push_str("'\";");
        let outcome = conn.execute_batch(&pragma);
        // Wipe the copies this function owns, regardless of success.
        pragma.zeroize();
        hex.zeroize();
        outcome?;
        Ok(())
    }
}

impl Drop for EncryptionKey {
    fn drop(&mut self) {
        self.0.zeroize();
    }
}

// Never leak key bytes through Debug.
impl std::fmt::Debug for EncryptionKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("EncryptionKey(<redacted>)")
    }
}
