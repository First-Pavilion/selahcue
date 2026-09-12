//! 86akgqdv0 (PR #33 review, Sana F1 remediation): the sermon-note draft persistence LAN
//! commands, exercised end-to-end through `LiveController::apply` — mirrors
//! `test_transcript_durability.rs`'s `SpySink` pattern with a `SpySermonNoteStore`, proving the
//! wire commands reach the injected [`SermonNoteStore`] rather than any store the operator
//! process might open itself.

#![allow(clippy::unwrap_used)]

use selahcue_app::{LiveController, SermonNoteStore};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::protocol::{
    Command, SermonNoteDraftInput, SermonNoteDraftView, SermonNoteEditInput, ServerMessage,
};
use selahcue_present::Theme;
use std::sync::{Arc, Mutex};

fn controller() -> LiveController {
    let mut plan = ServicePlan::new("Sunday Service");
    plan.add_item(ItemKind::Section, "Sermon");
    LiveController::new(plan, 320, 180, Theme::dark())
}

fn sample_draft() -> SermonNoteDraftInput {
    SermonNoteDraftInput {
        title: "The Faithful Servant".into(),
        summary: Some("A message on faithfulness in small things.".into()),
        sections_json: r#"[{"heading":"Points","items":["Be faithful"],"points":[]}]"#.into(),
        scriptures_json: r#"["Luke 16:10"]"#.into(),
        ai_generated: true,
        disclosure: Some("AI-generated. Check every reference.".into()),
        provider: "SelahCue AI".into(),
        model: None,
    }
}

/// A recording spy `SermonNoteStore`: keeps everything it was told, in call order — the same
/// bounded-memory-test discipline `SpySink` in `test_transcript_durability.rs` follows (assert
/// the exact entity, never a proxy like a call count alone).
#[derive(Clone, Default)]
struct SpyStore(Arc<Mutex<SpyState>>);

#[derive(Default)]
struct SpyState {
    active_transcript_id: Option<i64>,
    saved: Vec<(i64, SermonNoteDraftInput)>,
    updated: Vec<(i64, SermonNoteEditInput)>,
    /// The single-slot persisted draft this fake "store" actually holds, keyed by
    /// transcript_id — real enough to make `load_draft` after `save_draft` return something.
    persisted: Option<(i64, SermonNoteDraftView)>,
    fail_next: bool,
}

impl SpyStore {
    fn new() -> Self {
        Self::default()
    }
    fn with_active_transcript_id(self, id: i64) -> Self {
        self.0.lock().unwrap().active_transcript_id = Some(id);
        self
    }
    fn saved_calls(&self) -> Vec<(i64, SermonNoteDraftInput)> {
        self.0.lock().unwrap().saved.clone()
    }
    fn updated_calls(&self) -> Vec<(i64, SermonNoteEditInput)> {
        self.0.lock().unwrap().updated.clone()
    }
    fn fail_next_call(&self) {
        self.0.lock().unwrap().fail_next = true;
    }
}

impl SermonNoteStore for SpyStore {
    fn active_transcript_id(&mut self) -> Result<Option<i64>, String> {
        Ok(self.0.lock().unwrap().active_transcript_id)
    }
    fn save_draft(
        &mut self,
        transcript_id: i64,
        draft: &SermonNoteDraftInput,
    ) -> Result<SermonNoteDraftView, String> {
        let mut s = self.0.lock().unwrap();
        if std::mem::take(&mut s.fail_next) {
            return Err("simulated failure".into());
        }
        s.saved.push((transcript_id, draft.clone()));
        let view = SermonNoteDraftView {
            title: draft.title.clone(),
            summary: draft.summary.clone(),
            sections_json: draft.sections_json.clone(),
            scriptures_json: draft.scriptures_json.clone(),
            ai_generated: draft.ai_generated,
            disclosure: draft.disclosure.clone(),
            provider: draft.provider.clone(),
            model: draft.model.clone(),
            created_at_ms: 1_000,
            edited_at_ms: 1_000,
        };
        s.persisted = Some((transcript_id, view.clone()));
        Ok(view)
    }
    fn load_draft(&mut self, transcript_id: i64) -> Result<Option<SermonNoteDraftView>, String> {
        let s = self.0.lock().unwrap();
        Ok(s.persisted
            .as_ref()
            .filter(|(id, _)| *id == transcript_id)
            .map(|(_, v)| v.clone()))
    }
    fn update_draft(
        &mut self,
        transcript_id: i64,
        edit: &SermonNoteEditInput,
    ) -> Result<SermonNoteDraftView, String> {
        let mut s = self.0.lock().unwrap();
        if std::mem::take(&mut s.fail_next) {
            return Err("simulated failure".into());
        }
        s.updated.push((transcript_id, edit.clone()));
        let Some((id, existing)) = s.persisted.clone() else {
            return Err("no draft exists for this transcript".into());
        };
        if id != transcript_id {
            return Err("no draft exists for this transcript".into());
        }
        let updated = SermonNoteDraftView {
            title: edit.title.clone(),
            summary: edit.summary.clone(),
            sections_json: edit.sections_json.clone(),
            scriptures_json: edit.scriptures_json.clone(),
            edited_at_ms: 2_000,
            ..existing
        };
        s.persisted = Some((transcript_id, updated.clone()));
        Ok(updated)
    }
}

