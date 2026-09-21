//! 86akgqdv0 (PR #33 review, Sana F1 remediation): the sermon-note draft persistence LAN
//! commands, exercised end-to-end through `LiveController::apply` — mirrors
//! `test_transcript_durability.rs`'s `SpySink` pattern with a `SpySermonNoteStore`, proving the
//! wire commands reach the injected [`SermonNoteStore`] rather than any store the operator
//! process might open itself.

#![allow(clippy::unwrap_used)]

use selahcue_app::{LiveController, RegenerationSlot, SermonNoteStore};
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
    staged: Vec<(i64, SermonNoteDraftInput)>,
    /// The single-slot persisted draft this fake "store" actually holds, keyed by
    /// transcript_id — real enough to make `load_draft` after `save_draft` return something.
    persisted: Option<(i64, SermonNoteDraftView)>,
    /// The single-slot pending regeneration (FR-129, 86akgqdx8) — mirrors
    /// `sermon_note_repo`'s real `pending_*` columns closely enough to exercise
    /// `LiveController`'s dispatch, not a full re-implementation of the repo.
    pending: Option<(i64, SermonNoteDraftView)>,
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
    fn staged_calls(&self) -> Vec<(i64, SermonNoteDraftInput)> {
        self.0.lock().unwrap().staged.clone()
    }
    fn fail_next_call(&self) {
        self.0.lock().unwrap().fail_next = true;
    }
    fn has_pending(&self) -> bool {
        self.0.lock().unwrap().pending.is_some()
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
    fn stage_regeneration(
        &mut self,
        transcript_id: i64,
        draft: &SermonNoteDraftInput,
    ) -> Result<RegenerationSlot, String> {
        let mut s = self.0.lock().unwrap();
        if std::mem::take(&mut s.fail_next) {
            return Err("simulated failure".into());
        }
        let Some((id, current)) = s.persisted.clone() else {
            return Err("no accepted draft exists for this transcript".into());
        };
        if id != transcript_id {
            return Err("no accepted draft exists for this transcript".into());
        }
        s.staged.push((transcript_id, draft.clone()));
        let pending_view = SermonNoteDraftView {
            title: draft.title.clone(),
            summary: draft.summary.clone(),
            sections_json: draft.sections_json.clone(),
            scriptures_json: draft.scriptures_json.clone(),
            ai_generated: draft.ai_generated,
            disclosure: draft.disclosure.clone(),
            provider: draft.provider.clone(),
            model: draft.model.clone(),
            created_at_ms: 3_000,
            edited_at_ms: 3_000,
        };
        s.pending = Some((transcript_id, pending_view.clone()));
        Ok(RegenerationSlot {
            current: Some(current),
            pending: Some(pending_view),
        })
    }
    fn confirm_regeneration(&mut self, transcript_id: i64) -> Result<RegenerationSlot, String> {
        let mut s = self.0.lock().unwrap();
        let Some((id, current)) = s.persisted.clone() else {
            return Err("nothing pending for this transcript".into());
        };
        let Some((pending_id, pending)) = s.pending.clone() else {
            return Err("nothing pending for this transcript".into());
        };
        if id != transcript_id || pending_id != transcript_id {
            return Err("nothing pending for this transcript".into());
        }
        // "Once AI-generated, always AI-generated" (mirrors
        // `sermon_note_repo::confirm_regeneration`'s real guard).
        if current.ai_generated && !pending.ai_generated {
            return Err("would remove the AI-generated label".into());
        }
        s.persisted = Some((transcript_id, pending.clone()));
        s.pending = None;
        Ok(RegenerationSlot {
            current: Some(pending),
            pending: None,
        })
    }
    fn discard_regeneration(&mut self, transcript_id: i64) -> Result<RegenerationSlot, String> {
        let mut s = self.0.lock().unwrap();
        if s.pending
            .as_ref()
            .is_some_and(|(id, _)| *id == transcript_id)
        {
            s.pending = None;
        }
        Ok(RegenerationSlot {
            current: s
                .persisted
                .as_ref()
                .filter(|(id, _)| *id == transcript_id)
                .map(|(_, v)| v.clone()),
            pending: None,
        })
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

// ---------------------------------------------------------------------------------------
// FR-123/FR-128 integrity (PR #33 review, Sana N2 — Medium): the disclosure/ai_generated
// pairing and the "once AI-generated, always AI-generated" invariant are enforced HERE, in
// `LiveController::apply`, not merely hoped for from a well-behaved caller — RBAC narrowing
// (`SaveSermonNotes`, Operator-only) alone does not stop a PERMITTED caller from sending an
// internally inconsistent or provenance-downgrading payload.
// ---------------------------------------------------------------------------------------

#[test]
fn save_sermon_note_draft_with_ai_generated_true_and_no_disclosure_is_denied() {
    // Before this check existed, this exact payload silently relabelled an AI draft as
    // human-authored / stripped the FR-128 warning (PR #33 review, Sana N2's reproduction).
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));

    let mut draft = sample_draft();
    draft.ai_generated = true;
    draft.disclosure = None;
    let reply = c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft,
    });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Deny(selahcue_lan::protocol::DenyReason::BadRequest)
    ));
    assert!(
        store.saved_calls().is_empty(),
        "an inconsistent pairing must be refused BEFORE it ever reaches the store"
    );
}

