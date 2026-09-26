//! A durable store for the bounded autosave-SLOT history (FR-005 "last-3"; ticket 86ajy0hxg).
//!
//! Mirrors [`crate::sermon_note_store::SermonNoteStore`] / [`crate::transcript_sink::TranscriptSink`]
//! exactly, for the same reason stated on both: `selahcue-app` must not depend on
//! `selahcue-data` (the crate graph runs the other way — `selahcue-desktop` depends on both as
//! siblings), so this trait is the seam a binary crate implements against its own `Database` +
//! `autosave_repo`. [`LiveController`](crate::LiveController) holds one as
//! `Box<dyn AutosaveStore>`, defaulting to [`NullAutosaveStore`] for a caller with no store
//! configured (e.g. the operator's stand-alone in-process demo shell).
//!
//! Scoped to the cheap, always-synchronous-safe read only ([`AutosaveStore::list_slots`] is a
//! query against a 3-row table). Resolving a specific slot's full snapshot — which means an
//! `integrity_check` over the WHOLE store (FR-079), potentially hundreds of milliseconds — is
//! deliberately NOT part of this seam: PR #102's performance review (Vera) found that the
//! earlier shape (a `load_slot` method here, called from `LiveController::apply()`) held the
//! `Mutex<LiveController>` the render/present loop locks every frame for that whole duration,
//! stalling audience output. `Command::RestoreAutosave` is now resolved entirely on the HOST
//! side (`selahcue-desktop`'s `SessionStore::load_autosave_slot` + `App::handle_pending_restore`,
//! its own `SessionStore` connection, outside any controller lock), which already depends on
//! `selahcue-data` directly and needs no seam.

/// One listed restore point — the wire-facing summary
/// ([`selahcue_lan::protocol::AutosaveSlotView`]'s source data), without the full snapshot
/// payload `ListAutosaveSlots` does not need to move over the wire.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AutosaveSlotSummary {
    pub slot: i64,
    pub saved_at_ms: i64,
    pub label: Option<String>,
}

/// A durable store for the autosave-slot ring's SUMMARY listing only (see the module doc for
/// why a full-slot read is not part of this seam). Takes `&mut self` — mirrors
/// `SermonNoteStore`'s own signature and reasoning: a real implementation may want interior
/// mutability it does not have to expose, and `LiveController` already serializes every call
/// behind its own `Arc<Mutex<_>>` in real wiring, so `&mut self` costs nothing extra.
pub trait AutosaveStore: Send {
    /// List slots newest-first. `Err` only for a genuine storage failure — an empty history is
    /// `Ok(Vec::new())`, never an error. Cheap: a query against a table bounded to
    /// `selahcue_data::autosave_repo::MAX_AUTOSAVE_SLOTS` rows, no integrity check — safe to
    /// call synchronously from [`LiveController::apply`](crate::LiveController::apply).
    fn list_slots(&mut self) -> Result<Vec<AutosaveSlotSummary>, String>;
}

/// The default no-op store: an empty history, nothing to restore. Matches
/// [`crate::sermon_note_store::NullSermonNoteStore`]'s degradation exactly.
pub struct NullAutosaveStore;

impl AutosaveStore for NullAutosaveStore {
    fn list_slots(&mut self) -> Result<Vec<AutosaveSlotSummary>, String> {
        Ok(Vec::new())
    }
}
