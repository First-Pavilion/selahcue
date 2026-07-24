//! Persisted output → physical-display assignments (FR-040/FR-151; story
//! 86ajpew0c). One row per output role; the display key is the shell's stable
//! monitor identity (`name|WxH`).

use crate::{Database, Result};
use rusqlite::params;

/// Upsert the display assignment for an output role (`"main"`/`"stage"`).
pub fn save_assignment(db: &Database, role: &str, display_key: &str) -> Result<()> {
    db.conn().execute(
        "INSERT INTO output_config (role, display_key) VALUES (?1, ?2)
         ON CONFLICT(role) DO UPDATE SET display_key = ?2",
        params![role, display_key],
    )?;
    Ok(())
}

/// All persisted assignments as `(role, display_key)` pairs.
pub fn load_assignments(db: &Database) -> Result<Vec<(String, String)>> {
    let conn = db.conn();
    let mut stmt = conn.prepare("SELECT role, display_key FROM output_config ORDER BY role")?;
    let rows = stmt.query_map([], |r| Ok((r.get(0)?, r.get(1)?)))?;
    rows.collect::<std::result::Result<Vec<_>, _>>()
        .map_err(Into::into)
}