#[test]
fn save_sermon_note_draft_with_ai_generated_false_and_a_disclosure_is_denied() {
    // The other half of the "present EXACTLY WHEN" pairing: a disclosure on a draft that
    // claims to be human-authored is just as inconsistent as the reverse.
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));

    let mut draft = sample_draft();
    draft.ai_generated = false;
    draft.disclosure = Some("AI-generated. Check every reference.".into());
    let reply = c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft,
    });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Deny(selahcue_lan::protocol::DenyReason::BadRequest)
    ));
    assert!(store.saved_calls().is_empty());
}

#[test]
fn save_sermon_note_draft_with_a_consistent_human_authored_pairing_is_accepted_positive_control() {
    // Positive control for the two tests above: the pairing check must not reject
    // everything — a genuinely human-authored (or degraded-offline) draft with NO
    // disclosure and `ai_generated: false` is legitimate and must still save. Mirrors the
    // real `generate_sermon_notes` degraded/offline-fallback outcome (FR-135).
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));

    let mut draft = sample_draft();
    draft.ai_generated = false;
    draft.disclosure = None;
    let reply = c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: draft.clone(),
    });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteDraft {
            draft: Some(_),
            ..
        })
    ));
    assert_eq!(store.saved_calls(), vec![(7, draft)]);
}

#[test]
fn save_sermon_note_draft_cannot_flip_an_existing_ai_generated_draft_to_false() {
    // "Once AI-generated, always AI-generated": a SECOND save for the same transcript that
    // is itself internally consistent (ai_generated: false, disclosure: None passes the
    // pairing check above on its own) must still be refused if it would downgrade a draft
    // that is ALREADY persisted as AI-generated — editing/regenerating text must never
    // un-label provenance.
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));

    // First save: a real AI-generated draft, persisted.
    let first = sample_draft();
    assert!(first.ai_generated);
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: first,
    });
    assert_eq!(
        store.saved_calls().len(),
        1,
        "positive control: the first save succeeded"
    );

    // Second save: internally consistent on its own, but would downgrade the existing draft.
    let mut downgrade = sample_draft();
    downgrade.ai_generated = false;
    downgrade.disclosure = None;
    downgrade.title = "Rewritten as if human-authored".into();
    let reply = c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: downgrade,
    });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Deny(selahcue_lan::protocol::DenyReason::BadRequest)
    ));
    assert_eq!(
        store.saved_calls().len(),
        1,
        "the downgrade attempt must never reach the store — only the first save should be there"
    );
}

#[test]
fn save_sermon_note_draft_can_be_resaved_ai_generated_when_no_draft_exists_yet() {
    // Positive control for the no-downgrade test above: with NO existing draft, there is
    // nothing to downgrade FROM, so any consistent pairing (including ai_generated: false)
    // must be accepted on a fresh transcript — this must not become "Save always refuses
    // ai_generated: false".
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));

    let mut draft = sample_draft();
    draft.ai_generated = false;
    draft.disclosure = None;
    let reply = c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 42,
        draft,
    });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteDraft {
            draft: Some(_),
            ..
        })
    ));
    assert_eq!(store.saved_calls().len(), 1);
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
// Regenerate-with-retention (FR-129, 86akgqdx8): `LiveController::apply`'s dispatch for
// Stage/Confirm/Discard, exercised against the SAME `SpyStore` used above — proving the
// commands reach the injected store with the exact payload and that the "prior draft
// survives a failed/refused attempt" acceptance criterion holds AT THIS LAYER (a store
// failure/refusal never mutates `persisted`).
// ---------------------------------------------------------------------------------------

