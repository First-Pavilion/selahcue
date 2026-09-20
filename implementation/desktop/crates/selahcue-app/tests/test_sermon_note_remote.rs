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
use selahcue_lan::protocol::{
    self, SermonNoteDraftInput, SermonNoteDraftView, SermonNoteEditInput, ServerMessage,
};
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
    fn stage_regeneration(
        &mut self,
        transcript_id: i64,
        draft: &SermonNoteDraftInput,
    ) -> Result<selahcue_app::RegenerationSlot, String> {
        let generated_at_ms = 3_000;
        let pending = sermon_note_repo::PendingRegeneration {
            title: draft.title.clone(),
            summary: draft.summary.clone(),
            sections_json: draft.sections_json.clone(),
            scriptures_json: draft.scriptures_json.clone(),
            ai_generated: draft.ai_generated,
            disclosure: draft.disclosure.clone(),
            provider: draft.provider.clone(),
            model: draft.model.clone(),
            generated_at_ms,
        };
        sermon_note_repo::stage_regeneration(&self.db, transcript_id, &pending)
            .map_err(|e| e.to_string())?;
        let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
            .map_err(|e| e.to_string())?
            .ok_or("draft vanished immediately after stage")?;
        Ok(regeneration_slot_of(&record))
    }
    fn confirm_regeneration(
        &mut self,
        transcript_id: i64,
    ) -> Result<selahcue_app::RegenerationSlot, String> {
        let record = sermon_note_repo::confirm_regeneration(&self.db, transcript_id)
            .map_err(|e| e.to_string())?;
        Ok(regeneration_slot_of(&record))
    }
    // 86akgqdx8 review, Cody — Minor: a transcript with NO `sermon_note` row at all (never
    // generated) must discard as a harmless no-op, matching `discard_regeneration`'s own
    // trait doc ("never errors for nothing was pending") — not surface as a store-layer
    // error just because there is nothing to read back. Kept in sync by hand with
    // `selahcue-desktop`'s `RealSermonNoteStore` (see this file's module doc).
    fn discard_regeneration(
        &mut self,
        transcript_id: i64,
    ) -> Result<selahcue_app::RegenerationSlot, String> {
        sermon_note_repo::discard_regeneration(&self.db, transcript_id)
            .map_err(|e| e.to_string())?;
        let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
            .map_err(|e| e.to_string())?;
        Ok(match record {
            Some(record) => regeneration_slot_of(&record),
            None => selahcue_app::RegenerationSlot::default(),
        })
    }
}

