//! The persisted Providers & Privacy settings + consent store (Settings → Providers
//! & Privacy, node 338:124; FR-131/132/137).
//!
//! A flat key-value table (`providers_setting`), one row per setting, written as a
//! whole set in one transaction — the same shape as `saved_theme_repo`. The data
//! layer stays a dumb `(key, value)` store; the pure [`selahcue_core::providers`]
//! module owns the mapping to/from [`ProvidersConfig`], so the safe defaults
//! (offline-first, cloud OFF) live in exactly one place and a missing/partial row
//! set reads back as those defaults.

use crate::{Database, Result};
use rusqlite::params;
use selahcue_core::providers::ProvidersConfig;

/// Persist the whole Providers & Privacy config, replacing the stored set in one
/// transaction (so a removed key on disk matches the in-memory value and a crash
/// mid-write never leaves a half-updated config).
pub fn save(db: &Database, config: &ProvidersConfig) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute("DELETE FROM providers_setting", [])?;
    for (key, value) in config.to_kv() {
        tx.execute(
            "INSERT INTO providers_setting (key, value) VALUES (?1, ?2)",
            params![key, value],
        )?;
    }
    tx.commit()?;
    Ok(())
}

/// Load the Providers & Privacy config. An empty/partial store yields the core's
/// safe defaults (offline-first, cloud OFF) — never an error and never a panic.
pub fn load(db: &Database) -> Result<ProvidersConfig> {
    let conn = db.conn();
    let mut stmt = conn.prepare("SELECT key, value FROM providers_setting")?;
    let rows = stmt.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))?;
    let pairs = rows.collect::<std::result::Result<Vec<(String, String)>, _>>()?;
    Ok(ProvidersConfig::from_kv(pairs))
}