#[test]
fn stage_sermon_note_regeneration_reaches_the_store_and_leaves_the_accepted_draft_untouched() {
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });

    let mut regenerated = sample_draft();
    regenerated.title = "Regenerated Title".into();
    let reply = c.apply(&Command::StageSermonNoteRegeneration {
        transcript_id: 7,
        draft: regenerated.clone(),
    });
    match reply {
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteRegenerationState {
            transcript_id,
            current,
            pending,
        }) => {
            assert_eq!(transcript_id, 7);
            assert_eq!(
                current.as_ref().unwrap().title,
                sample_draft().title,
                "the accepted (prior) draft reported back must be UNCHANGED"
            );
            assert_eq!(pending.as_ref().unwrap().title, "Regenerated Title");
        }
        other => panic!("expected SermonNoteRegenerationState, got {other:?}"),
    }
    assert_eq!(store.staged_calls(), vec![(7, regenerated)]);
    assert!(store.has_pending());
}

#[test]
fn stage_sermon_note_regeneration_with_no_accepted_draft_is_denied() {
    // Regenerate requires something to regenerate FROM.
    let mut c = controller();
    c.set_sermon_note_store(Box::new(SpyStore::new()));

    let reply = c.apply(&Command::StageSermonNoteRegeneration {
        transcript_id: 7,
        draft: sample_draft(),
    });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Deny(selahcue_lan::protocol::DenyReason::BadRequest)
    ));
}

#[test]
fn stage_sermon_note_regeneration_with_an_inconsistent_pairing_is_denied() {
    // Same FR-123/FR-128 integrity check as Save, applied to the pending draft.
    let mut c = controller();
    c.set_sermon_note_store(Box::new(SpyStore::new()));
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });

    let mut bad = sample_draft();
    bad.ai_generated = true;
    bad.disclosure = None;
    let reply = c.apply(&Command::StageSermonNoteRegeneration {
        transcript_id: 7,
        draft: bad,
    });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Deny(selahcue_lan::protocol::DenyReason::BadRequest)
    ));
}

#[test]
fn a_failed_stage_attempt_never_touches_the_accepted_draft() {
    // Direct proof, at the `LiveController` dispatch layer, of "a transport failure during
    // regenerate must not lose the prior draft": a store failure during Stage (standing in
    // for "generation succeeded but persistence failed", or any other refusal) leaves
    // `save_sermon_note_draft`'s already-persisted content completely alone.
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });
    store.fail_next_call();

    let reply = c.apply(&Command::StageSermonNoteRegeneration {
        transcript_id: 7,
        draft: sample_draft(),
    });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Deny(selahcue_lan::protocol::DenyReason::BadRequest)
    ));
    assert!(
        !store.has_pending(),
        "a refused/failed stage must not leave a pending row behind"
    );

    // The accepted draft is still exactly what it was — reachable via Load, over the SAME
    // command surface the operator console actually uses to display it.
    let reload = c.apply(&Command::LoadSermonNoteDraft { transcript_id: 7 });
    match reload {
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteDraft {
            draft: Some(view),
            ..
        }) => assert_eq!(view.title, sample_draft().title),
        other => panic!("expected the untouched accepted draft, got {other:?}"),
    }
}

#[test]
fn confirm_sermon_note_regeneration_replaces_the_accepted_draft() {
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store));
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });
    let mut regenerated = sample_draft();
    regenerated.title = "Regenerated Title".into();
    c.apply(&Command::StageSermonNoteRegeneration {
        transcript_id: 7,
        draft: regenerated,
    });

    let reply = c.apply(&Command::ConfirmSermonNoteRegeneration { transcript_id: 7 });
    match reply {
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteRegenerationState {
            transcript_id,
            current,
            pending,
        }) => {
            assert_eq!(transcript_id, 7);
            assert_eq!(current.as_ref().unwrap().title, "Regenerated Title");
            assert!(pending.is_none());
        }
        other => panic!("expected SermonNoteRegenerationState, got {other:?}"),
    }

    // The confirmed content is now what Load returns — single prior version, the old one
    // is gone.
    let reload = c.apply(&Command::LoadSermonNoteDraft { transcript_id: 7 });
    match reload {
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteDraft {
            draft: Some(view),
            ..
        }) => assert_eq!(view.title, "Regenerated Title"),
        other => panic!("expected the confirmed draft, got {other:?}"),
    }
}

