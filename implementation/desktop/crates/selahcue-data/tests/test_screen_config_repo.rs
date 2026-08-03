//! Per-screen output-config persistence (schema v14 + v15 NDI; Screens page Design 2.0).

#![allow(clippy::unwrap_used)]

use selahcue_data::screen_config_repo::{self, ScreenConfigRow};
use selahcue_data::Database;

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

/// A representative non-default row (every field distinct from the identity default), including
/// an NDI output.
fn sample(screen: &str) -> ScreenConfigRow {
    ScreenConfigRow {
        screen: screen.to_string(),
        orientation: 1,
        scale_fit: "fit".to_string(),
        mirror: true,
        delay_ms: 40,
        frame_rate: 30,
        layer_background: true,
        layer_text: true,
        layer_lower_third: false,
        layer_logo: true,
        layer_timer: false,
        safe_area: true,
        ndi_enabled: true,
        ndi_name: format!("SelahCue {screen}"),
    }
}

#[test]
fn config_round_trips_ordered_by_screen() {
    let db = db();
    assert!(screen_config_repo::load_all(&db).unwrap().is_empty());

    screen_config_repo::save_all(&db, &[sample("stream"), sample("main")]).unwrap();
    let rows = screen_config_repo::load_all(&db).unwrap();
    // Ordered by screen id; every column preserved byte-for-byte (incl. the NDI fields).
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[0].screen, "main");
    assert_eq!(rows[1].screen, "stream");
    assert_eq!(rows[0], sample("main"));
    assert!(rows[0].ndi_enabled && rows[0].ndi_name == "SelahCue main");
}

#[test]
fn save_all_replaces_the_whole_set_so_a_reset_screen_is_dropped() {
    let db = db();
    screen_config_repo::save_all(&db, &[sample("main"), sample("stream")]).unwrap();
    assert_eq!(screen_config_repo::load_all(&db).unwrap().len(), 2);

    // Mirroring the in-memory map after `stream` returned to default (dropped in memory):
    // the whole-set replace removes it on disk too.
    screen_config_repo::save_all(&db, &[sample("main")]).unwrap();
    let rows = screen_config_repo::load_all(&db).unwrap();
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].screen, "main");

    // An empty set clears the table entirely.
    screen_config_repo::save_all(&db, &[]).unwrap();
    assert!(screen_config_repo::load_all(&db).unwrap().is_empty());
}

#[test]
fn reconfiguring_a_screen_keeps_a_single_row() {
    let db = db();
    screen_config_repo::save_all(&db, &[sample("main")]).unwrap();
    let mut changed = sample("main");
    changed.orientation = 2; // 180
    changed.scale_fit = "stretch".to_string();
    changed.ndi_enabled = false;
    changed.ndi_name = String::new();
    screen_config_repo::save_all(&db, &[changed.clone()]).unwrap();
    let rows = screen_config_repo::load_all(&db).unwrap();
    assert_eq!(rows, vec![changed]);
}