#[test]
fn get_active_transcript_id_reaches_the_injected_store() {
    let mut c = controller();
    let store = SpyStore::new().with_active_transcript_id(42);
    c.set_sermon_note_store(Box::new(store));

    let reply = c.apply(&Command::GetActiveTranscriptId);
    match reply {
        selahcue_app::ControllerReply::Message(ServerMessage::ActiveTranscriptId {
            transcript_id,
        }) => assert_eq!(transcript_id, Some(42)),
        other => panic!("expected ActiveTranscriptId, got {other:?}"),
    }
}

#[test]
fn get_active_transcript_id_is_none_with_no_store_wired() {
    let mut c = controller();
    // No `set_sermon_note_store` call — exercises the NullSermonNoteStore default.
    let reply = c.apply(&Command::GetActiveTranscriptId);
    match reply {
        selahcue_app::ControllerReply::Message(ServerMessage::ActiveTranscriptId {
            transcript_id,
        }) => assert_eq!(transcript_id, None),
        other => panic!("expected ActiveTranscriptId, got {other:?}"),
    }
}

#[test]
fn save_sermon_note_draft_reaches_the_store_with_the_exact_payload() {
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));

    let reply = c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });
    match reply {
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteDraft {
            transcript_id,
            draft: Some(view),
        }) => {
            assert_eq!(transcript_id, 7);
            assert_eq!(view.title, sample_draft().title);
            assert!(view.ai_generated);
            assert_eq!(view.disclosure, sample_draft().disclosure);
        }
        other => panic!("expected SermonNoteDraft with a draft, got {other:?}"),
    }
    assert_eq!(store.saved_calls(), vec![(7, sample_draft())]);
}

#[test]
fn load_sermon_note_draft_returns_what_was_previously_saved() {
    let mut c = controller();
    c.set_sermon_note_store(Box::new(SpyStore::new()));
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });

    let reply = c.apply(&Command::LoadSermonNoteDraft { transcript_id: 7 });
    match reply {
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteDraft {
            transcript_id,
            draft: Some(view),
        }) => {
            assert_eq!(transcript_id, 7);
            assert_eq!(view.title, sample_draft().title);
        }
        other => panic!("expected SermonNoteDraft with a draft, got {other:?}"),
    }
}

#[test]
fn load_sermon_note_draft_is_none_for_an_unknown_transcript() {
    let mut c = controller();
    c.set_sermon_note_store(Box::new(SpyStore::new()));
    let reply = c.apply(&Command::LoadSermonNoteDraft { transcript_id: 999 });
    match reply {
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteDraft {
            transcript_id,
            draft,
        }) => {
            assert_eq!(transcript_id, 999);
            assert_eq!(draft, None);
        }
        other => panic!("expected SermonNoteDraft with no draft, got {other:?}"),
    }
}

#[test]
fn update_sermon_note_draft_reaches_the_store_and_returns_the_updated_view() {
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });

    let edit = SermonNoteEditInput {
        title: "Edited title".into(),
        summary: None,
        sections_json: "[]".into(),
        scriptures_json: "[]".into(),
    };
    let reply = c.apply(&Command::UpdateSermonNoteDraft {
        transcript_id: 7,
        edit: edit.clone(),
    });
    match reply {
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteDraft {
            transcript_id,
            draft: Some(view),
        }) => {
            assert_eq!(transcript_id, 7);
            assert_eq!(view.title, "Edited title");
            // FR-123/FR-128: the label/disclosure survive an edit — the fake store models the
            // same structural guarantee the real `sermon_note_repo::update` has (nothing in
            // `SermonNoteEditInput` can carry them).
            assert!(view.ai_generated);
            assert_eq!(view.disclosure, sample_draft().disclosure);
        }
        other => panic!("expected SermonNoteDraft with a draft, got {other:?}"),
    }
    assert_eq!(store.updated_calls(), vec![(7, edit)]);
}

#[test]
fn update_sermon_note_draft_for_a_transcript_with_no_draft_is_denied() {
    let mut c = controller();
    c.set_sermon_note_store(Box::new(SpyStore::new()));

    let reply = c.apply(&Command::UpdateSermonNoteDraft {
        transcript_id: 7,
        edit: SermonNoteEditInput {
            title: "x".into(),
            summary: None,
            sections_json: "[]".into(),
            scriptures_json: "[]".into(),
        },
    });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Deny(selahcue_lan::protocol::DenyReason::BadRequest)
    ));
}

#[test]
fn save_sermon_note_draft_refused_by_the_store_is_denied_not_a_panic() {
    let mut c = controller();
    let store = SpyStore::new();
    store.fail_next_call();
    c.set_sermon_note_store(Box::new(store));

    let reply = c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Deny(selahcue_lan::protocol::DenyReason::BadRequest)
    ));
}

// ---------------------------------------------------------------------------------------
// Regression + positive control: ControllerSnapshot must stay untouched by sermon-note
// activity (mirrors `controller_snapshot_stays_untouched_by_transcript_activity` in
// `test_transcript_durability.rs`) — sermon notes are a SEPARATE store, never routed through
// crash recovery.
// ---------------------------------------------------------------------------------------
#[test]
fn controller_snapshot_stays_untouched_by_sermon_note_activity() {
    let mut c = controller();
    c.set_sermon_note_store(Box::new(SpyStore::new()));
    let now = std::time::Instant::now();
    let before = c.snapshot(now);

    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });
    c.apply(&Command::UpdateSermonNoteDraft {
        transcript_id: 7,
        edit: SermonNoteEditInput {
            title: "Edited".into(),
            summary: None,
            sections_json: "[]".into(),
            scriptures_json: "[]".into(),
        },
    });

    let after = c.snapshot(now);
    assert_eq!(
        before, after,
        "ControllerSnapshot must be completely unaffected by sermon-note draft persistence"
    );
}
