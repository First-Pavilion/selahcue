//! A durable store for generated sermon-note drafts (86akgqdv0; FR-123 "editable" half).
//!
//! PR #33's four-reviewer gate (Sana, F1 — High) found that the operator persisted a draft by
//! opening its OWN, differently-located SQLite file directly (`Database::open` against Tauri's
//! `app_data_dir()`), never the desktop's authoritative store (`data_dir()`). In a real launch
//! the operator's copy never has a real `transcript` row — only the desktop ever creates one —
//! so the whole persistence feature was inert outside a test harness that hardcoded a fake id.
//!
//! This module fixes it the same way 86akcfftu fixed the identical problem for the live
//! transcript store: the operator never opens `selahcue-data`'s file for this feature at all.
//! It sends LAN commands (`GetActiveTranscriptId`/`LoadSermonNoteDraft`/`SaveSermonNoteDraft`/
//! `UpdateSermonNoteDraft`); [`LiveController`](crate::LiveController) executes them against a
//! store IT holds, via [`SermonNoteStore`] — mirroring [`crate::transcript_sink::TranscriptSink`]
//! exactly: `selahcue-app` must not depend on `selahcue-data` (the crate graph runs the other
//! way — both `selahcue-desktop` and `selahcue-operator` depend on `selahcue-app` AND
//! `selahcue-data` as siblings), so this trait is the seam a binary crate implements against its
//! own `Database` + `sermon_note_repo`.
//!
//! **Regenerate-with-retention (FR-129, 86akgqdx8)** adds three more methods
//! (`stage_regeneration`/`confirm_regeneration`/`discard_regeneration`), the SAME seam
//! extended the same way: `LiveController` delegates to whatever store is wired in, a real
//! desktop-side implementation persists against `sermon_note_repo`'s new `pending_*` columns,
//! and [`NullSermonNoteStore`] answers honestly for a caller with no store configured. See
//! [`RegenerationSlot`] for the shared "current + pending" shape all three return.

use selahcue_lan::protocol::{SermonNoteDraftInput, SermonNoteDraftView, SermonNoteEditInput};

/// The sermon-note "slot" for a transcript after a stage/confirm/discard operation
/// (FR-129, 86akgqdx8) — mirrors [`selahcue_lan::protocol::ServerMessage::SermonNoteRegenerationState`]
/// minus the `transcript_id` (the caller already has it). `current` is the accepted draft;
/// `pending` is the not-yet-confirmed regeneration, `None` once nothing is staged.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct RegenerationSlot {
    pub current: Option<SermonNoteDraftView>,
    pub pending: Option<SermonNoteDraftView>,
}

/// A durable store for sermon-note drafts. [`LiveController`](crate::LiveController) holds one
/// as `Box<dyn SermonNoteStore>`, defaulting to [`NullSermonNoteStore`] — exactly like
/// [`crate::transcript_sink::TranscriptSink`]'s `NullTranscriptSink` default — for a caller with
/// no store configured (e.g. the operator's stand-alone in-process demo shell, `Backend::Local`:
/// no output window and no database shared with the desktop process that owns the real store).
///
/// Every method takes `&mut self` (not `&self`) even though the wrapped store is a single
/// SQLite connection — mirrors `TranscriptStoreWriter`'s own signature, for the same reason: a
/// real implementation may want interior mutability it does not have to expose (a retry
/// counter, a cached statement), and `LiveController` already serializes every call behind its
/// own `Arc<Mutex<_>>` in real wiring, so `&mut self` costs nothing extra.
pub trait SermonNoteStore: Send {
    /// Resolve the transcript id that new AI-derived content (a generated sermon-note draft)
    /// should attach to right now: the desktop's own `transcript_repo::most_recent_id`-shaped
    /// query (this crate does not depend on `selahcue-data`, so no intra-doc link here) — for a
    /// single-active-session desktop app, "the transcript this call is about" is the most
    /// recently STARTED one, whether it is still open or has already ended. `Ok(None)` if no
    /// transcript has ever been recorded. `Err` only for a genuine storage failure — never used
    /// to represent "nothing found", which is `Ok(None)`.
    fn active_transcript_id(&mut self) -> Result<Option<i64>, String>;
    /// Persist (upsert) a freshly generated draft against `transcript_id`. Returns the row
    /// re-read from the store on success — the source of truth, never an echo of the input.
    fn save_draft(
        &mut self,
        transcript_id: i64,
        draft: &SermonNoteDraftInput,
    ) -> Result<SermonNoteDraftView, String>;
    /// Load the persisted draft for `transcript_id`, if any. `Ok(None)` is the common, expected
    /// case (nothing generated yet, or the desktop store is unavailable) — never an error.
    fn load_draft(&mut self, transcript_id: i64) -> Result<Option<SermonNoteDraftView>, String>;
    /// Apply a text-only edit to the existing draft for `transcript_id`. An implementation
    /// returns `Err` (never panics) when no draft exists yet for this id, or the edit is
    /// refused (e.g. an oversized field) — [`LiveController::apply`](crate::LiveController::apply)
    /// turns that into [`crate::ControllerReply::Deny`] with
    /// [`selahcue_lan::protocol::DenyReason::BadRequest`].
    fn update_draft(
        &mut self,
        transcript_id: i64,
        edit: &SermonNoteEditInput,
    ) -> Result<SermonNoteDraftView, String>;