#[test]
fn confirm_sermon_note_regeneration_with_nothing_pending_is_denied() {
    let mut c = controller();
    c.set_sermon_note_store(Box::new(SpyStore::new()));
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });

    let reply = c.apply(&Command::ConfirmSermonNoteRegeneration { transcript_id: 7 });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Deny(selahcue_lan::protocol::DenyReason::BadRequest)
    ));
}

#[test]
fn confirm_sermon_note_regeneration_cannot_downgrade_the_ai_generated_label() {
    // "Once AI-generated, always AI-generated" (PR #33 review, Sana N2), extended to
    // confirm — the exact scenario a degraded (local-fallback) regenerate produces.
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(), // ai_generated: true
    });
    let mut degraded = sample_draft();
    degraded.ai_generated = false;
    degraded.disclosure = None;
    degraded.title = "Offline outline".into();
    c.apply(&Command::StageSermonNoteRegeneration {
        transcript_id: 7,
        draft: degraded,
    });

    let reply = c.apply(&Command::ConfirmSermonNoteRegeneration { transcript_id: 7 });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Deny(selahcue_lan::protocol::DenyReason::BadRequest)
    ));
    // The accepted draft is untouched, and the pending draft STAYS staged (not silently
    // dropped) so the operator can still discard it themselves.
    assert!(store.has_pending());
    let reload = c.apply(&Command::LoadSermonNoteDraft { transcript_id: 7 });
    match reload {
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteDraft {
            draft: Some(view),
            ..
        }) => {
            assert_eq!(view.title, sample_draft().title);
            assert!(view.ai_generated);
        }
        other => panic!("expected the untouched accepted draft, got {other:?}"),
    }
}

#[test]
fn discard_sermon_note_regeneration_leaves_the_accepted_draft_unchanged() {
    let mut c = controller();
    let store = SpyStore::new();
    c.set_sermon_note_store(Box::new(store.clone()));
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });
    let mut regenerated = sample_draft();
    regenerated.title = "A regeneration nobody wanted".into();
    c.apply(&Command::StageSermonNoteRegeneration {
        transcript_id: 7,
        draft: regenerated,
    });

    let reply = c.apply(&Command::DiscardSermonNoteRegeneration { transcript_id: 7 });
    match reply {
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteRegenerationState {
            transcript_id,
            current,
            pending,
        }) => {
            assert_eq!(transcript_id, 7);
            assert_eq!(current.as_ref().unwrap().title, sample_draft().title);
            assert!(pending.is_none());
        }
        other => panic!("expected SermonNoteRegenerationState, got {other:?}"),
    }
    assert!(!store.has_pending());
}

#[test]
fn discard_sermon_note_regeneration_with_nothing_pending_is_a_harmless_success_positive_control() {
    // Idempotent — discarding when nothing was ever staged is not an error.
    let mut c = controller();
    c.set_sermon_note_store(Box::new(SpyStore::new()));
    c.apply(&Command::SaveSermonNoteDraft {
        transcript_id: 7,
        draft: sample_draft(),
    });

    let reply = c.apply(&Command::DiscardSermonNoteRegeneration { transcript_id: 7 });
    assert!(matches!(
        reply,
        selahcue_app::ControllerReply::Message(ServerMessage::SermonNoteRegenerationState {
            pending: None,
            ..
        })
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
    c.apply(&Command::StageSermonNoteRegeneration {
        transcript_id: 7,
        draft: sample_draft(),
    });
    c.apply(&Command::ConfirmSermonNoteRegeneration { transcript_id: 7 });
    c.apply(&Command::DiscardSermonNoteRegeneration { transcript_id: 7 });

    let after = c.snapshot(now);
    assert_eq!(
        before, after,
        "ControllerSnapshot must be completely unaffected by sermon-note draft persistence"
    );
}
