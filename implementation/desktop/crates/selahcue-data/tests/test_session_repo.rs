//! Live-session snapshot persistence (crash recovery).

#![allow(clippy::unwrap_used)]

use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_data::session_repo::{self, SessionState};
use selahcue_data::{plan_repo, Database};

fn db() -> Database {
    Database::open_in_memory().unwrap()
}

#[test]
fn no_snapshot_loads_none() {
    assert_eq!(session_repo::load(&db()).unwrap(), None);
}

#[test]
fn snapshot_round_trips_all_fields() {
    let db = db();
    // The plan reference is a real FK — snapshotting an unknown plan must fail,
    // so round-trip against an actually persisted plan.
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening");
    let plan_id = plan_repo::insert(&db, &plan).unwrap();
    let s = SessionState {
        plan_id: Some(plan_id),
        live_idx: Some(2),
        staged_idx: Some(4),
        plan_cursor: Some(4),
        blackout: true,
        timer_total_secs: Some(300),
        timer_elapsed_secs: Some(117),
        timer_running: true,
        live_scripture: Some("Romans 8:28".into()),
        live_free_text: Some("Removed Song".into()),
        staged_scripture: Some("John 3:16".into()),
        live_free_body: Some("Way maker\nMiracle worker".into()),
        live_slide: Some(3),
        staged_slide: Some(1),
        cursor_slide: Some(1),
    };
    session_repo::save(&db, &s).unwrap();
    assert_eq!(session_repo::load(&db).unwrap(), Some(s));
}

#[test]
fn within_song_slide_positions_round_trip(/* S8-1 migration v6 */) {
    let db = db();
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Way Maker");
    let plan_id = plan_repo::insert(&db, &plan).unwrap();
    let s = SessionState {
        plan_id: Some(plan_id),
        live_idx: Some(0),
        live_slide: Some(4),
        cursor_slide: Some(4),
        ..Default::default()
    };
    session_repo::save(&db, &s).unwrap();
    let loaded = session_repo::load(&db).unwrap().unwrap();
    assert_eq!(loaded.live_slide, Some(4));
    assert_eq!(loaded.cursor_slide, Some(4));
    assert_eq!(loaded.staged_slide, None);
}

#[test]
fn deleting_the_plan_nulls_the_session_reference() {
    // ON DELETE SET NULL: a deleted plan must not take the snapshot down with it —
    // the session row survives with plan_id = None (the app then starts fresh).
    let db = db();
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening");
    let plan_id = plan_repo::insert(&db, &plan).unwrap();
    session_repo::save(
        &db,
        &SessionState {
            plan_id: Some(plan_id),
            live_idx: Some(0),
            ..Default::default()
        },
    )
    .unwrap();
    plan_repo::delete(&db, plan_id).unwrap();
    let loaded = session_repo::load(&db).unwrap().unwrap();
    assert_eq!(loaded.plan_id, None, "FK SET NULL applied");
    assert_eq!(loaded.live_idx, Some(0), "rest of the snapshot intact");
}

#[test]
fn empty_snapshot_round_trips() {
    let db = db();
    let s = SessionState::default();
    session_repo::save(&db, &s).unwrap();
    assert_eq!(session_repo::load(&db).unwrap(), Some(s));
}

#[test]
fn save_is_an_upsert_singleton() {
    // Autosave overwrites in place — the table never grows (no-leak rule).
    let db = db();
    for i in 0..500u32 {
        session_repo::save(
            &db,
            &SessionState {
                live_idx: Some(i),
                ..Default::default()
            },
        )
        .unwrap();
    }
    let loaded = session_repo::load(&db).unwrap().unwrap();
    assert_eq!(loaded.live_idx, Some(499));
    let rows: i64 = db
        .conn()
        .query_row("SELECT COUNT(*) FROM session_state", [], |r| r.get(0))
        .unwrap();
    assert_eq!(rows, 1, "singleton row, never accumulates");
}

#[test]
fn clear_removes_the_snapshot() {
    let db = db();
    session_repo::save(&db, &SessionState::default()).unwrap();
    session_repo::clear(&db).unwrap();
    assert_eq!(session_repo::load(&db).unwrap(), None);
}

#[test]
fn corrupt_out_of_range_values_surface_not_truncate() {
    let db = db();
    db.conn()
        .execute(
            "INSERT INTO session_state (id, live_idx, blackout) VALUES (1, -7, 0)",
            [],
        )
        .unwrap();
    assert!(
        session_repo::load(&db).is_err(),
        "negative index is corruption"
    );
}