fn regeneration_slot_of(r: &sermon_note_repo::SermonNoteRecord) -> selahcue_app::RegenerationSlot {
    selahcue_app::RegenerationSlot {
        current: Some(record_to_view(r)),
        pending: r
            .pending
            .as_ref()
            .map(|p| selahcue_lan::protocol::SermonNoteDraftView {
                title: p.title.clone(),
                summary: p.summary.clone(),
                sections_json: p.sections_json.clone(),
                scriptures_json: p.scriptures_json.clone(),
                ai_generated: p.ai_generated,
                disclosure: p.disclosure.clone(),
                provider: p.provider.clone(),
                model: p.model.clone(),
                created_at_ms: p.generated_at_ms,
                edited_at_ms: p.generated_at_ms,
            }),
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

// ---------------------------------------------------------------------------------------
// LAN frame cap vs. data-layer draft cap (86akgqdv0 PR #33 review — Vera F5 / Sana N1,
// High). Reproduced by BOTH reviewers independently against `d7d89f9`: a save/update whose
// serialized `Request` exceeded `selahcue_lan::MAX_MESSAGE_BYTES` (64 KiB) turned into a
// DROPPED TCP CONNECTION (tungstenite refuses the over-cap frame; `request_loop` reads that
// as an error and closes the socket), taking the operator's WHOLE control link down with it
// — GO LIVE, Next, Blackout, Clear all fail afterward, since `selahcue-operator` never
// re-dials. The fix has two parts, both exercised below: (1) `sermon_note_repo`'s
// `MAX_SECTIONS_JSON_BYTES`/`MAX_SCRIPTURES_JSON_BYTES` shrank so a REALISTIC draft at every
// declared maximum fits comfortably under the wire cap (the primary fix); (2)
// `RemoteOperator::would_exceed_wire_cap` measures the actual outgoing frame and refuses to
// send anything that would still exceed the cap — e.g. a hostile payload whose JSON escaping
// inflates far past its raw byte count (the backstop). Both tests below use a REAL
// `Database::open` file, a REAL `ControlServer`/`RemoteOperator` TLS round trip — no
// fabricated transcript id, no mocked transport.
// ---------------------------------------------------------------------------------------

/// A draft at every data-layer maximum, with ordinary (non-adversarial) content, must
/// persist over the real wire — not merely avoid crashing. This is the positive control for
/// the refusal test below: the cap reconciliation must not make the feature useless for
/// realistic content, only for pathological content.
///
/// **Before 86akgqdv0's fix** (the old `MAX_SECTIONS_JSON_BYTES = 200_000` /
/// `MAX_SCRIPTURES_JSON_BYTES = 20_000`, no pre-send guard), building this exact draft at
/// those old maxima and sending it would exceed `MAX_MESSAGE_BYTES` and drop the connection
/// — this test would fail with a `TransportError`, not a clean `unwrap()` panic on a `None`.
/// Mutation-verified by hand: reverting `sermon_note_repo`'s caps to their pre-fix values
/// turns this RED with exactly that symptom (see the PR description's verification section).
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_draft_at_every_data_layer_maximum_with_realistic_content_persists_over_the_real_wire() {
    let (mut op, assertion_db) = setup().await;
    op.start_transcript("Sunday Service", "on-device-whisper")
        .await
        .unwrap();
    let real_id = op
        .active_transcript_id()
        .await
        .unwrap()
        .expect("a transcript now exists in the real store");

    let draft = SermonNoteDraftInput {
        title: "x".repeat(sermon_note_repo::MAX_TITLE_CHARS),
        summary: Some("y".repeat(sermon_note_repo::MAX_SUMMARY_CHARS)),
        sections_json: format!(
            r#"["{}"]"#,
            "s".repeat(sermon_note_repo::MAX_SECTIONS_JSON_BYTES - 4)
        ),
        scriptures_json: format!(
            r#"["{}"]"#,
            "r".repeat(sermon_note_repo::MAX_SCRIPTURES_JSON_BYTES - 4)
        ),
        ai_generated: true,
        disclosure: Some("d".repeat(sermon_note_repo::MAX_DISCLOSURE_CHARS)),
        provider: "p".repeat(sermon_note_repo::MAX_PROVIDER_CHARS),
        model: Some("m".repeat(sermon_note_repo::MAX_MODEL_CHARS)),
    };
    // Sanity: every field really is AT its declared maximum, not merely close to it.
    assert_eq!(
        draft.title.chars().count(),
        sermon_note_repo::MAX_TITLE_CHARS
    );
    assert_eq!(
        draft.summary.as_ref().unwrap().chars().count(),
        sermon_note_repo::MAX_SUMMARY_CHARS
    );
    assert_eq!(
        draft.sections_json.len(),
        sermon_note_repo::MAX_SECTIONS_JSON_BYTES
    );
    assert_eq!(
        draft.scriptures_json.len(),
        sermon_note_repo::MAX_SCRIPTURES_JSON_BYTES
    );

    let saved = op
        .save_sermon_note_draft(real_id, draft.clone())
        .await
        .unwrap()
        .expect("a realistic draft at every declared maximum must persist over the real wire");
    assert_eq!(saved.title, draft.title);
    assert_eq!(saved.disclosure, draft.disclosure);

    // The link must still be alive: a follow-up command on the SAME connection succeeds.
    let after = op.active_transcript_id().await.unwrap();
    assert_eq!(
        after,
        Some(real_id),
        "the control link must survive this save"
    );

    // And it is REALLY on disk, bypassing the LAN link.
    let on_disk = sermon_note_repo::find_by_transcript(&assertion_db, real_id)
        .unwrap()
        .expect("the maximal draft must actually be persisted");
    assert_eq!(
        on_disk.sections_json.len(),
        sermon_note_repo::MAX_SECTIONS_JSON_BYTES
    );
}

/// The regression test proper: a draft at the SAME declared data-layer maxima as the test
/// above, but with hostile content (every byte of `sections_json`/`scriptures_json` a JSON
/// control character, which escapes to a 6-byte `\u00XX` sequence on the wire — the data
/// layer bounds byte length only, never format, so this is a legal value at this layer).
/// `6 * (MAX_SECTIONS_JSON_BYTES + MAX_SCRIPTURES_JSON_BYTES)` alone is ~111 KB, comfortably
/// past the 64 KiB transport cap even after 86akgqdv0's cap reconciliation — proving the
/// PRE-SEND GUARD, not merely the shrunk caps, is what keeps the connection alive here.
///
/// **This test fails today (before the guard existed) and passes after**: mutation-verified
/// by hand by deleting the `would_exceed_wire_cap` check from `RemoteOperator::
/// save_sermon_note_draft` — with the guard gone, this exact call becomes a dropped
/// connection (`Err(TransportError::Ws(..))`, "Connection reset by peer"), and the
/// `.unwrap()` on the save call panics instead of returning `Ok(None)`.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_draft_whose_escaped_wire_size_exceeds_the_frame_cap_is_refused_without_dropping_the_connection(
) {
    let (mut op, assertion_db) = setup().await;
    op.start_transcript("Sunday Service", "on-device-whisper")
        .await
        .unwrap();
    let real_id = op
        .active_transcript_id()
        .await
        .unwrap()
        .expect("a transcript now exists in the real store");

    let draft = SermonNoteDraftInput {
        title: "x".repeat(sermon_note_repo::MAX_TITLE_CHARS),
        summary: Some("y".repeat(sermon_note_repo::MAX_SUMMARY_CHARS)),
        sections_json: "\u{1}".repeat(sermon_note_repo::MAX_SECTIONS_JSON_BYTES),
        scriptures_json: "\u{1}".repeat(sermon_note_repo::MAX_SCRIPTURES_JSON_BYTES),
        ai_generated: true,
        disclosure: Some("d".repeat(sermon_note_repo::MAX_DISCLOSURE_CHARS)),
        provider: "p".repeat(sermon_note_repo::MAX_PROVIDER_CHARS),
        model: Some("m".repeat(sermon_note_repo::MAX_MODEL_CHARS)),
    };

    // The critical assertion: `Ok(_)`, never `Err` — the connection must never drop, even
    // though this frame is refused.
    let result = op
        .save_sermon_note_draft(real_id, draft)
        .await
        .expect("an over-cap save must be refused cleanly, never a transport/connection error");
    assert_eq!(
        result, None,
        "a frame this large must be refused pre-send, not sent and then rejected"
    );
    // Nothing was persisted.
    assert_eq!(
        sermon_note_repo::find_by_transcript(&assertion_db, real_id).unwrap(),
        None
    );

    // The whole point of the fix: the control link is still alive afterward. GO LIVE, Next,
    // Blackout, Clear all share this same connection in the real operator console.
    let after = op
        .active_transcript_id()
        .await
        .expect("the control link must survive an over-cap save attempt");
    assert_eq!(after, Some(real_id));

    // And the SAME connection can still do a normal, in-budget save afterward — the link is
    // not merely alive, it is still fully functional.
    let small_draft = SermonNoteDraftInput {
        title: "A Faithful Servant".into(),
        summary: None,
        sections_json: "[]".into(),
        scriptures_json: "[]".into(),
        ai_generated: false,
        disclosure: None,
        provider: "Local (offline)".into(),
        model: None,
    };
    let saved = op
        .save_sermon_note_draft(real_id, small_draft)
        .await
        .unwrap()
        .expect("a normal save on the same connection must still work after the refusal");
    assert_eq!(saved.title, "A Faithful Servant");
}

/// `sermon_note_repo`'s per-field caps are hand-reconciled against `MAX_MESSAGE_BYTES` for a
/// SINGLE draft travelling inside a `SaveSermonNoteDraft`/`UpdateSermonNoteDraft` `Request`
/// (see that doc comment, ~60,060 B worst case, 8% under the 64 KiB cap). FR-129's
/// `ServerMessage::SermonNoteRegenerationState` carries TWO drafts (`current` + `pending`) in
/// one REPLY — a shape that reconciliation never accounted for (Vera, this ticket's review).
///
/// This measures the REAL wire size (`selahcue_lan::protocol::to_json`, the exact function
/// `wire::send_json` calls) rather than trusting arithmetic, turning the reconciliation claim
/// into an executable, maintained fact instead of prose that can silently go stale.
///
/// Two data points, both real:
/// - Ordinary Latin-script content, every field at its declared maximum: the reply fits
///   comfortably under the cap (this test's main assertion — a REGRESSION here means a future
///   change to any of the per-field maxima needs to re-examine this reply shape too).
/// - Ordinary NON-Latin content (any 3-byte-UTF-8 script — CJK, many African/Asian scripts) at
///   the SAME declared maxima: `MAX_TITLE_CHARS`/`MAX_SUMMARY_CHARS` are CHARACTER bounds, so
///   3-byte-per-character content triples their byte footprint versus the Latin case above,
///   and the two-draft reply EXCEEDS the 64 KiB cap. This is NOT a live defect today — proven
///   separately below by actually sending it over the real wire and confirming the connection
///   survives — because neither the server's write path (only `max_message_size`/
///   `max_frame_size` on the READ side, `selahcue-lan/src/server.rs`) nor the client's default
///   `WebSocketConfig` (`selahcue-lan/src/client.rs`, ~64 MiB reader) enforces any cap on this
///   REPLY direction. `OperatorStateView.transcript` was already unbounded on this same reply
///   path before this ticket; FR-129 does not introduce the asymmetry. It DOES make the
///   per-field caps' "reconciled with the wire cap" doc claim overbroad for this reply shape —
///   fixed by scoping that doc to the request direction it was actually measured for. Adding
///   real enforcement to the reply direction (a `WebSocketConfig` on the client, matching the
///   server's) is tracked as a follow-up, not fixed here.
#[test]
fn a_two_draft_regeneration_state_reply_is_measured_against_the_wire_cap_both_ways() {
    fn maxed_view(fill_char: char) -> SermonNoteDraftView {
        SermonNoteDraftView {
            title: fill_char
                .to_string()
                .repeat(sermon_note_repo::MAX_TITLE_CHARS),
            summary: Some(
                fill_char
                    .to_string()
                    .repeat(sermon_note_repo::MAX_SUMMARY_CHARS),
            ),
            // Byte-denominated bounds already: the fill character choice does not change
            // their byte footprint the way the char-denominated bounds above do.
            sections_json: format!(
                r#"["{}"]"#,
                "s".repeat(sermon_note_repo::MAX_SECTIONS_JSON_BYTES - 4)
            ),
            scriptures_json: format!(
                r#"["{}"]"#,
                "r".repeat(sermon_note_repo::MAX_SCRIPTURES_JSON_BYTES - 4)
            ),
            ai_generated: true,
            disclosure: Some(
                fill_char
                    .to_string()
                    .repeat(sermon_note_repo::MAX_DISCLOSURE_CHARS),
            ),
            provider: fill_char
                .to_string()
                .repeat(sermon_note_repo::MAX_PROVIDER_CHARS),
            model: Some(
                fill_char
                    .to_string()
                    .repeat(sermon_note_repo::MAX_MODEL_CHARS),
            ),
            created_at_ms: 1_000,
            edited_at_ms: 2_000,
        }
    }

    let reply_size = |fill_char: char| -> usize {
        let msg = ServerMessage::SermonNoteRegenerationState {
            transcript_id: 1,
            current: Some(maxed_view(fill_char)),
            pending: Some(maxed_view(fill_char)),
        };
        protocol::to_json(&msg)
            .expect("a valid SermonNoteRegenerationState always serializes")
            .len()
    };

    let ascii_size = reply_size('x');
    assert!(
        ascii_size <= selahcue_lan::MAX_MESSAGE_BYTES,
        "a two-draft regeneration reply with ordinary Latin-script content at every declared \
         maximum must fit under the wire cap ({ascii_size} B vs {} B cap) — if this regresses, \
         a per-field maximum grew without re-checking this reply shape",
        selahcue_lan::MAX_MESSAGE_BYTES
    );

    // U+6771 ('東'): a real, ordinary 3-byte-UTF-8 character — not adversarial control-byte
    // escaping like the hostile test above, just everyday non-Latin text.
    let multibyte_size = reply_size('\u{6771}');
    assert!(
        multibyte_size > selahcue_lan::MAX_MESSAGE_BYTES,
        "ordinary non-Latin content at the same declared maxima was expected to exceed the \
         wire cap on THIS reply shape ({multibyte_size} B vs {} B cap) — if this now fits, the \
         reconciliation doc comment on sermon_note_repo's caps may be stale in the other \
         direction; re-check it either way",
        selahcue_lan::MAX_MESSAGE_BYTES
    );
}

/// 86akgqdx8 review, Cody — Minor: discarding a regeneration for a transcript that has NO
/// `sermon_note` row at all (never generated, nothing ever saved) must be the same harmless
/// no-op `discard_regeneration`'s trait doc promises for "nothing was pending" — not a denied
/// command. Before the fix, `RealSermonNoteStore`'s adapter read back `find_by_transcript`
/// after the (successful, zero-rows-affected) `UPDATE` and turned the resulting `None` into a
/// store-layer `Err`, which `LiveController::apply` turns into `ControllerReply::Deny` —
/// observable here as `Ok(None)` from `RemoteOperator`, exactly like a REFUSED command, not a
/// harmless one. Only reachable through the REAL SQL-backed store (the `SpyStore`-based
/// controller test of the same name never had this bug — it does not model "no row exists").
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn discarding_with_no_draft_ever_generated_is_a_harmless_success_over_the_real_wire() {
    let (mut op, _assertion_db) = setup().await;
    op.start_transcript("Sunday Service", "on-device-whisper")
        .await
        .unwrap();
    let real_id = op
        .active_transcript_id()
        .await
        .unwrap()
        .expect("a transcript now exists in the real store");
    // No SaveSermonNoteDraft/generate ever happened for this transcript — the premise.

    let slot = op
        .discard_sermon_note_regeneration(real_id)
        .await
        .expect("a discard with nothing to discard must never be a transport error")
        .expect(
            "discarding must be a harmless success even when no draft was ever generated, \
             not a denied command",
        );
    assert!(slot.current.is_none());
    assert!(slot.pending.is_none());

    // The link is still alive and functional afterward.
    let after = op.active_transcript_id().await.unwrap();
    assert_eq!(after, Some(real_id));
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

// ---------------------------------------------------------------------------------------
// Regenerate-with-retention (FR-129, 86akgqdx8), real store + real wire — the same "no id
// or content is ever fabricated by the test" discipline as the rest of this file.
// ---------------------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn staging_over_the_real_wire_leaves_the_accepted_draft_retrievable_until_confirmed() {
    let (mut op, assertion_db) = setup().await;
    op.start_transcript("Sunday Service", "on-device-whisper")
        .await
        .unwrap();
    let real_id = op.active_transcript_id().await.unwrap().unwrap();

    let original = SermonNoteDraftInput {
        title: "The Faithful Servant".into(),
        summary: Some("Original summary.".into()),
        sections_json: "[]".into(),
        scriptures_json: "[]".into(),
        ai_generated: true,
        disclosure: Some("AI-generated. Check every reference.".into()),
        provider: "SelahCue AI".into(),
        model: None,
    };
    op.save_sermon_note_draft(real_id, original.clone())
        .await
        .unwrap()
        .unwrap();

    let regenerated = SermonNoteDraftInput {
        title: "Regenerated Title".into(),
        summary: Some("A fresh summary.".into()),
        sections_json: "[]".into(),
        scriptures_json: "[]".into(),
        ai_generated: true,
        disclosure: Some("AI-generated. Check every reference.".into()),
        provider: "SelahCue AI".into(),
        model: None,
    };
    let slot = op
        .stage_sermon_note_regeneration(real_id, regenerated.clone())
        .await
        .unwrap()
        .expect("staging over a real draft must be accepted");
    // The accepted (prior) draft, as reported over the wire, is UNCHANGED.
    assert_eq!(slot.current.as_ref().unwrap().title, "The Faithful Servant");
    assert_eq!(slot.pending.as_ref().unwrap().title, "Regenerated Title");

    // Directly on disk, bypassing the LAN link: the prior draft's real columns are
    // untouched, and the pending regeneration really is there.
    let on_disk = sermon_note_repo::find_by_transcript(&assertion_db, real_id)
        .unwrap()
        .unwrap();
    assert_eq!(on_disk.title, "The Faithful Servant");
    assert_eq!(on_disk.pending.as_ref().unwrap().title, "Regenerated Title");

    // Confirming replaces the accepted draft; the prior version is now gone (single
    // prior version — not a history).
    let confirmed_slot = op
        .confirm_sermon_note_regeneration(real_id)
        .await
        .unwrap()
        .expect("confirming a legitimate pending regeneration must be accepted");
    assert_eq!(
        confirmed_slot.current.as_ref().unwrap().title,
        "Regenerated Title"
    );
    assert!(confirmed_slot.pending.is_none());

    let on_disk_after_confirm = sermon_note_repo::find_by_transcript(&assertion_db, real_id)
        .unwrap()
        .unwrap();
    assert_eq!(on_disk_after_confirm.title, "Regenerated Title");
    assert!(on_disk_after_confirm.pending.is_none());
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn discarding_over_the_real_wire_leaves_the_accepted_draft_exactly_as_it_was() {
    let (mut op, assertion_db) = setup().await;
    op.start_transcript("Sunday Service", "on-device-whisper")
        .await
        .unwrap();
    let real_id = op.active_transcript_id().await.unwrap().unwrap();

    let original = SermonNoteDraftInput {
        title: "The Faithful Servant".into(),
        summary: None,
        sections_json: "[]".into(),
        scriptures_json: "[]".into(),
        ai_generated: true,
        disclosure: Some("AI-generated. Check every reference.".into()),
        provider: "SelahCue AI".into(),
        model: None,
    };
    op.save_sermon_note_draft(real_id, original.clone())
        .await
        .unwrap()
        .unwrap();

    op.stage_sermon_note_regeneration(
        real_id,
        SermonNoteDraftInput {
            title: "A regeneration nobody wanted".into(),
            ..original.clone()
        },
    )
    .await
    .unwrap()
    .unwrap();

    let after_discard = op
        .discard_sermon_note_regeneration(real_id)
        .await
        .unwrap()
        .expect("discard must succeed even though it changes nothing about the accepted draft");
    assert_eq!(
        after_discard.current.as_ref().unwrap().title,
        "The Faithful Servant"
    );
    assert!(after_discard.pending.is_none());

    let on_disk = sermon_note_repo::find_by_transcript(&assertion_db, real_id)
        .unwrap()
        .unwrap();
    assert_eq!(on_disk.title, "The Faithful Servant");
    assert!(on_disk.pending.is_none());
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn confirming_a_downgrading_regeneration_is_denied_over_the_real_wire_and_stays_pending() {
    // "Once AI-generated, always AI-generated" (PR #33 review, Sana N2), proven end-to-end:
    // a degraded regenerate's pending draft cannot be confirmed over an AI-generated
    // accepted draft, but it STAYS staged (visible, discardable) rather than vanishing.
    let (mut op, assertion_db) = setup().await;
    op.start_transcript("Sunday Service", "on-device-whisper")
        .await
        .unwrap();
    let real_id = op.active_transcript_id().await.unwrap().unwrap();

    op.save_sermon_note_draft(
        real_id,
        SermonNoteDraftInput {
            title: "The Faithful Servant".into(),
            summary: None,
            sections_json: "[]".into(),
            scriptures_json: "[]".into(),
            ai_generated: true,
            disclosure: Some("AI-generated. Check every reference.".into()),
            provider: "SelahCue AI".into(),
            model: None,
        },
    )
    .await
    .unwrap()
    .unwrap();

    op.stage_sermon_note_regeneration(
        real_id,
        SermonNoteDraftInput {
            title: "Offline outline".into(),
            summary: None,
            sections_json: "[]".into(),
            scriptures_json: "[]".into(),
            ai_generated: false,
            disclosure: None,
            provider: "Local (offline)".into(),
            model: None,
        },
    )
    .await
    .unwrap()
    .unwrap();

    let denied = op.confirm_sermon_note_regeneration(real_id).await.unwrap();
    assert!(
        denied.is_none(),
        "the host must deny confirming a provenance downgrade"
    );

    // The accepted draft is untouched, and the pending draft is STILL there.
    let on_disk = sermon_note_repo::find_by_transcript(&assertion_db, real_id)
        .unwrap()
        .unwrap();
    assert_eq!(on_disk.title, "The Faithful Servant");
    assert!(on_disk.ai_generated);
    assert!(
        on_disk.pending.is_some(),
        "the refused pending draft must remain staged, not be silently dropped"
    );
}
