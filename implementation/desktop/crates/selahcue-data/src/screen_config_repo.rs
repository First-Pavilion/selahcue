//! The persisted per-SCREEN OUTPUT CONFIG (Screens page Design 2.0 inspector): each
//! configured screen's orientation, scaling/fit, mirror, output delay, frame-rate target,
//! safe-area guides, per-layer visibility, and NDI output delivery. One row per configured
//! screen; writes replace the whole set transactionally (mirrors the controller's in-memory
//! `output_configs` map, so clearing a screen's config in memory clears it on disk).
//!
//! The repo stores PRIMITIVE columns only — it does not interpret them (the desktop host maps
//! between these rows and `selahcue_lan::protocol::OutputConfigView`), so this crate stays
//! independent of the wire protocol. A forward-compatible `scale_fit` tag round-trips
//! untouched; the controller drops any row for an unknown screen or an all-default config on
//! load (`LiveController::load_output_configs`).

use crate::{Database, Result};
use rusqlite::params;

/// One persisted output-config row (primitive columns only — the desktop host maps to/from
/// `OutputConfigView`). A named struct rather than a tuple because the column count exceeds
/// Rust's 12-arity trait impls for tuples (and it reads far better at the mapping sites).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScreenConfigRow {
    pub screen: String,
    pub orientation: u8,
    /// `scale_fit` tag (`"fill"`/`"fit"`/`"stretch"`).
    pub scale_fit: String,
    pub mirror: bool,
    pub delay_ms: u32,
    pub frame_rate: u16,
    pub layer_background: bool,
    pub layer_text: bool,
    pub layer_lower_third: bool,
    pub layer_logo: bool,
    pub layer_timer: bool,
    pub safe_area: bool,
    pub ndi_enabled: bool,
    pub ndi_name: String,
}

/// Replace the persisted per-screen output-config set with `configs` in one transaction: the
/// on-disk set becomes exactly the supplied set, so a screen whose config returned to default
/// (and was dropped in memory) is honoured, and a crash mid-write never leaves a partial set.
pub fn save_all(db: &Database, configs: &[ScreenConfigRow]) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute("DELETE FROM screen_output_config", [])?;
    for c in configs {
        tx.execute(
            "INSERT INTO screen_output_config \
             (screen, orientation, scale_fit, mirror, delay_ms, frame_rate, \
              layer_background, layer_text, layer_lower_third, layer_logo, layer_timer, safe_area, \
              ndi_enabled, ndi_name) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14)",
            params![
                c.screen,
                c.orientation,
                c.scale_fit,
                c.mirror,
                c.delay_ms,
                c.frame_rate,
                c.layer_background,
                c.layer_text,
                c.layer_lower_third,
                c.layer_logo,
                c.layer_timer,
                c.safe_area,
                c.ndi_enabled,
                c.ndi_name
            ],
        )?;
    }
    tx.commit()?;
    Ok(())
}

/// The whole per-screen output-config set as rows, ordered by screen id.
pub fn load_all(db: &Database) -> Result<Vec<ScreenConfigRow>> {
    let conn = db.conn();
    let mut stmt = conn.prepare(
        "SELECT screen, orientation, scale_fit, mirror, delay_ms, frame_rate, \
                layer_background, layer_text, layer_lower_third, layer_logo, layer_timer, safe_area, \
                ndi_enabled, ndi_name \
         FROM screen_output_config ORDER BY screen",
    )?;
    let rows = stmt.query_map([], |r| {
        Ok(ScreenConfigRow {
            screen: r.get(0)?,
            orientation: r.get(1)?,
            scale_fit: r.get(2)?,
            mirror: r.get(3)?,
            delay_ms: r.get(4)?,
            frame_rate: r.get(5)?,
            layer_background: r.get(6)?,
            layer_text: r.get(7)?,
            layer_lower_third: r.get(8)?,
            layer_logo: r.get(9)?,
            layer_timer: r.get(10)?,
            safe_area: r.get(11)?,
            ndi_enabled: r.get(12)?,
            ndi_name: r.get(13)?,
        })
    })?;
    rows.collect::<std::result::Result<Vec<_>, _>>()
        .map_err(Into::into)
}
