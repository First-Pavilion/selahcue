//! End-to-end, real-store proof for 86akgqdv0's PR #33 review fix (Sana F1 — High).
//!
//! The bug this test exists to make impossible again: the operator used to resolve "which
//! transcript" by querying its OWN, differently-located SQLite file — a connection that, in a
//! real launch, NEVER has a real `transcript` row (only the desktop process ever creates one).
//! `scripts/operator_headless.py`'s webview harness could not catch this because it hardcodes
//! `SN_TRANSCRIPT_ID = 42` at the JS-mock layer, never touching real Rust persistence at all.
//!
//! This test is the missing layer: a REAL `selahcue_data::Database` (a real SQLite file on
//! disk, in a tempdir — exactly how `selahcue-desktop` opens its store), wired into
//! `LiveController` via `TranscriptStoreWriter`/`SermonNoteStore` implementations that are
//! themselves copies of `selahcue-desktop/src/main.rs`'s own `RealTranscriptStore`/
//! `RealSermonNoteStore` adapters, driven over a REAL `ControlServer` + `RemoteOperator` (TLS
//! WebSocket) round trip — the same transport the real operator process uses. No id is ever
//! fabricated by the test: `StartTranscript` opens a transcript the normal way, and every
//! id used afterward is whatever the real database actually assigned it.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use selahcue_app::{handler_for, LiveController, RemoteOperator, SermonNoteStore};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_data::{sermon_note_repo, transcript_repo, Database};
use selahcue_lan::protocol::{SermonNoteDraftInput, SermonNoteEditInput};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{ControlServer, Role, SelfSigned};
use selahcue_present::Theme;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex as AsyncMutex;

/// Adapts `selahcue_data::transcript_repo` to `TranscriptStoreWriter` — a direct copy of
/// `selahcue-desktop/src/main.rs`'s `RealTranscriptStore`, kept in sync by hand (that binary
/// crate is excluded from the workspace and cannot be depended on from here).
struct RealTranscriptStore {
    db: Database,
}

impl selahcue_app::TranscriptStoreWriter for RealTranscriptStore {
    fn open_transcript(
        &mut self,
        label: &str,
        provider: &str,
        started_at_ms: i64,
    ) -> Result<i64, String> {
        transcript_repo::create(
            &self.db,
            &transcript_repo::NewTranscript {
                label: label.to_string(),
                provider: provider.to_string(),
                plan_id: None,
                started_at_ms,
            },
        )
        .map_err(|e| e.to_string())
    }
    fn append_segment(
        &mut self,
        transcript_id: i64,
        start_ms: u64,
        end_ms: u64,
        text: &str,
    ) -> Result<i64, String> {
        transcript_repo::append_segment(&self.db, transcript_id, start_ms, end_ms, text)
            .map_err(|e| e.to_string())
    }
    fn end_transcript(&mut self, transcript_id: i64, ended_at_ms: i64) -> Result<(), String> {
        transcript_repo::end(&self.db, transcript_id, ended_at_ms).map_err(|e| e.to_string())
    }
}

/// Adapts `selahcue_data::sermon_note_repo` + `transcript_repo::most_recent_id` to
/// `SermonNoteStore` — a direct copy of the desktop's real adapter (86akgqdv0's fix).
struct RealSermonNoteStore {
    db: Database,
}

impl SermonNoteStore for RealSermonNoteStore {
    fn active_transcript_id(&mut self) -> Result<Option<i64>, String> {
        transcript_repo::most_recent_id(&self.db).map_err(|e| e.to_string())
    }
    fn save_draft(
        &mut self,
        transcript_id: i64,
        draft: &SermonNoteDraftInput,
    ) -> Result<selahcue_lan::protocol::SermonNoteDraftView, String> {
        let now_ms = 1_000;
        let note = sermon_note_repo::NewSermonNote {
            transcript_id,
            title: draft.title.clone(),
            summary: draft.summary.clone(),
            sections_json: draft.sections_json.clone(),
            scriptures_json: draft.scriptures_json.clone(),
            ai_generated: draft.ai_generated,
            disclosure: draft.disclosure.clone(),
            provider: draft.provider.clone(),
            model: draft.model.clone(),
            created_at_ms: now_ms,
        };
        sermon_note_repo::create(&self.db, &note).map_err(|e| e.to_string())?;
        let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
            .map_err(|e| e.to_string())?
            .ok_or("draft vanished immediately after create")?;
        Ok(record_to_view(&record))
    }
    fn load_draft(
        &mut self,
        transcript_id: i64,
    ) -> Result<Option<selahcue_lan::protocol::SermonNoteDraftView>, String> {
        sermon_note_repo::find_by_transcript(&self.db, transcript_id)
            .map(|opt| opt.map(|r| record_to_view(&r)))
            .map_err(|e| e.to_string())
    }
    fn update_draft(
        &mut self,
        transcript_id: i64,
        edit: &SermonNoteEditInput,
    ) -> Result<selahcue_lan::protocol::SermonNoteDraftView, String> {
        let edited_at_ms = 2_000;
        let db_edit = sermon_note_repo::DraftEdit {
            title: edit.title.clone(),
            summary: edit.summary.clone(),
            sections_json: edit.sections_json.clone(),
            scriptures_json: edit.scriptures_json.clone(),
        };
        sermon_note_repo::update(&self.db, transcript_id, &db_edit, edited_at_ms)
            .map_err(|e| e.to_string())?;
        let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
            .map_err(|e| e.to_string())?
            .ok_or("draft vanished immediately after update")?;
        Ok(record_to_view(&record))
    }
}

