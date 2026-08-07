//! The persisted media library (schema v17; Design 2.0 node 329:124) — the imported
//! media-asset registry mapped to structured `media_asset` columns (mirrors `plan_repo`'s
//! column mapping of a pure [`selahcue_core`] type, rather than an opaque JSON blob, so storage
//! accounting and missing/unused queries stay first-class). Writes replace the whole set
//! transactionally, so a removal in memory becomes a removal on disk.

use crate::{Database, Result};
use rusqlite::params;
use selahcue_core::media::{MediaAsset, MediaId, MediaKind};

/// Replace the persisted media library with `assets` in one transaction: the on-disk set becomes
/// exactly the supplied set (removals honoured; a crash mid-write never leaves a partial set).
pub fn save_all(db: &Database, assets: &[MediaAsset]) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute("DELETE FROM media_asset", [])?;
    for a in assets {
        tx.execute(
            "INSERT INTO media_asset \
             (id, path, kind, size_bytes, width, height, duration_ms, imported_at) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![
                a.id.0 as i64,
                a.path,
                a.kind.as_tag(),
                a.size_bytes as i64,
                a.width.map(|v| v as i64),
                a.height.map(|v| v as i64),
                a.duration_ms.map(|v| v as i64),
                a.imported_at as i64,
            ],
        )?;
    }
    tx.commit()?;
    Ok(())
}

/// The whole media library as [`MediaAsset`]s, ordered by id (deterministic). A row whose `kind`
/// column is not a recognised [`MediaKind`] tag is DROPPED (never guessed) — an old build that
/// wrote an unknown kind cannot crash a newer load.
pub fn load_all(db: &Database) -> Result<Vec<MediaAsset>> {
    let conn = db.conn();
    let mut stmt = conn.prepare(
        "SELECT id, path, kind, size_bytes, width, height, duration_ms, imported_at \
         FROM media_asset ORDER BY id",
    )?;
    let rows = stmt.query_map([], |r| {
        let id: i64 = r.get(0)?;
        let path: String = r.get(1)?;
        let kind_tag: String = r.get(2)?;
        let size_bytes: i64 = r.get(3)?;
        let width: Option<i64> = r.get(4)?;
        let height: Option<i64> = r.get(5)?;
        let duration_ms: Option<i64> = r.get(6)?;
        let imported_at: i64 = r.get(7)?;
        Ok(MediaKind::from_tag(&kind_tag).map(|kind| MediaAsset {
            id: MediaId(id as u64),
            path,
            kind,
            size_bytes: size_bytes as u64,
            width: width.map(|v| v as u32),
            height: height.map(|v| v as u32),
            duration_ms: duration_ms.map(|v| v as u32),
            imported_at: imported_at as u64,
        }))
    })?;
    // Drop rows with an unrecognised kind (the `None` entries) rather than failing the load.
    Ok(rows
        .collect::<std::result::Result<Vec<Option<MediaAsset>>, _>>()?
        .into_iter()
        .flatten()
        .collect())
}