    /// Stage a freshly (re)generated draft against `transcript_id` WITHOUT replacing the
    /// currently-accepted draft (FR-129, 86akgqdx8). `Err` if no accepted draft exists yet
    /// for `transcript_id` — regenerate requires something to regenerate FROM; a true
    /// first-time generate goes through [`save_draft`](Self::save_draft) instead. A second
    /// call before the first is confirmed/discarded OVERWRITES the pending slot (single
    /// pending slot per transcript — see [`RegenerationSlot`]'s doc and
    /// `sermon_note_repo::stage_regeneration`'s for the full reasoning).
    fn stage_regeneration(
        &mut self,
        transcript_id: i64,
        draft: &SermonNoteDraftInput,
    ) -> Result<RegenerationSlot, String>;

    /// Accept the pending regeneration for `transcript_id`, replacing the accepted draft
    /// with it. `Err` if nothing is currently pending.
    fn confirm_regeneration(&mut self, transcript_id: i64) -> Result<RegenerationSlot, String>;

    /// Discard the pending regeneration for `transcript_id`, leaving the accepted draft
    /// unchanged. Never errors for "nothing was pending" — idempotent, mirroring
    /// `sermon_note_repo::discard_regeneration`.
    fn discard_regeneration(&mut self, transcript_id: i64) -> Result<RegenerationSlot, String>;
}

/// The default, no-op store. A caller with no real store configured sees exactly what the
/// operator's persistence-unavailable path already showed before this ticket: no active
/// transcript, no drafts, edits refused with an honest message — never a panic, never a silent
/// fabrication.
#[derive(Debug, Default, Clone, Copy)]
pub struct NullSermonNoteStore;

impl SermonNoteStore for NullSermonNoteStore {
    fn active_transcript_id(&mut self) -> Result<Option<i64>, String> {
        Ok(None)
    }
    fn save_draft(
        &mut self,
        _transcript_id: i64,
        _draft: &SermonNoteDraftInput,
    ) -> Result<SermonNoteDraftView, String> {
        Err("no sermon-note store is configured".into())
    }
    fn load_draft(&mut self, _transcript_id: i64) -> Result<Option<SermonNoteDraftView>, String> {
        Ok(None)
    }
    fn update_draft(
        &mut self,
        _transcript_id: i64,
        _edit: &SermonNoteEditInput,
    ) -> Result<SermonNoteDraftView, String> {
        Err("no sermon-note store is configured".into())
    }
    fn stage_regeneration(
        &mut self,
        _transcript_id: i64,
        _draft: &SermonNoteDraftInput,
    ) -> Result<RegenerationSlot, String> {
        Err("no sermon-note store is configured".into())
    }
    fn confirm_regeneration(&mut self, _transcript_id: i64) -> Result<RegenerationSlot, String> {
        Err("no sermon-note store is configured".into())
    }
    fn discard_regeneration(&mut self, _transcript_id: i64) -> Result<RegenerationSlot, String> {
        Err("no sermon-note store is configured".into())
    }
}