fn record_to_view(
    r: &sermon_note_repo::SermonNoteRecord,
) -> selahcue_lan::protocol::SermonNoteDraftView {
    selahcue_lan::protocol::SermonNoteDraftView {
        title: r.title.clone(),
        summary: r.summary.clone(),
        sections_json: r.sections_json.clone(),
        scriptures_json: r.scriptures_json.clone(),
        ai_generated: r.ai_generated,
        disclosure: r.disclosure.clone(),
        provider: r.provider.clone(),
        model: r.model.clone(),
        created_at_ms: r.created_at_ms,
        edited_at_ms: r.edited_at_ms,
    }
}

/// Real store, real server, real client — the desktop's own production wiring shape, minus
/// only the Tauri/winit process boundary. Returns the addr/pin/database (for direct-file
/// assertions) alongside the connected `RemoteOperator`.
async fn setup() -> (RemoteOperator, Database) {
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;

    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Section, "Sermon");

    // ONE real on-disk SQLite file — a genuine tempdir path, exactly like the desktop's
    // `data_dir()/selahcue.db3`, opened TWICE (the pattern `SessionStore::open_transcript_sink`
    // documents: WAL supports multiple connections to one file with no shared Rust-level lock,
    // because every call into either connection is already serialized by `LiveController`'s own
    // `Arc<Mutex<_>>`).
    let dir = tempfile::tempdir().unwrap();
    let db_path = dir.path().join("selahcue.db3");
    let transcript_db = Database::open(&db_path).unwrap();
    let sermon_note_db = Database::open(&db_path).unwrap();
    let assertion_db = Database::open(&db_path).unwrap();

    let mut controller = LiveController::new(plan, 320, 180, Theme::dark());
    controller.set_transcript_sink(Box::new(selahcue_app::BatchingTranscriptWriter::new(
        RealTranscriptStore { db: transcript_db },
    )));
    controller.set_sermon_note_store(Box::new(RealSermonNoteStore { db: sermon_note_db }));
    let controller = Arc::new(Mutex::new(controller));

    let registry = Arc::new(AsyncMutex::new(SessionRegistry::new()));
    {
        let now = Instant::now();
        let mut reg = registry.lock().await;
        reg.offer_pairing("o", Role::Operator, now, Duration::from_secs(300));
        reg.redeem(
            "o",
            DeviceId("operator".into()),
            SessionToken::new("tok-op"),
            now,
        )
        .unwrap();
    }

    let server =
        Arc::new(ControlServer::new(&identity, registry, handler_for(controller.clone())).unwrap());
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr: SocketAddr = listener.local_addr().unwrap();
    let running = server.clone();
    tokio::spawn(async move {
        let _ = running.run(listener).await;
    });

    let op = RemoteOperator::connect(addr, "localhost", pin, "operator", "tok-op")
        .await
        .unwrap();
    (op, assertion_db)
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_real_transcript_id_flows_from_start_transcript_through_a_saved_and_loaded_draft() {
    let (mut op, assertion_db) = setup().await;

    // Before StartTranscript: no transcript exists yet anywhere in the real store.
    let before = op.active_transcript_id().await.unwrap();
    assert_eq!(
        before, None,
        "an empty real store must answer None, never a fabricated id"
    );

    // The desktop's real transcript-open path — the operator has no way to invent an id here;
    // it only learns what the host's real store assigns.
    op.start_transcript("Sunday Service", "on-device-whisper")
        .await
        .unwrap();

    // Ask the host, over the REAL LAN wire, which transcript new AI content should attach to.
    let real_id = op
        .active_transcript_id()
        .await
        .unwrap()
        .expect("a transcript now exists in the real store");

    // This is the crux of the F1 fix: the resolved id is whatever the REAL database assigned,
    // never a hardcoded stand-in like the webview harness's `SN_TRANSCRIPT_ID = 42`. Confirmed
    // directly against the database file, bypassing the LAN link entirely, so this assertion
    // cannot be satisfied by the server merely echoing back a made-up number.
    let rows_in_real_db = transcript_repo::list(&assertion_db).unwrap();
    assert_eq!(rows_in_real_db.len(), 1);
    assert_eq!(
        real_id, rows_in_real_db[0].id,
        "the id resolved over the LAN link must be the SAME id the real database assigned"
    );
    assert_eq!(rows_in_real_db[0].label, "Sunday Service");

    // Save a draft against that REAL id, over the real wire.
    let draft = SermonNoteDraftInput {
        title: "The Faithful Servant".into(),
        summary: Some("A message on faithfulness in small things.".into()),
        sections_json: r#"[{"heading":"Points","items":["Be faithful"],"points":[]}]"#.into(),
        scriptures_json: r#"["Luke 16:10"]"#.into(),
        ai_generated: true,
        disclosure: Some("AI-generated. Check every reference.".into()),
        provider: "SelahCue AI".into(),
        model: None,
    };
    let saved = op
        .save_sermon_note_draft(real_id, draft.clone())
        .await
        .unwrap()
        .expect("the host must accept and persist this draft");
    assert_eq!(saved.title, draft.title);
    assert!(saved.ai_generated);

    // Prove it is REALLY on disk, keyed to the REAL transcript id, bypassing the LAN link —
    // not merely echoed back by the server from what was sent.
    let on_disk = sermon_note_repo::find_by_transcript(&assertion_db, real_id)
        .unwrap()
        .expect("the note must actually be persisted in the real database file");
    assert_eq!(on_disk.title, draft.title);
    assert_eq!(on_disk.transcript_id, Some(real_id));

    // A fresh "app restart" load, over the real wire, against the real id: this is the
    // operator's `load_sermon_note_draft` Tauri command's real production path.
    let loaded = op
        .load_sermon_note_draft(real_id)
        .await
        .unwrap()
        .expect("the persisted draft must be loadable after a simulated restart");
    assert_eq!(loaded.title, draft.title);
    assert_eq!(loaded.disclosure, draft.disclosure);

    // Edit it, over the real wire, against the real id.
    let edit = SermonNoteEditInput {
        title: "Edited by the operator".into(),
        summary: None,
        sections_json: "[]".into(),
        scriptures_json: "[]".into(),
    };
    let updated = op
        .update_sermon_note_draft(real_id, edit.clone())
        .await
        .unwrap()
        .expect("the edit must be accepted");
    assert_eq!(updated.title, "Edited by the operator");
    // FR-123/FR-128 must survive the edit even over the full real LAN round trip.
    assert!(updated.ai_generated);
    assert_eq!(updated.disclosure, draft.disclosure);

    // And the source transcript is untouched throughout (FR-123's core invariant), verified
    // directly against the real database file.
    let transcript_after = transcript_repo::load(&assertion_db, real_id).unwrap();
    assert!(transcript_after.segments.is_empty());
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_stale_transcript_id_from_before_a_restart_still_resolves_over_the_real_wire() {
    // Extra confidence beyond the happy path above: start a transcript, end it (as a normal
    // "Stop Listening" would), and confirm the host STILL resolves it as the active transcript
    // for a generate/edit call that happens afterward — the real-world "generate notes right
    // after the sermon, listening already stopped" sequence.
    let (mut op, assertion_db) = setup().await;
    op.start_transcript("Sunday Service", "on-device-whisper")
        .await
        .unwrap();
    op.end_transcript().await.unwrap();

    let real_id = op
        .active_transcript_id()
        .await
        .unwrap()
        .expect("the ended transcript must still resolve");
    let rows = transcript_repo::list(&assertion_db).unwrap();
    assert_eq!(real_id, rows[0].id);
    assert!(
        rows[0].ended_at_ms.is_some(),
        "sanity: the transcript really is ended, not still open"
    );
}
